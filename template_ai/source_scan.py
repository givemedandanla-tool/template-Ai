"""Bounded reconciliation, versioned root configuration and candidate index in the existing SQLite."""
import fnmatch,time
from pathlib import Path
from .source_links import hash_source,ScanCancelled
from .source_discovery import discover_sources
from .training_store import digest
from .model import new_id
EXTENSIONS={'.ai','.pdf','.svg','.eps','.png','.jpg','.jpeg'}
DEFAULT_EXCLUDES=['.git/**','**/.git/**','.venv/**','**/.venv/**','~*','*.tmp','*.tmp.*','*.part','*.partial','*.bak','*.swp']


def active_roots(store):
    ids=[r[0] for r in store.db.execute("SELECT id FROM training_records WHERE kind='SCAN_ROOT' AND COALESCE(json_extract(payload,'$.archived'),0)=0 ORDER BY rowid LIMIT 21")]
    if len(ids)>20:raise ValueError('有效監看來源超過20，請先分組處理')
    return [store.get('SCAN_ROOT',identity) for identity in ids]


def options(extensions,excludes):
    extensions=sorted(set(EXTENSIONS if extensions is None else extensions));excludes=list(dict.fromkeys(excludes if excludes is not None else DEFAULT_EXCLUDES))
    if not extensions or any(e not in EXTENSIONS for e in extensions):raise ValueError('只選取明列支援格式')
    if len(excludes)>32 or any(not isinstance(p,str) or not p or len(p)>512 or Path(p).is_absolute() or '..' in p.split('/') or '\\' in p for p in excludes):raise ValueError('排除需最多32個相對路徑／檔名規則，不含上層或絕對路徑')
    return extensions,excludes


def register_root(store,path,recursive=False,*,extensions=None,excludes=None):
    root=Path(path).expanduser()
    if root.is_symlink() or not root.is_dir() or root.resolve()==Path(root.anchor) or str(path).startswith(('//','\\\\')):raise ValueError('需明列正常本機目錄；不選整個磁碟、symlink或網路分享')
    root=root.resolve();extensions,excludes=options(extensions,excludes);existing=active_roots(store)
    if len(existing)>=20:raise ValueError('最多20個有效來源根目錄')
    if any(r['path']==str(root) for r in existing):raise ValueError('此根目錄已登錄')
    owned=store.library.root
    if owned==root:raise ValueError('本程式資料庫目錄不可作為監看來源')
    if owned.is_relative_to(root):excludes.append(owned.relative_to(root).as_posix()+'/**')
    with store.transaction():return store._write('SCAN_ROOT',new_id(),dict(path=str(root),recursive=bool(recursive),extensions=extensions,excludes=excludes,mode='MANUAL_ONLY',enabled=False,archived=False,last_scan=None,last_success=None,requires_reconnect=False),0,'scan_root_added')


def configure_root(store,root,*,mode=None,enabled=None,recursive=None,extensions=None,excludes=None,archive=False):
    mode=mode or root.get('mode','MANUAL_ONLY')
    if mode not in ('MANUAL_ONLY','AUTO_PRECHECK'):raise ValueError('監看模式不支援')
    formats,patterns=options(root.get('extensions') if extensions is None else extensions,excludes if excludes is not None else root.get('excludes'))
    if any(v is not None and type(v) is not bool for v in (enabled,recursive)):raise ValueError('啟用／子資料夾需明確布林選擇')
    owned=store.library.root;directory=Path(root['path'])
    if owned==directory and enabled:raise ValueError('不可監看本程式資料目錄')
    if owned.is_relative_to(directory):
        protected=owned.relative_to(directory).as_posix()+'/**'
        if protected not in patterns:patterns.append(protected)
    formats,patterns=options(formats,patterns)
    if not isinstance(archive,bool):raise ValueError('移除狀態不合法')
    with store.transaction():
        now=store.get('SCAN_ROOT',root['id'])
        if now!=root:raise ValueError('來源根目錄版本已變更，請重新載入')
        now.update(mode=mode,enabled=bool(root.get('enabled') if enabled is None else enabled),recursive=bool(root.get('recursive') if recursive is None else recursive),extensions=formats,excludes=patterns,archived=archive,requires_reconnect=False)
        if archive:now.update(enabled=False,mode='MANUAL_ONLY')
        return store._write('SCAN_ROOT',now['id'],now,now['revision'],'scan_root_removed_without_data_deletion' if archive else 'scan_root_configuration_confirmed')



def known_sources(library,root):
    prefix=str(Path(root['path']).resolve())+__import__('os').sep
    rows=library.db.execute("SELECT s.id,COALESCE(l.current_path,s.original_path),s.hash,json_extract(s.payload,'$.page') FROM sources s LEFT JOIN source_links l ON l.source_id=s.id WHERE substr(COALESCE(l.current_path,s.original_path),1,?)=? ORDER BY s.id LIMIT 2001",(len(prefix),prefix)).fetchall()
    if len(rows)>2000:raise ValueError('單一來源根目錄登錄超過2000筆；請分組核對，未省略舊來源')
    known={}
    for sid,path,content,page in rows:
        item=known.setdefault(path,dict(hashes=[],sources=[]))
        if content not in item['hashes']:item['hashes'].append(content)
        item['sources'].append(dict(id=sid,hash=content,page=page))
    return known,digest(rows)


def scan_files(root,known,cancel=lambda:False,stable_wait=.25,progress=None,content_lookup=None):
    directory=Path(root['path']);prior={r['path']:r for r in (root.get('last_scan') or {}).get('entries',[])}
    if directory.is_symlink() or not directory.is_dir():return dict(state='ROOT_OFFLINE',entries=[],scanned_entries=0,complete=False,originals_modified=False,deletions_inferred=False)
    directory=directory.resolve();formats,patterns=options(root.get('extensions'),root.get('excludes'));rows=[];first=[];budgeted=0;read_bytes=0
    class Cancel:
        def is_set(self):return cancel()
    signal=Cancel();known_hashes={p:([v] if isinstance(v,str) else v.get('hashes',[v.get('hash')])) for p,v in known.items()};all_hashes={h for values in known_hashes.values() for h in values}
    def excluded(path):
        relative=path.relative_to(directory).as_posix();name=path.name
        return any(fnmatch.fnmatchcase(relative.casefold(),p.casefold()) or fnmatch.fnmatchcase(name.casefold(),p.casefold()) or fnmatch.fnmatchcase(relative.casefold()+'/',p.casefold()) for p in patterns)
    def visit(path,stat):
        nonlocal budgeted,read_bytes
        if path.suffix.lower() not in formats:return
        entry=dict(path=str(path),state='WAIT_STABLE',bytes=stat.st_size,registered_hashes=known_hashes.get(str(path),[]))
        if 2*stat.st_size+budgeted>256*1024*1024:raise ValueError('兩次內容核對超過256MiB實際讀取預算；請分組掃描')
        budgeted+=2*stat.st_size;rows.append(entry)
        try:
            proof=hash_source(path,cancel=signal,byte_limit=min(50_000_000,stat.st_size));read_bytes+=proof.stat[2]
            if not Path(proof.path).is_relative_to(directory):raise ValueError('檔案移出已授權根目錄，未採用')
            entry.update(hash=proof.hash);first.append((entry,proof))
        except ScanCancelled:raise
        except (OSError,ValueError) as error:entry.update(state='READ_ERROR',reason=str(error))
        if progress:progress(dict(stage='核對第一份內容',done=len(rows),total=None,path=str(path)))
    report=discover_sources([],directory,signal,max_entries=500,max_bytes=256*1024*1024,recursive=root.get('recursive',False),visit=visit,exclude=excluded)
    if report['status']=='CANCELLED':return dict(state='CANCELLED',entries=rows,scanned_entries=report['entries'],complete=False,originals_modified=False,deletions_inferred=False)
    end=time.monotonic()+max(.05,min(stable_wait,1.0))
    while time.monotonic()<end:
        if cancel():return dict(state='CANCELLED',entries=rows,scanned_entries=report['entries'],complete=False,originals_modified=False,deletions_inferred=False)
        time.sleep(.01)
    for index,(entry,proof) in enumerate(first):
        try:
            second=hash_source(entry['path'],cancel=signal,byte_limit=min(50_000_000,proof.stat[2]));read_bytes+=second.stat[2]
            if proof.hash!=second.hash or proof.stat!=second.stat:entry.update(state='WAIT_STABLE',reason='兩次內容／stat不同，不匯入');continue
            old=prior.get(entry['path']);registered=known_hashes.get(entry['path'],[]);previous=(old.get('hash') if old else None) or (registered[0] if len(registered)==1 else registered or None)
            state='UNCHANGED' if second.hash in registered or previous==second.hash else 'CONTENT_CHANGED_REVIEW_REQUIRED' if previous else 'DUPLICATE_ALIAS_KEEP_IDENTITY' if second.hash in all_hashes or (content_lookup and content_lookup(second.hash)) or any(x.get('hash')==second.hash and x['path']!=entry['path'] for x in rows) else 'NEW_CANDIDATE'
            entry.update(state=state,previous_hash=previous,verified_hash=second.hash,verified_stat=list(second.stat),registered=second.hash in registered,registered_source_ids=[v['id'] for v in (known.get(entry['path'],{}).get('sources',[]) if isinstance(known.get(entry['path']),dict) else []) if v['hash']==second.hash],
                         customer_code_candidate=Path(entry['path']).stem,artwork_count='UNKNOWN_UNTIL_PARSED')
        except ScanCancelled:return dict(state='CANCELLED',entries=rows,scanned_entries=report['entries'],complete=False,originals_modified=False,deletions_inferred=False)
        except (ValueError,OSError) as error:entry.update(state='WAIT_STABLE',reason=str(error))
        if progress:progress(dict(stage='核對第二份內容',done=index+1,total=len(first),path=entry['path']))
    enumeration_complete=report['status']=='COMPLETE'
    present={r['path'] for r in rows}
    if enumeration_complete:
        baseline={**prior,**{p:dict(path=p,hash=h[0] if len(h)==1 else h) for p,h in known_hashes.items()}}
        for path,old in baseline.items():
            p=Path(path)
            if p.is_relative_to(directory) and (root.get('recursive') or p.parent==directory) and not excluded(p) and p.suffix.lower() in formats and path not in present:
                rows.append(dict(path=path,hash=old.get('hash'),state='MISSING_OR_MOVED_REVIEW_REQUIRED',reason='本次完整範圍未找到；不是永久刪除，需定位或重試'))
    complete=enumeration_complete and all(r['state'] not in ('WAIT_STABLE','READ_ERROR','MISSING_OR_MOVED_REVIEW_REQUIRED') for r in rows)
    return dict(state='SCANNED' if complete else 'PARTIAL',entries=rows,scanned_entries=report['entries'],complete=complete,enumeration_complete=enumeration_complete,
                timestamp=time.time(),bytes_first_pass=sum(p.stat[2] for _,p in first),verified_hash_bytes=read_bytes,source_imported=False,originals_modified=False,deletions_inferred=False,
                directories=report.get('directories',[str(directory)]),excluded_entries=report.get('excluded_entries',0),errors=report['errors'],candidate_semantics='檔案未變不等於已匯入／已審；每個異名客戶獨立，解析作品數尚未知')


def candidate_id(root,path,content_hash):return digest(['SCAN_CANDIDATE',root['id'],path,content_hash])


def save_scan(store,root,result,*,automatic=False,cancel=lambda:False):
    with store.transaction():
        now=store.get('SCAN_ROOT',root['id'])
        if now!=root or now.get('archived'):raise ValueError('根目錄版本已變更，結果不套用')
        if automatic and (not now.get('enabled') or now.get('mode')!='AUTO_PRECHECK' or now.get('requires_reconnect')):raise ValueError('監看已停用／須重新連結，未建立自動候選')
        if result.get('source_index_digest') and known_sources(store.library,root)[1]!=result['source_index_digest']:raise ValueError('來源登錄索引在掃描期間已變更，未套用過期候選')
        now['latest_attempt']=result
        if result['state'] not in ('ROOT_OFFLINE','CANCELLED'):
            if result.get('enumeration_complete',result.get('complete')):now['last_scan']=result
            if result.get('complete'):now['last_success']=result['timestamp']
            for entry in result['entries']:
                if cancel():raise ScanCancelled()
                if not entry.get('verified_hash'):continue
                if entry.get('registered'):
                    item_id=candidate_id(root,entry['path'],entry['verified_hash']);existing=store.get('SCAN_CANDIDATE',item_id)
                    if existing and existing['state'] in ('FOUND_NOT_QUEUED','QUEUED_FOR_UI003_PREFLIGHT','DISPATCHED'):
                        existing.update(state='SOURCE_REGISTERED_REVIEW_PENDING',source_ids=entry.get('registered_source_ids',[]));store._write('SCAN_CANDIDATE',item_id,existing,existing['revision'],'candidate_source_registered_ownership_still_unreviewed')
                    continue
                stale_ids=[row[0] for row in store.db.execute("SELECT id FROM training_records WHERE kind='SCAN_CANDIDATE' AND json_extract(payload,'$.root_id')=? AND json_extract(payload,'$.path')=? AND json_extract(payload,'$.source_hash')!=? AND json_extract(payload,'$.state') IN ('FOUND_NOT_QUEUED','QUEUED_FOR_UI003_PREFLIGHT','REVIEW_REQUIRED')",(root['id'],entry['path'],entry['verified_hash']))]
                for stale_id in stale_ids:
                    stale=store.get('SCAN_CANDIDATE',stale_id);stale.update(state='STALE_SOURCE_CHANGED',replacement_hash=entry['verified_hash']);store._write('SCAN_CANDIDATE',stale_id,stale,stale['revision'],'source_candidate_changed_not_silently_reused')
                identity=candidate_id(root,entry['path'],entry['verified_hash']);old=store.get('SCAN_CANDIDATE',identity)
                if old:
                    if automatic and old['state']=='FOUND_NOT_QUEUED':
                        old.update(state='REVIEW_REQUIRED' if entry['state']=='CONTENT_CHANGED_REVIEW_REQUIRED' else 'QUEUED_FOR_UI003_PREFLIGHT',root_revision=root['revision']);store._write('SCAN_CANDIDATE',identity,old,old['revision'],'source_candidate_preflight_queue_enabled')
                    continue
                state='REVIEW_REQUIRED' if entry['state']=='CONTENT_CHANGED_REVIEW_REQUIRED' else 'QUEUED_FOR_UI003_PREFLIGHT' if automatic else 'FOUND_NOT_QUEUED'
                payload=dict(root_id=root['id'],root_revision=root['revision'],path=entry['path'],source_hash=entry['verified_hash'],bytes=entry['bytes'],verified_stat=entry['verified_stat'],state=state,
                             classification=entry['state'],previous_hash=entry.get('previous_hash'),created=time.time(),source_ids=[],artwork_count='UNKNOWN_UNTIL_PARSED',customer_ownership='UNREVIEWED',training_started=False)
                store._write('SCAN_CANDIDATE',identity,payload,0,'source_candidate_indexed_without_training')
        return store._write('SCAN_ROOT',now['id'],now,now['revision'],'source_automatic_scan_recorded' if automatic else 'source_manual_scan_recorded')


def candidate_page(store,root_id=None,offset=0,limit=50):
    if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=100:raise ValueError('候選需有效分頁')
    args=[];where="kind='SCAN_CANDIDATE'"
    if root_id:where+=" AND json_extract(payload,'$.root_id')=?";args.append(root_id)
    ids=[r[0] for r in store.db.execute('SELECT id FROM training_records WHERE '+where+' ORDER BY rowid LIMIT ? OFFSET ?',(*args,limit,offset))]
    return [store.get('SCAN_CANDIDATE',identity) for identity in ids]

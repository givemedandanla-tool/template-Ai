"""Authenticated relational bundles using SQLite backup and cryptography AESGCM.

Snapshots are isolated, bounded and never overwrite a running library. Font and
original-source inclusion need separate explicit local backup rights.
"""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
import sqlite3
import tempfile
import zipfile
import stat
import re
import time
from contextlib import closing
import sys
from importlib.metadata import version,PackageNotFoundError

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .secure_backup import key
from .safe_publish import publish_complete
from .background import file_digest

MAGIC=b'TABI2'
MAX_BYTES=256*1024*1024
MAX_FILES=5000
from .asset_references import PATH_KEYS,is_asset_path
ACTIVE_JSON={'sources','templates','logos','font_assets','artworks','training_records','runtime_requests'}
REQUIRED_TABLES={'sources','contents','templates','logos','font_assets','source_links'}


def _json(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()


def schema_fingerprint(db):
    rows=list(db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"))
    return hashlib.sha256(_json(rows)).hexdigest()


def application_fingerprint():
    package=Path(__file__).parent;files={}
    for path in sorted(package.glob('*.py')):
        if path.is_file() and not path.is_symlink():files[path.name]=file_digest(path)
    lock=package.parent/'requirements-lock.txt'
    if lock.is_file():files['requirements-lock.txt']=file_digest(lock)
    return hashlib.sha256(_json(files)).hexdigest()


def runtime_versions():
    packages={}
    for name in ('PySide6','cryptography','pypdf','phonenumbers','kiwisolver','fonttools'):
        try:packages[name]=version(name)
        except PackageNotFoundError:packages[name]='UNKNOWN'
    return dict(python='.'.join(map(str,sys.version_info[:3])),sqlite=sqlite3.sqlite_version,packages=packages,
                external_tools='OS/fonts/Inkscape/Tesseract/runtime base models require separate supported setup; not installed by restore')


def _integrity(db):
    if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():
        raise ValueError('SQLite完整性／外鍵檢查未通過')


def _tables(db):
    if db.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view')").fetchone():
        raise ValueError('此備份格式不支援自訂trigger/view，保持隔離不啟用')
    tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not REQUIRED_TABLES<=tables:raise ValueError('備份資料庫缺少必要schema，不能啟用')
    return tables


def _active_rows(db,table):
    if table=='training_records':
        return db.execute("SELECT rowid,kind,payload,revision,id FROM training_records WHERE kind NOT IN ('SCAN_ROOT','BACKUP_HISTORY','BACKUP_SCHEDULE')")
    return db.execute('SELECT rowid,NULL,payload,NULL,NULL FROM '+table)


def _portable_member(name):
    path=PurePosixPath(name)
    if path.as_posix()!=name or path.is_absolute() or '\\' in name or any(part in ('..','.') for part in path.parts):return False
    for part in path.parts:
        if part.endswith(('.', ' ')) or any(ord(c)<32 or c in '<>:"|?*' for c in part):return False
        if part.split('.')[0].upper() in {'CON','PRN','AUX','NUL'}|{f'{p}{i}' for p in ('COM','LPT') for i in range(1,10)}:return False
    return True


def _references(value,key_name=''):
    if isinstance(value,dict):
        for k,v in value.items():yield from _references(v,k)
    elif isinstance(value,list):
        for v in value:yield from _references(v,key_name)
    elif is_asset_path(key_name,value):yield value


def _snapshot(library,path):
    if library.db.in_transaction:raise ValueError('目前有未完成交易，先完成交易再備份')
    if library.db.execute('PRAGMA page_count').fetchone()[0]*library.db.execute('PRAGMA page_size').fetchone()[0]>MAX_BYTES:raise ValueError('資料庫超過256MiB本次工具預算，未開始複製')
    with closing(sqlite3.connect(path)) as destination, destination:
        library.db.backup(destination)
        _integrity(destination)
    return file_digest(path)


def _stage(cancel,progress,phase,**facts):
    if cancel():raise ValueError('已取消；保留現行資料，不發布半成品')
    if progress:progress(dict(phase=phase,**facts))


def plan_backup(library,include_sources=False,include_fonts=False,limit_bytes=64*1024*1024,
                customers=True,templates=True,training=True,cancel=lambda:False,progress=None):
    _stage(cancel,progress,'PLAN_VERIFY',verified_assets=0)
    if type(limit_bytes) is not int or not 1_048_576<=limit_bytes<=MAX_BYTES:raise ValueError('備份預算需為1至256MiB')
    if not all(type(v) is bool for v in (include_sources,include_fonts,customers,templates,training)):raise ValueError('範圍需明確勾選')
    if library.db.execute('PRAGMA page_count').fetchone()[0]*library.db.execute('PRAGMA page_size').fetchone()[0]>limit_bytes:raise ValueError('資料庫超過所選預算，未開始封裝')
    if not all((customers,templates,training)):
        return dict(state='BLOCKED_DATABASE_CATEGORY_DEPENDENCY',reasons=['客戶、版型、來源／訓練共用外鍵；目前需同一一致性資料庫快照，不提供會斷關聯的分類裁切'],complete=False)
    entries=[];sources=[];notes=[];total=0
    root=library.root.resolve();assets=library.assets.resolve()
    def add(path,member,required=True):
        nonlocal total
        _stage(cancel,progress,'PLAN_VERIFY',verified_assets=len(entries))
        path=Path(path)
        if path.is_symlink() or not path.is_file():
            notes.append(dict(path=str(path),state='MISSING_OR_SYMLINK',required=required));return None
        size=path.stat().st_size
        if size>limit_bytes-total:raise ValueError('資產總量超出本次備份預算，未省略必要檔案；請提高預算或另選明確部分範圍')
        proof=dict(origin=str(path.resolve()),member=member,bytes=size,sha256=file_digest(path),required=required)
        total+=size;entries.append(proof)
        if len(entries)>MAX_FILES:raise ValueError('單包超過5000檔案，請分段處理')
        return proof
    for base,dirs,names in os.walk(assets,followlinks=False):
        kept=[]
        for directory in sorted(dirs):
            path=Path(base)/directory
            if path.is_symlink():notes.append(dict(path=str(path),state='SYMLINK_DIRECTORY_NOT_PACKED',required=True))
            else:kept.append(directory)
        dirs[:]=kept
        for name in sorted(names):
            path=Path(base)/name;relative=path.relative_to(assets)
            if ('fonts' in relative.parts or path.suffix.lower() in ('.ttf','.otf','.ttc')) and not include_fonts:
                notes.append(dict(path=str(path),state='FONT_BACKUP_RIGHTS_NOT_CONFIRMED',required=True));continue
            add(path,'assets/'+relative.as_posix())
    for source_id,original,payload,current in library.db.execute(
            'SELECT s.id,s.original_path,s.payload,COALESCE(l.current_path,s.original_path) FROM sources s LEFT JOIN source_links l ON l.source_id=s.id ORDER BY s.id'):
        _stage(cancel,progress,'PLAN_VERIFY',verified_assets=len(entries),source_registrations=len(sources))
        metadata=json.loads(payload)
        item=dict(id=source_id,original_path=original,current_path=current,hash=metadata['hash'],included=False)
        if include_sources:
            path=Path(current);suffix=path.suffix.lower()
            if suffix not in ('.ai','.pdf','.svg','.eps','.png','.jpg','.jpeg'):suffix='.bin'
            # Canonical bytes can be shared while registrations and names remain independent.
            member='originals/'+metadata['hash']
            proof=next((p for p in entries if p['member']==member),None)
            if proof is None:proof=add(path,member)
            else:
                if not path.is_file() or path.is_symlink() or file_digest(path)!=metadata['hash']:raise ValueError('異名來源內容已變更，不能用另一檔的相同舊指紋冒充')
            if proof:
                if proof['sha256']!=metadata['hash']:raise ValueError('來源內容已變更，先重新核對')
                item.update(included=True,member=member,suffix=suffix)
        else:notes.append(dict(source_id=source_id,path=current,state='ORIGINAL_BACKUP_RIGHTS_NOT_CONFIRMED',required=True))
        sources.append(item)
        if len(sources)>MAX_FILES:raise ValueError('來源登錄超過5000筆本次備份預算，未截斷清單')
    known={item['origin'] for item in entries}
    references=set()
    for table in sorted(ACTIVE_JSON & _tables(library.db)):
        for _,kind,payload,_,_ in _active_rows(library.db,table):
            references.update(_references(json.loads(payload)))
            if len(references)>MAX_FILES:raise ValueError('有效資產參照超過5000筆預算，未截斷')
    for reference in sorted(references):
        path=Path(reference)
        if str(path.resolve()) in known:continue
        if reference in {s['current_path'] for s in sources}:continue  # Source rights already explicit above.
        font=path.suffix.lower() in ('.ttf','.otf','.ttc')
        if font and not include_fonts or not font and not include_sources:
            notes.append(dict(path=reference,state='EXTERNAL_ASSET_RIGHTS_NOT_CONFIRMED',required=True));continue
        if path.is_symlink() or not path.is_file():notes.append(dict(path=reference,state='REFERENCED_ASSET_MISSING',required=True));continue
        content=file_digest(path);suffix=path.suffix.lower()
        if not re.fullmatch(r'\.[a-z0-9]{1,8}',suffix):suffix='.bin'
        member='external/'+content+suffix
        item=next((p for p in entries if p['member']==member),None)
        if item is None:item=add(path,member)
        if item:known.add(str(path.resolve()))
        # Multiple paths with identical bytes still need their own relocation mapping.
        if item and item['origin']!=str(path.resolve()):entries.append(dict(item,origin=str(path.resolve()),alias_of=item['origin']))
    if len(entries)>MAX_FILES:raise ValueError('資產映射超過5000筆預算，未截斷')
    member_names={e['member'] for e in entries}
    if any(not _portable_member(name) for name in member_names) or len({name.casefold() for name in member_names})!=len(member_names):raise ValueError('資產檔名無法安全移轉Windows，請先處理大小寫／保留名稱衝突')
    options=dict(include_sources=include_sources,include_fonts=include_fonts,limit_bytes=limit_bytes,customers=customers,templates=templates,training=training)
    with tempfile.TemporaryDirectory(prefix='template-ai-backup-plan-') as temporary:
        probe=Path(temporary)/'snapshot.sqlite3';database_sha256=_snapshot(library,probe);database_bytes=probe.stat().st_size
        with closing(sqlite3.connect(probe.resolve().as_uri()+'?mode=ro',uri=True)) as db:schema_sha256=schema_fingerprint(db)
    if database_bytes+total>limit_bytes:raise ValueError('資料庫加資產超過所選預算，請調整範圍／預算')
    result=dict(schema=2,state='PLANNED',library_root=str(root),entries=entries,sources=sources,notes=notes,
                database_sha256=database_sha256,database_bytes=database_bytes,
                schema_sha256=schema_sha256,application_code_sha256=application_fingerprint(),runtime=runtime_versions(),
                estimated_extra_memory_bytes=4*(database_bytes+total)+4*1024*1024,
                estimated_stage_disk_bytes=2*database_bytes+total+4*1024*1024,
                complete=not notes,scope='FULL_RELATIONAL_BUNDLE' if not notes else 'PARTIAL_RELATIONAL_BUNDLE',
                asset_bytes=total,limit_bytes=limit_bytes,options=options,
                encryption='AES-256-GCM / scrypt N=16384 r=8 p=1; unique salt and nonce',
                password_stored=False,test_restore=False,formal_output_revalidation_required=True)
    result['sha256']=hashlib.sha256(_json(result)).hexdigest();return result


def create_backup(library,target,password,plan,approved=False,allow_partial=False,cancel=lambda:False,progress=None):
    target=Path(target)
    if not approved:raise ValueError('先核對範圍、個資／來源／字型保存權利與目的地')
    if plan.get('state')!='PLANNED':raise ValueError('備份範圍被關聯依賴阻擋')
    if not plan['complete'] and not allow_partial:raise ValueError('部分備份不能完整離線還原；需明確核准部分範圍')
    if not target.parent.is_dir() or target.exists():raise FileExistsError('請選存在資料夾中的新備份檔，不覆寫')
    if target.resolve().is_relative_to(library.assets.resolve()):raise ValueError('備份位置不能放入目前資產目錄，避免遞迴封裝備份本身')
    if shutil.disk_usage(target.parent).free<plan['estimated_stage_disk_bytes']:raise ValueError('備份位置可用空間低於暫存保守估計，未開始寫入')
    fresh=plan_backup(library,**plan['options'],cancel=cancel,progress=progress)
    if fresh!=plan:raise ValueError('預覽後資產／來源已變更，先重新預覽')
    version=library.db.execute('PRAGMA data_version').fetchone()[0];changes=library.db.total_changes
    with tempfile.TemporaryDirectory(prefix='.backup-stage-',dir=target.parent) as temporary:
        temporary=Path(temporary);database=temporary/'library.sqlite3'
        _stage(cancel,progress,'DATABASE_SNAPSHOT')
        database_hash=_snapshot(library,database);database_size=database.stat().st_size
        if database_hash!=plan['database_sha256']:raise ValueError('預覽後客戶／版型／模型或規則已更新，先重新預覽')
        if database_size+plan['asset_bytes']>plan['limit_bytes']:raise ValueError('一致性資料庫加資產超出預算，未建立半份成功備份')
        manifest=dict(plan,database_sha256=database_hash,database_bytes=database_size,application='template-Ai/v0.1')
        payload=io.BytesIO()
        with zipfile.ZipFile(payload,'w',compression=zipfile.ZIP_STORED) as archive:
            archive.write(database,'library.sqlite3')
            packed=set();pack_total=len({e['member'] for e in plan['entries']})
            for item in plan['entries']:
                _stage(cancel,None,'PACK_ASSETS')
                if item['member'] not in packed:archive.write(item['origin'],item['member']);packed.add(item['member'])
                if file_digest(item['origin'])!=item['sha256']:raise ValueError('封裝期間資產變更，備份未發布')
                _stage(cancel,progress,'PACK_ASSETS',completed=len(packed),total=pack_total)
            archive.writestr('manifest.json',_json(manifest))
        plain=payload.getvalue()
        if len(plain)>plan['limit_bytes']+2*1024*1024:raise ValueError('封裝資料超出預算')
        _stage(cancel,progress,'ENCRYPT',payload_bytes=len(plain))
        salt=os.urandom(16);nonce=os.urandom(12);derived=key(password,salt)
        blob=MAGIC+salt+nonce+AESGCM(derived).encrypt(nonce,plain,MAGIC)
        expected_archive_hash=hashlib.sha256(blob).hexdigest()
        _stage(cancel,progress,'AUTHENTICATE',encrypted_bytes=len(blob))
        if AESGCM(derived).decrypt(nonce,blob[33:],MAGIC)!=plain:raise ValueError('加密自我驗證失敗')
        fd,name=tempfile.mkstemp(prefix='.backup-complete-',dir=target.parent)
        staged=Path(name)
        try:
            with os.fdopen(fd,'wb') as stream:stream.write(blob);stream.flush();os.fsync(stream.fileno())
            if file_digest(staged)!=expected_archive_hash:raise ValueError('寫入的加密備份與驗證內容不符，未發布')
            def unchanged():
                _stage(cancel,progress,'PUBLISH_VERIFY')
                if library.db.total_changes!=changes or library.db.execute('PRAGMA data_version').fetchone()[0]!=version:raise ValueError('備份期間資料庫更新，請重建一致性快照')
                if plan_backup(library,**plan['options'],cancel=cancel)!=plan:raise ValueError('發布前資產改版，備份未發布')
            publish_complete(staged,target,unchanged)
        finally:staged.unlink(missing_ok=True)
    if target.stat().st_size!=len(blob) or file_digest(target)!=expected_archive_hash:raise ValueError('發布後檔案已變更；不列成功、不刪除該檔，請另行核對')
    return dict(scope=plan['scope'],state='CREATED_AUTHENTICATED',path=str(target),bytes=target.stat().st_size,
                sha256=expected_archive_hash,asset_files=len(plan['entries']),sources_included=sum(s['included'] for s in plan['sources']),
                complete=plan['complete'],test_restore=False,production_ready=False)


def read_bundle(archive,password):
    archive=Path(archive)
    if archive.is_symlink() or not archive.is_file() or archive.stat().st_size>MAX_BYTES+4*1024*1024:raise ValueError('備份檔案不可用或超過支援大小')
    blob=archive.read_bytes()
    if not blob.startswith(MAGIC) or len(blob)<49:raise ValueError('不是支援的完整關聯備份格式')
    try:plain=AESGCM(key(password,blob[5:21])).decrypt(blob[21:33],blob[33:],MAGIC)
    except Exception as error:raise ValueError('密碼錯誤或備份損壞；未修改目前資料') from error
    archive=zipfile.ZipFile(io.BytesIO(plain))
    members=archive.infolist()
    if len(members)>MAX_FILES+2 or len({m.filename.casefold() for m in members})!=len(members) or sum(m.file_size for m in members)>MAX_BYTES+2*1024*1024:
        raise ValueError('封裝重複檔名、數量或大小不合法')
    for member in members:
        path=PurePosixPath(member.filename)
        if not _portable_member(member.filename) or member.is_dir() or stat.S_ISLNK(member.external_attr>>16) or member.compress_type!=zipfile.ZIP_STORED:
            raise ValueError('封裝路徑／格式不合法，保持隔離')
    if archive.getinfo('manifest.json').file_size>8*1024*1024:raise ValueError('Manifest超出8MiB預算')
    manifest=json.loads(archive.read('manifest.json'))
    if manifest.get('schema')!=2 or manifest.get('application')!='template-Ai/v0.1':raise ValueError('不支援的備份schema／應用版本')
    expected={'manifest.json','library.sqlite3'}|{r['member'] for r in manifest['entries']}
    if expected!={m.filename for m in members}:raise ValueError('Manifest檔案清單不符')
    if any(not r['member'].startswith(('assets/','originals/','external/')) for r in manifest['entries']):raise ValueError('Manifest資產類型不合法')
    by_member={r['member']:r for r in manifest['entries']}
    for source in manifest['sources']:
        if source['included'] and (source.get('member') not in by_member or by_member[source['member']]['sha256']!=source['hash'] or source.get('suffix') not in ('.ai','.pdf','.svg','.eps','.png','.jpg','.jpeg','.bin')):raise ValueError('來源映射／格式不合法')
    checks=[dict(member='library.sqlite3',bytes=manifest['database_bytes'],sha256=manifest['database_sha256'])]+manifest['entries'];checked={}
    for entry in checks:
        proof=(entry['bytes'],entry['sha256'])
        if entry['member'] in checked:
            if checked[entry['member']]!=proof:raise ValueError('別名資產對同一內容成員提供衝突指紋')
            continue
        data=archive.read(entry['member'])
        if len(data)!=entry['bytes'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:raise ValueError('備份內容hash／大小不符')
        checked[entry['member']]=proof
    return archive,manifest


def _rewrite(value,mapping,key_name=''):
    if isinstance(value,dict):return {k:_rewrite(v,mapping,k) for k,v in value.items()}
    if isinstance(value,list):return [_rewrite(v,mapping,key_name) for v in value]
    if isinstance(value,str) and (key_name in PATH_KEYS or key_name.endswith('_path')) and key_name!='original_path':return mapping.get(value,value)
    return value


def inspect_restore(archive,password,trusted=False,existing_root=None,cancel=lambda:False):
    """Compare full table counts through SQLite; details are bounded, no writes."""
    if not trusted:raise ValueError('先確認備份來源可信及有權檢視資料')
    archive_pin=file_digest(archive);package,manifest=read_bundle(archive,password);rows=[]
    try:
        with tempfile.TemporaryDirectory(prefix='template-ai-restore-preview-') as temporary:
            probe=Path(temporary)/'preview.sqlite3';probe.write_bytes(package.read('library.sqlite3'))
            db=sqlite3.connect(probe.resolve().as_uri()+'?mode=ro',uri=True)
            try:
                db.execute('PRAGMA trusted_schema=OFF');tables=_tables(db);_integrity(db)
                current_tables=set()
                if existing_root is not None:
                    current=Path(existing_root)/'library.sqlite3'
                    if current.is_symlink() or not current.is_file():raise ValueError('目前環境資料庫失聯，不能假稱已完成差異預覽')
                    db.execute('ATTACH DATABASE ? AS current',(current.resolve().as_uri()+'?mode=ro',))
                    current_tables={r[0] for r in db.execute("SELECT name FROM current.sqlite_master WHERE type='table'")}
                def row_digest(*values):
                    clean=[{'blob_sha256':hashlib.sha256(v).hexdigest()} if isinstance(v,bytes) else v for v in values]
                    return hashlib.sha256(_json(clean)).hexdigest()
                db.create_function('restore_row_digest',-1,row_digest,deterministic=True)
                deadline=time.monotonic()+30
                db.set_progress_handler(lambda:int(cancel() or time.monotonic()>deadline),10000)
                db.execute('BEGIN')
                for table in sorted((tables|current_tables)-{'sqlite_sequence','sqlite_stat1','sqlite_stat4'}):
                    _stage(cancel,None,'RESTORE_COMPARE')
                    if not re.fullmatch(r'[a-z][a-z0-9_]*',table):raise ValueError('資料表名稱不屬支援格式，保持隔離')
                    backup_count=db.execute('SELECT count(*) FROM main.'+table).fetchone()[0] if table in tables else 0
                    current_count=db.execute('SELECT count(*) FROM current.'+table).fetchone()[0] if table in current_tables else 0
                    item=dict(category=table,backup_rows=backup_count,current_rows=current_count,
                              state='BACKUP_ONLY' if table not in current_tables else 'CURRENT_ONLY' if table not in tables else 'NOT_COMPARED',
                              different_rows=None,only_backup=None,only_current=None,examples=[])
                    if table in tables and table in current_tables:
                        columns=list(db.execute('PRAGMA main.table_info('+table+')'));other=list(db.execute('PRAGMA current.table_info('+table+')'))
                        if [(c[1],c[2],c[5]) for c in columns]!=[(c[1],c[2],c[5]) for c in other]:item['state']='SCHEMA_DIFFERENT'
                        else:
                            names=[c[1] for c in columns];pk=[c[1] for c in sorted(columns,key=lambda r:r[5]) if c[5]]
                            if not pk:pk=['rowid']
                            if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',c) for c in names+pk):raise ValueError('欄位名稱不屬支援格式')
                            quote=lambda name:'"'+name+'"'
                            joins=' AND '.join('a.'+quote(c)+'=b.'+quote(c) for c in pk)
                            missing='a.'+quote(pk[0])+' IS NULL';missing_b='b.'+quote(pk[0])+' IS NULL'
                            left='restore_row_digest('+','.join('a.'+quote(c) for c in names)+')'
                            right='restore_row_digest('+','.join('b.'+quote(c) for c in names)+')'
                            common=' FROM main.'+table+' a JOIN current.'+table+' b ON '+joins+' WHERE '+left+'<>'+right
                            item.update(different_rows=db.execute('SELECT count(*)'+common).fetchone()[0],
                                only_backup=db.execute('SELECT count(*) FROM main.'+table+' a LEFT JOIN current.'+table+' b ON '+joins+' WHERE '+missing_b).fetchone()[0],
                                only_current=db.execute('SELECT count(*) FROM current.'+table+' b LEFT JOIN main.'+table+' a ON '+joins+' WHERE '+missing).fetchone()[0])
                            item['examples']=[list(r) for r in db.execute('SELECT '+','.join('a.'+quote(c) for c in pk)+common+' LIMIT 20')]
                            item['state']='IDENTICAL_ROWS' if not any(item[k] for k in ('different_rows','only_backup','only_current')) else 'DIFFERENT_REQUIRES_REVIEW'
                    rows.append(item)
            except sqlite3.OperationalError as error:
                if 'interrupted' in str(error):raise ValueError('差異預覽取消或超出30秒預算，未宣稱全面核對') from error
                raise
            finally:db.close()
    finally:package.close()
    if file_digest(archive)!=archive_pin:raise ValueError('預覽期間備份檔已改變，請重新核對')
    return dict(state='RESTORE_PREVIEW',mode='NEW_ISOLATED_COPY' if existing_root is None else 'EXISTING_ENVIRONMENT_COMPARE_NEW_ISOLATED_COPY',
                archive=str(archive),archive_sha256=archive_pin,scope=manifest['scope'],complete=manifest['complete'],
                database_rows=rows,missing_or_external=manifest['notes'],included_assets=len({e['member'] for e in manifest['entries']}),
                sources_included=sum(s['included'] for s in manifest['sources']),
                existing_environment_modified=False,automatic_merge=False,formal_output_revalidation_required=True)


def restore_bundle(archive,target,password,trusted=False,allow_partial=False,cancel=lambda:False,progress=None,expected_archive_sha256=None):
    target=Path(target)
    if not trusted:raise ValueError('先確認備份來源可信及有權還原個資／資產')
    if target.exists() or target.is_symlink() or not target.parent.is_dir():raise FileExistsError('預設只還原到不存在的新目錄，不覆蓋現行環境')
    _stage(cancel,progress,'RESTORE_AUTHENTICATE')
    archive_pin=file_digest(archive);package,manifest=read_bundle(archive,password)
    if expected_archive_sha256 is not None and archive_pin!=expected_archive_sha256:package.close();raise ValueError('備份檔與已核對預覽不同，未還原')
    if not manifest['complete'] and not allow_partial:raise ValueError('此包缺少必要外部資產，僅可明確選擇隔離的部分還原')
    with tempfile.TemporaryDirectory(prefix='.restore-check-',dir=target.parent) as temporary:
        stage=Path(temporary)/'restored-library';stage.mkdir(mode=0o700)
        mapping={}
        for item in manifest['entries']:
            _stage(cancel,progress,'RESTORE_EXTRACT',completed=len(mapping),total=len(manifest['entries']))
            destination=stage/item['member'];destination.parent.mkdir(parents=True,exist_ok=True)
            if not destination.exists():destination.write_bytes(package.read(item['member']))
            mapping[item['origin']]=str(target/'restored-library'/item['member'])
        (stage/'library.sqlite3').write_bytes(package.read('library.sqlite3'))
        current_sources={}
        for source in manifest['sources']:
            if not source['included']:continue
            sid=source['id']
            if not isinstance(sid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',sid):raise ValueError('來源識別碼不能作為安全移轉路徑')
            name='source-files/source-'+hashlib.sha256(sid.encode()).hexdigest()+source['suffix'];destination=stage/name;destination.parent.mkdir(exist_ok=True)
            os.link(stage/source['member'],destination)
            current_sources[sid]=str(target/'restored-library'/name)
            mapping[source['current_path']]=current_sources[sid]
        migrated={}
        with closing(sqlite3.connect(stage/'library.sqlite3')) as db, db:
            _stage(cancel,progress,'RESTORE_RELATIONS')
            db.execute('PRAGMA trusted_schema=OFF');db.execute('PRAGMA foreign_keys=ON');tables=_tables(db);_integrity(db)
            if manifest.get('schema_sha256') and schema_fingerprint(db)!=manifest['schema_sha256']:raise ValueError('Manifest與資料庫schema版本指紋不符，保持隔離')
            training_changed=False
            for table in sorted(ACTIVE_JSON & tables):
                columns={r[1] for r in db.execute('PRAGMA table_info('+table+')')}
                if 'payload' not in columns:raise ValueError('不支援的資料表schema：'+table)
                if table=='training_records':rows=db.execute('SELECT rowid,kind,payload,revision,id FROM training_records').fetchall()
                else:rows=list(_active_rows(db,table))
                for identity,kind,payload,revision,record_id in rows:
                    old=json.loads(payload);new=_rewrite(old,mapping)
                    if table=='logos' and new.get('managed_logo'):new['restore_revalidation_required']=True
                    if table=='runtime_requests':
                        new.update(consent_session=None,consent_owner=None,owner=None,restore_state='EXPLICIT_RESUME_REQUIRED')
                        if new.get('state') in ('WAITING','RUNNING','PAUSED_RESOURCES'):new['state']='INTERRUPTED'
                    if table=='templates' and new.get('background'):new['background']['restore_revalidation_required']=True
                    if kind=='SCAN_ROOT':new.update(mode='MANUAL_ONLY',enabled=False,restore_state='RECONNECT_REQUIRED')
                    if kind=='WORKER' and new.get('active'):new.update(active=False,owner=None,restore_state='INTERRUPTED')
                    if kind in ('JOB','AUTO_JOB','EVAL_JOB','AUTO_UNIT','TRAINING_JOB','TRAINING_UNIT'):
                        if new.get('phase')=='RUNNING':new.update(phase='INTERRUPTED',owner=None,cancel_requested=False)
                        if kind=='EVAL_JOB':new.update(owner=None,owner_token=None,restore_state='EXPLICIT_RESUME_REQUIRED')
                        if kind=='AUTO_JOB' and new.get('operation')=='SEMANTIC_REPAIR_CANDIDATE':new.update(owner=None,restore_state='EXPLICIT_RESUME_REQUIRED')
                        if new.get('state')=='RUNNING':new['state']='INTERRUPTED'
                        for item in new.get('items',[]):
                            if item.get('state')=='RUNNING':item['state']='INTERRUPTED'
                    if table=='templates':
                        old_hash=hashlib.sha256(_json(old)).hexdigest();new_hash=hashlib.sha256(_json(new)).hexdigest();migrated[old_hash]=new_hash
                    if new!=old:
                        if table=='training_records':
                            training_changed=True
                            db.execute('UPDATE training_records SET payload=?,revision=revision+1 WHERE rowid=?',(_json(new).decode(),identity))
                            db.execute('INSERT INTO training_history VALUES(?,?,?,?,?,?,?)',(kind,record_id,revision+1,'restore_isolated_revalidation_required',payload,_json(new).decode(),time.time()))
                        else:db.execute('UPDATE '+table+' SET payload=? WHERE rowid=?',(_json(new).decode(),identity))
            if training_changed and 'training_meta' in tables:db.execute('UPDATE training_meta SET epoch=epoch+1 WHERE id=1')
            # Imported operational receipts do not authorize deleting files on the
            # old machine. A new host must explicitly configure its own schedule.
            from .backup_policy import SCHEDULE,HISTORY
            record=db.execute('SELECT value FROM preferences WHERE key=?',(SCHEDULE,)).fetchone()
            if record:
                value=json.loads(record[0]);value.update(enabled=False,state='RESTORE_RECONFIGURATION_REQUIRED',revision=value.get('revision',0)+1)
                db.execute('UPDATE preferences SET value=? WHERE key=?',(_json(value).decode(),SCHEDULE))
            record=db.execute('SELECT value FROM preferences WHERE key=?',(HISTORY,)).fetchone()
            if record:
                values=json.loads(record[0])
                for value in values:value.update(owned_by_app=False,restore_receipt_only=True)
                db.execute('UPDATE preferences SET value=? WHERE key=?',(_json(values).decode(),HISTORY))
            for sid,path in current_sources.items():
                db.execute('INSERT INTO source_links VALUES(?,?,1) ON CONFLICT(source_id) DO UPDATE SET current_path=excluded.current_path,revision=revision+1',(sid,path))
            for table in ('customer_styles','customer_source_associations'):
                if table in tables:
                    for old,new in migrated.items():db.execute('UPDATE '+table+' SET template_hash=? WHERE template_hash=?',(new,old))
            unresolved=[]
            final_root=str(target/'restored-library')
            for table in sorted(ACTIVE_JSON & tables):
                for _,kind,payload,_,_ in _active_rows(db,table):
                    for reference in _references(json.loads(payload)):
                        if reference.startswith(final_root+os.sep):candidate=stage/Path(reference).relative_to(final_root)
                        else:candidate=Path(reference)
                        if not candidate.is_file():unresolved.append(dict(table=table,path=reference))
            if manifest['complete'] and unresolved:raise ValueError('Manifest宣稱完整但有效資產仍失聯，保持隔離不啟用')
            _integrity(db)
        report=dict(state='RESTORED_ISOLATED_REVALIDATION_REQUIRED',database_integrity='PASS',scope=manifest['scope'],
                    complete_assets=manifest['complete'],asset_files=len(manifest['entries']),sources_restored=len(current_sources),
                    source_archive_sha256=archive_pin,library_root=str(target/'restored-library'),
                    original_database_sha256=manifest['database_sha256'],restored_database_sha256=file_digest(stage/'library.sqlite3'),
                    template_path_migrations=sum(a!=b for a,b in migrated.items()),test_restore=True,production_ready=False,
                    unresolved_references=unresolved,
                    training_state='PRESERVED_REVALIDATION_REQUIRED',old_host_source_stat_not_adopted=True,
                    notes=['目前環境未覆蓋；需於新位置啟動並重新檢查字型／來源／學習有效性與正式輸出Gate','原編號／來源名稱／操作歷史保留；只調整新副本的有效資產位置與版型指紋'])
        (stage/'RESTORE_REPORT.json').write_bytes(_json(report))
        _stage(cancel,progress,'RESTORE_PUBLISH_ISOLATED')
        if file_digest(archive)!=archive_pin:raise ValueError('還原期間備份檔已變更，未啟用')
        os.mkdir(target,0o700)
        try:
            (target/'RESTORE_STAGING_NOT_ACTIVE').write_text('隔離還原，尚未完成切換')
            os.rename(stage,target/'restored-library')
            (target/'RESTORE_COMPLETE.json').write_bytes(_json(report))
            (target/'RESTORE_STAGING_NOT_ACTIVE').unlink()
        except BaseException:
            # Retain the isolated incomplete folder for diagnosis; never touch current library.
            raise
    package.close();return report

"""Explicit roots and bounded manual reconciliation: notifications never count as facts."""
import os,time
from pathlib import Path
from .source_links import hash_source,fingerprint
from .training_store import digest
from .model import new_id
EXTENSIONS={'.ai','.pdf','.svg','.eps','.png','.jpg','.jpeg'}

def register_root(store,path,recursive=False):
    root=Path(path).expanduser()
    if root.is_symlink() or not root.is_dir():raise ValueError('需明確可讀本機目錄；不接受symlink')
    path=str(root.resolve())
    if store.count('SCAN_ROOT')>=20:raise ValueError('最多20個明確來源根目錄')
    if any(r['path']==path for r in store.records('SCAN_ROOT')):raise ValueError('此根目錄已登錄')
    with store.transaction():return store._write('SCAN_ROOT',new_id(),{'path':path,'recursive':bool(recursive),'mode':'MANUAL_ONLY','last_scan':None},0,'scan_root_added')

def scan_files(root,known,cancel=lambda:False,stable_wait=.25):
    directory=Path(root['path']);prior={r['path']:r for r in (root.get('last_scan') or {}).get('entries',[])};rows=[];total_bytes=0;seen=0;truncated=False
    if directory.is_symlink() or not directory.is_dir():return {'state':'ROOT_OFFLINE','entries':[],'scanned_entries':0,'complete':False,'originals_modified':False}
    iterator=(Path(base)/name for base,dirs,names in os.walk(directory,followlinks=False) for name in names) if root['recursive'] else directory.iterdir()
    first=[]
    for path in iterator:
        if cancel():return {'state':'CANCELLED','entries':rows,'scanned_entries':seen,'complete':False,'originals_modified':False}
        seen+=1
        if seen>500:truncated=True;break
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in EXTENSIONS:continue
        entry={'path':str(path),'state':'WAIT_STABLE'}
        try:
            size=path.stat().st_size;total_bytes+=size
            if total_bytes>256*1024*1024:truncated=True;break
            proof=hash_source(path,byte_limit=50_000_000);first.append((entry,proof));entry['hash']=proof.hash;entry['bytes']=size
        except (OSError,ValueError) as e:entry.update(state='READ_ERROR',reason=str(e))
        rows.append(entry)
    # Two independent byte hashes and stat snapshots, not a timer-based promise.
    end=time.monotonic()+max(.05,min(stable_wait,1.0))
    while time.monotonic()<end:
        if cancel():return {'state':'CANCELLED','entries':rows,'scanned_entries':seen,'complete':False,'originals_modified':False}
        time.sleep(.01)
    for entry,first_proof in first:
        try:
            second=hash_source(entry['path'],byte_limit=50_000_000)
            if first_proof.hash!=second.hash or first_proof.stat!=second.stat:entry.update(state='WAIT_STABLE',reason='兩次內容／stat不同，不匯入');continue
            old=prior.get(entry['path']);registered=known.get(entry['path'])
            previous=registered or (old.get('hash') if old else None)
            state='UNCHANGED' if previous==second.hash else 'CONTENT_CHANGED_REVIEW_REQUIRED' if previous else 'DUPLICATE_ALIAS_KEEP_IDENTITY' if second.hash in known.values() or any(x.get('hash')==second.hash and x['path']!=entry['path'] for x in rows) else 'NEW_CANDIDATE'
            entry.update(state=state,previous_hash=previous,verified_hash=second.hash)
        except (ValueError,OSError) as e:entry.update(state='WAIT_STABLE',reason=str(e))
    return {'state':'PARTIAL' if truncated or any(r['state'] in ('WAIT_STABLE','READ_ERROR') for r in rows) else 'SCANNED','entries':rows,'scanned_entries':min(seen,500),'complete':not truncated,'timestamp':time.time(),'bytes_first_pass':total_bytes,'source_imported':False,'originals_modified':False,'deletions_inferred':False}

def save_scan(store,root,result):
    with store.transaction():
        now=store.get('SCAN_ROOT',root['id'])
        if now!=root:raise ValueError('根目錄版本已變更，結果不套用')
        if result['state'] in ('ROOT_OFFLINE','CANCELLED'):
            # Keep last successful facts; offline is not permanent deletion.
            now['latest_attempt']=result
        else:now['last_scan']=result
        return store._write('SCAN_ROOT',now['id'],now,now['revision'],'source_manual_scan_recorded')

"""Local schedule/history in existing preferences; passwords never persisted.

Retention keeps the union of newest N and the chosen age window, plus a verified
complete backup. Only exact recorded bytes can move into owned recovery staging.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import time
import sqlite3

from .model import new_id
from .background import file_digest
from . import relational_backup as bundle

HISTORY='relational_backup_history_v2'
SCHEDULE='relational_backup_schedule_v2'
MAX_HISTORY=500


def _read(library,key,default):
    row=library.db.execute('SELECT value FROM preferences WHERE key=?',(key,)).fetchone()
    return json.loads(row[0]) if row else deepcopy(default)


def _save(library,key,value,expected):
    if library.db.in_transaction:raise ValueError('目前交易未完成，未覆寫備份設定')
    library.db.execute('BEGIN IMMEDIATE')
    try:
        if _read(library,key,None)!=expected:raise ValueError('備份設定／憑證已更新，請重新讀取')
        raw=json.dumps(value,ensure_ascii=False,allow_nan=False)
        if len(raw.encode())>1_048_576:raise ValueError('備份憑證超出1MiB預算，未截斷')
        library.db.execute('INSERT INTO preferences VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,raw))
        library.event(key,'backup_metadata_updated');library.db.commit()
        return value
    except BaseException:library.db.rollback();raise


def history(library):return _read(library,HISTORY,[])
def schedule(library):return _read(library,SCHEDULE,None)


def configure(library,directory,interval_seconds,retain_count=3,retain_days=0,options=None,enabled=True,expected_revision=0,now=None):
    directory=Path(directory)
    if not directory.is_absolute() or type(enabled) is not bool:raise ValueError('需明確本機絕對位置與啟用選擇')
    if type(interval_seconds) is not int or not 60<=interval_seconds<=365*86400:raise ValueError('排程間隔需1分鐘至365天')
    if type(retain_count) is not int or not 1<=retain_count<=100 or type(retain_days) is not int or not 0<=retain_days<=36500:raise ValueError('保留需1至100份；天數0至36500')
    options=dict(options or {})
    if set(options)-{'include_sources','include_fonts','limit_bytes','customers','templates','training'}:raise ValueError('排程不得保存密碼或未知參數')
    for key in ('include_sources','include_fonts','customers','templates','training'):
        if key in options and type(options[key]) is not bool:raise ValueError('排程資產權利需明確勾選')
    if 'limit_bytes' in options and (type(options['limit_bytes']) is not int or not 1_048_576<=options['limit_bytes']<=bundle.MAX_BYTES):raise ValueError('排程資源預算不合法')
    old=schedule(library)
    if (old or {}).get('revision',0)!=expected_revision:raise ValueError('排程版本已更新')
    now=time.time() if now is None else now
    value=dict(revision=expected_revision+1,directory=str(directory),interval_seconds=interval_seconds,
               retain_count=retain_count,retain_days=retain_days,options=options,enabled=enabled,
               next_due=now+interval_seconds,last_success=(old or {}).get('last_success'),last_attempt=None,
               state='WAITING_SESSION_KEY' if enabled else 'DISABLED',password_stored=False,
               execution_scope='APPLICATION_OPEN_SESSION_ONLY',closed_application_execution='UNAVAILABLE',
               retention_rule='UNION_NEWEST_N_AND_WITHIN_DAYS_PLUS_LAST_VERIFIED_COMPLETE')
    return _save(library,SCHEDULE,value,old)


def due_state(record,now=None,key_available=False,busy=False):
    now=time.time() if now is None else now
    if not record or not record.get('enabled'):return 'DISABLED'
    if record.get('last_attempt') is not None and now<record['last_attempt']:return 'CLOCK_ROLLBACK_REVIEW'
    if now<record['next_due']:return 'WAITING'
    if not Path(record['directory']).is_dir():return 'DESTINATION_OFFLINE'
    if busy:return 'WAITING_IDLE'
    if not key_available:return 'PASSWORD_REQUIRED'
    return 'DUE'


def update_attempt(library,expected,result=None,error=None,now=None):
    now=time.time() if now is None else now
    old=schedule(library)
    if old!=expected:raise ValueError('排程已變更，未覆寫新的設定')
    value=deepcopy(old);value.update(revision=old['revision']+1,last_attempt=now,next_due=now+old['interval_seconds'])
    if result and result.get('state')=='CREATED_AUTHENTICATED':
        value.update(last_success=now,state='SUCCESS',last_error=None,last_archive_sha256=result['sha256'])
    else:value.update(state='FAILED',last_error=str(error or '備份未完成')[:1000])
    return _save(library,SCHEDULE,value,old)


def record_result(library,result,now=None):
    if result.get('state')!='CREATED_AUTHENTICATED':raise ValueError('不能將未完成檔列入成功備份憑證')
    path=Path(result['path'])
    if path.is_symlink() or not path.is_file() or file_digest(path)!=result['sha256']:raise ValueError('成功檔已失聯／變更，不寫成功憑證')
    old=_read(library,HISTORY,None);rows=old or []
    duplicate=next((r for r in rows if r['path']==str(path) and r['sha256']==result['sha256']),None)
    if duplicate:return duplicate
    row={k:result[k] for k in ('path','sha256','bytes','scope','complete','test_restore')}
    row.update(id=new_id(),created=time.time() if now is None else now,state='CREATED_AUTHENTICATED',owned_by_app=True)
    _save(library,HISTORY,(rows+[row])[-MAX_HISTORY:],old)
    return row


def verify_record(record,password):
    path=Path(record['path'])
    if path.is_symlink() or not path.is_file() or file_digest(path)!=record['sha256']:raise ValueError('備份檔與成功憑證不符')
    package,manifest=bundle.read_bundle(path,password)
    try:
        with tempfile.TemporaryDirectory(prefix='template-ai-backup-verify-') as temporary:
            probe=Path(temporary)/'database.sqlite3';probe.write_bytes(package.read('library.sqlite3'))
            db=sqlite3.connect(probe)
            try:bundle._tables(db);bundle._integrity(db)
            finally:db.close()
        if file_digest(path)!=record['sha256']:raise ValueError('驗證期間備份檔變更')
        return dict(authenticated=True,database_integrity='PASS',complete=manifest['complete'],test_restore=False)
    finally:package.close()


def retention(library,directory,password,retain_count=3,retain_days=0,approved=False,now=None,cancel=lambda:False):
    if not approved:raise ValueError('先明確核准只處理本程式已記錄成功備份的保留政策')
    if type(retain_count) is not int or not 1<=retain_count<=100 or type(retain_days) is not int or not 0<=retain_days<=36500:raise ValueError('保留政策不合法')
    directory=Path(directory).resolve();now=time.time() if now is None else now;old=history(library)
    eligible=[r for r in old if r.get('owned_by_app') and r['state']=='CREATED_AUTHENTICATED' and Path(r['path']).parent.resolve()==directory]
    eligible.sort(key=lambda r:(r['created'],r['id']),reverse=True)
    report=dict(state='NO_DELETION',preserved=[],items=[],space_reclaimed=0,policy='UNION_NEWEST_N_AND_WITHIN_DAYS_PLUS_LAST_VERIFIED_COMPLETE')
    if len(eligible)<=retain_count:return report
    keep={r['id'] for r in eligible[:retain_count]}
    if retain_days:keep.update(r['id'] for r in eligible if r['created']>=now-retain_days*86400)
    complete=None
    for record in eligible[:10]:
        if cancel():report['state']='CANCELLED';return report
        try:
            verified=verify_record(record,password)
            if verified['complete']:complete=record;keep.add(record['id']);break
        except (ValueError,OSError,KeyError):continue
    if complete is None:report['state']='BLOCKED_NO_VERIFIED_COMPLETE_BACKUP';return report
    report['preserved']=sorted(keep)
    staging=directory/'.template-ai-retention-recovery'
    if staging.is_symlink():raise ValueError('保留恢復區不是可受控正常資料夾')
    staging.mkdir(exist_ok=True,mode=0o700)
    by_id={r['id']:deepcopy(r) for r in old};completed_journals=[]
    for record in eligible:
        if record['id'] in keep:continue
        if cancel():report['state']='CANCELLED';break
        path=Path(record['path']);moved=None;journal=None
        try:
            if not path.is_file() or path.is_symlink() or file_digest(path)!=record['sha256']:raise ValueError('檔案已變更／失聯，不刪除')
            if not Path(complete['path']).is_file() or file_digest(complete['path'])!=complete['sha256']:raise ValueError('保留的完整備份已變更，停止輪替')
            token=new_id();moved=staging/(token+'.tabi');journal=staging/(token+'.json')
            with journal.open('x',encoding='utf8') as stream:
                json.dump(dict(record_id=record['id'],original_path=str(path),recovery_path=str(moved),sha256=record['sha256'],state='PREPARED'),stream);stream.flush();os.fsync(stream.fileno())
            os.rename(path,moved)
            if file_digest(moved)!=record['sha256']:
                try:os.link(moved,path)
                except FileExistsError:pass
                raise ValueError('移轉期間檔案競爭，保留恢復區新內容，不刪除')
            if cancel():
                os.link(moved,path);moved.unlink();journal.unlink();report['state']='CANCELLED';break
            if not Path(complete['path']).is_file() or file_digest(complete['path'])!=complete['sha256']:raise ValueError('輪替期間保留的完整備份失聯，舊檔保留恢復區')
            moved.unlink()
            journal.write_text(json.dumps(dict(record_id=record['id'],original_path=str(path),recovery_path=str(moved),sha256=record['sha256'],state='DELETED_METADATA_PENDING')))
            completed_journals.append(journal)
            by_id[record['id']].update(state='PRUNED',pruned=now)
            report['items'].append(dict(id=record['id'],state='PRUNED',bytes=record['bytes']))
            report['space_reclaimed']+=record['bytes'];report['state']='APPLIED'
        except (OSError,ValueError) as error:
            item=dict(id=record['id'],state='NOT_DELETED',reason=str(error))
            if moved and moved.exists():item.update(state='RETENTION_RECOVERY',recovery_path=str(moved));by_id[record['id']].update(state='RETENTION_RECOVERY',recovery_path=str(moved))
            report['items'].append(item);report['state']='PARTIAL_FAILED'
    # CAS prevents an independently added backup record from being lost.
    current=history(library);expected=deepcopy(current)
    for row in current:
        if row['id'] in by_id and by_id[row['id']]!=next(r for r in old if r['id']==row['id']):row.update(by_id[row['id']])
    _save(library,HISTORY,current,expected)
    for journal in completed_journals:journal.unlink(missing_ok=True)
    return report


def recovery_entries(directory,limit=100):
    root=Path(directory)/'.template-ai-retention-recovery'
    if root.is_symlink() or not root.is_dir():return []
    result=[]
    for path in sorted(root.glob('*.json'))[:limit]:
        if path.is_symlink() or path.stat().st_size>16_384:continue
        record=json.loads(path.read_text());record['journal']=str(path);record['recovery_exists']=Path(record.get('recovery_path','')).is_file();result.append(record)
    return result

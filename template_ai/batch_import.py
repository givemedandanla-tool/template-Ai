"""Bounded readonly preflight and a transactional, recoverable import state machine."""
import copy
import json
import os
from pathlib import Path
import time
import weakref
from .model import new_id
from .source_links import hash_source,verify_source,check_verified,ScanCancelled
from .importer import import_file,cache_matches,MAX_PIXELS

EXTENSIONS={'.ai','.eps','.pdf','.svg','.png','.jpg','.jpeg'}
MAX_ITEMS=200
MAX_BYTES=50*1024*1024
LIVE_SESSIONS=weakref.WeakValueDictionary()


def end_session(library):
    LIVE_SESSIONS.pop(getattr(library,'import_session',''),None)


def expand_paths(paths,cancel=None):
    if not paths:raise ValueError('未選取來源')
    files=[];directories=0;entries=0
    for raw in paths:
        p=Path(raw)
        if p.is_symlink():raise ValueError('批次來源不接受符號連結')
        if p.is_dir():
            for base,dirs,names in os.walk(p,followlinks=False):
                directories+=1
                if directories>2000:raise ValueError('資料夾掃描超出2000目錄預算')
                dirs[:]=sorted(d for d in dirs if not d.startswith('.') and not (Path(base)/d).is_symlink())
                for name in sorted(names):
                    entries+=1
                    if entries>10000:raise ValueError('資料夾掃描超出項目預算')
                    f=Path(base)/name
                    if f.suffix.lower() in EXTENSIONS and not f.is_symlink():files.append(f.resolve())
                    if len(files)>MAX_ITEMS:raise ValueError('批次最多200來源／頁次')
                    if cancel and cancel.is_set():raise ScanCancelled()
        else:files.append(p.absolute())
        if len(files)>MAX_ITEMS:raise ValueError('批次最多200來源／頁次')
    return sorted(set(files),key=lambda p:str(p))


def healthy_source(source):
    try:
        verify_source(source.get('current_path',source['original_path']),source['hash'])
        folder=Path(source['image']).parent;meta=folder/'metadata.json'
        if meta.is_symlink() or meta.stat().st_size>100_000:return False
        cached=json.loads(meta.read_text())
        if not cache_matches(cached,folder,source['hash'],source['page']):return False
        for key in ('image','svg','width_mm','height_mm','page_count','file_hashes'):
            if cached.get(key)!=source.get(key):return False
        from PySide6.QtGui import QImageReader
        reader=QImageReader(source['image']);size=reader.size()
        return size.isValid() and size.width()*size.height()<=MAX_PIXELS and reader.canRead()
    except (OSError,ValueError,KeyError,TypeError):return False


def preflight(paths,sources,page=1,cancel=None):
    if type(page) is not int or not 1<=page<=1000:raise ValueError('頁次需1～1000')
    rows=[];seen={};known={}
    for s in sorted(sources,key=lambda s:s['id']):known.setdefault((s['hash'],s['page']),[]).append(s)
    for p in expand_paths(paths,cancel):
        row={'id':new_id(),'path':str(p),'page':page,'expected_hash':None,'status':'READY','reason':'待匯入；視覺／語意尚未核驗','attempts':0,'history':[],'source_id':None,'reuse_source':None}
        try:
            if p.suffix.lower() not in EXTENSIONS:raise ValueError('不支援來源格式')
            if p.is_symlink():raise ValueError('不接受符號連結')
            proof=hash_source(p,cancel,MAX_BYTES);row['expected_hash']=proof.hash;row['bytes']=proof.stat[2]
            key=(proof.hash,page)
            if key in seen:row.update(status='SKIPPED',duplicate_of=seen[key],reason='同批相同SHA-256／頁次；路徑證據保留，作品／模板相似仍UNKNOWN')
            else:
                seen[key]=row['id']
                for source in known.get(key,[]):
                    if healthy_source(source):row.update(reuse_source=copy.deepcopy(source),reason='已登錄同內容／頁次且原稿與快取健康，啟動時再次檢查');break
        except ScanCancelled:raise
        except (OSError,ValueError) as error:row.update(status='FAILED',reason=str(error),error_type='PREFLIGHT')
        rows.append(row)
    if not rows:raise ValueError('選取範圍沒有支援的來源')
    return {'items':rows,'page':page,'file_duplicates':sum(r['status']=='SKIPPED' for r in rows),'reuse_candidates':sum(bool(r['reuse_source']) for r in rows),'artwork_duplicates':'UNKNOWN','template_similarity':'UNKNOWN','scope':'只讀來源匯入；尚非自动語意辨識／學習／發布'}


def convert_item(item,assets):
    p=Path(item['path'])
    if p.is_symlink():raise ValueError('來源變成符號連結')
    proof=hash_source(p,byte_limit=MAX_BYTES)
    if proof.hash!=item['expected_hash']:raise ValueError('SOURCE_CHANGED：與預檢內容不同，請另行核對重試')
    reuse=item.get('reuse_source')
    if reuse:
        if not healthy_source(reuse):raise ValueError('CACHE_CHANGED：重用來源或快取已失效，請重新預檢')
        payload=copy.deepcopy(reuse)
    else:payload=import_file(p,Path(assets),item['page'])
    check_verified(proof,item['expected_hash'])
    after=hash_source(p,byte_limit=MAX_BYTES)
    if after.hash!=proof.hash or after.stat!=proof.stat:raise ValueError('SOURCE_CHANGED：轉換期間來源異動')
    if payload['hash']!=proof.hash:raise ValueError('轉換結果與來源身份不符')
    cache_proofs={}
    for key,expected in payload['file_hashes'].items():
        asset_proof=hash_source(payload[key],byte_limit=MAX_BYTES)
        if asset_proof.hash!=expected:raise ValueError('CACHE_CHANGED：轉換快取身份不符')
        cache_proofs[key]=asset_proof
    return {'payload':payload,'proof':after,'reused':bool(reuse),'cache_proofs':cache_proofs}


class BatchStore:
    def __init__(self,library):
        self.library=library;self.db=library.db
        self.db.execute('CREATE TABLE IF NOT EXISTS import_batches(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,payload TEXT NOT NULL)');self.db.commit()
        if not getattr(library,'import_session',None):library.import_session=new_id()
        self.session=library.import_session;LIVE_SESSIONS[self.session]=library
    def get(self,batch_id):
        row=self.db.execute('SELECT revision,payload FROM import_batches WHERE id=?',(batch_id,)).fetchone()
        if not row:raise ValueError('批次不存在')
        data=json.loads(row[1])
        if data['revision']!=row[0]:raise ValueError('批次索引／revision不一致')
        return data
    def list(self):return [self.get(r[0]) for r in self.db.execute('SELECT id FROM import_batches ORDER BY rowid DESC')]
    def create(self,report,confirmed=False):
        if not confirmed:raise ValueError('需核對預檢摘要並明確確認')
        items=copy.deepcopy(report['items'])
        if not items or len(items)>MAX_ITEMS or len({r['id'] for r in items})!=len(items):raise ValueError('批次項目範圍不合法')
        if any(r['status'] not in ('READY','SKIPPED','FAILED') or type(r['page']) is not int or not 1<=r['page']<=1000 for r in items):raise ValueError('預檢狀態／頁次不合法')
        b={'id':new_id(),'revision':1,'phase':'READY','created':time.time(),'items':items,'owner':None,'history':[],'scope':report['scope']}
        with self.db:
            self.db.execute('INSERT INTO import_batches VALUES(?,?,?)',(b['id'],1,json.dumps(b,ensure_ascii=False)));self.library.event(b['id'],'import_preflight_confirmed')
        return b
    def mutate(self,batch_id,revision,action,function):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            b=self.get(batch_id)
            if b['revision']!=revision:raise ValueError('批次已變更，請重新載入；不覆寫別人結果')
            function(b);b['revision']+=1;b['history'].append({'action':action,'revision':b['revision'],'created':time.time()})
            self.db.execute('UPDATE import_batches SET revision=?,payload=? WHERE id=?',(b['revision'],json.dumps(b,ensure_ascii=False),batch_id));self.library.event(batch_id,action);self.db.commit();return b
        except Exception:self.db.rollback();raise
    def claim(self,batch_id,revision,item_id):
        def change(b):
            if b['phase'] not in ('READY','RUNNING','CANCELLED','INTERRUPTED','PAUSED'):raise ValueError('此批次不可續跑')
            if b['phase']=='RUNNING' and b.get('owner')!={'pid':os.getpid(),'session':self.session}:raise ValueError('不能接管其他執行者')
            if any(x['phase']=='RUNNING' and x['id']!=b['id'] for x in self.list()):raise ValueError('已有其他批次執行，單worker不重複啟動')
            if any(r['status']=='RUNNING' for r in b['items']):raise ValueError('目前項尚未完成，不重複執行')
            r=next((r for r in b['items'] if r['id']==item_id),None)
            if not r or r['status']!='READY':raise ValueError('只啟動明確待執行項')
            r['status']='RUNNING';r['attempts']+=1;r['history'].append({'action':'CLAIM','attempt':r['attempts'],'hash':r['expected_hash']});b['phase']='RUNNING';b['owner']={'pid':os.getpid(),'session':self.session}
        return self.mutate(batch_id,revision,'import_item_started',change)
    def finish(self,batch_id,revision,item_id,result=None,error=None):
        def change(b):
            if b['phase']!='RUNNING' or b['owner']!={'pid':os.getpid(),'session':self.session}:raise ValueError('批次執行者不符')
            r=next((r for r in b['items'] if r['id']==item_id),None)
            if not r or r['status']!='RUNNING':raise ValueError('執行項狀態不符')
            if error:
                r.update(status='FAILED',reason=str(error),error_type='SOURCE_CHANGED' if 'SOURCE_CHANGED' in str(error) else 'CACHE_CHANGED' if 'CACHE_CHANGED' in str(error) else 'IMPORT')
            else:
                if not result:raise ValueError('缺少轉換結果，不冒稱完成')
                check_verified(result['proof'],r['expected_hash']);payload=result['payload']
                if payload['hash']!=r['expected_hash'] or payload['page']!=r['page']:raise ValueError('來源結果不屬此項')
                if set(result.get('cache_proofs',{}))!=set(payload['file_hashes']):raise ValueError('快取缺少核驗證據')
                for key,expected in payload['file_hashes'].items():check_verified(result['cache_proofs'][key],expected)
                if result['reused']:
                    source=self.library.source(r['reuse_source']['id'])
                    if source!=r['reuse_source']:raise ValueError('重用登錄在核驗後異動')
                    r.update(status='REUSED',source_id=source['id'],reason='健康同內容／頁次重用；視覺與語意仍未批准')
                else:
                    sid=new_id();data={**payload,'id':sid,'original_path':r['path']}
                    self.db.execute('INSERT OR IGNORE INTO contents VALUES(?,?)',(payload['hash'],result['proof'].stat[2]));self.db.execute('INSERT INTO sources VALUES(?,?,?,?)',(sid,payload['hash'],r['path'],json.dumps(data,ensure_ascii=False)))
                    r.update(status='SUCCESS',source_id=sid,reason='來源預覽已保存；視覺／作品辨識與訓練待核驗')
            r['history'].append({'action':r['status'],'attempt':r['attempts'],'reason':r['reason'],'source_id':r['source_id']})
        return self.mutate(batch_id,revision,'import_item_result_saved',change)
    def stop(self,batch_id,revision,cancelled=False):
        def change(b):
            if b['phase']=='RUNNING' and b.get('owner')!={'pid':os.getpid(),'session':self.session}:raise ValueError('不能停止其他執行者')
            if any(r['status']=='RUNNING' for r in b['items']):raise ValueError('目前轉換未結束，不能強制結案')
            b['phase']='CANCELLED' if cancelled else 'PAUSED' if any(r['status']=='READY' for r in b['items']) else 'DONE_WITH_ERRORS' if any(r['status'] in ('FAILED','INTERRUPTED') for r in b['items']) else 'DONE';b['owner']=None
        return self.mutate(batch_id,revision,'import_cancelled' if cancelled else 'import_run_stopped',change)
    def recover(self):
        recovered=[]
        for b in self.list():
            if b['phase']!='RUNNING':continue
            owner=b.get('owner') or {};pid=owner.get('pid')
            if pid==os.getpid():alive=owner.get('session') in LIVE_SESSIONS
            else:
                try:
                    if type(pid) is not int or pid<=0:raise ProcessLookupError()
                    os.kill(pid,0);alive=True
                except ProcessLookupError:alive=False
                except PermissionError:alive=True
            if alive:continue
            def change(data):
                data['phase']='INTERRUPTED';data['owner']=None
                for r in data['items']:
                    if r['status']=='RUNNING':r.update(status='INTERRUPTED',error_type='INTERRUPTED',reason='先前執行者已結束；需明確重試，不冒稱成功');r['history'].append({'action':'INTERRUPTED','attempt':r['attempts']})
            recovered.append(self.mutate(b['id'],b['revision'],'import_interruption_recovered',change))
        return recovered

    def interrupt_owned(self,batch_id,revision,reason):
        def change(b):
            if b.get('owner')!={'pid':os.getpid(),'session':self.session}:raise ValueError('不能接管其他執行者')
            for r in b['items']:
                if r['status']=='RUNNING':
                    r.update(status='INTERRUPTED',error_type='INTEGRITY',reason='結果未能交易保存：'+str(reason));r['history'].append({'action':'INTERRUPTED','reason':r['reason'],'attempt':r['attempts']})
            b['phase']='INTERRUPTED';b['owner']=None
        return self.mutate(batch_id,revision,'import_uncommitted_result_interrupted',change)

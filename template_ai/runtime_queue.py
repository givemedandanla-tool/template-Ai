"""FIFO requests in the existing SQLite database, atomic with the existing worker claim.

Queue bookkeeping deliberately does not change the learning epoch. Scope approval
belongs to an application session; restart/restore never silently resumes work.
"""
from contextlib import contextmanager
import hashlib,json
from .model import new_id
from .training_store import TrainingStore
from .training_pipeline import owner_alive,LIVE_OWNERS
import os

ELIGIBLE=('WAITING','PAUSED_RESOURCES')
ACTIVE=ELIGIBLE+('RUNNING','INTERRUPTED')
ITEM_KEYS=('sample_id','sample_revision','scope_digest','source_pins','name','preexisting_template_id','work_id','work_revision','source_hash','path','page','expected_page_count','work_scope','expected_pins')


def scope_digest(kind,job):
    scope={k:job.get(k) for k in ('id','dataset_id','dataset_revision','manifest_digest','purpose','scope')}
    scope['kind']=kind;scope['items']=[{k:item.get(k) for k in ITEM_KEYS} for item in job['items']]
    if kind=='AUTO_JOB' and job.get('operation') is not None:scope['operation']=job['operation']
    if kind=='AUTO_JOB' and job.get('pipeline_deployment') is not None:scope['pipeline_deployment']=job['pipeline_deployment']
    if kind=='EVAL_JOB':
        scope.update(protocol_id=job['protocol_id'],protocol_scope_digest=job['protocol_scope_digest'],side=job['side'],pipeline_id=job['pipeline_id'],pipeline_manifest_digest=job['pipeline_manifest_digest'])
        scope['items']=[{k:item.get(k) for k in (*ITEM_KEYS,'id','source_id','gold_ids','logical_file_keys')} for item in job['items']]
    return hashlib.sha256(json.dumps(scope,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


class RuntimeQueue:
    def __init__(self,library):self.library=library;self.db=library.db;self.store=TrainingStore.bind(library)

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:yield;self.db.commit()
        except BaseException:self.db.rollback();raise

    def get(self,identity):
        row=self.db.execute('SELECT seq,revision,payload FROM runtime_requests WHERE id=?',(identity,)).fetchone()
        return dict(json.loads(row[2]),id=identity,seq=row[0],revision=row[1]) if row else None

    @staticmethod
    def _selected(row):
        return dict(json.loads(row[3]),id=row[0],seq=row[1],revision=row[2])

    def page(self,offset=0,limit=50):
        if type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=200:raise ValueError('工作佇列需有效分頁，最多200項')
        return [self._selected(row) for row in self.db.execute('SELECT id,seq,revision,payload FROM runtime_requests ORDER BY seq DESC LIMIT ? OFFSET ?',(limit,offset))]

    def eligible(self,session=None):
        rows=[self._selected(row) for row in self.db.execute("SELECT id,seq,revision,payload FROM runtime_requests WHERE json_extract(payload,'$.state') IN ('WAITING','PAUSED_RESOURCES') ORDER BY seq LIMIT 200")]
        return [row for row in rows if (session is None or row['consent_session']==session) and owner_alive(row.get('consent_owner'))]

    def _write(self,value,expected,action):
        value=dict(value);identity=value.pop('id');value.pop('seq',None);value.pop('revision',None)
        raw=json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)
        if len(raw.encode())>32768:raise ValueError('執行請求超過32KiB，未保存')
        if expected==0:self.db.execute('INSERT INTO runtime_requests(id,revision,payload) VALUES(?,1,?)',(identity,raw))
        elif self.db.execute('UPDATE runtime_requests SET revision=revision+1,payload=? WHERE id=? AND revision=?',(raw,identity,expected)).rowcount!=1:raise ValueError('執行請求版次已改變')
        self.library.event(identity,'runtime_queue_'+action);return self.get(identity)

    def enqueue(self,kind,job_id,actor,session,approved=False,retry_failed=False):
        if approved is not True or kind not in ('JOB','AUTO_JOB','EVAL_JOB') or not isinstance(actor,str) or not actor.strip() or len(actor)>120 or not isinstance(session,str) or len(session)!=32 or type(retry_failed) is not bool:raise ValueError('需明確確認工作種類、範圍、操作者與本次階段')
        LIVE_OWNERS.add(session)
        with self.transaction():
            job=self.store.get(kind,job_id)
            if not job:raise ValueError('工作已失聯')
            digest=scope_digest(kind,job)
            old=self.db.execute("SELECT id FROM runtime_requests WHERE json_extract(payload,'$.kind')=? AND json_extract(payload,'$.job_id')=? AND json_extract(payload,'$.state') IN ('WAITING','PAUSED_RESOURCES','RUNNING','INTERRUPTED') ORDER BY seq LIMIT 1",(kind,job_id)).fetchone()
            if old:
                request=self.get(old[0])
                if request['state']=='RUNNING' and owner_alive(request.get('owner')):raise ValueError('此工作仍有活動執行者')
                if request['scope_digest']!=digest:raise ValueError('工作範圍已變更，請取消舊請求再重新預檢')
                return self._write(dict(request,state='WAITING',owner=None,actor=actor.strip(),consent_session=session,consent_owner=dict(pid=os.getpid(),token=session),retry_failed=retry_failed,message=None),request['revision'],'resume_scope_confirmed')
            count=self.db.execute("SELECT count(*) FROM runtime_requests WHERE json_extract(payload,'$.state') IN ('WAITING','PAUSED_RESOURCES','RUNNING','INTERRUPTED')").fetchone()[0]
            if count>=200:raise ValueError('待辦上限200，先完成／取消現有請求；沒有丟棄舊工作')
            return self._write(dict(id=new_id(),kind=kind,job_id=job_id,job_revision=job['revision'],scope_digest=digest,state='WAITING',actor=actor.strip(),consent_session=session,consent_owner=dict(pid=os.getpid(),token=session),retry_failed=retry_failed,owner=None,message=None),0,'scope_confirmed')

    def cancel_waiting(self,identity,revision):
        with self.transaction():
            request=self.get(identity)
            if not request or request['revision']!=revision or request['state'] not in ('WAITING','PAUSED_RESOURCES','INTERRUPTED','BLOCKED'):raise ValueError('請求已變更／正在執行／已結束，未改寫歷史結果')
            return self._write(dict(request,state='CANCELLED',consent_session=None),revision,'cancelled_before_claim')

    def recover_dead(self):
        with self.transaction():
            for row in self.db.execute("SELECT id FROM runtime_requests WHERE json_extract(payload,'$.state')='RUNNING' ORDER BY seq LIMIT 200").fetchall():
                request=self.get(row[0])
                if not owner_alive(request.get('owner')):
                    job=self.store.get(request['kind'],request['job_id'])
                    committed=bool(job and job['phase'] in ('COMPLETED','COMPLETED_WITH_EXCEPTIONS') and (job.get('owner') or {}).get('token')==(request.get('owner') or {}).get('token') and scope_digest(request['kind'],job)==request['scope_digest'])
                    value=dict(request,state='DONE' if committed else 'INTERRUPTED',consent_session=None,result_phase=job['phase'] if committed else 'INTERRUPTED',message='已從原工作提交讀回遺失收據' if committed else '原執行者已離開；明確確認恢復，已保存單位保留')
                    self._write(value,request['revision'],'committed_result_receipt_recovered' if committed else 'dead_owner_recoverable')

    def block(self,request,message):
        with self.transaction():return self._write(dict(request,state='BLOCKED',message=str(message)[:4000],consent_session=None),request['revision'],'blocked_not_discarded')

    def claim(self,request,session,admissible_ids=None):
        job=self.store.get(request['kind'],request['job_id'])
        if not job or scope_digest(request['kind'],job)!=request['scope_digest']:
            self.block(request,'範圍已變更／工作失聯，需重新預檢');return None
        chosen={r['id'] for r in self.eligible()} if admissible_ids is None else set(admissible_ids)
        def atomic_claim(claimed):
            current=self.get(request['id']);ordered=[r for r in self.eligible() if r['id'] in chosen]
            if not ordered or ordered[0]['id']!=request['id'] or current['consent_session']!=session or current['revision']!=request['revision']:raise ValueError('佇列順序／作用域／請求版次已改變，未接管')
            if scope_digest(request['kind'],claimed)!=request['scope_digest']:raise ValueError('工作範圍已改變')
            self._write(dict(current,state='RUNNING',owner=claimed['owner'],job_revision=claimed['revision'],retry_failed=False),current['revision'],'claimed_with_existing_worker_lease')
        if request['kind']=='JOB':return self.store.claim_training_job(job['id'],job['revision'],True,request['retry_failed'],claimed_hook=atomic_claim)
        if request['kind']=='EVAL_JOB':
            from .quality_jobs import EvaluationJobs
            return EvaluationJobs(self.library).claim(job['id'],job['revision'],True,request['retry_failed'],claimed_hook=atomic_claim)
        from .automatic_training import AutomaticTraining
        return AutomaticTraining(self.library).claim(job['id'],job['revision'],True,request['retry_failed'],claimed_hook=atomic_claim)

    def finish(self,identity,token,result=None,error=None):
        with self.transaction():
            request=self.get(identity)
            if request['state']!='RUNNING' or request['owner']['token']!=token:raise ValueError('執行請求擁有者已變更')
            phase=result['phase'] if result else 'INTERRUPTED'
            state='WAITING' if phase=='CONTINUATION_PENDING' else 'PAUSED_RESOURCES' if phase=='PAUSED_RESOURCES' else 'DONE' if phase in ('COMPLETED','COMPLETED_WITH_EXCEPTIONS') else 'BLOCKED'
            return self._write(dict(request,state=state,owner=None,result_phase=phase,message=str(error)[:4000] if error else (result.get('last_error') or result.get('system_error')),consent_session=request['consent_session'] if state in ELIGIBLE else None),request['revision'],'result_committed')

    def isolate_timed_out(self,identity,token,message):
        """Called only after our child is stopped; isolate exactly its durable active item."""
        with self.transaction():
            request=self.get(identity);job=self.store.get(request['kind'],request['job_id'])
            if request['state']!='RUNNING' or request['owner']['token']!=token or job['phase']!='RUNNING' or job['owner']['token']!=token or owner_alive(job['owner']) or scope_digest(request['kind'],job)!=request['scope_digest']:raise ValueError('無法證明已停止工作及原範圍，未自動續跑')
            active=[item for item in job['items'] if item['state']=='RUNNING']
            if len(active)!=1:raise ValueError('沒有唯一持久執行項，未猜測要隔離的來源／樣本')
            active[0].update(state='FAILED',error=str(message)[:4000],attempts=active[0].get('attempts',0)+1)
            job['phase']='CONTINUATION_PENDING' if any(item['state']=='READY' for item in job['items']) else 'COMPLETED_WITH_EXCEPTIONS'
            if request['kind']=='EVAL_JOB':job['phase']='CONTINUATION_PENDING'
            result=self.store._write(request['kind'],job['id'],job,job['revision'],'runtime_timed_out_item_isolated')
            worker='geometry-worker' if request['kind']=='JOB' else 'automatic-worker';lease=self.store.get('WORKER',worker)
            if not lease or lease.get('owner',{}).get('token')!=token:raise ValueError('既有worker執行權已改變')
            lease['active']=False;self.store._write('WORKER',worker,lease,lease['revision'],'runtime_timed_out_worker_released');return result

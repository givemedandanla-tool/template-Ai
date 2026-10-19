"""Versioned durable design jobs using the existing SQLite ledger and leases.

Cancellation is observed between atomic items/fit phases. A running sklearn fit
is not claimed to be interruptible or incrementally trainable.
"""
from copy import deepcopy
import os
import time

from .model import new_id
from .training_store import TrainingStore,digest,text
from .training_pipeline import LIVE_OWNERS,owner_alive

KINDS={'TRAIN_SHARED_MODEL','EVALUATE_LAYOUTS','OWNED_DESCRIPTOR_BENCHMARK','OWNED_SOURCE_FILE_BENCHMARK'}


class DesignJobs:
    def __init__(self,library):
        self.library=library
        self.store=TrainingStore.bind(library) if library.db.in_transaction else TrainingStore(library)

    def create(self,kind,plan,actor,approved=False):
        if not approved or kind not in KINDS:raise ValueError('Explicit supported job scope is required')
        text(actor,'Job actor',120)
        if not isinstance(plan,dict):raise ValueError('Job plan must be explicit')
        items=plan.get('items')
        if not isinstance(items,list) or not 1<=len(items)<=10000:raise ValueError('Job requires1–10000 bounded items')
        if len({digest(item) for item in items})!=len(items):raise ValueError('Duplicate job items are not independent work')
        with self.store.transaction():
            plan_record=self.store._write('DESIGN_JOB_PLAN',new_id(),dict(plan=deepcopy(plan),digest=digest(plan)),0,'immutable_design_job_plan')
            return self.store._write('DESIGN_JOB',new_id(),dict(kind=kind,plan_ref=plan_record['id'],plan_digest=digest(plan),item_count=len(items),
                actor=actor,phase='QUEUED',next_index=0,owner=None,cancel_requested=False,error=None,
                started=None,created=time.time(),elapsed_seconds=0.,events=[]),0,'design_job_created')

    def current(self,job_id):
        job=self.store.get('DESIGN_JOB',job_id)
        plan=self.store.get('DESIGN_JOB_PLAN',job['plan_ref']) if job else None
        if not job or not plan or digest(plan['plan'])!=job['plan_digest']:raise ValueError('Job plan missing or changed')
        return dict(job,plan=plan['plan'])

    def state(self,job_id):
        job=self.current(job_id)
        return 'INTERRUPTED' if job['phase']=='RUNNING' and not owner_alive(job['owner']) else job['phase']

    def claim(self,job_id,expected_revision):
        token=new_id();owner=dict(pid=os.getpid(),token=token,started=time.time());LIVE_OWNERS.add(token)
        try:
            with self.store.transaction():
                job=self.current(job_id);lease=self.store.get('WORKER','design-worker')
                if job['revision']!=expected_revision or job['phase']=='COMPLETE':raise ValueError('Job revision/phase changed')
                if lease and lease.get('active') and owner_alive(lease.get('owner')):raise ValueError('A design worker is already active')
                if job['phase']=='RUNNING' and owner_alive(job['owner']):raise ValueError('Running worker cannot be taken over')
                payload={k:deepcopy(v) for k,v in job.items() if k not in ('id','revision','plan')}
                payload.update(phase='RUNNING',owner=owner,cancel_requested=False,error=None,started=time.time())
                payload['events'].append(dict(event='CLAIM_OR_RESUME',next_index=job['next_index'],at=time.time()))
                saved=self.store._write('DESIGN_JOB',job_id,payload,expected_revision,'design_job_claimed')
                self.store._write('WORKER','design-worker',dict(active=True,job_id=job_id,owner=owner),
                    lease['revision'] if lease else 0,'design_worker_claimed')
                return dict(saved,plan=deepcopy(job['plan']))
        except BaseException:
            LIVE_OWNERS.discard(token);raise

    def owned(self,job_id,token):
        job=self.current(job_id);lease=self.store.get('WORKER','design-worker')
        if (job['phase']!='RUNNING' or job['owner']['token']!=token or not lease or not lease['active']
                or lease['job_id']!=job_id or lease['owner']['token']!=token):raise ValueError('Worker ownership changed')
        return job

    def request_cancel(self,job_id):
        with self.store.transaction():
            job=self.current(job_id)
            if job['phase']!='RUNNING':return job
            body={k:deepcopy(v) for k,v in job.items() if k not in ('id','revision','plan')};body['cancel_requested']=True
            return self.store._write('DESIGN_JOB',job_id,body,job['revision'],'design_job_cancel_requested')

    def item_key(self,job_id,index):return digest([job_id,index])

    def save_item(self,job_id,token,index,result,elapsed):
        with self.store.transaction():
            job=self.owned(job_id,token)
            if job['next_index']!=index:raise ValueError('Late job result cannot overwrite a newer step')
            key=self.item_key(job_id,index)
            if self.store.get('DESIGN_JOB_ITEM',key):raise ValueError('Committed item must not be recomputed')
            self.store._write('DESIGN_JOB_ITEM',key,dict(job_id=job_id,index=index,result=deepcopy(result),
                input_digest=digest(job['plan']['items'][index]),result_digest=digest(result),elapsed_seconds=elapsed),0,'design_job_item_committed')
            body={k:deepcopy(v) for k,v in job.items() if k not in ('id','revision','plan')}
            body['next_index']+=1;body['elapsed_seconds']+=elapsed
            self.store._write('DESIGN_JOB',job_id,body,job['revision'],'design_job_progress_committed')
            return self.current(job_id)

    def finish(self,job_id,token,phase,error=None,summary=None):
        if phase not in ('COMPLETE','PAUSED','FAILED'):raise ValueError('Unknown job terminal phase')
        with self.store.transaction():
            job=self.owned(job_id,token)
            if phase=='COMPLETE' and job['next_index']!=len(job['plan']['items']):raise ValueError('Incomplete items cannot become COMPLETE')
            body={k:deepcopy(v) for k,v in job.items() if k not in ('id','revision','plan')}
            body.update(phase=phase,error=error,summary=deepcopy(summary),finished=time.time())
            body['events'].append(dict(event=phase,next_index=job['next_index'],at=time.time()))
            saved=self.store._write('DESIGN_JOB',job_id,body,job['revision'],'design_job_'+phase.lower())
            lease=self.store.get('WORKER','design-worker');lease['active']=False
            self.store._write('WORKER','design-worker',lease,lease['revision'],'design_worker_released')
            LIVE_OWNERS.discard(token);return saved

    def results(self,job_id):
        job=self.current(job_id);results=[]
        for index in range(job['next_index']):
            row=self.store.get('DESIGN_JOB_ITEM',self.item_key(job_id,index))
            if not row or row['input_digest']!=digest(job['plan']['items'][index]) or row['result_digest']!=digest(row['result']):
                raise ValueError('Committed job evidence missing or changed')
            results.append(row['result'])
        return results


def run_design_job(root,job_id,token,cancel=None,progress=None):
    from .storage import Library
    library=Library(root);jobs=DesignJobs(library)
    try:
        job=jobs.owned(job_id,token)
        while job['next_index']<len(job['plan']['items']):
            if job['cancel_requested'] or cancel and cancel():return jobs.finish(job_id,token,'PAUSED')
            index=job['next_index'];started=time.perf_counter()
            from .design_evaluation import execute_item
            result=execute_item(library,job,index)
            job=jobs.save_item(job_id,token,index,result,time.perf_counter()-started)
            if progress:progress(dict(job_id=job_id,done=job['next_index'],total=len(job['plan']['items'])))
        if job['cancel_requested'] or cancel and cancel():return jobs.finish(job_id,token,'PAUSED')
        from .design_evaluation import summarize_job
        return jobs.finish(job_id,token,'COMPLETE',summary=summarize_job(library,job,jobs.results(job_id)))
    except Exception as error:
        try:jobs.finish(job_id,token,'FAILED',type(error).__name__+': '+str(error)[:512])
        except (ValueError,KeyError):pass
        raise
    finally:
        LIVE_OWNERS.discard(token);library.close()

"""Durable, bounded geometry queue. Each worker owns its SQLite connection."""
import copy
import os
import threading
import time
from .model import new_id

LIVE_OWNERS=set()
SUCCESS_STATES={'SUCCESS','REUSED'}


def owner_alive(owner):
    if not isinstance(owner,dict):return False
    if owner.get('pid')==os.getpid():return owner.get('token') in LIVE_OWNERS
    try:os.kill(owner['pid'],0);return True
    except ProcessLookupError:return False
    except (PermissionError,OSError):return True
    except (KeyError,TypeError,ValueError):return False


class TrainingQueueMixin:
    def training_job_plan(self,dataset_id,sample_ids,prefix):
        from .training_store import digest,text
        text(prefix,'草稿名稱前綴',100)
        if not isinstance(sample_ids,list) or not 1<=len(sample_ids)<=200 or len(sample_ids)!=len(set(sample_ids)):raise ValueError('明列1～200個不重複TRAIN樣本')
        validity=self.dataset_validity(dataset_id,sample_ids)
        if not validity['valid']:raise ValueError('選中資料集／樣本目前不可用：'+'；'.join(validity['errors']))
        ds=validity['dataset'];items=[]
        for sid in sorted(sample_ids):
            sample=self.get('SAMPLE',sid);entry=next((e for e in ds['entries'] if e['sample_id']==sid),None)
            if not entry or entry['role']!='TRAIN':raise ValueError('只能選本資料集TRAIN項；不自動排除holdout後假裝原範圍成功')
            duplicates=ds['manifest']['exact_duplicates'].get(entry['exact_label_signature'],[])
            if duplicates and sid!=min(duplicates):raise ValueError('exact duplicate非代表項，先明列代表樣本')
            existing=self.existing_geometry_result(dataset_id,sid)
            if existing:self.library._template_provenance(next(t for t in self.library.templates() if t.id==existing))
            else:self.geometry_learning_plan(dataset_id,sid,prefix+' '+str(len(items)+1))
            items.append({'sample_id':sid,'sample_revision':sample['revision'],'scope_digest':sample['scope_digest'],'source_pins':sample['pins'],'name':prefix+' '+str(len(items)+1),'state':'READY','attempts':0,'template_id':None,'error':None,'preexisting_template_id':existing})
        plan={'epoch':self.epoch,'dataset_id':dataset_id,'dataset_revision':ds['revision'],'manifest_digest':ds['manifest_digest'],'prefix':prefix,'items':items,'purpose':'GEOMETRY_DRAFT_ONLY'};plan['digest']=digest(plan);return plan

    def create_training_job(self,plan,actor,approved=False):
        from .training_store import text
        if approved is not True:raise ValueError('明確確認exact dataset／sample／用途後建立佇列')
        text(actor,'啟動者',120)
        with self.transaction():
            current=self.training_job_plan(plan['dataset_id'],[i['sample_id'] for i in plan['items']],plan['prefix'])
            if current['digest']!=plan.get('digest'):raise ValueError('訓練範圍已變更，重新預檢')
            return self._write('JOB',new_id(),{'phase':'PENDING','actor':actor,'dataset_id':current['dataset_id'],'dataset_revision':current['dataset_revision'],'manifest_digest':current['manifest_digest'],'items':current['items'],'purpose':'GEOMETRY_DRAFT_ONLY','owner':None,'cancel_requested':False,'created':time.time(),'last_error':None},0,'training_job_created')

    def training_job_state(self,job_id):
        job=self.get('JOB',job_id)
        if not job:raise ValueError('訓練工作不存在')
        return 'INTERRUPTED' if job['phase']=='RUNNING' and not owner_alive(job['owner']) else job['phase']

    def claim_training_job(self,job_id,expected_revision,approved=False,retry_failed=False,claimed_hook=None):
        if approved is not True:raise ValueError('啟動／中斷續跑需明確確認')
        token=new_id();owner={'pid':os.getpid(),'token':token,'started':time.time()}
        LIVE_OWNERS.add(token)
        try:
            with self.transaction():
                job=self.get('JOB',job_id);lease=self.get('WORKER','geometry-worker')
                automatic=self.get('WORKER','automatic-worker')
                if automatic and automatic.get('active') and owner_alive(automatic.get('owner')):raise ValueError('自動分析worker仍在執行，不能重複啟動訓練')
                if not job or job['revision']!=expected_revision:raise ValueError('工作版次已變更')
                if lease and lease.get('active') and owner_alive(lease.get('owner')):raise ValueError('本資料庫已有單一活動worker，不能跨視窗接管')
                if job['phase']=='RUNNING' and owner_alive(job['owner']):raise ValueError('原工作階段仍活動')
                if job['phase']=='COMPLETED':raise ValueError('全SUCCESS／REUSED工作不重跑')
                if lease and lease.get('active') and lease.get('job_id')!=job_id:
                    old=self.get('JOB',lease['job_id'])
                    if old and old['phase']=='RUNNING':old.update(phase='INTERRUPTED',owner=None,last_error='original owner exited');self._write('JOB',old['id'],old,old['revision'],'training_job_interrupted')
                for item in job['items']:
                    if item['state']=='RUNNING':item.update(state='READY',error='先前未提交單位需恢復')
                    if item['state']=='FAILED' and retry_failed:item.update(state='READY',error=None)
                if not any(i['state']=='READY' for i in job['items']):raise ValueError('沒有待續跑項；失敗項需明確選擇重試')
                job.update(phase='RUNNING',owner=owner,cancel_requested=False,last_error=None);saved=self._write('JOB',job_id,job,expected_revision,'training_job_claimed');self._write('WORKER','geometry-worker',{'active':True,'job_id':job_id,'owner':owner},lease['revision'] if lease else 0,'training_worker_claimed')
                if claimed_hook:claimed_hook(saved)
            return saved
        except BaseException:
            LIVE_OWNERS.discard(token);raise

    def _owned_job(self,job_id,token):
        job=self.get('JOB',job_id);lease=self.get('WORKER','geometry-worker')
        if not job or job['phase']!='RUNNING' or job['owner'].get('token')!=token or not lease or not lease['active'] or lease['job_id']!=job_id or lease['owner']['token']!=token:raise ValueError('worker owner／工作phase已變更，停止舊工作階段')
        return job

    def request_training_cancel(self,job_id,token):
        with self.transaction():
            job=self._owned_job(job_id,token);job['cancel_requested']=True;return self._write('JOB',job_id,job,job['revision'],'training_cancel_requested')

    def _finish_training_job(self,job_id,token,phase,error=None):
        if phase in ('CANCELLED','PAUSED_RESOURCES','FAILED_SYSTEM'):
            job=self._owned_job(job_id,token)
            for item in job['items']:
                if item['state']=='RUNNING':item.update(state='READY',error=error)
            self._write('JOB',job_id,job,job['revision'],'training_uncommitted_item_recoverable')
        job=self._owned_job(job_id,token);job.update(phase=phase,last_error=error,finished=time.time());result=self._write('JOB',job_id,job,job['revision'],'training_job_'+phase.lower());lease=self.get('WORKER','geometry-worker');lease['active']=False;self._write('WORKER','geometry-worker',lease,lease['revision'],'training_worker_released');return result


def run_training_job(root,job_id,token,cancel=None,progress=None,proof_function=None,audit_hook=None,admission=None):
    from .storage import Library
    from .training_store import TrainingStore
    library=Library(root);store=TrainingStore(library)
    if audit_hook:library.event=audit_hook(library.event)
    try:
        for _ in range(201):
            job=store._owned_job(job_id,token)
            index=next((i for i,item in enumerate(job['items']) if item['state']=='READY'),None)
            if index is None:
                phase='COMPLETED_WITH_EXCEPTIONS' if any(i['state']=='FAILED' for i in job['items']) else 'COMPLETED'
                with store.transaction():result=store._finish_training_job(job_id,token,phase)
                if progress:progress(result)
                return result
            if (cancel and cancel.is_set()) or job['cancel_requested']:
                with store.transaction():result=store._finish_training_job(job_id,token,'CANCELLED')
                if progress:progress(result)
                return result
            if admission:
                decision=admission()
                if not decision.allowed:
                    phase='CANCELLED' if cancel and cancel.is_set() else 'PAUSED_RESOURCES'
                    with store.transaction():result=store._finish_training_job(job_id,token,phase,','.join(decision.reasons))
                    if progress:progress(result)
                    return result
            item=job['items'][index];sample=store.get('SAMPLE',item['sample_id'])
            with store.transaction():
                active=store._owned_job(job_id,token);active['items'][index]['state']='RUNNING';store._write('JOB',job_id,active,active['revision'],'training_item_started_not_completed')
            try:
                proof=proof_function(store,sample) if proof_function else store.source_proof(sample['work_id'])
                with store.transaction():
                    current=store._owned_job(job_id,token);current_item=current['items'][index];fresh=store.get('SAMPLE',current_item['sample_id'])
                    if current_item['state']!='RUNNING' or fresh['revision']!=current_item['sample_revision'] or fresh['pins']!=current_item['source_pins'] or fresh['scope_digest']!=current_item['scope_digest']:raise ValueError('選中樣本／用途／版本已變更')
                    validity=store.dataset_validity(current['dataset_id'],[fresh['id']])
                    if not validity['valid'] or validity['dataset']['manifest_digest']!=current['manifest_digest'] or validity['dataset']['revision']!=current['dataset_revision']:raise ValueError('資料集或選中樣本已過期')
                    store.checked(fresh['work_id'],proof);existing=store.existing_geometry_result(current['dataset_id'],fresh['id'])
                    if existing:
                        template=next(t for t in library.templates() if t.id==existing);library._template_provenance(template);state='REUSED'
                    else:
                        plan=store.geometry_learning_plan(current['dataset_id'],fresh['id'],current_item['name']);template=store._write_geometry_draft(plan,proof,job_id=job_id,actor=current['actor']);state='SUCCESS'
                    current_item.update(state=state,template_id=template.id,error=None,attempts=current_item['attempts']+1,finished=time.time());updated=store._write('JOB',job_id,current,current['revision'],'training_item_'+state.lower())
            except (ValueError,OSError) as error:
                with store.transaction():
                    current=store._owned_job(job_id,token);current['items'][index].update(state='FAILED',error=str(error),attempts=current['items'][index]['attempts']+1,finished=time.time());updated=store._write('JOB',job_id,current,current['revision'],'training_item_failed')
            if progress:progress(updated)
        raise RuntimeError('工作超過200項有界步數，停止')
    except BaseException as error:
        # A database/audit failure cannot be treated as an isolated successful item.
        try:
            with store.transaction():store._finish_training_job(job_id,token,'FAILED_SYSTEM',str(error))
        except BaseException:pass  # RUNNING + dead owner is explicitly recoverable INTERRUPTED.
        raise
    finally:
        LIVE_OWNERS.discard(token);library.db.close()

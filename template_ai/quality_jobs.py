"""Durable source-level evaluation units using the existing shared worker lease."""
import copy
import os
import time
from collections import Counter
from .training_store import TrainingStore,digest,text
from .training_pipeline import LIVE_OWNERS,owner_alive
from .model import new_id
from .quality_protocol import QualityProtocols,SIDES
from .quality_pipeline import QualityPipelines
from .quality_gold import QualityGold
from .quality_domains import evaluate_source

JOB='EVAL_JOB'
ITEM='QUALITY_EVAL_ITEM'
RESULT='QUALITY_EVAL_RESULT'


class EvaluationJobs:
    def __init__(self,library):self.library=library;self.store=TrainingStore.bind(library);self.protocols=QualityProtocols(library)
    def get(self,identity):
        row=self.store.get(JOB,identity)
        if not row:raise ValueError('品質評估工作不存在')
        return row

    def create_pair(self,protocol_id,actor,approved=False):
        if approved is not True:raise ValueError('需核對固定兩版試驗與明列來源並明確建立持久工作')
        text(actor,'執行者',120);checked=self.protocols.validity(protocol_id,verify_sources=False)
        if not checked['valid']:raise ValueError('；'.join(checked['errors']))
        protocol=checked['protocol'];scope=protocol['scope'];dataset=self.store.get('QUALITY_SET',scope['dataset_id']);manifest=dataset['manifest'];items=[];source_ids={}
        for declared in manifest['declared_files']:
            for sid in declared['source_ids']:source_ids.setdefault(sid,[]).append(declared['logical_file_key'])
            if not declared['source_ids']:
                key=declared['logical_file_key'];items.append(dict(id=digest(['raw-quality-source',key]),source_id=None,path=declared['declared_physical_paths'][0],page=None,source_hash=None,expected_pins=None,gold_ids=[],logical_file_keys=[key],state='READY',attempts=0,error=None))
        for sid,keys in sorted(source_ids.items()):
            source=self.library.source(sid);gold_ids=[e['gold_id'] for e in dataset['entries'] if e['source_id']==sid]
            items.append(dict(id=digest(['registered-quality-source',sid]),source_id=sid,path=source['current_path'],page=source['page'],source_hash=source['hash'],expected_pins=dict(source_digest=digest(source)),gold_ids=gold_ids,logical_file_keys=sorted(keys),state='READY',attempts=0,error=None))
        if not 1<=len(items)<=1000:raise ValueError('持久評估工作需1～1000個明列來源頁／未解析檔案；請明確分組，不截斷')
        with self.store.transaction():
            self.protocols.check_metadata(scope)
            if self.store.get('QUALITY_PROTOCOL_JOBS',protocol_id):raise ValueError('本試驗已建立工作，請讀回原工作接續，不重建或重測')
            for item in items:
                if item['source_id'] and digest(self.library.source(item['source_id']))!=item['expected_pins']['source_digest']:raise ValueError('建立工作期間來源版本已變更')
            result={}
            for side in SIDES:
                identity=new_id();pin=scope['pipelines'][side]
                result[side]=self.store._write(JOB,identity,dict(protocol_id=protocol_id,protocol_scope_digest=protocol['scope_digest'],side=side,pipeline_id=pin['id'],pipeline_manifest_digest=pin['manifest_digest'],dataset_id=scope['dataset_id'],dataset_revision=scope['dataset_revision'],manifest_digest=scope['dataset_manifest_digest'],scope=dict(protocol=protocol['scope_digest'],side=side,pipeline=pin['manifest_digest']),purpose='INDEPENDENT_QUALITY_EVALUATION_LOCAL',items=copy.deepcopy(items),actor=actor,created=time.time(),phase='READY',owner=None,owner_token=None,result_id=None,cancel_requested=False),0,'quality_evaluation_job_created_not_executed')
            self.store._write('QUALITY_PROTOCOL_JOBS',protocol_id,dict(protocol_id=protocol_id,jobs={side:row['id'] for side,row in result.items()},actor=actor),0,'quality_pair_jobs_linked')
            return result

    def claim(self,identity,revision,approved=False,retry=False,claimed_hook=None):
        if approved is not True:raise ValueError('需明確啟動／接續固定品質工作')
        with self.store.transaction():
            row=self.get(identity)
            self.protocols.check_metadata(self.protocols.get(row['protocol_id'])['scope'])
            if row['revision']!=revision or row['phase'] in ('COMPLETED','COMPLETED_WITH_EXCEPTIONS'):raise ValueError('工作版次已變更／固定側別已完成；不以重測調參')
            for worker in ('geometry-worker','automatic-worker'):
                lease=self.store.get('WORKER',worker)
                if lease and lease.get('active') and owner_alive(lease.get('owner')):raise ValueError('已有共享worker執行，不重複啟動')
            if row['phase']=='RUNNING' and owner_alive(row.get('owner')):raise ValueError('此工作仍有執行者')
            for item in row['items']:
                if item['state']=='RUNNING' or retry and item['state']=='FAILED':item['state']='READY'
            owner=dict(pid=os.getpid(),token=new_id());row.update(phase='RUNNING',owner=owner,owner_token=owner['token'],cancel_requested=False)
            lease=self.store.get('WORKER','automatic-worker');self.store._write('WORKER','automatic-worker',dict(active=True,owner=owner,job_id=identity),lease['revision'] if lease else 0,'quality_worker_claimed_shared_lease')
            result=self.store._write(JOB,identity,row,revision,'quality_job_started_not_completed')
            if claimed_hook:claimed_hook(result)
        LIVE_OWNERS.add(owner['token']);return result

    def owned(self,identity,token):
        row=self.get(identity)
        if row['phase']!='RUNNING' or row.get('owner_token')!=token or not owner_alive(row.get('owner')):raise ValueError('品質工作owner／scope已失效')
        return row

    def finish(self,identity,token,phase,error=None):
        with self.store.transaction():
            row=self.owned(identity,token);row.update(phase=phase,finished=time.time(),system_error=str(error)[:4000] if error else None)
            for item in row['items']:
                if item['state']=='RUNNING':item['state']='READY'
            result=self.store._write(JOB,identity,row,row['revision'],'quality_job_'+phase.lower());lease=self.store.get('WORKER','automatic-worker')
            if not lease or lease.get('owner',{}).get('token')!=token:raise ValueError('共享執行權已改變，未偽造完成')
            lease['active']=False;self.store._write('WORKER','automatic-worker',lease,lease['revision'],'quality_shared_worker_released');return result

    def evaluate_item(self,row,item):
        dataset=self.store.get('QUALITY_SET',row['dataset_id']);policy=self.store.get('QUALITY_POLICY',self.protocols.get(row['protocol_id'])['scope']['policy_id'])['plan']
        if not item['source_id'] or not item['gold_ids']:return None,evaluate_source([],None,policy,unresolved_reason='來源未解析／沒有本機品質用途與人工gold，未讀原稿，仍保留分母')
        if digest(self.library.source(item['source_id']))!=item['expected_pins']['source_digest']:raise ValueError('來源頁版本已改變，未改用新來源')
        # Only this source and trained weights enter prediction. Gold is read afterwards.
        prediction=QualityPipelines(self.library).predict_source(row['pipeline_id'],item['source_id'])
        golds=[]
        for gid in item['gold_ids']:
            checked=QualityGold(self.library).validity(gid,verify_bytes=False)
            if not checked['valid']:raise ValueError('gold／來源／用途許可已失效：'+'；'.join(checked['errors']))
            entry=next(e for e in dataset['entries'] if e['gold_id']==gid)
            if digest(checked['gold'])!=entry['gold_digest']:raise ValueError('gold不是預先固定的版本')
            golds.append(checked['gold'])
        complete=dataset['manifest']['whole_source_gold_complete']
        return prediction,evaluate_source(golds,prediction,policy,complete_source_gold=complete)

    def commit_item(self,identity,token,index,prediction,evaluation):
        with self.store.transaction():
            row=self.owned(identity,token);item=row['items'][index]
            if item['state']!='RUNNING':raise ValueError('來源執行階段已改變')
            if item['source_id'] and digest(self.library.source(item['source_id']))!=item['expected_pins']['source_digest']:raise ValueError('保存前來源版本已變更')
            prediction_ids=[]
            if prediction:
                from .source_links import check_verified,VerifiedSource
                from .trusted_samples import cache_stamps
                p=prediction['source_proof'];check_verified(VerifiedSource(p['path'],p['hash'],tuple(p['stat'])),p['hash'])
                if cache_stamps(self.library.source(item['source_id']))!=prediction['source_cache_stamps']:raise ValueError('保存前cache已變更')
                for work in prediction['predictions']:
                    wid=digest([identity,item['id'],work['key']]);self.store._write('QUALITY_PREDICTED_WORK',wid,dict(job_id=identity,item_id=item['id'],source_id=item['source_id'],source_hash=item['source_hash'],pipeline_manifest_digest=row['pipeline_manifest_digest'],prediction=work,origin=prediction['prediction_origin']),0,'quality_source_only_prediction_saved');prediction_ids.append(wid)
            iid=digest([identity,item['id']]);saved=self.store._write(ITEM,iid,dict(job_id=identity,item_id=item['id'],source_id=item['source_id'],source_hash=item['source_hash'],protocol_scope_digest=row['protocol_scope_digest'],pipeline_manifest_digest=row['pipeline_manifest_digest'],prediction_ids=prediction_ids,evaluation=evaluation,state='UNRESOLVED' if evaluation['unresolved_source_pages'] else 'MEASURED',origin='ACTUAL_FIXED_PIPELINE_EVALUATION',source_proof=prediction['source_proof'] if prediction else None,source_cache_stamps=prediction['source_cache_stamps'] if prediction else None),0,'quality_source_evaluation_atomically_saved')
            item.update(state='FAILED' if evaluation['unresolved_source_pages'] else 'DONE',error=evaluation.get('unresolved_reason'),attempts=item['attempts']+1,result_id=iid,result_digest=digest(saved))
            return self.store._write(JOB,identity,row,row['revision'],'quality_source_result_and_progress_committed')

    def complete(self,identity,token):
        with self.store.transaction():
            row=self.owned(identity,token)
            if any(item['state'] in ('READY','RUNNING') for item in row['items']):raise ValueError('仍有未執行來源，不能將工作標完成')
            critical=Counter();unknown=set();references=[]
            for item in row['items']:
                result=self.store.get(ITEM,item.get('result_id',''))
                if not result:unknown.add('SOURCE_RESULT_MISSING');continue
                if digest(result)!=item['result_digest']:raise ValueError('來源結果收據已改變')
                critical.update(result['evaluation']['critical_errors']);unknown.update(name for name,domain in result['evaluation']['domains'].items() if domain['state']!='MEASURED_DESCRIPTIVE_ONLY');references.append(dict(id=result['id'],digest=digest(result)))
            result_id=new_id();result=self.store._write(RESULT,result_id,dict(job_id=identity,protocol_id=row['protocol_id'],side=row['side'],dataset_id=row['dataset_id'],dataset_manifest_digest=row['manifest_digest'],pipeline_manifest_digest=row['pipeline_manifest_digest'],protocol_scope_digest=row['protocol_scope_digest'],source_results=references,critical_errors=dict(critical),unmeasured_domains=sorted(unknown),quality_gate='FAILED_CRITICAL' if any(critical.values()) else 'EVIDENCE_INSUFFICIENT' if unknown else 'PENDING_STATISTICAL_POLICY_CHECK',quality_pass=False,automatic_recommendation_allowed=False,origin='ACTUAL_FIFO_SOURCE_EVALUATION',finished_at=time.time(),immutable=True),0,'quality_fixed_side_result_saved_not_release')
            use_id=digest([row['protocol_id'],row['side']]);use=self.store.get('QUALITY_PROTOCOL_USE',use_id)
            if not use or use['job_id']!=identity or use['owner_token']!=token or use['state']=='COMPLETED':raise ValueError('固定側別使用權已改變')
            use.update(state='COMPLETED',result_id=result_id,finished_at=time.time());self.store._write('QUALITY_PROTOCOL_USE',use_id,use,use['revision'],'quality_fixed_side_completed_with_immutable_result')
            row['result_id']=result_id;row['phase']='COMPLETED_WITH_EXCEPTIONS' if any(i['state']=='FAILED' for i in row['items']) else 'COMPLETED';row['finished']=time.time();saved=self.store._write(JOB,identity,row,row['revision'],'quality_job_computation_completed_not_quality_pass')
            lease=self.store.get('WORKER','automatic-worker')
            if lease.get('owner',{}).get('token')!=token:raise ValueError('共享worker owner已改變')
            lease['active']=False;self.store._write('WORKER','automatic-worker',lease,lease['revision'],'quality_shared_worker_released');return saved


def run_evaluation(root,identity,token,cancel=None,progress=None,admission=None):
    from .storage import Library
    from .runtime_admission import require_resources,ResourcePause
    library=Library(root);TrainingStore(library);service=EvaluationJobs(library);LIVE_OWNERS.add(token)
    try:
        row=service.owned(identity,token);service.protocols.begin(row['protocol_id'],row['side'],identity,token)
        for index in range(len(row['items'])):
            row=service.owned(identity,token);item=row['items'][index]
            if cancel and cancel.is_set():return service.finish(identity,token,'CANCELLED')
            if item['state']!='READY':continue
            try:
                require_resources(admission)
                with service.store.transaction():
                    current=service.owned(identity,token);current['items'][index]['state']='RUNNING';row=service.store._write(JOB,identity,current,current['revision'],'quality_source_started_not_completed')
                if progress:progress(row)
                prediction,evaluation=service.evaluate_item(row,item);row=service.commit_item(identity,token,index,prediction,evaluation)
            except ResourcePause as error:return service.finish(identity,token,'CANCELLED' if cancel and cancel.is_set() else 'PAUSED_RESOURCES',str(error))
            except (ValueError,OSError) as error:
                evaluation=evaluate_source([],None,{},unresolved_reason=str(error));row=service.commit_item(identity,token,index,None,evaluation)
            if progress:progress(row)
        if cancel and cancel.is_set():return service.finish(identity,token,'CANCELLED')
        return service.complete(identity,token)
    except BaseException as error:
        try:service.finish(identity,token,'FAILED_SYSTEM',str(error))
        except BaseException:pass
        raise
    finally:LIVE_OWNERS.discard(token);library.close()

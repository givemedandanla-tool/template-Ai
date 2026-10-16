"""Semantic candidate operation on the existing AUTO_JOB shared worker.

Validated before AutomaticTraining.claim and dispatched in the existing
run_automatic owned-library/finally scope.
No new queue, worker lease, model activation or source import.
"""
import copy,json,time
from .training_store import digest,text
from .model import new_id
from .semantic_learning import SemanticLearning
from .quality_repairs import QualityRepairs

OPERATION='SEMANTIC_REPAIR_CANDIDATE'


def root_review(service,identity):
    review=service.store.get('QUALITY_REPAIR_ROOT_REVIEW',identity)
    if not review or not review['plan']['can_prepare_candidate']:raise ValueError('根因／來源／人工真值尚不可核對，未建立候選訓練')
    plan=review['plan']
    current=QualityRepairs(service.library).root_plan(plan['issue_id'],plan['layer'],plan['hypothesis'],plan['evidence'],plan['original_reviewed'],plan['truth_reviewed'])
    if current!=plan:raise ValueError('根因核對已過期，需重新核對原稿與真值')
    return review


def create(service,review_id,training_plan,actor,approved=False):
    if approved is not True:raise ValueError('需明確核對局部TRAIN／VALIDATION文字範圍；不使用失效holdout答案')
    text(actor,'局部候選訓練者',120)
    with service.store.transaction():
        review=root_review(service,review_id)
        if review['plan']['layer'] not in ('FIELD_OWNER_SEMANTICS','MODEL_REGRESSION'):raise ValueError('此根因需適當的解析器／OCR／規則／人工修復，不自動以文字模型代替')
        semantic=SemanticLearning.bind(service.library);fresh=semantic.plan(training_plan['work_roles'])
        if fresh!=training_plan:raise ValueError('局部訓練範圍／確認文字版本變更')
        items=[]
        for scope in fresh['scopes']:
            work=service.library.artwork(scope['work_id']);source=service.library.source(work['source_id'])
            items.append(dict(path=source['current_path'],page=source['page'],source_hash=source['hash'],
                source_id=source['id'],work_id=work['id'],work_revision=work['revision'],
                expected_pins=copy.deepcopy(scope['pins']),state='READY',unit_ids=[],attempts=0,
                action='LOCAL_CONFIRMED_TEXT_SOURCE_CHECK_NOT_MODEL_QUALITY'))
        value=dict(operation=OPERATION,phase='READY',items=items,actor=actor,created=time.time(),
            owner=None,cancel_requested=False,semantic_plan=fresh,root_review_id=review_id,
            root_review_digest=digest(review),candidate_id=None,model_id=None,
            purpose='LOCAL_SELECTED_SCOPE_SEMANTIC_CANDIDATE_NOT_ACTIVATION',
            scope=dict(operation=OPERATION,training_digest=fresh['digest'],root_review_digest=digest(review)))
        if len(json.dumps(value,ensure_ascii=False).encode())>1024*1024-4096:raise ValueError('局部訓練工作metadata超過1MiB，需縮小明列範圍；未截斷資料')
        return service.store._write('AUTO_JOB',new_id(),value,0,'repair_local_semantic_candidate_job_created_not_executed')


def check(service,job):
    if job.get('operation')!=OPERATION:raise ValueError('非局部語意修復工作')
    if job.get('candidate_id') or job.get('model_id') or job['phase']=='COMPLETED':raise ValueError('此工作已有實際候選結果，讀回原版本而不重複訓練')
    review=root_review(service,job['root_review_id'])
    if digest(review)!=job['root_review_digest']:raise ValueError('根因核對憑證變更')
    if SemanticLearning.bind(service.library).plan(job['semantic_plan']['work_roles'])!=job['semantic_plan']:raise ValueError('局部訓練文字／資料角色／來源確認已變更')
    expected=dict(operation=OPERATION,training_digest=job['semantic_plan']['digest'],root_review_digest=digest(review))
    if job['scope']!=expected:raise ValueError('局部訓練明列範圍改變，未沿用舊佇列確認')


def run(service,job,token,cancel=None,progress=None,admission=None):
    from .runtime_admission import require_resources,ResourcePause
    identity=job['id']
    def cancelled():return bool(cancel and cancel.is_set())
    try:
        check(service,job)
        if job.get('candidate_id'):raise ValueError('此候選已產生，請讀回原版本，不重訓同工作')
        for index in range(len(job['items'])):
            if cancelled():return service.finish(identity,token,'CANCELLED')
            require_resources(admission)
            current=service.owned(identity,token);item=current['items'][index]
            if item['state']=='SUCCESS':continue
            if item['state']!='READY':raise ValueError('失敗項需明確重試，不略過來源核對')
            service.store.checked(item['work_id'],service.store.source_proof(item['work_id']))
            with service.store.transaction():
                current=service.owned(identity,token);current['items'][index].update(state='SUCCESS',error=None,
                    attempts=item['attempts']+1,action='SOURCE_VERIFIED_NOT_YET_TRAINED')
                current['semantic_training_state']='SOURCES_BEING_VERIFIED_NOT_TRAINED'
                job=service.store._write('AUTO_JOB',identity,current,current['revision'],'repair_training_source_verified')
            if progress:progress(job)
        if cancelled():return service.finish(identity,token,'CANCELLED')
        require_resources(admission)
        with service.store.transaction():
            current=service.owned(identity,token);current['items'][-1].update(state='RUNNING',action='ACTUAL_LOCAL_SEMANTIC_TRAINING_NOT_QUALITY')
            job=service.store._write('AUTO_JOB',identity,current,current['revision'],'repair_candidate_training_started_not_completed')
        if progress:progress(job)
        # Model, candidate reference, final job and lease release commit together.
        with service.store.transaction():
            current=service.owned(identity,token);check(service,current)
            model=SemanticLearning.bind(service.library).train_in_transaction(current['semantic_plan'],current['actor'],True)
            if cancelled():raise ResourcePause('局部訓練取消；尚未提交候選模型')
            candidate=service.store._write('QUALITY_REPAIR_CANDIDATE',new_id(),dict(
                issue_id=root_review(service,current['root_review_id'])['plan']['issue_id'],
                root_review_id=current['root_review_id'],root_review_digest=current['root_review_digest'],
                job_id=identity,model_id=model['id'],model_digest=digest(model),
                training_digest=current['semantic_plan']['digest'],actor=current['actor'],at=time.time(),
                state='ISOLATED_PENDING_ACTUAL_REGRESSION_AND_NEW_INDEPENDENT_HOLDOUT',
                quality_pass=False,can_activate=False,original_and_published_data_modified=False),0,'repair_actual_semantic_candidate_created_not_activated')
            current=service.owned(identity,token);current['items'][-1].update(state='SUCCESS',action='MODEL_CREATED_NOT_ACTIVATED')
            current.update(model_id=model['id'],candidate_id=candidate['id'],semantic_training_state='CANDIDATE_CREATED_NOT_QUALITY_VERIFIED')
            job=service.store._write('AUTO_JOB',identity,current,current['revision'],'repair_candidate_job_result_linked')
            result=service.finish_in_transaction(identity,token,'COMPLETED')
        if progress:progress(result)
        return result
    except ResourcePause as error:
        return service.finish(identity,token,'CANCELLED' if cancelled() else 'PAUSED_RESOURCES',str(error))

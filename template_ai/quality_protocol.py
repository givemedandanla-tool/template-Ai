"""Predeclared paired holdout use, exposure and exact scope, in existing SQLite."""
import copy
import time
from pathlib import Path
from .training_store import TrainingStore,digest,text
from .quality_sets import QualitySets
from .quality_policy import QualityPolicies
from .quality_pipeline import QualityPipelines
from .background import file_digest
from .model import new_id

PROTOCOL='QUALITY_PROTOCOL'
USE='QUALITY_PROTOCOL_USE'
CONSUMED='QUALITY_HOLDOUT_USAGE'
SIDES=('BASELINE','CANDIDATE')


def calculation_files():
    root=Path(__file__).parent
    names=('quality_metrics.py','quality_domains.py','quality_facets.py','quality_diagnostics.py','quality_rechecks.py','coverage_evidence.py','quality_statistics.py','quality_reports.py','quality_mapping.py','quality_logo.py','quality_pipeline.py','quality_engine.py','quality_jobs.py','quality_gold.py','quality_sets.py','quality_groups.py','quality_protocol.py','quality_evaluation.py')
    return {name:file_digest(root/name) for name in names}


class QualityProtocols:
    def __init__(self,library):
        self.library=library;self.store=TrainingStore.bind(library);self.sets=QualitySets(library);self.policies=QualityPolicies(library);self.pipelines=QualityPipelines(library)

    def content_scope(self,dataset):
        return sorted({node.split(':',1)[1] for component in dataset['manifest']['group_components'] for node in component if node.startswith('CONTENT:')})

    def plan(self,name,dataset_id,policy_id,pipelines,reason):
        text(name,'固定獨立試驗名稱',120);text(reason,'試驗目的與預先固定的比較依據',2000)
        if not isinstance(pipelines,dict) or set(pipelines)!=set(SIDES) or any(not isinstance(value,str) or not value for value in pipelines.values()):raise ValueError('先明列基準／候選實際pipeline版本；不能看完分數再選候選')
        checked=self.sets.validity(dataset_id)
        if not checked['valid']:raise ValueError('獨立驗收集無效：'+'；'.join(checked['errors']))
        dataset=checked['dataset'];policy=self.policies.status(policy_id)
        if not policy['valid']:raise ValueError(policy['reason'])
        versions={};environment=None
        for side,identity in sorted(pipelines.items()):
            result=self.pipelines.validity(identity)
            if not result['valid']:raise ValueError(side+'：'+'；'.join(result['errors']))
            record=result['pipeline'];versions[side]=dict(id=identity,revision=record['revision'],manifest_digest=record['manifest_digest'])
            current_env=record['manifest']['environment']
            if environment is None:environment=current_env
            elif environment!=current_env:raise ValueError('基準／候選測試環境不相同，不能公平配對A/B')
        contents=self.content_scope(dataset) if dataset['manifest'].get('evaluation_role','HOLDOUT')=='HOLDOUT' else []
        if any(self.store.get(CONSUMED,sha) for sha in contents):raise ValueError('此來源／相關家族已供先前試驗或已揭露答案，需真正全新獨立群組；複製驗收集不會重置曝光')
        scope=dict(schema_version=1,evaluation_role=dataset['manifest'].get('evaluation_role','HOLDOUT'),name=name,dataset_id=dataset_id,dataset_revision=dataset['revision'],dataset_manifest_digest=dataset['manifest_digest'],policy_id=policy_id,policy_revision=policy['policy']['revision'],policy_digest=digest(policy['policy']),pipelines=versions,environment=copy.deepcopy(environment),calculation_files=calculation_files(),content_scope=contents,gold_work_count=dataset['manifest']['gold_work_count'],gold_object_count=dataset['manifest']['gold_object_count'],source_file_count=dataset['manifest']['file_count'],independent_groups=dataset['manifest']['independent_group_count'],reason=reason,source_only_predictions_required=True,predeclared_sides=list(SIDES),one_frozen_protocol_per_related_holdout_group=True)
        result=dict(scope=scope,scope_digest=digest(scope),quality_pass_claim=False,independence_claim=dataset['manifest']['independence_scope_ready'],whole_source_gold_complete=dataset['manifest']['whole_source_gold_complete'],complete_font_environment=bool(environment['fonts']['complete']))
        result['digest']=digest(result);return result

    def freeze(self,plan,actor,approved=False):
        if approved is not True:raise ValueError('需先核對固定資料／真值／品質政策／兩版pipeline及一次性holdout範圍')
        text(actor,'試驗宣告者',120);preview=copy.deepcopy(plan);expected=preview.pop('digest',None)
        if expected!=digest(preview):raise ValueError('預先宣告試驗的預覽已被修改')
        scope=plan['scope'];current=self.plan(scope['name'],scope['dataset_id'],scope['policy_id'],{side:row['id'] for side,row in scope['pipelines'].items()},scope['reason'])
        if current!=plan:raise ValueError('固定比較條件已改變')
        with self.store.transaction():
            self.check_metadata(scope)
            current_set=self.sets.validity(scope['dataset_id'],verify_bytes=False)
            if not current_set['valid']:raise ValueError('gold／群組依賴已改變：'+'；'.join(current_set['errors']))
            if any(self.store.get(CONSUMED,sha) for sha in scope['content_scope']):raise ValueError('holdout已被其他試驗保留／曝光')
            return self.store._write(PROTOCOL,new_id(),dict(scope=copy.deepcopy(scope),scope_digest=plan['scope_digest'],actor=actor,declared_at=time.time(),immutable=True,state='FROZEN_BEFORE_ANY_SCORE',quality_pass=False),0,'quality_paired_protocol_predeclared_not_quality_release')

    def get(self,identity):
        value=self.store.get(PROTOCOL,identity)
        if not value:raise ValueError('固定試驗版本不存在')
        return value

    def check_metadata(self,scope):
        dataset=self.store.get('QUALITY_SET',scope['dataset_id']);policy=self.policies.status(scope['policy_id'])
        if not dataset or dataset['revision']!=scope['dataset_revision'] or dataset['manifest_digest']!=scope['dataset_manifest_digest'] or not policy['valid'] or digest(policy['policy'])!=scope['policy_digest']:raise ValueError('固定驗收集／政策版本已改變')
        if self.store.get('HOLDOUT_EXPOSED',scope['dataset_id']):raise ValueError('holdout已揭露或獨立性已失效')
        for side,pin in scope['pipelines'].items():
            record=self.store.get('QUALITY_PIPELINE',pin['id'])
            if not record or record['revision']!=pin['revision'] or record['manifest_digest']!=pin['manifest_digest']:raise ValueError('實際pipeline版本已改變')

    def validity(self,identity,verify_sources=True):
        protocol=self.get(identity);scope=protocol['scope'];errors=[]
        try:
            if digest(scope)!=protocol['scope_digest'] or calculation_files()!=scope['calculation_files']:raise ValueError('試驗／計算口徑版本已改變')
            self.check_metadata(scope)
            dataset=self.sets.validity(scope['dataset_id'],verify_sources)
            if not dataset['valid']:errors+=dataset['errors']
            for side,pin in scope['pipelines'].items():
                checked=self.pipelines.validity(pin['id'])
                if not checked['valid']:errors += [side+'：'+e for e in checked['errors']]
            for sha in scope['content_scope']:
                used=self.store.get(CONSUMED,sha)
                if used and used['protocol_id']!=identity:errors.append('此來源／相關群組已由其他試驗使用，不能視為新獨立樣本')
        except (OSError,ValueError,KeyError) as error:errors.append(str(error))
        return dict(valid=not errors,errors=sorted(set(errors)),protocol=protocol)

    def begin(self,identity,side,job_id,owner_token):
        if side not in SIDES:raise ValueError('試驗側別不合法')
        text(job_id,'持久工作ID',128);text(owner_token,'本次執行owner',128)
        checked=self.validity(identity,verify_sources=False)
        if not checked['valid']:raise ValueError('；'.join(checked['errors']))
        with self.store.transaction():return self._begin_in_transaction(checked['protocol'],side,job_id,owner_token)

    def _begin_in_transaction(self,protocol,side,job_id,owner_token):
        if not self.store.db.in_transaction:raise RuntimeError('固定試驗使用必須在既有同SQLite交易內提交')
        scope=protocol['scope'];self.check_metadata(scope);identity=protocol['id'];uid=digest([identity,side]);prior=self.store.get(USE,uid)
        job=self.store.get('EVAL_JOB',job_id)
        if side not in SIDES or not job or job.get('protocol_id')!=identity or job.get('side')!=side or job.get('phase')!='RUNNING' or job.get('owner_token')!=owner_token:raise ValueError('品質試驗必須由綁定相同protocol／側別／owner的持久工作執行')
        if prior:
            if prior['job_id']!=job_id or prior['state']=='COMPLETED':raise ValueError('此固定側別已由另一工作保留／已完成，不自動重跑或另測同一holdout')
        for sha in scope['content_scope']:
            used=self.store.get(CONSUMED,sha)
            if used and used['protocol_id']!=identity:raise ValueError('來源／相關群組已供另一試驗，不准反覆調參重測')
            if not used:self.store._write(CONSUMED,sha,dict(protocol_id=identity,dataset_id=scope['dataset_id'],state='RESERVED_FOR_ONE_PREDECLARED_PAIR',at=time.time()),0,'quality_holdout_group_first_protocol_reserved')
        return self.store._write(USE,uid,dict(protocol_id=identity,side=side,job_id=job_id,owner_token=owner_token,state='STARTED_FIXED_SCOPE',scope_digest=protocol['scope_digest'],started_at=prior['started_at'] if prior else time.time(),resumed_at=time.time() if prior else None),prior['revision'] if prior else 0,'quality_fixed_side_started_or_same_job_resumed')

    def expose(self,identity,actor,reason,approved=False):
        if approved is not True:raise ValueError('查看正確答案／逐案對照將標示holdout已揭露；需明確核對影響')
        text(actor,'答案檢視者',120);text(reason,'檢視目的',2000)
        with self.store.transaction():
            protocol=self.get(identity);scope=protocol['scope'];prior=self.store.get('HOLDOUT_EXPOSED',scope['dataset_id'])
            for sha in scope['content_scope']:
                used=self.store.get(CONSUMED,sha)
                if not used:self.store._write(CONSUMED,sha,dict(protocol_id=identity,dataset_id=scope['dataset_id'],state='ANSWERS_EXPOSED_NOT_FRESH_HOLDOUT',at=time.time()),0,'quality_answer_view_reserves_group_against_future_tuning')
            record=dict(dataset_id=scope['dataset_id'],protocol_id=identity,actor=actor,reason=reason,at=time.time(),state='ANSWERS_EXPOSED_REQUIRES_NEW_INDEPENDENT_GROUP' if scope.get('evaluation_role','HOLDOUT')=='HOLDOUT' else 'DIAGNOSTIC_ANSWERS_EXPOSED_NOT_INDEPENDENT',old_evaluation_records_preserved=True)
            exposure=self.store.get('QUALITY_ANSWER_EXPOSURE',identity)
            saved=self.store._write('QUALITY_ANSWER_EXPOSURE',identity,record,exposure['revision'] if exposure else 0,'quality_answers_explicitly_viewed_local_only')
            if scope.get('evaluation_role','HOLDOUT')=='HOLDOUT':return self.store._write('HOLDOUT_EXPOSED',scope['dataset_id'],record,prior['revision'] if prior else 0,'quality_gold_answers_exposed_not_fresh_test')
            return saved

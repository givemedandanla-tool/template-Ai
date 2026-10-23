"""Versioned accepted runtime deployments and revalidated explicit rollback."""
import copy,time
from .training_store import TrainingStore,digest,text
from .model import new_id
from .quality_reports import QualityReports
from .quality_pipeline import QualityPipelines
from .quality_repair_gates import QualityRepairGates,STAGES

ACTIVE='QUALITY_PIPELINE_ACTIVE'
EVENT='QUALITY_PIPELINE_DEPLOYMENT'
KEY='automatic-source'
IMPACT='QUALITY_REPAIR_IMPACT_REVIEW'


class QualityRepairReleases:
    def __init__(self,library):self.library=library;self.store=TrainingStore.bind(library)

    def impact_plan(self,candidate_id):
        from .quality_rechecks import QualityRechecks
        from .quality_repairs import QualityRepairs
        candidate=QualityRepairGates(self.library).candidate(candidate_id);root=candidate['plan'];issue=self.store.get('QUALITY_REPAIR_ISSUE',root['issue_id'])
        extra=set()
        for parent in root['parents']:
            row=self.store.get(parent['kind'],parent['id'])
            if parent['kind']=='RULE':extra.update(ref['work_id'] for ref in row['positive_examples']+row['counterexamples'])
            elif parent['kind']=='QUALITY_REPAIR_CANDIDATE':extra.update(scope['work_id'] for scope in self.store.get('SEMANTIC_MODEL',row['model_id'])['plan']['scopes'])
        source=QualityRechecks(self.library).source_dependencies(issue['evidence']['work_id'],sorted(extra))
        review=self.store.get('QUALITY_REPAIR_ROOT_REVIEW',root['root_review_id']);layer=review['plan']['layer']
        component='MODEL' if layer in ('FIELD_OWNER_SEMANTICS','MODEL_REGRESSION') else 'PARSER'
        original=self.store.get('QUALITY_PIPELINE',issue['evidence'].get('pipeline_id',''))
        if not original:raise ValueError('需先取得原問題實際版本與歷史影響')
        if component=='MODEL' and not original['manifest'].get('semantic_model_id'):component='PARSER'
        dependency=QualityRechecks(self.library).dependencies(original['id'],component)
        rule_impacts=[QualityRechecks(self.library).dependencies(original['id'],'RULE',rule['id']) for rule in original['manifest'].get('rules',[])]
        work_ids=sorted(set(source['affected_work_ids'])|{r['work_id'] for impact in [dependency,*rule_impacts] for r in impact['rows']})
        pending=[]
        for wid in work_ids:
            pending.extend(row[0] for row in self.store.db.execute("SELECT id FROM training_records WHERE kind='QUALITY_WORK_QUARANTINE' AND json_extract(payload,'$.work_id')=? AND json_extract(payload,'$.state')='REVIEW_REQUIRED' ORDER BY id",(wid,)).fetchmany(201))
            if len(pending)>200:raise ValueError('待重審超過200件，需分組處理，不截斷放行')
        result=dict(candidate_id=candidate_id,candidate_digest=digest(candidate),source_impact=source,component_impact=dependency,rule_impacts=rule_impacts,
                    affected_work_ids=work_ids,pending_historical_rechecks=sorted(set(pending)),
                    missing_historical_evidence=bool(source['missing_historical_nodes'] or any(impact['missing_historical_work_ids'] for impact in [dependency,*rule_impacts])),
                    unknown_unrecorded_dependencies=True,unscanned_history_is_not_certified_safe=True,
                    original_and_published_data_modified=False)
        result['digest']=digest(result);return result

    def confirm_impact(self,plan,actor,reason,approved=False):
        if approved is not True:raise ValueError('需明確核對已知／潛在／未知歷史影響及候選適用邊界')
        text(actor,'歷史影響核對者',120);text(reason,'已知影響與未知歷史的人工處置依據',2000)
        with self.store.transaction():
            if self.impact_plan(plan['candidate_id'])!=plan:raise ValueError('歷史影響／重審已改變')
            return self.store._write(IMPACT,new_id(),dict(plan=copy.deepcopy(plan),actor=actor,reason=reason,at=time.time(),immutable=True),0,'repair_historical_impact_reviewed_not_recheck_clearance')

    def quality(self,decision_id):
        decision=self.store.get('QUALITY_VERSION_DECISION',decision_id)
        status=QualityReports(self.library).recommendation_status(decision_id)
        if not decision or not status['quality_verified_recommendation_allowed']:raise ValueError('品質版本不可信，禁止啟用／安全回退：'+'；'.join(status['errors']))
        checked=QualityPipelines(self.library).validity(decision['pipeline_id'])
        if not checked['valid']:raise ValueError('凍結執行版本不可核對：'+'；'.join(checked['errors']))
        return decision,checked['pipeline']

    def plan(self,decision_id,expected_revision,operation='DEPLOY',gate_id=None,impact_review_id=None,target_event_id=None):
        if operation not in ('INITIAL_BASELINE','DEPLOY','ROLLBACK') or type(expected_revision) is not int or expected_revision<0:raise ValueError('需明列版本動作與目前正式指標版次')
        current=self.store.get(ACTIVE,KEY)
        if (current['revision'] if current else 0)!=expected_revision:raise ValueError('正式啟用指標已改變，需重新預覽')
        decision,pipeline=self.quality(decision_id);gate=None;impact=None;target=None
        if operation=='INITIAL_BASELINE':
            if current or gate_id or target_event_id:raise ValueError('初始可信基準僅適用尚無正式指標；修復／回退必須完整Gate')
            if self.store.db.execute("SELECT 1 FROM training_records WHERE kind IN ('QUALITY_REPAIR_ISSUE','QUALITY_REPAIR_CANDIDATE','QUALITY_REPAIR_PIPELINE_CANDIDATE') LIMIT 1").fetchone():raise ValueError('已有修復問題／候選，不能用初始基準入口繞過順序Gate')
            if any(r.get('state')=='ISOLATED_APPROVED_REPAIR_CANDIDATE' for r in pipeline['manifest'].get('rule_records',[])):raise ValueError('隔離修復規則不能繞過Gate作初始啟用')
        elif operation=='ROLLBACK':
            target=self.store.get(EVENT,target_event_id)
            if not current or not target or target['plan']['decision_id']!=decision_id:raise ValueError('需明列已部署的可信舊版本及目前指標')
            self.check_event(target)
            gate_id=target['plan']['gate_id'];impact_review_id=target['plan']['impact_review_id']
        if operation=='DEPLOY' or operation=='ROLLBACK' and gate_id:
            gate=QualityRepairGates(self.library).checked_gate(gate_id)
            if gate['plan']['stage']!=STAGES[-1] or gate['plan']['report_id']!=decision['report_id']:raise ValueError('需同一exact候選的新獨立品質接受與完整前置順序Gate')
            impact=self.store.get(IMPACT,impact_review_id)
            if not impact or impact['plan']['candidate_id']!=gate['plan']['candidate_id']:raise ValueError('需明確歷史影響核對憑證')
            fresh=self.impact_plan(gate['plan']['candidate_id'])
            if fresh!=impact['plan'] or fresh['pending_historical_rechecks'] or fresh['missing_historical_evidence']:raise ValueError('歷史高風險仍待重審／有缺失或影響範圍變更，不採用候選')
        report=self.store.get('QUALITY_PAIR_REPORT',decision['report_id'])
        result=dict(operation=operation,expected_revision=expected_revision,previous_active_digest=digest(current) if current else None,
                    decision_id=decision_id,decision_digest=digest(decision),pipeline_id=pipeline['id'],pipeline_manifest_digest=pipeline['manifest_digest'],
                    report_id=report['id'],report_digest=digest(report),gate_id=gate_id,gate_digest=digest(gate) if gate else None,
                    impact_review_id=impact_review_id,impact_review_digest=digest(impact) if impact else None,
                    target_event_id=target_event_id,target_event_digest=digest(target) if target else None,
                    verified_scope=copy.deepcopy(report['plan']['denominators']),
                    source_formats_and_native_illustrator_generalization='NOT_CERTIFIED_OUTSIDE_RECORDED_DATASET_AND_ENVIRONMENT',
                    original_and_published_data_modified=False,automatic_fallback=False)
        result['digest']=digest(result);return result

    def confirm(self,plan,actor,reason,approved=False):
        if approved is not True:raise ValueError('需明確確認exact正式採用／安全回退，預設不啟用')
        text(actor,'正式版本採用者',120);text(reason,'採用邊界／回退依據',2000)
        with self.store.transaction():
            current=self.plan(plan['decision_id'],plan['expected_revision'],plan['operation'],plan['gate_id'],plan['impact_review_id'],plan['target_event_id'])
            if current!=plan:raise ValueError('啟用／回退品質與歷史證據已改變')
            event=self.store._write(EVENT,new_id(),dict(plan=copy.deepcopy(plan),actor=actor,reason=reason,at=time.time(),immutable=True),0,'quality_exact_runtime_deployment_recorded')
            pointer=self.store._write(ACTIVE,KEY,dict(event_id=event['id'],event_digest=digest(event),pipeline_id=plan['pipeline_id'],state='ACTIVE_EXPLICITLY_ACCEPTED_FROZEN_PIPELINE'),plan['expected_revision'],'quality_runtime_pointer_cas_committed')
            return dict(event=event,pointer=pointer)

    def check_event(self,event):
        plan=event['plan'];decision,pipeline=self.quality(plan['decision_id'])
        if digest(decision)!=plan['decision_digest'] or pipeline['manifest_digest']!=plan['pipeline_manifest_digest']:raise ValueError('部署exact版本／品質決策已變更')
        report=self.store.get('QUALITY_PAIR_REPORT',plan['report_id'])
        if digest(report)!=plan['report_digest']:raise ValueError('部署品質報告指紋不符')
        if plan['gate_id']:
            gate=QualityRepairGates(self.library).checked_gate(plan['gate_id'])
            impact=self.store.get(IMPACT,plan['impact_review_id'])
            if digest(gate)!=plan['gate_digest'] or digest(impact)!=plan['impact_review_digest']:raise ValueError('部署順序／歷史影響憑證失聯')
            for wid in impact['plan']['affected_work_ids']:
                if self.store.db.execute("SELECT 1 FROM training_records WHERE kind='QUALITY_WORK_QUARANTINE' AND json_extract(payload,'$.work_id')=? AND json_extract(payload,'$.state')='REVIEW_REQUIRED' LIMIT 1",(wid,)).fetchone():raise ValueError('部署後歷史高風險重新待審，維持阻擋')
        return event

    def pin(self):
        pointer=self.store.get(ACTIVE,KEY)
        if pointer is None:return None
        if pointer.get('restore_state') or pointer['state']!='ACTIVE_EXPLICITLY_ACCEPTED_FROZEN_PIPELINE':raise ValueError('正式版本需明確重新核對，未自動改用其他舊版')
        event=self.store.get(EVENT,pointer['event_id'])
        if not event or digest(event)!=pointer['event_digest'] or pointer['pipeline_id']!=event['plan']['pipeline_id']:raise ValueError('正式部署憑證失聯，未自動回退')
        self.check_event(event)
        return dict(event_id=event['id'],event_digest=digest(event),pipeline_id=pointer['pipeline_id'],pipeline_manifest_digest=event['plan']['pipeline_manifest_digest'],decision_id=event['plan']['decision_id'],active_revision=pointer['revision'])

    def check_pin(self,pin):
        if not isinstance(pin,dict):raise ValueError('工作正式版本需exact部署憑證')
        pointer=self.store.get(ACTIVE,KEY)
        if pointer and pointer.get('restore_state'):raise ValueError('備份恢復後需明確重新核對正式部署，不自動續用舊工作版本')
        event=self.store.get(EVENT,pin.get('event_id',''))
        if not event or digest(event)!=pin.get('event_digest') or event['plan']['pipeline_id']!=pin.get('pipeline_id') or event['plan']['pipeline_manifest_digest']!=pin.get('pipeline_manifest_digest') or event['plan']['decision_id']!=pin.get('decision_id') or pin.get('active_revision')!=event['plan']['expected_revision']+1:raise ValueError('工作綁定的部署／版本憑證不符，不切換模型')
        self.check_event(event);return event

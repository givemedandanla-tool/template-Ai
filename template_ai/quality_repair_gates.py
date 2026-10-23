"""Ordered repair receipts using actual existing paired source evaluations."""
import copy,time
from .training_store import TrainingStore,digest,text
from .model import new_id
from .quality_repair_training import root_review
from .quality_pipeline import QualityPipelines
from .quality_protocol import QualityProtocols,REPAIR
from .quality_reports import QualityReports

STAGES=('ROOT_REGRESSION','CRITICAL_CONTROLS','INDEPENDENT_ACCEPTANCE')
CANDIDATE='QUALITY_REPAIR_PIPELINE_CANDIDATE'
GATE='QUALITY_REPAIR_GATE'


class QualityRepairGates:
    def __init__(self,library):self.library=library;self.store=TrainingStore.bind(library)

    def candidate_plan(self,review_id,pipeline_id):
        review=root_review(self,review_id);issue=self.store.get('QUALITY_REPAIR_ISSUE',review['plan']['issue_id'])
        checked=QualityPipelines(self.library).validity(pipeline_id)
        if not checked['valid']:raise ValueError('候選實際pipeline不可核對：'+'；'.join(checked['errors']))
        pipeline=checked['pipeline'];manifest=pipeline['manifest'];parents=[];layer=review['plan']['layer']
        if issue['evidence'].get('pipeline_manifest_digest')==pipeline['manifest_digest']:raise ValueError('實際候選版本沒有變更，不能只換名稱宣稱修復')
        if layer in ('FIELD_OWNER_SEMANTICS','MODEL_REGRESSION'):
            row=self.store.db.execute("SELECT id FROM training_records WHERE kind='QUALITY_REPAIR_CANDIDATE' AND json_extract(payload,'$.root_review_id')=? AND json_extract(payload,'$.model_id')=? ORDER BY id LIMIT 2",(review_id,manifest.get('semantic_model_id'))).fetchall()
            if len(row)!=1:raise ValueError('語意修復需同一根因及實際局部訓練候選，不能代換未訓練版本')
            candidate=self.store.get('QUALITY_REPAIR_CANDIDATE',row[0][0]);model=self.store.get('SEMANTIC_MODEL',candidate['model_id'])
            if digest(model)!=candidate['model_digest'] or candidate['root_review_digest']!=digest(review):raise ValueError('局部模型候選／根因憑證已改變')
            parents.append(dict(kind='QUALITY_REPAIR_CANDIDATE',id=candidate['id'],digest=digest(candidate)))
        if layer=='NOISE_RULE':
            from .quality_repair_rules import STATE,checked as checked_rule
            rules=[r for r in manifest.get('rule_records',[]) if r['state']==STATE and r['root_review_id']==review_id]
            if not rules:raise ValueError('雜訊修復需同根因的獨立核准隔離規則')
            for rule in rules:
                checked_rule(self.store,rule['id'],rule['revision']);parents.append(dict(kind='RULE',id=rule['id'],digest=digest(rule)))
        result=dict(root_review_id=review_id,root_review_digest=digest(review),issue_id=issue['id'],
                    pipeline_id=pipeline_id,pipeline_revision=pipeline['revision'],pipeline_manifest_digest=pipeline['manifest_digest'],
                    parents=parents,quality_pass=False,production_active=False,original_and_published_data_modified=False)
        result['digest']=digest(result);return result

    def register(self,plan,actor,reason,approved=False):
        if approved is not True:raise ValueError('需明確核對exact候選版本；登錄不代表正式採用')
        text(actor,'修復版本核對者',120);text(reason,'局部修復邊界及對照依據',2000)
        with self.store.transaction():
            if self.candidate_plan(plan['root_review_id'],plan['pipeline_id'])!=plan:raise ValueError('候選來源／模型／規則／根因改變')
            return self.store._write(CANDIDATE,new_id(),dict(plan=copy.deepcopy(plan),actor=actor,reason=reason,at=time.time(),immutable=True),0,'repair_exact_pipeline_candidate_registered_not_activated')

    def candidate(self,identity):
        row=self.store.get(CANDIDATE,identity)
        if not row or self.candidate_plan(row['plan']['root_review_id'],row['plan']['pipeline_id'])!=row['plan']:raise ValueError('exact修復候選已失效，需重新核對')
        return row

    def checked_gate(self,identity):
        row=self.store.get(GATE,identity)
        if not row or not row['plan']['passed'] or self.plan(row['plan']['report_id'])!=row['plan']:raise ValueError('前階段未通過或來源／結果／版本已改變，不跳階')
        return row

    def stage_context(self,candidate_id,stage,previous_gate_id,dataset_id,pipelines):
        if stage not in STAGES:raise ValueError('修復階段需依原問題／關鍵對照／新獨立驗收順序')
        candidate=self.candidate(candidate_id);plan=candidate['plan'];issue=self.store.get('QUALITY_REPAIR_ISSUE',plan['issue_id'])
        if pipelines.get('CANDIDATE')!=plan['pipeline_id']:raise ValueError('各階段必須使用相同exact候選版本')
        if pipelines.get('BASELINE')!=issue['evidence'].get('pipeline_id'):raise ValueError('基準必須是原問題的實際版本；原稿疑義先取得實際失敗憑證')
        dataset=self.store.get('QUALITY_SET',dataset_id)
        if not dataset:raise ValueError('階段資料集不存在')
        prior=None
        if stage==STAGES[0]:
            if previous_gate_id:raise ValueError('原問題回歸不可冒接其他Gate')
            origin=QualityProtocols(self.library).get(issue['evidence']['protocol_id'])
            from .quality_repair_truth import checked as checked_truth
            from .quality_repairs import QualityRepairs
            truth=checked_truth(QualityRepairs(self.library),issue['id'])
            expected_dataset=truth['plan']['dataset_id'] if truth else origin['scope']['dataset_id']
            if dataset_id!=expected_dataset:raise ValueError('先重播原問題同一來源及明確核對的有效人工答案')
        else:
            prior=self.checked_gate(previous_gate_id)
            if prior['plan']['stage']!=STAGES[STAGES.index(stage)-1] or prior['plan']['candidate_id']!=candidate_id:raise ValueError('需同一候選的直接前階段PASS憑證')
            previous=QualityProtocols(self.library).get(prior['plan']['protocol_id'])
            old=self.store.get('QUALITY_SET',previous['scope']['dataset_id'])
            current_nodes={node for group in dataset['manifest']['group_components'] for node in group}
            old_nodes={node for group in old['manifest']['group_components'] for node in group}
            if current_nodes.intersection(old_nodes):raise ValueError('新階段需無關來源／客戶／家族群組，不重用原問題或對照答案')
            origin=QualityProtocols(self.library).get(issue['evidence']['protocol_id'])
            original=self.store.get('QUALITY_SET',origin['scope']['dataset_id'])
            if current_nodes.intersection(node for group in original['manifest']['group_components'] for node in group):raise ValueError('不得重用原問題相關家族作新階段')
            if stage==STAGES[2] and dataset['manifest'].get('evaluation_role','HOLDOUT')!='HOLDOUT':raise ValueError('最後階段需真正全新獨立HOLDOUT，不是TRAIN／VALIDATION')
        return dict(candidate_id=candidate_id,candidate_digest=digest(candidate),stage=stage,previous_gate_id=previous_gate_id,
                    previous_gate_digest=digest(prior) if prior else None,root_review_id=plan['root_review_id'])

    def protocol_plan(self,candidate_id,stage,dataset_id,policy_id,reason,previous_gate_id=None):
        candidate=self.candidate(candidate_id);issue=self.store.get('QUALITY_REPAIR_ISSUE',candidate['plan']['issue_id'])
        pipelines=dict(BASELINE=issue['evidence'].get('pipeline_id'),CANDIDATE=candidate['plan']['pipeline_id'])
        binding=dict(candidate_id=candidate_id,stage=stage,previous_gate_id=previous_gate_id)
        return QualityProtocols(self.library).plan(stage,dataset_id,policy_id,pipelines,reason,
            repair_review_id=candidate['plan']['root_review_id'] if stage==STAGES[0] else None,repair_stage=binding)

    def plan(self,report_id):
        report=self.store.get('QUALITY_PAIR_REPORT',report_id)
        if not report:raise ValueError('階段尚無已保存的實際雙側比較報告')
        current=QualityReports(self.library).plan(report['plan']['protocol_id'])
        if current!=report['plan']:raise ValueError('雙側報告來源／版本／計算口徑已改變')
        protocol=QualityProtocols(self.library).get(current['protocol_id']);scope=protocol['scope'];binding=scope.get('repair_stage')
        if not binding:raise ValueError('這不是預先綁定順序的修復試驗，不接受事後補Gate')
        # QualityReports.plan -> protocol.validity -> check_metadata already
        # freshly validates this exact stage/candidate and the entire prior
        # gate chain. Repeating stage_context here branches that same chain
        # exponentially; read immutable rows after that authoritative check.
        blockers=[];stage=binding['stage'];candidate=self.store.get(CANDIDATE,binding['candidate_id'])
        if not candidate:raise ValueError('修復候選憑證失聯')
        issue=self.store.get('QUALITY_REPAIR_ISSUE',candidate['plan']['issue_id'])
        if not issue:raise ValueError('原問題憑證失聯')
        if not current['fair_comparison']:blockers.append('原稿／真值／兩側來源分母仍不可核對')
        if current['new_critical_errors'] or current['class_regressions']:blockers.append('新增重大錯誤或既有類別退步')
        if binding['previous_gate_id']:
            prior=self.store.get(GATE,binding['previous_gate_id'])
            if not prior:raise ValueError('前置Gate憑證失聯')
            if protocol['declared_at']<prior['at']:blockers.append('試驗早於前一階段PASS，不能事後跳階')
        if stage==STAGES[0]:
            target=issue['evidence']['row']['case'];keys=('work_id','gold_id','reason','gold_kind','kind_error','critical_owner_error')
            def matches(case):return case.get('source_id')==issue['evidence']['source_id'] and all(case.get(key)==target.get(key) for key in keys)
            fixed=sum(matches(case) for case in current['fixed_cases']);remaining=sum(matches(case) for case in current['unresolved_cases']+current['new_cases'])
            if not fixed or remaining:blockers.append('原始失敗尚未由實際候選消除；不能用手填已修復')
            if scope.get('purpose')!=REPAIR:blockers.append('原問題重播不可當獨立品質驗收')
        elif stage==STAGES[1]:
            if any(any(current['critical_errors'][side].values()) for side in ('BASELINE','CANDIDATE')):blockers.append('關鍵對照本身仍有重大錯誤')
            statistics=current['results']['CANDIDATE']['statistics']
            required={'person_ownership':('ALL',),'field_types':('name','phone'),'whole_logo':('ALL',),'physical_size':('ALL',),'customer_style_mapping':('ALL',),'work_segmentation':('ALL',)}
            for domain,kinds in required.items():
                for kind in kinds:
                    row=statistics['domains'][domain]['classes'].get(kind)
                    if not row or row['gold_objects']<1 or row['unknown_source_units']:blockers.append(domain+':'+kind+'關鍵對照缺少有效正例／有未知')
                    before=current['results']['BASELINE']['statistics']['domains'][domain]['classes'].get(kind)
                    if domain!='physical_size' and (not before or not (before.get('descriptive_counts') or {}).get('tp') or not row or not (row.get('descriptive_counts') or {}).get('tp')):blockers.append(domain+':'+kind+'缺少基準與候選均實際正確的關鍵對照')
                    if domain=='physical_size' and (not before or before['failed_independent_groups'] or row and row['failed_independent_groups']):blockers.append('物理尺寸對照仍超出明確mm容差')
            pair=self.store.get('QUALITY_PROTOCOL_JOBS',protocol['id']);job=self.store.get('EVAL_JOB',pair['jobs']['CANDIDATE'])
            has_multi=any(self.store.get('QUALITY_EVAL_ITEM',item['result_id'])['facets']['multi_work']==['YES'] for item in job['items'] if item.get('result_id'))
            if not has_multi:blockers.append('缺少實際單檔多作品切分對照')
        elif not current['candidate_decision_eligible']:blockers.append('新的獨立UI053品質驗收尚未達標')
        result=dict(candidate_id=binding['candidate_id'],stage=stage,previous_gate_id=binding['previous_gate_id'],
                    report_id=report_id,report_digest=digest(report),protocol_id=protocol['id'],protocol_scope_digest=protocol['scope_digest'],
                    passed=not blockers,blockers=sorted(set(blockers)),production_active=False,
                    independence_claim=stage==STAGES[2] and not blockers,original_and_published_data_modified=False)
        result['digest']=digest(result);return result

    def confirm(self,plan,actor,approved=False):
        if approved is not True:raise ValueError('需明確保存階段驗證憑證；失敗仍保留而不放行')
        text(actor,'階段驗證者',120)
        with self.store.transaction():
            if self.plan(plan['report_id'])!=plan:raise ValueError('階段證據改變')
            return self.store._write(GATE,new_id(),dict(plan=copy.deepcopy(plan),actor=actor,at=time.time(),immutable=True),0,'repair_ordered_stage_receipt_not_activation')

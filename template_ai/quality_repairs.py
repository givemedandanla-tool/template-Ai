"""Local repair issues reference existing truth/results; never duplicate a trainer.

Canonical source-bound repair intake; candidates never mutate formal data.
"""
import copy,json,time
from .training_store import TrainingStore,digest,text
from .model import new_id

ROOT_LAYERS=(
    'SOURCE_INCOMPLETE','WORK_SEGMENTATION','NATIVE_TEXT_EFFECT',
    'OCR','FIELD_OWNER_SEMANTICS','NOISE_RULE','WHOLE_LOGO',
    'SIZE_SPECIFIC_LOGO_ASSET','CUSTOMER_STYLE_VERSION','MODEL_REGRESSION',
    'DISPUTED_GOLD')


class QualityRepairs:
    def __init__(self,library):
        self.library=library;self.store=TrainingStore.bind(library)

    def source_state(self,work_id):
        work=self.library.artwork(work_id)
        if not work:raise ValueError('修復作品失聯，不能猜測其他作品')
        facts=self.store.facts(work_id);errors=[]
        try:
            proof=self.store.source_proof(work_id);self.store.checked(work_id,proof)
            if self.store.facts_state(work_id,proof)!='CONFIRMED':errors.append('作品事實尚未人工確認或已過期，不能作修復正解')
        except (ValueError,OSError) as error:errors.append(str(error))
        return dict(work_id=work_id,source_id=work['source_id'],pins=self.store.pins(work_id),
                    facts_revision=facts['revision'],facts_digest=digest(facts),
                    human_truth_current=not errors,errors=errors)

    def plan_quality_issue(self,protocol_id,side,row,work_id=None):
        from .quality_diagnostics import QualityDiagnostics
        from .quality_protocol import QualityProtocols
        if row.get('ordinal')=='SOURCE_OVERVIEW':raise ValueError('零錯誤來源總覽不是失敗案例；人工新疑義請走原稿核對入口')
        detail=QualityDiagnostics(self.library).detail(protocol_id,side,row,work_id)
        protocol=QualityProtocols(self.library).get(protocol_id)
        selected=detail['selected_work_id']
        state=self.source_state(selected) if selected else None
        gold_refs=[dict(id=g['id'],revision=g['revision'],digest=digest(g)) for g in detail['golds']]
        domain=row['domain']
        truth_ready=bool(detail['golds']) and all(g['domain_truth'].get(domain)=='MANUALLY_VERIFIED' for g in detail['golds'])
        result=dict(origin='ACTUAL_QUALITY_CASE',protocol_id=protocol_id,side=side,
                    row=copy.deepcopy(row),work_id=selected,source_id=detail['source_id'],
                    source_hash=detail['source_hash'],source_state=state,
                    gold_refs=gold_refs,protocol_scope_digest=detail['protocol_scope_digest'],
                    pipeline_id=protocol['scope']['pipelines'][side]['id'],
                    pipeline_manifest_digest=detail['pipeline_manifest_digest'],
                    local_only=True,root_cause_proven=False,
                    domain_truth_ready=truth_ready,
                    automatic_repair_allowed=bool(state and state['human_truth_current'] and truth_ready),
                    scope='EXACT_EXISTING_SOURCE_AND_CASE_NOT_ALL_CUSTOMER_OR_TEMPLATE_DATA')
        result['digest']=digest(result);return result

    def create_quality_issue(self,plan,actor,reason,approved=False):
        if approved is not True:raise ValueError('需明確確認問題來源、案例及修復隔離邊界')
        text(actor,'修復問題登錄者',120);text(reason,'問題與人工核對依據',2000)
        if len(json.dumps(plan,ensure_ascii=False).encode())>1024*1024:raise ValueError('單案例修復metadata超過1MiB，請縮小具名範圍')
        with self.store.transaction():
            fresh=self.plan_quality_issue(plan['protocol_id'],plan['side'],plan['row'],plan['work_id'])
            if fresh!=plan:raise ValueError('案例／人工真值／來源版本已改變，需重新預覽')
            return self.store._write('QUALITY_REPAIR_ISSUE',new_id(),dict(
                evidence=fresh,actor=actor,reason=reason,at=time.time(),
                state='AWAITING_ROOT_REVIEW' if fresh['automatic_repair_allowed'] else 'MANUAL_SOURCE_OR_TRUTH_REVIEW_REQUIRED',
                root_cause_proven=False,formal_versions_changed=False),0,'quality_repair_issue_registered_no_formal_mutation')

    def plan_source_issue(self,work_id,origin,origin_id,description):
        if origin not in ('SOURCE_FACTS','EXCEPTION','CROSS_BATCH_RECHECK'):raise ValueError('不支援的既有修復入口')
        text(description,'來源問題與可核對現象',2000)
        if origin=='CROSS_BATCH_RECHECK':
            record=self.store.get('QUALITY_MAJOR_RECHECK',origin_id)
            quarantine=self.store.get('QUALITY_WORK_QUARANTINE',digest([origin_id,work_id]))
            if not record or not quarantine or quarantine['case_id']!=origin_id or quarantine['work_id']!=work_id:raise ValueError('作品不在既有持久重審影響清單')
            reference=dict(kind='QUALITY_MAJOR_RECHECK',id=record['id'],digest=digest(record),quarantine=dict(id=quarantine['id'],revision=quarantine['revision'],digest=digest(quarantine)))
        elif origin=='SOURCE_FACTS':
            if origin_id!=work_id:raise ValueError('原稿入口必須精確對應同一作品')
            reference=dict(kind='FACTS',id=work_id,digest=digest(self.store.facts(work_id)))
        else:
            record=self.store.get('AUTO_UNIT',origin_id)
            if not record or record['work_id']!=work_id or not record.get('issues') or record['state']=='EXCLUDED':raise ValueError('例外入口需實際同作品AUTO_UNIT未排除問題憑證，不能手填錯誤冒充')
            reference=dict(kind='AUTO_UNIT',id=record['id'],revision=record['revision'],digest=digest(record))
        state=self.source_state(work_id)
        result=dict(origin=origin,origin_reference=reference,work_id=work_id,
                    source_id=state['source_id'],source_state=state,description=description,
                    root_cause_proven=False,automatic_repair_allowed=False,
                    next_step='EXPLICIT_MANUAL_ROOT_AND_TRUTH_REVIEW_NOT_AUTOMATIC_REPAIR')
        result['digest']=digest(result);return result

    def create_source_issue(self,plan,actor,reason,approved=False):
        if approved is not True:raise ValueError('需核對原稿／重審入口與修復隔離範圍')
        text(actor,'問題登錄者',120);text(reason,'原稿核對依據',2000)
        ref=plan['origin_reference']
        with self.store.transaction():
            fresh=self.plan_source_issue(plan['work_id'],plan['origin'],ref['id'],plan['description'])
            if fresh!=plan:raise ValueError('原稿／事實／重審憑證改變，需重新預覽')
            return self.store._write('QUALITY_REPAIR_ISSUE',new_id(),dict(evidence=fresh,actor=actor,
                reason=reason,at=time.time(),state='AWAITING_ROOT_REVIEW',root_cause_proven=False,
                formal_versions_changed=False),0,'quality_source_issue_registered_not_formal_mutation')

    def plan_import_issue(self,batch_id,item_id,expected_revision,description):
        import json
        text(description,'匯入來源問題與可重現現象',2000)
        if not self.store.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='import_batches'").fetchone():raise ValueError('沒有既有匯入批次憑證')
        raw=self.store.db.execute('SELECT revision,payload FROM import_batches WHERE id=?',(batch_id,)).fetchone()
        if not raw:raise ValueError('實際匯入批次不存在')
        batch=json.loads(raw[1])
        if raw[0]!=expected_revision or batch['revision']!=expected_revision:raise ValueError('匯入批次版次改變，需重新讀取例外')
        item=next((row for row in batch['items'] if row['id']==item_id),None)
        if not item or item['status'] not in ('FAILED','INTERRUPTED'):raise ValueError('需明列實際失敗／中斷項；已排除或正常項不能冒充失敗')
        result=dict(origin='IMPORT_EXCEPTION',origin_reference=dict(kind='IMPORT_BATCH_ITEM',id=batch_id,revision=expected_revision,item_id=item_id,item_digest=digest(item),batch_digest=digest(batch)),
                    work_id=None,source_id=item.get('source_id') or (item.get('reuse_source') or {}).get('id'),
                    source_path=item['path'],source_hash=item.get('expected_hash'),source_page=item['page'],
                    actual_error=dict(status=item['status'],type=item.get('error_type'),reason=item.get('error') or item.get('reason')),
                    description=description,root_cause_proven=False,automatic_repair_allowed=False,
                    next_step='USE_EXISTING_IMPORT_RETRY_AND_MANUAL_SOURCE_TRUTH_NOT_TRAINING')
        result['digest']=digest(result);return result

    def create_import_issue(self,plan,actor,reason,approved=False):
        if approved is not True:raise ValueError('需明確核對實際匯入例外；沒有作品時不建立訓練候選')
        text(actor,'匯入問題登錄者',120);text(reason,'原始匯入錯誤核對依據',2000);ref=plan['origin_reference']
        with self.store.transaction():
            if self.plan_import_issue(ref['id'],ref['item_id'],ref['revision'],plan['description'])!=plan:raise ValueError('匯入例外／來源範圍已改變')
            return self.store._write('QUALITY_REPAIR_ISSUE',new_id(),dict(evidence=plan,actor=actor,reason=reason,at=time.time(),state='MANUAL_SOURCE_RECOVERY_REQUIRED',root_cause_proven=False,formal_versions_changed=False),0,'quality_actual_import_issue_registered_no_training')

    def current_issue(self,identity):
        issue=self.store.get('QUALITY_REPAIR_ISSUE',identity)
        if not issue:raise ValueError('修復問題不存在')
        return issue

    def impact_plan(self,identity,component='SOURCE',rule_id=None):
        from .quality_rechecks import QualityRechecks
        issue=self.current_issue(identity);pipeline_id=issue['evidence'].get('pipeline_id')
        service=QualityRechecks(self.library)
        if not issue['evidence'].get('work_id'):raise ValueError('此匯入例外尚無已核對作品；已知批次保留，其他依賴未知，請先由既有匯入重試恢復原稿')
        if component=='SOURCE':dependencies=service.source_dependencies(issue['evidence']['work_id'])
        else:
            if not pipeline_id:raise ValueError('尚無可核對的實際版本；先從原稿／模型／規則依賴確認版本，不把未知說成已掃描')
            dependencies=service.dependencies(pipeline_id,component,rule_id)
        result=dict(issue_id=identity,issue_revision=issue['revision'],issue_digest=digest(issue),
                    dependencies=dependencies,root_cause_proven=False,
                    automatic_quarantine=False,automatic_training=False,
                    next_step='REVIEW_EXACT_POTENTIAL_UNKNOWN_IMPACT_AND_EXPLICIT_REPAIR_SCOPE')
        result['digest']=digest(result);return result

    def root_plan(self,identity,layer,hypothesis,evidence,original_reviewed=False,truth_reviewed=False):
        issue=self.current_issue(identity)
        if layer not in ROOT_LAYERS:raise ValueError('需選擇實際問題層，不能將AI猜測當根因')
        text(hypothesis,'根因候選及可重現發生條件',2000);text(evidence,'人工核對與負面案例依據',4000)
        state=self.source_state(issue['evidence']['work_id']) if issue['evidence'].get('work_id') else None
        blockers=[]
        if original_reviewed is not True or truth_reviewed is not True:blockers.append('尚未明確核對原稿及人工正確答案')
        if not state or not state['human_truth_current']:blockers.append('來源／人工真值不可核對或已過期')
        from .quality_repair_truth import checked as checked_truth
        truth=None
        try:truth=checked_truth(self,identity)
        except (ValueError,KeyError,OSError) as error:blockers.append(str(error))
        if issue['evidence']['origin']=='ACTUAL_QUALITY_CASE' and not truth and not issue['evidence']['domain_truth_ready']:blockers.append('此錯誤領域仍無明確人工黃金答案，停止自動修復')
        if issue['evidence']['origin']=='ACTUAL_QUALITY_CASE':
            from .quality_gold import QualityGold
            for reference in truth['plan']['gold_refs'] if truth else issue['evidence']['gold_refs']:
                current=self.store.get('QUALITY_GOLD',reference['id'])
                if not current or digest(current)!=reference['digest'] or not QualityGold(self.library).validity(reference['id'])['valid']:
                    blockers.append('原案例Gold已失效；需明確建立新的人工真值版本，不自動沿用舊答案')
        if layer in ('SOURCE_INCOMPLETE','DISPUTED_GOLD'):blockers.append('來源不完整或真值有爭議，停止自動修復並走人工修訂')
        result=dict(issue_id=identity,issue_revision=issue['revision'],issue_digest=digest(issue),
                    layer=layer,hypothesis=hypothesis,evidence=evidence,source_state=state,truth_review_digest=digest(truth) if truth else None,
                    original_reviewed=original_reviewed is True,truth_reviewed=truth_reviewed is True,
                    blockers=blockers,can_prepare_candidate=not blockers,root_cause_proven=False,
                    next_step='REPRODUCIBLE_ROOT_REGRESSION_THEN_UNAFFECTED_CONTROLS_THEN_FRESH_HOLDOUT')
        result['digest']=digest(result);return result

    def confirm_root(self,plan,actor,approved=False):
        if approved is not True:raise ValueError('需明確確認根因候選與證據，不能自動認定已證實')
        text(actor,'根因核對者',120)
        with self.store.transaction():
            fresh=self.root_plan(plan['issue_id'],plan['layer'],plan['hypothesis'],plan['evidence'],plan['original_reviewed'],plan['truth_reviewed'])
            if fresh!=plan:raise ValueError('根因候選／來源證據已變更')
            return self.store._write('QUALITY_REPAIR_ROOT_REVIEW',new_id(),dict(plan=fresh,actor=actor,
                at=time.time(),state='CANDIDATE_PREPARATION_ALLOWED' if not fresh['blockers'] else 'MANUAL_REVIEW_REQUIRED',
                root_cause_proven=False,formal_versions_changed=False),0,'quality_repair_root_hypothesis_reviewed_not_proven')

    def page(self,offset=0,query=''):
        if type(offset) is not int or offset<0 or not isinstance(query,str) or len(query)>500:raise ValueError('問題清單需50筆分頁與有界搜尋')
        base="kind='QUALITY_REPAIR_ISSUE'";args=[]
        for token in query.casefold().split():
            base+=" AND instr(training_casefold(id||' '||payload),?)>0";args.append(token)
        total=self.store.db.execute('SELECT count(*) FROM training_records WHERE '+base,args).fetchone()[0]
        rows=[dict(id=r[0],revision=r[1],state=r[2],source_id=r[3],work_id=r[4],reason=r[5]) for r in self.store.db.execute(
            "SELECT id,revision,json_extract(payload,'$.state'),json_extract(payload,'$.evidence.source_id'),json_extract(payload,'$.evidence.work_id'),json_extract(payload,'$.reason') FROM training_records WHERE "+base+' ORDER BY id LIMIT 50 OFFSET ?',(*args,offset))]
        return dict(rows=rows,total=total,offset=offset,limit=50,private_local_only=True)

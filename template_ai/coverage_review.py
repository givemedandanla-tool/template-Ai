"""Explicit, pinned source-boundary and per-work layer dispositions."""
import copy
import time
from .coverage_evidence import LAYERS, work_context, low_risk_rule_evidence
from .training_store import digest, text
from .source_links import verify_source, check_verified, VerifiedSource

REVIEW = 'COVERAGE_REVIEW'
SEGMENTATION = 'COVERAGE_SEGMENTATION'
EXCLUSION = 'COVERAGE_EXCLUSION'


class CoverageReviewMixin:
    def exclusion_dependencies(self,member):
        return [dict(work_id=work['id'],context_digest=work_context(self,work['id'])['context_digest']) for pin in member['frozen']['source_pins'] for work in pin['works']]
    def member(self, identity):
        member = self.store.get('COVERAGE_MEMBER', identity)
        if not member: raise ValueError('批次成員不存在')
        return member

    def assert_open(self, member):
        batch = self.batch(member['batch_id'])
        if batch.get('closure_receipt') or batch['state'] not in ('BOUNDARY_FROZEN', 'OPEN'):
            raise ValueError('批次已有結案／過期，需明確重開並建立新版本')
        return batch

    def current_member_proofs(self, member):
        frozen = member['frozen']
        if len(frozen['expected_hashes'])!=1 or not frozen['source_pins']:
            raise ValueError('來源未解析或版本衝突，不可審核結案')
        proofs = {}
        for pin in frozen['source_pins']:
            if self.source_pin(pin['source_id'])!=pin: raise ValueError('來源／作品集合已變更，需新批次版本')
            key = (pin['current_path'], pin['source_hash'])
            if key not in proofs: proofs[key] = verify_source(*key)
        return [dict(path=p.path, hash=p.hash, stat=list(p.stat)) for p in proofs.values()]

    def recheck_member_proofs(self, member, proofs):
        for pin in member['frozen']['source_pins']:
            if self.source_pin(pin['source_id'])!=pin: raise ValueError('來源／作品依賴已變更')
        expected = {(str(__import__('pathlib').Path(pin['current_path']).resolve()), pin['source_hash']) for pin in member['frozen']['source_pins']}
        if {(p['path'], p['hash']) for p in proofs}!=expected: raise ValueError('來源憑證不完整')
        for proof in proofs: check_verified(VerifiedSource(proof['path'], proof['hash'], tuple(proof['stat'])), proof['hash'])

    def segmentation_plan(self, member_id, actual_work_ids, reason):
        member = self.member(member_id); batch = self.assert_open(member); text(reason, '切分證據與理由', 2000)
        frozen = member['frozen']; pins = frozen['source_pins']
        expected = sorted(work['id'] for pin in pins for work in pin['works'])
        if not isinstance(actual_work_ids, list) or sorted(actual_work_ids)!=expected or not expected or len(set(expected))!=len(expected):
            raise ValueError('需明列來源中全部真實作品ID；空集合／畫板數不可當完整切分')
        page_counts = {pin['page_count'] for pin in pins}
        if len(page_counts)!=1 or next(iter(page_counts)) is None: raise ValueError('原稿總頁數未知，不能聲稱全檔已切分')
        page_count = next(iter(page_counts))
        if type(page_count) is not int or page_count<1 or len(pins)!=page_count or {pin['page'] for pin in pins}!=set(range(1,page_count+1)) or any(not pin['works'] for pin in pins):
            raise ValueError('缺少原稿頁面或尚未切分頁；保持待審')
        from .model import Rect
        for pin in pins:
            boxes=[]
            for work in pin['works']:
                box=Rect(**self.library.artwork(work['id'])['payload']['crop'])
                if any(box.intersects(previous) for previous in boxes):raise ValueError('同頁作品切分框重複／互相跨界；先到畫布修正，不能以作品紀錄數冒充真實作品數')
                boxes.append(box)
        plan = dict(member_id=member_id, member_revision=member['revision'], batch_id=batch['id'], batch_revision=batch['revision'], member_scope_digest=frozen['member_scope_digest'], work_ids=expected, actual_work_count=len(expected), page_count=page_count, reason=reason, source_proofs=self.current_member_proofs(member), prior_revision=(self.store.get(SEGMENTATION,member_id) or {}).get('revision',0))
        plan['plan_digest'] = digest(plan); return plan

    def confirm_segmentation(self, plan, actor, approved=False):
        self.validate_plan(plan, actor, approved)
        with self.store.transaction():
            member = self.member(plan['member_id']); batch = self.assert_open(member)
            if member['revision']!=plan['member_revision'] or batch['revision']!=plan['batch_revision']: raise ValueError('切分審核預覽已過期')
            self.recheck_member_proofs(member, plan['source_proofs'])
            record = dict(member_id=member['id'], batch_id=batch['id'], member_scope_digest=plan['member_scope_digest'], work_ids=plan['work_ids'], actual_work_count=plan['actual_work_count'], page_count=plan['page_count'], actor=actor, reason=plan['reason'], at=time.time(), source_proofs=plan['source_proofs'], state='MANUALLY_CONFIRMED_FULL_SOURCE_WORK_BOUNDARIES')
            return self.store._write(SEGMENTATION, member['id'], record, plan['prior_revision'], 'coverage_source_segmentation_individually_confirmed')

    def validate_plan(self, plan, actor, approved):
        if approved is not True: raise ValueError('需人工核對確切影響範圍並明確確認')
        text(actor, '審核者', 120)
        if not isinstance(plan, dict): raise ValueError('缺少審核預覽')
        preview = copy.deepcopy(plan); expected = preview.pop('plan_digest', None)
        if expected!=digest(preview): raise ValueError('審核預覽已被修改')

    def layer_plan(self, member_id, work_id, layer, decision, reason, evidence):
        member = self.member(member_id); batch = self.assert_open(member)
        if work_id not in {w['id'] for pin in member['frozen']['source_pins'] for w in pin['works']}: raise ValueError('作品不在此檔案的固定範圍')
        if layer not in LAYERS or decision not in ('CONFIRMED', 'VERIFIED_ABSENT', 'NO_CANDIDATE_RETAINED'): raise ValueError('審核層次／決定不支援')
        if decision=='NO_CANDIDATE_RETAINED' and layer!='styles': raise ValueError('只有版型層可明示本次未形成版型，不可略過其他審核')
        text(reason, '審核理由', 2000); text(evidence, '來源定位／證據說明', 2000)
        context = work_context(self,work_id)
        if context['quality_blockers']:raise ValueError('既有標記品質檢查仍有阻擋，先修正重複框／歸屬／越界等來源問題')
        if layer=='customer' and context['unresolved_customer_candidates']:raise ValueError('既有客戶來源候選仍待處置／提交，不能以覆蓋確認繞過身分審查')
        if layer=='fields' and (context['unconfirmed_observation_ids'] or context['unobserved_slot_ids'] or context['unresolved_observation_ids'] or context['observation_count'] and context['facts_state']!='CONFIRMED'):
            raise ValueError('仍有未確認／過期的來源觀察；先到既有來源事實工具逐項審核')
        if decision=='VERIFIED_ABSENT':
            count = {'people':len(context['person_root_candidates']), 'companies':len(context['company_candidates']), 'whole_logo':context['whole_logo_candidates'], 'fields':context['observation_count'], 'customer':context['association_count'], 'styles':context['style_version_count']}.get(layer,0)
            if count: raise ValueError('仍存在此層候選／關聯，不能宣稱不存在')
        identity = digest([member_id,work_id,layer]); previous = self.store.get(REVIEW,identity)
        plan = dict(member_id=member_id,member_revision=member['revision'],batch_id=batch['id'],batch_revision=batch['revision'],work_id=work_id,layer=layer,decision=decision,reason=reason,evidence=evidence,context=context,context_digest=context['context_digest'],review_id=identity,prior_revision=previous['revision'] if previous else 0,source_proofs=self.current_member_proofs(member),impact=dict(only_this_work_and_layer=True,does_not_publish_rules_templates_or_output=True,does_not_assign_customer=True))
        plan['plan_digest']=digest(plan); return plan

    def confirm_layer(self, plan, actor, approved=False):
        self.validate_plan(plan,actor,approved)
        with self.store.transaction():
            member = self.member(plan['member_id']); batch = self.assert_open(member)
            if member['revision']!=plan['member_revision'] or batch['revision']!=plan['batch_revision'] or work_context(self,plan['work_id'])['context_digest']!=plan['context_digest']: raise ValueError('審核所依來源／規則／事實／歸屬／模板版本已改變')
            self.recheck_member_proofs(member,plan['source_proofs'])
            record = {key:copy.deepcopy(plan[key]) for key in ('member_id','batch_id','work_id','layer','decision','reason','evidence','context_digest','source_proofs','impact')}
            record.update(actor=actor,at=time.time(),state='MANUALLY_REVIEWED_EXACT_LAYER')
            return self.store._write(REVIEW,plan['review_id'],record,plan['prior_revision'],'coverage_high_risk_layer_individually_reviewed')

    def exclusion_plan(self, member_id, reason, evidence):
        member = self.member(member_id); batch = self.assert_open(member)
        text(reason,'排除理由',2000);text(evidence,'排除來源證據',2000)
        proofs=self.current_member_proofs(member)
        segmentation=self.store.get(SEGMENTATION,member_id)
        if not segmentation or segmentation['member_scope_digest']!=member['frozen']['member_scope_digest']: raise ValueError('未讀取／未解析／未完整切分來源不可用排除隱藏；先核對全檔真實作品')
        for pin in member['frozen']['source_pins']:
            for work in pin['works']:
                context=work_context(self,work['id'])
                if context['quality_blockers'] or context['unresolved_customer_candidates'] or any(unit['state']=='FAILED' for unit in context['analysis_states']):raise ValueError('未解分析／標記／客戶歸屬阻擋不可藉排除隱藏，先處理例外')
        plan = dict(member_id=member_id,member_revision=member['revision'],batch_id=batch['id'],batch_revision=batch['revision'],member_scope_digest=member['frozen']['member_scope_digest'],source_proofs=proofs,work_contexts=self.exclusion_dependencies(member),segmentation_revision=segmentation['revision'],reason=reason,evidence=evidence,prior_revision=(self.store.get(EXCLUSION,member_id) or {}).get('revision',0),impact=dict(file_count=1,recorded_work_count=member['frozen']['recorded_work_count'],counts_as_successful_learning=False,counts_as_approved_style=False,whole_directory_claim=False))
        plan['plan_digest']=digest(plan);return plan

    def confirm_exclusion(self, plan, actor, approved=False):
        self.validate_plan(plan,actor,approved)
        with self.store.transaction():
            member=self.member(plan['member_id']);batch=self.assert_open(member)
            if member['revision']!=plan['member_revision'] or batch['revision']!=plan['batch_revision']: raise ValueError('排除預覽已過期')
            if (self.store.get(SEGMENTATION,member['id']) or {}).get('revision')!=plan['segmentation_revision']: raise ValueError('全檔切分審核版本已變更')
            if self.exclusion_dependencies(member)!=plan['work_contexts']:raise ValueError('排除所依事實／歸屬／規則或版型版本已變更')
            self.recheck_member_proofs(member,plan['source_proofs'])
            record={key:copy.deepcopy(plan[key]) for key in ('member_id','batch_id','member_scope_digest','reason','evidence','source_proofs','work_contexts','impact')};record.update(actor=actor,at=time.time(),state='MANUALLY_APPROVED_SOURCE_EXCLUSION')
            return self.store._write(EXCLUSION,member['id'],record,plan['prior_revision'],'coverage_source_explicitly_excluded_not_learned')

    def member_evidence(self, member_id, verify_bytes=True):
        member=self.member(member_id);frozen=member['frozen'];blockers=[]
        proofs=[]
        try:
            if verify_bytes: proofs=self.current_member_proofs(member)
            else:
                for pin in frozen['source_pins']:
                    if self.source_pin(pin['source_id'])!=pin: raise ValueError('來源／作品已變更')
        except (OSError,ValueError) as error:blockers.append(dict(code='SOURCE_UNRESOLVED',reason=str(error)))
        exclusion=self.store.get(EXCLUSION,member_id)
        excluded=bool(exclusion and exclusion['member_scope_digest']==frozen['member_scope_digest'] and exclusion.get('work_contexts')==self.exclusion_dependencies(member) and not blockers)
        segmentation=self.store.get(SEGMENTATION,member_id)
        if not excluded and (not segmentation or segmentation['member_scope_digest']!=frozen['member_scope_digest']):blockers.append(dict(code='FULL_SOURCE_SEGMENTATION_NOT_REVIEWED',reason='未核對所有頁面中全部真實作品，畫板數不是作品數'))
        works=[];review_pins=[];layer_counts={layer:dict(required=0,current_reviewed=0) for layer in LAYERS}
        for pin in frozen['source_pins']:
            for work in pin['works']:
                context=work_context(self,work['id']);layers={}
                if not excluded:
                    if context['unresolved_customer_candidates']:blockers.append(dict(code='CUSTOMER_IDENTITY_UNRESOLVED',work_id=work['id'],reason='既有客戶來源候選待處置／提交，先到客戶來源審查'))
                    for issue in context['quality_blockers']:blockers.append(dict(code=issue['code'],work_id=work['id'],reason=issue['reason']))
                    for unit in context['analysis_states']:
                        if unit['state']=='FAILED':blockers.append(dict(code='UNRESOLVED_ANALYSIS_FAILURE',work_id=work['id'],reason='分析失敗尚未處理，先到例外中心核對原錯誤與修復'))
                for layer in LAYERS:
                    review=self.store.get(REVIEW,digest([member_id,work['id'],layer]));valid=bool(review and review['context_digest']==context['context_digest'])
                    layers[layer]=dict(state='APPROVED_EXCLUSION' if excluded else 'REVIEWED_CURRENT' if valid else 'STALE_REVIEW' if review else 'WAITING_HUMAN',decision=review['decision'] if review else None,review_id=review['id'] if review else None,revision=review['revision'] if review else 0)
                    layer_counts[layer]['required']+=1;layer_counts[layer]['current_reviewed']+=int(valid and not excluded)
                    if review:review_pins.append([review['id'],review['revision'],digest(review)])
                    if not valid and not excluded:blockers.append(dict(code='REQUIRED_LAYER_UNREVIEWED',work_id=work['id'],layer=layer,reason=layers[layer]['state']))
                decisions=self.store.noise_decisions(work['id'])
                conflicts=[row['observation_id'] for row in decisions if row['state'] in ('REVIEW_CONFLICT','REVIEW_RULE_STALE','REVIEW_BUDGET')]
                if conflicts and not excluded:blockers.append(dict(code='RULE_CONFLICT_OR_STALE_PROOF',work_id=work['id'],observation_ids=conflicts,reason='先在既有規則工具處理衝突／過期證據'))
                verification=[]
                for decision in decisions:
                    automatic=False
                    if decision['state']=='EXCLUDED_RULE' and not decision['protected'] and len(decision['rule_matches'])==1:
                        rule=decision['rule_matches'][0];receipt=self.store.get('COVERAGE_RULE_CHECK',digest([member_id,work['id'],decision['observation_id'],rule['id'],rule['revision']]))
                        automatic=bool(receipt and receipt['context_digest']==context['context_digest'] and receipt['decision_digest']==digest(decision))
                    verification.append(dict(observation_id=decision['observation_id'],state='AUTO_VERIFIED_BY_APPROVED_RULE' if automatic else 'RULE_ELIGIBLE_AWAITING_CONTROLLED_GROUP' if decision['state']=='EXCLUDED_RULE' and not decision['protected'] else 'MANUAL_FACT_CONFIRMED' if decision['state'] in ('KEPT_PROTECTED','INCLUDED','KEPT_LOCAL','KEPT_WHITELIST','EXCLUDED_LOCAL') else 'WAITING_HUMAN',rule_versions=decision['rule_matches'],protected=decision['protected']))
                works.append(dict(work_id=work['id'],source_id=pin['source_id'],context_digest=context['context_digest'],context=context,layers=layers,low_risk_rules=low_risk_rule_evidence(self,work['id']),observation_verification=verification,excluded=excluded))
        if not works and not excluded:blockers.append(dict(code='WORK_COUNT_UNKNOWN',reason='未解析／未切分來源留在檔案分母，作品總數未知'))
        denominator_verified=bool(segmentation and segmentation['member_scope_digest']==frozen['member_scope_digest'] and not any(b['code']=='SOURCE_UNRESOLVED' for b in blockers))
        rates={layer:dict(denominator_basis='CURRENT_VERIFIED_ACTUAL_WORKS' if denominator_verified else 'REGISTERED_WORK_RECORDS_ONLY_ALL_SOURCE_DENOMINATOR_UNKNOWN',denominator_verified=denominator_verified,review_rate=counts['current_reviewed']/counts['required'] if denominator_verified and counts['required'] else None,approved_excluded_work_count=counts['required'] if excluded else 0) for layer,counts in layer_counts.items()}
        return dict(member_id=member_id,member_revision=member['revision'],file_count=1,source_page_count=frozen['source_page_count'],recorded_work_count=frozen['recorded_work_count'],actual_work_count=segmentation['actual_work_count'] if denominator_verified else None,layer_counts=layer_counts,layer_rates=rates,works=works,source_proofs=proofs,segmentation_revision=segmentation['revision'] if segmentation else 0,exclusion_revision=exclusion['revision'] if exclusion else 0,review_pins=review_pins,disposition='APPROVED_EXCLUSION' if excluded else 'ALL_REQUIRED_LAYERS_REVIEWED' if not blockers else 'UNRESOLVED',closure_allowed=not blockers,blockers=blockers)

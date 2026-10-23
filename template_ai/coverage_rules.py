"""Controlled grouped verification of already-approved low-risk annotation rules."""
import time
from .coverage_evidence import work_context
from .training_store import digest

RULE_CHECK='COVERAGE_RULE_CHECK'


class CoverageRuleMixin:
    def group_rule_plan(self,member_ids,rule_id,rule_revision):
        if not isinstance(member_ids,list) or not 1<=len(member_ids)<=200 or len(set(member_ids))!=len(member_ids):raise ValueError('分組需明列1～200個不重複來源檔案')
        rule=self.store.get('RULE',rule_id)
        active,invalid=self.store.active_noise_rules()
        if not rule or rule['revision']!=rule_revision or rule_id not in {r['id'] for r in active}:raise ValueError('規則沒有目前有效正式核准版本；不可依信心值或候選規則核實')
        items=[];members=[];skipped=[];batch_id=None
        for member_id in member_ids:
            member=self.member(member_id);self.assert_open(member)
            if batch_id is None:batch_id=member['batch_id']
            if member['batch_id']!=batch_id:raise ValueError('不得跨批次混用適用範圍')
            eligible=[]
            for pin in member['frozen']['source_pins']:
                for work in pin['works']:
                    context=work_context(self,work['id'])
                    for decision in self.store.noise_decisions(work['id']):
                        matches=[r for r in decision['rule_matches'] if r['id']==rule_id and r['revision']==rule_revision]
                        if decision['state']=='EXCLUDED_RULE' and not decision['protected'] and len(decision['rule_matches'])==1 and matches:
                            identity=digest([member_id,work['id'],decision['observation_id'],rule_id,rule_revision]);previous=self.store.get(RULE_CHECK,identity)
                            eligible.append(dict(id=identity,member_id=member_id,work_id=work['id'],observation_id=decision['observation_id'],decision_digest=digest(decision),context_digest=context['context_digest'],prior_revision=previous['revision'] if previous else 0))
            if not eligible:skipped.append(dict(member_id=member_id,reason='無相同正式核准版本且不受保護的exact低風險註記；未當已驗證'));continue
            members.append(dict(member_id=member_id,member_revision=member['revision'],source_proofs=self.current_member_proofs(member)));items+=eligible
        if not items:raise ValueError('沒有可依同一有效核准規則處理的低風險項目；高風險仍逐項人工審核')
        plan=dict(batch_id=batch_id,batch_revision=self.batch(batch_id)['revision'],rule_id=rule_id,rule_revision=rule_revision,rule_digest=digest(rule),members=members,items=items,skipped_members=skipped,impact=dict(files=len(members),observations=len(items),high_risk_items=0,does_not_approve_people_company_customer_logo_or_style=True,not_human_confirmation=True))
        plan['plan_digest']=digest(plan);return plan

    def confirm_group_rule(self,plan,actor,approved=False):
        self.validate_plan(plan,actor,approved)
        with self.store.transaction():
            if self.batch(plan['batch_id'])['revision']!=plan['batch_revision'] or digest(self.store.get('RULE',plan['rule_id']))!=plan['rule_digest']:raise ValueError('批次／核准規則版本已改變')
            active,_=self.store.active_noise_rules()
            if plan['rule_id'] not in {r['id'] for r in active}:raise ValueError('核准規則的支持／反例證據已失效')
            for pin in plan['members']:
                member=self.member(pin['member_id']);self.assert_open(member)
                if member['revision']!=pin['member_revision']:raise ValueError('分組來源版次已改變')
                self.recheck_member_proofs(member,pin['source_proofs'])
            saved=[]
            for item in plan['items']:
                context=work_context(self,item['work_id']);decision=next((r for r in self.store.noise_decisions(item['work_id']) if r['observation_id']==item['observation_id']),None)
                if context['context_digest']!=item['context_digest'] or not decision or decision['state']!='EXCLUDED_RULE' or decision['protected'] or digest(decision)!=item['decision_digest']:raise ValueError('低風險適用條件／來源事實／歸屬已改變，未保存過期結果')
                record=dict(batch_id=plan['batch_id'],member_id=item['member_id'],work_id=item['work_id'],observation_id=item['observation_id'],rule_id=plan['rule_id'],rule_revision=plan['rule_revision'],decision_digest=item['decision_digest'],context_digest=item['context_digest'],state='AUTO_VERIFIED_BY_APPROVED_RULE',validation_origin='APPROVED_RULE_NOT_HUMAN_FACT_CONFIRMATION',batch_action_actor=actor,at=time.time(),high_risk_or_style_approval=False)
                saved.append(self.store._write(RULE_CHECK,item['id'],record,item['prior_revision'],'coverage_low_risk_verified_by_exact_approved_rule'))
            return dict(state='COMMITTED_APPROVED_RULE_VALIDATION',saved_count=len(saved),files=len(plan['members']),record_ids=[r['id'] for r in saved],human_confirmation_claim=False)

    def refresh_assessment(self,member_id):
        evidence=self.member_evidence(member_id);member=self.member(member_id)
        if not evidence['source_proofs']:return evidence
        methods=[]
        if any(v['current_reviewed'] for v in evidence['layer_counts'].values()):methods.append('人工分層確認')
        if any(o['state']=='AUTO_VERIFIED_BY_APPROVED_RULE' for work in evidence['works'] for o in work['observation_verification']):methods.append('核准規則自動驗證')
        if evidence['disposition']=='APPROVED_EXCLUSION':methods.append('明確核准排除')
        payload=dict(batch_id=member['batch_id'],member_id=member_id,checked_at=time.time(),directory=str(__import__('pathlib').Path(member['frozen']['original_path']).parent),works=[work['work_id'] for work in evidence['works']],risks=sorted({b['code'] for b in evidence['blockers']}),review_methods=methods or ['尚未完成核實'],blocker_reasons=[b['reason'] for b in evidence['blockers']],style_versions=[r for work in evidence['works'] for r in work['context']['context']['style_version_refs']],disposition=evidence['disposition'],snapshot_only_current_validity_requires_recheck=True)
        with self.store.transaction():
            current=self.member_evidence(member_id,verify_bytes=False)
            # Source stat and current metadata are checked before persisting this descriptive cache.
            from .coverage_closure import evidence_digest
            if evidence_digest(current)!=evidence_digest(evidence):raise ValueError('核對後依賴已變更，未保存過期統計')
            if evidence['source_proofs']:self.recheck_member_proofs(member,evidence['source_proofs'])
            prior=self.store.get('COVERAGE_ASSESSMENT',member_id)
            self.store._write('COVERAGE_ASSESSMENT',member_id,payload,prior['revision'] if prior else 0,'coverage_descriptive_assessment_saved_not_closure')
        return evidence

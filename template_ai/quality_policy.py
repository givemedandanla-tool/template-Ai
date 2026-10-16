"""Explicit user-reviewed statistical policy, with no guessed default thresholds."""
import copy
import math
import time
from .quality_gold import DOMAINS
from .quality_metrics import VERSION,wilson_interval
from .training_store import TrainingStore,digest,text
from .model import new_id

POLICY='QUALITY_POLICY'


class QualityPolicies:
    def __init__(self,library):self.store=TrainingStore.bind(library)

    def plan(self,name,thresholds,matching_iou,confidence,basis,reference,scope):
        text(name,'品質政策名稱',120);text(basis,'各類門檻及必要樣本量依據',2000);text(reference,'門檻研究／核准參考',2000)
        if scope not in ('SYNTHETIC_SELF_CHECK','AUTHORIZED_LOCAL_QUALITY_ACCEPTANCE'):raise ValueError('需明列合成自驗或已獲授權本機品質驗收範圍')
        if type(matching_iou) not in (int,float) or not math.isfinite(matching_iou) or not 0<matching_iou<=1:raise ValueError('需明確核准IoU配對口徑；沒有預設門檻')
        wilson_interval(0,1,confidence)
        required={'minimum_independent_groups','minimum_gold_objects','minimum_precision','minimum_recall','maximum_group_failure_rate'}
        if not isinstance(thresholds,dict) or set(thresholds)!=set(DOMAINS):raise ValueError('九個領域需各自完整門檻與樣本數；沒有一個總準確率取代')
        for domain,values in thresholds.items():
            if not isinstance(values,dict) or set(values)!=required:raise ValueError('需明列每層獨立群組數／gold數／precision／recall／群組失敗率')
            for key in ('minimum_independent_groups','minimum_gold_objects'):
                if type(values[key]) is not int or not 1<=values[key]<=1000000:raise ValueError('必要樣本數需明確正整數，不能靠空分母通過')
            for key in ('minimum_precision','minimum_recall','maximum_group_failure_rate'):
                if type(values[key]) not in (int,float) or not math.isfinite(values[key]) or not 0<=values[key]<=1:raise ValueError('各類率門檻需明確有限0～1數值')
        plan=dict(schema_version=1,name=name,thresholds=copy.deepcopy(thresholds),matching_iou=matching_iou,confidence=confidence,basis=basis,reference=reference,scope=scope,calculation_version=VERSION,critical_owner_logo_missing_work_errors_always_block=True,unknown_or_leaked_evidence_always_blocks=True,quality_policy_is_not_model_rule_publication=True,threshold_source='EXPLICIT_USER_REVIEWED_BASIS_NO_EMPIRICAL_DEFAULTS')
        plan['digest']=digest(plan);return plan

    def approve(self,plan,actor,approved=False):
        if approved is not True:raise ValueError('需明確核對門檻依據及適用範圍，不自動核准預設值')
        text(actor,'政策核准者',120);preview=copy.deepcopy(plan);expected=preview.pop('digest',None)
        if expected!=digest(preview):raise ValueError('政策預覽已被修改')
        current=self.plan(plan['name'],plan['thresholds'],plan['matching_iou'],plan['confidence'],plan['basis'],plan['reference'],plan['scope'])
        if current!=plan:raise ValueError('政策口徑已改變')
        with self.store.transaction():
            return self.store._write(POLICY,new_id(),dict(plan=copy.deepcopy(plan),actor=actor,approved_at=time.time(),state='APPROVED_EXACT_POLICY_VERSION',immutable=True),0,'quality_policy_explicitly_approved_not_model_publication')

    def status(self,policy_id):
        record=self.store.get(POLICY,policy_id) if policy_id else None
        if not record:return dict(state='UNCONFIGURED',valid=False,policy=None,reason='尚無明確核准的各類門檻／必要樣本量／依據，不能宣稱品質PASS')
        plan=copy.deepcopy(record['plan']);expected=plan.pop('digest',None)
        valid=not self.store.get('QUALITY_POLICY_WITHDRAWAL',policy_id) and record['state']=='APPROVED_EXACT_POLICY_VERSION' and expected==digest(plan) and plan['calculation_version']==VERSION
        return dict(state=record['state'] if valid else 'WITHDRAWN',valid=valid,policy=record,reason='政策核准不代表模型／驗收集／品質已通過')

    def withdraw(self,policy_id,expected_revision,actor,reason,approved=False):
        if approved is not True:raise ValueError('需明確撤回此政策版本')
        text(actor,'撤回者',120);text(reason,'撤回依據',2000)
        with self.store.transaction():
            policy=self.store.get(POLICY,policy_id)
            if not policy or policy['revision']!=expected_revision:raise ValueError('政策版本已變更／失聯')
            prior=self.store.get('QUALITY_POLICY_WITHDRAWAL',policy_id)
            return self.store._write('QUALITY_POLICY_WITHDRAWAL',policy_id,dict(policy_id=policy_id,actor=actor,reason=reason,at=time.time(),state='WITHDRAWN_NO_AUTOMATIC_SAFE_FALLBACK'),prior['revision'] if prior else 0,'quality_policy_withdrawn_old_policy_not_unconditionally_safe')

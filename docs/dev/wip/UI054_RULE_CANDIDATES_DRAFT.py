"""UNEXECUTED draft: independently approved repair rules stay outside ACTIVE.

Before integration, reuse approval_checks from the existing review_rules path,
extend exact frozen selection to this state, preserve TRAIN exposure history,
and implement separately gated runtime deployment. This file is not imported.
"""
import copy,time
from .training_store import digest,text
from .model import new_id
from .quality_groups import QualityGroups
from .quality_repairs import QualityRepairs
from .quality_repair_training import root_review

STATE='ISOLATED_APPROVED_REPAIR_CANDIDATE'


def approval_checks(plan,detail_reviewed):
    """Extract existing checks into one shared function when integrating."""
    if any(row['state'] not in ('PENDING','DEFERRED') for row in plan['rows']):raise ValueError('只核對尚未正式啟用的草稿版本')
    if any(row['risk']=='BLOCK' for row in plan['rows']):raise ValueError('支持／反例／影響證據不足，不能核准候選')
    if len(plan['rows'])>1 and not plan['batch_eligible']:raise ValueError('只有相同前提的LOW風險才可整組核對')
    if any(row['risk']=='HIGH' for row in plan['rows']) and (len(plan['rows'])!=1 or detail_reviewed is not True):raise ValueError('HIGH風險必須逐條詳閱原稿、支持與反例')


def approve(store,review_id,plan,actor,reason,approved=False,detail_reviewed=False):
    if approved is not True:raise ValueError('需明確核對修復規則候選；此操作不正式發布')
    text(actor,'候選規則核對者',120);text(reason,'獨立核對與適用邊界',2000)
    with store.transaction():
        review=root_review(QualityRepairs(store.library),review_id)
        current=store.rule_review_plan(plan['ids'])
        if current!=plan:raise ValueError('規則草稿／原稿支持／反例或影響清單改變，需重新預覽')
        approval_checks(current,detail_reviewed)
        results=[]
        for row in current['rows']:
            record=copy.deepcopy(row['rule']);refs=record['positive_examples']+record['counterexamples']
            if QualityGroups(store.library).role_conflicts([(ref['pins']['source_hash'],'TRAIN') for ref in refs]):raise ValueError('修復規則不能吸收HOLDOUT／VALIDATION或相關家族答案')
            for ref in refs:store.validate_ref(ref)
            candidate_id=new_id();origin=copy.deepcopy(record)
            origin.update(state='ISOLATED_IN_REPAIR',repair_candidate_id=candidate_id,root_review_id=review_id)
            locked=store._write('RULE',row['id'],origin,row['revision'],'repair_rule_draft_isolated_not_formally_activated')
            record.pop('id',None);record.pop('revision',None)
            record.update(state=STATE,immutable=True,root_review_id=review_id,root_review_digest=digest(review),
                origin_rule=dict(id=locked['id'],revision=locked['revision'],digest=digest(locked)),
                review=dict(actor=actor,reason=reason,decision='APPROVE',reviewed_revision=0,
                    plan_digest=current['digest'],risk=row['risk'],impact=row['matches'],timestamp=time.time(),
                    detail_reviewed=detail_reviewed is True,publication='ISOLATED_NOT_ACTIVE'),
                quality_pass=False,production_active=False)
            results.append(store._write('RULE',candidate_id,record,0,'repair_rule_candidate_independently_approved_not_published'))
        return results


def checked(store,identity,revision):
    record=store.get('RULE',identity)
    if not record or record['revision']!=revision or record['state']!=STATE or not record.get('immutable'):raise ValueError('隔離規則候選版本不存在或已改變')
    approval=record.get('review') or {}
    if approval.get('decision')!='APPROVE' or approval.get('reviewed_revision')!=revision-1 or approval.get('publication')!='ISOLATED_NOT_ACTIVE':raise ValueError('候選沒有可核對的獨立核准憑證')
    origin=record['origin_rule'];current=store.get('RULE',origin['id'])
    if not current or current['revision']!=origin['revision'] or digest(current)!=origin['digest'] or current['state']!='ISOLATED_IN_REPAIR':raise ValueError('原始草稿／修復隔離已變更，候選不能繼續發布')
    root_review(QualityRepairs(store.library),record['root_review_id'])
    for ref in record['positive_examples']+record['counterexamples']:store.validate_ref(ref)
    return record

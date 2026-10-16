"""Independently approved repair rules; explicit quality use, never default ACTIVE."""
import copy,time
from .training_store import digest,text
from .model import new_id
from .quality_groups import QualityGroups
from .quality_repairs import QualityRepairs
from .quality_repair_training import root_review

STATE='ISOLATED_APPROVED_REPAIR_CANDIDATE'


from .noise_review import approval_checks


def approve(store,review_id,plan,actor,reason,approved=False,detail_reviewed=False):
    if approved is not True:raise ValueError('需明確核對修復規則候選；此操作不正式發布')
    text(actor,'候選規則核對者',120);text(reason,'獨立核對與適用邊界',2000)
    with store.transaction():
        review=root_review(QualityRepairs(store.library),review_id)
        if review['plan']['layer']!='NOISE_RULE':raise ValueError('只有經核對的NOISE_RULE根因可準備規則候選')
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
    review=root_review(QualityRepairs(store.library),record['root_review_id'])
    if digest(review)!=record['root_review_digest'] or review['plan']['layer']!='NOISE_RULE':raise ValueError('規則根因憑證不一致')
    for ref in record['positive_examples']+record['counterexamples']:store.validate_ref(ref)
    return record

"""Locally reviewed production ranker certificates; no private data upload."""
from copy import deepcopy
import math

from .candidate_risk import engine_digest
from .model import new_id
from .training_store import digest, text


def rank_quality_errors(report,policy):
    for key in ('minimum_ndcg','minimum_improvement','minimum_ndcg_lower_bound'):
        value=policy.get(key)
        if type(value) not in (int,float) or not math.isfinite(value) or not -1<=value<=1:
            raise ValueError('Explicit finite ranking quality thresholds required')
    minimum=policy.get('minimum_independent_groups')
    if type(minimum) is not int or minimum<5:raise ValueError('Ranking qualification needs five or more independent heldout groups')
    errors=[]
    if report.get('origin')!='REAL_AUTHORIZED_CORPUS':errors.append('REAL_CORPUS_REVIEW_REQUIRED')
    if report.get('independent_groups',0)<minimum:errors.append('INSUFFICIENT_INDEPENDENT_GROUPS')
    if report.get('unknown_queries',1) or report.get('known_queries',0)!=report.get('denominator'):errors.append('INCOMPLETE_INDEPENDENT_GRADES')
    value=report.get('group_macro_ndcg_at_k');baseline=report.get('baseline_group_macro_ndcg_at_k')
    interval=report.get('ndcg_group_bootstrap_95')
    if value is None or baseline is None or value<policy['minimum_ndcg'] or value-baseline<policy['minimum_improvement']:
        errors.append('RANKING_QUALITY_BELOW_POLICY')
    if not interval or interval[0]<policy['minimum_ndcg_lower_bound']:errors.append('RANKING_UNCERTAINTY_BELOW_POLICY')
    return errors


class RankerQualification:
    def __init__(self,library):
        from .design_feedback import DesignFeedback
        from .design_jobs import DesignJobs
        self.library=library;self.feedback=DesignFeedback(library);self.store=self.feedback.store;self.jobs=DesignJobs(library)

    def plan(self,ranker_id,job_id,corpus_review_id,policy):
        from .design_rank_evaluation import RankingEvaluation
        text(policy.get('version'),'Ranker qualification policy version',128)
        text(policy.get('basis'),'Ranker qualification basis',2048)
        ranker=self.feedback.checked_ranker(ranker_id);job=self.jobs.current(job_id)
        if job['kind']!='EVALUATE_LAYOUTS' or job['phase']!='COMPLETE':raise ValueError('Complete actual ranking evaluation required')
        if job['plan'].get('ranker_ref')!=dict(id=ranker_id,weights_digest=ranker['weights_digest']):
            raise ValueError('Evaluation did not use this exact ranker')
        model,dataset=self.feedback.learning.checked_model(job['plan']['model_id'])
        review=self.store.get('DESIGN_CORPUS_REVIEW',corpus_review_id)
        if (not review or review.get('state')!='APPROVED' or review.get('job_id')!=job_id
                or review.get('manifest_digest')!=model['manifest_digest'] or review.get('weights_digest')!=model['weights_digest']
                or review.get('real_authorized') is not True or review.get('lineage_independence_reviewed') is not True
                or job['plan']['origin']!='REAL_AUTHORIZED_CORPUS'):
            raise ValueError('Actual local authorized corpus/lineage review missing;synthetic cannot qualify')
        rows=self.jobs.results(job_id)
        if not rows or any(row['role']!='HOLDOUT' for row in rows):raise ValueError('Ranker qualification uses sealed HOLDOUT only')
        if any(row['learned']['status']!='FEASIBLE' or not row['learned'].get('integrity') or row['learned']['integrity']['data_integrity']!=1 for row in rows):
            raise ValueError('Actual layout/data integrity failed')
        report=RankingEvaluation(self.library).report(job_id,policy.get('k',3))
        errors=rank_quality_errors(report,policy)
        if errors:raise ValueError('Ranker qualification failed: '+','.join(errors))
        plan=dict(ranker_id=ranker_id,weights_digest=ranker['weights_digest'],model_id=model['id'],
            model_weights_digest=model['weights_digest'],manifest_digest=model['manifest_digest'],job_id=job_id,
            corpus_review_id=corpus_review_id,corpus_review_digest=digest(review),report_digest=report['digest'],
            policy=deepcopy(policy),engine_digest=engine_digest(),scope='LOCAL_DIGITAL_RANKING_NOT_PHYSICAL_PRINT_QUALIFICATION')
        plan['digest']=digest(plan);return plan

    def approve(self,plan,actor,approved=False):
        if not approved:raise ValueError('Explicit local production ranker approval required')
        text(actor,'Ranker qualification reviewer',120)
        with self.store.transaction():
            fresh=self.plan(plan['ranker_id'],plan['job_id'],plan['corpus_review_id'],plan['policy'])
            if fresh!=plan:raise ValueError('Ranker qualification support changed')
            return self.store._write('DESIGN_RANK_QUALIFICATION',new_id(),dict(state='APPROVED',plan=deepcopy(plan),actor=actor),0,
                'local_production_ranker_qualified_no_private_upload')

    def checked(self,identity,ranker_id):
        certificate=self.store.get('DESIGN_RANK_QUALIFICATION',identity)
        if not certificate or certificate.get('state')!='APPROVED' or certificate['plan']['ranker_id']!=ranker_id:
            raise ValueError('Current production ranker certificate missing')
        plan=certificate['plan'];fresh=self.plan(ranker_id,plan['job_id'],plan['corpus_review_id'],plan['policy'])
        if fresh!=plan:raise ValueError('Production ranker certificate is stale')
        return certificate

"""Explicit real-source qualification; no synthetic PASS promotes production.

Thresholds are versioned reviewer policy, not invented universal print limits.
This certifies the measured core digital scope only, never physical prepress or
an untested device. Existing output/font/format checks remain mandatory.
"""
from copy import deepcopy
import math

from .training_store import TrainingStore,digest,text
from .design_jobs import DesignJobs
from .design_learning import CrossWorkLearning
from .candidate_risk import engine_digest
from .model import new_id


class DesignQualification:
    def __init__(self,library):
        self.library=library
        self.store=TrainingStore.bind(library) if library.db.in_transaction else TrainingStore(library)
        self.jobs=DesignJobs(library);self.learning=CrossWorkLearning(library)

    def review_corpus(self,job_id,actor,evidence,*,real_authorized,lineage_independence_reviewed,approved=False):
        if not approved or real_authorized is not True or lineage_independence_reviewed is not True:
            raise ValueError('Real authorized source and near-duplicate/lineage review must be explicit')
        text(actor,'Independent corpus reviewer',120);text(evidence,'Actual source review evidence',2048)
        job=self.jobs.current(job_id)
        if job['kind']!='EVALUATE_LAYOUTS' or job['plan']['origin']!='REAL_AUTHORIZED_CORPUS':
            raise ValueError('Authored/synthetic or unknown corpus cannot be promoted to real-source qualification')
        model,dataset=self.learning.checked_model(job['plan']['model_id'])
        with self.store.transaction():
            return self.store._write('DESIGN_CORPUS_REVIEW',new_id(),dict(job_id=job_id,actor=actor,evidence=evidence,
                manifest_digest=dataset['manifest_digest'],weights_digest=model['weights_digest'],
                real_authorized=True,lineage_independence_reviewed=True,state='APPROVED'),0,'actual_corpus_review_recorded')

    def plan(self,job_id,corpus_review_id,policy):
        job=self.jobs.current(job_id);review=self.store.get('DESIGN_CORPUS_REVIEW',corpus_review_id)
        if job['kind']!='EVALUATE_LAYOUTS' or job['phase']!='COMPLETE':raise ValueError('Complete actual layout evaluation required')
        model,dataset=self.learning.checked_model(job['plan']['model_id'])
        if (not review or review['state']!='APPROVED' or review['job_id']!=job_id
                or review['manifest_digest']!=dataset['manifest_digest'] or review['weights_digest']!=model['weights_digest']
                or job['plan']['origin']!='REAL_AUTHORIZED_CORPUS'):
            raise ValueError('Actual reviewed corpus/lineage proof missing or stale')
        text(policy.get('version'),'Qualification policy version',128);text(policy.get('basis'),'Qualification policy evidence',2048)
        minimum=policy.get('minimum_independent_groups')
        if type(minimum) is not int or minimum<5:raise ValueError('Qualification needs at least five independent heldout lineages')
        for key in ('minimum_feasible_rate','minimum_preference_win_or_tie_rate'):
            value=policy.get(key)
            if type(value) not in (int,float) or not math.isfinite(value) or not .5<=value<=1:
                raise ValueError('Explicit bounded feasibility and preference thresholds required')
        rows=self.jobs.results(job_id)
        if any(row['role']!='HOLDOUT' for row in rows):raise ValueError('Qualification uses sealed HOLDOUT,not tuning validation')
        if len({row['lineage_group'] for row in rows})<minimum:raise ValueError('Insufficient independent heldout support')
        if job['plan']['weights_digest']!=model['weights_digest'] or job['plan']['manifest_digest']!=model['manifest_digest']:
            raise ValueError('Evaluated model version differs')
        errors=[];feasible=sum(row['learned']['status']=='FEASIBLE' for row in rows)
        if any(row['learned']['status']=='HARD_ERROR' for row in rows):errors.append('HARD_LAYOUT_ERROR')
        if any(row['learned']['integrity'] and row['learned']['integrity']['data_integrity']!=1 for row in rows):errors.append('DATA_INTEGRITY')
        if feasible/len(rows)<policy['minimum_feasible_rate']:errors.append('FEASIBILITY_BELOW_REVIEWED_POLICY')
        reviews={}
        identifiers=self.store.db.execute("SELECT id FROM training_records WHERE kind='DESIGN_PREFERENCE_REVIEW' AND json_extract(payload,'$.job_id')=? ORDER BY id LIMIT 10001",(job_id,)).fetchall()
        if len(identifiers)>10000:raise ValueError('Preference review resource budget exceeded;not truncated')
        for (identity,) in identifiers:
            row=self.store.get('DESIGN_PREFERENCE_REVIEW',identity);reviews.setdefault(row['index'],[]).append(row)
        preference_refs=[];wins=0
        for index,result in enumerate(rows):
            item=self.store.get('DESIGN_JOB_ITEM',self.jobs.item_key(job_id,index))
            choices=reviews.get(index,[])
            if len(choices)!=1 or choices[0]['result_digest']!=item['result_digest']:
                errors.append('INDEPENDENT_PREFERENCE_MISSING_OR_CONFLICTING');continue
            selected=choices[0];preference_refs.append(dict(id=selected['id'],revision=selected['revision'],digest=digest(selected)))
            wins+=selected['winner'] in ('LEARNED','TIE')
        if wins/len(rows)<policy['minimum_preference_win_or_tie_rate']:errors.append('PREFERENCE_BELOW_REVIEWED_POLICY')
        # UNKNOWN alignment/identity is retained in training, but cannot silently
        # establish a fully qualified production style.
        for family in model['artifact']['profile_model']['families']:
            for data in family['data_requirement_profiles']:
                for sample in data['presentation_evidence']:
                    if sample['kind']=='logo':continue
                    if not sample['source_font_ref'] or sample['joint']['source_pt'] is None or sample['align']=='UNKNOWN':
                        errors.append('SOURCE_STYLE_OR_FONT_UNKNOWN')
        if errors:raise ValueError('Qualification remains blocked: '+','.join(sorted(set(errors))))
        result=dict(job_id=job_id,job_revision=job['revision'],job_plan_digest=job['plan_digest'],
            summary_digest=digest(job['summary']),item_result_digests=[digest(row) for row in rows],
            model_id=model['id'],weights_digest=model['weights_digest'],manifest_digest=dataset['manifest_digest'],
            corpus_review=dict(id=review['id'],revision=review['revision'],digest=digest(review)),
            preference_refs=preference_refs,policy=deepcopy(policy),engine_digest=engine_digest(),
            scope='MEASURED_CORE_DIGITAL_LAYOUT_ONLY;NOT_PHYSICAL_PREPRESS_OR_UNTESTED_DEVICES')
        result['digest']=digest(result);return result

    def approve(self,plan,actor,approved=False):
        if not approved:raise ValueError('Explicit scoped production qualification approval required')
        text(actor,'Qualification reviewer',120)
        with self.store.transaction():
            fresh=self.plan(plan['job_id'],plan['corpus_review']['id'],plan['policy'])
            if fresh!=plan:raise ValueError('Qualification evidence changed during review')
            certificate=self.store._write('DESIGN_QUALIFICATION',new_id(),dict(state='APPROVED',plan=deepcopy(plan),actor=actor),0,'core_digital_qualification_approved')
            model=self.store.get('DESIGN_MODEL',plan['model_id']);body={k:deepcopy(v) for k,v in model.items() if k not in ('id','revision')}
            body.update(formal_qualification='PASS',qualification_id=certificate['id'])
            self.store._write('DESIGN_MODEL',model['id'],body,model['revision'],'model_qualification_metadata_added_weights_unchanged')
            return certificate


def validate_certificate(library,model):
    store=TrainingStore.bind(library);certificate=store.get('DESIGN_QUALIFICATION',model.get('qualification_id','missing'))
    if not certificate or certificate['state']!='APPROVED':raise ValueError('Current model qualification missing or withdrawn')
    plan=certificate['plan']
    if (digest({k:v for k,v in plan.items() if k!='digest'})!=plan['digest'] or plan['model_id']!=model['id']
            or plan['weights_digest']!=model['weights_digest'] or plan['manifest_digest']!=model['manifest_digest']
            or plan['engine_digest']!=engine_digest()):raise ValueError('Qualification model/engine/scope proof changed')
    jobs=DesignJobs(library);job=jobs.current(plan['job_id'])
    if job['revision']!=plan['job_revision'] or digest(job['summary'])!=plan['summary_digest']:
        raise ValueError('Qualification evaluation changed')
    if [digest(row) for row in jobs.results(job['id'])]!=plan['item_result_digests']:raise ValueError('Qualification item evidence changed')
    for kind,refs in [('DESIGN_CORPUS_REVIEW',[plan['corpus_review']]),('DESIGN_PREFERENCE_REVIEW',plan['preference_refs'])]:
        for ref in refs:
            row=store.get(kind,ref['id'])
            if not row or row['revision']!=ref['revision'] or digest(row)!=ref['digest']:raise ValueError('Qualification supporting review changed')
    return certificate

"""Local empirical suitable regions, calibrated on independent VALIDATION groups.

Regions are advice backed by observed joint demands, never a global capacity
theorem or permission to bypass actual shaping/layout/output checks. HOLDOUT is
reserved for final evaluation and cannot be used to fit these boundaries.
"""
from collections import defaultdict
from copy import deepcopy
import math

from scipy.stats import beta

from .training_store import digest, text

VERSION='conditional-capacity-calibration-2'


def fit_capacity(records,policy):
    if not isinstance(records,list) or not records or len(records)>10000:
        raise ValueError('Explicit bounded capacity calibration cases required')
    minimum=policy.get('minimum_independent_groups');probability=policy.get('minimum_success_lower_bound')
    alpha=policy.get('alpha');bins=policy.get('bin_widths')
    distance=policy.get('maximum_support_distance',.25)
    if (type(minimum) is not int or minimum<5 or type(alpha) not in (int,float) or not 0<alpha<.5
            or type(probability) not in (int,float) or not 0<probability<1
            or not isinstance(bins,list) or not bins or len(bins)>128
            or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in bins)):
        raise ValueError('Capacity policy needs explicit group,confidence and joint-demand bins')
    if type(distance) not in (int,float) or not math.isfinite(distance) or not 0<distance<=2:
        raise ValueError('Invalid calibrated joint-support distance')
    text(policy.get('version'),'Capacity policy version',128)
    groups=defaultdict(list);seen=set();role_by_group={}
    for record in records:
        if record.get('role')!='VALIDATION':raise ValueError('Capacity fitting uses VALIDATION,never TRAIN or sealed HOLDOUT')
        key=record.get('id');lineage=record.get('lineage_group')
        if not isinstance(key,str) or not key or key in seen or not isinstance(lineage,str) or not lineage:
            raise ValueError('Known independent lineage and unique calibration case IDs required')
        seen.add(key)
        context=record.get('context');demand=record.get('demand')
        if (not isinstance(context,dict) or not context.get('family_id') or not context.get('font_signature')
                or type(context.get('field_count')) is not int or context['field_count']<1
                or not isinstance(demand,list) or len(demand)!=len(bins)
                or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in demand)
                or type(record.get('layout_pass')) is not bool or type(record.get('qualified_style')) is not bool
                or not record.get('evidence_refs')):
            raise ValueError('Capacity needs actual joint demands,layout checks and independently reviewed style')
        bucket=tuple(math.floor(v/width) for v,width in zip(demand,bins))
        groups[(digest(context),bucket)].append(record)
    cells=[]
    for (context_id,bucket),items in sorted(groups.items()):
        by_group=defaultdict(list)
        for record in items:by_group[record['lineage_group']].append(record)
        passed=sum(all(r['layout_pass'] and r['qualified_style'] for r in rows) for rows in by_group.values())
        total=len(by_group);lower=float(beta.ppf(alpha,passed,total-passed+1)) if passed else 0.
        eligible=total>=minimum and lower>=probability
        positive=[r for r in items if r['layout_pass'] and r['qualified_style']]
        negative=[r for r in items if not (r['layout_pass'] and r['qualified_style'])]
        cells.append(dict(context=deepcopy(items[0]['context']),context_digest=context_id,bucket=list(bucket),
            observed_lower=[min(r['demand'][i] for r in positive) for i in range(len(bins))] if positive else [],
            observed_upper=[max(r['demand'][i] for r in positive) for i in range(len(bins))] if positive else [],
            joint_support=[list(r['demand']) for r in positive],
            negative_joint_support=[list(r['demand']) for r in negative],
            positive_case_ids=sorted(r['id'] for r in positive),negative_case_ids=sorted(r['id'] for r in negative),
            independent_groups=total,successful_groups=passed,
            one_sided_success_lower_bound=lower,status='VALIDATED_EMPIRICAL_REGION' if eligible else 'INSUFFICIENT_OR_FAILED',
            source_case_ids=sorted(r['id'] for r in items),source_refs=sorted({v for r in items for v in r['evidence_refs']})))
    artifact=dict(version=VERSION,policy=deepcopy(policy),cells=cells,source_digest=digest(records),
        maximum_validated_field_count=max((c['context']['field_count'] for c in cells if c['status']=='VALIDATED_EMPIRICAL_REGION'),default=None),
        maximum_validated_field_count_scope='ALL_CONTEXTS_SUMMARY_NOT_QUERY_LIMIT',
        hard_global_capacity=None,scope='JOINT_EMPIRICAL_ADVICE;ACTUAL_LAYOUT_REQUIRED;NO_UNOBSERVED_CAPACITY_CLAIM')
    artifact['digest']=digest(artifact);return artifact


def capacity_advice(artifact,context,demand):
    if artifact.get('version')!=VERSION or digest({k:v for k,v in artifact.items() if k!='digest'})!=artifact.get('digest'):
        raise ValueError('Capacity model changed or incompatible')
    bins=artifact['policy']['bin_widths']
    if not isinstance(demand,list) or len(demand)!=len(bins) or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in demand):
        raise ValueError('Invalid actual joint demand')
    context_id=digest(context);bucket=[math.floor(v/w) for v,w in zip(demand,bins)]
    for cell in artifact['cells']:
        if cell['context_digest']!=context_id or cell['bucket']!=bucket or cell['status']!='VALIDATED_EMPIRICAL_REGION':continue
        # Confidence across a bucket does not turn an explicit failed/unqualified
        # point into positive evidence, even if other records at that point pass.
        if any(all(math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-12) for a,b in zip(demand,row))
               for row in cell['negative_joint_support']):continue
        if not all(a<=v<=b for a,v,b in zip(cell['observed_lower'],demand,cell['observed_upper'])):continue
        distance=min(math.sqrt(sum(((a-b)/w)**2 for a,b,w in zip(demand,row,bins))) for row in cell['joint_support'])
        if distance>artifact['policy'].get('maximum_support_distance',.25):continue
        return dict(status='WITHIN_VALIDATED_EMPIRICAL_REGION',actual_layout_required=True,
            suitable_intervals=list(zip(cell['observed_lower'],cell['observed_upper'])),
            maximum_validated_field_count=cell['context']['field_count'],
            maximum_validated_field_count_scope='MATCHED_CONTEXT_ONLY',hard_global_capacity=None,
            independent_groups=cell['independent_groups'],lower_bound=cell['one_sided_success_lower_bound'])
    return dict(status='UNKNOWN_OR_OUTSIDE_VALIDATED_REGION',actual_layout_required=True,hard_global_capacity=None)


def joint_demand(candidate,graph,width,height):
    from .design_synthesis import input_facts
    from .design_learning import grapheme_count
    from .design_style import font_identity,functional
    from .layout import text_geometry
    facts=sorted(input_facts(graph),key=lambda value:value['role_key'])
    items={item.slot.id:item for item in candidate.items};demand=[];fonts=[]
    for fact in facts:
        item=items[fact['render_id']];slot=item.slot
        if slot.kind=='logo':continue
        if slot.text_flow:
            from .design_text_flow import shape_flow
            measured=shape_flow(item.text,slot.font,slot.size_pt,item.scale,slot.rect.w,slot.font_asset,slot.font_style,item.tracking_mm,slot.text_flow,slot.kind)
            advance=measured['natural_advance_mm']
        else:
            advance,_,errors=text_geometry(slot.font,slot.size_pt,item.text,slot.font_style,slot.font_asset,item.tracking_mm)
            if errors:raise ValueError('Calibration font measurement is unknown')
        demand.extend([grapheme_count(fact['value']),advance/slot.size_pt])
        fonts.append(dict(role=fact['role_key'],font=font_identity(slot.font_asset),flow=functional(slot.text_flow)))
    return dict(family_id=candidate.template.family_id,font_signature=digest(fonts),field_count=len(facts),width_mm=width,height_mm=height,roles=[fact['role_key'] for fact in facts]),demand


class LocalCapacityCalibration:
    def __init__(self,library):
        from .design_learning import CrossWorkLearning
        self.learning=CrossWorkLearning(library);self.store=self.learning.store

    def save(self,model_id,records,policy,actor,approved=False):
        if not approved:raise ValueError('Explicit local capacity review is required')
        text(actor,'Capacity reviewer',120)
        model,dataset=self.learning.checked_model(model_id)
        entries={row['sample_id']:row for row in dataset['entries']}
        for row in records:
            entry=entries.get(row.get('sample_id'))
            if not entry or entry['role']!='VALIDATION' or row.get('lineage_group')!=entry['lineage_group']:
                raise ValueError('Capacity samples must match this model independent VALIDATION split')
        artifact=fit_capacity(records,policy)
        with self.store.transaction():
            fresh,_=self.learning.checked_model(model_id)
            if fresh!=model:raise ValueError('Model/support changed during capacity calibration')
            identity=digest([model['weights_digest'],artifact['digest']])
            prior=self.store.get('DESIGN_CAPACITY',identity)
            return prior or self.store._write('DESIGN_CAPACITY',identity,dict(model_id=model_id,
                weights_digest=model['weights_digest'],manifest_digest=model['manifest_digest'],artifact=artifact,actor=actor,
                scope='LOCAL_CALIBRATION_NOT_PRODUCTION_QUALIFICATION'),0,'local_conditional_capacity_calibrated')

    def checked(self,identity):
        record=self.store.get('DESIGN_CAPACITY',identity)
        if not record:raise ValueError('Capacity model missing')
        model,_=self.learning.checked_model(record['model_id'])
        if model['weights_digest']!=record['weights_digest'] or model['manifest_digest']!=record['manifest_digest']:
            raise ValueError('Capacity model dependencies changed')
        if record['artifact'].get('version')!=VERSION:
            raise ValueError('Capacity calibration version changed;explicit recalibration required')
        if digest({k:v for k,v in record['artifact'].items() if k!='digest'})!=record['artifact']['digest']:
            raise ValueError('Capacity calibration changed')
        return record

    def review_case(self,job_id,index,qualified_style,actor,evidence,approved=False):
        from .design_jobs import DesignJobs
        if not approved or type(qualified_style) is not bool:raise ValueError('Explicit independent suitable-style review required')
        text(actor,'Suitable-style reviewer',120);text(evidence,'Suitable-style evidence',2048)
        jobs=DesignJobs(self.learning.library);job=jobs.current(job_id)
        row=self.store.get('DESIGN_JOB_ITEM',jobs.item_key(job_id,index))
        if job['phase']!='COMPLETE' or not row or row['result']['role']!='VALIDATION':
            raise ValueError('Actual VALIDATION output must exist before capacity-style review')
        identity=digest([job_id,index,row['result_digest']])
        with self.store.transaction():
            if self.store.get('DESIGN_STYLE_REVIEW',identity):raise ValueError('Suitable-style review is immutable')
            return self.store._write('DESIGN_STYLE_REVIEW',identity,dict(job_id=job_id,index=index,
                result_digest=row['result_digest'],qualified_style=qualified_style,actor=actor,evidence=evidence),0,'actual_validation_suitability_reviewed')

    def from_evaluation(self,job_id,policy,actor,approved=False):
        from .design_jobs import DesignJobs
        from .design_session import _candidate
        from .design_synthesis import input_facts
        from .design_learning import grapheme_count
        from .design_style import font_identity,functional
        from .input_graph import InputGraph
        from .layout import text_geometry
        jobs=DesignJobs(self.learning.library);job=jobs.current(job_id)
        if job['kind']!='EVALUATE_LAYOUTS' or job['phase']!='COMPLETE':raise ValueError('Complete actual evaluation required for calibration')
        rows=jobs.results(job_id);records=[]
        for index,row in enumerate(rows):
            if row['role']!='VALIDATION':continue # Sealed HOLDOUT never fits a boundary.
            saved=self.store.get('DESIGN_JOB_ITEM',jobs.item_key(job_id,index))
            review=self.store.get('DESIGN_STYLE_REVIEW',digest([job_id,index,saved['result_digest']]))
            if not review or review['result_digest']!=saved['result_digest']:
                raise ValueError('Every VALIDATION case needs an explicit suitable-style review')
            if row['learned']['status']!='FEASIBLE':
                raise ValueError('Unshaped validation case has unknown joint demand;cannot calibrate this cohort')
            candidate=_candidate(row['learned']['serialized']);case=job['plan']['items'][index]
            graph=InputGraph(case['input_graph'])
            context,demand=joint_demand(candidate,graph,case['width_mm'],case['height_mm'])
            records.append(dict(id=row['case_id'],sample_id=row['sample_id'],role='VALIDATION',lineage_group=row['lineage_group'],
                context=context,demand=demand,layout_pass=row['learned']['integrity']['status']=='PASS',
                qualified_style=review['qualified_style'],evidence_refs=[job_id,saved['result_digest'],review['id']]))
        if not records:raise ValueError('No reviewed independent VALIDATION cohort')
        return self.save(job['plan']['model_id'],records,policy,actor,approved)

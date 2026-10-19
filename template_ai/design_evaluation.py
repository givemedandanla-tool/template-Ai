"""Independent layout integrity checks and grouped, immutable evaluation jobs.

No geometry score supplies aesthetic truth. Synthetic scale runs and authorized
real-source qualification are separate and cannot be promoted by a PASS label.
"""
from collections import Counter
from copy import deepcopy
import math
import platform
import psutil
import statistics
import time

from .training_store import TrainingStore,digest,text
from .design_learning import CrossWorkLearning
from .design_synthesis import synthesize,input_facts
from .design_session import DesignSessions
from .input_graph import InputGraph
from .design_jobs import DesignJobs


def wilson(success,total):
    if not total:return None
    z=1.959963984540054;p=success/total;denominator=1+z*z/total
    centre=(p+z*z/(2*total))/denominator
    radius=z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/denominator
    return [max(0.,centre-radius),min(1.,centre+radius)]


def check_layout(candidate,graph,intents=None):
    """Re-measure emitted data; independently inspect bounds, collisions and IDs."""
    from .layout import text_geometry
    from .logo_assets import errors as logo_errors
    expected={row['render_id']:row for row in input_facts(graph)}
    emitted={item.slot.id:item for item in candidate.items};errors=[]
    if len(emitted)!=len(candidate.items):errors.append('DUPLICATE_RENDER_ID')
    if set(expected)!=set(emitted):errors.append('DATA_COVERAGE_MISMATCH')
    for identity,item in emitted.items():
        fact=expected.get(identity);slot=item.slot
        if not fact:continue
        if slot.owner!=fact['owner_port']:errors.append('OWNER_CHANGED')
        if not slot.rect.inside(candidate.template.width_mm,candidate.template.height_mm):errors.append('OUTSIDE_CANVAS')
        if slot.kind=='logo':
            if fact['kind']!='company' or not item.logo or item.logo.get('company')!=fact['value'] or logo_errors(item.logo):
                errors.append('LOGO_INTEGRITY')
        else:
            label=candidate.risk_context.get('design_label_bindings',{}).get(identity,{'kind':'NO_FIXED_LABEL'})
            expected_text=(label.get('prefix','') if label.get('kind')=='DYNAMIC_PREFIX' else '')+fact['value']
            if slot.kind!=fact['kind'] or expected_text!=item.text:errors.append('DATA_CHANGED')
            if slot.text_flow:
                from .design_text_flow import shape_flow
                try:
                    flow=shape_flow(item.text,slot.font,slot.size_pt,item.scale,slot.rect.w,slot.font_asset,
                        slot.font_style,item.tracking_mm,slot.text_flow,slot.kind)
                    width,height=flow['width_mm'],flow['height_mm'];issues=[]
                except ValueError:width=height=0;issues=['FLOW_INVALID']
            else:
                width,height,issues=text_geometry(slot.font,slot.size_pt,item.text,slot.font_style,slot.font_asset,item.tracking_mm)
                width*=item.scale
            if issues:errors.append('FONT_SHAPING_UNVERIFIED')
            if width>slot.rect.w+1e-6 or height>slot.rect.h+1e-6:errors.append('ACTUAL_TEXT_OVERFLOW')
    items=list(emitted.values())
    for i,left in enumerate(items):
        for right in items[i+1:]:
            if left.slot.rect.intersects(right.slot.rect):errors.append('FIELD_COLLISION')
    for intent in list(intents or [])+candidate.risk_context.get('design_relations',[]):
        if intent['subject'] not in emitted or intent['object'] not in emitted:errors.append('INTENT_REFERENCE_MISSING');continue
        a=emitted[intent['subject']].slot.rect;b=emitted[intent['object']].slot.rect
        okay={'ABOVE':a.y+a.h<=b.y+1e-6,'BELOW':b.y+b.h<=a.y+1e-6,
              'LEFT_OF':a.x+a.w<=b.x+1e-6,'RIGHT_OF':b.x+b.w<=a.x+1e-6}.get(intent['relation'],False)
        if not okay:errors.append('EXPLICIT_RELATION_VIOLATED')
    return dict(status='PASS' if not errors else 'FAIL',errors=sorted(set(errors)),
        expected_instances=len(expected),emitted_instances=len(emitted),
        data_integrity=1. if not any(code in errors for code in ('DUPLICATE_RENDER_ID','DATA_COVERAGE_MISMATCH','OWNER_CHANGED','DATA_CHANGED','LOGO_INTEGRITY')) else 0.)


class DesignEvaluation:
    def __init__(self,library):
        self.library=library;self.learning=CrossWorkLearning(library);self.jobs=DesignJobs(library);self.store=self.jobs.store

    def create(self,model_id,cases,policy,actor,*,origin,review_refs,approved=False):
        if not approved or origin not in ('AUTHORED_SYNTHETIC','REAL_AUTHORIZED_CORPUS') or not review_refs:
            raise ValueError('Explicit corpus origin and independent source-review evidence required')
        model,dataset=self.learning.checked_model(model_id)
        if not isinstance(cases,list) or not cases:raise ValueError('Explicit grouped cases required')
        entries={row['sample_id']:row for row in dataset['entries']}
        identities=set()
        for case in cases:
            text(case.get('id'),'Evaluation case ID',128)
            if case['id'] in identities:raise ValueError('Duplicate evaluation case ID')
            identities.add(case['id']);entry=entries.get(case.get('sample_id'))
            if not entry or entry['role'] not in ('VALIDATION','HOLDOUT'):raise ValueError('TRAIN sources cannot masquerade as independent evaluation')
            InputGraph(case['input_graph'])
            if not case.get('truth_refs'):raise ValueError('Independent input/source correspondence review is required')
        return self.jobs.create('EVALUATE_LAYOUTS',dict(model_id=model_id,weights_digest=model['weights_digest'],
            manifest_digest=model['manifest_digest'],items=deepcopy(cases),policy=deepcopy(policy),
            origin=origin,review_refs=deepcopy(review_refs),independence='KNOWN_LINEAGE_GROUPS_ONLY;UNREVIEWED_NEAR_DUPLICATES_UNKNOWN'),actor,True)

    def review_preference(self,job_id,index,winner,actor,evidence,scope='ORDER'):
        if winner not in ('LEARNED','BASELINE','TIE','NEITHER') or scope not in ('ORDER','CUSTOMER','REVIEWED_STYLE'):
            raise ValueError('Explicit independent comparison and scope required')
        text(actor,'Preference reviewer',120);text(evidence,'Preference evidence',2048)
        job=self.jobs.current(job_id);row=self.store.get('DESIGN_JOB_ITEM',self.jobs.item_key(job_id,index))
        if job['kind']!='EVALUATE_LAYOUTS' or not row:raise ValueError('Actual paired output must exist before comparison')
        if not row['result']['learned'].get('placement_digest') or not row['result']['baseline'].get('placement_digest'):
            raise ValueError('Both exact actual layouts must exist before aesthetic comparison')
        with self.store.transaction():
            from .model import new_id
            return self.store._write('DESIGN_PREFERENCE_REVIEW',new_id(),dict(job_id=job_id,index=index,
                result_digest=row['result_digest'],winner=winner,actor=actor,evidence=evidence,scope=scope,
                role=row['result']['role'],global_policy_changed=False,label_source='EXPLICIT_INDEPENDENT_COMPARISON'),0,'independent_layout_preference_reviewed')


def owned_example(index):
    # Authored anonymous descriptor workload, not parsed AI files or font fidelity.
    style=index%3;variation=(index%17)*.02
    return dict(id='owned-'+str(index),role='TRAIN',lineage_group='owned-lineage-'+str(index),
        width_mm=90.,height_mm=54.,fields=[dict(id='name',owner='p1',kind='name',index=0,
            rect=dict(x=5.+style*20+variation,y=5.,w=25.,h=7.)),
            dict(id='phone',owner='p1',kind='phone',index=0,rect=dict(x=5.+style*20+variation,y=22.,w=25.,h=6.))])


def execute_item(library,job,index):
    plan=job['plan'];kind=job['kind'];item=plan['items'][index]
    if kind=='TRAIN_SHARED_MODEL':
        model=CrossWorkLearning(library).train(plan['dataset_id'],job['actor'],plan.get('settings'),True,
            origin_job=job['id'],previous_model_id=plan.get('previous_model_id'))
        return dict(model_id=model['id'],weights_digest=model['weights_digest'])
    if kind=='OWNED_DESCRIPTOR_BENCHMARK':
        from .design_family import feature_vector
        vector=feature_vector(owned_example(item))
        return dict(index=item,feature_digest=digest(vector),unknown_source_typography=True)
    if kind!='EVALUATE_LAYOUTS':raise ValueError('Unsupported design job kind')
    learning=CrossWorkLearning(library);model,dataset=learning.checked_model(plan['model_id'])
    if model['weights_digest']!=plan['weights_digest'] or model['manifest_digest']!=plan['manifest_digest']:
        raise ValueError('Evaluation model/data changed')
    entry=next(row for row in dataset['entries'] if row['sample_id']==item['sample_id'])
    graph=InputGraph(item['input_graph']);policy=dict(plan['policy'],approved=True)
    logos=DesignSessions(library).resolve_logos(graph,item['width_mm'],item['height_mm'])
    from .design_session import _serialize
    from .candidate_risk import placement_digest
    outputs={}
    for label,joint in (('learned',True),('baseline',False)):
        choices=[];statuses=[]
        for profile in model['artifact']['profile_model']['families']:
            result=synthesize(profile,graph,item['width_mm'],item['height_mm'],dict(policy,enable_joint_prediction=joint),item.get('intents'),logos)
            statuses.append(result['status']);choices.extend(result['candidates'])
        choices.sort(key=lambda row:(-row['candidate'].score,row['geometry_digest']))
        if choices:
            candidate=choices[0]['candidate'];integrity=check_layout(candidate,graph,item.get('intents'))
            outputs[label]=dict(status='FEASIBLE' if integrity['status']=='PASS' else 'HARD_ERROR',integrity=integrity,
                placement_digest=placement_digest(candidate),serialized=_serialize(candidate),
                family_id=candidate.template.family_id)
        else:outputs[label]=dict(status='UNKNOWN_OR_UNSUPPORTED',search_states=statuses,integrity=None)
    if entry['role']=='HOLDOUT':
        with learning.store.transaction():
            key=digest([job['id'],index])
            if not learning.store.get('DESIGN_HOLDOUT_EXPOSURE',key):
                learning.store._write('DESIGN_HOLDOUT_EXPOSURE',key,dict(model_id=model['id'],job_id=job['id'],
                    sample_id=item['sample_id'],source_hash=entry['source_hash'],weights_digest=model['weights_digest']),0,'heldout_actual_layout_exposed_no_fit')
    return dict(case_id=item['id'],sample_id=item['sample_id'],role=entry['role'],lineage_group=entry['lineage_group'],
        origin=plan['origin'],learned=outputs['learned'],baseline=outputs['baseline'],
        aesthetics='UNKNOWN_WITHOUT_INDEPENDENT_PAIR_REVIEW')


def summarize_job(library,job,results):
    if job['kind']=='TRAIN_SHARED_MODEL':return dict(model_id=results[0]['model_id'],scope='CANDIDATE_NOT_ACTIVATED')
    common=dict(process_platform=platform.platform(),elapsed_item_seconds=job['elapsed_seconds'],
        items=len(results),hardware_scope='CURRENT_PROCESS_CURRENT_HOST_ONLY',
        process_rss_kib=psutil.Process().memory_info().rss/1024)
    if job['kind']=='OWNED_DESCRIPTOR_BENCHMARK':
        from .design_family import train_families
        from .design_profiles import learn_profiles
        started=time.perf_counter();examples=[owned_example(index) for index in job['plan']['items']]
        families=train_families(examples);profiles=learn_profiles(families,examples)
        return dict(common,scope='AUTHORED_DESCRIPTOR_EXTRACTION_AND_SHARED_FAMILY_PROFILE_FIT_ONLY_NOT_REAL_AI_IMPORT',
            fit_seconds=time.perf_counter()-started,families=len(families['families']),
            profile_count=len(profiles['families']),source_font_fidelity='NOT_MEASURED',production_qualification='NOT_EVALUATED')
    statuses=Counter(row['learned']['status'] for row in results);feasible=statuses['FEASIBLE']
    known=[row['learned']['integrity'] for row in results if row['learned']['integrity']]
    group_counts=Counter(row['lineage_group'] for row in results)
    group_feasible=Counter(row['lineage_group'] for row in results if row['learned']['status']=='FEASIBLE')
    groups=len(group_counts)
    macro=sum(group_feasible[key]/count for key,count in group_counts.items())/groups
    all_feasible=sum(group_feasible[key]==count for key,count in group_counts.items())
    return dict(common,origin=job['plan']['origin'],denominator=len(results),independent_lineage_groups=groups,
        statuses=dict(statuses),feasible_rate=feasible/len(results),case_wilson_95=wilson(feasible,len(results)),
        uncertainty='CASE_INTERVAL_NOT_GROUP_BOOTSTRAP;MULTIPLE_CASES_IN_GROUP_ARE_CORRELATED',
        group_macro_feasible_rate=macro,group_all_cases_feasible=all_feasible,
        group_all_cases_feasible_wilson_95=wilson(all_feasible,groups),data_integrity_denominator=len(known),
        group_statistics_scope='EQUAL_WEIGHT_KNOWN_LINEAGE_GROUPS;ALL_CASES_SUCCESS_INTERVAL_IS_DIFFERENT_FROM_CASE_RATE',
        hard_error_count=statuses['HARD_ERROR'],data_integrity_rate=min((row['data_integrity'] for row in known),default=None),
        baseline_feasible=sum(row['baseline']['status']=='FEASIBLE' for row in results),
        preference_quality='UNKNOWN_WITHOUT_INDEPENDENT_PAIR_REVIEW',production_qualification='NOT_EVALUATED')

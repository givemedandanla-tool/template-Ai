"""Bounded shared-rule synthesis with real Qt measurements and Kiwi geometry.

Produces preview candidates without publishing a template or bypassing prepress.
Formal instance qualification is a separate persisted lifecycle decision.
"""
from copy import deepcopy
from itertools import product, islice
import math
import kiwisolver as kiwi
import networkx as nx

from .model import Template, Slot, Rect, template_errors
from .layout import Candidate, Placed, text_geometry, layout_dependency
from .candidate_risk import pin_inputs
from .training_store import digest

VERSION='cross-work-synthesis-1'
RELATIONS={'ABOVE','BELOW','LEFT_OF','RIGHT_OF'}


def input_facts(graph):
    graph.validate(graph.data)
    people={row['id']:'p'+str(i+1) for i,row in enumerate(graph.data['people'])}
    companies={row['id']:'c'+str(i+1) for i,row in enumerate(graph.data['companies'])}
    ports=dict(people,**companies);counts={};facts=[]
    for row in graph.data['fields']:
        for entity in row['users']:
            kind='company' if entity in companies and row['kind']=='name' else row['kind']
            key=(entity,kind);index=counts.get(key,0);counts[key]=index+1
            if not row['value']:continue
            facts.append(dict(field_id=row['id'],entity_id=entity,owner_port=ports[entity],kind=kind,
                index=index,value=row['value'],role_key=ports[entity]+':'+kind+':'+str(index),
                render_id='render-'+digest([row['id'],entity])[:32]))
    return facts


def _font_options(profile, key, width, height, value=None, policy=None):
    options={}
    for data in profile['data_requirement_profiles']:
        for sample in data['presentation_evidence']:
            if sample['role_key']!=key:continue
            vector=sample['joint'];asset=sample['source_font_ref']
            if (not isinstance(asset,dict) or vector['source_pt'] is None
                    or vector['horizontal_scale'] is None or vector['tracking_mm'] is None):continue
            if not 1<=vector['source_pt']<=200 or not .05<=vector['horizontal_scale']<=1 or not 0<=vector['tracking_mm']<=2:
                continue  # Observed source facts survive; current output policy is narrower.
            candidate=dict(font_asset=deepcopy(asset),size_pt=vector['source_pt'],scale=vector['horizontal_scale'],
                tracking_mm=vector['tracking_mm'],width_mm=sample['frame'][2]*width,
                height_mm=sample['frame'][3]*height,source_dimension_mm=sample['dimensions_mm'],
                label_binding=deepcopy(sample['label_binding']),source_ref=sample['example_id'])
            identity=digest({k:v for k,v in candidate.items() if k!='source_ref'})
            if identity not in options:options[identity]=dict(candidate,id=identity,support=0)
            options[identity]['support']+=1
    if value is not None and (policy or {}).get('enable_joint_prediction') is True:
        from .design_joint import predict_joint
        role=next(row for row in profile['roles'] if row['key']==key)
        joint_model=role.get('conditional_joint_model',{})
        measured={}
        for mode in joint_model.get('modes',[]):
            condition=mode['condition'];asset=condition['font_asset'];label=condition['label_binding']
            if label.get('status')!='CONFIRMED' or label.get('kind') not in ('NO_FIXED_LABEL','DYNAMIC_PREFIX'):continue
            display=label.get('prefix','')+value if label.get('kind')=='DYNAMIC_PREFIX' else value
            identity=digest([asset,display])
            if identity not in measured:
                measured[identity]=text_geometry(asset['families'][0],12.,display,
                    (asset.get('styles') or [''])[0],asset,0.)
            advance,_,errors=measured[identity]
            if errors or advance<=0:continue
            for prediction in predict_joint(joint_model,width,height,advance/12.):
                if prediction['mode_id']!=mode['id']:continue
                vector=prediction['joint']
                if not (1<=vector['source_pt']<=200 and .05<=vector['horizontal_scale']<=1
                        and 0<=vector['tracking_mm']<=2 and vector['frame_width_mm']>0 and vector['frame_height_mm']>0):continue
                candidate=dict(font_asset=deepcopy(asset),size_pt=vector['source_pt'],scale=vector['horizontal_scale'],
                    tracking_mm=vector['tracking_mm'],width_mm=vector['frame_width_mm'],height_mm=vector['frame_height_mm'],
                    source_dimension_mm=[width,height],label_binding=deepcopy(label),source_ref='JOINT:'+mode['id'],
                    support=prediction['support'],joint_prediction=prediction)
                candidate['id']=digest(candidate);options[candidate['id']]=candidate
    return sorted(options.values(),key=lambda row:(-row['support'],
        abs(row['source_dimension_mm'][0]-width)+abs(row['source_dimension_mm'][1]-height),row['id']))


def _relation_graph(relations, ids):
    horizontal,vertical=nx.DiGraph(),nx.DiGraph();horizontal.add_nodes_from(ids);vertical.add_nodes_from(ids)
    for intent in relations:
        if set(intent)!={'subject','relation','object'} or intent['relation'] not in RELATIONS:
            raise ValueError('Only typed relative-position intent is supported')
        a,b=intent['subject'],intent['object']
        if a not in ids or b not in ids or a==b:raise ValueError('Position intent has a missing or repeated instance')
        graph=vertical if intent['relation'] in ('ABOVE','BELOW') else horizontal
        graph.add_edge(b,a) if intent['relation'] in ('BELOW','RIGHT_OF') else graph.add_edge(a,b)
    if not nx.is_directed_acyclic_graph(horizontal) or not nx.is_directed_acyclic_graph(vertical):
        raise ValueError('Relative-position intent contains a cycle')
    return horizontal,vertical


def synthesize(profile, graph, width_mm, height_mm, policy, intents=None, logos=None):
    width,height=width_mm,height_mm
    if any(type(value) not in (int,float) or not math.isfinite(value) or not 0<value<=2000 for value in (width,height)):
        raise ValueError('Physical output size is invalid')
    if not isinstance(policy,dict) or policy.get('approved') is not True or not policy.get('version'):
        raise ValueError('Synthesis needs a versioned approved core policy')
    budget=policy.get('candidate_budget',32)
    if type(budget) is not int or not 1<=budget<=1024:raise ValueError('Invalid bounded candidate budget')
    margin=policy.get('safe_margin_mm',0.)
    if type(margin) not in (int,float) or not math.isfinite(margin) or not 0<=margin<min(width,height)/2:
        raise ValueError('Invalid approved physical margin')
    intents=deepcopy(intents or []);facts=input_facts(graph)
    if not 1<=len(facts)<=64:raise ValueError('Synthesis field processing budget exceeded;not a learned capacity')
    ids={row['render_id'] for row in facts};horizontal,vertical=_relation_graph(intents,ids)
    moved={intent[key] for intent in intents for key in ('subject','object')}
    allowed=set(policy.get('movable_kinds',('phone','email','line','ig','address')))
    subjects={intent['subject'] for intent in intents}
    if any(row['render_id'] in subjects and row['kind'] not in allowed for row in facts):
        raise ValueError('Requested protected role is outside approved relative-position policy')
    by_render={row['render_id']:row for row in facts}
    if any(by_render[intent['subject']]['owner_port']!=by_render[intent['object']]['owner_port'] for intent in intents):
        raise ValueError('Cross-owner relative editing needs separately supported group correspondence')
    roles={role['key']:role for role in profile['roles']};missing=[];options=[]
    for fact in facts:
        if fact['role_key'] not in roles:
            missing.append(dict(render_id=fact['render_id'],reason='UNSUPPORTED_ROLE_OR_REPEAT_COUNT'));continue
        rows=_font_options(profile,fact['role_key'],width,height,fact['value'],policy)
        if not rows:missing.append(dict(render_id=fact['render_id'],reason='SOURCE_JOINT_TYPOGRAPHY_OR_FONT_IDENTITY_UNKNOWN'))
        options.append(rows)
    base=dict(version=VERSION,family_id=profile['family_id'],input_digest=digest(graph.data),
        policy_version=policy['version'],intents=intents,field_refs=[{k:v for k,v in f.items() if k!='value'} for f in facts],
        actual_template_objects_created=0,scope='CURRENT_INPUT_PREVIEW_NOT_GLOBAL_TEMPLATE_OR_FORMAL_APPROVAL')
    if missing:
        return dict(base,status='SOURCE_EVIDENCE_REQUIRED',issues=missing,candidates=[],searched=0,
                    complete_search=False)
    people,companies,compiled_logos=graph.compile()
    logos=deepcopy(logos if logos is not None else compiled_logos)
    # Whole Logo graphics cannot be silently omitted or fabricated as text.
    if any(role['kind']=='logo' for role in profile['roles']) or any(row['logo_id'] for row in graph.data['companies']):
        return dict(base,status='ASSET_ADAPTATION_REQUIRED',issues=[dict(reason='WHOLE_SIZE_SPECIFIC_LOGO_RULE_REQUIRED')],
                    candidates=[],searched=0,complete_search=False)
    combinations=math.prod(len(row) for row in options);candidates=[];attempts=[]
    for selected in islice(product(*options),budget):
        solver=kiwi.Solver();variables={};slots=[];measurements=[];failure=None
        try:
            for fact,configuration in zip(facts,selected):
                role=roles[fact['role_key']];frame=role['frame_centre'];asset=configuration['font_asset']
                family=asset['families'][0];style=(asset.get('styles') or [''])[0]
                label=configuration['label_binding']
                if label.get('status')!='CONFIRMED' or label.get('kind') not in ('NO_FIXED_LABEL','DYNAMIC_PREFIX'):
                    failure='LABEL_BINDING_UNKNOWN';break
                if label.get('kind')=='DYNAMIC_PREFIX':
                    prefix=label.get('prefix')
                    if not isinstance(prefix,str) or len(prefix)>128:failure='LABEL_PREFIX_UNVERIFIED';break
                    display=prefix+fact['value']
                else:display=fact['value']
                tw,th,errors=text_geometry(family,configuration['size_pt'],display,style,asset,configuration['tracking_mm'])
                if errors:failure='FONT_MEASUREMENT_UNVERIFIED';break
                w,h=configuration['width_mm'],configuration['height_mm']
                if tw*configuration['scale']>w+1e-7 or th>h+1e-7:failure='MEASURED_TEXT_EXCEEDS_JOINT_CONFIGURATION';break
                rid=fact['render_id'];x,y=kiwi.Variable(rid+'-x'),kiwi.Variable(rid+'-y');variables[rid]=(x,y,w,h)
                for constraint in (x>=margin,y>=margin,x+w<=width-margin,y+h<=height-margin):solver.addConstraint(constraint)
                solver.addConstraint((x==frame[0]*width)|kiwi.strength.strong)
                solver.addConstraint((y==frame[1]*height)|kiwi.strength.strong)
                slots.append(Slot(fact['kind'],fact['owner_port'],Rect(frame[0]*width,frame[1]*height,w,h),
                    index=fact['index'],font=family,font_style=style,size_pt=configuration['size_pt'],
                    min_scale=configuration['scale'],font_asset=deepcopy(asset),id=rid,tracking_mm=configuration['tracking_mm'],
                    tracking_min_mm=configuration['tracking_mm'],tracking_max_mm=configuration['tracking_mm']))
                measurements.append(dict(render_id=rid,text=display,width_mm=tw,height_mm=th,
                    scale=configuration['scale'],configuration_id=configuration['id']))
            if failure:
                attempts.append(dict(reason=failure,configuration_ids=[row['id'] for row in selected]));continue
            # Preserve unaffected pair topology; incident edges can be replaced
            # by explicit customer intent. Each remaining pair gets one legal
            # separation branch; unsupported overlapping learned frames abstain.
            preferred={row['render_id']:i for i,row in enumerate(sorted(facts,
                key=lambda row:(roles[row['role_key']]['frame_centre'][1],
                                roles[row['role_key']]['frame_centre'][0],row['render_id'])))}
            vgraph=vertical.copy();hgraph=horizontal.copy()
            for i,a in enumerate(facts):
                for b in facts[i+1:]:
                    aid,bid=a['render_id'],b['render_id']
                    if aid in moved or bid in moved:continue
                    af=roles[a['role_key']]['frame_centre'];bf=roles[b['role_key']]['frame_centre']
                    if af[1]+af[3]<=bf[1]+1e-9:vgraph.add_edge(aid,bid)
                    elif bf[1]+bf[3]<=af[1]+1e-9:vgraph.add_edge(bid,aid)
                    elif af[0]+af[2]<=bf[0]+1e-9:hgraph.add_edge(aid,bid)
                    elif bf[0]+bf[2]<=af[0]+1e-9:hgraph.add_edge(bid,aid)
            if not nx.is_directed_acyclic_graph(vgraph) or not nx.is_directed_acyclic_graph(hgraph):
                raise ValueError('Intent contradicts protected relative structure')
            for a,b in sorted(horizontal.edges):
                ax,ay,aw,ah=variables[a];bx,by,bw,bh=variables[b];solver.addConstraint(ax+aw<=bx)
            for a,b in sorted(vertical.edges):
                ax,ay,aw,ah=variables[a];bx,by,bw,bh=variables[b];solver.addConstraint(ay+ah<=by)
            vrank={rid:i for i,rid in enumerate(nx.lexicographical_topological_sort(vgraph,key=lambda rid:(preferred[rid],rid)))}
            hrank={rid:i for i,rid in enumerate(nx.lexicographical_topological_sort(hgraph,key=lambda rid:(preferred[rid],rid)))}
            vertical_edit=any(intent['relation'] in ('ABOVE','BELOW') for intent in intents)
            for i,a in enumerate(facts):
                for b in facts[i+1:]:
                    aid,bid=a['render_id'],b['render_id'];ax,ay,aw,ah=variables[aid];bx,by,bw,bh=variables[bid]
                    if (horizontal.has_edge(aid,bid) or horizontal.has_edge(bid,aid)
                            or vertical.has_edge(aid,bid) or vertical.has_edge(bid,aid)):continue
                    elif aid in moved or bid in moved:
                        if vertical_edit:
                            solver.addConstraint(ay+ah<=by if vrank[aid]<vrank[bid] else by+bh<=ay)
                        else:
                            solver.addConstraint(ax+aw<=bx if hrank[aid]<hrank[bid] else bx+bw<=ax)
                    else:
                        af=roles[a['role_key']]['frame_centre'];bf=roles[b['role_key']]['frame_centre']
                        if af[1]+af[3]<=bf[1]+1e-9:solver.addConstraint(ay+ah<=by)
                        elif bf[1]+bf[3]<=af[1]+1e-9:solver.addConstraint(by+bh<=ay)
                        elif af[0]+af[2]<=bf[0]+1e-9:solver.addConstraint(ax+aw<=bx)
                        elif bf[0]+bf[2]<=af[0]+1e-9:solver.addConstraint(bx+bw<=ax)
                        else:raise ValueError('No learned separation branch;not a proof of global infeasibility')
            solver.updateVariables()
            for slot in slots:
                x,y,w,h=variables[slot.id];slot.rect=Rect(x.value(),y.value(),w,h)
            template=Template(name='Learned '+profile['family_id'],width_mm=width,height_mm=height,
                slots=slots,capacity=len(people),family_id=profile['family_id'],
                id='instance-'+digest([profile['family_id'],graph.data,intents,[row['id'] for row in selected]])[:32],
                company_bindings={f'p{i+1}':person.get('companies',[]) for i,person in enumerate(people)
                                  if person.get('companies')},safe_margin_mm=margin)
            errors=template_errors(template)
            if errors:
                attempts.append(dict(reason='WHOLE_TEMPLATE_CHECK_FAILED',details=errors));continue
            items=[Placed(slot,measurement['text'],measurement['scale'],slot.tracking_mm)
                   for slot,measurement in zip(slots,measurements)]
            candidate=Candidate(template,items,['新學習實例尚待正式來源／模型資格核實'],
                score=-sum(abs(slot.rect.x-roles[fact['role_key']]['frame_centre'][0]*width)
                           +abs(slot.rect.y-roles[fact['role_key']]['frame_centre'][1]*height)
                           for slot,fact in zip(slots,facts)),
                diagnostics=[dict(code='UNPUBLISHED',severity='BLOCK')],
                dependency_stamp=layout_dependency(template,logos))
            pin_inputs(candidate,people,companies,logos)
            candidates.append(dict(candidate=candidate,configuration_ids=[row['id'] for row in selected],
                geometry_digest=digest(template.to_dict()),measurements=measurements,legal_preview_geometry=True,
                formal_qualification='NOT_EVALUATED'))
        except (kiwi.UnsatisfiableConstraint,ValueError,KeyError) as error:
            attempts.append(dict(reason=type(error).__name__,message=str(error)))
    candidates.sort(key=lambda row:(-row['candidate'].score,row['configuration_ids'],row['geometry_digest']))
    searched=min(combinations,budget)
    return dict(base,status='FEASIBLE_PREVIEW' if candidates else 'SEARCH_EXHAUSTED' if combinations>budget else 'NO_SUPPORTED_CANDIDATE',
        candidates=candidates,searched=searched,complete_search=combinations<=budget,
        all_mathematical_layouts_enumerated=False,issues=attempts,
        default_basis='MINIMUM_DEVIATION_THEN_STABLE_CONFIGURATION_AND_GEOMETRY',
        best_scope='SEARCHED_SOURCE_SUPPORTED_CONFIGURATIONS_ONLY')

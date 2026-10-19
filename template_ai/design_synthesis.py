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
from .design_style import style_identity, font_identity

VERSION='cross-work-synthesis-2-domain-admission'
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
            from .design_assignment import semantic_observation
            facts.append(dict(semantic_observation=semantic_observation(kind,row['value']),field_id=row['id'],entity_id=entity,owner_port=ports[entity],kind=kind,
                index=index,value=row['value'],role_key=ports[entity]+':'+kind+':'+str(index),
                render_id='render-'+digest([row['id'],entity])[:32]))
    return facts


def _font_options(profile, key, width, height, value=None, policy=None, semantic_type=None):
    options={};support_groups={}
    for data in profile['data_requirement_profiles']:
        for sample in data['presentation_evidence']:
            if sample['role_key']!=key:continue
            observed=sample['semantic_type']
            if semantic_type in ('mobile','landline') and observed in ('mobile','landline') and observed!=semantic_type:continue
            vector=sample['joint'];asset=sample['source_font_ref']
            if (not isinstance(asset,dict) or vector['source_pt'] is None
                    or vector['horizontal_scale'] is None or vector['tracking_mm'] is None):continue
            if not 1<=vector['source_pt']<=200 or not .05<=vector['horizontal_scale']<=10 or not 0<=vector['tracking_mm']<=2:
                continue  # Observed source facts survive; current output policy is narrower.
            if vector.get('word_spacing_mm') not in (None,0,0.):
                spacing=(sample.get('source_text_flow') or {}).get('spacing_rule',{})
                if (spacing.get('mode')!='WORDS' or spacing.get('status')!='HUMAN_CONFIRMED_SOURCE_RULE'
                        or spacing.get('value_mm')!=vector['word_spacing_mm']):
                    continue # Never silently lose a known original word-spacing style.
            candidate=dict(font_asset=deepcopy(asset),size_pt=vector['source_pt'],scale=vector['horizontal_scale'],
                tracking_mm=vector['tracking_mm'],width_mm=sample['frame'][2]*width,
                height_mm=sample['frame'][3]*height,source_dimension_mm=sample['dimensions_mm'],
                label_binding=deepcopy(sample['label_binding']),align=sample['align'] if sample['align'] in ('left','center','right','distributed') else 'left',
                source_alignment_status='REVIEWED' if sample['align']!='UNKNOWN' else 'UNKNOWN_PREVIEW_FALLBACK',
                distribution=deepcopy(sample['distribution']),text_flow=deepcopy(sample.get('source_text_flow')),source_ref=sample['example_id'])
            identity=digest(style_identity({k:v for k,v in candidate.items()
                if k not in ('source_ref','source_dimension_mm')}))
            if identity not in options:
                options[identity]=dict(candidate,id=identity,support=0,source_refs=[],observed_dimensions_mm=[])
            option=options[identity]
            option['source_refs'].append(sample['example_id'])
            if list(sample['dimensions_mm']) not in option['observed_dimensions_mm']:
                option['observed_dimensions_mm'].append(list(sample['dimensions_mm']))
            distance=lambda dimensions:abs(dimensions[0]-width)+abs(dimensions[1]-height)
            if (distance(sample['dimensions_mm']),sample['example_id']) < (distance(option['source_dimension_mm']),option['source_ref']):
                for name in ('source_dimension_mm','source_ref','font_asset','label_binding','distribution','text_flow'):
                    option[name]=deepcopy(candidate[name])
            support_groups.setdefault(identity,set()).add(sample['lineage_group'])
            option['support']=len(support_groups[identity])
    for option in options.values():
        option['source_refs']=sorted(set(option['source_refs']))
        option['observed_dimensions_mm'].sort()
        option['size_admission']=('OBSERVED_EXACT_SIZE' if any(
            abs(d[0]-width)<1e-7 and abs(d[1]-height)<1e-7 for d in option['observed_dimensions_mm'])
            else 'UNVERIFIED_SIZE_PREVIEW_ONLY')
    if value is not None and (policy or {}).get('enable_joint_prediction') is True:
        from .design_joint import predict_joint
        role=next(row for row in profile['roles'] if row['key']==key)
        joint_model=role.get('conditional_joint_model',{})
        measured={}
        for mode in joint_model.get('modes',[]):
            condition=mode['condition'];asset=condition['font_asset'];label=condition['label_binding']
            if condition.get('word_spacing_mm') not in (None,0,0.):
                rule=(condition.get('text_flow') or {}).get('spacing_rule',{})
                if rule.get('mode')!='WORDS' or rule.get('value_mm')!=condition['word_spacing_mm']:continue
            if label.get('status')!='CONFIRMED' or label.get('kind') not in ('NO_FIXED_LABEL','DYNAMIC_PREFIX','SEPARATE_STATIC_LABEL'):continue
            display=label.get('prefix','')+value if label.get('kind')=='DYNAMIC_PREFIX' else value
            flow=condition.get('text_flow')
            identity=digest([asset,display,flow])
            if identity not in measured:
                if flow and flow.get('rich_text'):
                    from .design_text_flow import shape_flow
                    ratios=[part['pt_ratio'] for part in flow['rich_text']['segments']]
                    reference_pt=min(max(12.,1/min(ratios)),200/max(ratios))
                    try:
                        shaped=shape_flow(display,asset['families'][0],reference_pt,1.,2000.,asset,
                            (asset.get('styles') or [''])[0],0.,flow,key.split(':')[1])
                        measured[identity]=(shaped['natural_advance_mm']/reference_pt*12.,0.,[])
                    except ValueError:measured[identity]=(0.,0.,['COMPOSITE_DEMAND_UNSUPPORTED'])
                else:measured[identity]=text_geometry(asset['families'][0],12.,display,
                    (asset.get('styles') or [''])[0],asset,0.)
            advance,_,errors=measured[identity]
            if errors or advance<=0:continue
            for prediction in predict_joint(joint_model,width,height,advance/12.):
                if prediction['mode_id']!=mode['id']:continue
                vector=prediction['joint']
                if not (1<=vector['source_pt']<=200 and .05<=vector['horizontal_scale']<=10
                        and 0<=vector['tracking_mm']<=2 and vector['frame_width_mm']>0 and vector['frame_height_mm']>0):continue
                candidate=dict(font_asset=deepcopy(asset),size_pt=vector['source_pt'],scale=vector['horizontal_scale'],
                    tracking_mm=vector['tracking_mm'],width_mm=vector['frame_width_mm'],height_mm=vector['frame_height_mm'],
                    source_dimension_mm=[width,height],label_binding=deepcopy(label),source_ref='JOINT:'+mode['id'],
                    support=prediction['support'],joint_prediction=prediction,size_admission='LEARNED_JOINT_DOMAIN',
                    align=condition['align'] if condition['align'] in ('left','center','right','distributed') else 'left',
                    source_alignment_status='REVIEWED' if condition['align']!='UNKNOWN' else 'UNKNOWN_PREVIEW_FALLBACK',
                    distribution=deepcopy(condition['distribution']),text_flow=deepcopy(condition.get('text_flow')))
                spacing=(candidate.get('text_flow') or {}).get('spacing_rule')
                if spacing and spacing.get('mode')=='WORDS':
                    word_value=vector.get('word_spacing_mm')
                    if word_value is None or not 0<=word_value<=2:continue
                    spacing['value_mm']=word_value
                elif spacing and spacing.get('mode')=='CHARACTERS':spacing['value_mm']=vector['tracking_mm']
                candidate['id']=digest(candidate);options[candidate['id']]=candidate
    return sorted(options.values(),key=lambda row:(row.get('size_admission')=='UNVERIFIED_SIZE_PREVIEW_ONLY',-row['support'],
        abs(row['source_dimension_mm'][0]-width)+abs(row['source_dimension_mm'][1]-height),row['id']))


def _adapt_distribution(profile,key,configuration,display,kind):
    if configuration.get('align')!='distributed':return configuration
    from .text_policy import tracking_geometry
    groups=set();tracking=[]
    for data in profile['data_requirement_profiles']:
        for row in data['presentation_evidence']:
            vector=row['joint'];approval=row['distribution']
            if (row['role_key']!=key or row['align']!='distributed' or not isinstance(approval,dict)
                    or approval.get('approved') is not True or not row['source_font_ref']):continue
            if (font_identity(row['source_font_ref'])!=font_identity(configuration['font_asset'])
                    or vector['source_pt']!=configuration['size_pt'] or vector['horizontal_scale']!=configuration['scale']
                    or vector['tracking_mm'] is None):continue
            original_width=row['frame'][2]*row['dimensions_mm'][0]
            original_height=row['frame'][3]*row['dimensions_mm'][1]
            if abs(original_width-configuration['width_mm'])>1e-5 or abs(original_height-configuration['height_mm'])>1e-5:continue
            groups.add(row['lineage_group']);tracking.append(vector['tracking_mm'])
    if len(groups)<5:return configuration
    result=deepcopy(configuration);asset=result['font_asset']
    slot=Slot(kind,'p1',Rect(0,0,result['width_mm']/result['scale'],result['height_mm']),
        font=asset['families'][0],font_style=(asset.get('styles') or [''])[0],font_asset=asset,
        size_pt=result['size_pt'],align='distributed',tracking_mm=result['tracking_mm'],
        tracking_min_mm=min(tracking),tracking_max_mm=max(tracking),distribution_approval=result['distribution'])
    _,_,errors,chosen,strategy=tracking_geometry(slot,display,text_geometry)
    if errors:raise ValueError('Learned distribution measurement or semantic permission failed')
    result['tracking_mm']=chosen;result['distribution_adaptation']=dict(strategy=strategy,
        conditioned_tracking_range_mm=[min(tracking),max(tracking)],independent_support=len(groups),
        basis='SAME_FONT_PT_SCALE_PHYSICAL_CONTAINER_AND_REVIEWED_SEMANTIC_POLICY')
    return result


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
    moved={intent['subject'] for intent in intents}
    allowed=set(policy.get('movable_kinds',('phone','email','line','ig','address')))
    subjects={intent['subject'] for intent in intents}
    if any(row['render_id'] in subjects and row['kind'] not in allowed for row in facts):
        raise ValueError('Requested protected role is outside approved relative-position policy')
    by_render={row['render_id']:row for row in facts}
    if any(by_render[intent['subject']]['owner_port']!=by_render[intent['object']]['owner_port'] for intent in intents):
        raise ValueError('Cross-owner relative editing needs separately supported group correspondence')
    roles={role['key']:deepcopy(role) for role in profile['roles']};missing=[];options=[]
    people,companies,compiled_logos=graph.compile()
    logos=deepcopy(logos if logos is not None else compiled_logos)
    company_entities={row['id']:row for row in graph.data['companies']}
    for fact in facts:
        logo_key=fact['owner_port']+':logo:0'
        if fact['kind']=='company' and logo_key in roles:
            fact['kind']='logo';fact['role_key']=logo_key
    from collections import Counter
    pattern=dict(Counter(fact['owner_port']+':'+fact['kind'] for fact in facts))
    conditioned=next((row for row in profile.get('conditional_geometry',[])
        if row['pattern']==pattern and row['independent_support']>=5),None)
    if conditioned:
        for key,frame in conditioned['frames'].items():
            if key in roles:roles[key]['frame_centre']=deepcopy(frame)
    from .design_assignment import assign_fields
    assignment=assign_fields(profile,facts,policy,lambda fact,key:_font_options(profile,key,width,height,
        fact['value'],policy,fact['semantic_observation']['semantic_type']))
    assigned={row['render_id']:row for row in assignment['assignments']}
    if assignment['status']!='ASSIGNED':missing.append(dict(reason=assignment['status']))
    for fact in facts:
        if fact['render_id'] in assigned:
            fact['input_role_key']=fact['role_key'];fact['role_key']=assigned[fact['render_id']]['source_role_key']
    base_scope='CURRENT_INPUT_PREVIEW_NOT_GLOBAL_TEMPLATE_OR_FORMAL_APPROVAL'

    for fact in facts:
        if fact['role_key'] not in roles:
            missing.append(dict(render_id=fact['render_id'],reason='UNSUPPORTED_ROLE_OR_REPEAT_COUNT'));continue
        if fact['kind']=='logo':
            from .logo_assets import errors as logo_errors
            asset=logos.get(fact['owner_port']);entity=company_entities.get(fact['entity_id'],{})
            if (not asset or entity.get('logo_id')!=asset.get('id') or asset.get('company')!=fact['value']
                    or asset.get('design_entity_ref')!=fact['entity_id']
                    or abs(asset.get('width_mm',0)-width)>1e-5 or abs(asset.get('height_mm',0)-height)>1e-5
                    or logo_errors(asset)):
                missing.append(dict(render_id=fact['render_id'],reason='EXACT_WHOLE_COMPANY_SIZE_LOGO_REQUIRED'));continue
            frame=roles[fact['role_key']]['frame_centre']
            configuration=dict(id=digest([asset,frame,width,height]),logo=deepcopy(asset),font_asset=None,
                width_mm=frame[2]*width,height_mm=frame[3]*height,scale=1.,tracking_mm=0.,support=roles[fact['role_key']]['support'],
                size_admission='OBSERVED_EXACT_SIZE')
            rows=[configuration]
        else:rows=assigned.get(fact['render_id'],{}).get('options',[])
        if not rows:missing.append(dict(render_id=fact['render_id'],reason='SOURCE_JOINT_TYPOGRAPHY_OR_FONT_IDENTITY_UNKNOWN'))
        options.append(rows)
    base=dict(version=VERSION,family_id=profile['family_id'],input_digest=digest(graph.data),
        policy_version=policy['version'],intents=intents,field_refs=[{k:v for k,v in f.items() if k!='value'} for f in facts],
        assignment={k:v for k,v in assignment.items() if k!='assignments'},
        assigned_containers=[{k:v for k,v in row.items() if k!='options'} for row in assignment['assignments']],
        actual_template_objects_created=0,scope='CURRENT_INPUT_PREVIEW_NOT_GLOBAL_TEMPLATE_OR_FORMAL_APPROVAL')
    if missing:
        return dict(base,status='SOURCE_EVIDENCE_REQUIRED',issues=missing,candidates=[],searched=0,
                    complete_search=False)
    represented={fact['owner_port'] for fact in facts if fact['kind']=='logo'}
    if any(company['logo_id'] and 'c'+str(i+1) not in represented for i,company in enumerate(graph.data['companies'])):
        return dict(base,status='ASSET_ADAPTATION_REQUIRED',issues=[dict(reason='SELECTED_LOGO_NOT_REPRESENTED_BY_FAMILY')],
                    candidates=[],searched=0,complete_search=False)
    joint_counts=dict(Counter(fact['owner_port']+':'+fact['kind'] for fact in facts))
    observed_patterns=[row['pattern'] for row in profile['grammar'].get('observed_joint_counts',[])]
    style_admission='OBSERVED_JOINT_ROLE_COUNTS' if not observed_patterns or joint_counts in observed_patterns else 'UNVERIFIED_JOINT_ROLE_COMBINATION_PREVIEW_ONLY'
    combinations=math.prod(len(row) for row in options);candidates=[];attempts=[]
    for selected in islice(product(*options),budget):
        solver=kiwi.Solver();variables={};slots=[];measurements=[];failure=None
        try:
            for fact,configuration in zip(facts,selected):
                role=roles[fact['role_key']];frame=role['frame_centre'];asset=configuration['font_asset']
                if fact['kind']=='logo':
                    rid=fact['render_id'];w,h=configuration['width_mm'],configuration['height_mm']
                    x,y=kiwi.Variable(rid+'-x'),kiwi.Variable(rid+'-y');variables[rid]=(x,y,w,h)
                    for constraint in (x>=margin,y>=margin,x+w<=width-margin,y+h<=height-margin):solver.addConstraint(constraint)
                    solver.addConstraint((x==frame[0]*width)|kiwi.strength.strong)
                    solver.addConstraint((y==frame[1]*height)|kiwi.strength.strong)
                    slots.append(Slot('logo',fact['owner_port'],Rect(frame[0]*width,frame[1]*height,w,h),id=rid))
                    measurements.append(dict(render_id=rid,text=fact['value'],scale=1.,logo=configuration['logo'],
                        width_mm=w,height_mm=h,configuration_id=configuration['id']))
                    continue
                family=asset['families'][0];style=(asset.get('styles') or [''])[0]
                label=configuration['label_binding']
                if label.get('status')!='CONFIRMED' or label.get('kind') not in ('NO_FIXED_LABEL','DYNAMIC_PREFIX','SEPARATE_STATIC_LABEL'):
                    failure='LABEL_BINDING_UNKNOWN';break
                if label.get('kind')=='DYNAMIC_PREFIX':
                    prefix=label.get('prefix')
                    if not isinstance(prefix,str) or len(prefix)>128:failure='LABEL_PREFIX_UNVERIFIED';break
                    display=prefix+fact['value']
                else:display=fact['value']
                configuration=_adapt_distribution(profile,fact['role_key'],configuration,display,fact['kind'])
                w,h=configuration['width_mm'],configuration['height_mm']
                flow=configuration.get('text_flow')
                if flow:
                    from .design_text_flow import shape_flow
                    shaped=shape_flow(display,family,configuration['size_pt'],configuration['scale'],w,asset,
                        style,configuration['tracking_mm'],flow,fact['kind'])
                    tw,th=shaped['width_mm']/configuration['scale'],shaped['height_mm']
                    baseline_offset=(h-th)/2+shaped['first_baseline_mm'] if shaped['first_baseline_mm'] is not None else None
                else:
                    tw,th,errors=text_geometry(family,configuration['size_pt'],display,style,asset,configuration['tracking_mm'])
                    if errors:failure='FONT_MEASUREMENT_UNVERIFIED';break
                    from .render import prepared_text_metrics
                    _,ink,factor=prepared_text_metrics(display,family,configuration['size_pt'],style,asset,configuration['tracking_mm'])
                    baseline_offset=(h-ink['height']*factor)/2+ink['ascent']*factor
                if tw*configuration['scale']>w+1e-7 or th>h+1e-7:failure='MEASURED_TEXT_EXCEEDS_JOINT_CONFIGURATION';break
                rid=fact['render_id'];x,y=kiwi.Variable(rid+'-x'),kiwi.Variable(rid+'-y');variables[rid]=(x,y,w,h)
                for constraint in (x>=margin,y>=margin,x+w<=width-margin,y+h<=height-margin):solver.addConstraint(constraint)
                source_baselines=any(row.get('residuals',{}).get('baseline_delta',{}).get('support',0)>=5
                    for row in profile.get('relations',[]))
                anchor_strength=kiwi.strength.medium if source_baselines else kiwi.strength.strong
                solver.addConstraint((x==frame[0]*width)|anchor_strength)
                solver.addConstraint((y==frame[1]*height)|anchor_strength)
                slots.append(Slot(fact['kind'],fact['owner_port'],Rect(frame[0]*width,frame[1]*height,w,h),
                    index=fact['index'],font=family,font_style=style,size_pt=configuration['size_pt'],
                    min_scale=min(1.,configuration['scale']),font_asset=deepcopy(asset),id=rid,tracking_mm=configuration['tracking_mm'],
                    align=configuration.get('align','left'),distribution_approval=deepcopy(configuration.get('distribution')) if isinstance(configuration.get('distribution'),dict) else None,
                    tracking_min_mm=configuration['tracking_mm'],tracking_max_mm=configuration['tracking_mm'],text_flow=deepcopy(flow)))
                measurements.append(dict(render_id=rid,text=display,width_mm=tw,height_mm=th,
                    scale=configuration['scale'],configuration_id=configuration['id'],baseline_offset_mm=baseline_offset))
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
                    if af[0]+af[2]<=bf[0]+1e-9:hgraph.add_edge(aid,bid)
                    elif bf[0]+bf[2]<=af[0]+1e-9:hgraph.add_edge(bid,aid)
            if not nx.is_directed_acyclic_graph(vgraph) or not nx.is_directed_acyclic_graph(hgraph):
                raise ValueError('Intent contradicts protected relative structure')
            for a,b in sorted(hgraph.edges):
                ax,ay,aw,ah=variables[a];bx,by,bw,bh=variables[b];solver.addConstraint(ax+aw<=bx)
            for a,b in sorted(vgraph.edges):
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
            # Source distributions are preferences, not guessed print tolerances.
            # Explicitly moved fields and all hard ownership/topology gates win.
            measured={row['render_id']:row for row in measurements};role_ids={row['role_key']:row['render_id'] for row in facts}
            applied=[]
            for relation in profile.get('relations',[]):
                a=role_ids.get(relation['left']);b=role_ids.get(relation['right'])
                if not a or not b or a in moved or b in moved or relation['support']<5:continue
                ax,ay,aw,ah=variables[a];bx,by,bw,bh=variables[b]
                expressions=dict(left_delta=(bx-ax,width),right_delta=(bx+bw-ax-aw,width),
                    centre_delta=(bx+bw/2-ax-aw/2,width),vertical_gap=(by-ay-ah,height),horizontal_gap=(bx-ax-aw,width))
                ba=measured[a].get('baseline_offset_mm');bb=measured[b].get('baseline_offset_mm')
                if ba is not None and bb is not None:expressions['baseline_delta']=(by+bb-ay-ba,height)
                for metric,(expression,dimension) in expressions.items():
                    distribution=relation['residuals'].get(metric,{})
                    if distribution.get('centre') is None or distribution.get('support',0)<5:continue
                    strength=kiwi.strength.strong if metric=='baseline_delta' else kiwi.strength.medium
                    solver.addConstraint((expression==distribution['centre']*dimension)|strength)
                    applied.append(dict(left=a,right=b,metric=metric,independent_support=distribution['support'],
                        source_refs=relation.get('source_refs',[]),strength='SOFT_BASELINE_STRONG_OTHER_MEDIUM_BELOW_HARD_INTENT'))
            from .design_object_spacing import apply_object_spacing
            apply_object_spacing(solver,variables,facts,profile.get('object_spacing_rules',[]),width,height)
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
            items=[Placed(slot,measurement['text'],measurement['scale'],slot.tracking_mm,measurement.get('logo'))
                   for slot,measurement in zip(slots,measurements)]
            candidate=Candidate(template,items,['新學習實例尚待正式來源／模型資格核實'],
                score=-sum(abs(slot.rect.x-roles[fact['role_key']]['frame_centre'][0]*width)
                           +abs(slot.rect.y-roles[fact['role_key']]['frame_centre'][1]*height)
                           for slot,fact in zip(slots,facts)),
                diagnostics=[dict(code='UNPUBLISHED',severity='BLOCK')],
                dependency_stamp=layout_dependency(template,logos))
            pin_inputs(candidate,people,companies,logos)
            candidate.risk_context['design_style_admission']=style_admission
            style_reference={}
            for fact,config in zip(facts,selected):
                if fact['kind']=='logo':continue
                rows=[]
                for data in profile['data_requirement_profiles']:
                    for sample in data['presentation_evidence']:
                        joint=sample['joint'];dimensions=sample['dimensions_mm']
                        if (sample['role_key']==fact['role_key'] and joint['source_pt']
                                and joint['horizontal_scale'] is not None and joint['tracking_mm'] is not None
                                and font_identity(sample['source_font_ref'])==font_identity(config['font_asset'])):
                            rows.append([joint['source_pt']/dimensions[1],joint['horizontal_scale'],
                                joint['tracking_mm']/(joint['source_pt']*25.4/72),
                                joint['frame_width_mm']/dimensions[0],joint['frame_height_mm']/dimensions[1]])
                style_reference[fact['render_id']]=rows
            candidate.risk_context['design_joint_style_reference']=style_reference
            candidate.risk_context['design_size_admission']=('SOURCE_OR_LEARNED_DOMAIN' if all(
                config.get('size_admission') in ('OBSERVED_EXACT_SIZE','LEARNED_JOINT_DOMAIN') for config in selected)
                else 'UNVERIFIED_SIZE_PREVIEW_ONLY')
            candidate.risk_context['design_geometry_basis']=dict(
                kind='SHARED_CONDITIONAL_ROLE_PATTERN' if conditioned else 'GROUP_BALANCED_FAMILY_DEFAULT',
                pattern=pattern,source_refs=conditioned['source_refs'] if conditioned else [],soft_relations=applied)
            candidate.risk_context['design_label_bindings']={fact['render_id']:deepcopy(config.get('label_binding'))
                for fact,config in zip(facts,selected) if fact['kind']!='logo'}
            candidate.risk_context['design_relations']=[dict(subject=a,relation=relation,object=b)
                for relation,edges in [('ABOVE',vgraph.edges),('LEFT_OF',hgraph.edges)] for a,b in sorted(edges)]
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

"""Distinct authored synthetic control/acceptance layouts; no production accuracy claim."""
import copy,xml.etree.ElementTree as ET
from dataclasses import asdict
from template_ai.model import Slot,Rect,Template
from template_ai.importer import import_file
from template_ai.customers import CustomerStore
from template_ai.quality_gold import QualityGold,DOMAINS,USE,DIAGNOSTIC_USE
from template_ai.quality_sets import QualitySets
from template_ai.quality_groups import QualityGroups


def group(case,label,portrait=False,multi=False):
    library=case.library;store=case.store;customers=CustomerStore(library);gold_service=QualityGold(library)
    width,height=(60,95) if portrait else (110,70);golds=[];sources=[];works=[];targets=[];gold_requests=[]
    role='HOLDOUT' if portrait else 'VALIDATION';rights=dict(basis='OWNED',reference='Authored synthetic safety state machine; not calibrated production or native Illustrator',use=USE if portrait else DIAGNOSTIC_USE)
    def record(source,name,payload,observations,target,logo_prefix=''):
        work=library.create_artwork(source['id'],name,payload)
        saved=store.save_facts(work['id'],observations,0,work['revision']);store.confirm_facts(work['id'],[o['id'] for o in observations],saved['revision'],saved['pins'],store.source_proof(work['id']),'Synthetic author',True)
        kwargs=dict(mapping_truth=dict(customer_id=target['id'],style_id=target['styles'][0]['id'],review_reason='Explicit authored expected catalog target, not inferred from prediction'))
        if any(o['classification']=='LOGO' for o in observations):kwargs['logo_truth']={'observation-logo':dict(root_id=logo_prefix+'brand-logo',component_ids=[logo_prefix+'brand-mark',logo_prefix+'brand-label'],text_component_ids=[logo_prefix+'brand-label'],review_reason='Authored complete vector and text group',original_correspondence_confirmed=True)}
        gold_requests.append((work,kwargs));return work
    for index in (1,2):
        code=label+'-'+str(index);path=case.root/(code+'.svg')
        fields=[('name','p1','Name: Synthetic '+code),('title','p1','Title: Designer'),('phone','p1','Phone: +1 202 555 013'+str(index)),('email','p1','Email: '+code+'@example.test'),('address','p1','Address: '+str(index)+' Test Road'),('line','p1','LINE: '+code),('ig','p1','IG: '+code)]
        if index==2:fields.append(('company','c1','Company: '+label+' Ltd'))
        slots=[];observations=[];text=''
        for i,(kind,owner,value) in enumerate(fields):
            x,y=(6,18+i*8) if portrait else (6+(i%2)*52,8+(i//2)*12)
            rect=Rect(x,y-3,45,5);identity='field-'+str(i)
            slots.append(asdict(Slot(kind,owner,rect,id=identity,size_pt=8)))
            observations.append(dict(id='observation-'+str(i),slot_id=identity,text=value,region=asdict(rect),object_type='TEXT',classification='FIELD'))
            text+=f'<text id="text-{i}" x="{x}" y="{y}" font-size="2">{value}</text>'
        logo=''
        if index==1:
            cx,cy,tx,ty=(45,7,35,13) if portrait else (95,56,87,65)
            logo=f'<g id="brand-logo"><circle id="brand-mark" cx="{cx}" cy="{cy}" r="3"/><text id="brand-label" x="{tx}" y="{ty}" font-size="1.5">Brand {label}</text></g>'
            rect=Rect(34,2,25,13) if portrait else Rect(86,51,23,18)
            slots.append(asdict(Slot('logo','c1',rect,id='logo',size_pt=8)));observations.append(dict(id='observation-logo',slot_id='logo',text='Authored complete '+label+' brand',region=asdict(rect),object_type='LOGO_PART',classification='LOGO'))
        path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" viewBox="0 0 {width} {height}"><rect id="card" width="{width}" height="{height}" fill="white"/><g fill="black" font-family="sans-serif">'+text+logo+'</g></svg>')
        source=library.add_source(path,import_file(path,library.assets));sources.append(source)
        template=Template('Authored '+code,width,height,[Slot('name','p1',Rect(5,5,40,5))]);library.save_template(template)
        customer=customers.create(code,'Authored '+code,[dict(owner='p1',kind='name',value='Synthetic '+code)],template.id,True);targets.append(customer)
        work=record(source,'Authored '+code,dict(crop=dict(x=0,y=0,w=width,h=height),work_width=width,work_height=height,slots=slots,company_bindings={'p1':['c1']},visual_confirmed=True),observations,customer);works.append(work)
    if multi:
        canvas=ET.Element('{http://www.w3.org/2000/svg}svg',dict(width=str(2*width+10)+'mm',height=str(height)+'mm',viewBox=f'0 0 {2*width+10} {height}'))
        for index,source in enumerate(sources[:2]):
            wrapper=ET.SubElement(canvas,'{http://www.w3.org/2000/svg}g',dict(transform=f'translate({index*(width+10)},0)'))
            for child in ET.parse(source['original_path']).getroot():
                child=copy.deepcopy(child)
                for node in child.iter():
                    if node.get('id'):node.set('id','multi-'+str(index)+'-'+node.get('id'))
                wrapper.append(child)
        path=case.root/(label+'-multi.svg');ET.ElementTree(canvas).write(path,encoding='unicode')
        source=library.add_source(path,import_file(path,library.assets));sources.append(source)
        for index,original in enumerate(works):
            dx=index*(width+10);payload=copy.deepcopy(original['payload']);payload['crop']['x']=dx
            observations=copy.deepcopy(store.facts(original['id'])['observations'])
            for observation in observations:observation['region']['x']+=dx
            record(source,'Authored real multi-panel '+str(index),payload,observations,targets[index],'multi-'+str(index)+'-')
    for work,kwargs in gold_requests:
        golds.append(gold_service.confirm(gold_service.plan(work['id'],rights,{domain:'MANUALLY_VERIFIED' for domain in DOMAINS},'Authored labels/coordinates established before inference','Distinct synthetic layout with explicit original comparison',**kwargs),'Synthetic author',True))
    groups=QualityGroups(library)
    for source in sources[1:]:groups.confirm_link(groups.link_plan('CONTENT:'+sources[0]['hash'],'CONTENT:'+source['hash'],'SAME_DESIGN_FAMILY','Known related authored designs within this synthetic group','Distinct groups use different dimensions/orientation/column design; safety branch only'),'Synthetic author',True)
    sets=QualitySets(library);preview=sets.plan('Authored '+label+' safety scope',[g['id'] for g in golds],True,True,'Known related variants stay together; separate synthetic layout group, no production generalization',evaluation_role=role)
    case.assertFalse(preview['errors'],preview['errors'])
    dataset=sets.create(preview,'Synthetic author',True)
    return dict(dataset=dataset,customer_ids=[c['id'] for c in targets],sources=sources)


def actual_chain(case):
    from template_ai.quality_repair_gates import STAGES
    from template_ai.quality_reports import QualityReports
    from template_ai.quality_repair_releases import QualityRepairReleases
    case.prepare(full_chain=True)
    root=case.run_stage(case.gates.protocol_plan(case.candidate['id'],STAGES[0],case.dataset_id,case.policy_id,'Actual root correction first'))
    case.assertTrue(root['plan']['passed'],root['plan']['blockers'])
    controls=case.run_stage(case.gates.protocol_plan(case.candidate['id'],STAGES[1],case.controls['dataset']['id'],case.policy_id,'Unrelated two-column actual phone/person/logo/mm/customer and multi-panel controls',root['id']))
    case.assertTrue(controls['plan']['passed'],controls['plan']['blockers'])
    final=case.run_stage(case.gates.protocol_plan(case.candidate['id'],STAGES[2],case.independent['dataset']['id'],case.policy_id,'New authored portrait HOLDOUT, software state-machine safety only',controls['id']))
    case.assertTrue(final['plan']['passed'],final['plan']['blockers']);case.assertTrue(final['plan']['independence_claim'])
    decision=QualityReports(case.library).decide(final['plan']['report_id'],'Reviewer','Explicit intentionally lenient authored synthetic safety test; not production accuracy',True)
    release=QualityRepairReleases(case.library);impact=release.confirm_impact(release.impact_plan(case.candidate['id']),'Reviewer','Inspect known impact and explicitly retain unknown history; no pending confirmed highrisk',True)
    plan=release.plan(decision['id'],0,gate_id=final['id'],impact_review_id=impact['id'])
    installed=release.confirm(plan,'Reviewer','Exact candidate passed ordered actual safety checks, remains human-review source recommendation',True)
    case.assertEqual(release.pin()['event_id'],installed['event']['id']);case.assertEqual(release.pin()['pipeline_id'],case.candidate['plan']['pipeline_id'])
    return dict(root=root,controls=controls,final=final,decision=decision,release=release,impact=impact,installed=installed)

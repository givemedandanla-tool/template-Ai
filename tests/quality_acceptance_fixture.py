"""Authored SVG acceptance-branch fixture, not production model calibration."""
from dataclasses import asdict
from types import SimpleNamespace
from template_ai.model import Slot,Rect,Template,new_id
from template_ai.importer import import_file
from template_ai.customers import CustomerStore
from template_ai.quality_gold import QualityGold,DOMAINS,USE
from template_ai.quality_sets import QualitySets
from template_ai.quality_policy import QualityPolicies
from template_ai.quality_pipeline import QualityPipelines
from template_ai.quality_protocol import QualityProtocols
from template_ai.quality_groups import QualityGroups
from template_ai.quality_jobs import EvaluationJobs,run_evaluation


def actual_positive_pair(case):
    library=case.library;store=case.store;customers=CustomerStore(library);golds=[];customer_ids=[];sources=[]
    for index in (1,2):
        code='authored-'+str(index);path=case.root/(code+'.svg')
        fields=[('name','p1','Name: Synthetic Person '+str(index)),('title','p1','Title: Designer'),('phone','p1','Phone: +1 202 555 010'+str(index)),('email','p1','Email: qa'+str(index)+'@example.test'),('address','p1','Address: '+str(index)+' Test Road'),('line','p1','LINE: synthetic'+str(index)),('ig','p1','IG: synthetic'+str(index))]
        if index==2:fields.append(('company','c1','Company: Synthetic Two Ltd'))
        text=''.join(f'<text id="text-{i}" x="6" y="{6+i*5}" font-size="3">{value}</text>' for i,(_,_,value) in enumerate(fields))
        logo='<g id="brand-logo"><circle id="brand-mark" cx="79" cy="12" r="4"/><text id="brand-label" x="74" y="19" font-size="2">Brand One</text></g>' if index==1 else ''
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 90 54"><rect id="card" width="90" height="54" fill="white"/><g fill="black" font-family="sans-serif">'+text+logo+'</g></svg>')
        source=library.add_source(path,import_file(path,library.assets));sources.append(source)
        slots=[];observations=[]
        for i,(kind,owner,value) in enumerate(fields):
            identity='field-'+str(i);rect=Rect(6,3+i*5,60,4);slots.append(asdict(Slot(kind,owner,rect,id=identity,size_pt=8)))
            observations.append(dict(id='observation-'+str(i),slot_id=identity,text=value,region=asdict(rect),object_type='TEXT',classification='FIELD'))
        if index==1:
            rect=Rect(73,7,15,15);slots.append(asdict(Slot('logo','c1',rect,id='logo',size_pt=8)));observations.append(dict(id='observation-logo',slot_id='logo',text='Authored complete Brand One Logo',region=asdict(rect),object_type='LOGO_PART',classification='LOGO'))
        work=library.create_artwork(source['id'],'Authored synthetic card '+str(index),dict(crop=dict(x=0,y=0,w=90,h=54),work_width=90,work_height=54,slots=slots,company_bindings={'p1':['c1']},visual_confirmed=True))
        saved=store.save_facts(work['id'],observations,0,work['revision']);store.confirm_facts(work['id'],[o['id'] for o in observations],saved['revision'],saved['pins'],store.source_proof(work['id']),'Synthetic author',True)
        template=Template('Existing synthetic catalog '+str(index),90,54,[Slot('name','p1',Rect(5,5,40,5))]);library.save_template(template)
        customer=customers.create(code,'Synthetic catalog '+str(index),[dict(owner='p1',kind='name',value='Synthetic Person '+str(index))],template.id,True);customer_ids.append(customer['id'])
        kwargs=dict(mapping_truth=dict(customer_id=customer['id'],style_id=customer['styles'][0]['id'],review_reason='Independent authored fixture expected exact catalog target'))
        if index==1:kwargs['logo_truth']={'observation-logo':dict(root_id='brand-logo',component_ids=['brand-mark','brand-label'],text_component_ids=['brand-label'],review_reason='Authored SVG complete circle and text; not native Illustrator certification',original_correspondence_confirmed=True)}
        gold=QualityGold(library);golds.append(gold.confirm(gold.plan(work['id'],dict(basis='OWNED',reference='Authored synthetic local software safety fixture only',use=USE),{domain:'MANUALLY_VERIFIED' for domain in DOMAINS},'Expected labels and boxes authored before inference','Exact authored SVG element/physical coordinates',**kwargs),'Synthetic author',True))
    # Both synthetic layouts deliberately share one authored design family.
    groups=QualityGroups(library);groups.confirm_link(groups.link_plan('CONTENT:'+sources[0]['hash'],'CONTENT:'+sources[1]['hash'],'SAME_DESIGN_FAMILY','Shared synthetic authored family, not two independent designs','Fixture source generation'),'Synthetic author',True)
    sets=QualitySets(library);dataset=sets.create(sets.plan('Authored one-family software safety scope',[g['id'] for g in golds],True,True,'One explicitly related group; no training sources'),'Synthetic author',True)
    thresholds={d:dict(minimum_independent_groups=1,minimum_gold_objects=1,minimum_precision=0,minimum_recall=0,maximum_group_failure_rate=1) for d in DOMAINS}
    thresholds['physical_size']=dict(minimum_independent_groups=1,minimum_gold_objects=1,maximum_group_failure_rate=1,maximum_absolute_error_mm=.1)
    from template_ai.model import KINDS
    thresholds['field_types']['required_classes']=list(KINDS)
    policies=QualityPolicies(library);policy=policies.approve(policies.plan('EXPLICIT SYNTHETIC ACCEPTANCE-BRANCH SAFETY TEST',thresholds,.05,.95,'Intentionally lenient synthetic thresholds test state transitions, not production model quality','No real-world calibration or native Illustrator/hardware claim','AUTHORIZED_LOCAL_QUALITY_ACCEPTANCE'),'Synthetic author',True)
    pipelines=QualityPipelines(library);config=dict(code_pattern=r'(?P<code>.+)',maximum_size_error_mm=.1,customer_ids=customer_ids)
    sides={side:pipelines.freeze('Actual authored '+side,None,'Synthetic author',True,mapping_config=config,rule_versions=[])['id'] for side in ('BASELINE','CANDIDATE')}
    protocols=QualityProtocols(library);protocol=protocols.freeze(protocols.plan('Actual acceptance-branch pair',dataset['id'],policy['id'],sides,'Software decision/withdraw/rollback safety only'),'Synthetic author',True)
    service=EvaluationJobs(library);jobs=service.create_pair(protocol['id'],'Synthetic author',True)
    for job in jobs.values():
        claimed=service.claim(job['id'],job['revision'],True);done=run_evaluation(library.root,job['id'],claimed['owner_token'])
        result=store.get('QUALITY_EVAL_RESULT',done['result_id'])
        if not result['quality_pass']:raise AssertionError(str(dict(gate=result['quality_gate'],critical=result['critical_errors'],unknown=result['unmeasured_domains'],statistics=result['statistics'])))
    return dict(protocol=protocol,dataset=dataset,jobs=jobs,sources=sources)

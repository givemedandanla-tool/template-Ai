"""Generate an isolated synthetic corpus and run the real local learning core.

No customer work is read. No network or upload is used. The specified directory
must be new, so this can never train into an existing customer database.
"""
from copy import deepcopy
from dataclasses import asdict
import argparse
import json
from pathlib import Path
import sys
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def choose_font():
    import os
    candidates=[Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    if sys.platform=='win32':
        root=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts'
        candidates=[root/name for name in ('arial.ttf','segoeui.ttf','calibri.ttf')]+candidates
    return next((path for path in candidates if path.is_file()),None)


def run(directory,font_path=None,*,progress=lambda message:None):
    from PySide6.QtWidgets import QApplication
    from template_ai.storage import Library
    from template_ai.fonts import FontManager
    from template_ai.demo import demo_template
    from template_ai.importer import import_file
    from template_ai.model import Rect
    from template_ai.training_store import TrainingStore
    from template_ai.design_source_binding import SourceTypographyReview
    from template_ai.design_learning import CrossWorkLearning,USE
    from template_ai.design_evaluation import DesignEvaluation,check_layout
    from template_ai.design_jobs import DesignJobs,run_design_job
    from template_ai.design_session import DesignSessions
    from template_ai.input_graph import InputGraph
    from template_ai.render import render_image
    from template_ai.background import file_digest
    from template_ai.recovery_diagnostics import shareable_report,issue

    app=QApplication.instance() or QApplication([])
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=False)
    font_path=Path(font_path or choose_font() or '')
    if not font_path.is_file():raise ValueError('No supported local test font;specify --font with an installed regular TTF/OTF')
    sources_dir=directory/'authored-sources';sources_dir.mkdir()
    library=Library(directory/'isolated-data');manager=FontManager(library)
    result=dict(schema='LOCAL_SYNTHETIC_LEARNING_ACCEPTANCE_V1',status='RUNNING',customer_artwork_read=False,local_font_read=True,
        network_or_upload_used=False,production_qualification='NOT_GRANTED_SYNTHETIC_ONLY',
        independence_scope='CONTROLLED_SYNTHETIC_EXPERIMENTAL_UNITS_NOT_REAL_DESIGN_LINEAGE_PROOF')
    try:
        asset=manager.import_font(font_path,True)
        store=TrainingStore(library);reviewer=SourceTypographyReview(library);learning=CrossWorkLearning(library)
        roles={};cases=[];source_digests={};sample_metadata={}
        for number in range(22):
            family=number%2;seed=number//2;width=90.+(seed%3)*5;height=54.
            role='TRAIN' if number<12 else 'VALIDATION' if number<18 else 'HOLDOUT'
            template=demo_template();template.width_mm=width
            texts=[['Alex Example','Jordan Example','Casey Example','Robin Example','Taylor Example','Morgan Example'][seed%6],
                   ['Designer','Senior Designer','Lead Designer','Studio Lead','Visual Designer','Art Director'][seed%6],
                   '+1 202 555 '+format(100+seed,'04d'),
                   ['a','alex','jordan','longer.name','very.long.name','short'][seed%6]+'@example.test']
            if role!='TRAIN':texts[0]=('Avery Example' if role=='HOLDOUT' else 'Jamie Example')+' '+str(seed)
            nodes=[];observations=[]
            for index,(slot,value) in enumerate(zip(template.slots,texts)):
                slot.font=asset['families'][0];slot.font_asset=deepcopy(asset)
                slot.rect.x*=width/90;slot.rect.w*=width/90;slot.size_pt*=width/90
                if family:slot.rect.y={'name':36.,'title':25.,'phone':15.,'email':5.}[slot.kind]
                baseline=slot.rect.y+slot.rect.h*.75
                nodes.append('<text id="field'+str(index)+'" x="'+str(slot.rect.x)+'" y="'+str(baseline)+'" font-size="'+str(slot.size_pt*25.4/72)+'">'+escape(value)+'</text>')
                observations.append(dict(id='known-field-'+str(index),slot_id=slot.id,text=value,object_type='TEXT',classification='FIELD',region=asdict(slot.rect)))
            path=sources_dir/('case-'+str(number)+'.svg')
            path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="'+str(width)+'mm" height="54mm" viewBox="0 0 '+str(width)+' 54"><rect width="100%" height="100%" fill="white"/><g font-family="'+escape(asset['families'][0],{'"':'&quot;'})+'">'+''.join(nodes)+'</g></svg>',encoding='utf-8')
            source_digests[str(number)]=file_digest(path)
            source=library.add_source(path,import_file(path,library.assets))
            work=library.create_artwork(source['id'],'Controlled synthetic design '+str(number),dict(crop=asdict(Rect(0,0,width,height)),work_width=width,work_height=height,slots=[asdict(s) for s in template.slots],visual_confirmed=True))
            facts=store.save_facts(work['id'],observations,0,work['revision'])
            store.confirm_facts(work['id'],[row['id'] for row in observations],facts['revision'],facts['pins'],store.source_proof(work['id']),'SYNTHETIC_KNOWN_TRUTH',True)
            rights=dict(basis='OWNED',reference='Generated anonymous source and known construction truth',use='GEOMETRY_TRAINING_LOCAL')
            sample=store.approve_sample(store.sample_approval_plan(work['id'],rights),store.source_proof(work['id']),'SYNTHETIC_KNOWN_TRUTH',True)
            original=store._design_observation_document(work['id'])['original_text_evidence']
            runs={row['source_locator'].get('object_id'):row for row in original['runs']}
            for index,slot in enumerate(template.slots):
                review=dict(source_identity_confirmed=True,basis='Generated exact source/font/units;not real user font proof',
                    horizontal_scale=1.,tracking=0.,word_spacing=0.,parameter_measurement_refs=['known generator parameters'],source_alignment='left',
                    label_binding=dict(status='CONFIRMED',kind='NO_FIXED_LABEL',evidence_refs=['known construction']))
                reviewer.confirm(reviewer.plan(work['id'],slot.id,runs['field'+str(index)]['id'],asset,review),'SYNTHETIC_KNOWN_TRUTH',True)
            roles[sample['id']]=role;sample_metadata[sample['id']]=dict(family=family,texts=texts,width=width)
            if role in ('VALIDATION','HOLDOUT'):
                graph=InputGraph.from_legacy([dict(name=texts[0],title=texts[1],phone=texts[2],email=texts[3])],[])
                cases.append(dict(id='case-'+str(number),sample_id=sample['id'],input_graph=graph.data,width_mm=90. if role=='VALIDATION' else width,height_mm=height,
                    truth_refs=['Frozen generated input values and independently checked layout invariants']))
            progress(dict(stage='AUTHORED_SOURCE',completed=number+1,total=22))
        dataset=learning.freeze_dataset(learning.dataset_plan(roles,dict(use=USE,actor='SYNTHETIC_KNOWN_TRUTH',basis='Owned isolated synthetic rule-learning self-test')),'SYNTHETIC_KNOWN_TRUTH',True)
        model=learning.train(dataset['id'],'SYNTHETIC_KNOWN_TRUTH',approved=True)
        families=model['artifact']['profile_model']['families']
        if len(families)!=2:raise AssertionError('Expected two shared structural families,got '+str(len(families)))
        policy=dict(version='synthetic-known-layout-1',candidate_budget=32,safe_margin_mm=0.,production=False,enable_joint_prediction=True,
                    approved=True,basis='Owned synthetic known-parameter layout self-test')
        evaluation=DesignEvaluation(library);jobs=DesignJobs(library)
        job=evaluation.create(model['id'],cases,policy,'SYNTHETIC_KNOWN_TRUTH',origin='AUTHORED_SYNTHETIC',review_refs=['Controlled experimental units,not real-design independence'],approved=True)
        claimed=jobs.claim(job['id'],job['revision']);run_design_job(library.root,job['id'],claimed['owner']['token'])
        job=jobs.current(job['id']);rows=jobs.results(job['id'])
        if job['phase']!='COMPLETE' or len(rows)!=len(cases):raise AssertionError('Actual evaluation did not complete')
        bad=[row['case_id'] for row in rows if row['learned']['status']!='FEASIBLE' or row['learned']['integrity']['status']!='PASS']
        if bad:raise AssertionError('Actual unseen-input synthesis/integrity failed: '+repr(bad))
        from template_ai.design_capacity import LocalCapacityCalibration,capacity_advice
        calibration=LocalCapacityCalibration(library)
        for index,row in enumerate(rows):
            if row['role']=='VALIDATION':
                calibration.review_case(job['id'],index,True,'SYNTHETIC_KNOWN_TRUTH',
                    'Controlled font hierarchy/frames and independent data/overflow checker;not a real aesthetic label',True)
        capacity=calibration.from_evaluation(job['id'],dict(version='synthetic-capacity-1',minimum_independent_groups=5,
            minimum_success_lower_bound=.5,alpha=.05,bin_widths=[32.,10.]*4,maximum_support_distance=.25),'SYNTHETIC_KNOWN_TRUTH',True)
        capacity_model=capacity['artifact']
        eligible=next((cell for cell in capacity_model['cells'] if cell['status']=='VALIDATED_EMPIRICAL_REGION'),None)
        if not eligible:raise AssertionError('Actual reviewed validation outputs did not calibrate a suitable region')
        advice=capacity_advice(capacity_model,eligible['context'],eligible['joint_support'][0])
        if advice['status']!='WITHIN_VALIDATED_EMPIRICAL_REGION':raise AssertionError('Calibrated joint demand was not admitted as advice')
        sessions=DesignSessions(library);case=cases[-1];graph=InputGraph(case['input_graph'])
        session=sessions.create(graph,case['width_mm'],case['height_mm'],'SYNTHETIC_KNOWN_TRUTH',model['id'],policy)
        first=sessions.solve(session['id'],session['revision'])
        second=sessions.solve(session['id'],sessions.current(session['id'])['revision'])
        if first['selected']['id']!=second['selected']['id']:raise AssertionError('Repeated same-input layout changed')
        _,_,candidate=sessions.checked_result(session['id'])
        if check_layout(candidate,graph)['status']!='PASS':raise AssertionError('Independent output/data check failed')
        preview=directory/'synthetic-preview.png'
        if not render_image(candidate,150,preview=True).save(str(preview),'PNG'):raise AssertionError('Actual preview output failed')
        if library.templates():raise AssertionError('Learning incorrectly created one global template per source')
        if any(file_digest(sources_dir/('case-'+key+'.svg'))!=sha for key,sha in source_digests.items()):raise AssertionError('Original source changed')
        public=shareable_report(dict(source_kind='SVG',issues=[issue('FONT_AMBIGUOUS')],private_text='NEVER_EXPORT_THIS',font_path=str(font_path)))
        if 'NEVER_EXPORT_THIS' in json.dumps(public) or str(font_path) in json.dumps(public):raise AssertionError('Diagnostic redaction failed')
        result.update(status='PASS',authored_sources=22,train_sources=12,validation_sources=6,holdout_sources=4,
            shared_families=len(families),global_templates=0,actual_evaluated_cases=len(rows),hard_errors=0,data_integrity=1.,
            stable_repeat=True,source_bytes_unchanged=True,actual_preview_written=True,privacy_projection_pass=True,
            actual_validation_capacity_calibrated=True,maximum_validated_field_count=capacity_model['maximum_validated_field_count'],
            model_weights_unchanged_after_evaluation=learning.checked_model(model['id'])[0]['weights_digest']==model['weights_digest'])
        (directory/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return result
    except Exception as error:
        result.update(status='FAIL',stage_failure_type=type(error).__name__)
        (directory/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        raise
    finally:manager.close();library.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',required=True);parser.add_argument('--font')
    args=parser.parse_args();print(json.dumps(run(args.directory,args.font,progress=lambda value:print(json.dumps(value),flush=True)),ensure_ascii=False))

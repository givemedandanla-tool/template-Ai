from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

from PySide6.QtWidgets import QApplication

from template_ai.background import file_digest
from template_ai.demo import demo_template
from template_ai.design_learning import CrossWorkLearning,USE
from template_ai.design_source_binding import SourceTypographyReview
from template_ai.design_synthesis import synthesize,_font_options
from template_ai.design_evaluation import check_layout
from template_ai.fonts import FontManager
from template_ai.importer import import_file
from template_ai.input_graph import InputGraph
from template_ai.model import Rect
from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.render import render_image

APP=QApplication.instance() or QApplication([])


class CompositeLearningIntegrationTests(unittest.TestCase):
    def test_actual_multisource_training_generates_new_mixed_face_and_static_components(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);library=Library(root/'data');manager=FontManager(library)
            try:
                assets=[manager.import_font('/usr/share/fonts/truetype/dejavu/'+name,True) for name in ('DejaVuSans.ttf','DejaVuSerif.ttf')]
                icon=root/'owned-icon.svg';icon.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M1 1H9V9H1Z"/></svg>')
                store=TrainingStore(library);reviewer=SourceTypographyReview(library);roles={}
                for i in range(6):
                    template=demo_template();name='Alex Example'+str(i);phone='+1 202 555 010'+str(i);values=[name,'Designer',phone,'case'+str(i)+'@example.test']
                    path=root/('owned-'+str(i)+'.svg')
                    path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 90 54"><g font-family="DejaVu Sans"><text id="given" x="8" y="14" font-size="6.35">Alex <tspan id="family" font-family="DejaVu Serif" font-size="4.23333333333333">Example'+str(i)+'</tspan></text><text id="title" x="8" y="24" font-size="3.88055555555556">Designer</text><text id="phone" x="24" y="36" font-size="3.52777777777778">'+phone+'</text><text id="email" x="8" y="45" font-size="3.52777777777778">'+values[3]+'</text><text id="label" x="12" y="35" font-family="DejaVu Serif" font-size="2.82222222222222">TEL</text></g><path d="M8 32H10V34H8Z"/></svg>')
                    source=library.add_source(path,import_file(path,library.assets))
                    work=library.create_artwork(source['id'],'Controlled composite '+str(i),dict(crop=asdict(Rect(0,0,90,54)),work_width=90,work_height=54,slots=[asdict(s) for s in template.slots],visual_confirmed=True))
                    observations=[dict(id='field-'+str(n),slot_id=s.id,text=v,object_type='TEXT',classification='FIELD',region=asdict(s.rect)) for n,(s,v) in enumerate(zip(template.slots,values))]
                    facts=store.save_facts(work['id'],observations,0,work['revision']);store.confirm_facts(work['id'],[r['id'] for r in observations],facts['revision'],facts['pins'],store.source_proof(work['id']),'KNOWN_SYNTHETIC_TRUTH',True)
                    sample=store.approve_sample(store.sample_approval_plan(work['id'],dict(basis='OWNED',reference='Controlled generated scene',use='GEOMETRY_TRAINING_LOCAL')),store.source_proof(work['id']),'KNOWN_SYNTHETIC_TRUTH',True)
                    original=store._design_observation_document(work['id'])['original_text_evidence'];runs={r['source_locator'].get('object_id'):r for r in original['runs']}
                    review=dict(source_identity_confirmed=True,basis='Known authored source/font correspondence;no real-corpus claim',horizontal_scale=1.,tracking=0.,word_spacing=0.,parameter_measurement_refs=['known author parameters'],source_alignment='left',label_binding=dict(status='CONFIRMED',kind='NO_FIXED_LABEL',evidence_refs=['known construction']))
                    spans=[dict(start=0,end=5,source_run_id=runs['given']['id'],font_asset=assets[0],selector=dict(kind='WORD_SLICE',start=0,end=1)),dict(start=5,end=len(name),source_run_id=runs['family']['id'],font_asset=assets[1],selector=dict(kind='WORD_SLICE',start=1,end=None))]
                    reviewer.confirm(reviewer.plan_composite(work['id'],template.slots[0].id,spans,review),'KNOWN_SYNTHETIC_TRUTH',True)
                    for slot,key in zip(template.slots[1:],('title','phone','email')):
                        current=deepcopy(review)
                        if key=='phone':
                            current['label_binding']['kind']='SEPARATE_STATIC_LABEL'
                            current['source_text_flow']=dict(status='HUMAN_CONFIRMED_SOURCE_RULE',break_rule='NO_WRAP',max_lines_observed=1,line_height_factor=1.,alignment='left',evidence_refs=['known composition'],presentation=dict(status='HUMAN_CONFIRMED_SOURCE_RULE',evidence_refs=['known source component frames'],value_frame=[.23,0.,.77,.1],components=[dict(kind='STATIC_TEXT',text='TEL',font_asset=assets[1],source_run_id=runs['label']['id'],pt_ratio=.8,frame=[.06,0.,.12,.08]),dict(kind='SVG_ICON',frame=[0.,.02,.04,.04],asset=dict(path=str(icon),hash=file_digest(icon),semantic_scope='DECORATIVE_FIELD_SYMBOL',source_hash=source['hash'],reviewed_source_association=True,usage_rights=dict(print_export=True)))]))
                        reviewer.confirm(reviewer.plan(work['id'],slot.id,runs[key]['id'],assets[0],current),'KNOWN_SYNTHETIC_TRUTH',True)
                    roles[sample['id']]='TRAIN'
                learning=CrossWorkLearning(library);dataset=learning.freeze_dataset(learning.dataset_plan(roles,dict(use=USE,actor='KNOWN_SYNTHETIC_TRUTH',basis='Controlled composite learning')),'KNOWN_SYNTHETIC_TRUTH',True)
                model=learning.train(dataset['id'],'KNOWN_SYNTHETIC_TRUTH',approved=True)
                profiles=model['artifact']['profile_model']['families'];self.assertEqual(len(profiles),1)
                self.assertEqual(len(_font_options(profiles[0],'p1:phone:0',90,54)),1)
                self.assertEqual(_font_options(profiles[0],'p1:phone:0',90,54)[0]['support'],6)
                graph=InputGraph.from_legacy([dict(name='Jordan New Family',title='Visual Designer',phone='+1 202 555 9999',email='novel@example.test')],[])
                result=synthesize(profiles[0],graph,90,54,dict(approved=True,version='controlled-composite-1',candidate_budget=32,safe_margin_mm=0.))
                self.assertEqual(result['status'],'FEASIBLE_PREVIEW',result.get('attempts'))
                candidate=result['candidates'][0]['candidate'];self.assertEqual(check_layout(candidate,graph)['status'],'PASS')
                self.assertTrue(render_image(candidate,100,preview=True).save(str(root/'new-composite.png'),'PNG'))
                self.assertFalse(library.templates())
                icon.write_text('<svg/>')
                with self.assertRaises(ValueError):learning.checked_model(model['id'])
            finally:manager.close();library.close()

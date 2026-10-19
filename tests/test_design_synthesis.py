from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from PySide6.QtWidgets import QApplication

from template_ai.storage import Library
from template_ai.fonts import FontManager
from template_ai.demo import demo_template
from template_ai.input_graph import InputGraph
from template_ai.design_family import train_families
from template_ai.design_profiles import learn_profiles
from template_ai.design_synthesis import synthesize,input_facts
from authored_font_fixture import bind_authored_fonts
from test_design_family import example

APP=QApplication.instance() or QApplication([])

class DesignSynthesisTests(unittest.TestCase):
    def test_same_appearance_different_review_ids_merges_but_unlearned_size_stays_preview(self):
        from template_ai.design_synthesis import _font_options
        key=self.profile['roles'][0]['key']
        for data in self.profile['data_requirement_profiles']:
            for sample in data['presentation_evidence']:
                sample['label_binding']['evidence_refs']=['unique-'+sample['example_id']]
        options=_font_options(self.profile,key,90,54)
        self.assertEqual(len(options),1)
        self.assertEqual(options[0]['support'],8)
        self.assertEqual(len(options[0]['source_refs']),8)
        self.assertEqual(options[0]['size_admission'],'OBSERVED_EXACT_SIZE')
        result=synthesize(self.profile,self.graph,180,108,self.policy)
        self.assertEqual(result['status'],'FEASIBLE_PREVIEW')
        self.assertTrue(all(row['candidate'].risk_context['design_size_admission']=='UNVERIFIED_SIZE_PREVIEW_ONLY'
            for row in result['candidates']))

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.library=Library(Path(self.temp.name)/'data');self.addCleanup(self.library.db.close)
        source=bind_authored_fonts(demo_template(),FontManager(self.library));asset=source.slots[0].font_asset
        rows=[example(i) for i in range(8)]
        for row in rows:
            row['fields'].append(dict(id='phone2',owner='p1',kind='phone',index=1,
                rect=dict(x=8,y=35,w=38,h=6)))
            for field in row['fields']:
                field['source_typography']={'font_asset_ref':deepcopy(asset),
                    'source_pt':dict(value=10.,unit='pt',status='OBSERVED',evidence_refs=['authored']),
                    'horizontal_scale':dict(value=1.,unit='ratio',status='OBSERVED',evidence_refs=['authored']),
                    'tracking':dict(value=0.,unit='mm',status='OBSERVED',evidence_refs=['authored'])}
                field['label_binding']=dict(status='CONFIRMED',kind='NO_FIXED_LABEL',evidence_refs=['author'])
        self.profile=learn_profiles(train_families(rows),rows)['families'][0]
        self.graph=InputGraph.from_legacy([dict(name='Alex Example',phone=['0123456789','0987654321'])],[])
        self.policy=dict(approved=True,version='authored-1',candidate_budget=32,safe_margin_mm=0.)

    def solve(self,intents=None):return synthesize(self.profile,self.graph,90,54,self.policy,intents)

    def test_real_qt_shaping_and_kiwi_create_preview_without_publishing_or_losing_data(self):
        result=self.solve();self.assertEqual(result['status'],'FEASIBLE_PREVIEW')
        candidate=result['candidates'][0]['candidate']
        self.assertEqual(len(candidate.items),3)
        self.assertEqual({item.text for item in candidate.items},{'Alex Example','0123456789','0987654321'})
        self.assertFalse(candidate.valid);self.assertEqual(candidate.template.state,'draft')
        self.assertEqual(self.library.templates(),[])

    def test_same_input_repeat_and_explicit_swap_keep_same_family_and_stable_geometry(self):
        base=self.solve();again=self.solve()
        self.assertEqual(base['candidates'][0]['geometry_digest'],again['candidates'][0]['geometry_digest'])
        facts=input_facts(self.graph);phones=[f for f in facts if f['kind']=='phone']
        swap=[dict(subject=phones[0]['render_id'],relation='BELOW',object=phones[1]['render_id'])]
        result=self.solve(swap);self.assertEqual(result['status'],'FEASIBLE_PREVIEW')
        candidate=result['candidates'][0]['candidate'];items={item.slot.id:item for item in candidate.items}
        self.assertGreaterEqual(items[phones[0]['render_id']].slot.rect.y,
            items[phones[1]['render_id']].slot.rect.y+items[phones[1]['render_id']].slot.rect.h)
        self.assertEqual(candidate.template.family_id,base['family_id'])

    def test_cycles_and_customer_fine_parameter_commands_are_rejected(self):
        a,b=[f['render_id'] for f in input_facts(self.graph) if f['kind']=='phone']
        with self.assertRaises(ValueError):self.solve([dict(subject=a,relation='ABOVE',object=b),dict(subject=b,relation='ABOVE',object=a)])
        with self.assertRaises(ValueError):self.solve([dict(subject=a,relation='FONT_SIZE',object=b)])

    def test_missing_source_typography_is_unknown_instead_of_default_font(self):
        for data in self.profile['data_requirement_profiles']:
            for sample in data['presentation_evidence']:sample['joint']['source_pt']=None
        result=self.solve();self.assertEqual(result['status'],'SOURCE_EVIDENCE_REQUIRED')
        self.assertEqual(result['candidates'],[])

    def test_oversized_input_is_retained_and_cannot_be_silently_truncated(self):
        phone=next(row for row in self.graph.data['fields'] if row['kind']=='phone')
        phone['value']='1234567890'*20
        result=self.solve();self.assertNotEqual(result['status'],'FEASIBLE_PREVIEW')
        self.assertEqual(phone['value'],'1234567890'*20)

    def test_semantic_phone_assignment_uses_learned_default_independent_of_input_order(self):
        for data in self.profile['data_requirement_profiles']:
            for row in data['presentation_evidence']:
                if row['role_key']=='p1:phone:0':row['semantic_type']='mobile'
                elif row['role_key']=='p1:phone:1':row['semantic_type']='landline'
        self.profile['grammar']['default_semantic_roles'].update({'p1:phone:0':'mobile','p1:phone:1':'landline'})
        graph=InputGraph.from_legacy([dict(name='Alex Example',phone=['02-2345-6789','0912-345-678'])],[])
        result=synthesize(self.profile,graph,90,54,self.policy)
        self.assertEqual(result['status'],'FEASIBLE_PREVIEW',result['issues'])
        by_value={item.text:item for item in result['candidates'][0]['candidate'].items}
        self.assertLess(by_value['0912-345-678'].slot.rect.y,by_value['02-2345-6789'].slot.rect.y)
        rows=result['assigned_containers'];self.assertEqual(len({row['container_key'] for row in rows}),len(rows))
        self.assertEqual(by_value['02-2345-6789'].slot.index,0)

    def test_source_observed_expanded_width_is_core_controlled_and_actually_measured(self):
        for data in self.profile['data_requirement_profiles']:
            for row in data['presentation_evidence']:row['joint']['horizontal_scale']=1.1
        result=self.solve()
        self.assertEqual(result['status'],'FEASIBLE_PREVIEW',result['issues'])
        candidate=result['candidates'][0]['candidate']
        self.assertTrue(all(item.scale==1.1 for item in candidate.items))
        from template_ai.design_evaluation import check_layout
        self.assertEqual(check_layout(candidate,self.graph)['status'],'PASS')

    def test_distributed_style_uses_conditional_source_bounds_and_actual_fixed_pt_measurement(self):
        asset=self.profile['data_requirement_profiles'][0]['presentation_evidence'][0]['source_font_ref']
        rows=[example(i) for i in range(8)]
        for i,row in enumerate(rows):
            for field in row['fields']:
                field['source_typography']=dict(font_asset_ref=deepcopy(asset),
                    source_pt=dict(value=10.,unit='pt',status='OBSERVED',evidence_refs=['owned']),
                    horizontal_scale=dict(value=1.,unit='ratio',status='OBSERVED',evidence_refs=['owned']),
                    tracking=dict(value=(i*.2 if field['kind']=='phone' else 0.),unit='mm',status='OBSERVED',evidence_refs=['owned']))
                field['label_binding']=dict(status='CONFIRMED',kind='NO_FIXED_LABEL',evidence_refs=['author'])
                if field['kind']=='phone':
                    field['kind']='title';field['source_alignment']='distributed'
                    field['source_distribution']=dict(approved=True,actor='Owned source reviewer',reason='Source title style measured')
        profile=learn_profiles(train_families(rows),rows)['families'][0]
        graph=InputGraph.from_legacy([dict(name='Alex Example',title='Senior Designer')],[])
        result=synthesize(profile,graph,90,54,self.policy)
        self.assertEqual(result['status'],'FEASIBLE_PREVIEW',result['issues'])
        item=next(item for item in result['candidates'][0]['candidate'].items if item.slot.kind=='title')
        self.assertEqual(item.slot.align,'distributed');self.assertEqual(item.slot.size_pt,10.)
        self.assertGreaterEqual(item.tracking_mm,0.);self.assertLessEqual(item.tracking_mm,1.4+1e-9)
        from template_ai.layout import text_geometry
        width,_,errors=text_geometry(item.slot.font,10.,item.text,item.slot.font_style,item.slot.font_asset,item.tracking_mm)
        self.assertFalse(errors);self.assertLessEqual(width,item.slot.rect.w+1e-4)

from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from PySide6.QtWidgets import QApplication
from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.fonts import FontManager
from template_ai.demo import demo_template
from template_ai.design_source_binding import SourceTypographyReview
from template_ai.design_learning import CrossWorkLearning,USE
from authored_font_fixture import bind_authored_fonts
from training_fixture import source_work
from test_noise_authoring import confirmed
from test_trusted_samples import admitted

APP=QApplication.instance() or QApplication([])

class SourceTypographyBindingTests(unittest.TestCase):
    def test_unknown_source_pt_stays_unknown_when_work_pt_is_independently_measured(self):
        from unittest.mock import patch
        observation=deepcopy(self.store._design_observation_document(self.work['id']))
        observation['original_text_evidence']['runs'][0]['source_pt'].update(value=None,status='UNKNOWN')
        review=dict(self.review,physical_work_pt=17.,physical_work_measurement_refs=['authored work-space measurement'])
        with patch.object(self.service.store,'_design_observation_document',return_value=observation):
            plan=self.service.plan(self.work['id'],self.slot['id'],self.run['id'],self.asset,review)
        self.assertEqual(plan['typography']['source_page_pt']['status'],'UNKNOWN')
        self.assertEqual(plan['typography']['source_pt']['value'],17.)
        contradictory=dict(self.review,word_spacing=.2,source_text_flow=dict(spacing_rule=dict(mode='WORDS',value_mm=.3)))
        with self.assertRaisesRegex(ValueError,'contradicts'):
            self.service.plan(self.work['id'],self.slot['id'],self.run['id'],self.asset,contradictory)

    def resized_work(self,sx,sy):
        payload=deepcopy(self.work['payload']);payload.update(work_width=90*sx,work_height=54*sy)
        for slot in payload['slots']:
            for key,scale in [('x',sx),('w',sx),('y',sy),('h',sy)]:slot['rect'][key]*=scale
        work=self.library.create_artwork(self.source['id'],'Authored resized work',payload)
        confirmed(self.store,work)
        return work

    def test_uniform_work_scale_changes_effective_pt_not_original_source_fact(self):
        work=self.resized_work(.5,.5)
        plan=self.service.plan(work['id'],self.slot['id'],self.run['id'],self.asset,self.review)
        self.assertAlmostEqual(plan['typography']['source_pt']['value'],9.)
        self.assertAlmostEqual(plan['typography']['source_page_pt']['value'],18.)
        self.assertEqual(plan['typography']['source_pt']['status'],'DERIVED')
        self.assertAlmostEqual(plan['typography']['source_anchor_work_mm']['y'],7.)
        self.assertNotIn('baseline',plan['typography']) # SVG anchor is not recovered glyph baseline

    def test_anisotropic_work_requires_work_measurements_instead_of_scalar_guess(self):
        work=self.resized_work(.5,.75)
        with self.assertRaisesRegex(ValueError,'Anisotropic'):
            self.service.plan(work['id'],self.slot['id'],self.run['id'],self.asset,self.review)
        review=dict(self.review,physical_work_pt=13.,physical_work_measurement_refs=['authored measured output'])
        plan=self.service.plan(work['id'],self.slot['id'],self.run['id'],self.asset,review)
        self.assertEqual(plan['typography']['horizontal_scale']['status'],'UNKNOWN')
        self.assertEqual(plan['typography']['tracking']['status'],'UNKNOWN')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.library=Library(self.root/'data');self.addCleanup(self.library.db.close)
        self.source,self.work=source_work(self.library,self.root);self.store=TrainingStore(self.library)
        confirmed(self.store,self.work);self.sample=admitted(self.store,self.work)
        self.asset=bind_authored_fonts(demo_template(),FontManager(self.library)).slots[0].font_asset
        original=self.store._design_observation_document(self.work['id'])['original_text_evidence']
        self.run=original['runs'][0];self.slot=self.work['payload']['slots'][0]
        self.review=dict(source_identity_confirmed=True,
            basis='Authored fixture expert correspondence;not real Illustrator font fidelity evidence',
            horizontal_scale=1.,tracking=0.,parameter_measurement_refs=['authored source parameter inspection'],
            label_binding=dict(status='CONFIRMED',kind='NO_FIXED_LABEL',evidence_refs=['author']))
        self.service=SourceTypographyReview(self.library)

    def test_explicit_binding_is_pinned_and_enables_measured_demand_not_default_typography(self):
        plan=self.service.plan(self.work['id'],self.slot['id'],self.run['id'],self.asset,self.review)
        with self.assertRaises(ValueError):self.service.confirm(plan,'Reviewer')
        saved=self.service.confirm(plan,'Reviewer',True)
        self.assertAlmostEqual(saved['typography']['source_pt']['value'],18)
        self.assertEqual(saved['typography']['glyph_runs']['status'],'UNKNOWN')
        self.assertIsNotNone(saved['typography']['shaped_advance']['value'])
        learning=CrossWorkLearning(self.library)
        dataset=learning.dataset_plan({self.sample['id']:'TRAIN'},
            dict(use=USE,actor='Author',basis='Authored explicit rule learning permission'))
        field=next(row for row in dataset['examples'][0]['fields'] if row['id']==self.slot['id'])
        self.assertAlmostEqual(field['source_typography']['source_pt']['value'],18)
        self.assertEqual(field['label_binding']['kind'],'NO_FIXED_LABEL')

    def test_wrong_run_unknown_identity_and_changed_facts_cannot_be_bound(self):
        original=self.store._design_observation_document(self.work['id'])['original_text_evidence']
        with self.assertRaises(ValueError):
            self.service.plan(self.work['id'],self.slot['id'],original['runs'][1]['id'],self.asset,self.review)
        with self.assertRaises(ValueError):
            self.service.plan(self.work['id'],self.slot['id'],self.run['id'],self.asset,dict(self.review,source_identity_confirmed=False))
        plan=self.service.plan(self.work['id'],self.slot['id'],self.run['id'],self.asset,self.review)
        facts=self.store.facts(self.work['id'])
        self.store.save_facts(self.work['id'],facts['observations'],facts['revision'],self.work['revision'])
        with self.assertRaises(ValueError):self.service.confirm(plan,'Reviewer',True)

    def test_hidden_original_text_is_not_a_visible_source_font_binding(self):
        from unittest.mock import patch
        original=deepcopy(self.store._design_observation_document(self.work['id']))
        original['original_text_evidence']['runs'][0]['visibility']='NONPAINTING_TEXT'
        with patch.object(self.service.store,'_design_observation_document',return_value=original):
            with self.assertRaisesRegex(ValueError,'Hidden'):
                self.service.plan(self.work['id'],self.slot['id'],self.run['id'],self.asset,self.review)

    def test_measured_parameter_cannot_overwrite_known_original_source_value(self):
        from unittest.mock import patch
        original=deepcopy(self.store._design_observation_document(self.work['id']))
        original['original_text_evidence']['runs'][0]['horizontal_scale']={
            'value':.8,'unit':'ratio','status':'OBSERVED','basis':'ORIGINAL_PDF_TZ','evidence_refs':[self.run['id']]}
        with patch.object(self.service.store,'_design_observation_document',return_value=original):
            with self.assertRaisesRegex(ValueError,'contradicts'):
                self.service.plan(self.work['id'],self.slot['id'],self.run['id'],self.asset,self.review)

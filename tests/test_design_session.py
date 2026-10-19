from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication

from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.fonts import FontManager
from template_ai.demo import demo_template
from template_ai.input_graph import InputGraph
from template_ai.design_learning import CrossWorkLearning,USE
from template_ai.design_source_binding import SourceTypographyReview
from template_ai.design_session import DesignSessions
from template_ai.design_synthesis import input_facts
from authored_font_fixture import bind_authored_fonts
from training_fixture import source_work
from test_noise_authoring import confirmed
from test_trusted_samples import admitted

APP=QApplication.instance() or QApplication([])


class DesignSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        library=Library(cls.root/'data');store=TrainingStore(library)
        asset=bind_authored_fonts(demo_template(),FontManager(library)).slots[0].font_asset
        samples=[];reviewer=SourceTypographyReview(library)
        for i in range(8):
            source,work=source_work(library,cls.root,name='design-'+str(i)+'.svg',note_text='Authored design '+str(i))
            confirmed(store,work);sample=admitted(store,work);samples.append(sample)
            original=store._design_observation_document(work['id'])['original_text_evidence']
            for slot,run in zip(work['payload']['slots'],original['runs']):
                review=dict(source_identity_confirmed=True,basis='Synthetic source author correspondence record',
                    horizontal_scale=1.,tracking=0.,parameter_measurement_refs=['Authored source inspection'],
                    label_binding=dict(status='CONFIRMED',kind='NO_FIXED_LABEL',evidence_refs=['author']))
                reviewer.confirm(reviewer.plan(work['id'],slot['id'],run['id'],asset,review),'Author',True)
        learning=CrossWorkLearning(library)
        roles={sample['id']:'TRAIN' if i<6 else 'VALIDATION' if i==6 else 'HOLDOUT' for i,sample in enumerate(samples)}
        dataset=learning.freeze_dataset(learning.dataset_plan(roles,
            dict(use=USE,actor='Author',basis='Explicit authored local rule learning use')),'Author',True)
        cls.model=learning.train(dataset['id'],'Author',approved=True)
        cls.dataset_id=dataset['id'];library.db.close()

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def setUp(self):
        self.library=Library(self.root/'data');self.addCleanup(self.library.db.close)
        self.sessions=DesignSessions(self.library)
        self.graph=InputGraph.from_legacy([dict(name='Alex Example',title='Designer',
            phone='+1 202 555 0100',email='alex@example.test')],[])
        self.policy=dict(version='authored-1',approved=True,basis='Authored preview policy',production=False)
        self.session=self.sessions.create(self.graph,90,54,'Author',self.model['id'],self.policy)

    def solve(self):
        row=self.sessions.current(self.session['id'])
        return self.sessions.solve(row['id'],row['revision'])

    def test_actual_source_bound_model_input_solve_confirm_and_preview_output(self):
        result=self.solve();self.assertEqual(result['status'],'FEASIBLE_PREVIEW')
        current=self.sessions.current(self.session['id'])
        confirmed=self.sessions.confirm(current['id'],current['revision'],'Author')
        self.assertEqual(confirmed['confirmation']['scope'],'PREVIEW_ONLY')
        target=self.root/('PREVIEW-'+self.session['id']+'.png')
        artifact=self.sessions.export(current['id'],target)
        self.assertTrue(target.is_file());self.assertFalse(artifact['production'])
        self.assertEqual(self.sessions.replay_artifact(artifact['id'])['sha256'],artifact['sha256'])
        with self.assertRaises(ValueError):self.sessions.export(current['id'],self.root/'formal.png',preview=False)

    def test_correct_data_then_undo_layout_preserves_new_phone_and_owner(self):
        self.solve();facts=input_facts(self.graph)
        phone=next(f for f in facts if f['kind']=='phone');email=next(f for f in facts if f['kind']=='email')
        current=self.sessions.current(self.session['id'])
        self.sessions.set_relation(current['id'],current['revision'],'move-1',phone['render_id'],'BELOW',email['render_id'])
        result=self.solve();self.assertEqual(result['status'],'FEASIBLE_PREVIEW')
        current=self.sessions.current(self.session['id']);graph=InputGraph(current['input_graph'])
        next(f for f in graph.data['fields'] if f['kind']=='phone')['value']='+1 202 555 0199'
        self.sessions.replace_input(current['id'],current['revision'],'phone-1',graph);self.solve()
        current=self.sessions.current(self.session['id'])
        self.sessions.undo_layout(current['id'],current['revision'],'undo-1')
        after=self.sessions.current(current['id'])
        self.assertEqual(next(f for f in after['input_graph']['fields'] if f['kind']=='phone')['value'],'+1 202 555 0199')
        self.assertEqual(after['data_revision'],2);self.assertEqual(after['intents'],[])
        with self.assertRaises(ValueError):self.sessions.confirm(after['id'],after['revision'],'Author')
        self.assertEqual(self.solve()['status'],'FEASIBLE_PREVIEW')

    def test_idempotent_request_and_reopen_keep_intent_without_default_override(self):
        self.solve();phone,email=[f for f in input_facts(self.graph) if f['kind'] in ('phone','email')]
        current=self.sessions.current(self.session['id'])
        first=self.sessions.set_relation(current['id'],current['revision'],'same-request',phone['render_id'],'BELOW',email['render_id'])
        replay=self.sessions.set_relation(current['id'],current['revision'],'same-request',phone['render_id'],'BELOW',email['render_id'])
        self.assertTrue(replay['replayed']);self.assertEqual(first['applied_revision'],replay['applied_revision'])
        reopened=Library(self.library.root)
        try:self.assertEqual(DesignSessions(reopened).current(current['id'])['intents'][0]['relation'],'BELOW')
        finally:reopened.db.close()

    def test_late_solve_cannot_install_old_data_over_new_input(self):
        from template_ai.design_synthesis import synthesize
        fired=[]
        def delayed(*args,**kwargs):
            result=synthesize(*args,**kwargs)
            if not fired:
                fired.append(True);current=self.sessions.current(self.session['id']);graph=InputGraph(current['input_graph'])
                next(f for f in graph.data['fields'] if f['kind']=='phone')['value']='+1 202 555 0111'
                self.sessions.replace_input(current['id'],current['revision'],'late-input',graph)
            return result
        with patch('template_ai.design_session.synthesize',side_effect=delayed):
            with self.assertRaises(ValueError):self.solve()
        current=self.sessions.current(self.session['id'])
        self.assertEqual(next(f for f in current['input_graph']['fields'] if f['kind']=='phone')['value'],'+1 202 555 0111')
        self.assertNotEqual(current['result_state'],'CURRENT')

    def test_accepted_artifact_reuses_exact_bytes_after_new_model_activation(self):
        self.solve();current=self.sessions.current(self.session['id']);self.sessions.confirm(current['id'],current['revision'],'Author')
        artifact=self.sessions.export(current['id'],self.root/('PREVIEW-repeat-'+current['id']+'.png'))
        learning=CrossWorkLearning(self.library);new=learning.train(self.dataset_id,'Author',approved=True)
        active=learning.store.get('DESIGN_ACTIVE','local-layout')
        learning.activate(new['id'],active['revision'] if active else 0,'Author',self.policy,True)
        changed_revision=InputGraph(deepcopy(self.graph.data));changed_revision.data['revision']+=5
        found=self.sessions.find_accepted(changed_revision,90,54,production=False)
        self.assertEqual(found['id'],artifact['id'])
        replay=self.sessions.replay_artifact(artifact['id'])
        self.assertEqual(replay['sha256'],artifact['sha256']);self.assertEqual(replay['model_id'],self.model['id'])

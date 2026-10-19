from copy import deepcopy
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from template_ai.storage import Library
from template_ai.design_session import DesignSessions,_candidate
from template_ai.design_feedback import DesignFeedback,USE
from template_ai.design_qualification import DesignQualification
from template_ai.design_evaluation import DesignEvaluation
from template_ai.design_jobs import DesignJobs,run_design_job
from template_ai.input_graph import InputGraph
from template_ai.design_synthesis import input_facts
from template_ai.training_store import digest
import test_design_session as session_fixture


class ExactFeedbackQualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=session_fixture.DesignSessionTests;cls.fixture.setUpClass()
        cls.root=cls.fixture.root;cls.model=cls.fixture.model;cls.dataset_id=cls.fixture.dataset_id
    @classmethod
    def tearDownClass(cls):cls.fixture.tearDownClass()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.library=Library(Path(self.temp.name)/'data');self.addCleanup(self.library.close)
        original=Library(self.root/'data')
        try:original.db.backup(self.library.db)
        finally:original.close()
        self.sessions=DesignSessions(self.library);self.feedback=DesignFeedback(self.library)
        self.dataset=self.feedback.learning.checked_dataset(self.dataset_id)
        self.policy=dict(version='authored-gates-1',approved=True,production=False)
        self.permission=dict(use=USE,basis='Explicit authored preference training mechanism use')
    def graph_for_sample(self,sample_id):
        sample=self.feedback.store.get('SAMPLE',sample_id);slots={row['id']:row for row in sample['label_slots']}
        person={}
        for label in sample['positive_labels']:
            slot=slots[label['slot_id']];person.setdefault(slot['kind'],[]).append(label['text'])
        return InputGraph.from_legacy([person],[])
    def pair(self,sample_id):
        graph=self.graph_for_sample(sample_id);session=self.sessions.create(graph,90,54,'Author',self.model['id'],self.policy)
        before=self.sessions.solve(session['id'],session['revision'])
        fields={row['kind']:row for row in input_facts(graph)};current=self.sessions.current(session['id'])
        command=self.sessions.set_relation(session['id'],current['revision'],'authored-phone-after-mail',
            fields['phone']['render_id'],'BELOW',fields['email']['render_id'])
        current=self.sessions.current(session['id']);after=self.sessions.solve(session['id'],current['revision'])
        return session,before,command,after
    def test_actual_result_feedback_retains_unknown_reason_and_cannot_change_global_policy(self):
        entry=next(row for row in self.dataset['entries'] if row['role']=='TRAIN')
        _,before,command,after=self.pair(entry['sample_id'])
        saved=self.feedback.record(before['id'],command['id'],after['id'],True,'ORDER','Author')
        self.assertEqual(saved['reason_status'],'UNKNOWN');self.assertFalse(saved['global_policy_changed'])
        with self.assertRaises(ValueError):self.feedback.curate(saved['id'],entry['sample_id'],'Reviewer',self.permission,'Actual comparison',True)
        other,_,_,_=self.pair(entry['sample_id'])
        foreign=self.sessions.solve(other['id'],self.sessions.current(other['id'])['revision'])
        with self.assertRaises(ValueError):self.feedback.record(before['id'],command['id'],foreign['id'],True,'ORDER','Author')
    def test_curated_actual_train_pairs_fit_preview_ranker_and_withdrawal_invalidates_support(self):
        selected=[row for row in self.dataset['entries'] if row['role']=='TRAIN'][:2];examples=[]
        for entry in selected:
            _,before,command,after=self.pair(entry['sample_id'])
            feedback=self.feedback.record(before['id'],command['id'],after['id'],True,'REVIEWED_STYLE',
                'Independent authored reviewer','Preferred contact order in this owned example','PREFERENCE')
            examples.append(self.feedback.curate(feedback['id'],entry['sample_id'],'Curator',self.permission,
                'Compared actual before and after draft',True))
        ranker=self.feedback.train([row['id'] for row in examples],'Curator',True)
        self.assertEqual(ranker['state'],'PENDING')
        active=self.feedback.activate(ranker['id'],0,'Reviewer',dict(version='owned-pref-1',production=False),True)
        self.assertEqual(active['model_id'],ranker['id'])
        with self.assertRaises(ValueError):self.feedback.activate(ranker['id'],active['revision'],'Reviewer',dict(version='invalid',production=True),True)
        sample_id=selected[0]['sample_id'];self.feedback.store.transition_sample(
            self.feedback.store.sample_transition_plan(sample_id,'REVOKE'),'Author','Owned support withdrawal',True)
        with self.assertRaises(ValueError):self.feedback.checked_ranker(ranker['id'])
    def test_synthetic_evaluation_cannot_obtain_real_corpus_certificate(self):
        heldout=next(row for row in self.dataset['entries'] if row['role']=='HOLDOUT')
        graph=self.graph_for_sample(heldout['sample_id']);evaluation=DesignEvaluation(self.library)
        job=evaluation.create(self.model['id'],[dict(id='owned-only',sample_id=heldout['sample_id'],
            input_graph=graph.data,width_mm=90.,height_mm=54.,truth_refs=['Owned exact source review'])],
            self.policy,'Reviewer',origin='AUTHORED_SYNTHETIC',review_refs=['Owned source only'],approved=True)
        service=DesignQualification(self.library)
        with self.assertRaisesRegex(ValueError,'synthetic'):
            service.review_corpus(job['id'],'Reviewer','Owned source only',real_authorized=True,
                lineage_independence_reviewed=True,approved=True)
    def test_forged_qualification_state_or_generated_reference_cannot_enable_formal_output(self):
        entry=next(row for row in self.dataset['entries'] if row['role']=='TRAIN')
        session,before,_,_=self.pair(entry['sample_id'])
        current=self.sessions.current(session['id'])
        with self.assertRaises(ValueError):self.sessions.qualify_result(current['id'],current['revision'],'Reviewer')
        candidate=_candidate(before['selected']['serialized'])
        candidate.template.state='learned_instance';candidate.template.generation_reference=dict(instance_id='forged')
        self.assertFalse(candidate.formal_eligible)
        with self.assertRaises(ValueError):self.library.publish(candidate.template)

    def test_current_instance_output_mechanics_with_mocked_external_certificate_boundary(self):
        # This owned-fixture test stubs real-corpus qualification ONLY. It does
        # not qualify any corpus/model for production outside this temporary DB.
        model=self.feedback.store.get('DESIGN_MODEL',self.model['id'])
        with self.feedback.store.transaction():
            body={k:deepcopy(v) for k,v in model.items() if k not in ('id','revision')}
            body['formal_qualification']='PASS'
            self.feedback.store._write('DESIGN_MODEL',model['id'],body,model['revision'],'owned_mock_certificate_boundary')
        policy=dict(self.policy,production=True)
        certificate=dict(id='OWNED_MOCK_EXTERNAL_CERTIFICATE_NOT_REAL_QUALIFICATION',plan=dict(layout_policy=policy))
        entry=next(row for row in self.dataset['entries'] if row['role']=='TRAIN')
        graph=self.graph_for_sample(entry['sample_id'])
        session=self.sessions.create(graph,90,54,'Authored test reviewer',model['id'],policy)
        self.sessions.solve(session['id'],session['revision'])
        with patch('template_ai.design_instances.validate_certificate',return_value=certificate):
            current=self.sessions.current(session['id'])
            result=self.sessions.qualify_result(current['id'],current['revision'],'Authored test reviewer')
            current,result,candidate=self.sessions.checked_result(session['id'])
            self.assertTrue(candidate.formal_eligible,candidate.risk)
            self.assertEqual(self.library.templates(),[])
            self.sessions.confirm(current['id'],current['revision'],'Authored test reviewer',for_production=True)
            target=Path(self.temp.name)/'owned-mocked-boundary-output.png'
            artifact=self.sessions.export(session['id'],target,preview=False,dpi=72)
            self.assertTrue(target.is_file());self.assertTrue(artifact['production'])
            self.assertEqual(self.sessions.replay_artifact(artifact['id'])['sha256'],artifact['sha256'])
            candidate.items[0].text+=' unauthorized change'
            self.assertFalse(candidate.formal_eligible)
        # Removing the mocked boundary restores the real missing-certificate gate.
        _,_,actual=self.sessions.checked_result(session['id'])
        self.assertFalse(actual.formal_eligible)

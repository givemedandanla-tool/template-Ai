from copy import deepcopy
import unittest
from template_ai.storage import Library
from template_ai.design_jobs import DesignJobs,run_design_job
from template_ai.design_evaluation import DesignEvaluation,check_layout,wilson
from template_ai.design_session import DesignSessions
from template_ai.input_graph import InputGraph
import test_design_session as session_fixture


class ActualLayoutEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=session_fixture.DesignSessionTests
        cls.fixture.setUpClass();cls.root=cls.fixture.root;cls.model=cls.fixture.model;cls.dataset_id=cls.fixture.dataset_id
    @classmethod
    def tearDownClass(cls):cls.fixture.tearDownClass()
    def setUp(self):
        self.library=Library(self.root/'data');self.addCleanup(self.library.close)
        self.service=DesignEvaluation(self.library);self.jobs=DesignJobs(self.library)
        self.graph=InputGraph.from_legacy([dict(name='Alex Example',title='Designer',phone='+1 202 555 0100',email='alex@example.test')],[])
        self.dataset=self.service.learning.checked_dataset(self.dataset_id)
        self.heldout=next(row for row in self.dataset['entries'] if row['role']=='HOLDOUT')
        self.policy=dict(version='authored-evaluation-1',approved=True,candidate_budget=32)
    def case(self,identity='owned-evaluation',graph=None):
        return dict(id=identity,sample_id=self.heldout['sample_id'],input_graph=(graph or self.graph).data,
            width_mm=90.,height_mm=54.,truth_refs=['Authored independent input/source correspondence'])
    def create(self,cases):
        return self.service.create(self.model['id'],cases,self.policy,'Owned reviewer',origin='AUTHORED_SYNTHETIC',
            review_refs=['Authored known source lineage'],approved=True)
    def run_job(self,job):
        claimed=self.jobs.claim(job['id'],job['revision'])
        return run_design_job(self.library.root,job['id'],claimed['owner']['token'])
    def test_actual_paired_layout_evaluation_preserves_weights_and_records_unknown_denominator(self):
        large=InputGraph(deepcopy(self.graph.data))
        next(field for field in large.data['fields'] if field['kind']=='email')['value']='a'*1000+'@example.test'
        job=self.create([self.case('short'),self.case('long',large)])
        report=self.run_job(job)['summary']
        self.assertEqual(report['denominator'],2);self.assertEqual(report['hard_error_count'],0)
        self.assertEqual(report['statuses'],{'FEASIBLE':1,'UNKNOWN_OR_UNSUPPORTED':1})
        self.assertEqual(report['feasible_rate'],.5);self.assertEqual(report['data_integrity_rate'],1.)
        self.assertEqual(report['origin'],'AUTHORED_SYNTHETIC')
        self.assertEqual(self.service.learning.checked_model(self.model['id'])[0]['weights_digest'],self.model['weights_digest'])
        self.assertTrue(self.service.store.count('DESIGN_HOLDOUT_EXPOSURE'))
    def test_training_source_cannot_be_relabelled_as_heldout_evaluation(self):
        case=self.case();case['sample_id']=next(row['sample_id'] for row in self.dataset['entries'] if row['role']=='TRAIN')
        with self.assertRaisesRegex(ValueError,'TRAIN'):self.create([case])
    def test_preference_requires_actual_two_outputs_and_remains_scoped(self):
        job=self.create([self.case()])
        with self.assertRaises(ValueError):self.service.review_preference(job['id'],0,'LEARNED','Reviewer','No output yet')
        self.run_job(job)
        review=self.service.review_preference(job['id'],0,'TIE','Independent authored reviewer','Both exact authored layouts inspected')
        self.assertFalse(review['global_policy_changed']);self.assertEqual(review['role'],'HOLDOUT')
    def test_independent_checker_detects_data_loss_owner_change_overflow_and_collision(self):
        sessions=DesignSessions(self.library)
        session=sessions.create(self.graph,90,54,'Author',self.model['id'],self.policy)
        sessions.solve(session['id'],session['revision']);_,_,candidate=sessions.checked_result(session['id'])
        self.assertEqual(check_layout(candidate,self.graph)['status'],'PASS')
        candidate.items[0].text+=' silently inserted data'
        candidate.items[1].slot.owner='p2';candidate.items[1].slot.rect=candidate.items[0].slot.rect
        result=check_layout(candidate,self.graph)
        self.assertEqual(result['status'],'FAIL')
        self.assertTrue({'DATA_CHANGED','OWNER_CHANGED','FIELD_COLLISION'}<=set(result['errors']))
        candidate.items.pop();self.assertIn('DATA_COVERAGE_MISMATCH',check_layout(candidate,self.graph)['errors'])
    def test_uncertainty_with_zero_cases_remains_unknown(self):
        self.assertIsNone(wilson(0,0));lower,upper=wilson(1,2)
        self.assertLess(lower,.5);self.assertGreater(upper,.5)

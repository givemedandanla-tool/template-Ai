"""Re-execute real exposed failures without resetting holdout independence."""
import copy,unittest
import test_quality_repairs as fixtures
from template_ai.quality_protocol import QualityProtocols,REPAIR
from template_ai.quality_jobs import EvaluationJobs
from template_ai.quality_reports import QualityReports
from template_ai.runtime_queue import RuntimeQueue
from template_ai.runtime_worker import run_isolated
from template_ai.model import new_id
from test_runtime_execution import ALLOW


class QualityRepairReplayTests(unittest.TestCase):
    setUp=fixtures.QualityRepairIssueTests.setUp
    build=fixtures.QualityRepairIssueTests.build
    critical=fixtures.QualityRepairIssueTests.critical
    issue_plan=fixtures.QualityRepairIssueTests.issue_plan

    def prepare(self):
        plan=self.issue_plan();issue=self.repairs.create_quality_issue(plan,'Reviewer','Actual exposed failure root investigation',True)
        root=self.repairs.root_plan(issue['id'],'WORK_SEGMENTATION','Reproduce exact omitted work before any new acceptance','Original and gold reviewed; this is not independent quality evidence',True,True)
        self.review=self.repairs.confirm_root(root,'Reviewer',True);self.protocols=QualityProtocols(self.library)
        scope=self.protocol['scope']
        self.args=('Actual root reproduction',scope['dataset_id'],scope['policy_id'],{side:pin['id'] for side,pin in scope['pipelines'].items()},'Same exposed cases used only as descriptive root regression')
        return self.protocols.plan(*self.args,repair_review_id=self.review['id'])

    def test_bound_replay_keeps_actual_holdout_exposure_roles_and_original_consumption(self):
        plan=self.prepare();consumption=list(self.store.db.execute("SELECT id,revision,payload FROM training_records WHERE kind='QUALITY_HOLDOUT_USAGE' ORDER BY id"));roles=list(self.store.db.execute("SELECT id,revision,payload FROM training_records WHERE kind='GROUP_ROLE' ORDER BY id"))
        self.assertFalse(plan['independence_claim']);self.assertEqual(plan['scope']['purpose'],REPAIR)
        with self.assertRaises(ValueError):self.protocols.plan(*self.args)
        replay=self.protocols.freeze(plan,'Reviewer',True);jobs=EvaluationJobs(self.library).create_pair(replay['id'],'Reviewer',True)
        queue=RuntimeQueue(self.library);session=new_id()
        for side in ('BASELINE','CANDIDATE'):
            request=queue.enqueue('EVAL_JOB',jobs[side]['id'],'Reviewer',session,True);claimed=queue.claim(queue.get(request['id']),session)
            done=run_isolated(self.library.root,'EVAL_JOB',claimed['id'],claimed['owner_token'],admission=lambda:ALLOW);queue.finish(request['id'],claimed['owner_token'],done)
            self.assertEqual(done['phase'],'COMPLETED');result=self.store.get('QUALITY_EVAL_RESULT',done['result_id'])
            self.assertEqual(result['origin'],'ACTUAL_FIFO_SOURCE_EVALUATION');self.assertFalse(result['quality_pass'])
            self.assertEqual(result['quality_gate'],'DESCRIPTIVE_REPAIR_ONLY_NOT_INDEPENDENT')
            self.assertEqual(result['statistics']['evaluation_role'],REPAIR)
            self.assertTrue(result['source_results'])
            self.assertTrue(all(c['failure_rate_interval'] is None for d in result['statistics']['domains'].values() for c in d['classes'].values()))
        report=QualityReports(self.library).plan(replay['id']);self.assertFalse(report['candidate_decision_eligible'])
        receipt=QualityReports(self.library).save(report,'Reviewer',True)
        with self.assertRaises(ValueError):QualityReports(self.library).decide(receipt['id'],'Reviewer','Cannot accept exposed regression as independent pass',True)
        self.assertEqual(list(self.store.db.execute("SELECT id,revision,payload FROM training_records WHERE kind='QUALITY_HOLDOUT_USAGE' ORDER BY id")),consumption)
        self.assertEqual(list(self.store.db.execute("SELECT id,revision,payload FROM training_records WHERE kind='GROUP_ROLE' ORDER BY id")),roles)
        self.assertFalse(self.sets.validity(self.args[1])['valid']);self.assertEqual(self.store.count('SAMPLE'),0)

    def test_tampered_independence_or_root_receipt_cannot_freeze(self):
        plan=self.prepare();bad=copy.deepcopy(plan);bad['independence_claim']=True
        with self.assertRaises(ValueError):self.protocols.freeze(bad,'Reviewer',True)
        bad=copy.deepcopy(plan);bad['scope']['repair_review']['id']='invented-root-review'
        with self.assertRaises(ValueError):self.protocols.freeze(bad,'Reviewer',True)
        with self.assertRaises(ValueError):self.protocols.plan(*self.args,repair_review_id='invented-root-review')
        self.assertEqual(self.store.count('QUALITY_PROTOCOL'),1)

    def test_changed_truth_invalidates_replay_instead_of_silently_using_old_answers(self):
        plan=self.prepare();replay=self.protocols.freeze(plan,'Reviewer',True)
        facts=self.store.facts(self.work['id']);observations=copy.deepcopy(facts['observations']);observations[0]['text']='Synthetic corrected human truth'
        self.store.save_facts(self.work['id'],observations,facts['revision'],self.work['revision'])
        self.assertFalse(self.protocols.validity(replay['id'])['valid'])
        with self.assertRaises(ValueError):EvaluationJobs(self.library).create_pair(replay['id'],'Reviewer',True)

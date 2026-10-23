import sqlite3
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_quality_gold_sets as gold_fixture
import test_quality_policy as policy_fixture
from template_ai.quality_policy import QualityPolicies
from template_ai.quality_pipeline import QualityPipelines
from template_ai.quality_protocol import QualityProtocols
from template_ai.quality_jobs import EvaluationJobs,run_evaluation
from template_ai.runtime_queue import RuntimeQueue
from template_ai.runtime_worker import run_isolated
from template_ai.model import new_id
from test_runtime_execution import ALLOW,HOLD


class QualityJobTests(unittest.TestCase):
    setUp=gold_fixture.QualityGoldSetTests.setUp

    def build(self,two_sources=False):
        golds=[self.gold.confirm(gold_fixture.QualityGoldSetTests.plan(self),'Synthetic reviewer',True)]
        if two_sources:
            from training_fixture import source_work
            from test_noise_authoring import confirmed
            source,work=source_work(self.library,self.root,'alias.svg');confirmed(self.store,work)
            golds.append(self.gold.confirm(gold_fixture.QualityGoldSetTests.plan(self,work),'Synthetic reviewer',True))
        dataset=self.sets.create(self.sets.plan('Actual job synthetic holdout',[g['id'] for g in golds],True,True,'Reviewed as related content group'),'Reviewer',True)
        policies=QualityPolicies(self.library);policy_plan=policy_fixture.QualityPolicyTests.plan(SimpleNamespace(policy=lambda:policies));policy=policies.approve(policy_plan,'Reviewer',True)
        pipelines=QualityPipelines(self.library);left=pipelines.freeze('Actual baseline',None,'Reviewer',True);right=pipelines.freeze('Actual candidate',None,'Reviewer',True);protocols=QualityProtocols(self.library)
        plan=protocols.plan('Fixed real execution pair',dataset['id'],policy['id'],dict(BASELINE=left['id'],CANDIDATE=right['id']),'Fixed before any source score');protocol=protocols.freeze(plan,'Reviewer',True)
        self.service=EvaluationJobs(self.library);self.protocol=protocol;self.jobs=self.service.create_pair(protocol['id'],'Reviewer',True);return self.jobs

    def test_actual_fifo_isolated_children_execute_both_sides_and_keep_quality_insufficient(self):
        jobs=self.build();queue=RuntimeQueue(self.library);session=new_id()
        first=queue.enqueue('EVAL_JOB',jobs['BASELINE']['id'],'Reviewer',session,True);second=queue.enqueue('EVAL_JOB',jobs['CANDIDATE']['id'],'Reviewer',session,True)
        with self.assertRaises(ValueError):queue.claim(second,session)
        for request in (first,second):
            current=queue.get(request['id']);claimed=queue.claim(current,session)
            result=run_isolated(self.library.root,'EVAL_JOB',claimed['id'],claimed['owner_token'],admission=lambda:ALLOW)
            queue.finish(request['id'],claimed['owner_token'],result)
            self.assertEqual(result['phase'],'COMPLETED');receipt=self.store.get('QUALITY_EVAL_RESULT',result['result_id'])
            self.assertEqual(receipt['origin'],'ACTUAL_FIFO_SOURCE_EVALUATION');self.assertFalse(receipt['quality_pass']);self.assertEqual(receipt['quality_gate'],'EVIDENCE_INSUFFICIENT')
        self.assertEqual([r['state'] for r in queue.page()],['DONE','DONE']);self.assertEqual(self.store.count('SAMPLE'),0);self.assertEqual(self.library.templates(),[])

    def test_resource_pause_resumes_same_job_without_repredicting_committed_source(self):
        jobs=self.build(True);job=jobs['BASELINE'];claimed=self.service.claim(job['id'],job['revision'],True);decisions=iter([ALLOW,HOLD]);calls=[];original=QualityPipelines.predict_source
        def predict(service,pipeline,source):calls.append(source);return original(service,pipeline,source)
        with patch.object(QualityPipelines,'predict_source',new=predict):
            paused=run_evaluation(self.library.root,job['id'],claimed['owner_token'],admission=lambda:next(decisions))
            self.assertEqual(paused['phase'],'PAUSED_RESOURCES');self.assertEqual([i['state'] for i in paused['items']],['DONE','READY'])
            resumed=self.service.claim(job['id'],paused['revision'],True);done=run_evaluation(self.library.root,job['id'],resumed['owner_token'],admission=lambda:ALLOW)
        self.assertEqual(done['phase'],'COMPLETED');self.assertEqual(len(calls),2);self.assertEqual(len(set(calls)),2);self.assertEqual(self.store.count('QUALITY_EVAL_ITEM'),2)

    def test_cancel_before_first_source_saves_no_predictions_and_explicit_resume_works(self):
        job=self.build()['BASELINE'];claimed=self.service.claim(job['id'],job['revision'],True);cancel=threading.Event();cancel.set()
        cancelled=run_evaluation(self.library.root,job['id'],claimed['owner_token'],cancel)
        self.assertEqual(cancelled['phase'],'CANCELLED');self.assertEqual(self.store.count('QUALITY_PREDICTED_WORK'),0)
        resumed=self.service.claim(job['id'],cancelled['revision'],True);done=run_evaluation(self.library.root,job['id'],resumed['owner_token'])
        self.assertEqual(done['phase'],'COMPLETED')

    def test_atomic_result_audit_failure_never_leaves_prediction_or_fake_done(self):
        from template_ai.storage import Library
        job=self.build()['BASELINE'];claimed=self.service.claim(job['id'],job['revision'],True);event=Library.event
        def failed(library,identity,action):
            if action=='training_quality_source_result_and_progress_committed':raise sqlite3.OperationalError('synthetic disk full after result insertion')
            return event(library,identity,action)
        with patch.object(Library,'event',new=failed):
            with self.assertRaises(sqlite3.OperationalError):run_evaluation(self.library.root,job['id'],claimed['owner_token'])
        saved=self.service.get(job['id']);self.assertEqual(saved['phase'],'FAILED_SYSTEM');self.assertEqual(saved['items'][0]['state'],'READY');self.assertEqual(self.store.count('QUALITY_PREDICTED_WORK'),0);self.assertEqual(self.store.count('QUALITY_EVAL_ITEM'),0);self.assertIsNone(saved['result_id'])

    def test_queue_claim_receipt_failure_rolls_back_shared_lease_and_job(self):
        job=self.build()['BASELINE'];queue=RuntimeQueue(self.library);session=new_id();request=queue.enqueue('EVAL_JOB',job['id'],'Reviewer',session,True)
        with patch.object(queue,'_write',side_effect=sqlite3.OperationalError('synthetic queue receipt failure')):
            with self.assertRaises(sqlite3.OperationalError):queue.claim(request,session)
        self.assertEqual(self.service.get(job['id'])['phase'],'READY');self.assertEqual(queue.get(request['id'])['state'],'WAITING');self.assertFalse((self.store.get('WORKER','automatic-worker') or {}).get('active'));self.assertEqual(self.store.count('QUALITY_HOLDOUT_USAGE'),0)

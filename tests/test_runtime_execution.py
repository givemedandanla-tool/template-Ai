import unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_automatic_training as fixtures
from template_ai.automatic_training import run_automatic
from template_ai.runtime_resources import ResourceDecision

ALLOW=ResourceDecision(True,'READY',(),0,0,None)
HOLD=ResourceDecision(False,'PAUSED_RESOURCES',('SYNTHETIC_MEMORY_PRESSURE',),0,0,None)


class RuntimeAutomaticExecutionTests(unittest.TestCase):
    def test_source_registration_and_job_pointer_roll_back_together_on_audit_failure(self):
        from template_ai.storage import Library
        job=self.job();original=Library.event
        def fail(library,entity,action):
            if action=='training_automatic_source_registered_before_work_analysis':raise OSError('SYNTHETIC source-link disk full')
            return original(library,entity,action)
        with patch.object(Library,'event',fail),self.assertRaisesRegex(RuntimeError,'未一起提交'):self.execute(job,lambda:ALLOW)
        self.assertEqual(self.library.list_sources(),[]);self.assertEqual(self.service.store.count('AUTO_UNIT'),0);saved=self.service.get(job['id']);self.assertEqual(saved['phase'],'FAILED_SYSTEM');self.assertIsNone(saved['items'][0]['source_id']);self.assertFalse(self.service.store.get('WORKER','automatic-worker')['active'])
    setUp=fixtures.AutomaticTrainingTests.setUp
    tearDown=fixtures.AutomaticTrainingTests.tearDown
    job=fixtures.AutomaticTrainingTests.job

    def execute(self,job,admission):
        claimed=self.service.claim(job['id'],job['revision'],True);self.tokens.append(claimed['owner']['token'])
        return run_automatic(self.library.root,claimed['id'],claimed['owner']['token'],admission=admission)

    def test_pressure_before_first_source_releases_lease_and_does_not_register_or_approve(self):
        job=self.job();result=self.execute(job,lambda:HOLD)
        self.assertEqual(result['phase'],'PAUSED_RESOURCES');self.assertEqual(self.library.list_sources(),[])
        self.assertEqual(self.service.store.count('AUTO_UNIT'),0);self.assertFalse(self.service.store.get('WORKER','automatic-worker')['active'])
        self.assertEqual(result['items'][0]['state'],'READY');self.assertIn('SYNTHETIC_MEMORY_PRESSURE',result['system_error'])

    def test_pressure_after_first_durable_unit_preserves_it_and_resume_reuses_without_duplicate_sources(self):
        job=self.job()
        result=self.execute(job,lambda:HOLD if self.service.store.count('AUTO_UNIT') else ALLOW)
        self.assertEqual(result['phase'],'PAUSED_RESOURCES');self.assertEqual(self.service.store.count('AUTO_UNIT'),1)
        unit=self.service.store.records('AUTO_UNIT')[0];sources=self.library.list_sources();self.assertEqual(len(sources),1)
        original=self.path.read_bytes();finished=self.execute(result,lambda:ALLOW)
        self.assertEqual(finished['phase'],'COMPLETED_WITH_EXCEPTIONS');self.assertGreaterEqual(finished['items'][0]['reused_units'],1)
        self.assertEqual(self.service.store.get('AUTO_UNIT',unit['id']),unit);self.assertEqual(len(self.library.list_sources()),1)
        self.assertEqual(self.path.read_bytes(),original);self.assertIsNone(self.service.store.facts(unit['work_id'])['confirmation'])

    def test_pause_commit_audit_failure_is_failure_and_keeps_recoverable_running_state(self):
        job=self.job()
        from template_ai.storage import Library
        original=Library.event
        def fail(library,entity,action):
            if action in ('training_automatic_job_paused_resources','training_automatic_job_failed_system'):raise OSError('SYNTHETIC disk full')
            return original(library,entity,action)
        with patch.object(Library,'event',fail),self.assertRaises(OSError):self.execute(job,lambda:HOLD)
        saved=self.service.store.get('AUTO_JOB',job['id']);self.assertEqual(saved['phase'],'RUNNING');self.assertEqual(self.service.phase(saved),'INTERRUPTED')

import json,unittest
from unittest.mock import patch
import test_automatic_training as fixtures
from template_ai.runtime_queue import RuntimeQueue,scope_digest
from template_ai.automatic_training import run_automatic
from template_ai.model import new_id
from template_ai.training_pipeline import LIVE_OWNERS
from template_ai.storage import Library


class RuntimeQueueTests(unittest.TestCase):
    setUp=fixtures.AutomaticTrainingTests.setUp
    job=fixtures.AutomaticTrainingTests.job

    def tearDown(self):
        for session in getattr(self,'sessions',[]):LIVE_OWNERS.discard(session)
        fixtures.AutomaticTrainingTests.tearDown(self)

    def session(self):
        if not hasattr(self,'sessions'):self.sessions=[]
        token=new_id();self.sessions.append(token);return token

    def enqueue(self,session=None):
        if not hasattr(self,'queue'):self.queue=RuntimeQueue(self.library)
        job=self.job();return self.queue.enqueue('AUTO_JOB',job['id'],'SYNTHETIC_TEST',session or self.session(),True)

    def test_queue_bookkeeping_never_changes_learning_epoch_and_requires_scope_confirmation(self):
        job=self.job();self.queue=RuntimeQueue(self.library);epoch=self.service.store.epoch
        with self.assertRaises(ValueError):self.queue.enqueue('AUTO_JOB',job['id'],'SYNTHETIC_TEST',self.session())
        request=self.queue.enqueue('AUTO_JOB',job['id'],'SYNTHETIC_TEST',self.session(),True)
        self.assertEqual(self.service.store.epoch,epoch);self.queue.cancel_waiting(request['id'],request['revision']);self.assertEqual(self.service.store.epoch,epoch)

    def test_fifo_does_not_follow_wall_clock_and_atomic_claim_cannot_bypass_older_live_scope(self):
        session=self.session()
        with patch('time.time',return_value=1000):first=self.enqueue(session)
        with patch('time.time',return_value=100):second=self.enqueue(session)
        self.assertLess(first['seq'],second['seq']);epoch=self.service.store.epoch
        with self.assertRaises(ValueError):self.queue.claim(second,session)
        self.assertEqual(self.queue.get(second['id'])['state'],'WAITING');self.assertEqual(self.service.store.epoch,epoch)
        self.assertEqual(self.service.get(second['job_id'])['phase'],'READY')
        claimed=self.queue.claim(first,session);self.tokens.append(claimed['owner']['token']);self.assertEqual(self.queue.get(first['id'])['state'],'RUNNING')

    def test_scope_changed_request_is_blocked_and_next_eligible_is_not_starved(self):
        session=self.session();first=self.enqueue(session);second=self.enqueue(session)
        job=self.service.get(first['job_id']);job['items'][0]['page']=2
        with self.service.store.transaction():self.service.store._write('AUTO_JOB',job['id'],job,job['revision'],'synthetic_changed_scope')
        self.assertIsNone(self.queue.claim(first,session));self.assertEqual(self.queue.get(first['id'])['state'],'BLOCKED')
        claimed=self.queue.claim(second,session);self.tokens.append(claimed['owner']['token']);self.assertEqual(claimed['id'],second['job_id'])

    def test_dead_session_does_not_auto_resume_and_explicit_resume_keeps_original_arrival_rank(self):
        first=self.enqueue();old_session=first['consent_session'];LIVE_OWNERS.discard(old_session)
        self.assertEqual(self.queue.eligible(),[]);session=self.session()
        with self.assertRaises(ValueError):self.queue.claim(first,session)
        resumed=self.queue.enqueue('AUTO_JOB',first['job_id'],'SYNTHETIC_NEW_SESSION',session,True)
        self.assertEqual(resumed['seq'],first['seq']);self.assertEqual(resumed['id'],first['id']);self.assertEqual(self.queue.eligible(session)[0]['id'],first['id'])

    def test_other_window_cannot_duplicate_worker_and_stale_request_cas_rolls_back(self):
        session=self.session();first=self.enqueue(session)
        other=Library(self.library.root);self.addCleanup(other.close);queue=RuntimeQueue(other)
        claimed=self.queue.claim(first,session);self.tokens.append(claimed['owner']['token']);epoch=self.service.store.epoch
        with self.assertRaises(ValueError):queue.claim(first,session)
        self.assertEqual(self.service.store.epoch,epoch);self.assertEqual(queue.get(first['id'])['owner'],claimed['owner'])

    def test_queue_audit_failure_rolls_back_backend_claim_worker_lease_and_request(self):
        session=self.session();request=self.enqueue(session);epoch=self.service.store.epoch;event=self.library.event
        def fail(entity,action):
            if action=='runtime_queue_claimed_with_existing_worker_lease':raise OSError('SYNTHETIC disk full')
            return event(entity,action)
        with patch.object(self.library,'event',fail),self.assertRaises(OSError):self.queue.claim(request,session)
        self.assertEqual(self.queue.get(request['id'])['state'],'WAITING');self.assertEqual(self.service.get(request['job_id'])['phase'],'READY');self.assertEqual(self.service.store.epoch,epoch)
        self.assertIsNone(self.service.store.get('WORKER','automatic-worker'))

    def test_pressure_resume_uses_same_confirmed_scope_and_persisted_completed_units(self):
        import test_runtime_execution as execution
        session=self.session();request=self.enqueue(session);claimed=self.queue.claim(request,session);token=claimed['owner']['token'];self.tokens.append(token)
        paused=run_automatic(self.library.root,claimed['id'],token,admission=lambda:execution.HOLD if self.service.store.count('AUTO_UNIT') else execution.ALLOW)
        saved=self.queue.finish(request['id'],token,paused);self.assertEqual(saved['state'],'PAUSED_RESOURCES');self.assertEqual(saved['consent_session'],session)
        self.assertEqual(scope_digest('AUTO_JOB',paused),request['scope_digest']);claim=self.queue.claim(saved,session);self.tokens.append(claim['owner']['token'])
        result=run_automatic(self.library.root,claim['id'],claim['owner']['token']);self.queue.finish(saved['id'],claim['owner']['token'],result)
        self.assertEqual(self.queue.get(saved['id'])['state'],'DONE');self.assertGreaterEqual(result['items'][0]['reused_units'],1);self.assertEqual(len(self.library.list_sources()),1)

    def test_dead_running_request_is_recoverable_and_keeps_all_original_backend_results(self):
        session=self.session();request=self.enqueue(session);claimed=self.queue.claim(request,session);token=claimed['owner']['token'];LIVE_OWNERS.discard(token)
        before=self.service.get(request['job_id']);self.queue.recover_dead();saved=self.queue.get(request['id'])
        self.assertEqual(saved['state'],'INTERRUPTED');self.assertIsNone(saved['consent_session']);self.assertEqual(self.service.get(request['job_id']),before)
        self.assertEqual(self.service.phase(before),'INTERRUPTED')

    def test_real_timeout_isolates_only_active_source_then_continues_other_files_without_retrying_failure(self):
        import subprocess,sys
        from template_ai.runtime_worker import run_isolated,WorkerTimeout
        import test_runtime_execution as resources
        stalled=self.path.with_name('00000-stall.svg');stalled.write_bytes(self.path.read_bytes());job=self.job([stalled,self.path]);self.queue=RuntimeQueue(self.library);session=self.session();request=self.queue.enqueue('AUTO_JOB',job['id'],'SYNTHETIC_TIMEOUT',session,True,True);claimed=self.queue.claim(request,session);token=claimed['owner']['token']
        script="from template_ai.automatic_training import AutomaticTraining\noriginal=AutomaticTraining.run_source\ndef stalled(self,item,job,cancel=None,admission=None):\n    if item['path'].endswith('00000-stall.svg'):\n        self.db.execute('BEGIN IMMEDIATE')\n        self.db.execute(\"INSERT INTO preferences VALUES('synthetic_uncommitted_source','unsafe')\")\n        import time;time.sleep(30)\n    return original(self,item,job,cancel,admission)\nAutomaticTraining.run_source=stalled\nfrom template_ai.runtime_worker import child_main\nraise SystemExit(child_main())"
        def factory(command,**options):return subprocess.Popen([sys.executable,'-c',script,*command[command.index('--root'):]],**options)
        with self.assertRaises(WorkerTimeout):run_isolated(self.library.root,'AUTO_JOB',job['id'],token,admission=lambda:resources.ALLOW,unit_timeout=2.5,process_factory=factory)
        self.assertEqual(self.service.get(job['id'])['items'][0]['state'],'RUNNING');self.assertIsNone(self.library.db.execute("SELECT value FROM preferences WHERE key='synthetic_uncommitted_source'").fetchone())
        isolated=self.queue.isolate_timed_out(request['id'],token,'SYNTHETIC isolated timeout');self.assertEqual(isolated['phase'],'CONTINUATION_PENDING');self.assertEqual(isolated['items'][0]['state'],'FAILED')
        saved=self.queue.finish(request['id'],token,isolated);self.assertEqual(saved['state'],'WAITING');self.assertFalse(saved['retry_failed']);claimed=self.queue.claim(saved,session)
        result=run_isolated(self.library.root,'AUTO_JOB',job['id'],claimed['owner']['token'],admission=lambda:resources.ALLOW);self.queue.finish(request['id'],claimed['owner']['token'],result)
        self.assertEqual(result['items'][0]['state'],'FAILED');self.assertEqual(result['items'][0]['attempts'],1);self.assertEqual(result['items'][1]['state'],'WAITING_REVIEW');self.assertEqual(len(self.library.list_sources()),1);self.assertEqual(self.queue.get(request['id'])['state'],'DONE')

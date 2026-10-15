import json,subprocess,sys,threading,unittest
from pathlib import Path
import test_automatic_training as fixtures
from template_ai.runtime_worker import run_isolated
import test_runtime_execution as resources


class RuntimeWorkerTests(unittest.TestCase):
    setUp=fixtures.AutomaticTrainingTests.setUp
    tearDown=fixtures.AutomaticTrainingTests.tearDown
    job=fixtures.AutomaticTrainingTests.job

    def claim(self):
        job=self.job();claimed=self.service.claim(job['id'],job['revision'],True);self.tokens.append(claimed['owner']['token']);return claimed

    def test_real_subprocess_runs_existing_engine_and_returns_only_verified_committed_job(self):
        claimed=self.claim();progress=[]
        result=run_isolated(self.library.root,'AUTO_JOB',claimed['id'],claimed['owner']['token'],progress=progress.append,admission=lambda:resources.ALLOW)
        self.assertEqual(result['phase'],'COMPLETED_WITH_EXCEPTIONS');self.assertEqual(self.service.get(claimed['id']),result);self.assertTrue(progress);self.assertEqual(len(self.library.list_sources()),1)
        self.assertTrue(all(self.service.store.facts(unit['work_id'])['confirmation'] is None for unit in self.service.store.records('AUTO_UNIT')))

    def test_real_subprocess_pauses_at_boundary_and_reuses_saved_work_on_explicit_resume(self):
        claimed=self.claim()
        result=run_isolated(self.library.root,'AUTO_JOB',claimed['id'],claimed['owner']['token'],admission=lambda:resources.HOLD if self.service.store.count('AUTO_UNIT') else resources.ALLOW)
        self.assertEqual(result['phase'],'PAUSED_RESOURCES');self.assertEqual(self.service.store.count('AUTO_UNIT'),1)
        before=self.service.store.records('AUTO_UNIT')[0];claimed=self.service.claim(result['id'],result['revision'],True);self.tokens.append(claimed['owner']['token'])
        done=run_isolated(self.library.root,'AUTO_JOB',claimed['id'],claimed['owner']['token'],admission=lambda:resources.ALLOW)
        self.assertGreaterEqual(done['items'][0]['reused_units'],1);self.assertEqual(self.service.store.get('AUTO_UNIT',before['id']),before)

    def test_actual_stalled_process_is_killed_and_uncommitted_sqlite_write_rolls_back(self):
        claimed=self.claim();marker=self.root/'entered';database=self.library.root/'library.sqlite3'
        script="import sqlite3,time;from pathlib import Path;db=sqlite3.connect("+repr(str(database))+");db.execute('BEGIN IMMEDIATE');db.execute(\"INSERT INTO preferences VALUES('synthetic_uncommitted_stall','unsafe')\");Path("+repr(str(marker))+").write_text('ready');time.sleep(30)"
        processes=[]
        def factory(command,**options):
            process=subprocess.Popen([sys.executable,'-c',script],**options);processes.append(process);return process
        with self.assertRaisesRegex(RuntimeError,'安全邊界'):run_isolated(self.library.root,'AUTO_JOB',claimed['id'],claimed['owner']['token'],unit_timeout=1.5,process_factory=factory)
        self.assertTrue(marker.exists());self.assertIsNotNone(processes[0].poll());self.assertIsNone(self.library.db.execute("SELECT value FROM preferences WHERE key='synthetic_uncommitted_stall'").fetchone());self.assertEqual(self.service.get(claimed['id'])['phase'],'RUNNING')

    def test_truncated_or_unbound_success_protocol_never_marks_real_job_completed(self):
        claimed=self.claim()
        def factory(command,**options):return subprocess.Popen([sys.executable,'-c',"print('TEMPLATE_AI_RUNTIME_V1 '+"+repr(json.dumps(dict(type='RESULT',job_id=claimed['id'],revision=claimed['revision'],phase='COMPLETED')))+")"],**options)
        with self.assertRaisesRegex(RuntimeError,'不一致'):run_isolated(self.library.root,'AUTO_JOB',claimed['id'],claimed['owner']['token'],process_factory=factory)
        self.assertEqual(self.service.get(claimed['id'])['phase'],'RUNNING');self.assertEqual(self.library.list_sources(),[])

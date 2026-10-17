from gui_wait import dispose_main_window
import subprocess
import sys
import unittest
from unittest.mock import patch
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import test_quality_jobs as fixtures
from template_ai.gui import MainWindow
from template_ai.runtime_queue import RuntimeQueue
from template_ai.runtime_worker import run_isolated,WorkerTimeout
from template_ai.quality_jobs import run_evaluation
from template_ai.model import new_id
from runtime_fixture import controlled_resources
from test_runtime_execution import ALLOW

APP=QApplication.instance() or QApplication([])


class QualityDispatchTests(unittest.TestCase):
    setUp=fixtures.QualityJobTests.setUp
    build=fixtures.QualityJobTests.build

    def window(self):
        window=MainWindow(self.library.root);controlled_resources(window)
        def close():
            window.execution_queue.cancel_event.set();window.pool.waitForDone(5000);APP.processEvents();window.source=None;window.work=None;window.template=None;dispose_main_window(window)
        self.addCleanup(close);return window

    def wait(self,predicate,window):
        for _ in range(2000):
            APP.processEvents()
            if predicate():return
            QTest.qWait(10)
        self.fail('actual dispatcher did not finish: '+str(window.execution_queue.error))

    def test_actual_gui_dispatcher_uses_existing_fifo_worker_and_preserves_quality_boundary(self):
        jobs=self.build();window=self.window();dispatch=window.execution_queue
        a=dispatch.submit('EVAL_JOB',jobs['BASELINE'],'Synthetic reviewer');b=dispatch.submit('EVAL_JOB',jobs['CANDIDATE'],'Synthetic reviewer')
        self.wait(lambda:all(dispatch.queue.get(r['id'])['state']=='DONE' for r in (a,b)),window)
        for job in jobs.values():
            saved=self.service.get(job['id']);receipt=self.store.get('QUALITY_EVAL_RESULT',saved['result_id']);self.assertFalse(receipt['quality_pass']);self.assertEqual(receipt['declared_logical_files'],1)
        self.assertIsNone(dispatch.error);self.assertEqual(self.store.count('SAMPLE'),0)

    def test_actual_pool_launch_failure_releases_eval_lease_without_false_source_result(self):
        job=self.build()['BASELINE'];window=self.window();dispatch=window.execution_queue
        with patch.object(window.pool,'start',side_effect=RuntimeError('synthetic quality worker launch failure')):
            request=dispatch.submit('EVAL_JOB',job,'Synthetic reviewer');self.wait(lambda:dispatch.queue.get(request['id'])['state']=='BLOCKED',window)
        self.assertEqual(self.service.get(job['id'])['phase'],'FAILED_SYSTEM');self.assertFalse(self.store.get('WORKER','automatic-worker')['active']);self.assertEqual(self.store.count('QUALITY_EVAL_ITEM'),0)

    def test_real_owned_stalled_child_kill_rolls_back_then_persists_last_failed_source_receipt(self):
        job=self.build()['BASELINE'];queue=RuntimeQueue(self.library);session=new_id();request=queue.enqueue('EVAL_JOB',job['id'],'Reviewer',session,True);claimed=queue.claim(request,session);token=claimed['owner_token']
        with self.store.transaction():
            current=self.service.owned(job['id'],token);current['items'][0]['state']='RUNNING';self.store._write('EVAL_JOB',job['id'],current,current['revision'],'synthetic_durable_source_begin_before_stall')
        code="import sqlite3,sys,time;d=sqlite3.connect(sys.argv[1]);d.execute('BEGIN IMMEDIATE');d.execute(\"INSERT INTO preferences VALUES('quality_uncommitted_stall','1')\");time.sleep(30)"
        processes=[]
        def factory(command,**kwargs):
            process=subprocess.Popen([sys.executable,'-c',code,str(self.library.root/'library.sqlite3')],**kwargs);processes.append(process);return process
        with self.assertRaises(WorkerTimeout):run_isolated(self.library.root,'EVAL_JOB',job['id'],token,process_factory=factory,unit_timeout=.25)
        self.assertIsNotNone(processes[0].poll());self.assertIsNone(self.library.db.execute("SELECT value FROM preferences WHERE key='quality_uncommitted_stall'").fetchone())
        isolated=queue.isolate_timed_out(request['id'],token,'Synthetic real child timeout, no model prediction')
        self.assertEqual(isolated['phase'],'CONTINUATION_PENDING');queue.finish(request['id'],token,isolated)
        resumed=queue.claim(queue.get(request['id']),session);done=run_evaluation(self.library.root,job['id'],resumed['owner_token'],admission=lambda:ALLOW);queue.finish(request['id'],resumed['owner_token'],done)
        receipt=self.store.get('QUALITY_EVAL_RESULT',done['result_id']);self.assertEqual(done['phase'],'COMPLETED_WITH_EXCEPTIONS');self.assertEqual(receipt['required_source_pages_or_unparsed_files'],1);self.assertEqual(receipt['declared_gold_objects'],5);self.assertFalse(receipt['quality_pass'])
        source=self.store.get('QUALITY_EVAL_ITEM',receipt['source_results'][0]['id']);self.assertEqual(source['origin'],'DURABLE_FAILED_UNIT_NO_PREDICTION');self.assertEqual(source['prediction_ids'],[])

    def test_actual_encrypted_backup_restore_clears_eval_owner_and_requires_explicit_resume(self):
        from template_ai import relational_backup as backup
        from template_ai.storage import Library
        from template_ai.training_store import TrainingStore
        job=self.build()['BASELINE'];claimed=self.service.claim(job['id'],job['revision'],True)
        archive=self.root/'quality-backup.tabi';plan=backup.plan_backup(self.library,include_sources=True)
        self.assertTrue(plan['complete'],plan.get('notes'));backup.create_backup(self.library,archive,'synthetic quality backup password',plan,True)
        report=backup.restore_bundle(archive,self.root/'quality-restored','synthetic quality backup password',True)
        restored=Library(report['library_root'])
        try:
            row=TrainingStore(restored).get('EVAL_JOB',job['id']);self.assertEqual(row['phase'],'INTERRUPTED');self.assertIsNone(row['owner']);self.assertIsNone(row['owner_token']);self.assertEqual(row['restore_state'],'EXPLICIT_RESUME_REQUIRED')
        finally:restored.close()
        self.assertEqual(self.service.get(job['id'])['owner_token'],claimed['owner_token'])

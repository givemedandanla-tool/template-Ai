import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import test_automatic_training as fixtures
from template_ai.gui import MainWindow
from template_ai.runtime_panel import RuntimePanel
from runtime_fixture import controlled_resources

APP=QApplication.instance() or QApplication([])


class RuntimeDispatchTests(unittest.TestCase):
    job=fixtures.AutomaticTrainingTests.job

    def setUp(self):
        fixtures.AutomaticTrainingTests.setUp(self);self.window=MainWindow(self.library.root);controlled_resources(self.window);self.dispatch=self.window.execution_queue;self.panels=[]

    def tearDown(self):
        self.dispatch.cancel_event.set();self.window.pool.waitForDone(5000);APP.processEvents()
        for panel in self.panels:panel.close()
        self.window.source=None;self.window.work=None;self.window.template=None;self.window.close();fixtures.AutomaticTrainingTests.tearDown(self)

    def wait(self,predicate):
        for _ in range(1500):
            APP.processEvents()
            if predicate():return
            QTest.qWait(10)
        self.fail('bounded runtime dispatch did not reach expected state: '+str(self.dispatch.error))

    def test_actual_pause_gui_preserves_pending_request_then_resume_runs_and_keeps_human_review_pending(self):
        panel=RuntimePanel(self.window);self.panels.append(panel);panel.show();QTest.mouseClick(panel.pause,Qt.LeftButton)
        job=self.job();request=self.dispatch.submit('AUTO_JOB',job,'SYNTHETIC_UI');APP.processEvents();panel.refresh()
        self.assertEqual(self.dispatch.queue.get(request['id'])['state'],'WAITING');self.assertEqual(self.service.get(job['id'])['phase'],'READY');self.assertEqual(panel.queue_table.rowCount(),1)
        QTest.mouseClick(panel.resume,Qt.LeftButton);self.wait(lambda:self.dispatch.queue.get(request['id'])['state']=='DONE')
        saved=self.service.get(job['id']);self.assertEqual(saved['phase'],'COMPLETED_WITH_EXCEPTIONS');self.assertTrue(all(self.service.store.facts(unit['work_id'])['confirmation'] is None for unit in self.service.store.records('AUTO_UNIT')))

    def test_multiple_actual_jobs_run_fifo_and_cancelled_waiting_scope_never_claims(self):
        self.window.runtime.set_paused(True);jobs=[self.job() for _ in range(3)];requests=[self.dispatch.submit('AUTO_JOB',job,'SYNTHETIC_FIFO') for job in jobs];finished=[];self.dispatch.finished.connect(lambda identity,result:finished.append(identity))
        self.dispatch.cancel(requests[1]['id']);self.assertEqual(self.service.get(jobs[1]['id'])['phase'],'READY');self.assertEqual(self.dispatch.queue.get(requests[1]['id'])['state'],'CANCELLED')
        self.window.runtime.set_paused(False);self.wait(lambda:self.dispatch.queue.get(requests[2]['id'])['state']=='DONE')
        self.assertLess(finished.index(requests[0]['id']),finished.index(requests[2]['id']));self.assertFalse(self.window.busy);self.assertIsNone(self.dispatch.active)

    def test_actual_pool_launch_failure_is_visible_and_requires_explicit_retry_without_auto_loop(self):
        job=self.job()
        with patch.object(self.window.pool,'start',side_effect=RuntimeError('SYNTHETIC pool launch failure')):
            request=self.dispatch.submit('AUTO_JOB',job,'SYNTHETIC_FAILURE');self.wait(lambda:self.dispatch.queue.get(request['id'])['state']=='BLOCKED')
        self.assertIn('pool launch failure',self.dispatch.queue.get(request['id'])['message']);self.assertEqual(self.service.phase(self.service.get(job['id'])),'INTERRUPTED');self.dispatch.dispatch();self.assertFalse(self.window.busy)
        retry=self.dispatch.submit('AUTO_JOB',self.service.get(job['id']),'SYNTHETIC_EXPLICIT_RETRY');self.assertGreater(retry['seq'],request['seq']);self.wait(lambda:self.dispatch.queue.get(retry['id'])['state']=='DONE')

    def test_closed_project_stops_real_timers_and_keeps_pending_backend_scope_unmodified(self):
        self.window.runtime.set_paused(True);job=self.job();request=self.dispatch.submit('AUTO_JOB',job,'SYNTHETIC_CLOSE');panel=RuntimePanel(self.window);self.panels.append(panel)
        self.window.library.close();APP.processEvents();self.assertTrue(self.dispatch.closed);self.assertFalse(self.dispatch.timer.isActive());self.assertFalse(panel.timer.isActive());self.assertFalse(panel.restore.isEnabled())
        self.assertEqual(self.service.get(job['id'])['phase'],'READY');self.assertEqual(self.dispatch.queue.library.closed,True)
        self.assertEqual(self.library.db.execute('SELECT count(*) FROM runtime_requests').fetchone()[0],1)

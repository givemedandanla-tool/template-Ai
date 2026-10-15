import threading,unittest
from unittest.mock import patch
from PySide6.QtTest import QTest
from template_ai.automatic_training import AutomaticTraining
from template_ai.automatic_training_dialog import AutomaticTrainingDialog
from template_ai.source_links import ScanCancelled
import test_automatic_training as fixture
APP=fixture.APP

class PreflightProgressTests(unittest.TestCase):
    setUp=fixture.AutomaticTrainingTests.setUp
    tearDown=fixture.AutomaticTrainingTests.tearDown
    window=fixture.AutomaticTrainingGuiTests.window

    def test_preflight_true_hash_progress_cancel_keeps_database_and_original_unchanged(self):
        event=threading.Event();seen=[];raw=self.path.read_bytes();before=self.library.db.total_changes
        def progress(row):seen.append(row);event.set()
        with self.assertRaises(ScanCancelled):self.service.preflight([self.path],cancel=event,progress=progress)
        self.assertEqual(seen,[dict(stage='來源雜湊',done=1,total=1,path=str(self.path))]);self.assertEqual(self.library.db.total_changes,before);self.assertEqual(self.path.read_bytes(),raw)

    def test_actual_preflight_escape_cancels_safely_and_shows_no_learned_job(self):
        window=self.window();d=AutomaticTrainingDialog(window);self.addCleanup(d.deleteLater);entered=threading.Event()
        def scan(service,paths,**kwargs):
            entered.set();kwargs['progress'](dict(stage='來源雜湊',done=1,total=2,path=str(self.path)))
            if not kwargs['cancel'].wait(3):raise AssertionError('cancel not delivered')
            raise ScanCancelled()
        with patch.object(AutomaticTraining,'preflight',scan):
            d.preflight([self.path]);self.assertTrue(entered.wait(2));d.reject()
            for _ in range(300):
                APP.processEvents();QTest.qWait(10)
                if not d.running:break
        self.assertFalse(d.running);self.assertFalse(window.busy);self.assertIn('取消',d.status.text());self.assertIsNone(d.report);self.assertEqual(d.service.store.count('AUTO_JOB'),0);self.assertFalse(d.start_button.isEnabled())

    def test_persistent_jobs_are_paged_and_not_limited_to_first_two_hundred(self):
        window=self.window();d=AutomaticTrainingDialog(window);self.addCleanup(d.deleteLater)
        with d.service.store.transaction():
            for index in range(205):d.service.store._write('AUTO_JOB','synthetic-job-'+str(index).zfill(3),dict(phase='READY',items=[],owner=None),0,'synthetic_fixture')
        d.reload();self.assertEqual(d.jobs.count(),200);d.job_page(200);self.assertEqual(d.jobs.count(),5);self.assertEqual(d.jobs.itemData(0),'synthetic-job-200');d.job_page(-200);self.assertEqual(d.jobs.count(),200)

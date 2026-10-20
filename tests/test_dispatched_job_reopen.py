"""Actual scan/training dialogs reopen the exact persisted job without starting work."""
import unittest
import test_source_watch_center as fixture_source
from template_ai.source_scan import record_dispatch


class DispatchedJobReopenTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_source.SourceWatchCenterTests()
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;f.scan();self.selected=f.select(lambda row:True);f.dialog.launch()
        self.child=f.dialog.training_dialog;f.wait(lambda:not self.child.running and not f.window.busy)
        self.target=self.child.service.create(self.child.report,'AUTHORED_REOPEN',True)
        record_dispatch(f.store,self.selected,self.target['id'])
        self.decoy=self.child.service.create(self.child.report,'AUTHORED_OTHER_JOB',True)
        f.select(lambda row:row['state']=='DISPATCHED');self.child.reload()
        self.child.jobs.setCurrentIndex(self.child.jobs.findData(self.decoy['id']))

    def test_reopen_dispatched_job_selects_exact_offpage_job_without_starting(self):
        f=self.fixture;before=f.store.count('AUTO_JOB');target_before=f.store.get('AUTO_JOB',self.target['id'])
        self.child.job_offset=200;self.child.reload();self.assertEqual(self.child.jobs.count(),0)
        f.dialog.launch()
        self.assertEqual(self.child.jobs.currentData(),self.target['id'])
        self.assertEqual(self.child.table.rowCount(),len(target_before['items']))
        self.assertEqual(f.store.get('AUTO_JOB',self.target['id']),target_before)
        self.assertEqual(f.store.count('AUTO_JOB'),before);self.assertFalse(self.child.running);self.assertFalse(f.window.busy)
        self.assertIn('確切既有工作',f.dialog.status.text())

    def test_reopen_does_not_change_different_running_job(self):
        f=self.fixture;self.child.running=True
        try:
            f.dialog.launch()
            self.assertEqual(self.child.jobs.currentData(),self.decoy['id'])
            self.assertTrue(self.child.running);self.assertIn('進行',f.dialog.status.text())
        finally:self.child.running=False

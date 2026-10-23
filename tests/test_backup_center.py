"""Actual Qt, background SQLite connections, encrypted files and safe lifecycle."""
from gui_wait import dispose_main_window,wait_for_gui
from runtime_fixture import controlled_resources
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication,QMessageBox
from template_ai.gui import MainWindow
from template_ai.backup_center import BackupManagerDialog
from template_ai import relational_backup as bundle,backup_policy as policy
from template_ai.customers import CustomerStore
from template_ai.storage import Library
import test_customer_candidates as fixture

APP=QApplication.instance() or QApplication([])
PASSWORD='synthetic Qt backup password'


class BackupCenterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.window=MainWindow(self.root/'library');controlled_resources(self.window);self.dialog=BackupManagerDialog(self.window)
        self.errors=[];self.old_hook=sys.excepthook
        def hook(kind,value,tb):self.errors.append(str(value));self.old_hook(kind,value,tb)
        sys.excepthook=hook

    def tearDown(self):
        self.dialog.cancel_event.set();self.window.backup_scheduler.cancel_event.set()
        self.window.pool.waitForDone(30000);APP.processEvents()
        self.dialog.reject();self.dialog.deleteLater();dispose_main_window(self.window)
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);APP.processEvents()
        sys.excepthook=self.old_hook;self.temp.cleanup();self.assertEqual(self.errors,[])

    def wait(self,predicate=None):
        predicate=predicate or (lambda:not self.dialog.running and not self.window.busy)
        if not wait_for_gui(predicate,15):self.fail('Qt background operation did not finish: '+self.dialog.status.text())

    def data(self):
        case=fixture.CustomerCandidateTests();case.library=self.window.library;case.root=self.root
        case.store=CustomerStore(case.library)
        from template_ai.customer_candidates import CustomerCandidates
        case.candidates=CustomerCandidates(case.store)
        source,work,template=case.make_source('00123.svg')
        reviewed=case.reviewed(case.candidates.propose(source['id'])[0]);case.commit([reviewed])
        return case.store.search('00123',field='CODE')[0]

    def create(self,full=True):
        self.dialog.sources.setChecked(full);self.dialog.fonts.setChecked(full);self.dialog.password.setText(PASSWORD)
        self.dialog.preview_backup();self.wait();self.assertIsNotNone(self.dialog.backup_plan)
        path=self.root/'actual-Qt-backup.tabi'
        with patch('template_ai.backup_center.QFileDialog.getSaveFileName',return_value=(str(path),'')),patch('template_ai.backup_center.QMessageBox.question',return_value=QMessageBox.Yes):self.dialog.create()
        self.wait();return path

    def test_real_gui_backup_receipt_test_restore_and_new_copy_keep_original_customer_and_template(self):
        customer=self.data();before=self.window.library.template_snapshots();archive=self.create()
        self.assertTrue(archive.is_file(),self.dialog.status.text());self.assertEqual(len(policy.history(self.window.library)),1)
        self.assertEqual(self.dialog.password.text(),'')
        self.dialog.history_tree.setCurrentItem(self.dialog.history_tree.topLevelItem(0));self.dialog.password.setText(PASSWORD)
        self.dialog.test_restore();self.wait()
        self.assertTrue(policy.history(self.window.library)[0]['test_restore'],self.dialog.status.text())
        self.dialog.archive.setText(str(archive));self.dialog.trusted.setChecked(True);self.dialog.mode.setCurrentIndex(1);self.dialog.password.setText(PASSWORD)
        self.dialog.preview_restore();self.wait()
        self.assertIsNotNone(self.dialog.restore_plan,self.dialog.status.text());self.assertFalse(self.dialog.restore_ack.isChecked())
        self.dialog.restore_ack.setChecked(True)
        with patch('template_ai.backup_center.QFileDialog.getExistingDirectory',return_value=str(self.root)),patch('template_ai.backup_center.QInputDialog.getText',return_value=('restored-copy',True)),patch('template_ai.backup_center.QMessageBox.question',return_value=QMessageBox.Yes):self.dialog.restore()
        self.wait();self.assertIsNotNone(self.dialog.last_restore,self.dialog.status.text())
        restored=Library(self.dialog.last_restore['library_root'])
        try:self.assertEqual(CustomerStore(restored).get(customer['id'])['fields'],customer['fields'])
        finally:restored.close()
        self.assertEqual(CustomerStore(self.window.library).get(customer['id'])['fields'],customer['fields'])
        self.assertEqual(self.window.library.template_snapshots(),before)
        with patch('template_ai.backup_center.QProcess.startDetached',return_value=(True,12345)) as launch:self.dialog.open_copy()
        self.assertIn('--data-dir',launch.call_args.args[1]);self.assertEqual(launch.call_args.args[1][-1],self.dialog.last_restore['library_root'])
        self.assertNotIn(PASSWORD,str(self.window.library.db.execute('SELECT value FROM preferences').fetchall()))

    def test_partial_scope_and_shared_database_dependency_never_become_silent_full_success(self):
        self.data();path=self.create(full=False)
        self.assertFalse(path.exists());self.assertIn('部分備份',self.dialog.status.text())
        self.assertEqual(policy.history(self.window.library),[])
        self.dialog.groups['customers'].setChecked(False);self.dialog.preview_backup();self.wait()
        self.assertEqual(self.dialog.backup_plan['state'],'BLOCKED_DATABASE_CATEGORY_DEPENDENCY')
        self.assertFalse(self.dialog.create_button.isEnabled())

    def test_actual_background_cancel_keeps_user_files_and_releases_shared_worker(self):
        (self.window.library.assets/'large.bin').write_bytes(b'fixture'*(1024*1024))
        self.dialog.password.setText(PASSWORD);self.dialog.preview_backup();self.wait()
        target=self.root/'cancelled.tabi';user=self.root/'user-file.txt';user.write_text('keep')
        with patch('template_ai.backup_center.QFileDialog.getSaveFileName',return_value=(str(target),'')),patch('template_ai.backup_center.QMessageBox.question',return_value=QMessageBox.Yes):self.dialog.create()
        self.dialog.cancel_work();self.wait()
        self.assertFalse(target.exists());self.assertEqual(user.read_text(),'keep');self.assertFalse(self.window.busy)

    def test_schedule_waits_for_key_and_idle_runs_one_real_backup_and_stops_before_library_close(self):
        self.data();destination=self.root/'drive';destination.mkdir()
        record=policy.configure(self.window.library,destination,60,retain_count=2,options=dict(include_sources=True,include_fonts=True),now=0)
        scheduler=self.window.backup_scheduler;scheduler.refresh();scheduler.tick(now=time.time())
        self.assertFalse(scheduler.running);self.assertIn('密碼',scheduler.status)
        self.window.busy=True;scheduler.set_session_password(PASSWORD);scheduler.tick(now=time.time())
        self.assertFalse(scheduler.running);self.assertIn('等待',scheduler.status)
        self.window.busy=False;scheduler.tick(now=time.time());self.wait(lambda:not scheduler.running and not self.window.busy)
        current=policy.schedule(self.window.library)
        self.assertEqual(current['state'],'SUCCESS',scheduler.status);self.assertIsNotNone(current['last_success'])
        self.assertEqual(len(policy.history(self.window.library)),1)
        self.assertNotIn(PASSWORD,str(self.window.library.db.execute('SELECT value FROM preferences').fetchall()))
        destination.rename(self.root/'drive-offline');scheduler.tick(now=current['next_due']+1)
        self.assertIn('離線',scheduler.status);self.assertEqual(policy.schedule(self.window.library)['last_success'],current['last_success'])
        scheduler.shutdown();self.assertFalse(scheduler.timer.isActive());self.assertIsNone(scheduler._password)
        scheduler.tick();self.assertFalse(scheduler.running)

    def test_wrong_password_attempts_are_bounded_across_tabs_without_writes(self):
        plan=bundle.plan_backup(self.window.library);archive=self.root/'known.tabi'
        bundle.create_backup(self.window.library,archive,PASSWORD,plan,True)
        self.dialog.archive.setText(str(archive));self.dialog.trusted.setChecked(True)
        for index in range(3):
            self.dialog.password.setText('wrong password '+str(index));self.dialog.preview_restore();self.wait()
        self.assertEqual(self.dialog.failures[str(archive.resolve())],3)
        self.dialog.password.setText(PASSWORD);self.dialog.preview_restore()
        self.assertFalse(self.dialog.running);self.assertIn('3次',self.dialog.status.text());self.assertIsNone(self.dialog.restore_plan)

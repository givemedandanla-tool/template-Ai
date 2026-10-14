import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox,QFileDialog
from template_ai.storage import Library
from template_ai.batch_import import BatchStore,preflight,convert_item,MAX_BYTES
from template_ai.batch_dialog import BatchImportDialog
from template_ai.gui import MainWindow
APP=QApplication.instance() or QApplication([])


def svg(path,color='red'):
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm"><rect width="20" height="20" fill="{color}"/></svg>');return path


class BatchImportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.lib=Library(self.root/'data');self.addCleanup(lambda:self.lib.close());self.store=BatchStore(self.lib);self.paths=[svg(self.root/'a.svg'),svg(self.root/'b.svg','blue')]
    def batch(self,paths=None):return self.store.create(preflight(paths or self.paths,self.lib.list_sources()),True)
    def execute(self,b,i=0):
        r=b['items'][i];b=self.store.claim(b['id'],b['revision'],r['id']);return self.store.finish(b['id'],b['revision'],r['id'],convert_item(r,self.lib.assets))
    def test_preflight_exact_duplicates_keep_paths_and_no_visual_guess(self):
        third=self.root/'copy.svg';third.write_bytes(self.paths[0].read_bytes());before=[p.read_bytes() for p in self.paths]
        r=preflight([self.root],[]);self.assertEqual(r['file_duplicates'],1);self.assertEqual(len(r['items']),3);self.assertEqual(r['artwork_duplicates'],'UNKNOWN');self.assertEqual(r['template_similarity'],'UNKNOWN');self.assertEqual(self.lib.list_sources(),[]);self.assertEqual(before,[p.read_bytes() for p in self.paths])
        with self.assertRaisesRegex(ValueError,'確認'):self.store.create(r)
    def test_health_reuse_recheck_and_no_duplicate_registration(self):
        b=self.execute(self.batch([self.paths[0]]));b=self.store.stop(b['id'],b['revision']);source=self.lib.list_sources()[0]
        r=preflight([self.paths[0]],self.lib.list_sources());self.assertEqual(r['reuse_candidates'],1)
        reused=self.execute(self.store.create(r,True));self.assertEqual(reused['items'][0]['status'],'REUSED');self.assertEqual(len(self.lib.list_sources()),1)
        self.store.stop(reused['id'],reused['revision']);r=preflight([self.paths[0]],self.lib.list_sources());Path(source['image']).write_bytes(b'corrupted')
        with self.assertRaisesRegex(ValueError,'CACHE_CHANGED'):convert_item(r['items'][0],self.lib.assets)
        self.assertEqual(preflight([self.paths[0]],self.lib.list_sources())['reuse_candidates'],0)
    def test_source_changed_before_and_during_conversion_never_committed(self):
        b=self.batch([self.paths[0]]);r=b['items'][0];svg(self.paths[0],'green')
        with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED'):convert_item(r,self.lib.assets)
        b=self.batch([self.paths[0]]);r=b['items'][0]
        from template_ai.importer import import_file
        def changed(p,assets,page):
            result=import_file(p,assets,page);svg(p,'yellow');return result
        with patch('template_ai.batch_import.import_file',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'變更|SOURCE_CHANGED|異動'):convert_item(r,self.lib.assets)
        self.assertEqual(self.lib.list_sources(),[])
    def test_cancel_resume_reopen_successes_preserved_once(self):
        b=self.execute(self.batch());b=self.store.stop(b['id'],b['revision'],True);self.assertEqual([r['status'] for r in b['items']],['SUCCESS','READY']);source_id=b['items'][0]['source_id']
        self.lib.close();self.lib=Library(self.root/'data');self.store=BatchStore(self.lib);self.store.recover();b=self.store.get(b['id']);b=self.execute(b,1);b=self.store.stop(b['id'],b['revision']);self.assertEqual(b['phase'],'DONE');self.assertEqual(b['items'][0]['source_id'],source_id);self.assertEqual([r['attempts'] for r in b['items']],[1,1]);self.assertEqual(len(self.lib.list_sources()),2)
    def test_individual_failure_isolation_and_real_counts(self):
        b=self.batch();r=b['items'][0];b=self.store.claim(b['id'],b['revision'],r['id']);b=self.store.finish(b['id'],b['revision'],r['id'],error='parse failure');b=self.execute(b,1);b=self.store.stop(b['id'],b['revision']);self.assertEqual(b['phase'],'DONE_WITH_ERRORS');self.assertEqual([r['status'] for r in b['items']],['FAILED','SUCCESS']);self.assertEqual(len(self.lib.list_sources()),1);self.assertTrue(b['items'][0]['history'])
    def test_cas_owner_live_recovery_and_dead_session(self):
        b=self.batch();b=self.store.claim(b['id'],b['revision'],b['items'][0]['id'])
        self.assertEqual(self.store.recover(),[])
        other=Library(self.root/'data');other_store=BatchStore(other);self.assertEqual(other_store.recover(),[])
        with self.assertRaisesRegex(ValueError,'執行者'):other_store.finish(b['id'],b['revision'],b['items'][0]['id'],error='fake')
        with self.assertRaisesRegex(ValueError,'尚未完成'):self.store.claim(b['id'],b['revision'],b['items'][0]['id'])
        self.lib.close();self.lib=other;self.store=other_store;recovered=self.store.recover();self.assertEqual(len(recovered),1);self.assertEqual(recovered[0]['items'][0]['status'],'INTERRUPTED');self.assertEqual(recovered[0]['items'][1]['status'],'READY')
        with self.assertRaisesRegex(ValueError,'變更'):self.store.stop(b['id'],b['revision'])
    def test_late_audit_rolls_back_source_and_result_then_can_recover(self):
        b=self.batch([self.paths[0]]);r=b['items'][0];b=self.store.claim(b['id'],b['revision'],r['id']);result=convert_item(r,self.lib.assets)
        with patch.object(self.lib,'event',side_effect=RuntimeError('late audit')):
            with self.assertRaisesRegex(RuntimeError,'late audit'):self.store.finish(b['id'],b['revision'],r['id'],result)
        self.assertEqual(self.lib.list_sources(),[]);self.assertEqual(self.store.get(b['id']),b)
        b=self.store.finish(b['id'],b['revision'],r['id'],result);self.assertEqual(b['items'][0]['status'],'SUCCESS')
    def test_other_live_session_cannot_take_over_between_items(self):
        b=self.execute(self.batch());other=Library(self.root/'data');self.addCleanup(other.close);store=BatchStore(other)
        with self.assertRaisesRegex(ValueError,'執行者'):store.claim(b['id'],b['revision'],b['items'][1]['id'])
        with self.assertRaisesRegex(ValueError,'執行者'):store.stop(b['id'],b['revision'])
        self.assertEqual(self.store.get(b['id']),b);b=self.execute(b,1);self.assertEqual(b['items'][1]['status'],'SUCCESS')
    def test_bounded_folder_files_cancel_page_and_final_cache_changed(self):
        with self.assertRaisesRegex(ValueError,'頁次'):preflight(self.paths,[],0)
        for i in range(201):svg(self.root/f'limit{i}.svg')
        with self.assertRaisesRegex(ValueError,'200'):preflight([self.root],[])
        huge=self.root/'huge.svg'
        with huge.open('wb') as f:f.truncate(MAX_BYTES+1)
        self.assertEqual(preflight([huge],[])['items'][0]['status'],'FAILED')
        b=self.batch([self.paths[0]]);r=b['items'][0];b=self.store.claim(b['id'],b['revision'],r['id']);result=convert_item(r,self.lib.assets);Path(result['payload']['image']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'變更'):self.store.finish(b['id'],b['revision'],r['id'],result)
        self.assertEqual(self.lib.list_sources(),[])


class BatchImportGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.window=MainWindow(self.root/'data');self.addCleanup(lambda:self.window.close());self.paths=[svg(self.root/'a.svg'),svg(self.root/'b.svg','blue')];self.dlg=BatchImportDialog(self.window);self.dlg.show();APP.processEvents();self.addCleanup(lambda:self.dlg.close())
    def wait_for(self,predicate,seconds=10):
        end=time.monotonic()+seconds
        while not predicate() and time.monotonic()<end:QTest.qWait(10)
        self.assertTrue(predicate(),self.dlg.status.text())
    def scan(self):
        with patch.object(QFileDialog,'getOpenFileNames',return_value=([str(p) for p in self.paths],'')):QTest.mouseClick(self.dlg.choose_files,Qt.LeftButton)
        QTest.mouseClick(self.dlg.scan_button,Qt.LeftButton);self.wait_for(lambda:not self.dlg.busy);self.assertIsNotNone(self.dlg.report)
    def test_real_preflight_confirmation_background_progress_and_source_locate(self):
        self.scan();self.assertEqual(self.dlg.table.rowCount(),2)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):QTest.mouseClick(self.dlg.start_button,Qt.LeftButton)
        self.assertEqual(self.window.import_store.list(),[])
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.dlg.start_button,Qt.LeftButton)
        self.wait_for(lambda:not self.dlg.running and not self.dlg.busy);self.assertEqual(self.dlg.batch['phase'],'DONE');self.assertEqual(self.dlg.progress.value(),2);self.assertTrue(self.dlg.choose_files.isEnabled());self.dlg.table.selectRow(0);QTest.mouseClick(self.dlg.locate_button,Qt.LeftButton);self.assertEqual(self.window.source['id'],self.dlg.batch['items'][0]['source_id']);self.assertFalse(self.window.source['visual_confirmed'])
    def test_actual_cooperative_cancel_history_reopen_resume_and_close_guard(self):
        self.scan();entered=threading.Event();release=threading.Event()
        def gated(item,assets):entered.set();release.wait(4);return convert_item(item,assets)
        with patch('template_ai.batch_dialog.convert_item',side_effect=gated):
            with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.dlg.start_button,Qt.LeftButton)
            self.wait_for(entered.is_set);self.dlg.reject();self.assertTrue(self.dlg.isVisible());self.assertTrue(self.dlg.cancel_requested);release.set();self.wait_for(lambda:not self.dlg.running and not self.dlg.busy)
        bid=self.dlg.batch['id'];self.assertEqual([r['status'] for r in self.dlg.batch['items']],['SUCCESS','READY']);self.dlg.close();self.window.close();self.window=MainWindow(self.root/'data');self.dlg=BatchImportDialog(self.window);self.dlg.show();self.dlg.history.setCurrentIndex(self.dlg.history.findData(bid));self.assertTrue(self.dlg.resume_button.isEnabled())
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.dlg.resume_button,Qt.LeftButton)
        self.wait_for(lambda:not self.dlg.running and not self.dlg.busy);self.assertEqual(self.dlg.batch['phase'],'DONE');self.assertEqual([r['attempts'] for r in self.dlg.batch['items']],[1,1]);self.assertEqual(len(self.window.library.list_sources()),2)
    def test_background_failure_isolated_and_preflight_failure_controls_recover(self):
        self.dlg.paths=[];QTest.mouseClick(self.dlg.scan_button,Qt.LeftButton);self.wait_for(lambda:not self.dlg.busy);self.assertTrue(self.dlg.scan_button.isEnabled());self.assertIsNone(self.dlg.report)
        self.scan();calls=[]
        def work(item,assets):
            calls.append(item['id'])
            if len(calls)==1:raise RuntimeError('synthetic parse failure')
            return convert_item(item,assets)
        with patch('template_ai.batch_dialog.convert_item',side_effect=work):
            with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.dlg.start_button,Qt.LeftButton)
            self.wait_for(lambda:not self.dlg.running and not self.dlg.busy)
        self.assertEqual(self.dlg.batch['phase'],'DONE_WITH_ERRORS');self.assertEqual(len(calls),2);self.assertEqual(len(self.window.library.list_sources()),1);self.assertFalse(self.window.busy);self.assertTrue(self.dlg.choose_files.isEnabled())
    def test_late_result_transaction_failure_stops_and_reenables_gui(self):
        self.scan();event=self.window.library.event
        def fail(entity,action):
            if action=='import_item_result_saved':raise RuntimeError('late result audit')
            event(entity,action)
        with patch.object(self.window.library,'event',side_effect=fail):
            with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.dlg.start_button,Qt.LeftButton)
            self.wait_for(lambda:not self.dlg.running and not self.dlg.busy)
        self.assertEqual(self.dlg.batch['phase'],'INTERRUPTED');self.assertEqual(self.dlg.batch['items'][0]['status'],'INTERRUPTED');self.assertEqual(self.dlg.batch['items'][1]['status'],'READY');self.assertEqual(self.window.library.list_sources(),[]);self.assertTrue(self.dlg.scan_button.isEnabled())
    def test_page_change_invalidates_preview_and_worker_launch_failure_recovers(self):
        self.scan();self.dlg.page.setValue(2);self.assertIsNone(self.dlg.report);self.assertFalse(self.dlg.start_button.isEnabled());self.dlg.page.setValue(1);self.scan()
        with patch.object(self.window,'run_job',side_effect=RuntimeError('worker launch failed')):
            with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.dlg.start_button,Qt.LeftButton)
            self.wait_for(lambda:not self.dlg.running and not self.dlg.busy)
        self.assertEqual(self.dlg.batch['phase'],'INTERRUPTED');self.assertFalse(self.window.busy);self.assertTrue(self.dlg.scan_button.isEnabled());self.assertEqual(self.window.library.list_sources(),[])
    def test_modal_preflight_scope_mutation_and_dirty_navigation_are_blocked(self):
        self.scan()
        def mutate(*args):self.dlg.report['items'].pop();return QMessageBox.Yes
        with patch.object(QMessageBox,'question',side_effect=mutate):self.dlg.start_confirmed()
        self.assertEqual(self.window.import_store.list(),[]);self.assertIn('異動',self.dlg.status.text())
        from template_ai.batch_dialog import navigation_clean
        from template_ai.model import Slot,Rect
        self.window.current_slot=Slot('name','p1',Rect(4,4,20,10));self.window.load_slot_form(self.window.current_slot) if hasattr(self.window,'load_slot_form') else None
        with patch.object(self.window,'make_slot',return_value=Slot('name','p1',Rect(5,4,20,10))):self.assertFalse(navigation_clean(self.window))
        self.window.current_slot=None

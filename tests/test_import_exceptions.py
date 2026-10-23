import copy
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox,QInputDialog
from template_ai.storage import Library
from template_ai.batch_import import BatchStore,preflight,convert_item
from template_ai.import_exceptions import exception_rows,prepare_retry,apply_action
from template_ai.exception_dialog import ImportExceptionDialog
from template_ai.model import Rect
from template_ai.demo import demo_template
from template_ai.gui import MainWindow
APP=QApplication.instance() or QApplication([])


def svg(path,color='red'):
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm"><rect width="20" height="20" fill="{color}"/></svg>');return path


def failed_batch(store,paths):
    b=store.create(preflight(paths,store.library.list_sources()),True);r=b['items'][0];b=store.claim(b['id'],b['revision'],r['id']);b=store.finish(b['id'],b['revision'],r['id'],error='synthetic import failure');return store.stop(b['id'],b['revision'])


class ImportExceptionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.lib=Library(self.root/'data');self.addCleanup(lambda:self.lib.close());self.store=BatchStore(self.lib);self.paths=[svg(self.root/'a.svg'),svg(self.root/'b.svg','blue')];self.b=failed_batch(self.store,self.paths)
    def row(self):return next(r for r in exception_rows(self.lib,self.store) if r['batch_id']==self.b['id'])
    def test_exact_registered_dependencies_stable_ranking_and_filters(self):
        from template_ai.importer import import_file
        s=self.lib.add_source(self.paths[0],import_file(self.paths[0],self.lib.assets));w=self.lib.create_artwork(s['id'],'Anonymous',{'crop':Rect(0,0,90,54).__dict__,'work_width':90,'work_height':54,'slots':[],'visual_confirmed':False})
        t=demo_template();t.source_id=s['id'];self.lib.save_template(t);row=self.row();self.assertEqual(row['source_ids'],[s['id']]);self.assertEqual(row['impacts']['work_ids'],[w['id']]);self.assertEqual(row['impacts']['template_ids'],[t.id]);self.assertEqual(row['impact_count'],2);self.assertEqual(row['customer_impact'],'UNKNOWN')
        more=failed_batch(self.store,[self.paths[1]]);rows=exception_rows(self.lib,self.store);self.assertEqual(rows[0]['batch_id'],self.b['id']);self.assertEqual(exception_rows(self.lib,self.store),rows);self.assertEqual(len(exception_rows(self.lib,self.store,'a.svg')),1);self.assertEqual(len(exception_rows(self.lib,self.store,'no-match')),0);self.assertTrue(exception_rows(self.lib,self.store,order='TYPE'));self.assertEqual(self.store.get(more['id'])['phase'],'DONE_WITH_ERRORS')
    def test_exclude_restore_reopen_never_success_or_modify_source(self):
        row=self.row();before=self.lib.list_sources();b=apply_action(self.store,self.b['id'],self.b['revision'],[row['item']['id']],'EXCLUDE','not used',confirmed=True);self.assertEqual(b['items'][0]['status'],'EXCLUDED');self.assertEqual(b['items'][1],self.b['items'][1]);self.assertEqual(exception_rows(self.lib,self.store),[]);self.assertEqual(len(exception_rows(self.lib,self.store,status='EXCLUDED')),1)
        self.lib.close();self.lib=Library(self.root/'data');self.store=BatchStore(self.lib);b=self.store.get(b['id']);b=apply_action(self.store,b['id'],b['revision'],[row['item']['id']],'RESTORE',confirmed=True);self.assertEqual(b['items'][0]['status'],'FAILED');self.assertEqual(self.lib.list_sources(),before);self.assertEqual([r['action'] for r in b['items'][0]['history']][-2:],['EXCLUDE','RESTORE'])
    def test_retry_changed_hash_selected_only_preserves_ready_and_attempt_history(self):
        row=self.row();old=row['item']['expected_hash'];svg(self.paths[0],'green');plan=prepare_retry([row],self.lib.list_sources());self.assertTrue(plan['items'][row['item']['id']]['changed']);b=apply_action(self.store,self.b['id'],self.b['revision'],[row['item']['id']],'RETRY',plan=plan,confirmed=True);self.assertNotEqual(b['items'][0]['expected_hash'],old);self.assertEqual(b['items'][1],self.b['items'][1]);r=b['items'][0];b=self.store.claim(b['id'],b['revision'],r['id']);b=self.store.finish(b['id'],b['revision'],r['id'],convert_item(r,self.lib.assets));b=self.store.stop(b['id'],b['revision']);self.assertEqual(b['phase'],'PAUSED');self.assertEqual([r['status'] for r in b['items']],['SUCCESS','READY']);self.assertEqual(b['items'][0]['attempts'],2);self.assertEqual(b['items'][1]['attempts'],0)
    def test_cas_invalid_scope_proof_mutation_and_running_batch_rejected(self):
        row=self.row();plan=prepare_retry([row],[])
        for ids in [[],[row['item']['id']]*2,['unknown'],[self.b['items'][1]['id']]]:
            with self.assertRaises(ValueError):apply_action(self.store,self.b['id'],self.b['revision'],ids,'RETRY',plan=plan,confirmed=True)
        with self.assertRaisesRegex(ValueError,'明確'):apply_action(self.store,self.b['id'],self.b['revision'],[row['item']['id']],'EXCLUDE','reason')
        with self.assertRaisesRegex(ValueError,'原因'):apply_action(self.store,self.b['id'],self.b['revision'],[row['item']['id']],'EXCLUDE','',confirmed=True)
        svg(self.paths[0],'yellow')
        with self.assertRaisesRegex(ValueError,'變更'):apply_action(self.store,self.b['id'],self.b['revision'],[row['item']['id']],'RETRY',plan=plan,confirmed=True)
        self.assertEqual(self.store.get(self.b['id']),self.b)
        b=self.store.claim(self.b['id'],self.b['revision'],self.b['items'][1]['id'])
        with self.assertRaisesRegex(ValueError,'仍在執行'):apply_action(self.store,b['id'],b['revision'],[row['item']['id']],'EXCLUDE','reason',confirmed=True)
        with self.assertRaisesRegex(ValueError,'變更'):apply_action(self.store,b['id'],self.b['revision'],[row['item']['id']],'EXCLUDE','reason',confirmed=True)
    def test_action_late_audit_atomic_rollback_and_forged_plan_no_partial(self):
        row=self.row();plan=prepare_retry([row],[]);bad=copy.deepcopy(plan);bad['ids'].append(self.b['items'][1]['id'])
        with self.assertRaisesRegex(ValueError,'範圍'):apply_action(self.store,self.b['id'],self.b['revision'],[row['item']['id']],'RETRY',plan=bad,confirmed=True)
        for action in ['EXCLUDE','RETRY']:
            with patch.object(self.lib,'event',side_effect=RuntimeError('late exception audit')):
                with self.assertRaises(RuntimeError):apply_action(self.store,self.b['id'],self.b['revision'],[row['item']['id']],action,'reason',plan,True)
            self.assertEqual(self.store.get(self.b['id']),self.b);self.assertEqual(self.lib.list_sources(),[])
    def test_cross_batch_and_excluded_not_silently_retried(self):
        second=failed_batch(self.store,[self.paths[1]]);rows=exception_rows(self.lib,self.store)
        with self.assertRaisesRegex(ValueError,'一個批次'):prepare_retry(rows,[])
        row=self.row();b=apply_action(self.store,self.b['id'],self.b['revision'],[row['item']['id']],'EXCLUDE','not used',confirmed=True)
        with self.assertRaisesRegex(ValueError,'已排除'):prepare_retry(exception_rows(self.lib,self.store,status='EXCLUDED'),[])
        self.assertEqual(self.store.get(second['id'])['items'][0]['status'],'FAILED');self.assertEqual(b['items'][1]['status'],'READY')
    def test_integrity_corruption_blocks_exclusion_without_discarding_audit(self):
        # Real FK corruption creates an integrity guard failure instead of a fake PASS.
        b=copy.deepcopy(self.b);b['items'][0]['error_type']='INTEGRITY'
        import json
        self.store.db.execute('UPDATE import_batches SET payload=? WHERE id=?',(json.dumps(b),b['id']));self.store.db.commit()
        self.store.db.execute('PRAGMA foreign_keys=OFF');self.store.db.execute('INSERT INTO active_artworks VALUES(?,?)',('missing-source','missing-artwork'));self.store.db.commit();self.store.db.execute('PRAGMA foreign_keys=ON')
        with self.assertRaisesRegex(ValueError,'完整性'):apply_action(self.store,b['id'],b['revision'],[b['items'][0]['id']],'EXCLUDE','cannot hide corruption',confirmed=True)
        self.assertEqual(self.store.get(b['id']),b);self.store.db.execute('DELETE FROM active_artworks WHERE source_id=?',('missing-source',));self.store.db.commit()
        result=apply_action(self.store,b['id'],b['revision'],[b['items'][0]['id']],'EXCLUDE','explicit known item exclusion after actual integrity repair',confirmed=True);self.assertEqual(result['items'][0]['status'],'EXCLUDED');self.assertEqual(result['items'][1]['status'],'READY')


class ImportExceptionGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.window=MainWindow(self.root/'data');self.addCleanup(lambda:self.window.close());self.paths=[svg(self.root/'a.svg'),svg(self.root/'b.svg','blue')];self.b=failed_batch(self.window.import_store,self.paths);self.dlg=ImportExceptionDialog(self.window);self.dlg.show();APP.processEvents();self.addCleanup(lambda:self.dlg.close())
    def wait_for(self,predicate):
        end=time.monotonic()+12
        while not predicate() and time.monotonic()<end:QTest.qWait(10)
        self.assertTrue(predicate(),self.dlg.status.text())
    def select(self):self.dlg.table.selectRow(0);APP.processEvents()
    def test_real_search_sort_filter_and_exact_source_navigation(self):
        from template_ai.importer import import_file
        s=self.window.library.add_source(self.paths[0],import_file(self.paths[0],self.window.library.assets));self.dlg.reload();self.select();self.assertIn(s['id'],self.dlg.details.toPlainText());key=self.dlg.selection()[0]['key'];self.dlg.order.setCurrentIndex(1);self.assertEqual(self.dlg.selection()[0]['key'],key);self.dlg.search.setText('missing');self.assertEqual(self.dlg.table.rowCount(),0);self.dlg.search.setText('a.svg');self.select();QTest.mouseClick(self.dlg.locate_button,Qt.LeftButton);self.assertEqual(self.window.source['id'],s['id']);self.assertIn('未自動批准',self.dlg.status.text())
    def test_gui_exclude_decline_reason_restore_and_reopen_history(self):
        self.select()
        with patch.object(QInputDialog,'getText',return_value=('synthetic not needed',True)),patch.object(QMessageBox,'question',return_value=QMessageBox.No):self.dlg.change_status('EXCLUDE')
        self.assertEqual(self.window.import_store.get(self.b['id']),self.b)
        with patch.object(QInputDialog,'getText',return_value=('synthetic not needed',True)),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):self.dlg.change_status('EXCLUDE')
        self.assertEqual(self.dlg.table.rowCount(),0);self.dlg.filter.setCurrentIndex(1);self.select()
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.dlg.restore_button,Qt.LeftButton)
        self.dlg.filter.setCurrentIndex(0);self.assertEqual(self.dlg.table.rowCount(),1);b=self.window.import_store.get(self.b['id']);self.assertEqual(b['items'][0]['status'],'FAILED');self.assertEqual(b['items'][0]['history'][-1]['action'],'RESTORE')
    def test_actual_changed_hash_preview_confirm_retry_only_selected_ready_untouched(self):
        svg(self.paths[0],'green');self.select();QTest.mouseClick(self.dlg.preview_button,Qt.LeftButton);self.wait_for(lambda:not self.dlg.busy);self.assertIsNotNone(self.dlg.plan);self.assertIn('new_hash',self.dlg.details.toPlainText())
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):QTest.mouseClick(self.dlg.apply_button,Qt.LeftButton)
        self.assertIsNone(self.dlg.runner)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.dlg.apply_button,Qt.LeftButton)
        self.assertIsNotNone(self.dlg.runner);self.wait_for(lambda:not self.dlg.runner.running and not self.dlg.runner.busy);b=self.window.import_store.get(self.b['id']);self.assertEqual([r['status'] for r in b['items']],['SUCCESS','READY']);self.assertEqual([r['attempts'] for r in b['items']],[2,0]);self.assertEqual(b['phase'],'PAUSED');self.dlg.runner.close();APP.processEvents();self.assertEqual(self.dlg.table.rowCount(),0)
    def test_background_failure_and_late_apply_failure_controls_recover(self):
        self.select();self.paths[0].unlink();self.dlg.preview_retry();self.wait_for(lambda:not self.dlg.busy);self.assertIsNone(self.dlg.plan);self.assertTrue(self.dlg.reload_button.isEnabled());svg(self.paths[0]);self.dlg.preview_retry();self.wait_for(lambda:not self.dlg.busy);self.assertIsNotNone(self.dlg.plan)
        with patch.object(self.window.library,'event',side_effect=RuntimeError('late exception audit')),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):self.dlg.apply_retry()
        self.assertIsNone(self.dlg.runner);self.assertEqual(self.window.import_store.get(self.b['id']),self.b);self.assertTrue(self.dlg.apply_button.isEnabled())
    def test_stale_source_modal_selection_and_plan_mutation_rejected(self):
        self.select();self.dlg.preview_retry();self.wait_for(lambda:not self.dlg.busy);svg(self.paths[0],'yellow')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):self.dlg.apply_retry()
        self.assertEqual(self.window.import_store.get(self.b['id']),self.b);self.assertIsNone(self.dlg.runner)
        self.dlg.preview_retry();self.wait_for(lambda:not self.dlg.busy)
        def mutate(*args):self.dlg.plan['ids'].append(self.b['items'][1]['id']);return QMessageBox.Yes
        with patch.object(QMessageBox,'question',side_effect=mutate):self.dlg.apply_retry()
        self.assertEqual(self.window.import_store.get(self.b['id']),self.b);self.assertIsNone(self.dlg.runner)
        def selection(*args):self.dlg.table.clearSelection();return QMessageBox.Yes
        with patch.object(QInputDialog,'getText',return_value=('reason',True)),patch.object(QMessageBox,'question',side_effect=selection):self.dlg.change_status('EXCLUDE')
        self.assertEqual(self.window.import_store.get(self.b['id']),self.b)

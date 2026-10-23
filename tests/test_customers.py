import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QMessageBox
from template_ai.gui import MainWindow
from template_ai.model import Template,Slot,Rect
from template_ai.customers import CustomerStore
from template_ai.customer_dialog import CustomerDialog
from template_ai.secure_backup import backup,restore
APP=QApplication.instance() or QApplication([])

class CustomerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.window=MainWindow(self.root/'data');self.addCleanup(self.window.library.db.close);self.store=CustomerStore(self.window.library)
        self.template=Template('Customer exact version',90,54,[Slot('name','p1',Rect(5,5,40,8))]);self.window.library.save_template(self.template)
        self.fields=[dict(owner='p1',kind='name',value='Alex Example'),dict(owner='p1',kind='phone',value='+12025550100'),dict(owner='p1',kind='email',value='alex@example.test')]
        self.c=self.store.create('00123','Synthetic Customer',self.fields,self.template.id,True)
    def test_create_stable_fields_zero_code_unique_foreign_keys_and_no_purchase_states(self):
        self.assertEqual(self.c['code'],'00123');self.assertEqual(len({f['id'] for f in self.c['fields']}),3);self.assertEqual(self.window.library.db.execute('PRAGMA foreign_keys').fetchone()[0],1)
        with self.assertRaises(Exception):self.store.create('00123','Other',self.fields,self.template.id,True)
        with self.assertRaises(ValueError):self.store.create('0099','Other',[dict(owner='p2',kind='name',value='Casey')],self.template.id,True)
        self.assertNotIn('purchased',json.dumps(self.c));self.assertNotIn('designed',json.dumps(self.c));self.assertEqual(self.store.get(self.c['id']),self.c)
    def test_search_and_identity_confirmed_exact_reorder_readonly_stale_template(self):
        other=self.store.create('00999','Other',self.fields,self.template.id,True);self.assertEqual(len(self.store.search('+12025550100')),2);self.assertEqual(self.store.search(''),[]);self.assertEqual(self.store.search('%'),[])
        self.assertEqual(self.store.search('00123')[0]['id'],self.c['id'])
        before=self.window.library.db.total_changes
        with self.assertRaises(ValueError):self.store.reorder(self.c['id'],self.c['styles'][0]['id'])
        draft=self.store.reorder(self.c['id'],self.c['styles'][0]['id'],True);self.assertEqual(draft['template_id'],self.template.id);self.assertEqual(draft['status'],'PREFILL_PENDING_VALIDATION');self.assertEqual(before,self.window.library.db.total_changes)
        self.template.name='Changed';self.window.library.save_template(self.template)
        with self.assertRaises(ValueError):self.store.reorder(self.c['id'],self.c['styles'][0]['id'],True)
    def test_selected_field_atomic_CAS_clear_vs_absent_other_customer_untouched(self):
        f=self.c['fields'];values={f[1]['id']:'',f[2]['id']:'new@example.test'}
        result=self.store.writeback(self.c,values,[f[1]['id']],True);self.assertEqual(result['fields'][1]['value'],'');self.assertEqual(result['fields'][2]['value'],f[2]['value']);self.assertEqual(result['revision'],2)
        plan=self.store.differences(self.c,values);self.assertEqual(plan['rows'][0]['operation'],'CLEAR');self.assertEqual(plan['current_revision'],2)
        with self.assertRaises(ValueError):self.store.writeback(self.c,values,[f[2]['id']],True)
        with self.assertRaises(ValueError):self.store.writeback(result,{'other-customer-field':'bad'},['other-customer-field'],True)
    def test_late_audit_failure_rolls_back_fields_version_and_history(self):
        f=self.c['fields'][1]
        with patch.object(self.window.library,'event',side_effect=RuntimeError('late audit')),self.assertRaises(RuntimeError):self.store.writeback(self.c,{f['id']:'changed'},[f['id']],True)
        self.assertEqual(self.store.get(self.c['id']),self.c);self.assertEqual(self.store.db.execute('SELECT count(*) FROM customer_changes').fetchone()[0],0)
    def test_duplicate_comparison_no_inferred_merge_or_identity_or_writes(self):
        other=self.store.create('00999','Other',self.fields,self.template.id,True);before=self.store.db.total_changes;result=self.store.compare(self.c['id'],other['id']);self.assertTrue(result['shared_clues']);self.assertEqual(result['identity'],'UNKNOWN');self.assertFalse(result['automatic_merge']);self.assertEqual(self.store.db.total_changes,before);self.assertEqual(len(self.store.search('Alex')),2)
    def test_authenticated_snapshot_isolated_restore_wrong_password_corruption_and_no_overwrite(self):
        path=self.root/'backup.tabi';password='synthetic-test-password';result=backup(self.window.library,path,password);self.assertFalse(result['assets_included']);self.assertTrue(result['authenticated']);self.assertNotIn(b'Alex Example',path.read_bytes());self.assertNotIn(password.encode(),path.read_bytes())
        target=self.root/'restored';r=restore(path,target,password);self.assertFalse(r['production_ready']);self.assertTrue((target/'library.sqlite3').exists());self.assertEqual(r['external_assets'],'NOT_RESTORED')
        import sqlite3
        with sqlite3.connect(target/'library.sqlite3') as db:self.assertEqual(db.execute('SELECT code FROM customers').fetchone()[0],'00123')
        with self.assertRaises(FileExistsError):restore(path,target,password)
        with self.assertRaises(ValueError):restore(path,self.root/'bad','wrong-password-000')
        self.assertFalse((self.root/'bad').exists());blob=bytearray(path.read_bytes());blob[-1]^=1;path.write_bytes(blob)
        with self.assertRaises(ValueError):restore(path,self.root/'tampered',password)
        self.assertFalse((self.root/'tampered').exists());self.assertEqual(self.store.get(self.c['id']),self.c)
    def test_actual_gui_search_unchecked_diff_cancel_commit_stale_and_duplicate_compare(self):
        other=self.store.create('00999','Other',self.fields,self.template.id,True);d=CustomerDialog(self.window);self.addCleanup(d.deleteLater);d.show();d.query.setText('Alex');d.search();d.customers.selectRow(0);APP.processEvents();self.assertIsNotNone(d.snapshot);self.assertEqual(d.fields.item(1,0).checkState(),Qt.Unchecked)
        d.fields.item(1,3).setText('Changed synthetic phone');d.preview();self.assertIn('Changed synthetic phone',d.details.toPlainText());d.fields.item(1,0).setCheckState(Qt.Checked)
        with patch('template_ai.customer_dialog.QMessageBox.question',return_value=QMessageBox.No):d.write()
        self.assertEqual(self.store.get(d.snapshot['id'])['revision'],1)
        with patch('template_ai.customer_dialog.QMessageBox.question',return_value=QMessageBox.Yes):d.write()
        self.assertEqual(self.store.get(d.snapshot['id'])['revision'],2);self.assertIn('已原子回寫',d.status.text())
        snapshot=d.snapshot;fid=snapshot['fields'][0]['id'];self.store.writeback(snapshot,{fid:'Updated Name'},[fid],True);d.fields.item(1,3).setText('Concurrent stale');d.fields.item(1,0).setCheckState(Qt.Checked)
        with patch('template_ai.customer_dialog.QMessageBox.question',return_value=QMessageBox.Yes):d.write()
        self.assertIn('主檔已更新',d.status.text());d.customers.selectAll();d.compare();self.assertIn('UNKNOWN',d.details.toPlainText());d.hide()
    def test_actual_gui_explicit_reorder_fills_work_only_no_automatic_master_write(self):
        d=CustomerDialog(self.window);self.addCleanup(d.deleteLater);d.query.setText('00123');d.search();d.customers.selectRow(0);APP.processEvents();label=f"{self.c['styles'][0]['id']} · 90.0×54.0mm · {self.template.id}"
        # SQLite REAL return uses 90.0; let dialog choose its actual option.
        def choose(parent,title,prompt,labels,*args):return labels[0],True
        with patch('template_ai.customer_dialog.QInputDialog.getItem',side_effect=choose),patch('template_ai.customer_dialog.QMessageBox.question',return_value=QMessageBox.Yes):d.prefill()
        self.assertEqual(self.window.people.item(0,0).text(),'Alex Example');self.assertEqual(self.window.reorder_template_id,self.template.id);self.assertEqual(self.store.get(self.c['id']),self.c);self.assertFalse(self.window.export_button.isEnabled())

"""Original encrypted store, real durable transaction readback and lost-RAM honesty."""
import copy,tempfile,unittest,threading
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox
from template_ai.batch_objects import batch_plan,apply_batch,BatchObjectDialog
from template_ai.batch_recovery import store,inspect,payload,reconnect,decode_checked
from template_ai.layout_recovery import LayoutRecovery
from template_ai.customers import digest
from template_ai.storage import Library
from training_fixture import source_work
from sync_workflow_fixture import SyncWorkflowFixture,APP
from gui_wait import wait_for_gui
import test_batch_correction_gui as source_gui
import test_batch_candidate_gui as candidate_gui


class BatchRecoverySourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.library=Library(Path(self.temp.name));self.addCleanup(self.library.close)
        self.works=[source_work(self.library,Path(self.temp.name),f'recovery{i}.svg')[1] for i in range(3)]
        self.plan=batch_plan(self.library,[dict(id=w['id'],slot_ids=[w['payload']['slots'][0]['id']],request=dict(operation='MOVE',ids=[w['payload']['slots'][0]['id']],dx=.1,dy=0,cross_owner=False)) for w in self.works])
        self.value=dict(kind='BATCH_CORRECTION',state='PAUSED_SAFE',scope='ARTWORK',root_digest=digest(str(self.library.root.resolve())),plan=self.plan,results=[],checked={})
    def test_encrypted_restart_readback_and_retry_do_not_repeat_saved_relative_move(self):
        progress=[];first=apply_batch(self.library,self.plan,True,cancel=lambda:len(progress)>=1,progress=progress.append);self.assertEqual(first[0]['outcome'],'APPLIED_PENDING_FULL_VALIDATION');before=self.library.object_snapshot('ARTWORK',self.works[0]['id']);store(self.library.root).save(self.value,'synthetic-batch-password')
        other=Library(self.library.root)
        try:
            restored=store(other.root).load('synthetic-batch-password');rows=inspect(other,restored);self.assertEqual(rows[0]['outcome'],'APPLIED_PENDING_FULL_VALIDATION');self.assertFalse(rows[0]['attempted']);self.assertEqual(rows[1]['outcome'],'CANCELLED');apply_batch(other,restored['plan'],True);self.assertEqual(other.object_snapshot('ARTWORK',self.works[0]['id']),before)
        finally:other.close()
    def test_typed_slots_do_not_overwrite_or_clear_layout_and_wrong_loader_refuses(self):
        layout=LayoutRecovery(self.library.root);layout.save(dict(state='CANCELLED',rows=[]),'synthetic-layout-password');batch=store(self.library.root);batch.save(self.value,'synthetic-batch-password');self.assertNotEqual(layout.path,batch.path);batch.clear();self.assertTrue(layout.pending());batch.save(self.value,'synthetic-batch-password')
        with self.assertRaisesRegex(ValueError,'批次'):layout.validate(self.library,batch.load('synthetic-batch-password'))
        self.assertTrue(batch.pending());self.assertTrue(layout.pending())
    def test_wrong_password_does_not_change_ciphertext_or_business_history(self):
        r=store(self.library.root);r.save(self.value,'synthetic-batch-password');before=r.path.read_bytes()
        with self.assertRaises(ValueError):r.load('incorrect-password')
        self.assertEqual(r.path.read_bytes(),before);self.assertEqual(self.library.db.execute('SELECT count(*) FROM object_edits').fetchone()[0],0);self.assertNotIn(self.works[0]['id'].encode(),before)
    def test_authenticated_but_modified_scope_seal_is_refused(self):
        value=copy.deepcopy(self.value);value['plan']['rows'][0]['request']['dx']=2;store(self.library.root).save(value,'synthetic-batch-password')
        with self.assertRaisesRegex(ValueError,'範圍'):inspect(self.library,store(self.library.root).load('synthetic-batch-password'))
    def test_root_or_unstopped_or_wrong_kind_cannot_be_replayed(self):
        for update in (dict(root_digest='other'),dict(state='RUNNING'),dict(kind='LAYOUT')):
            with self.assertRaises(ValueError):inspect(self.library,{**self.value,**update})
    def test_aggregate_original_recovery_budget_is_bounded(self):
        LayoutRecovery(self.library.root).save(dict(state='CANCELLED',padding='a'*(3*1024*1024)),'synthetic-layout-password')
        with self.assertRaisesRegex(ValueError,'合計'):store(self.library.root).save({**self.value,'padding':'b'*(2*1024*1024)},'synthetic-batch-password')
        self.assertFalse(store(self.library.root).path.exists())


class BatchRecoveryGuiTests(unittest.TestCase):
    setUp=source_gui.BatchCorrectionGuiTests.setUp
    close_window=source_gui.BatchCorrectionGuiTests.close_window
    make=source_gui.BatchCorrectionGuiTests.make
    dispose=source_gui.BatchCorrectionGuiTests.dispose
    check=source_gui.BatchCorrectionGuiTests.check
    apply=source_gui.BatchCorrectionGuiTests.apply
    # Inherit the real source fixtures, not duplicate inherited test cases.
    __test__=True
    def test_recovery_buttons_during_real_owned_worker_do_not_clear_running_or_start_restore(self):
        d=self.make();self.check(self.works[0]);d.preview();started=threading.Event();release=threading.Event();original=Library.apply_object_edit
        def hold(library,*args):
            started.set()
            if not release.wait(5):raise TimeoutError('owned fixture release missing')
            return original(library,*args)
        try:
            with patch.object(Library,'apply_object_edit',hold):
                with patch('template_ai.batch_objects.QMessageBox.question',return_value=QMessageBox.Yes):d.apply()
                self.assertTrue(wait_for_gui(started.is_set,5));self.assertTrue(d.running);d.recovery_controller.save();self.assertTrue(d.running);d.recovery_controller.restore();self.assertTrue(d.running);self.assertTrue(self.w.busy);d.close();self.assertTrue(d.running);release.set();self.assertTrue(wait_for_gui(lambda:not d.running and not self.w.busy,5))
        finally:release.set()
    def test_changed_parameters_cannot_be_saved_as_old_preflight(self):
        d=self.make();self.check(self.works[0]);d.preview();d.dx.setValue(3)
        with self.assertRaisesRegex(ValueError,'參數'):payload(d)
    def test_source_graphic_preview_is_readonly_and_does_not_add_history(self):
        d=self.make();key=self.check(self.works[0]);d.preview();index=next(i for i in range(d.table.rowCount()) if d.table.item(i,0).data(Qt.UserRole)==key);d.table.setCurrentCell(index,1);before=self.w.library.db.execute('SELECT count(*) FROM object_edits').fetchone()[0];graphic=d.make_graphic_preview();self.addCleanup(graphic.deleteLater);graphic.show();APP.processEvents();self.assertEqual(len(graphic.canvases),2);self.assertTrue(all(c.readonly and c.mode=='pan' for c in graphic.canvases));self.assertEqual(self.w.library.db.execute('SELECT count(*) FROM object_edits').fetchone()[0],before)
    def test_actual_worker_save_restore_reads_partial_source_history_without_writing(self):
        d=self.make();self.check(self.works[0]);self.check(self.works[1]);second=self.works[1];data=copy.deepcopy(second['payload']);data['slots'][0]['locked']=True;self.w.library.save_artwork(second['id'],data,second['revision']);d.preview();self.apply();before=self.w.library.object_snapshot('ARTWORK',self.works[0]['id'])
        with patch('PySide6.QtWidgets.QInputDialog.getText',return_value=('synthetic-batch-password',True)):d.recovery_controller.save()
        self.assertTrue(wait_for_gui(lambda:not d.running and not self.w.busy,10),d.status.text());self.assertTrue(store(self.w.library.root).pending());self.assertIn('逐位元讀回',d.status.text());self.assertIsNone(self.w.navigation.recovery)
        with patch('PySide6.QtWidgets.QInputDialog.getText',return_value=('synthetic-batch-password',True)),patch('PySide6.QtWidgets.QMessageBox.question',return_value=QMessageBox.Yes):d.recovery_controller.restore();self.assertTrue(wait_for_gui(lambda:not d.running and not self.w.busy,10),d.status.text())
        self.assertEqual(self.w.library.object_snapshot('ARTWORK',self.works[0]['id']),before);applied=next(row for row in d.results if row['id']==self.works[0]['id']);self.assertEqual(applied['outcome'],'APPLIED_PENDING_FULL_VALIDATION');self.assertFalse(applied['attempted'])


class BatchRecoveryCandidateTests(unittest.TestCase):
    setUp=candidate_gui.BatchCandidateGuiTests.setUp
    dispose=candidate_gui.BatchCandidateGuiTests.dispose
    check=candidate_gui.BatchCandidateGuiTests.check
    wait=candidate_gui.BatchCandidateGuiTests.wait
    preview=candidate_gui.BatchCandidateGuiTests.preview
    apply=candidate_gui.BatchCandidateGuiTests.apply
    def test_candidate_graphic_preview_keeps_cached_before_after_and_current_model(self):
        slot=self.check('A90');self.preview();before=copy.deepcopy(self.f.candidate('A90'));index=next(i for i in range(self.d.table.rowCount()) if self.d.by_key[self.d.table.item(i,0).data(Qt.UserRole)]['slot_ids']==[slot]);self.d.table.setCurrentCell(index,1);graphic=self.d.make_graphic_preview();self.addCleanup(graphic.deleteLater);graphic.show();APP.processEvents();self.assertTrue(all(c.readonly for c in graphic.canvases));self.assertEqual(self.f.candidate('A90').template.to_dict(),before.template.to_dict());self.assertEqual(self.f.candidate('A90').risk_context,before.risk_context)
    def test_actual_gui_restore_then_selected_inverse_keeps_same_stable_field_identity(self):
        self.check('A90');self.check('C100');self.preview();self.apply();store(self.f.w.library.root).save(payload(self.d),'synthetic-batch-password')
        with patch('PySide6.QtWidgets.QInputDialog.getText',return_value=('synthetic-batch-password',True)),patch('PySide6.QtWidgets.QMessageBox.question',return_value=QMessageBox.Yes):self.d.recovery_controller.restore();self.wait()
        self.assertEqual(sum(r['outcome']=='ALREADY_APPLIED' for r in self.d.results),1)
        for i in range(self.d.table.rowCount()):
            item=self.d.table.item(i,0);row=self.d.by_key[item.data(Qt.UserRole)]
            if row['id']!=self.f.candidate('A90').template.id:item.setCheckState(Qt.Unchecked)
        with patch('PySide6.QtWidgets.QMessageBox.question',return_value=QMessageBox.Yes):self.d.undo()
        self.wait();self.assertIn('已回復 1',self.d.status.text());self.assertEqual(next(s for s in self.f.candidate('A90').template.slots if s.kind=='phone' and s.owner=='p1').align,'left')
    def test_candidate_cached_receipt_roundtrip_reconnects_exact_current_origin(self):
        self.check('A90');self.check('C100');self.preview();self.apply();before=copy.deepcopy(self.f.candidate('A90'));value=payload(self.d);r=store(self.f.w.library.root);r.save(value,'synthetic-batch-password');restored=r.load('synthetic-batch-password');rows=inspect(self.f.w.library,restored);rows,checked=reconnect(self.d,restored,rows);self.assertEqual(sum(row['outcome']=='ALREADY_APPLIED' for row in rows),1);self.assertEqual(self.f.candidate('A90').risk_context['manual_history'],before.risk_context['manual_history']);self.assertEqual(len(checked),2)
    def test_restarted_view_without_original_ram_origin_is_unverified_and_cannot_replay(self):
        self.check('A90');self.check('C100');self.preview();self.apply();value=payload(self.d)
        from template_ai.multi_size_dialog import MultiSizeDialog
        other=MultiSizeDialog(self.f.w);other.service=self.f.d.service;dialog=BatchObjectDialog(self.f.w,origin=other);dialog.scope.setCurrentIndex(dialog.scope.findData('CANDIDATE'));self.addCleanup(dialog.deleteLater);self.addCleanup(other.deleteLater);before=copy.deepcopy(self.f.candidate('A90').template.to_dict());rows,checked=reconnect(dialog,value,inspect(self.f.w.library,value));self.assertFalse(checked);self.assertTrue(all(row['outcome']=='RESULT_UNVERIFIED' for row in rows));self.assertEqual(self.f.candidate('A90').template.to_dict(),before)
    def test_tampered_cached_candidate_is_rejected_before_any_adoption(self):
        self.check('A90');self.preview();value=payload(self.d);item=next(iter(value['checked'].values()));item['candidate']['template']['slots'][0]['rect']['x']+=1
        with self.assertRaises(ValueError):decode_checked(item)
    def test_all_applied_phase_does_not_retain_normal_completed_private_snapshot(self):
        self.check('A90');self.preview();self.apply()
        with self.assertRaisesRegex(ValueError,'已完成'):payload(self.d)

if __name__=='__main__':unittest.main()

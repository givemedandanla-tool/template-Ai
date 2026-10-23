"""Actual single worker backpressure, partial canvas and human edit fencing."""
import copy,threading,unittest
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtWidgets import QMessageBox,QInputDialog
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
import test_seventy_ui as fixture
from template_ai.demo import demo_template
from template_ai.layout_session import LayoutSessionDialog,LayoutWorker,canvas_stamp
from template_ai.layout_recovery import LayoutRecovery
from template_ai.layout import generate
from template_ai.candidate_edit import plan_candidate,apply_candidate
APP=fixture.APP;pump_until=fixture.pump_until

class LayoutSessionExtendedTests(unittest.TestCase):
    setUp=fixture.SeventyUiTests.setUp
    close_window=fixture.SeventyUiTests.close_window
    def dialog(self):
        d=LayoutSessionDialog(self.w);self.addCleanup(d.deleteLater);d.show();return d
    def test_resource_wait_real_stage_partial_preview_cancel_and_resume_only_unstarted(self):
        self.w.library.publish(demo_template());d=self.dialog();calls=[];allow=threading.Event();original=generate
        def calculate(*args,**kwargs):calls.append(args[0].id);return original(*args,**kwargs)
        def admit(*args,**kwargs):return SimpleNamespace(allowed=not calls or allow.is_set(),reasons=('SYNTHETIC_MEMORY_PRESSURE',))
        phases=[];original_progress=d.progress
        def progress(event):phases.append(event['phase']);original_progress(event)
        d.progress=progress
        with patch('template_ai.layout_session.generate',side_effect=calculate),patch.object(self.w.runtime,'admit',side_effect=admit):
            d.start();pump_until(lambda:'PAUSED_RESOURCES' in phases);self.assertEqual(len(d.rows),1);self.assertTrue(d.running);self.assertIn('FIXED_FONT_GEOMETRY',phases);d.list.setCurrentRow(0);d.preview_selected();self.assertIn('部分候選',d.status.text());self.assertFalse(self.w.export_button.isEnabled());self.assertEqual(self.w.candidates,[])
            QTest.mouseClick(d.cancel_button,Qt.LeftButton);pump_until(lambda:not d.running);self.assertEqual(len(calls),1);self.assertEqual(len(d.rows),1);allow.set();QTest.mouseClick(d.resume_button,Qt.LeftButton);pump_until(lambda:not d.running);self.assertEqual(len(calls),2);self.assertEqual(len(set(calls)),2);self.assertEqual(len(d.rows),2);self.assertEqual(d.report_state,'COMPLETED')
    def test_old_worker_cannot_overwrite_current_manual_geometry_even_after_reconfirmation(self):
        d=self.dialog();d.start();pump_until(lambda:not d.running)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):d.adopt()
        slot=self.w.candidates[0].template.slots[0];plan=plan_candidate(self.w,0,[slot.id],1,0);apply_candidate(self.w,plan,True);before=canvas_stamp(self.w)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):d.adopt()
        self.assertEqual(canvas_stamp(self.w),before);self.assertIn('人工修正',d.status.text())
    def test_resume_rechecks_changed_input_and_template_instead_of_clearing_paused_flag(self):
        d=self.dialog();d.start();pump_until(lambda:not d.running);d.report_state='CANCELLED';d.pause_event.set();self.w.people.item(0,0).setText('Changed person');d.resume();self.assertTrue(d.pause_event.is_set());self.assertFalse(d.running);self.assertIn('版本已改變',d.status.text())
    def test_native_password_save_restart_explicit_restore_clear_and_normal_completion_cleanup(self):
        from template_ai.input_graph import InputGraph
        people,companies,logos=self.w.input_data();self.w.adopt_input_graph(InputGraph.from_legacy(people,companies,logos).data)
        d=self.dialog();d.start();pump_until(lambda:not d.running);d.report_state='CANCELLED';d.controls()
        with patch.object(QInputDialog,'getText',return_value=('synthetic-password-123',True)):d.save_recovery();pump_until(lambda:not self.w.busy)
        self.assertTrue(d.recovery.pending());self.assertIn('實際驗證加密',d.status.text());reopened=self.dialog();self.assertIn('恢復上一次',reopened.status.text());self.assertEqual(reopened.rows,[])
        with patch.object(QInputDialog,'getText',return_value=('synthetic-password-123',True)),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):reopened.restore_recovery();pump_until(lambda:not self.w.busy)
        self.assertEqual(reopened.report_state,'CANCELLED');self.assertEqual(len(reopened.rows),1);self.assertIsNotNone(reopened.rows[0]['candidate']);self.assertTrue(reopened.resume_button.isEnabled());self.assertIn('未自動採用',reopened.status.text())
        reopened.resume();pump_until(lambda:not reopened.running);self.assertFalse(reopened.recovery.pending());self.assertEqual(reopened.report_state,'COMPLETED')
    def test_restore_background_decryption_cannot_replace_newer_input(self):
        d=self.dialog();d.start();pump_until(lambda:not d.running);d.report_state='CANCELLED';d.recovery.save(d.recovery_payload(),'synthetic-password-123');real=d.recovery.load
        def changed(password):result=real(password);return result
        # The success callback must compare the GUI generation captured before dispatch.
        original=self.w.run_job
        def dispatch(message,work,done,**kwargs):
            def finish(result):self.w.people.item(0,0).setText('New manual person');done(result)
            return original(message,work,finish,**kwargs)
        with patch.object(QInputDialog,'getText',return_value=('synthetic-password-123',True)),patch.object(self.w,'run_job',side_effect=dispatch):d.restore_recovery();pump_until(lambda:not self.w.busy)
        self.assertEqual(self.w.people.item(0,0).text(),'New manual person');self.assertIn('保留目前工作',d.status.text());self.assertTrue(d.recovery.pending())

    def test_new_main_calculation_preserves_preexisting_manual_layout_until_explicit_difference_choice(self):
        from gui_wait import wait_layout
        d=self.dialog();d.start();pump_until(lambda:not d.running)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):d.adopt()
        slot=self.w.candidates[0].template.slots[0];apply_candidate(self.w,plan_candidate(self.w,0,[slot.id],1,0),True);self.w.people.item(0,0).setText('New person input');before=canvas_stamp(self.w);self.w.generate();new=wait_layout(self.w)
        self.assertEqual(canvas_stamp(self.w),before);self.assertFalse(new.auto_apply);self.assertIn('人工',new.details.toPlainText());self.assertTrue(new.rows);self.assertFalse(self.w.export_button.isEnabled())
    def test_actual_gui_encrypted_snapshot_preserves_current_legal_manual_geometry_and_receipt(self):
        d=self.dialog();d.start();pump_until(lambda:not d.running)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):d.adopt()
        slot=self.w.candidates[0].template.slots[0];old_x=slot.rect.x;apply_candidate(self.w,plan_candidate(self.w,0,[slot.id],1,0),True);d.report_state='CANCELLED';d.controls()
        with patch.object(QInputDialog,'getText',return_value=('synthetic-password-123',True)):d.save_recovery();pump_until(lambda:not self.w.busy)
        payload=d.recovery.load('synthetic-password-123');rows=d.recovery.validate(self.w.library,payload);self.assertIsNotNone(rows[0]['candidate']);self.assertEqual(rows[0]['candidate'].template.slots[0].rect.x,old_x+1);self.assertIn('manual_edit_receipt',rows[0]['candidate'].risk_context);self.assertEqual(rows[0]['candidate'].risk_context['manual_revision'],1);self.assertEqual(len(rows[0]['candidate'].risk_context['manual_history']),1);self.assertEqual(rows[0]['candidate'].risk_context['manual_base_template']['slots'][0]['rect']['x'],old_x)
    def test_save_after_input_change_never_claims_stale_session_is_current_saved_work(self):
        d=self.dialog();d.start();pump_until(lambda:not d.running);d.report_state='CANCELLED';self.w.people.item(0,0).setText('New unsaved input')
        with patch.object(QInputDialog,'getText',return_value=('synthetic-password-123',True)):d.save_recovery();pump_until(lambda:not self.w.busy)
        self.assertFalse(d.recovery.pending());self.assertIn('未保存',d.status.text())

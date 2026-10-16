"""Actual shared-worker ordering, transient manual state, cancellation and freshness."""
import threading,unittest,json
from unittest.mock import patch
from PySide6.QtCore import QCoreApplication,QEvent
import test_seventy_ui as fixture
from gui_wait import wait_layout,wait_for_gui,wait_candidate_edits
from template_ai.candidate_edit import plan_candidate,plan_undo,plan_recheck,plan_original,CandidateEditDialog
from template_ai.candidate_edit_dispatch import dispatcher,calculate_edit
from template_ai.model import Template


class CandidateEditDispatchTests(unittest.TestCase):
    setUp=fixture.SeventyUiTests.setUp
    close_window=fixture.SeventyUiTests.close_window
    def ready(self):
        self.w.generate();wait_layout(self.w);return self.w.candidates[0]
    def move(self,dx=1):
        return dispatcher(self.w).submit(plan_candidate(self.w,0,[self.w.candidates[0].template.slots[0].id],dx,0))
    def blocked(self):
        started=threading.Event();release=threading.Event();calls=[]
        self.addCleanup(release.set)
        def work(envelope,library):
            calls.append(envelope);started.set()
            if not release.wait(5):raise AssertionError('Test did not release owned worker')
            return calculate_edit(envelope,library)
        return started,release,calls,patch('template_ai.candidate_edit_dispatch.calculate_edit',side_effect=work)
    def test_pending_geometry_is_visible_and_formal_blocked_on_existing_pool(self):
        c=self.ready();x=c.template.slots[0].rect.x;pool=self.w.pool;started,release,calls,guard=self.blocked()
        with guard:
            pending=self.move();self.assertEqual(pending.template.slots[0].rect.x,x+1);self.assertFalse(pending.formal_eligible);self.assertEqual(pending.risk_context['edit_state'],'PENDING_MANUAL_RECHECK');self.assertTrue(wait_for_gui(started.is_set,2));self.assertIs(self.w.pool,pool);self.assertEqual(pool.maxThreadCount(),1);self.w.people.setCurrentCell(0,0);self.assertEqual(self.w.people.currentRow(),0);release.set();wait_candidate_edits(self.w)
        self.assertTrue(self.w.candidates[0].formal_eligible);self.assertEqual(len(calls),1)
    def test_latest_pending_edit_coalesces_while_existing_job_owns_worker(self):
        c=self.ready();x=c.template.slots[0].rect.x;started=threading.Event();release=threading.Event();self.addCleanup(release.set)
        def other():
            started.set()
            if not release.wait(5):raise AssertionError('Owned background job not released')
            return 'done'
        self.w.run_job('Synthetic existing geometry job',other,lambda result:None,resource_kind='GEOMETRY');self.assertTrue(wait_for_gui(started.is_set,2));manager=dispatcher(self.w)
        self.move();self.move();self.move();self.assertEqual(len(manager.pending),1);self.assertEqual(self.w.candidates[0].risk_context['manual_revision'],3);self.assertEqual(self.w.candidates[0].template.slots[0].rect.x,x+3);release.set();wait_candidate_edits(self.w);self.assertEqual(self.w.candidates[0].template.slots[0].rect.x,x+3);self.assertTrue(self.w.candidates[0].formal_eligible)
    def test_undo_during_active_move_rejects_old_result_and_preserves_history(self):
        c=self.ready();before=c.template.to_dict();started,release,calls,guard=self.blocked();manager=dispatcher(self.w);completed=[];manager.completed.connect(lambda index,result:completed.append(result))
        with guard:
            self.move();self.assertTrue(wait_for_gui(started.is_set,2));receipt=self.w.candidates[0].risk_context['manual_history'][0]['id'];manager.submit(plan_undo(self.w,0));self.assertEqual(self.w.candidates[0].template.to_dict(),before);release.set();wait_candidate_edits(self.w)
        self.assertEqual(len(calls),2);self.assertEqual(len(completed),1);current=self.w.candidates[0];self.assertEqual(current.risk_context['manual_revision'],2);self.assertEqual(current.risk_context['manual_history'][0]['id'],receipt);self.assertTrue(current.risk_context['manual_history'][0]['undone']);self.assertEqual(current.template.to_dict(),before)
    def test_changed_input_rejects_late_result_then_current_long_phone_rechecks(self):
        self.ready();started,release,calls,guard=self.blocked();manager=dispatcher(self.w);completed=[];manager.completed.connect(lambda index,result:completed.append(result))
        with guard:
            self.move();self.assertTrue(wait_for_gui(started.is_set,2));manual=self.w.candidates[0].template.to_dict();phone='1234567890'*20;self.w.people.item(0,2).setText(phone);release.set();wait_candidate_edits(self.w)
        self.assertFalse(completed);self.assertFalse(self.w.candidates[0].formal_eligible);manager.submit(plan_recheck(self.w,0));wait_candidate_edits(self.w);current=self.w.candidates[0];self.assertEqual(current.template.to_dict(),manual);self.assertIn(phone,[i.text for i in current.items]);self.assertEqual(current.risk['state'],'HARD_BLOCKED');self.assertTrue(current.risk_context['recompute_impact']['whole_card_validation_required'])
    def test_cancel_active_preserves_manual_pending_without_formal_release(self):
        c=self.ready();x=c.template.slots[0].rect.x;started,release,calls,guard=self.blocked();manager=dispatcher(self.w)
        with guard:
            self.move();self.assertTrue(wait_for_gui(started.is_set,2));manager.cancel(0);release.set();wait_candidate_edits(self.w)
        self.assertEqual(self.w.candidates[0].template.slots[0].rect.x,x+1);self.assertFalse(self.w.candidates[0].formal_eligible);self.assertEqual(self.w.candidates[0].risk_context['edit_state'],'PENDING_MANUAL_RECHECK')
    def test_destroyed_dialog_does_not_receive_worker_callback(self):
        self.ready();started,release,calls,guard=self.blocked();dialog=CandidateEditDialog(self.w);dialog.show()
        with guard:
            self.move();self.assertTrue(wait_for_gui(started.is_set,2));dialog.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);release.set();wait_candidate_edits(self.w)
        self.assertTrue(self.w.candidates[0].formal_eligible)

    def test_nonformal_comparison_preserves_manual_until_explicit_safe_adoption(self):
        c=self.ready();original=c.template.to_dict();self.move();wait_candidate_edits(self.w);manual=self.w.candidates[0];manager=dispatcher(self.w);ready=[];manager.preview_ready.connect(lambda index,envelope,result:ready.append((envelope,result)))
        manager.preview(plan_original(self.w,0));wait_candidate_edits(self.w);self.assertEqual(len(ready),1);self.assertIs(self.w.candidates[0],manual);self.assertEqual(ready[0][1].template.to_dict(),original);self.assertTrue(ready[0][1].risk_context['comparison_only']);self.assertFalse(ready[0][1].formal_eligible);manager.adopt_preview(*ready[0]);self.assertEqual(self.w.candidates[0].template.to_dict(),original);self.assertTrue(self.w.candidates[0].formal_eligible)
        with self.assertRaises(ValueError):manager.adopt_preview(*ready[0])
    def test_failed_comparison_cannot_replace_manual_or_erase_hard_block(self):
        self.ready();self.move();wait_candidate_edits(self.w);self.w.people.item(0,2).setText('1234567890'*20);manager=dispatcher(self.w);ready=[];manager.preview_ready.connect(lambda index,envelope,result:ready.append((envelope,result)));manual=self.w.candidates[0];manager.preview(plan_original(self.w,0));wait_candidate_edits(self.w);self.assertEqual(ready[0][1].risk['state'],'HARD_BLOCKED')
        with self.assertRaisesRegex(ValueError,'完整Gate'):manager.adopt_preview(*ready[0])
        self.assertIs(self.w.candidates[0],manual)
    def test_changed_published_source_during_worker_invalidates_result(self):
        self.ready();started,release,calls,guard=self.blocked();manager=dispatcher(self.w);completed=[];manager.completed.connect(lambda index,result:completed.append(result))
        with guard:
            self.move();self.assertTrue(wait_for_gui(started.is_set,2));published=Template.from_dict(self.w.library.object_snapshot('TEMPLATE',self.t.id)['payload']);published.name+=' externally replaced';self.w.library.db.execute('UPDATE templates SET payload=? WHERE id=?',(json.dumps(published.to_dict()),published.id));self.w.library.db.commit();release.set();wait_candidate_edits(self.w)
        self.assertFalse(completed);self.assertFalse(self.w.candidates[0].formal_eligible)
    def test_actual_canvas_selection_resize_lock_and_keep_comparison(self):
        from PySide6.QtWidgets import QMessageBox
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt
        c=self.ready();dialog=CandidateEditDialog(self.w);self.addCleanup(dialog.deleteLater);dialog.show();identity=c.template.slots[0].id;dialog.current_canvas.select_id(identity);self.assertEqual(dialog.objects.selectedItems()[0].data(Qt.UserRole),identity);dialog.operation.setCurrentIndex(1);dialog.width.setValue(c.template.slots[0].rect.w-1);dialog.preview();self.assertIn('rect.w',dialog.details.toPlainText());self.assertIn('核心元素',dialog.details.toPlainText());dialog.compare();wait_candidate_edits(self.w);self.assertTrue(dialog.adopt_button.isEnabled());self.assertIs(self.w.candidates[0],c)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(dialog.adopt_button,Qt.LeftButton)
        self.assertEqual(self.w.candidates[0].template.slots[0].rect.w,c.template.slots[0].rect.w-1);dialog.preview_original();dialog.compare();wait_candidate_edits(self.w);current=self.w.candidates[0];QTest.mouseClick(dialog.keep_button,Qt.LeftButton);self.assertIs(self.w.candidates[0],current);self.assertFalse(dialog.adopt_button.isEnabled());dialog.operation.setCurrentIndex(2);dialog.preview()
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(dialog.apply_button,Qt.LeftButton)
        wait_candidate_edits(self.w);self.assertTrue(self.w.candidates[0].template.slots[0].locked)

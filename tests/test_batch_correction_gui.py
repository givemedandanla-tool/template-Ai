"""Real queued original worker and dialog scope/focus tests for batch source metadata."""
import copy,threading,unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QTimer,QPointF,QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox
from template_ai.batch_objects import BatchObjectDialog
from template_ai.storage import Library
from training_fixture import source_work
from gui_wait import wait_for_gui
import test_seventy_ui as fixture

APP=fixture.APP


class BatchCorrectionGuiTests(unittest.TestCase):
    setUp=fixture.SeventyUiTests.setUp
    close_window=fixture.SeventyUiTests.close_window
    def make(self,count=2):
        self.works=[source_work(self.w.library,self.root,f'gui-batch{i}.svg',note_text=str(i))[1] for i in range(count)];self.d=BatchObjectDialog(self.w);self.addCleanup(self.dispose);return self.d
    def dispose(self):
        if self.d.running:self.d.cancel();self.assertTrue(wait_for_gui(lambda:not self.d.running,5))
        self.d.deleteLater();APP.processEvents()
    def check(self,work,slot=0,checked=True):
        key='ARTWORK:'+work['id']+':'+work['payload']['slots'][slot]['id'];item=next(self.d.table.item(i,0) for i in range(self.d.table.rowCount()) if self.d.table.item(i,0).data(Qt.UserRole)==key);item.setCheckState(Qt.Checked if checked else Qt.Unchecked);return key
    def apply(self):
        with patch('template_ai.batch_objects.QMessageBox.question',return_value=QMessageBox.Yes):self.d.apply()
        self.assertTrue(wait_for_gui(lambda:not self.d.running,5),self.d.status.text())
    def test_sorted_filtered_hidden_selection_keeps_exact_ids_counts_and_only_selected_states(self):
        d=self.make();keys={self.check(self.works[0],2),self.check(self.works[1],0)};d.table.sortItems(2,Qt.DescendingOrder);d.search.setText('phone');self.assertEqual(set(d.selection_pin()),keys);self.assertIn('實際勾選 2',d.counts.text());self.assertIn('仍勾選 1',d.counts.text());d.preview();self.assertIsNotNone(d.plan,d.status.text());self.assertIn('預檢可修改 2',d.counts.text());self.assertEqual(sum(r['state']=='可核對套用' for r in d.rows),2);self.apply()
        self.assertEqual(self.w.library.artwork(self.works[0]['id'])['payload']['slots'][2]['align'],'center');self.assertEqual(self.w.library.artwork(self.works[0]['id'])['payload']['slots'][0]['align'],'left');self.assertEqual(self.w.library.artwork(self.works[1]['id'])['payload']['slots'][0]['align'],'center')
    def test_actual_confirmation_selection_race_rejects_without_starting_worker_or_writing(self):
        d=self.make();self.check(self.works[0]);d.preview();before=[self.w.library.artwork(w['id']) for w in self.works];errors=[]
        def change():
            box=QApplication.activeModalWidget()
            try:self.assertIsInstance(box,QMessageBox);self.check(self.works[1]);box.button(QMessageBox.Yes).click()
            except BaseException as error:errors.append(error)
            finally:
                if box and box.isVisible():box.reject()
        QTimer.singleShot(0,change);d.apply();self.assertFalse(errors,errors);self.assertFalse(d.running);self.assertIn('確認期間',d.status.text());self.assertEqual([self.w.library.artwork(w['id']) for w in self.works],before);self.assertFalse(self.w.busy)
    def test_actual_shared_worker_partial_states_and_no_unselected_false_success(self):
        self.make();work=self.works[1];payload=copy.deepcopy(work['payload']);payload['slots'][0]['locked']=True;self.w.library.save_artwork(work['id'],payload,work['revision']);self.d.reload();self.check(self.works[0]);self.check(self.works[1]);self.d.preview();pool=self.w.pool;self.apply()
        self.assertIs(self.w.pool,pool);self.assertEqual(pool.maxThreadCount(),1);self.assertEqual([r['outcome'] for r in self.d.results].count('APPLIED_PENDING_FULL_VALIDATION'),1);self.assertEqual([r['outcome'] for r in self.d.results].count('NEEDS_MANUAL_REVIEW'),1);self.assertEqual(sum(r['state']=='已處理／待整卡重驗' for r in self.d.rows),1);self.assertIn('預檢可修改 0',self.d.counts.text());self.assertIn('需人工 1',self.d.status.text())
    def test_close_cancels_unstarted_only_and_stays_open_until_current_transaction_finishes(self):
        d=self.make();[self.check(w) for w in self.works];d.preview();d.show();APP.processEvents();started=threading.Event();release=threading.Event();self.addCleanup(release.set);real=Library.apply_object_edit
        def blocked(library,*args):
            started.set()
            if not release.wait(4):raise RuntimeError('test-owned worker was not released')
            return real(library,*args)
        with patch.object(Library,'apply_object_edit',blocked),patch('template_ai.batch_objects.QMessageBox.question',return_value=QMessageBox.Yes):
            d.apply();self.assertTrue(wait_for_gui(started.is_set,2));self.assertFalse(d.close());self.assertTrue(d.running);release.set();self.assertTrue(wait_for_gui(lambda:not d.running,5))
        outcomes=[r['outcome'] for r in d.results];self.assertEqual(outcomes.count('APPLIED_PENDING_FULL_VALIDATION'),1);self.assertEqual(outcomes.count('CANCELLED'),1);self.assertTrue(d.close())
    def test_undo_one_original_transaction_keeps_other_source_and_counts_truthfully(self):
        d=self.make();[self.check(w) for w in self.works];d.preview();self.apply();self.check(self.works[1],checked=False)
        with patch('template_ai.batch_objects.QMessageBox.question',return_value=QMessageBox.Yes):d.undo()
        self.assertTrue(wait_for_gui(lambda:not d.running,5));self.assertEqual(self.w.library.artwork(self.works[0]['id'])['payload']['slots'][0]['align'],'left');self.assertEqual(self.w.library.artwork(self.works[1]['id'])['payload']['slots'][0]['align'],'center');self.assertIn('已回復 1',d.status.text())
    def test_locate_uses_current_exact_object_and_keeps_existing_pinned_tools_without_new_job(self):
        d=self.make(1);self.w.property_pin_checks['text'].setChecked(True);key=self.check(self.works[0],2);index=next(i for i in range(d.table.rowCount()) if d.table.item(i,0).data(Qt.UserRole)==key);d.table.setCurrentCell(index,2);d.locate();self.assertEqual(self.w.tabs.currentIndex(),0);self.assertEqual(self.w.current_slot.id,self.works[0]['payload']['slots'][2]['id']);self.assertTrue(self.w.property_pin_checks['text'].isChecked());self.assertFalse(self.w.busy)
    def test_located_pan_mouse_gesture_changes_only_view_and_never_creates_content_history(self):
        d=self.make(1);key=self.check(self.works[0],2);index=next(i for i in range(d.table.rowCount()) if d.table.item(i,0).data(Qt.UserRole)==key);d.table.setCurrentCell(index,2);d.locate();w=self.w;w.show();APP.processEvents();canvas=w.train_canvas;canvas.set_zoom(canvas.transform().m11()*2);before=copy.deepcopy(w.slots);r=w.current_slot.rect;point=canvas.mapFromScene(QPointF(r.x+r.w/2,r.y+r.h/2));centre=canvas.mapToScene(canvas.viewport().rect().center());QTest.mousePress(canvas.viewport(),Qt.LeftButton,pos=point);QTest.mouseMove(canvas.viewport(),point+QPoint(40,30));QTest.mouseRelease(canvas.viewport(),Qt.LeftButton,pos=point+QPoint(40,30));self.assertEqual(w.slots,before);self.assertFalse(w.undo_stack);self.assertGreater((canvas.mapToScene(canvas.viewport().rect().center())-centre).manhattanLength(),.1)
    def test_located_locked_source_properties_settle_without_overlapping_controls(self):
        d=self.make(1);work=self.works[0];payload=copy.deepcopy(work['payload']);payload['slots'][0]['locked']=True;self.w.library.save_artwork(work['id'],payload,work['revision']);d.reload();key=self.check(work);index=next(i for i in range(d.table.rowCount()) if d.table.item(i,0).data(Qt.UserRole)==key);d.table.setCurrentCell(index,2);self.w.resize(1360,940);self.w.show();d.locate();controls=[self.w.font_input,self.w.pt,self.w.text_color,self.w.scale,self.w.align,self.w.property_policy_button]
        def settled():return all(a.height()>=a.minimumSizeHint().height() and b.geometry().top()>a.geometry().bottom() for a,b in zip(controls,controls[1:]))
        self.assertTrue(wait_for_gui(settled,3),str([(c.y(),c.height(),c.minimumSizeHint().height()) for c in controls]));self.w.property_panel.ensureWidgetVisible(self.w.property_button);self.assertTrue(wait_for_gui(lambda:not self.w.property_button.visibleRegion().isEmpty(),2));self.assertEqual(self.w.pt.value(),18);self.assertTrue(self.w.current_slot.locked)

"""Actual Qt focus/composition/gesture events use existing exact-ID transactions."""
import copy,unittest
from PySide6.QtCore import Qt,QEvent,QPoint,QPointF
from PySide6.QtGui import QInputMethodEvent,QKeyEvent,QWheelEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
import test_property_selection as fixture

APP=fixture.APP


class CanvasCommandFocusTests(unittest.TestCase):
    setUp=fixture.PropertySelectionTests.setUp
    close_window=fixture.PropertySelectionTests.close_window
    def focus(self,widget):
        APP.processEvents();self.w.activateWindow();widget.setFocus();APP.processEvents();self.assertTrue(widget.hasFocus())
    def test_actual_focused_canvas_nudges_only_selected_mm_and_keeps_fixed_font(self):
        w=self.w;before=copy.deepcopy(w.template.slots);self.focus(w.edit_canvas);QTest.keyClick(w.edit_canvas,Qt.Key_Right)
        self.assertAlmostEqual(w.template.slots[0].rect.x,before[0].rect.x+.1);self.assertEqual(w.template.slots[1:],before[1:]);self.assertEqual(w.template.slots[0].size_pt,18);self.assertEqual(len(w.undo_stack),1)
    def test_text_delete_arrows_and_ctrlz_stay_in_real_property_field(self):
        w=self.w;before=w.template.to_dict();self.focus(w.text_color);w.text_color.selectAll();QTest.keyClicks(w.text_color,'#abcdef');QTest.keyClick(w.text_color,Qt.Key_Left);QTest.keyClick(w.text_color,Qt.Key_Delete);QTest.keyClick(w.text_color,Qt.Key_Z,Qt.ControlModifier)
        self.assertEqual(w.template.to_dict(),before);self.assertFalse(w.undo_stack);self.assertNotEqual(w.text_color.text(),'#111827')
    def test_numeric_and_combo_focus_never_dispatch_move_to_old_canvas_selection(self):
        w=self.w;before=w.template.to_dict()
        for control in [w.coords[0],w.font_input,w.kind]:
            self.focus(control);QTest.keyClick(control,Qt.Key_Up);QTest.keyClick(control,Qt.Key_Down)
        self.assertEqual(w.template.to_dict(),before);self.assertFalse(w.undo_stack)
    def test_ime_preedit_on_canvas_blocks_arrow_until_composition_ends(self):
        w=self.w;before=w.template.to_dict();self.focus(w.edit_canvas);APP.sendEvent(w.edit_canvas,QInputMethodEvent('中文',[]));QTest.keyClick(w.edit_canvas,Qt.Key_Right);self.assertEqual(w.template.to_dict(),before)
        APP.sendEvent(w.edit_canvas,QInputMethodEvent('',[]));QTest.keyClick(w.edit_canvas,Qt.Key_Right);self.assertAlmostEqual(w.template.slots[0].rect.x,8.1)
    def test_actual_text_preedit_leaves_selected_geometry_untouched(self):
        w=self.w;before=w.template.to_dict();self.focus(w.text_color);APP.sendEvent(w.text_color,QInputMethodEvent('中文',[]));QTest.keyClick(w.text_color,Qt.Key_Left);APP.sendEvent(w.text_color,QInputMethodEvent('',[]));self.assertEqual(w.template.to_dict(),before)
    def test_phone_table_real_editor_chinese_commit_and_cursor_do_not_move_old_selected_frame(self):
        from PySide6.QtWidgets import QLineEdit
        w=self.w;before=w.template.to_dict();w.tabs.setCurrentIndex(2);w.legacy_input_panel.setChecked(True);w.output_page_scroll.ensureWidgetVisible(w.people);APP.processEvents();self.focus(w.people);w.people.setCurrentCell(0,2);w.people.editItem(w.people.item(0,2));APP.processEvents();editor=APP.focusWidget();self.assertIsInstance(editor,QLineEdit)
        event=QInputMethodEvent();event.setCommitString('中文電話');APP.sendEvent(editor,event);self.assertIn('中文',editor.text());cursor=editor.cursorPosition();QTest.keyClick(editor,Qt.Key_Left);self.assertEqual(editor.cursorPosition(),cursor-1);self.assertEqual(w.template.to_dict(),before);self.assertFalse(w.undo_stack)
    def test_pinned_text_then_logo_keyboard_nudge_keeps_whole_logo_attributes(self):
        from template_ai.model import Slot,Rect
        w=self.w;w.property_pin_checks['text'].setChecked(True);logo=Slot('logo','c1',Rect(65,40,15,10));w.template.slots.append(logo);w.refresh_editor();w.editor_selection([logo.id]);APP.processEvents();w.right_context.sync();before=copy.deepcopy(w.template.slots[-1]);self.assertFalse(w.font_input.isEnabled());self.focus(w.edit_canvas);QTest.keyClick(w.edit_canvas,Qt.Key_Right);after=w.template.slots[-1];self.assertAlmostEqual(after.rect.x,before.rect.x+.1)
        expected=copy.deepcopy(before);expected.rect.x=after.rect.x;self.assertEqual(after,expected)
    def test_pending_property_prevents_canvas_nudge_without_losing_input(self):
        w=self.w;w.coords[0].setValue(12);self.focus(w.edit_canvas);QTest.keyClick(w.edit_canvas,Qt.Key_Right);self.assertEqual(w.template.slots[0].rect.x,8);self.assertEqual(w.coords[0].value(),12);self.assertIn('待套用',w.statusBar().currentMessage());self.assertFalse(w.undo_stack)
    def test_locked_or_stale_source_refuses_keyboard_geometry_without_transactions(self):
        w=self.w;w.template.slots[0].locked=True;w.refresh_editor();w.editor_selection([self.ids[0]]);self.focus(w.edit_canvas);QTest.keyClick(w.edit_canvas,Qt.Key_Right);self.assertEqual(w.template.slots[0].rect.x,8);self.assertFalse(w.undo_stack)
        w.template.slots[0].locked=False;w.refresh_editor();w.editor_selection([self.ids[0]]);changed=copy.deepcopy(w.template);changed.name+=' newer';w.library.save_template(changed,expected_revision=w.template_revision)
        self.focus(w.edit_canvas);QTest.keyClick(w.edit_canvas,Qt.Key_Right);self.assertEqual(w.template.slots[0].rect.x,8);self.assertIn('版本已變更',w.statusBar().currentMessage());self.assertFalse(w.undo_stack)
    def test_auto_repeat_does_not_submit_any_repeated_content_transaction(self):
        w=self.w;self.focus(w.edit_canvas);APP.sendEvent(w.edit_canvas,QKeyEvent(QEvent.KeyPress,Qt.Key_Right,Qt.NoModifier,'',True,5));self.assertEqual(w.template.slots[0].rect.x,8);self.assertFalse(w.undo_stack)
    def test_space_focus_loss_restores_exact_tool_and_selection_without_model_change(self):
        w=self.w;before=w.template.to_dict();self.focus(w.edit_canvas);QTest.keyPress(w.edit_canvas,Qt.Key_Space);self.assertEqual(w.edit_canvas.mode,'pan');self.focus(w.text_color)
        self.assertEqual(w.edit_canvas.mode,'edit');self.assertEqual(w.edit_canvas.selection_intent,{self.ids[0]});self.assertIsNone(w.edit_canvas.pan_restore);self.assertEqual(w.template.to_dict(),before)
    def test_actual_space_mouse_drag_changes_viewport_only(self):
        w=self.w;before=w.template.to_dict();canvas=w.edit_canvas;self.focus(canvas);QTest.keyPress(canvas,Qt.Key_Space);centre=canvas.mapToScene(canvas.viewport().rect().center());start=canvas.viewport().rect().center();QTest.mousePress(canvas.viewport(),Qt.LeftButton,pos=start);QTest.mouseMove(canvas.viewport(),start+QPoint(40,30));QTest.mouseRelease(canvas.viewport(),Qt.LeftButton,pos=start+QPoint(40,30));APP.processEvents();self.assertGreater((canvas.mapToScene(canvas.viewport().rect().center())-centre).manhattanLength(),.1);QTest.keyRelease(canvas,Qt.Key_Space);self.assertEqual(w.template.to_dict(),before);self.assertFalse(w.undo_stack)
    def test_ctrl_space_is_reserved_for_ime_and_never_starts_pan(self):
        w=self.w;self.focus(w.edit_canvas);QTest.keyClick(w.edit_canvas,Qt.Key_Space,Qt.ControlModifier);self.assertIsNone(w.edit_canvas.pan_restore);self.assertEqual(w.edit_canvas.mode,'edit')
    def test_wheel_without_canvas_focus_is_ignored_and_focused_zoom_is_view_only(self):
        w=self.w;before=w.template.to_dict();view=w.edit_canvas.transform();self.focus(w.text_color)
        def wheel():APP.sendEvent(w.edit_canvas.viewport(),QWheelEvent(QPointF(100,100),QPointF(100,100),QPoint(),QPoint(0,120),Qt.NoButton,Qt.NoModifier,Qt.NoScrollPhase,False))
        wheel();self.assertEqual(w.edit_canvas.transform(),view);self.focus(w.edit_canvas);wheel();self.assertNotEqual(w.edit_canvas.transform(),view);self.assertEqual(w.template.to_dict(),before);self.assertFalse(w.undo_stack)
    def test_unfocused_property_wheel_never_changes_numeric_draft_by_hover(self):
        w=self.w;self.focus(w.edit_canvas);before=w.coords[0].value();APP.sendEvent(w.coords[0],QWheelEvent(QPointF(10,10),QPointF(10,10),QPoint(),QPoint(0,120),Qt.NoButton,Qt.NoModifier,Qt.NoScrollPhase,False));self.assertEqual(w.coords[0].value(),before);self.assertFalse(w.navigation.pending_form())
        self.focus(w.coords[0]);APP.sendEvent(w.coords[0],QWheelEvent(QPointF(10,10),QPointF(10,10),QPoint(),QPoint(0,120),Qt.NoButton,Qt.NoModifier,Qt.NoScrollPhase,False));self.assertEqual(w.coords[0].value(),before+1);self.assertEqual(w.template.slots[0].rect.x,before);self.assertTrue(w.navigation.pending_form())
    def test_escape_cancels_only_unsubmitted_marking_rectangle(self):
        from template_ai.gui import Canvas
        canvas=Canvas();self.addCleanup(canvas.deleteLater);canvas.resize(600,400);canvas.set_content(90,54);canvas.set_mode('slot');canvas.show();canvas.activateWindow();canvas.setFocus();APP.processEvents();rectangles=[];canvas.rectangle.connect(rectangles.append)
        QTest.mousePress(canvas.viewport(),Qt.LeftButton,pos=QPoint(150,150));QTest.mouseMove(canvas.viewport(),QPoint(200,190));self.assertIsNotNone(canvas.rubber);QTest.keyClick(canvas,Qt.Key_Escape);QTest.mouseRelease(canvas.viewport(),Qt.LeftButton,pos=QPoint(200,190));self.assertEqual(rectangles,[]);self.assertIsNone(canvas.rubber);self.assertIsNone(canvas.start)

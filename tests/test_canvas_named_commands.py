"""Keyboard routes share original history, exact scope and real confirmation dialogs."""
import copy,unittest
from PySide6.QtCore import Qt,QTimer,QEvent
from PySide6.QtGui import QKeyEvent,QKeySequence
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtTest import QTest
from template_ai.editor_settings import COMMAND_KEYS,validate_commands,load_commands,EditorSettingsDialog
from template_ai.viewport_controls import dispatch_canvas_command
import test_canvas_command_focus as fixture

APP=fixture.APP


class CanvasNamedCommandTests(unittest.TestCase):
    setUp=fixture.CanvasCommandFocusTests.setUp
    close_window=fixture.CanvasCommandFocusTests.close_window
    focus=fixture.CanvasCommandFocusTests.focus
    def move(self):self.focus(self.w.edit_canvas);QTest.keyClick(self.w.edit_canvas,Qt.Key_Right)
    def key(self,key,modifier=Qt.NoModifier):
        if getattr(self,'_modal_ready',False):self._modal_ready=False
        else:self.focus(self.w.edit_canvas)
        QTest.keyClick(self.w.edit_canvas,key,modifier)
    def modal(self,action):
        self.focus(self.w.edit_canvas);self._modal_ready=True;errors=[]
        def run():
            dialog=QApplication.activeModalWidget()
            try:action(dialog)
            except BaseException as error:errors.append(error)
            finally:
                if dialog and dialog.isVisible():dialog.reject()
        QTimer.singleShot(0,run);return errors
    def test_canvas_ctrlz_and_redo_use_only_current_existing_work_stack(self):
        self.move();self.assertAlmostEqual(self.w.template.slots[0].rect.x,8.1);self.key(Qt.Key_Z,Qt.ControlModifier);self.assertEqual(self.w.template.slots[0].rect.x,8);self.assertEqual(len(self.w.redo_stack),1)
        self.key(Qt.Key_Y,Qt.ControlModifier);self.assertAlmostEqual(self.w.template.slots[0].rect.x,8.1);self.assertEqual(self.w.template.slots[0].size_pt,18);self.assertIsNone(self.w.pending_property_conflict)
    def test_ctrlz_in_text_field_after_canvas_edit_never_consumes_work_history(self):
        self.move();w=self.w;self.focus(w.text_color);w.text_color.selectAll();QTest.keyClicks(w.text_color,'#abcdef');QTest.keyClick(w.text_color,Qt.Key_Z,Qt.ControlModifier)
        self.assertAlmostEqual(w.template.slots[0].rect.x,8.1);self.assertEqual(len(w.undo_stack),1);self.assertEqual(w.text_color.text(),'#111827')
    def test_pending_property_blocks_work_undo_without_erasing_typed_value(self):
        self.move();self.w.coords[0].setValue(12);self.key(Qt.Key_Z,Qt.ControlModifier);self.assertAlmostEqual(self.w.template.slots[0].rect.x,8.1);self.assertEqual(self.w.coords[0].value(),12);self.assertEqual(len(self.w.undo_stack),1)
    def test_delete_opens_actual_exact_scope_preview_and_cancel_writes_nothing(self):
        from template_ai.object_dialog import ObjectToolsDialog
        w=self.w;before=w.library.object_snapshot('TEMPLATE',self.draft.id);seen=[]
        def inspect(d):
            self.assertIsInstance(d,ObjectToolsDialog);self.assertEqual(d.request['operation'],'DELETE');self.assertEqual(d.request['ids'],[self.ids[0]]);self.assertTrue(d.apply_button.isEnabled());seen.append(True)
        errors=self.modal(inspect);self.key(Qt.Key_Delete);self.assertFalse(errors,errors);self.assertEqual(seen,[True]);self.assertEqual(w.library.object_snapshot('TEMPLATE',self.draft.id),before);self.assertEqual(len(w.template.slots),4)
    def test_cross_person_delete_preview_requires_existing_explicit_scope_permission(self):
        from template_ai.model import Slot,Rect
        from template_ai.object_dialog import ObjectToolsDialog
        w=self.w;t=copy.deepcopy(w.template);t.capacity=2;t.slots.append(Slot('phone','p2',Rect(8,44,30,6)));w.library.save_template(t,expected_revision=w.template_revision);w.template=None;w.refresh_templates(t.id);ids=[t.slots[0].id,t.slots[-1].id];w.editor_selection(ids);before=w.library.object_snapshot('TEMPLATE',t.id);seen=[]
        def inspect(d):
            self.assertIsInstance(d,ObjectToolsDialog);self.assertEqual(set(d.ids),set(ids));self.assertIsNone(d.plan);self.assertIn('跨',d.status.text());self.assertFalse(d.apply_button.isEnabled());seen.append(True)
        errors=self.modal(inspect);self.key(Qt.Key_Delete);self.assertFalse(errors,errors);self.assertEqual(seen,[True]);self.assertEqual(w.library.object_snapshot('TEMPLATE',t.id),before)
    def test_undo_of_another_selection_requires_actual_scope_confirmation_and_cancel_keeps_history(self):
        self.move();w=self.w;w.editor_selection([self.ids[1]]);seen=[]
        def inspect(box):
            self.assertIsInstance(box,QMessageBox);self.assertIn(self.ids[0],box.text());seen.append(True);box.button(QMessageBox.No).click()
        errors=self.modal(inspect);self.key(Qt.Key_Z,Qt.ControlModifier);self.assertFalse(errors,errors);self.assertEqual(seen,[True]);self.assertAlmostEqual(w.template.slots[0].rect.x,8.1);self.assertEqual(len(w.undo_stack),1)
    def test_work_changed_inside_real_undo_confirmation_is_preserved_and_old_history_not_applied(self):
        self.move();w=self.w;w.editor_selection([self.ids[1]])
        def change(box):w.template.name+=' late human edit';box.button(QMessageBox.Yes).click()
        errors=self.modal(change);self.key(Qt.Key_Z,Qt.ControlModifier);self.assertFalse(errors,errors);self.assertIn('late human edit',w.template.name);self.assertAlmostEqual(w.template.slots[0].rect.x,8.1);self.assertEqual(len(w.undo_stack),1);self.assertIn('已變更',w.statusBar().currentMessage())
    def test_auto_repeat_and_reentry_cannot_consume_two_history_transactions(self):
        self.move();self.move();w=self.w;APP.sendEvent(w.edit_canvas,QKeyEvent(QEvent.KeyPress,Qt.Key_Z,Qt.ControlModifier,'z',True,5));self.assertEqual(len(w.undo_stack),2)
        w.edit_canvas.command_requested.connect(lambda command:dispatch_canvas_command(w.edit_canvas,command));self.key(Qt.Key_Z,Qt.ControlModifier);self.assertEqual(len(w.undo_stack),1);self.assertAlmostEqual(w.template.slots[0].rect.x,8.1);self.assertIn('未重複提交',w.statusBar().currentMessage())
    def test_stale_or_locked_history_is_not_popped_or_forced_into_current_model(self):
        self.move();w=self.w;w.editor_canvas_apply(dict(operation='LOCK',ids=[self.ids[0]],locked=True));self.key(Qt.Key_Z,Qt.ControlModifier);self.assertTrue(w.template.slots[0].locked);self.assertEqual(len(w.undo_stack),2)
        changed=copy.deepcopy(w.template);changed.name+=' external';w.library.save_template(changed,expected_revision=w.template_revision);self.key(Qt.Key_Z,Qt.ControlModifier);self.assertEqual(len(w.undo_stack),2);self.assertIn('版本已變更',w.statusBar().currentMessage())
    def test_invalid_keymap_rejects_whole_settings_save_before_any_preference_write(self):
        w=self.w;d=EditorSettingsDialog(w);self.addCleanup(d.deleteLater);before=w.library.db.total_changes;d.step.setValue(.5);d.command_keys['REDO'].setKeySequence(QKeySequence('Ctrl+Z'));d.save();self.assertIn('衝突',d.status.text());self.assertEqual(w.library.db.total_changes,before);self.assertEqual(w.edit_canvas.nudge_mm,.1)
    def test_explicit_remap_persists_in_existing_preferences_and_old_key_no_longer_undoes(self):
        self.move();w=self.w;before=w.library.object_snapshot('TEMPLATE',self.draft.id);d=EditorSettingsDialog(w);self.addCleanup(d.deleteLater)
        for name,key in [('UNDO','F7'),('REDO','F8'),('DELETE','F9')]:d.command_keys[name].setKeySequence(QKeySequence(key))
        d.save();self.assertEqual(load_commands(w.library),dict(UNDO='F7',REDO='F8',DELETE='F9'));self.assertEqual(w.edit_canvas.command_bindings,load_commands(w.library));self.key(Qt.Key_Z,Qt.ControlModifier);self.assertEqual(len(w.undo_stack),1);self.key(Qt.Key_F7);self.assertEqual(w.template.slots[0].rect.x,8);self.assertEqual(w.library.object_snapshot('TEMPLATE',self.draft.id),before)


class CanvasKeymapValidationTests(unittest.TestCase):
    def test_duplicate_normalized_keys_rejected(self):
        with self.assertRaisesRegex(ValueError,'衝突'):validate_commands(dict(UNDO='Delete',REDO='Ctrl+Y',DELETE='Del'))
    def test_reserved_ime_system_clipboard_navigation_and_chords_rejected(self):
        for raw in ['Ctrl+Space','Alt+F4','Ctrl+Alt+Del','Ctrl+C','Ctrl+V','Ctrl+A','Ctrl+0','Ctrl++','Left','Shift+Left','Tab','F1','Ctrl+K, Ctrl+C','unknown']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):validate_commands(dict(COMMAND_KEYS,UNDO=raw))
    def test_empty_disables_and_portable_delete_alias_is_canonical(self):
        self.assertEqual(validate_commands(dict(UNDO='',REDO='Ctrl+Y',DELETE='Delete')),dict(UNDO='',REDO='Ctrl+Y',DELETE='Del'))
    def test_unknown_command_scope_or_nontext_value_rejected(self):
        for value in [dict(COMMAND_KEYS,EXPORT='F9'),dict(COMMAND_KEYS,UNDO=True),None]:
            with self.assertRaises(ValueError):validate_commands(value)

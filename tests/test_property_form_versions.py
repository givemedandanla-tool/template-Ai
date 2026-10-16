"""Mode memory and unfinished numeric input must retain their original source version."""
import copy,unittest
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from test_workbench_navigation import click_message
import test_property_selection as fixture

APP=fixture.APP


class PropertyFormVersionTests(unittest.TestCase):
    def setUp(self):fixture.PropertySelectionTests.setUp(self);APP.processEvents();self.w.right_context.sync();APP.processEvents()
    close_window=fixture.PropertySelectionTests.close_window
    def replace_while_in_other_mode(self):
        w=self.w;w.tabs.setCurrentIndex(0);changed=copy.deepcopy(w.template);changed.slots[0].rect.x+=3
        w.library.save_template(changed,expected_revision=w.template_revision)
        w.template=None;w.refresh_templates(changed.id);w.tabs.setCurrentIndex(1);APP.processEvents();return w.template.slots[0]
    def test_old_mode_values_and_undo_are_not_restored_into_newer_same_id_source(self):
        w=self.w;w.undo_stack.append(copy.deepcopy(w.template.slots));current=self.replace_while_in_other_mode()
        self.assertEqual(w.coords[0].value(),current.rect.x);self.assertFalse(w.navigation.pending_form());self.assertEqual(w.undo_stack,[])
    def test_old_mode_pending_values_are_retained_as_conflict_without_retargeting_new_source(self):
        w=self.w;w.coords[0].setValue(77);current=self.replace_while_in_other_mode()
        self.assertEqual(w.coords[0].value(),current.rect.x);self.assertIsNotNone(w.pending_property_conflict);self.assertEqual(w.pending_property_conflict['values']['coords'][0],77);self.assertEqual(current.rect.x,11)
    def test_unfinished_numeric_input_blocks_apply_without_fake_history(self):
        w=self.w;editor=w.coords[0];editor.setFocus();editor.selectAll();QTest.keyClicks(editor,'-');self.assertFalse(editor.hasAcceptableInput());before=w.template.to_dict();count=len(w.undo_stack)
        with patch.object(w,'error') as error:w.apply_properties();self.assertEqual(error.call_count,1)
        self.assertEqual(w.template.to_dict(),before);self.assertEqual(len(w.undo_stack),count)
    def test_unfinished_numeric_input_is_pending_and_stay_preserves_it(self):
        w=self.w;editor=w.coords[0];editor.setFocus();editor.selectAll();QTest.keyClicks(editor,'-');self.assertTrue(w.navigation.pending_form())
        QTimer.singleShot(0,lambda:click_message('返回目前物件繼續編輯'));w.editor_selection([self.ids[1]])
        self.assertEqual(w.current_slot.id,self.ids[0]);self.assertEqual(w.coords[0].cleanText(),'-')

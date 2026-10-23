"""Mode memory and unfinished numeric input must retain their original source version."""
import copy,unittest
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtTest import QTest
from test_workbench_navigation import click_message
import test_property_selection as fixture
import test_property_lifecycle as lifecycle_fixture

APP=fixture.APP


class PropertyFormVersionTests(unittest.TestCase):
    def setUp(self):fixture.PropertySelectionTests.setUp(self);APP.processEvents();self.w.right_context.sync();APP.processEvents()
    close_window=fixture.PropertySelectionTests.close_window
    dialog=lifecycle_fixture.PropertyLifecycleTests.dialog
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
    def test_unfinished_main_number_survives_unchanged_mode_roundtrip(self):
        w=self.w;editor=w.coords[0];editor.setFocus();editor.selectAll();QTest.keyClicks(editor,'-');w.tabs.setCurrentIndex(0);w.tabs.setCurrentIndex(1);APP.processEvents()
        self.assertEqual(w.coords[0].cleanText(),'-');self.assertTrue(w.navigation.pending_form());self.assertEqual(w.current_slot.rect.x,8)
    def test_existing_editor_unfinished_number_blocks_preview_and_stay_keeps_raw_text(self):
        d=self.dialog();editor=d.editors['x'];editor.setFocus();editor.selectAll();QTest.keyClicks(editor,'-');self.assertIn('x',d.dirty);self.assertIn('x',d.incomplete_inputs)
        before=self.w.library.object_snapshot('TEMPLATE',self.draft.id);d.preview_patch();self.assertIsNone(d.plan);self.assertFalse(d.apply_button.isEnabled());self.assertIn('尚未完成',d.status.text())
        QTimer.singleShot(0,lambda:click_message('返回目前物件繼續編輯'));d.reject();self.assertTrue(d.isVisible());self.assertEqual(d.editors['x'].cleanText(),'-');self.assertEqual(self.w.library.object_snapshot('TEMPLATE',self.draft.id),before)
    def test_existing_editor_stale_retains_unfinished_raw_input_with_old_owner(self):
        d=self.dialog();editor=d.editors['x'];editor.setFocus();editor.selectAll();QTest.keyClicks(editor,'-');changed=copy.deepcopy(self.w.template);changed.name+=' new';self.w.library.save_template(changed,expected_revision=d.snapshot['revision'])
        d.update_context();self.assertEqual(d.ids,[]);self.assertFalse(d.objects.selectedItems());self.assertEqual(d.retained_patch['ids'],[self.ids[0]]);self.assertIn('-',d.retained_patch['incomplete']['x']);self.assertFalse(d.apply_button.isEnabled())
    def test_current_model_replacement_rebinds_controls_and_retains_pending_values_without_db_write(self):
        w=self.w;before=w.library.object_snapshot('TEMPLATE',self.draft.id);w.coords[0].setValue(77);replacement=copy.deepcopy(w.template);replacement.slots[0].rect.x=11;w.template=replacement;w.right_context.sync()
        self.assertIs(w.current_slot,w.template.slots[0]);self.assertEqual(w.coords[0].value(),11);self.assertEqual(w.pending_property_conflict['values']['coords'][0],77);self.assertEqual(w.library.object_snapshot('TEMPLATE',self.draft.id),before)
    def test_identical_same_source_model_refresh_rebinds_pointer_and_keeps_unapplied_values(self):
        w=self.w;w.coords[0].setValue(77);w.template=copy.deepcopy(w.template);w.right_context.sync()
        self.assertIs(w.current_slot,w.template.slots[0]);self.assertEqual(w.coords[0].value(),77);self.assertTrue(w.navigation.pending_form());self.assertIsNone(w.pending_property_conflict)
    def test_successful_explicit_apply_does_not_archive_its_own_values_as_a_version_conflict(self):
        w=self.w;w.coords[0].setValue(9);w.apply_properties();APP.processEvents();self.assertEqual(w.template.slots[0].rect.x,9);self.assertIsNone(w.pending_property_conflict);self.assertFalse(w.navigation.pending_form())
    def test_save_draft_with_unapplied_fields_keeps_them_pending_without_claiming_saved(self):
        w=self.w;before=w.library.object_snapshot('TEMPLATE',self.draft.id);w.coords[0].setValue(10);w.save_draft();APP.processEvents()
        self.assertEqual(w.coords[0].value(),10);self.assertTrue(w.navigation.pending_form());self.assertEqual(w.library.object_snapshot('TEMPLATE',self.draft.id),before);self.assertIn('待套用',w.statusBar().currentMessage())

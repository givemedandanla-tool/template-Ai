"""Pending property input belongs to exact original selection, never a new object."""
import copy,unittest
from PySide6.QtCore import Qt,QTimer
from template_ai.demo import demo_template
from template_ai.object_dialog import ObjectToolsDialog
from test_workbench_navigation import click_message
import test_seventy_ui as fixture

APP=fixture.APP


class PropertySelectionTests(unittest.TestCase):
    def setUp(self):
        fixture.SeventyUiTests.setUp(self);self.draft=demo_template();self.w.library.save_template(self.draft)
        self.w.refresh_templates(self.draft.id);self.w.tabs.setCurrentIndex(1);self.w.template_stack.setCurrentIndex(1)
        self.w.show();APP.processEvents();self.ids=[s.id for s in self.w.template.slots];self.w.editor_selection([self.ids[0]])
    close_window=fixture.SeventyUiTests.close_window
    def dialog(self):
        d=ObjectToolsDialog(self.w,'TEMPLATE',self.draft.id);self.addCleanup(d.deleteLater);d.show();APP.processEvents();d.select_ids([self.ids[0]]);return d
    def test_main_stay_keeps_original_pending_value_and_three_way_selection_without_db_write(self):
        w=self.w;before=w.template.to_dict();changes=w.library.db.total_changes;old=w.coords[0].value();w.coords[0].setValue(old+1)
        QTimer.singleShot(0,lambda:click_message('返回目前物件繼續編輯'));w.editor_selection([self.ids[1]])
        self.assertEqual(w.current_slot.id,self.ids[0]);self.assertEqual(w.coords[0].value(),old+1);self.assertEqual(w.edit_canvas.selection_intent,{self.ids[0]})
        self.assertTrue(w.navigation.pending_form());self.assertEqual(w.template.to_dict(),before);self.assertEqual(w.library.db.total_changes,changes)
    def test_main_explicit_discard_selects_new_object_without_transferring_old_value(self):
        w=self.w;before=w.template.to_dict();w.coords[0].setValue(77)
        QTimer.singleShot(0,lambda:click_message('放棄未套用輸入並切換'));w.editor_selection([self.ids[1]])
        self.assertEqual(w.current_slot.id,self.ids[1]);self.assertEqual(w.coords[0].value(),w.template.slots[1].rect.x);self.assertEqual(w.template.to_dict(),before);self.assertFalse(w.navigation.pending_form())
    def test_reselecting_same_object_never_clears_unapplied_value(self):
        w=self.w;w.coords[0].setValue(77);w.editor_selection([self.ids[0]]);self.assertEqual(w.coords[0].value(),77);self.assertTrue(w.navigation.pending_form())
    def test_actual_model_move_updates_display_without_becoming_fake_unapplied_input(self):
        w=self.w;original=w.current_slot.rect.x
        w.editor_canvas_apply(dict(operation='MOVE',ids=[self.ids[0]],dx=2,dy=0,cross_owner=False))
        self.assertEqual(w.current_slot.rect.x,original+2);self.assertEqual(w.coords[0].value(),original+2);self.assertFalse(w.navigation.pending_form())
    def test_replaced_same_id_retains_old_pending_diagnostic_without_applying_to_new_version(self):
        w=self.w;old=w.current_slot;w.coords[0].setValue(77);replacement=copy.deepcopy(old);replacement.rect.x+=2;w.template.slots[0]=replacement
        w.select_slot(replacement);self.assertIs(w.current_slot,replacement);self.assertEqual(w.coords[0].value(),replacement.rect.x)
        self.assertEqual(w.pending_property_conflict['slot_id'],old.id);self.assertEqual(w.pending_property_conflict['values']['coords'][0],77);self.assertFalse(w.navigation.pending_form())
    def test_existing_object_editor_stay_preserves_dirty_value_and_original_ids(self):
        d=self.dialog();changes=self.w.library.db.total_changes;original=d.editors['x'].value();d.editors['x'].setValue(original+1)
        QTimer.singleShot(0,lambda:click_message('返回目前物件繼續編輯'));d.select_ids([self.ids[1]])
        self.assertEqual(d.ids,[self.ids[0]]);self.assertEqual(d.editors['x'].value(),original+1);self.assertEqual(d.dirty,{'x'});self.assertEqual(d.canvas.selection_intent,{self.ids[0]});self.assertEqual(self.w.library.db.total_changes,changes)
    def test_existing_object_editor_discard_keeps_untouched_model_and_loads_new_selection(self):
        d=self.dialog();before=self.w.library.object_snapshot('TEMPLATE',self.draft.id);d.editors['x'].setValue(77)
        QTimer.singleShot(0,lambda:click_message('放棄未套用輸入並切換'));d.select_ids([self.ids[1]])
        self.assertEqual(d.ids,[self.ids[1]]);self.assertFalse(d.dirty);self.assertEqual(d.editors['x'].value(),self.w.template.slots[1].rect.x);self.assertEqual(self.w.library.object_snapshot('TEMPLATE',self.draft.id),before)

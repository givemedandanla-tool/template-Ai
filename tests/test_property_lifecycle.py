"""Actual locked/current-version/close/reload safety of the reused object editor."""
import copy,unittest
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox
from template_ai.object_dialog import ObjectToolsDialog
from template_ai.property_context import load_tool_pins
from test_workbench_navigation import click_message
import test_property_selection as fixture

APP=fixture.APP


class PropertyLifecycleTests(unittest.TestCase):
    setUp=fixture.PropertySelectionTests.setUp
    close_window=fixture.PropertySelectionTests.close_window
    def dialog(self):
        d=ObjectToolsDialog(self.w,'TEMPLATE',self.draft.id);self.addCleanup(d.deleteLater);d.show();APP.processEvents();d.select_ids([self.ids[0]]);return d
    def test_actual_close_stay_then_explicit_discard_preserves_model(self):
        d=self.dialog();before=self.w.library.object_snapshot('TEMPLATE',self.draft.id);d.editors['x'].setValue(77)
        QTimer.singleShot(0,lambda:click_message('返回目前物件繼續編輯'));d.reject();self.assertTrue(d.isVisible());self.assertEqual(d.editors['x'].value(),77);self.assertEqual(d.dirty,{'x'})
        QTimer.singleShot(0,lambda:click_message('放棄未套用輸入並關閉'));d.reject();self.assertFalse(d.isVisible());self.assertFalse(d.dirty);self.assertEqual(self.w.library.object_snapshot('TEMPLATE',self.draft.id),before)
    def test_actual_reload_stay_retains_input_and_discard_reloads_without_automatic_adoption(self):
        d=self.dialog();before=self.w.library.object_snapshot('TEMPLATE',self.draft.id);d.editors['x'].setValue(77)
        QTimer.singleShot(0,lambda:click_message('返回目前物件繼續編輯'));d.reload();self.assertEqual(d.editors['x'].value(),77);self.assertEqual(d.dirty,{'x'})
        QTimer.singleShot(0,lambda:click_message('放棄未套用輸入並重新載入'));d.reload();self.assertFalse(d.dirty);self.assertEqual(d.ids,[]);self.assertEqual(self.w.library.object_snapshot('TEMPLATE',self.draft.id),before)
    def test_stale_source_clears_active_selection_preserves_typed_patch_and_never_previews_or_applies(self):
        d=self.dialog();d.editors['x'].setValue(77);changed=copy.deepcopy(self.w.template);changed.name+=' newer';self.w.library.save_template(changed,expected_revision=d.snapshot['revision']);before=self.w.library.object_snapshot('TEMPLATE',self.draft.id)
        d.update_context();self.assertEqual(d.ids,[]);self.assertFalse(d.editors['x'].isEnabled());self.assertEqual(d.editors['x'].value(),d.editors['x'].minimum());self.assertEqual(d.retained_patch['patch']['x'],77);self.assertEqual(d.retained_patch['ids'],[self.ids[0]])
        d.preview_patch();d.apply();self.assertFalse(d.apply_button.isEnabled());self.assertEqual(self.w.library.object_snapshot('TEMPLATE',self.draft.id),before);self.assertIn('已變更',d.status.text())
    def test_locked_existing_object_disables_value_tools_but_explicit_unlock_uses_original_pipeline(self):
        d=self.dialog();d.preview_lock(True)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):d.apply()
        d.select_ids([self.ids[0]]);self.assertTrue(self.w.library.object_snapshot('TEMPLATE',self.draft.id)['payload']['slots'][0]['locked']);self.assertTrue(all(not editor.isEnabled() for editor in d.editors.values()));self.assertFalse(d.font_choice.isEnabled());self.assertIn('鎖定',d.context_status.text())
        d.preview_lock(False);self.assertEqual(d.plan['request']['operation'],'LOCK');self.assertTrue(d.apply_button.isEnabled())
    def test_pin_preferences_share_existing_main_controls_without_changing_object(self):
        d=self.dialog();before=self.w.library.object_snapshot('TEMPLATE',self.draft.id);d.pin_text.setChecked(True)
        self.assertIn('text',load_tool_pins(self.w.library));self.assertTrue(self.w.property_pin_checks['text'].isChecked());self.assertFalse(d.dirty);self.assertEqual(self.w.library.object_snapshot('TEMPLATE',self.draft.id),before)
    def test_new_selection_does_not_inherit_previous_cross_owner_scope_confirmation(self):
        d=self.dialog();d.cross.setChecked(True);d.select_ids([self.ids[1]]);self.assertFalse(d.cross.isChecked());self.assertEqual(d.ids,[self.ids[1]])
    def test_main_close_impact_includes_unapplied_existing_dialog_fields(self):
        d=self.dialog();d.editors['x'].setValue(77);self.assertTrue(any('物件編輯器' in impact for impact in self.w.navigation.close_impacts()));self.assertEqual(self.w.current_slot.rect.x,self.w.template.slots[0].rect.x)

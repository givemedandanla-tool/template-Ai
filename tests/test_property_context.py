"""Existing widget applicability/pins/mixed values and current hard gates."""
import copy,unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton
from PySide6.QtTest import QTest
from template_ai.gui import MainWindow
from template_ai.model import Slot,Rect
from template_ai.property_context import load_tool_pins
import test_property_selection as fixture
from gui_wait import wait_for_gui

APP=fixture.APP


class PropertyContextTests(unittest.TestCase):
    setUp=fixture.PropertySelectionTests.setUp
    close_window=fixture.PropertySelectionTests.close_window
    def sync(self):APP.processEvents();self.w.right_context.sync();APP.processEvents()
    def logo(self):
        logo=Slot('logo','c1',Rect(65,40,15,10));self.w.template.slots.append(logo);self.w.refresh_editor();self.w.editor_selection([logo.id]);self.sync();return logo
    def test_text_context_uses_original_fixed_size_and_collapse_does_not_modify_model(self):
        w=self.w;self.sync();before=w.template.to_dict();self.assertIn('文字物件',w.property_context_label.text());self.assertTrue(w.font.isEnabled());self.assertEqual(w.pt.value(),18)
        for group in w.property_groups.values():group.setChecked(False);group.setChecked(True)
        w.all_property_tools.setChecked(True);self.sync();self.assertEqual(w.template.to_dict(),before);self.assertEqual(w.pt.value(),18)
    def test_pinned_text_stays_visible_but_disabled_for_whole_logo_and_never_changes_it(self):
        w=self.w;w.property_pin_checks['text'].setChecked(True);logo=self.logo();before=copy.deepcopy(logo)
        self.assertTrue(w.property_groups['text'].isVisible());self.assertIn('不適用',w.property_groups['text'].title());self.assertFalse(w.font.isEnabled());self.assertFalse(w.scale.isEnabled());self.assertFalse(w.property_policy_button.isEnabled())
        self.assertTrue(w.coords[0].isEnabled());w.all_property_tools.setChecked(True);self.sync();self.assertEqual(logo,before)
    def test_multiple_different_fields_have_blank_mixed_values_and_reuse_existing_editor_ids(self):
        from template_ai.object_dialog import ObjectToolsDialog
        w=self.w;before=w.template.to_dict();w.editor_selection(self.ids[:2]);self.sync()
        self.assertIn('混合',w.property_context_label.text());self.assertEqual(w.pt.cleanText(),'');self.assertFalse(w.pt.isEnabled());self.assertFalse(w.property_button.isEnabled());self.assertTrue(w.property_object_tools.isEnabled())
        scopes=[]
        def inspect(dialog):scopes.append(dialog.ids.copy());return 0
        with patch.object(ObjectToolsDialog,'exec',new=inspect):QTest.mouseClick(w.property_object_tools,Qt.LeftButton)
        self.assertEqual(set(scopes[0]),set(self.ids[:2]));self.assertEqual(w.template.to_dict(),before)
    def test_no_selection_disables_old_values_and_new_frame_uses_legal_original_defaults(self):
        w=self.w;w.select_slot(None);w.edit_canvas.select_ids([]);self.sync();self.assertIn('尚未選取',w.property_context_label.text());self.assertFalse(w.property_button.isEnabled())
        self.assertFalse(w.property_groups['text'].isVisible());new=w.make_slot(Rect(5,45,15,5));self.assertEqual(new.kind,'name');self.assertEqual(new.owner,'p1');self.assertTrue(new.font);self.assertEqual(new.color,'#111827');self.assertEqual(new.align,'left');self.assertGreater(new.size_pt,0)
    def test_only_explicit_pin_preference_persists_and_reopened_window_reads_it_without_business_change(self):
        w=self.w;before=w.library.object_snapshot('TEMPLATE',self.draft.id);w.property_pin_checks['text'].setChecked(True);self.assertEqual(load_tool_pins(w.library),{'text'})
        other=MainWindow(w.library.root);self.addCleanup(other.deleteLater);self.addCleanup(other.library.close);self.addCleanup(other.font_manager.close)
        self.assertTrue(other.property_pin_checks['text'].isChecked());self.assertEqual(w.library.object_snapshot('TEMPLATE',self.draft.id),before)
    def test_stale_source_clears_active_controls_and_keeps_unapplied_conflict_readonly(self):
        w=self.w;w.coords[0].setValue(77);changed=copy.deepcopy(w.template);changed.name+=' external'
        # Authored external replacement via supported draft CAS; current UI base is now old.
        w.library.save_template(changed,expected_revision=w.template_revision);self.sync()
        self.assertIsNone(w.current_slot);self.assertFalse(w.property_button.isEnabled());self.assertFalse(w.coords[0].isEnabled());self.assertEqual(w.coords[0].cleanText(),'')
        self.assertEqual(w.pending_property_conflict['values']['coords'][0],77);self.assertIn('需重新驗證',w.property_edit_state.text());self.assertTrue(any('舊物件' in row for row in w.navigation.close_impacts()))
    def test_narrow_panel_scroll_keeps_apply_and_conflict_status_reachable(self):
        w=self.w;w.resize(960,640);w.workspace_splitter.setSizes([140,590,220]);w.all_property_tools.setChecked(True);self.sync();w.property_panel.ensureWidgetVisible(w.property_button)
        self.assertTrue(wait_for_gui(lambda:not w.property_button.visibleRegion().isEmpty(),2));self.assertTrue(w.property_edit_state.isEnabled());self.assertEqual(w.template.slots[0].size_pt,18)


import test_candidate_results as results_fixture


class CandidatePropertyGateTests(unittest.TestCase):
    def setUp(self):results_fixture.CandidateResultsTests.setUp(self);self.w.tabs.setCurrentIndex(2);self.w.show();APP.processEvents()
    close_window=results_fixture.CandidateResultsTests.close_window
    ready=results_fixture.CandidateResultsTests.ready
    another=results_fixture.CandidateResultsTests.another
    def test_pins_all_properties_and_hidden_panel_never_relax_actual_hard_block(self):
        self.ready();bad=self.another(width=.1);w=self.w;w.candidate_list.setCurrentRow(1);w.right_context.sync();before=bad.risk['digest']
        w.property_pin_checks['text'].setChecked(True);w.all_property_tools.setChecked(True)
        for group in w.property_groups.values():group.setChecked(False)
        w.property_panel.hide();APP.processEvents();self.assertFalse(w.export_button.isEnabled());self.assertFalse(bad.formal_eligible);self.assertEqual(bad.risk['digest'],before)
    def test_problem_selection_and_input_staleness_keep_same_object_scope_and_disable_old_correction(self):
        from template_ai.candidate_results import problem_rows,locate_problem
        self.ready();self.another(width=.1);w=self.w;row=next(r for r in problem_rows(w,1) if r['slot_ids']);locate_problem(w,row,open_input=False);APP.processEvents();w.right_context.sync()
        self.assertIn('文字物件',w.property_context_label.text());self.assertFalse(w.property_button.isEnabled());self.assertTrue(w.property_candidate_edit.isEnabled())
        w.people.item(0,2).setText('1234567890'*20);APP.processEvents();w.right_context.sync();self.assertFalse(w.property_candidate_edit.isEnabled());self.assertFalse(w.property_problem.isEnabled());self.assertFalse(w.export_button.isEnabled());self.assertIn('需重新',w.property_edit_state.text())

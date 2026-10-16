"""Actual native seven-page GUI using owned quality workers, not placeholder tabs."""
import unittest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QComboBox
import test_quality_panel as gui_fixture
import test_quality_gold_sets as fixtures
from template_ai.quality_repair_dialog import QualityRepairDialog,TITLES
from template_ai.quality_repairs import QualityRepairs
from template_ai.training_quality_dialog import TrainingQualityDialog

APP=QApplication.instance() or QApplication([])


class QualityRepairGuiTests(unittest.TestCase):
    setUp=fixtures.QualityGoldSetTests.setUp
    window=gui_fixture.QualityPanelTests.window
    panel=gui_fixture.QualityPanelTests.panel
    wait=gui_fixture.QualityPanelTests.wait

    def dialog(self):
        panel=self.panel();dialog=QualityRepairDialog(panel);dialog.show();self.addCleanup(dialog.deleteLater);return panel,dialog

    def test_seven_actual_tabs_are_lazy_with_unchecked_truth_roles_and_confirmation(self):
        panel,dialog=self.dialog();self.assertEqual([dialog.tabs.tabText(i) for i in range(dialog.tabs.count())],list(TITLES))
        self.assertFalse(panel.loading);self.assertFalse(dialog.consent.isChecked());self.assertFalse(dialog.original_reviewed.isChecked());self.assertFalse(dialog.truth_reviewed.isChecked());self.assertEqual(dialog.layer.currentData(),None)
        self.assertEqual(dialog.roles,{});self.assertEqual(dialog.work_table.rowCount(),0);self.assertTrue(dialog.source_work.isReadOnly())
        for index in range(7):dialog.tabs.setCurrentIndex(index);APP.processEvents()
        self.assertEqual(self.store.count('QUALITY_REPAIR_ISSUE'),0);self.assertEqual(self.store.count('AUTO_JOB'),0)

    def test_actual_preview_confirm_root_and_changed_input_invalidates_preview(self):
        panel,dialog=self.dialog();dialog.actor.setText('Synthetic reviewer');dialog.reason.setText('Actual source and bounded repair scope reviewed')
        dialog.source_work.setText(self.work['id']);dialog.description.setText('Synthetic original source discrepancy');dialog.source_issue('SOURCE_FACTS',self.work['id']);self.wait(panel)
        self.assertIsNotNone(dialog.pending);self.assertFalse(dialog.consent.isChecked())
        dialog.guard(dialog.confirm);self.assertEqual(self.store.count('QUALITY_REPAIR_ISSUE'),0)
        dialog.consent.setChecked(True);dialog.confirm();self.wait(panel);self.assertIsNotNone(dialog.issue);self.assertEqual(self.store.count('QUALITY_REPAIR_ISSUE'),1)
        dialog.layer.setCurrentIndex(dialog.layer.findData('NOISE_RULE'));dialog.hypothesis.setText('Potential narrow annotation context');dialog.evidence.setText('Actual confirmed source and negative context')
        dialog.preview('REPAIR_ROOT_PLAN',dict(identity=dialog.issue['id'],layer='NOISE_RULE',hypothesis=dialog.hypothesis.text(),evidence=dialog.evidence.text(),original_reviewed=False,truth_reviewed=False),'ROOT');self.wait(panel)
        self.assertFalse(dialog.pending[1]['can_prepare_candidate']);dialog.hypothesis.setText('Edited hypothesis');self.assertIsNone(dialog.pending);self.assertFalse(dialog.consent.isChecked())

    def test_actual_holdout_metadata_rows_have_disabled_train_choices_and_remain_unselected(self):
        gold=self.gold.confirm(fixtures.QualityGoldSetTests.plan(self),'Reviewer',True);self.sets.create(self.sets.plan('Native heldout catalog',[gold['id']],True,True,'Actual whole source reserved'),'Reviewer',True)
        panel,dialog=self.dialog();dialog.tabs.setCurrentIndex(2);dialog.work_page(0);self.wait(panel)
        self.assertEqual(dialog.work_table.rowCount(),1);combo=dialog.work_table.cellWidget(0,2);self.assertIsInstance(combo,QComboBox)
        self.assertIsNone(combo.currentData());self.assertFalse(combo.model().item(1).isEnabled());self.assertFalse(combo.model().item(2).isEnabled());self.assertEqual(dialog.roles,{})

    def test_native_source_entry_preserves_pending_human_editor_and_background_close_is_guarded(self):
        window=self.window();center=TrainingQualityDialog(window);self.addCleanup(center.deleteLater)
        dialog=QualityRepairDialog(center.quality_panel);self.addCleanup(dialog.deleteLater);dialog.show();center.facts_panel.focus(self.work['id'],[])
        center.facts_panel.observed_text.setText('Unsaved human editor content')
        dialog.source_work.setText('different-work');dialog.guard(dialog.source_facts);self.assertIn('未套用',dialog.status.text());self.assertEqual(center.facts_panel.observed_text.text(),'Unsaved human editor content')
        center.quality_panel.loading=True;dialog.reject();self.assertTrue(dialog.isVisible());center.quality_panel.loading=False;dialog.reject();self.assertFalse(dialog.isVisible())

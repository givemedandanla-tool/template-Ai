"""Actual qualified coverage through owned worker; no implicit training or stale source return."""
import unittest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import test_quality_panel as gui_fixture
import test_quality_gold_sets as source_fixture
import test_trusted_samples as sample_fixture
from template_ai.training_quality_dialog import TrainingQualityDialog
APP=QApplication.instance() or QApplication([])

class QualifiedCoverageGuiTests(unittest.TestCase):
    setUp=source_fixture.QualityGoldSetTests.setUp
    window=gui_fixture.QualityPanelTests.window
    wait=gui_fixture.QualityPanelTests.wait
    def panel(self,admit=True):
        sample=sample_fixture.admitted(self.store,self.work) if admit else None;window=self.window();dialog=TrainingQualityDialog(window);self.addCleanup(dialog.deleteLater);dialog.show();self.assertEqual(self.store.count('COVERAGE_SNAPSHOT'),0);panel=dialog.coverage_panel;dialog.tabs.setCurrentWidget(panel);self.wait(dialog.quality_panel);self.assertIsNotNone(panel.report,panel.status.text());return dialog,panel,sample
    def select_work(self,panel):
        axis=panel.tree.topLevelItem(0);group=axis.child(0);axis.setExpanded(True);group.setExpanded(True);panel.tree.setCurrentItem(group.child(0));APP.processEvents()
    def test_lazy_primary_defaults_to_trainable_and_candidate_view_is_separate(self):
        dialog,panel,sample=self.panel(False);self.assertEqual(panel.collection.currentData(),'APPROVED_TRAINABLE');self.assertEqual(panel.report['counts']['currently_verified_occurrences'],0);self.assertFalse(panel.report['quality_pass_claim']);self.assertEqual(self.store.count('AUTO_JOB'),0)
        panel.collection.setCurrentIndex(panel.collection.findData('CANDIDATE_PENDING'));self.wait(dialog.quality_panel);self.assertEqual(panel.report['counts']['matching_record_occurrences'],1);self.assertEqual(panel.report['counts']['currently_verified_occurrences'],0);self.assertIsNot(panel,dialog.inventory_panel)
    def test_exact_dataset_requires_explicit_selection_and_real_validation_role_is_not_training(self):
        dialog,panel,sample=self.panel();dataset=self.store.create_dataset(self.store.dataset_plan('Actual validation scope',[dict(sample_id=sample['id'],role='VALIDATION')]),'Reviewer',True)
        panel.collection.setCurrentIndex(panel.collection.findData('EXACT_DATASET'));self.wait(dialog.quality_panel);self.assertIsNone(panel.dataset.currentData());self.assertIsNone(panel.report);panel.dataset.setCurrentIndex(panel.dataset.findData(dataset['id']));self.wait(dialog.quality_panel);self.assertEqual(panel.report['roles'],{'VALIDATION':1})
        panel.collection.setCurrentIndex(panel.collection.findData('APPROVED_TRAINABLE'));self.wait(dialog.quality_panel);self.assertEqual(panel.report['counts']['currently_verified_occurrences'],0)
    def test_saved_history_is_not_current_and_revoke_updates_new_counts(self):
        dialog,panel,sample=self.panel();old=panel.report['snapshot_id'];self.store.transition_sample(self.store.sample_transition_plan(sample['id'],'REVOKE'),'Reviewer','Synthetic purpose withdrawn',True);panel.reload();self.wait(dialog.quality_panel);self.assertEqual(panel.report['counts']['currently_verified_occurrences'],0)
        panel.histories();self.wait(dialog.quality_panel);panel.history.setCurrentIndex(panel.history.findData(old));panel.load_history();self.wait(dialog.quality_panel);self.assertTrue(panel.historical);self.assertEqual(panel.report['counts']['currently_verified_occurrences'],1);self.assertIn('當時核實',panel.count.text());self.assertNotIn('當前核實',panel.count.text());self.assertFalse(panel.locate_button.isEnabled());panel.guard(panel.locate);self.assertIn('歷史快照',panel.status.text())
    def test_source_return_preserves_pending_editor_then_returns_exact_work_after_explicit_discard(self):
        dialog,panel,sample=self.panel();self.select_work(panel);dialog.facts_panel.focus(self.work['id'],[]);original=dialog.facts_panel.observed_text.text();dialog.facts_panel.observed_text.setText('Pending exact human editor');panel.guard(panel.locate);self.assertIn('未套用',panel.status.text());self.assertEqual(dialog.facts_panel.observed_text.text(),'Pending exact human editor')
        dialog.facts_panel.observed_text.setText(original);panel.locate();APP.processEvents();self.assertEqual(dialog.tabs.currentWidget(),dialog.facts_panel);self.assertEqual(dialog.facts_panel.loaded['id'],self.work['id']);self.assertEqual(panel.window.work['id'],self.work['id'])

    def test_busy_foreground_rejection_does_not_leave_false_loading_or_save_a_snapshot(self):
        dialog,panel,sample=self.panel();before=self.store.count('COVERAGE_SNAPSHOT');panel.window.busy=True;panel.guard(lambda:panel.reload(0));self.assertFalse(panel.loading);self.assertEqual(self.store.count('COVERAGE_SNAPSHOT'),before);self.assertIn('背景操作',panel.status.text());panel.window.busy=False;panel.reload(0);self.wait(dialog.quality_panel);self.assertIsNotNone(panel.report)

    def test_changed_collection_during_owned_count_does_not_apply_old_scope_result(self):
        dialog,panel,sample=self.panel();panel.reload(0);panel.collection.setCurrentIndex(panel.collection.findData('CANDIDATE_PENDING'));self.wait(dialog.quality_panel);self.assertIsNone(panel.report);self.assertIn('選擇已變更',panel.status.text());self.assertFalse(panel.loading);panel.reload(0);self.wait(dialog.quality_panel);self.assertEqual(panel.report['collection'],'CANDIDATE_PENDING')

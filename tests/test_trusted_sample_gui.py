"""Actual trusted-pool Qt events through the existing owned command worker."""
import sys,unittest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import test_quality_panel as fixture
import test_quality_gold_sets as source_fixture
from template_ai.training_quality_dialog import TrainingQualityDialog
from template_ai.trusted_sample_dialog import TrustedSampleReviewDialog,FILTERS
APP=QApplication.instance() or QApplication([])

class TrustedSampleGuiTests(unittest.TestCase):
    setUp=source_fixture.QualityGoldSetTests.setUp
    window=fixture.QualityPanelTests.window
    wait=fixture.QualityPanelTests.wait
    def dialog(self):
        window=self.window();center=TrainingQualityDialog(window);self.addCleanup(center.deleteLater);center.show();dialog=TrustedSampleReviewDialog(center.quality_panel);self.addCleanup(dialog.deleteLater);dialog.show();self.wait(center.quality_panel);return center,dialog
    def test_real_owned_directory_and_six_filters_default_to_no_actions_or_privacy_consent(self):
        center,dialog=self.dialog();self.assertEqual(dialog.collection.count(),6);self.assertEqual(dialog.table.rowCount(),1);self.assertIsNone(dialog.table.cellWidget(0,3).currentData());self.assertFalse(dialog.consent.isChecked());self.assertTrue(all(not check.isChecked() for _,check in dialog.purpose_checks));self.assertEqual(dialog.privacy_records.count(),0)
        for index in range(6):dialog.collection.setCurrentIndex(index);self.wait(center.quality_panel)
        self.assertEqual(self.store.count('SAMPLE'),0);self.assertEqual(self.store.count('AUTO_JOB'),0)
    def test_actual_preview_confirm_admission_and_changed_input_clears_old_authorization(self):
        center,dialog=self.dialog();dialog.actor.setText('Synthetic reviewer');dialog.basis.setCurrentIndex(dialog.basis.findData('OWNED'));dialog.reference.setText('Authored local synthetic source');dialog.table.selectRow(0);dialog.table.cellWidget(0,3).setCurrentIndex(1);dialog.preview_batch();self.wait(center.quality_panel);self.assertIsNotNone(dialog.pending)
        dialog.consent.setChecked(True);dialog.reference.setText('Updated explicit authority');self.assertIsNone(dialog.pending);self.assertFalse(dialog.consent.isChecked());dialog.guard(dialog.confirm);self.assertEqual(self.store.count('SAMPLE'),0)
        dialog.preview_batch();self.wait(center.quality_panel);dialog.consent.setChecked(True);dialog.confirm();self.wait(center.quality_panel);self.assertEqual(self.store.count('SAMPLE'),1);self.assertEqual(self.store.count('SEMANTIC_MODEL'),0);self.assertIsNone(dialog.pending);self.assertFalse(dialog.consent.isChecked())
    def test_fact_row_selection_and_return_preserve_pending_human_edit_and_have_no_qt_errors(self):
        center,dialog=self.dialog();dialog.table.selectRow(0);dialog.detail();self.wait(center.quality_panel);self.assertIn('Synthetic Example',dialog.details.toPlainText());errors=[];previous=sys.excepthook;sys.excepthook=lambda *args:errors.append(args);self.addCleanup(setattr,sys,'excepthook',previous)
        center.facts_panel.focus(self.work['id'],[]);baseline_text=center.facts_panel.observed_text.text();center.facts_panel.observed_text.setText('Pending human source edit');dialog.guard(dialog.source_facts);self.assertIn('未套用',dialog.status.text());self.assertEqual(center.facts_panel.observed_text.text(),'Pending human source edit');self.assertTrue(dialog.isVisible());self.assertEqual(errors,[])
        center.facts_panel.observed_text.setText(baseline_text);self.assertFalse(center.facts_panel.has_pending_observation());dialog.source_facts();APP.processEvents();self.assertFalse(dialog.isVisible());self.assertEqual(center.tabs.currentWidget(),center.facts_panel);self.assertEqual(center.facts_panel.loaded['id'],self.work['id']);self.assertEqual(errors,[])
    def test_actual_source_purpose_stop_and_selected_training_copy_redaction_through_worker(self):
        center,dialog=self.dialog();dialog.actor.setText('Synthetic reviewer');dialog.basis.setCurrentIndex(1);dialog.reference.setText('Synthetic owned source');dialog.table.selectRow(0);dialog.table.cellWidget(0,3).setCurrentIndex(1);dialog.preview_batch();self.wait(center.quality_panel);dialog.consent.setChecked(True);dialog.confirm();self.wait(center.quality_panel)
        sample=self.store.records('SAMPLE')[0];subject=sample['positive_labels'][0]['text'];dialog.purpose_checks[0][1].setChecked(True);dialog.preview_restriction();self.wait(center.quality_panel);dialog.consent.setChecked(True);dialog.confirm();self.wait(center.quality_panel);self.assertEqual(self.store.sample_state(sample['id']),'RESTRICTED_USE')
        dialog.load_privacy_records();self.wait(center.quality_panel);self.assertEqual(dialog.privacy_records.count(),1);self.assertEqual(dialog.privacy_records.item(0).checkState(),Qt.Unchecked);dialog.privacy_records.item(0).setCheckState(Qt.Checked);dialog.preview_redaction();self.wait(center.quality_panel);dialog.consent.setChecked(True);dialog.confirm();self.wait(center.quality_panel)
        self.assertTrue(self.store.get('SAMPLE',sample['id'])['local_training_text_redacted']);self.assertNotIn(subject,str(self.store.history('SAMPLE',sample['id'])));self.assertEqual(self.store.count('TRAINING_PRIVACY_REDACTION'),1);self.assertTrue(self.store.facts(self.work['id'])['observations'])

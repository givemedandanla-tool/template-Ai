"""Actual original delivery row entry, same proof/detail engines and worker review."""
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QTimer,Qt
from PySide6.QtWidgets import QApplication,QMessageBox
import test_multi_size as fixture
import test_output_batch_gui as gui_fixture
from template_ai.batch_format_review_dialog import BatchFormatReviewDialog
from gui_wait import wait_for_gui
APP=fixture.APP


class BatchFormatReviewGuiTests(unittest.TestCase):
    setUp=fixture.MultiSizeTests.setUp
    requests=fixture.MultiSizeTests.requests
    dialog=gui_fixture.OutputBatchGuiTests.dialog
    def tearDown(self):
        if self.workflow._format_proofs:self.workflow._format_proofs.cleanup()
        fixture.MultiSizeTests.tearDown(self)
    def make(self):
        self.d,self.parent=self.dialog();self.d.dpi.setValue(96);self.r=BatchFormatReviewDialog(self.d,self.d.engine.items[0]);self.addCleanup(self.r.deleteLater);self.r.show();return self.r
    def wait(self):self.assertTrue(wait_for_gui(lambda:not self.r.running and not self.r.host_window.busy,15),self.r.status.text())
    def inspect(self):self.r.inspect();self.wait();self.assertIsNotNone(self.r.proof,self.r.status.text())
    def test_actual_original_row_entry_uses_unchecked_current_target_and_no_auto_review(self):
        self.d,self.parent=self.dialog();self.d.table.selectRow(0);errors=[]
        def close():
            r=QApplication.activeModalWidget()
            try:self.assertIsInstance(r,BatchFormatReviewDialog);self.assertEqual(r.row['id'],'0');self.assertFalse(r.consent.isChecked());self.assertIsNone(r.proof)
            except BaseException as error:errors.append(str(error))
            r.reject()
        QTimer.singleShot(0,close);self.d.review_selected();self.assertFalse(errors);self.assertFalse(self.workflow.format_reviews)
    def test_actual_proof_detail_and_literal_named_confirmation_register_only_this_row(self):
        self.make();self.inspect();self.r.open_detail();self.wait();self.assertIsNotNone(self.r.detail);self.assertIs(self.r.detail.parentWidget(),self.r);self.r.confirm();self.assertFalse(self.workflow.format_reviews);self.r.actor.setText('SYNTHETIC_SOURCE_AUTHOR');self.r.evidence.setText('Actual selected PDF source and full original-size object/Logo snapshot checked');self.r.consent.setChecked(True);self.r.confirm();self.wait();self.assertEqual(len(self.workflow.format_reviews),1);self.assertTrue(self.workflow.get_format_review(self.r.row['key'],'PDF',96));self.assertFalse(self.workflow.get_format_review(self.r.row['key'],'JPG',96));self.assertIn('尚未輸出',self.d.status.text())
    def test_parent_dpi_change_invalidates_open_target_without_registering_receipt(self):
        self.make();self.inspect();self.d.dpi.setValue(150);self.r.actor.setText('Synthetic source author');self.r.evidence.setText('Old DPI not accepted');self.r.consent.setChecked(True);self.r.confirm();self.assertFalse(self.workflow.format_reviews);self.assertIn('具名證據',self.r.status.text())
    def test_actual_worker_delivery_copies_review_registry_and_selected_dpi(self):
        self.make();self.inspect();self.r.actor.setText('SYNTHETIC_SOURCE_AUTHOR');self.r.evidence.setText('Authored selected PDF and96DPI actual source reviewed');self.r.consent.setChecked(True);self.r.confirm();self.wait()
        for name,action in self.d.controls[1:]:action.setCurrentIndex(action.findData('SKIP'))
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):self.d.run(False)
        self.assertTrue(wait_for_gui(lambda:not self.d.running and not self.d.host_window.busy,15),self.d.status.text());self.assertEqual(self.d.engine.items[0]['status'],'SUCCESS',self.d.engine.items[0]);self.assertTrue(Path(self.d.engine.items[0]['path']).is_file());self.assertEqual([r['status'] for r in self.d.engine.items[1:]],['SKIPPED']*5)
    def test_sorted_table_review_identity_uses_userrole_not_visible_row_number(self):
        self.d,self.parent=self.dialog();self.d.table.setSortingEnabled(True);self.d.table.sortItems(0,Qt.DescendingOrder);self.d.table.selectRow(0);identity=self.d.table.item(0,0).data(Qt.UserRole);self.assertEqual(self.d.ids(),[identity])

if __name__=='__main__':unittest.main()

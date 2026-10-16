"""Actual current format consent and original MainWindow output publication."""
import threading,unittest
from pathlib import Path
from unittest.mock import patch
import test_digital_preflight_gui as fixture
from gui_wait import wait_for_gui


class DigitalReviewGuiTests(unittest.TestCase):
    setUp=fixture.DigitalPreflightGuiTests.setUp
    cleanup=fixture.DigitalPreflightGuiTests.cleanup
    wait=fixture.DigitalPreflightGuiTests.wait
    inspect=fixture.DigitalPreflightGuiTests.inspect
    def prepare(self):
        self.p.format.setCurrentText('PDF');self.inspect();self.p.review_actor.setText('SYNTHETIC_SOURCE_AUTHOR');self.p.review_evidence.setText('All current people/companies, whole Logo, physical size and actual PDF snapshot checked')
    def accept(self):self.p.review_consent.setChecked(True);self.p.confirm_review();self.wait();self.assertIsNotNone(self.p.review_receipt,self.p.status.text())
    def test_actual_default_no_requires_explicit_named_scope_before_enabling_formal_output(self):
        self.prepare();self.assertFalse(self.p.review_consent.isChecked());self.assertFalse(self.w.export_button.isEnabled());self.p.confirm_review();self.assertIsNone(self.p.review_receipt);self.accept();self.assertTrue(self.w.export_button.isEnabled());self.assertEqual(self.p.review_receipt['scope']['format'],'PDF')
    def test_actor_change_clears_consent_and_receipt_but_preserves_actual_proof(self):
        self.prepare();self.accept();proof=self.p.proof;self.p.review_actor.setText('Another current reviewer');self.assertIs(self.p.proof,proof);self.assertIsNone(self.p.review_receipt);self.assertFalse(self.p.review_consent.isChecked());self.assertFalse(self.w.export_button.isEnabled())
    def test_real_original_main_export_uses_reviewed_exact_pdf_without_replacing_published_template(self):
        self.prepare();self.accept();c=self.w.candidates[0];before=self.w.library.object_snapshot('TEMPLATE',c.template.id);path=self.f.root/'authored-reviewed-FINAL.pdf';errors=[]
        with patch('template_ai.gui.QFileDialog.getSaveFileName',return_value=(str(path),'PDF (*.pdf)')),patch.object(self.w,'error',side_effect=errors.append):self.w.export_current(False)
        self.assertFalse(errors,errors);self.assertTrue(path.is_file());self.assertEqual(self.w.library.object_snapshot('TEMPLATE',c.template.id),before)
    def test_current_format_change_cannot_reuse_old_receipt_even_if_export_called_directly(self):
        self.prepare();self.accept();self.w.dpi.setValue(150);path=self.f.root/'stale-reviewed-FINAL.pdf';errors=[]
        with patch('template_ai.gui.QFileDialog.getSaveFileName',return_value=(str(path),'PDF (*.pdf)')),patch.object(self.w,'error',side_effect=errors.append):self.w.export_current(False)
        self.assertFalse(path.exists());self.assertTrue(errors);self.assertIsNone(self.p.review_receipt)
    def test_late_reviewer_change_does_not_install_old_actor_receipt(self):
        from template_ai.digital_review import confirm
        self.prepare();self.p.review_consent.setChecked(True);started=threading.Event();release=threading.Event()
        def slow(*args):started.set();release.wait(8);return confirm(*args)
        with patch('template_ai.digital_review.confirm',side_effect=slow):
            self.p.confirm_review();self.assertTrue(wait_for_gui(started.is_set,3));self.p.review_actor.setText('Later actual reviewer');release.set();self.wait()
        self.assertIsNone(self.p.review_receipt);self.assertIn('舊憑證未採用',self.p.status.text())

if __name__=='__main__':unittest.main()

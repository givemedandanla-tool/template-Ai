"""Actual original workbench current human conclusions and scoped reopening."""
import unittest
import test_major_review_gui as fixture
from training_fixture import observations
from template_ai.quality_rechecks import blocked
APP=fixture.APP


class MajorFindingGuiTests(unittest.TestCase):
    setUp=fixture.MajorReviewGuiTests.setUp
    dispose=fixture.MajorReviewGuiTests.dispose
    wait=fixture.MajorReviewGuiTests.wait
    def case(self):
        self.page.preview();self.wait();self.d.consent.setChecked(True);self.d.confirm();self.wait();self.page.table.selectRow(0);self.page.finding_evidence.setPlainText('Original source, all text objects and current human facts explicitly checked')
    def facts(self):
        facts=self.store.facts(self.work['id']);work=self.library.artwork(self.work['id']);saved=self.store.save_facts(work['id'],observations(work),facts['revision'],work['revision']);return self.store.confirm_facts(work['id'],[o['id'] for o in saved['observations']],saved['revision'],saved['pins'],self.store.source_proof(work['id']),'Synthetic reviewer',True)
    def preview(self,value='CHECKED_OK'):
        self.page.finding.setCurrentIndex(self.page.finding.findData(value));self.page.preview_finding();self.wait();self.assertIsNotNone(self.page.finding_plan,self.d.status.text())
    def save(self):self.d.consent.setChecked(True);self.d.confirm();self.wait()
    def test_actual_gui_new_confirmed_facts_release_only_this_work_not_case_or_model(self):
        self.case();self.facts();self.preview();self.save();self.assertFalse(blocked(self.store,self.work['id']));self.assertIn('確認無誤 1',self.page.counts.text());self.assertFalse(self.page.case['completed']);self.assertEqual(self.store.count('SEMANTIC_MODEL'),0)
    def test_old_or_unconfirmed_facts_cannot_preview_safe_conclusion(self):
        self.case();self.page.preview_finding();self.wait();self.assertIsNone(self.page.finding_plan);self.assertTrue(blocked(self.store,self.work['id']));self.assertIn('更新',self.d.status.text())
    def test_explicit_error_finding_retains_actual_quarantine_and_counts(self):
        self.case();self.preview('ERROR_NEEDS_FIX');self.save();self.assertTrue(blocked(self.store,self.work['id']));self.assertIn('確認錯誤待修 1',self.page.counts.text());self.assertFalse(self.page.case['completed'])
    def test_selection_or_evidence_change_prevents_manual_release(self):
        self.case();self.facts();self.preview();self.page.finding_evidence.setPlainText('Different evidence entered after preview');self.d.consent.setChecked(True)
        with self.assertRaises(ValueError):self.d.confirm()
        self.assertTrue(blocked(self.store,self.work['id']))
    def test_actual_gui_reopen_requires_another_new_fact_review_and_preserves_old_receipt(self):
        self.case();self.facts();self.preview();self.save();first=self.page.rows[0]['revision'];self.page.table.selectRow(0);self.page.preview_reopen();self.wait();self.assertIsNotNone(self.page.finding_plan);self.save();self.assertTrue(blocked(self.store,self.work['id']));self.assertGreater(self.page.rows[0]['revision'],first);self.page.table.selectRow(0);self.page.preview_finding();self.wait();self.assertIsNone(self.page.finding_plan);self.facts();self.preview('REAPPROVED');self.save();self.assertFalse(blocked(self.store,self.work['id']));self.assertIn('修正後重新核准 1',self.page.counts.text())

if __name__=='__main__':unittest.main()

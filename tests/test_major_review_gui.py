"""Actual Qt source-major page over the original owned quality subprocess worker."""
import threading,unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
import test_quality_source_review as source_fixture
import test_quality_dispatch as dispatch_fixture
from gui_wait import wait_for_gui
from template_ai.quality_panel import QualityPanel
from template_ai.quality_repair_dialog import QualityRepairDialog
from template_ai.quality_rechecks import blocked
from template_ai.quality_command import run_command
APP=source_fixture.APP


class MajorReviewGuiTests(unittest.TestCase):
    def setUp(self):
        source_fixture.QualitySourceReviewTests.setUp(self);self.w=dispatch_fixture.QualityDispatchTests.window(self);self.panel=QualityPanel(self.w);self.addCleanup(self.panel.deleteLater);self.d=QualityRepairDialog(self.panel);self.addCleanup(self.dispose);self.d.issue=self.issue;self.d.actor.setText('Synthetic GUI reviewer');self.d.reason.setText('Source evidence and exact dependency snapshot reviewed');self.page=self.d.major_review;self.page.correct.setPlainText('Phone belongs to p1 in authored source');self.page.wrong.setPlainText('Observed phone assigned to p2');self.d.tabs.setCurrentWidget(self.d.major_scroll)
    def dispose(self):
        if self.panel.loading:self.panel.cancel_event.set();wait_for_gui(lambda:not self.panel.loading and not self.w.busy,12)
        self.d.deleteLater();APP.processEvents()
    def wait(self):self.assertTrue(wait_for_gui(lambda:not self.panel.loading and not self.w.busy,15),self.d.status.text()+' / '+self.panel.status.text())
    def preview(self):self.page.preview();self.wait();self.assertIsNotNone(self.page.plan,self.d.status.text())
    def confirm(self):self.d.consent.setChecked(True);self.d.confirm();self.wait()
    def test_actual_shared_worker_preview_requires_explicit_consent_and_reads_atomic_case(self):
        self.preview();self.assertFalse(blocked(self.store,self.work['id']));self.assertIn(self.work['id'],self.d.details.toPlainText());self.assertIn('未記錄',self.page.coverage.text())
        with self.assertRaises(ValueError):self.d.confirm()
        self.assertEqual(self.store.count('QUALITY_MAJOR_RECHECK'),0);self.confirm();self.assertTrue(blocked(self.store,self.work['id']));self.assertIsNotNone(self.page.case);self.assertEqual(self.page.table.rowCount(),1);self.assertIn('未掃描 1',self.page.counts.text());self.assertFalse(self.page.case['completed'])
    def test_changed_evidence_after_preview_invalidates_consent_and_never_starts_case(self):
        self.preview();self.d.consent.setChecked(True);self.page.wrong.setPlainText('New different observed mistake');self.assertIsNone(self.page.plan);self.assertFalse(self.d.consent.isChecked())
        with self.assertRaises(ValueError):self.d.confirm()
        self.assertEqual(self.store.count('QUALITY_MAJOR_RECHECK'),0)
    def test_real_owned_worker_late_preview_does_not_overwrite_new_form(self):
        started=threading.Event();release=threading.Event();original=run_command
        def hold(root,command,payload,**kwargs):
            if command=='MAJOR_PLAN':started.set();release.wait(5)
            return original(root,command,payload,**kwargs)
        try:
            with patch('template_ai.quality_panel.run_command',side_effect=hold):
                self.page.preview();self.assertTrue(wait_for_gui(started.is_set,5));self.page.correct.setPlainText('Newer human evidence kept');release.set();self.wait()
            self.assertIsNone(self.page.plan);self.assertEqual(self.page.correct.toPlainText(),'Newer human evidence kept');self.assertEqual(self.store.count('QUALITY_MAJOR_RECHECK'),0)
        finally:release.set()
    def test_new_workbench_reads_persistent_case_without_restarting_review(self):
        self.preview();self.confirm();identity=self.page.case['id'];other=QualityRepairDialog(self.panel);self.addCleanup(other.deleteLater);page=other.major_review;page.list_cases(0);self.wait();self.assertEqual(page.cases.currentData(),identity);page.load_case(0);self.wait();self.assertEqual(page.case['id'],identity);self.assertEqual(page.table.rowCount(),1);self.assertFalse(page.case['completed']);self.assertEqual(self.store.count('QUALITY_MAJOR_RECHECK'),1)
    def test_actual_case_filter_reports_loaded_scope_and_unscanned_state(self):
        self.preview();self.confirm();self.page.unit_query.setText(self.work['id']);self.page.load_case(0);self.wait();self.assertEqual(len(self.page.rows),1);self.assertIn('符合搜尋 1／本頁 1',self.page.counts.text());self.page.unit_query.setText(self.other_work['id']);self.page.load_case(0);self.wait();self.assertEqual(len(self.page.rows),0);self.assertIn('本案工作／模板任務 1',self.page.counts.text());self.assertFalse(blocked(self.store,self.other_work['id']))
    def test_locate_reads_userrole_identity_and_keeps_existing_navigation(self):
        self.preview();self.confirm();self.page.table.setSortingEnabled(True);self.page.table.sortItems(0,Qt.DescendingOrder);self.page.table.setCurrentCell(0,0);self.page.locate();self.assertEqual(self.w.work['id'],self.work['id']);self.assertEqual(self.panel.recheck_item['work_id'],self.work['id']);self.assertTrue(blocked(self.store,self.work['id']))
    def test_actor_or_reason_change_requires_fresh_preview(self):
        self.preview();self.d.actor.setText('Another human reviewer');self.d.consent.setChecked(True)
        with self.assertRaises(ValueError):self.d.confirm()
        self.assertEqual(self.store.count('QUALITY_MAJOR_RECHECK'),0)

if __name__=='__main__':unittest.main()

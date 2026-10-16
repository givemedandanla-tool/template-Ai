"""Native entry routing retains exact persisted source/trace IDs and dirty editors."""
import unittest
from unittest.mock import patch
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QPushButton
import test_major_review_gui as fixture
from template_ai.training_quality_dialog import TrainingQualityDialog
from template_ai.quality_repair_dialog import QualityRepairDialog
from gui_wait import wait_for_gui
APP=fixture.APP


class MajorReviewEntryTests(unittest.TestCase):
    setUp=fixture.MajorReviewGuiTests.setUp
    dispose=fixture.MajorReviewGuiTests.dispose
    wait=fixture.MajorReviewGuiTests.wait
    def center(self):
        center=TrainingQualityDialog(self.w);self.addCleanup(center.deleteLater);return center
    def test_actual_source_entry_pins_work_and_dirty_editor_blocks_it(self):
        center=self.center();facts=center.facts_panel;facts.focus(self.work['id'],[])
        with patch.object(center.quality_panel,'open_major_review') as opened:
            facts.major_button.click();self.assertEqual(opened.call_args.args[0]['work_id'],self.work['id']);self.assertEqual(opened.call_args.args[0]['origin'],'SOURCE_FACTS');opened.reset_mock()
            facts.observed_text.setText('Unsaved exact human observation');facts.major_button.click();opened.assert_not_called();self.assertEqual(facts.observed_text.text(),'Unsaved exact human observation')
    def test_actual_exception_entry_keeps_original_receipt_and_work_ids(self):
        center=self.center();row=dict(unit_id='persisted-unit',work_id=self.work['id'],reason='Observed exception')
        with patch.object(center.automatic_exceptions,'current',return_value=row),patch.object(center.quality_panel,'open_major_review') as opened:
            center.automatic_exceptions.open_repair(True);self.assertEqual(opened.call_args.args[0],dict(origin='EXCEPTION',origin_id='persisted-unit',work_id=self.work['id'],description='Observed exception'))
    def test_actual_rule_trace_entry_does_not_claim_proven_global_cause(self):
        center=self.center();hits=center.hits_panel;row=dict(id='actual-hit',stored=dict(work_id=self.work['id']))
        with patch.object(hits,'selected_row',return_value=row),patch.object(center.quality_panel,'open_major_review') as opened:
            hits.major_recheck();entry=opened.call_args.args[0];self.assertEqual(entry['work_id'],self.work['id']);self.assertIn('actual-hit',entry['description']);self.assertIn('尚未證實',entry['description'])
    def test_overview_opens_actual_major_page_without_creating_any_record(self):
        failures=[]
        def inspect():
            dialog=self.panel._repair_dialog
            try:self.assertIs(dialog.tabs.currentWidget(),dialog.major_scroll);self.assertFalse(dialog.consent.isChecked())
            except BaseException as error:failures.append(str(error))
            dialog.reject()
        QTimer.singleShot(0,inspect);self.panel.open_major_review();self.assertFalse(failures);self.assertEqual(self.store.count('QUALITY_MAJOR_RECHECK'),0)
    def test_source_evidence_save_routes_same_dialog_to_major_page_without_auto_start(self):
        self.d.major_entrypoint=True;self.d.tabs.setCurrentIndex(0);self.d.source_work.setText(self.work['id']);self.d.description.setText('Actual source evidence before possible broad review');self.d.source_issue('SOURCE_FACTS',self.work['id']);self.wait();self.d.consent.setChecked(True);self.d.confirm();self.wait();self.assertIs(self.d.tabs.currentWidget(),self.d.major_scroll);self.assertFalse(self.d.consent.isChecked());self.assertEqual(self.store.count('QUALITY_MAJOR_RECHECK'),0);self.assertTrue(self.d.issue['id'])

    def test_actual_closed_batch_entry_pins_current_work_and_preserves_old_closure(self):
        from template_ai.coverage_batches import CoverageBatches
        from test_coverage_batches import CoverageBatchTests
        from types import SimpleNamespace
        from test_noise_authoring import confirmed
        confirmed(self.store,self.work)
        service=CoverageBatches(self.library);batch=service.create(service.plan_registered_sources([self.work['source_id']]),'Synthetic reviewer',True);member=service.members(batch['id'])['rows'][0]
        CoverageBatchTests.review_all(SimpleNamespace(service=service),member,self.work);receipt=service.close(service.closure_plan(batch['id']),'Synthetic reviewer',True)
        center=self.center();page=center.closure_panel;page.activate();self.assertTrue(wait_for_gui(lambda:not page.loading and not self.w.busy,15));page.batches.setCurrentIndex(page.batches.findData(batch['id']));page.load_batch();self.assertTrue(wait_for_gui(lambda:not page.loading and not self.w.busy,15));page.table.selectRow(0);page.inspect();self.assertTrue(wait_for_gui(lambda:not page.loading and not self.w.busy,15));page.work_combo.setCurrentIndex(page.work_combo.findData(self.work['id']))
        with patch.object(center.quality_panel,'open_major_review') as opened:
            page.open_major_review();self.assertEqual(opened.call_args.args[0]['work_id'],self.work['id'])
        from template_ai.quality_repairs import QualityRepairs
        repairs=QualityRepairs(self.library);issue=repairs.create_source_issue(repairs.plan_source_issue(self.work['id'],'SOURCE_FACTS',self.work['id'],'New doubt after an actual closed batch'),'Synthetic reviewer','Exact current source proof',True)
        plan=self.service.source_plan(issue_id=issue['id'],category='OWNER',correct_example='Exact Alex owner',wrong_example='Wrong Blair owner');row=next(r for r in plan['rows'] if r['work_id']==self.work['id']);self.assertIn(batch['id'],row['batch_ids']);self.service.confirm_source(plan,'Synthetic reviewer','New doubt after original closure',True)
        self.assertFalse(service.closure_status(batch['id'])['current_complete']);self.assertEqual(self.store.get('COVERAGE_CLOSURE',receipt['id']),receipt)

if __name__=='__main__':unittest.main()

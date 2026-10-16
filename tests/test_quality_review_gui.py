import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QMessageBox
import test_quality_panel as gui_fixture
import test_quality_gold_sets as fixtures
import test_quality_rechecks as recheck_fixture
import test_quality_jobs as jobs_fixture
from quality_acceptance_fixture import actual_positive_pair
from template_ai.quality_reports import QualityReports
from template_ai.quality_rechecks import blocked


class QualityReviewGuiTests(unittest.TestCase):
    setUp=fixtures.QualityGoldSetTests.setUp
    window=gui_fixture.QualityPanelTests.window
    panel=gui_fixture.QualityPanelTests.panel
    wait=gui_fixture.QualityPanelTests.wait
    build=jobs_fixture.QualityJobTests.build
    critical=recheck_fixture.QualityRecheckTests.critical

    def test_actual_native_compare_accept_and_withdraw_preserves_original_decision(self):
        fixture=actual_positive_pair(self);panel=self.panel();panel.activate();self.wait(panel);panel.compare();self.wait(panel)
        self.assertTrue(panel.pending[1]['candidate_decision_eligible'])
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):panel.confirm_preview()
        self.wait(panel);self.assertTrue(panel.report_id.text())
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):panel.decide()
        self.wait(panel);identity=panel.decision_id.text();self.assertTrue(identity)
        decision=self.store.get('QUALITY_VERSION_DECISION',identity);self.assertTrue(QualityReports(self.library).recommendation_status(identity)['quality_verified_recommendation_allowed'])
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):panel.withdraw()
        self.wait(panel);self.assertFalse(QualityReports(self.library).recommendation_status(identity)['quality_verified_recommendation_allowed']);self.assertEqual(self.store.get('QUALITY_VERSION_DECISION',identity),decision)

    def test_actual_native_single_work_resolution_requires_new_facts_and_keeps_model_quarantine(self):
        plan=self.critical(True);self.rechecks.confirm(plan,'Reviewer','Confirmed common failure',True)
        panel=self.panel();panel.list_quarantines();self.wait(panel);self.assertEqual(panel.quarantines.count(),1)
        panel.preview_resolution();self.wait(panel);panel.review_evidence.setText('Newly reviewed exact source and facts')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):panel.confirm_preview()
        self.wait(panel);self.assertTrue(blocked(self.store,self.work['id']))
        current=self.store.facts(self.work['id']);saved=self.store.save_facts(self.work['id'],current['observations'],current['revision'],self.work['revision'])
        self.store.confirm_facts(self.work['id'],[o['id'] for o in saved['observations']],saved['revision'],saved['pins'],self.store.source_proof(self.work['id']),'Reviewer',True)
        panel.preview_resolution();self.wait(panel)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):panel.confirm_preview()
        self.wait(panel);self.assertFalse(blocked(self.store,self.work['id']))
        self.assertIsNotNone(self.store.get('QUALITY_PIPELINE_QUARANTINE',plan['pipeline_id']))

    def test_impact_preview_is_paged_and_does_not_open_unrelated_case_rows(self):
        panel=self.panel();row=dict(legacy_dependency_versions_unknown=True,source_id=self.source['id'],work_id=self.work['id'],batch_ids=['synthetic-closed'],facts_revision=2,samples=[])
        panel.impact_rows=[dict(row,work_id='synthetic-'+str(i)) for i in range(123)];panel.show_impact()
        self.assertEqual(panel.table.rowCount(),50);panel.cases(50);self.assertEqual(panel.impact_offset,50);self.assertEqual(panel.table.rowCount(),50)
        panel.cases(50);self.assertEqual(panel.table.rowCount(),23);self.assertEqual(panel.rows,[])

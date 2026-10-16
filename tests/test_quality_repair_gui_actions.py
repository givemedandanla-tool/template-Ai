"""Actual repair GUI training/rule operations and canonical historical entry."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
import test_quality_repair_gui as gui_fixture
import test_semantic_learning as semantic_fixture
import test_quality_repair_rules as rule_fixture
import test_quality_rechecks as recheck_fixture
from template_ai.quality_repair_dialog import QualityRepairDialog
from template_ai.quality_repairs import QualityRepairs
from template_ai.semantic_learning import SemanticLearning
from template_ai.training_store import digest

APP=QApplication.instance() or QApplication([])


class QualityRepairGuiActionTests(unittest.TestCase):
    setUp=gui_fixture.QualityRepairGuiTests.setUp
    window=gui_fixture.QualityRepairGuiTests.window
    panel=gui_fixture.QualityRepairGuiTests.panel
    wait=gui_fixture.QualityRepairGuiTests.wait
    dialog=gui_fixture.QualityRepairGuiTests.dialog
    build=recheck_fixture.QualityRecheckTests.build
    critical=recheck_fixture.QualityRecheckTests.critical

    def reviewed(self,layer):
        service=QualityRepairs(self.library)
        issue=service.create_source_issue(service.plan_source_issue(self.work['id'],'SOURCE_FACTS',self.work['id'],'Actual original source repair investigation'),'Reviewer','Explicit original context and root scope',True)
        root=service.root_plan(issue['id'],layer,'Narrow source-derived repair candidate','Original and human facts independently reviewed',True,True)
        return issue,service.confirm_root(root,'Reviewer',True)

    def test_actual_native_training_selection_owned_candidate_job_and_shared_fifo(self):
        context=SimpleNamespace(root=self.root,library=self.library,service=SemanticLearning(self.library))
        train=semantic_fixture.SemanticLearningTests.work(context,'gui-repair-train',[('title','資深雲端工程師'),('title','資深後端工程師'),('address','台中市西區公益路10號'),('address','台中市西區中正路20號')])
        validation=semantic_fixture.SemanticLearningTests.work(context,'gui-repair-validation',[('title','資深前端工程師'),('address','台中市西區民生路30號')])
        issue,review=self.reviewed('FIELD_OWNER_SEMANTICS');panel,dialog=self.dialog();dialog.issue=issue;dialog.actor.setText('Synthetic reviewer');dialog.reason.setText('Only selected actual training and unrelated validation sources')
        dialog.select_record(dialog.review,review['id'],'Actual reviewed semantic root');dialog.work_page(0);self.wait(panel)
        for index in range(dialog.work_table.rowCount()):
            label=dialog.work_table.item(index,0).text();combo=dialog.work_table.cellWidget(index,2)
            if label.startswith(train['name']+' · '):combo.setCurrentIndex(combo.findData('TRAIN'))
            if label.startswith(validation['name']+' · '):combo.setCurrentIndex(combo.findData('VALIDATION'))
        self.assertEqual(dialog.roles,{train['id']:'TRAIN',validation['id']:'VALIDATION'})
        dialog.preview('REPAIR_SEMANTIC_PLAN',dict(work_roles=dict(dialog.roles)),'TRAIN',dict(review_id=dialog.review_id()));self.wait(panel)
        self.assertIsNotNone(dialog.pending);dialog.consent.setChecked(True);dialog.confirm();self.wait(panel)
        identity=dialog.job.currentData();self.assertTrue(identity);dialog.consent.setChecked(True);dialog.enqueue_train()
        for _ in range(1500):
            APP.processEvents();job=self.store.get('AUTO_JOB',identity)
            if job.get('candidate_id'):break
            QTest.qWait(20)
        self.assertTrue(job.get('candidate_id'),job);self.assertEqual(job['phase'],'COMPLETED');self.assertIsNone(self.store.get('SEMANTIC_ACTIVE','local-text'))
        dialog.job_page(0);self.wait(panel);self.assertIn('COMPLETED',dialog.progress.toPlainText())
        self.assertFalse(self.store.get('QUALITY_REPAIR_CANDIDATE',job['candidate_id'])['can_activate'])

    def test_actual_high_risk_rule_failure_is_visible_and_detail_approval_remains_isolated(self):
        # Borrow only fixture operations, not another TestCase class/catalog.
        self.propose=rule_fixture.QualityRepairRuleTests.propose.__get__(self)
        pending,review,plan=rule_fixture.QualityRepairRuleTests.prepare(self)
        issue=self.store.get('QUALITY_REPAIR_ISSUE',review['plan']['issue_id']);panel,dialog=self.dialog();dialog.issue=issue
        dialog.actor.setText('Synthetic reviewer');dialog.reason.setText('Exact narrow annotation rule, original positives and counterexamples')
        dialog.select_record(dialog.review,review['id'],'Actual noise root');dialog.select_record(dialog.rule,pending['id'],pending['literal'])
        dialog.preview('REPAIR_RULE_PLAN',dict(rule_ids=[pending['id']]),'RULE',dict(review_id=dialog.review_id(),detail_reviewed=False));self.wait(panel)
        dialog.consent.setChecked(True);dialog.confirm();self.wait(panel);self.assertIn('HIGH',dialog.status.text());self.assertIsNone(dialog.pending);self.assertFalse(dialog.consent.isChecked())
        dialog.detail_rule.setChecked(True);dialog.preview('REPAIR_RULE_PLAN',dict(rule_ids=[pending['id']]),'RULE',dict(review_id=dialog.review_id(),detail_reviewed=True));self.wait(panel)
        dialog.consent.setChecked(True);dialog.confirm();self.wait(panel)
        self.assertEqual(self.store.get('RULE',pending['id'])['state'],'ISOLATED_IN_REPAIR');self.assertEqual(self.store.active_noise_rules()[0],[])
        self.assertEqual(self.store.count('QUALITY_PIPELINE_DEPLOYMENT'),0)

    def test_real_cross_recheck_entry_uses_persisted_work_quarantine_and_quality_side_data(self):
        plan=self.critical(True);case=self.rechecks.confirm(plan,'Reviewer','Actual critical source and historical closed work',True)
        quarantine=self.store.db.execute("SELECT id FROM training_records WHERE kind='QUALITY_WORK_QUARANTINE' AND json_extract(payload,'$.work_id')=?",(self.work['id'],)).fetchone()[0]
        record=self.store.get('QUALITY_WORK_QUARANTINE',quarantine);service=QualityRepairs(self.library)
        preview=service.plan_source_issue(self.work['id'],'CROSS_BATCH_RECHECK',case['id'],'Original historical affected work needs root investigation')
        self.assertEqual(preview['origin_reference']['quarantine']['id'],quarantine)
        issue=service.create_source_issue(preview,'Reviewer','Actual persisted cross-recheck scope',True);self.assertEqual(issue['evidence']['origin_reference']['id'],case['id'])
        panel=self.panel();panel.recheck_item=record
        with patch.object(panel,'open_repair') as opened:panel.repair_selected()
        self.assertEqual(opened.call_args.args[0]['origin'],'CROSS_BATCH_RECHECK')
        panel.recheck_item=record;panel.impact_mode=False;panel.rows=[dict(case=dict(work_id=self.work['id']))];panel.table.setRowCount(1);panel.table.selectRow(0);panel.protocols.addItem('Actual source protocol',self.protocol['id']);panel.protocols.setCurrentIndex(panel.protocols.count()-1);panel.side.setCurrentIndex(1)
        with patch.object(panel,'open_repair') as opened:panel.repair_selected()
        self.assertEqual(opened.call_args.args[0]['side'],'CANDIDATE')

    def test_actual_native_quality_acceptance_preserves_exact_report_and_does_not_activate(self):
        from quality_acceptance_fixture import actual_positive_pair
        from template_ai.quality_reports import QualityReports
        fixture=actual_positive_pair(self);reports=QualityReports(self.library);report=reports.save(reports.plan(fixture['protocol']['id']),'Reviewer',True)
        panel,dialog=self.dialog();dialog.actor.setText('Synthetic reviewer');dialog.reason.setText('Authored lenient safety fixture, not production accuracy')
        dialog.select_record(dialog.report,report['id'],'Actual saved comparison')
        dialog.preview('REPAIR_DECISION_PLAN',dict(report_id=report['id']),'DECISION');self.wait(panel)
        self.assertTrue(dialog.pending[1]['candidate_decision_eligible']);self.assertEqual(dialog.pending[1]['report_digest'],digest(report))
        with self.assertRaises(ValueError):reports.decide(report['id'],'Reviewer','Stale preview must fail',True,expected_report_digest='not-the-approved-report')
        dialog.consent.setChecked(True);dialog.confirm();self.wait(panel)
        decision=self.store.get('QUALITY_VERSION_DECISION',dialog.decision.currentData());self.assertEqual(decision['report_id'],report['id'])
        self.assertEqual(decision['state'],'ACCEPTED_QUALITY_ONLY');self.assertIsNone(self.store.get('QUALITY_PIPELINE_ACTIVE','automatic-source'))

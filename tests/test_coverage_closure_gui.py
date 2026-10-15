import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QTimer,Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from template_ai.gui import MainWindow
from template_ai.training_store import TrainingStore
from template_ai.coverage_batches import CoverageBatches
from template_ai.coverage_closure_panel import CoverageClosurePanel
from template_ai.coverage_command import run_command
from runtime_fixture import controlled_resources
import test_coverage_batches as fixtures

APP=QApplication.instance() or QApplication([])


class CoverageClosureGuiTests(unittest.TestCase):
    source=fixtures.CoverageBatchTests.source
    batch=fixtures.CoverageBatchTests.batch
    work_member=fixtures.CoverageBatchTests.work_member
    review_all=fixtures.CoverageBatchTests.review_all

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.window=MainWindow(self.root/'data');controlled_resources(self.window)
        self.library=self.window.library;self.store=TrainingStore(self.library);self.service=CoverageBatches(self.library)
        self.panel=CoverageClosurePanel(self.window);self.panel.resize(1200,900);self.panel.show()

    def tearDown(self):
        self.panel.cancel();self.window.pool.waitForDone(5000);APP.processEvents();self.panel.close();self.window.source=None;self.window.work=None;self.window.template=None;self.window.close();self.tmp.cleanup()

    def wait(self,predicate):
        for _ in range(1000):
            APP.processEvents()
            if predicate():return
            QTest.qWait(10)
        self.fail('coverage operation did not finish: '+self.panel.status.text())

    def load(self,batch):
        self.panel.activate();self.wait(lambda:not self.panel.loading)
        self.panel.batches.setCurrentIndex(self.panel.batches.findData(batch['id']));self.panel.load_batch();self.wait(lambda:not self.panel.loading)
        self.panel.table.selectRow(0);self.panel.inspect();self.wait(lambda:not self.panel.loading)
        self.assertIsNotNone(self.panel.detail)

    def test_panel_is_lazy_and_unreviewed_layers_block_close_without_freezing_gui(self):
        self.assertFalse(self.panel.started);self.assertFalse(self.panel.loading)
        source,work,batch,member=self.work_member();ticks=[];timer=QTimer();timer.setInterval(5);timer.timeout.connect(lambda:ticks.append(1));timer.start()
        try:
            self.load(batch);self.panel.plan_close();self.wait(lambda:not self.panel.loading)
        finally:timer.stop()
        self.assertGreater(len(ticks),3);self.assertFalse(self.panel.confirm_button.isEnabled());self.assertFalse(self.panel.pending[1]['closure_allowed'])
        self.assertIn('不能結案',self.panel.status.text());self.assertEqual(self.store.count('COVERAGE_CLOSURE'),0)

    def test_one_layer_explicit_preview_and_approval_never_approves_other_layers(self):
        source,work,batch,member=self.work_member();self.load(batch)
        self.panel.actor.setText('Synthetic Reviewer');self.panel.reason.setText('Individually checked source person boundary');self.panel.evidence.setText('Page1 whole source visual')
        self.panel.layer.setCurrentIndex(self.panel.layer.findData('people'));self.panel.plan_layer();self.wait(lambda:not self.panel.loading)
        self.assertIsNotNone(self.panel.pending);self.panel.confirm();self.assertEqual(self.store.count('COVERAGE_REVIEW'),0)
        self.panel.approved.setChecked(True);QTest.mouseClick(self.panel.confirm_button,Qt.LeftButton)
        self.wait(lambda:not self.panel.loading)
        self.assertEqual(self.store.count('COVERAGE_REVIEW'),1)
        evidence=self.service.member_evidence(member['id']);self.assertEqual(evidence['layer_counts']['people']['current_reviewed'],1)
        self.assertEqual(evidence['layer_counts']['customer']['current_reviewed'],0);self.assertFalse(evidence['closure_allowed'])

    def test_gui_closure_persists_actual_receipt_without_rules_styles_or_output(self):
        source,work,batch,member=self.work_member();self.review_all(member,work);self.load(batch)
        self.panel.actor.setText('Synthetic Reviewer');self.panel.plan_close();self.wait(lambda:not self.panel.loading)
        self.assertTrue(self.panel.confirm_button.isEnabled());self.panel.approved.setChecked(True);self.panel.confirm();self.wait(lambda:not self.panel.loading)
        self.assertEqual(self.store.count('COVERAGE_CLOSURE'),1);self.assertTrue(self.service.closure_status(batch['id'])['current_complete'])
        self.assertEqual(self.store.count('RULE'),0);self.assertEqual(self.library.db.execute('SELECT count(*) FROM templates').fetchone()[0],0)

    def test_subprocess_failure_and_unknown_command_do_not_create_success(self):
        with self.assertRaisesRegex(ValueError,'不支援'):run_command(self.library.root,'UNKNOWN',{})
        self.assertEqual(self.store.count('COVERAGE_CLOSURE'),0)

    def test_resource_wait_can_be_cancelled_without_launching_child_or_claiming_saved(self):
        import test_runtime_execution as resources
        with patch.object(self.window.runtime,'admit',return_value=resources.HOLD),patch('template_ai.coverage_closure_panel.run_command',side_effect=AssertionError('resource-blocked child started')):
            self.panel.activate();self.assertTrue(self.panel.loading);self.panel.cancel();self.wait(lambda:not self.panel.loading)
        self.assertEqual(self.store.count('COVERAGE_BATCH'),0);self.assertEqual(self.window._waiting_launches,{})
        self.assertIn('結果未確認',self.panel.status.text())

    def test_600_file_gui_pages_search_globally_without_opening_source_models(self):
        sources=[self.source(f'file-{i:04}.svg') for i in range(600)];batch=self.batch(sources)
        self.panel.activate();self.wait(lambda:not self.panel.loading);self.panel.load_batch();self.wait(lambda:not self.panel.loading)
        self.assertEqual(len(self.panel.rows),50);self.assertEqual(self.panel.batch['file_count'],600)
        self.panel.query.setText('FILE-0599');self.panel.search();self.wait(lambda:not self.panel.loading)
        self.assertEqual(len(self.panel.rows),1);self.assertTrue(self.panel.rows[0]['frozen']['original_path'].endswith('0599.svg'))
        self.assertEqual(self.store.count('AUTO_UNIT'),0);self.assertEqual(self.store.count('AUTO_JOB'),0)

    def test_subprocess_timeout_stops_owned_child_and_keeps_no_success_receipt(self):
        import psutil
        import template_ai.coverage_command as commands
        original=commands.subprocess.Popen;processes=[]
        def start(*args,**kwargs):
            process=original(*args,**kwargs);processes.append(process);return process
        with patch.object(commands.subprocess,'Popen',side_effect=start):
            with self.assertRaisesRegex(ValueError,'隔離停止'):run_command(self.library.root,'BATCHES',{},timeout=0)
        self.assertTrue(processes);self.assertFalse(psutil.pid_exists(processes[0].pid));self.assertEqual(self.store.count('COVERAGE_CLOSURE'),0)

    def test_actual_approved_rule_group_gui_labels_automatic_origin_without_human_layer_approval(self):
        import test_coverage_rules as rule_fixture
        source,work,rule,batch,member=rule_fixture.CoverageRuleTests.seed(self)
        self.load(batch);self.assertGreater(self.panel.rules.count(),0)
        self.panel.actor.setText('Synthetic batch operator');self.panel.plan_group_rule();self.wait(lambda:not self.panel.loading)
        self.assertEqual(self.panel.pending[0],'GROUP_RULE');self.assertEqual(self.panel.pending[1]['impact']['high_risk_items'],0)
        self.panel.approved.setChecked(True);self.panel.confirm();self.wait(lambda:not self.panel.loading)
        self.assertEqual(self.store.count('COVERAGE_RULE_CHECK'),1);self.assertEqual(self.store.count('COVERAGE_REVIEW'),0)
        self.assertIn('依正式核准規則自動驗證完成',self.panel.details.toPlainText());self.assertFalse(self.service.member_evidence(member['id'])['closure_allowed'])

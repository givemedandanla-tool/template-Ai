"""Actual approved isolated selection through existing Qt setup and source engine."""
import copy,unittest
import test_quality_repair_rules as rule_fixture
import test_quality_repair_gui as gui_fixture
from template_ai.quality_rule_selector import ExactRuleSelector
from template_ai.quality_setup import QualitySetupDialog
from template_ai.quality_repair_dialog import QualityRepairDialog
from template_ai.quality_pipeline import QualityPipelines
from template_ai.quality_rules import snapshots
from template_ai.model import new_id


class QualityRuleSelectorTests(unittest.TestCase):
    setUp=rule_fixture.QualityRepairRuleTests.setUp
    propose=rule_fixture.QualityRepairRuleTests.propose
    prepare=rule_fixture.QualityRepairRuleTests.prepare
    candidate=rule_fixture.QualityRepairRuleTests.candidate
    window=gui_fixture.QualityRepairGuiTests.window
    panel=gui_fixture.QualityRepairGuiTests.panel
    wait=gui_fixture.QualityRepairGuiTests.wait

    def test_actual_isolated_rule_selected_by_name_and_frozen_via_reused_native_setup(self):
        _,candidate=self.candidate();panel=self.panel();host=QualityRepairDialog(panel);self.addCleanup(host.deleteLater);host.actor.setText('Synthetic reviewer');host.reason.setText('Only explicit independently approved isolated rule, not deployment')
        dialog=QualitySetupDialog(host);self.addCleanup(dialog.deleteLater);dialog.show();dialog.tabs.setCurrentIndex(3)
        dialog.rules_mode.setCurrentIndex(dialog.rules_mode.findData('EXACT_APPROVED'))
        self.assertEqual(dialog.exact_rules.table.rowCount(),1);self.assertEqual(dialog.exact_rules.rows[0]['id'],candidate['id']);self.assertEqual(dialog.exact_rules.selected_versions,{})
        self.assertFalse(dialog.exact_rules.table.cellWidget(0,0).isChecked());dialog.exact_rules.table.cellWidget(0,0).setChecked(True)
        dialog.version_name.setText('Actual isolated rule selected through existing version GUI');dialog.freeze_version();self.wait(panel)
        identity=host.pipeline.currentData();self.assertTrue(identity,host.status.text());pipeline=self.store.get('QUALITY_PIPELINE',identity)
        self.assertEqual(pipeline['manifest']['rule_selection'],[dict(id=candidate['id'],revision=candidate['revision'])]);self.assertEqual(self.store.active_noise_rules()[0],[])
        self.assertTrue(QualityPipelines(self.library).predict_source(identity,self.source['id'])['predictions']);self.assertIsNone(self.store.get('QUALITY_PIPELINE_ACTIVE','automatic-source'))

    def test_empty_or_changed_current_rule_selection_cannot_silently_freeze_other_versions(self):
        _,candidate=self.candidate();selector=ExactRuleSelector(self.store);self.addCleanup(selector.deleteLater);selector.refresh()
        with self.assertRaises(ValueError):selector.selection()
        selector.table.cellWidget(0,0).setChecked(True)
        with self.store.transaction():self.store._write('RULE',candidate['id'],dict(candidate,state='REPAIR_WITHDRAWN'),candidate['revision'],'synthetic_explicit_withdrawal')
        with self.assertRaises(ValueError):selector.selection()

    def test_cloned_candidate_id_cannot_impersonate_origin_exact_approval_link(self):
        _,candidate=self.candidate();clone=copy.deepcopy(candidate);clone.pop('id');clone.pop('revision')
        with self.store.transaction():copied=self.store._write('RULE',new_id(),clone,0,'synthetic_corrupt_cloned_candidate_not_new_approval')
        with self.assertRaises(ValueError):snapshots(self.store,[dict(id=copied['id'],revision=copied['revision'])])
        self.assertEqual(snapshots(self.store,[dict(id=candidate['id'],revision=candidate['revision'])]),[candidate])

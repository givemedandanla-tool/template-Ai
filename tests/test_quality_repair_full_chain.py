"""Bounded own module: full actual repair adoption and stale prior-proof block."""
import unittest
import test_quality_repair_gates as fixtures
from template_ai.quality_repair_gates import STAGES
from template_ai.quality_reports import QualityReports


class QualityRepairFullChainTests(unittest.TestCase):
    setUp=fixtures.QualityRepairGateTests.setUp
    prepare=fixtures.QualityRepairGateTests.prepare
    run_stage=fixtures.QualityRepairGateTests.run_stage

    def test_full_actual_ordered_control_independent_chain_and_repair_deployment(self):
        from quality_repair_acceptance_fixture import actual_chain
        chain=actual_chain(self);final=chain['final'];release=chain['release'];installed=chain['installed']
        issue=self.store.get('QUALITY_REPAIR_ISSUE',self.candidate['plan']['issue_id'])
        old_gold=self.store.get('QUALITY_GOLD',issue['evidence']['gold_refs'][0]['id'])
        self.gold.withdraw(old_gold['id'],old_gold['revision'],'Reviewer','Actual prior root evidence withdrawn after deployment',True)
        with self.assertRaises(ValueError):self.gates.checked_gate(final['id'])
        with self.assertRaises(ValueError):release.pin()
        self.assertEqual(self.store.get('QUALITY_PIPELINE_ACTIVE','automatic-source')['event_id'],installed['event']['id'])

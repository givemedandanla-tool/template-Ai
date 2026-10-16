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
        from template_ai.quality_repair_releases import QualityRepairReleases
        self.prepare(full_chain=True)
        root=self.run_stage(self.gates.protocol_plan(self.candidate['id'],STAGES[0],self.dataset_id,self.policy_id,'Actual root correction first'))
        self.assertTrue(root['plan']['passed'],root['plan']['blockers'])
        controls=self.run_stage(self.gates.protocol_plan(self.candidate['id'],STAGES[1],self.controls['dataset']['id'],self.policy_id,'Unrelated two-column actual phone/person/logo/mm/customer and multi-panel controls',root['id']))
        self.assertTrue(controls['plan']['passed'],controls['plan']['blockers'])
        final=self.run_stage(self.gates.protocol_plan(self.candidate['id'],STAGES[2],self.independent['dataset']['id'],self.policy_id,'New authored portrait HOLDOUT, software state-machine safety only',controls['id']))
        self.assertTrue(final['plan']['passed'],final['plan']['blockers']);self.assertTrue(final['plan']['independence_claim'])
        decision=QualityReports(self.library).decide(final['plan']['report_id'],'Reviewer','Explicit intentionally lenient authored synthetic safety test; not production accuracy',True)
        release=QualityRepairReleases(self.library);impact=release.confirm_impact(release.impact_plan(self.candidate['id']),'Reviewer','Inspect known impact and explicitly retain unknown history; no pending confirmed highrisk',True)
        plan=release.plan(decision['id'],0,gate_id=final['id'],impact_review_id=impact['id'])
        installed=release.confirm(plan,'Reviewer','Exact candidate passed ordered actual safety checks, remains human-review source recommendation',True)
        self.assertEqual(release.pin()['event_id'],installed['event']['id']);self.assertEqual(release.pin()['pipeline_id'],self.candidate['plan']['pipeline_id'])
        issue=self.store.get('QUALITY_REPAIR_ISSUE',self.candidate['plan']['issue_id'])
        old_gold=self.store.get('QUALITY_GOLD',issue['evidence']['gold_refs'][0]['id'])
        self.gold.withdraw(old_gold['id'],old_gold['revision'],'Reviewer','Actual prior root evidence withdrawn after deployment',True)
        with self.assertRaises(ValueError):self.gates.checked_gate(final['id'])
        with self.assertRaises(ValueError):release.pin()
        self.assertEqual(self.store.get('QUALITY_PIPELINE_ACTIVE','automatic-source')['event_id'],installed['event']['id'])

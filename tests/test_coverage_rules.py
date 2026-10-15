import sqlite3
import unittest
from unittest.mock import patch
import test_coverage_batches as fixtures


class CoverageRuleTests(unittest.TestCase):
    setUp=fixtures.CoverageBatchTests.setUp
    source=fixtures.CoverageBatchTests.source
    batch=fixtures.CoverageBatchTests.batch
    work_member=fixtures.CoverageBatchTests.work_member

    def seed(self,activate=True):
        from test_rule_review import pending_rule
        from test_noise_hits import activate as approve
        source,work,rule=pending_rule(self.store,self.root)
        if activate:
            rule=approve(self.store,rule)
            # Rule authoring leaves a valid local exclusion on its original example.
            # Use a new independently confirmed work to exercise actual rule reuse.
            from training_fixture import source_work
            from test_noise_authoring import confirmed
            source,work=source_work(self.library,self.root,'future.svg');confirmed(self.store,work)
        batch=self.batch([source]);member=self.service.members(batch['id'])['rows'][0]
        return source,work,rule,batch,member

    def test_only_formally_approved_rule_can_verify_group(self):
        source,work,rule,batch,member=self.seed(False)
        with self.assertRaisesRegex(ValueError,'正式核准'):self.service.group_rule_plan([member['id']],rule['id'],rule['revision'])
        self.assertEqual(self.store.count('COVERAGE_RULE_CHECK'),0)

    def test_group_checks_annotation_only_and_never_confirms_protected_fields(self):
        source,work,rule,batch,member=self.seed();facts=self.store.facts(work['id']);rule_count=self.store.count('RULE')
        plan=self.service.group_rule_plan([member['id']],rule['id'],rule['revision'])
        self.assertTrue(plan['items']);self.assertTrue(all(item['observation_id']=='note' for item in plan['items']))
        self.assertEqual(plan['impact']['high_risk_items'],0)
        result=self.service.confirm_group_rule(plan,'Batch operator',True)
        self.assertFalse(result['human_confirmation_claim']);self.assertEqual(self.store.facts(work['id']),facts);self.assertEqual(self.store.count('RULE'),rule_count)
        evidence=self.service.member_evidence(member['id']);observations=evidence['works'][0]['observation_verification']
        self.assertEqual(next(o for o in observations if o['observation_id']=='note')['state'],'AUTO_VERIFIED_BY_APPROVED_RULE')
        self.assertTrue(all(o['state']!='AUTO_VERIFIED_BY_APPROVED_RULE' for o in observations if o['protected']))
        self.assertFalse(evidence['closure_allowed']);self.assertEqual(self.store.count('COVERAGE_REVIEW'),0)

    def test_rule_version_change_and_audit_failure_rollback_group(self):
        source,work,rule,batch,member=self.seed();plan=self.service.group_rule_plan([member['id']],rule['id'],rule['revision'])
        with patch.object(self.library,'event',side_effect=sqlite3.OperationalError('disk full')):
            with self.assertRaises(sqlite3.OperationalError):self.service.confirm_group_rule(plan,'Operator',True)
        self.assertEqual(self.store.count('COVERAGE_RULE_CHECK'),0)
        with self.store.transaction():self.store._write('RULE',rule['id'],dict(rule,state='DISABLED'),rule['revision'],'test_rule_rolled_back')
        with self.assertRaises(ValueError):self.service.confirm_group_rule(plan,'Operator',True)
        self.assertEqual(self.store.count('COVERAGE_RULE_CHECK'),0)

    def test_persisted_assessment_facets_are_searchable_and_explicitly_not_current_closure(self):
        source,work,batch,member=self.work_member();evidence=self.service.refresh_assessment(member['id'])
        record=self.store.get('COVERAGE_ASSESSMENT',member['id']);self.assertTrue(record['snapshot_only_current_validity_requires_recheck'])
        for grouping in ('file','directory','work','risk','method','blocker','style'):
            page=self.service.members(batch['id'],query=work['id'],group_by=grouping);self.assertEqual(page['total'],1)
        self.assertFalse(evidence['closure_allowed']);self.assertEqual(self.store.count('COVERAGE_CLOSURE'),0)

    def test_failed_analysis_and_duplicate_label_are_real_blockers(self):
        source,work,batch,member=self.work_member()
        with self.store.transaction():self.store._write('AUTO_UNIT','failed-analysis',dict(work_id=work['id'],state='FAILED',issues=[]),0,'test_failed_analysis')
        self.assertIn('UNRESOLVED_ANALYSIS_FAILURE',{b['code'] for b in self.service.member_evidence(member['id'])['blockers']})
        from dataclasses import asdict
        from template_ai.demo import demo_template
        payload=work['payload'];slot=asdict(demo_template().slots[0]);payload['slots']=[slot,slot]
        self.library.save_artwork(work['id'],payload,work['revision'])
        fresh=self.batch([source]);fresh_member=self.service.members(fresh['id'])['rows'][0]
        with self.assertRaisesRegex(ValueError,'品質檢查'):self.service.layer_plan(fresh_member['id'],work['id'],'people','CONFIRMED','Cannot approve duplicate IDs','Page1')
        self.assertIn('DUPLICATE_ID',{b['code'] for b in self.service.member_evidence(fresh_member['id'])['blockers']})

"""Actual quality/rule use withdrawal and encrypted restore, not synthetic pass flags."""
import unittest
from unittest.mock import patch
import test_quality_gold_sets as gold_fixture
import test_rule_review as rule_fixture
import test_trusted_samples as sample_fixture
from quality_acceptance_fixture import actual_positive_pair
from template_ai.quality_reports import QualityReports
from template_ai.quality_gold import USE,QualityGold
from template_ai.quality_rechecks import QualityRechecks
from template_ai.quality_pipeline import QualityPipelines
from template_ai.trusted_sample_pool import TrustedSamplePool

class TrustedQualityUseTests(unittest.TestCase):
    setUp=gold_fixture.QualityGoldSetTests.setUp
    def test_actual_accepted_quality_receipt_trace_and_source_withdrawal_block_old_recommendation(self):
        fixture=actual_positive_pair(self);reports=QualityReports(self.library);report=reports.save(reports.plan(fixture['protocol']['id']),'Synthetic reviewer',True);decision=reports.decide(report['id'],'Synthetic reviewer','Authored fixture qualification only',True)
        self.assertTrue(reports.recommendation_status(decision['id'])['quality_verified_recommendation_allowed']);entry=fixture['dataset']['entries'][0];pool=TrustedSamplePool(self.library)
        trace=QualityRechecks(self.library).source_dependencies(entry['work_id'],include_quality_evidence=True);nodes={row['key'] for row in trace['nodes']}
        self.assertIn('QUALITY_SET:'+fixture['dataset']['id'],nodes);self.assertIn('PROTOCOL:'+fixture['protocol']['id'],nodes);self.assertIn('QUALITY_REPORT:'+report['id'],nodes);self.assertIn('QUALITY_DECISION:'+decision['id'],nodes)
        pool.stop_use(pool.restriction_plan(entry['work_id'],[USE],'STOP_USE',7),'Rights reviewer',True)
        with patch('template_ai.quality_gold.healthy_source',side_effect=AssertionError('Forbidden source re-read')):
            self.assertFalse(QualityGold(self.library).validity(entry['gold_id'])['valid'])
        self.assertFalse(reports.recommendation_status(decision['id'])['quality_verified_recommendation_allowed']);self.assertEqual(self.store.get('QUALITY_VERSION_DECISION',decision['id']),decision);self.assertEqual(self.store.get('QUALITY_PAIR_REPORT',report['id']),report)

class TrustedRuleUseTests(unittest.TestCase):
    setUp=rule_fixture.RuleReviewTests.setUp
    def test_actual_rule_support_withdrawal_blocks_frozen_pipeline_without_rewriting_rule(self):
        plan=self.store.rule_review_plan([self.rule['id']]);active=self.store.review_rules(plan,'APPROVE','Reviewer','Verified complete source scope',True)[0];pipelines=QualityPipelines(self.library);pipeline=pipelines.freeze('Actual approved rule source',None,'Reviewer',True,rule_versions=[dict(id=active['id'],revision=active['revision'])]);self.assertTrue(pipelines.validity(pipeline['id'])['valid'])
        pool=TrustedSamplePool(self.library);pool.stop_use(pool.restriction_plan(self.work['id'],['RULE_APPROVAL_LOCAL'],'STOP_USE',7),'Rights reviewer',True)
        self.assertFalse(pipelines.validity(pipeline['id'])['valid']);self.assertEqual(self.store.get('RULE',active['id']),active);self.assertTrue(self.store.facts(self.work['id'])['confirmation'])

class TrustedPrivacyRestoreTests(unittest.TestCase):
    setUp=sample_fixture.TrustedSamplesTests.setUp
    def test_encrypted_restore_keeps_source_stop_redaction_and_minimal_receipt_without_auto_training(self):
        from template_ai import relational_backup as backup
        from template_ai.storage import Library
        from template_ai.training_store import TrainingStore
        sample=sample_fixture.admitted(self.store,self.work);subject=sample['positive_labels'][0]['text'];pool=TrustedSamplePool(self.library);pool.stop_use(pool.restriction_plan(self.work['id'],['GEOMETRY_TRAINING_LOCAL'],'REQUEST_LOCAL_ERASURE',0),'Privacy reviewer',True)
        result=pool.redact_training_copies(pool.redaction_plan(self.work['id'],[dict(kind='SAMPLE',id=sample['id'])]),'Privacy reviewer',True)
        target=self.root/'private-local-copy.tabi';plan=backup.plan_backup(self.library,include_sources=True,include_fonts=False);backup.create_backup(self.library,target,'synthetic backup password',plan,True);restored=backup.restore_bundle(target,self.root/'restored','synthetic backup password',True);library=Library(restored['library_root']);self.addCleanup(library.close);store=TrainingStore(library)
        self.assertEqual(store.count('SOURCE_USE_RESTRICTION'),1);self.assertEqual(store.get('SOURCE_USE_RESTRICTION',self.store.records('SOURCE_USE_RESTRICTION')[0]['id'])['state'],'STOPPED');self.assertNotEqual(store.sample_state(sample['id']),'APPROVED');self.assertTrue(store.get('SAMPLE',sample['id'])['local_training_text_redacted']);self.assertNotIn(subject,str(store.history('SAMPLE',sample['id'])));self.assertIsNotNone(store.get('TRAINING_PRIVACY_REDACTION',result['receipt']['id']));self.assertEqual(store.count('AUTO_JOB'),0)

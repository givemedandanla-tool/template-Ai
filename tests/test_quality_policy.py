import copy
import math
import sqlite3
import unittest
from unittest.mock import patch
import test_coverage_batches as fixtures
from template_ai.quality_policy import QualityPolicies
from template_ai.quality_gold import DOMAINS


class QualityPolicyTests(unittest.TestCase):
    setUp=fixtures.CoverageBatchTests.setUp
    def policy(self):return QualityPolicies(self.library)
    def plan(self):
        # Explicit synthetic fixture parameters, never shipping acceptance defaults.
        thresholds={domain:dict(minimum_independent_groups=2,minimum_gold_objects=3,minimum_precision=.9,minimum_recall=.8,maximum_group_failure_rate=.1) for domain in DOMAINS}
        return self.policy().plan('Synthetic policy arithmetic fixture',thresholds,.5,.95,'Synthetic test-only numerical parameters','QA fixture,not production evidence','SYNTHETIC_SELF_CHECK')

    def test_no_default_policy_and_approval_never_claims_model_quality_or_activation(self):
        self.assertEqual(self.policy().status(None)['state'],'UNCONFIGURED');self.assertFalse(self.policy().status(None)['valid'])
        plan=self.plan()
        with self.assertRaises(ValueError):self.policy().approve(plan,'Reviewer')
        record=self.policy().approve(plan,'Reviewer',True);self.assertTrue(self.policy().status(record['id'])['valid']);self.assertIsNone(self.store.get('SEMANTIC_ACTIVE','local-text'));self.assertEqual(self.store.count('RULE'),0)
        self.assertTrue(record['plan']['critical_owner_logo_missing_work_errors_always_block'])

    def test_missing_domain_nan_or_empty_denominator_policy_cannot_be_approved(self):
        plan=self.plan();thresholds=copy.deepcopy(plan['thresholds']);thresholds['field_types']['minimum_independent_groups']=0
        for bad in (thresholds,{},dict(plan['thresholds'],field_types=None)):
            with self.assertRaises(ValueError):self.policy().plan('Bad',bad,.5,.95,'Basis','Reference','SYNTHETIC_SELF_CHECK')
        with self.assertRaises(ValueError):self.policy().plan('Bad',plan['thresholds'],math.nan,.95,'Basis','Reference','SYNTHETIC_SELF_CHECK')
        with self.assertRaises(ValueError):self.policy().plan('Bad',plan['thresholds'],.5,None,'Basis','Reference','SYNTHETIC_SELF_CHECK')

    def test_policy_withdrawal_keeps_old_version_without_assuming_fallback_safe(self):
        record=self.policy().approve(self.plan(),'Reviewer',True);self.policy().withdraw(record['id'],record['revision'],'Reviewer','Research basis changed',True)
        self.assertFalse(self.policy().status(record['id'])['valid']);self.assertEqual(self.store.get('QUALITY_POLICY',record['id']),record)

    def test_disk_failure_cannot_create_approved_policy_in_memory_or_storage(self):
        with patch.object(self.library,'event',side_effect=sqlite3.OperationalError('disk full')):
            with self.assertRaises(sqlite3.OperationalError):self.policy().approve(self.plan(),'Reviewer',True)
        self.assertEqual(self.store.count('QUALITY_POLICY'),0);self.assertFalse(self.policy().status(None)['valid'])


class SemanticQualityIsolationTests(unittest.TestCase):
    def setUp(self):
        import test_semantic_learning as fixture
        self.case=fixture.SemanticLearningTests('runTest');self.case.setUp();self.addCleanup(self.case.doCleanups)

    def test_quality_holdout_cannot_bypass_guard_via_semantic_training_api(self):
        store=self.case.service.store;source=self.case.library.source(self.case.train['source_id'])
        with store.transaction():store._write('GROUP_ROLE',source['hash'],dict(role='HOLDOUT'),0,'synthetic_quality_holdout')
        with self.assertRaisesRegex(ValueError,'品質holdout'):self.case.service.plan(self.case.roles)
        self.assertEqual(store.count('SEMANTIC_MODEL'),0)

    def test_actual_model_history_remains_exposure_when_current_role_cache_is_missing(self):
        from template_ai.quality_groups import QualityGroups
        model=self.case.candidate();store=self.case.service.store;sha=self.case.library.source(self.case.train['source_id'])['hash']
        with self.case.library.db:self.case.library.db.execute("DELETE FROM training_records WHERE kind='GROUP_ROLE'")
        self.assertTrue(QualityGroups(self.case.library).role_conflicts([(sha,'HOLDOUT')]))
        self.assertEqual(store.get('SEMANTIC_MODEL',model['id']),model)

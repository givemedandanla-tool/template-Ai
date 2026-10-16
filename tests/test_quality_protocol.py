import sqlite3
import unittest
from unittest.mock import patch
import test_quality_gold_sets as fixtures
from template_ai.quality_gold import DOMAINS
from template_ai.quality_policy import QualityPolicies
from template_ai.quality_pipeline import QualityPipelines
from template_ai.quality_protocol import QualityProtocols


class QualityProtocolTests(unittest.TestCase):
    def setUp(self):
        fixtures.QualityGoldSetTests.setUp(self)
        plan=fixtures.QualityGoldSetTests.plan(self);self.gold_record=self.gold.confirm(plan,'Synthetic reviewer',True)
        self.dataset=self.sets.create(self.sets.plan('Synthetic independent pair',[self.gold_record['id']],True,True,'Reviewed source and independent family as one group'),'Synthetic reviewer',True)
        self.policies=QualityPolicies(self.library);thresholds={d:dict(minimum_independent_groups=2,minimum_gold_objects=2,minimum_precision=.9,minimum_recall=.9,maximum_group_failure_rate=.1) for d in DOMAINS}
        self.policy=self.policies.approve(self.policies.plan('Explicit synthetic fixture',thresholds,.5,.95,'Synthetic arithmetic fixture','Not production thresholds','SYNTHETIC_SELF_CHECK'),'Synthetic reviewer',True)
        pipelines=QualityPipelines(self.library);self.left=pipelines.freeze('Actual baseline',None,'Synthetic reviewer',True);self.right=pipelines.freeze('Actual candidate',None,'Synthetic reviewer',True);self.protocols=QualityProtocols(self.library)

    def plan(self,dataset=None):return self.protocols.plan('Predeclared pair',(dataset or self.dataset)['id'],self.policy['id'],dict(BASELINE=self.left['id'],CANDIDATE=self.right['id']),'Versions fixed before any source prediction score')
    def freeze(self):return self.protocols.freeze(self.plan(),'Synthetic reviewer',True)
    def job(self,protocol,side='BASELINE',identity='synthetic-job',owner='owner-token'):
        with self.store.transaction():return self.store._write('EVAL_JOB',identity,dict(protocol_id=protocol['id'],side=side,phase='RUNNING',owner_token=owner),0,'synthetic_bound_scheduler_job')

    def test_exact_predeclared_pair_does_not_claim_quality_or_consume_holdout_early(self):
        protocol=self.freeze();self.assertFalse(protocol['quality_pass']);self.assertTrue(self.protocols.validity(protocol['id'])['valid'])
        self.assertEqual(protocol['scope']['gold_work_count'],1);self.assertEqual(protocol['scope']['gold_object_count'],5);self.assertEqual(self.store.count('QUALITY_HOLDOUT_USAGE'),0)

    def test_begin_requires_bound_job_and_same_scope_only_then_reserves_pair(self):
        protocol=self.freeze()
        with self.assertRaisesRegex(ValueError,'持久工作'):self.protocols.begin(protocol['id'],'BASELINE','missing','owner-token')
        self.job(protocol);use=self.protocols.begin(protocol['id'],'BASELINE','synthetic-job','owner-token')
        self.assertEqual(use['side'],'BASELINE');self.assertEqual(self.store.count('QUALITY_HOLDOUT_USAGE'),1)
        self.job(protocol,'CANDIDATE','candidate-job');self.protocols.begin(protocol['id'],'CANDIDATE','candidate-job','owner-token')
        self.assertEqual(self.store.count('QUALITY_HOLDOUT_USAGE'),1);self.assertEqual(self.store.count('QUALITY_PROTOCOL_USE'),2)

    def test_copying_set_or_another_job_cannot_reset_used_holdout_for_tuning(self):
        protocol=self.freeze();self.job(protocol);self.protocols.begin(protocol['id'],'BASELINE','synthetic-job','owner-token')
        cloned=self.sets.create(self.sets.plan('Copied manifest same gold',[self.gold_record['id']],True,True,'Same already-used family'),'Reviewer',True)
        with self.assertRaisesRegex(ValueError,'全新獨立群組'):self.plan(cloned)
        self.job(protocol,'BASELINE','other-job')
        with self.assertRaisesRegex(ValueError,'另一工作'):self.protocols.begin(protocol['id'],'BASELINE','other-job','owner-token')

    def test_explicit_gold_exposure_invalidates_future_use_and_preserves_gold_protocol(self):
        protocol=self.freeze()
        with self.assertRaises(ValueError):self.protocols.expose(protocol['id'],'Reviewer','Inspect failure cases')
        self.protocols.expose(protocol['id'],'Reviewer','Inspect failure cases',True)
        self.assertFalse(self.protocols.validity(protocol['id'])['valid']);self.assertEqual(self.store.get('QUALITY_PROTOCOL',protocol['id']),protocol);self.assertEqual(self.store.get('QUALITY_GOLD',self.gold_record['id']),self.gold_record)

    def test_policy_withdrawal_and_changed_scope_prevent_old_preview_freeze(self):
        plan=self.plan();self.policies.withdraw(self.policy['id'],self.policy['revision'],'Reviewer','Research basis withdrawn',True)
        with self.assertRaises(ValueError):self.protocols.freeze(plan,'Reviewer',True)
        self.assertEqual(self.store.count('QUALITY_PROTOCOL'),0)

    def test_late_audit_failure_rolls_back_content_reservation_and_side_start(self):
        protocol=self.freeze();self.job(protocol);event=self.library.event
        def failed(identity,action):
            if 'fixed_side_started' in action:raise sqlite3.OperationalError('disk full after content reservation')
            event(identity,action)
        with patch.object(self.library,'event',side_effect=failed):
            with self.assertRaises(sqlite3.OperationalError):self.protocols.begin(protocol['id'],'BASELINE','synthetic-job','owner-token')
        self.assertEqual(self.store.count('QUALITY_HOLDOUT_USAGE'),0);self.assertEqual(self.store.count('QUALITY_PROTOCOL_USE'),0)

"""Actual approved isolated rules, shared review guards and historical leakage."""
import copy,unittest
from unittest.mock import patch
import test_noise_authoring as fixtures
from template_ai.quality_repairs import QualityRepairs
from template_ai.quality_repair_rules import approve,checked,STATE
from template_ai.quality_rules import snapshots,production_current,approved_for_quality_current
from template_ai.quality_groups import QualityGroups
from template_ai.quality_pipeline import QualityPipelines


class QualityRepairRuleTests(unittest.TestCase):
    setUp=fixtures.NoiseAuthorTests.setUp
    propose=fixtures.NoiseAuthorTests.propose

    def prepare(self,layer='NOISE_RULE'):
        current=self.store.facts(self.work['id']);observations=copy.deepcopy(current['observations'])
        for observation in observations:
            if observation['id']=='note':observation['object_type']='TEXT'
        saved=self.store.save_facts(self.work['id'],observations,current['revision'],self.work['revision'])
        self.facts=self.store.confirm_facts(self.work['id'],[o['id'] for o in saved['observations']],saved['revision'],saved['pins'],self.store.source_proof(self.work['id']),'Synthetic reviewer',True)
        pending=self.propose(zone=dict(x=0,y=0,w=1,h=1))
        service=QualityRepairs(self.library)
        plan=service.plan_source_issue(self.work['id'],'SOURCE_FACTS',self.work['id'],'Actual source-context noise repair investigation')
        issue=service.create_source_issue(plan,'Reviewer','Inspect exact confirmed source context',True)
        root=service.root_plan(issue['id'],layer,'Narrow noise scope requires a separately approved candidate','Source, counterexample and protected fields reviewed',True,True)
        review=service.confirm_root(root,'Reviewer',True)
        return pending,review,self.store.rule_review_plan([pending['id']])

    def candidate(self):
        pending,review,plan=self.prepare()
        return pending,approve(self.store,review['id'],plan,'Reviewer','Only isolated quality use after detailed source review',True,True)[0]

    def test_explicit_rule_executes_in_frozen_pipeline_but_default_remains_empty(self):
        pending,candidate=self.candidate();before=self.library.artwork(self.work['id'])
        self.assertEqual(checked(self.store,candidate['id'],candidate['revision']),candidate)
        self.assertEqual(self.store.get('RULE',pending['id'])['state'],'ISOLATED_IN_REPAIR')
        with self.assertRaises(ValueError):self.store.review_rules(self.store.rule_review_plan([pending['id']]),'APPROVE','Reviewer','Cannot bypass isolation through ordinary approval',True,True)
        for identity in (pending['id'],candidate['id']):
            for operation in ('DISABLE','ROLLBACK'):
                with self.assertRaisesRegex(ValueError,'修復隔離'):self.store.rule_version_plan(identity,operation,history_revision=1)
        self.assertEqual(snapshots(self.store),[])
        frozen=snapshots(self.store,[dict(id=candidate['id'],revision=candidate['revision'])])
        self.assertTrue(approved_for_quality_current(self.store,frozen));self.assertFalse(production_current(self.store,frozen))
        pipelines=QualityPipelines(self.library)
        pipeline=pipelines.freeze('Explicit isolated rule quality trial',None,'Reviewer',True,rule_versions=[dict(id=candidate['id'],revision=candidate['revision'])])
        result=pipelines.predict_source(pipeline['id'],self.source['id'])
        matches=[m for w in result['predictions'] for o in w['observations'] for m in o['rule_diagnostics']['matches']]
        self.assertIn(candidate['id'],[m['id'] for m in matches]);self.assertEqual(self.library.artwork(self.work['id']),before)
        self.assertFalse(candidate['quality_pass']);self.assertFalse(candidate['production_active'])

    def test_shared_high_risk_policy_and_root_layer_cannot_be_bypassed(self):
        pending,review,plan=self.prepare()
        with self.assertRaisesRegex(ValueError,'HIGH'):approve(self.store,review['id'],plan,'Reviewer','Missing detailed human review',True,False)
        self.assertEqual(self.store.get('RULE',pending['id'])['state'],'PENDING')
        service=QualityRepairs(self.library);root=service.root_plan(review['plan']['issue_id'],'MODEL_REGRESSION','Different actual layer','This is not a noise-rule root review',True,True)
        other=service.confirm_root(root,'Reviewer',True)
        with self.assertRaisesRegex(ValueError,'NOISE_RULE'):approve(self.store,other['id'],self.store.rule_review_plan([pending['id']]),'Reviewer','Wrong candidate family',True,True)

    def test_late_audit_failure_rolls_back_origin_lock_and_candidate(self):
        pending,review,plan=self.prepare();original=self.store.get('RULE',pending['id']);event=self.library.event
        def fail(identity,action,*args,**kwargs):
            if action=='training_repair_rule_candidate_independently_approved_not_published':raise OSError('Synthetic late audit disk failure')
            return event(identity,action,*args,**kwargs)
        with patch.object(self.library,'event',side_effect=fail):
            with self.assertRaises(OSError):approve(self.store,review['id'],plan,'Reviewer','No partial candidate',True,True)
        self.assertEqual(self.store.get('RULE',pending['id']),original);self.assertEqual(self.store.count('RULE'),1)

    def test_candidate_training_exposure_survives_later_withdrawal(self):
        pending,candidate=self.candidate();self.assertIn((self.source['hash'],'TRAIN'),QualityGroups(self.library).model_exposure_roles())
        with self.store.transaction():self.store._write('RULE',candidate['id'],dict(candidate,state='REPAIR_WITHDRAWN'),candidate['revision'],'synthetic_candidate_withdrawal')
        self.assertIn((self.source['hash'],'TRAIN'),QualityGroups(self.library).model_exposure_roles())
        self.assertFalse(approved_for_quality_current(self.store,[candidate]))
        with self.assertRaises(ValueError):snapshots(self.store,[dict(id=candidate['id'],revision=candidate['revision'])])

    def test_actual_holdout_lock_blocks_isolated_approval(self):
        pending,review,plan=self.prepare()
        with self.store.transaction():self.store._write('GROUP_ROLE',self.source['hash'],dict(role='HOLDOUT'),0,'synthetic_reserved_holdout')
        with self.assertRaisesRegex(ValueError,'HOLDOUT'):approve(self.store,review['id'],self.store.rule_review_plan([pending['id']]),'Reviewer','Cannot train on heldout answers',True,True)
        self.assertEqual(self.store.get('RULE',pending['id'])['state'],'PENDING')

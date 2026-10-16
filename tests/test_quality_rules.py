import unittest
from types import SimpleNamespace
import test_noise_authoring as fixtures
from template_ai.quality_pipeline import QualityPipelines
from template_ai.quality_rules import snapshots,production_current
from template_ai.quality_groups import QualityGroups


class QualityRuleTests(unittest.TestCase):
    setUp=fixtures.NoiseAuthorTests.setUp
    propose=fixtures.NoiseAuthorTests.propose

    def approved(self):
        import copy
        current=self.store.facts(self.work['id']);observations=copy.deepcopy(current['observations'])
        for observation in observations:
            if observation['id']=='note':observation['object_type']='TEXT'
        saved=self.store.save_facts(self.work['id'],observations,current['revision'],self.work['revision'])
        self.facts=self.store.confirm_facts(self.work['id'],[o['id'] for o in saved['observations']],saved['revision'],saved['pins'],self.store.source_proof(self.work['id']),'Synthetic reviewer',True)
        pending=self.propose(zone=dict(x=0,y=0,w=1,h=1))
        plan=self.store.rule_review_plan([pending['id']])
        return self.store.review_rules(plan,'APPROVE','Reviewer','Explicit source context and counterexamples reviewed',True,True)[0]

    def test_actual_frozen_rules_execute_scope_checks_and_keep_unknown_without_gold(self):
        rule=self.approved();service=QualityPipelines(self.library);pipeline=service.freeze('Real approved rules parser',None,'Reviewer',True)
        result=service.predict_source(pipeline['id'],self.source['id'])
        observations=[o for work in result['predictions'] for o in work['observations']]
        note=next(o for o in observations if o['text']=='已校稿')
        self.assertTrue(result['capabilities']['rule_processor_executed'])
        self.assertEqual(note['rule_diagnostics']['matches'][0]['id'],rule['id'])
        self.assertEqual(note['rule_diagnostics']['state'],'KEPT_PROTECTED')
        self.assertFalse(note['rule_diagnostics']['human_gold_used'])
        self.assertEqual(note['classification'],'UNKNOWN')
        self.assertEqual(self.store.count('QUALITY_GOLD'),0)

    def test_historical_approved_rule_version_can_execute_but_not_be_current_production_evidence(self):
        rule=self.approved();service=QualityPipelines(self.library);pipeline=service.freeze('Before defer exact rules',None,'Reviewer',True)
        plan=self.store.rule_version_plan(rule['id'],'DISABLE');self.store.apply_rule_version(plan,'Reviewer','Keep historical comparison but stop trusting current rule',True)
        self.assertTrue(service.validity(pipeline['id'])['valid'])
        result=service.predict_source(pipeline['id'],self.source['id']);self.assertTrue(result['predictions'])
        frozen=snapshots(self.store,[dict(id=rule['id'],revision=rule['revision'])])
        self.assertEqual(frozen,[rule]);self.assertFalse(production_current(self.store,frozen))
        roles=QualityGroups(self.library).model_exposure_roles()
        self.assertIn((self.source['hash'],'TRAIN'),roles)

    def test_rule_authoring_and_late_approval_cannot_absorb_holdout_answers(self):
        pending=self.propose()
        with self.store.transaction():self.store._write('GROUP_ROLE',self.source['hash'],dict(role='HOLDOUT'),0,'synthetic_reserved_holdout')
        with self.assertRaisesRegex(ValueError,'HOLDOUT'):self.propose()
        plan=self.store.rule_review_plan([pending['id']])
        with self.assertRaisesRegex(ValueError,'HOLDOUT'):self.store.review_rules(plan,'APPROVE','Reviewer','Must not absorb heldout answers',True,True)
        self.assertEqual(self.store.get('RULE',pending['id'])['state'],'PENDING')

    def test_explicit_no_rules_snapshot_is_independent_of_new_active_rules(self):
        service=QualityPipelines(self.library);pipeline=service.freeze('No-rule baseline',None,'Reviewer',True,rule_versions=[])
        self.approved()
        self.assertTrue(service.validity(pipeline['id'])['valid'])
        result=service.predict_source(pipeline['id'],self.source['id'])
        self.assertTrue(all(not o['rule_diagnostics']['matches'] for w in result['predictions'] for o in w['observations']))

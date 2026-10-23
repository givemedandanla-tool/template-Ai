"""Actual trained/approved versions cannot clear quarantine by changing IDs.

These verify component identity enforcement; parser confirmation has a separate
actual failed-evaluation integration test in test_quality_decisions.
"""
import unittest
import test_semantic_learning as semantic_fixture
import test_quality_rules as rule_fixture
from template_ai.quality_pipeline import QualityPipelines
from template_ai.quality_trust import components,blockers


class QualityModelIdentityTests(unittest.TestCase):
    setUp=semantic_fixture.SemanticLearningTests.setUp
    work=semantic_fixture.SemanticLearningTests.work

    def test_actual_retraining_same_parameters_cannot_reset_model_quarantine(self):
        plan=self.service.plan(self.roles)
        first=self.service.train(plan,'Synthetic trainer',True)
        second=self.service.train(plan,'Synthetic trainer',True)
        self.assertNotEqual(first['id'],second['id'])
        pipelines=QualityPipelines(self.library)
        frozen=[pipelines.freeze('Actual model '+row['id'],row['id'],'Reviewer',True) for row in (first,second)]
        identities=[next(c for c in components(p['manifest']) if c['kind']=='MODEL') for p in frozen]
        self.assertEqual(identities[0]['key'],identities[1]['key'])
        store=pipelines.store
        with store.transaction():
            store._write('QUALITY_COMPONENT_QUARANTINE',identities[0]['key'],dict(case_id='synthetic_identity_guard_case'),0,'synthetic_component_identity_guard')
        for pipeline in frozen:
            self.assertTrue(any(c['kind']=='MODEL' for c in blockers(store,pipeline)))


class QualityRuleIdentityTests(unittest.TestCase):
    setUp=rule_fixture.QualityRuleTests.setUp
    propose=rule_fixture.QualityRuleTests.propose
    approved=rule_fixture.QualityRuleTests.approved

    def test_actual_same_approved_predicate_cannot_reset_rule_quarantine(self):
        first=self.approved()
        # Keep the confirmed source revision unchanged so both approvals remain valid.
        pending=self.propose(zone=dict(x=0,y=0,w=1,h=1))
        plan=self.store.rule_review_plan([pending['id']])
        second=self.store.review_rules(plan,'APPROVE','Reviewer','Same confirmed source, explicit second approval',True,True)[0]
        self.assertNotEqual(first['id'],second['id'])
        service=QualityPipelines(self.library)
        frozen=[service.freeze('Actual rule '+row['id'],None,'Reviewer',True,rule_versions=[dict(id=row['id'],revision=row['revision'])]) for row in (first,second)]
        identities=[next(c for c in components(p['manifest']) if c['kind']=='RULE') for p in frozen]
        self.assertEqual(identities[0]['key'],identities[1]['key'])
        with self.store.transaction():
            self.store._write('QUALITY_COMPONENT_QUARANTINE',identities[0]['key'],dict(case_id='synthetic_identity_guard_case'),0,'synthetic_component_identity_guard')
        for pipeline in frozen:
            self.assertTrue(any(c['kind']=='RULE' for c in blockers(self.store,pipeline)))

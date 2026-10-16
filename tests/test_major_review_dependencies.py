"""Actual learned/rule aliases and quality-approved runtime downstream trust."""
import copy,unittest
import test_quality_provenance as provenance
import test_quality_component_trust as identities
import test_quality_repair_releases as releases
from template_ai.quality_rechecks import QualityRechecks
from template_ai.quality_repairs import QualityRepairs
from template_ai.quality_pipeline import QualityPipelines
from template_ai.quality_trust import blockers
from template_ai.quality_gold import QualityGold


def source_case(test,work_id):
    repairs=QualityRepairs(test.library)
    issue=repairs.create_source_issue(repairs.plan_source_issue(work_id,'SOURCE_FACTS',work_id,'Authored serious ownership error with exact original source evidence'),'Synthetic reviewer','Explicit source issue, not inferred global cause',True)
    service=QualityRechecks(test.library)
    value=service.source_plan(issue_id=issue['id'],category='FIELD_OWNER',correct_example='Exact source confirms owner Alex',wrong_example='Historical interpretation assigns field to Blair')
    return service,value


class MajorModelDependencyTests(unittest.TestCase):
    setUp=provenance.QualityProducerProvenanceTests.setUp
    trained_model=provenance.QualityProducerProvenanceTests.trained_model
    def test_actual_source_training_quarantines_same_parameter_model_aliases(self):
        first=self.trained_model();second=self.semantic.train(self.training_plan,'Synthetic trainer',True)
        pipes=[QualityPipelines(self.library).freeze('Actual alias '+r['id'],r['id'],'Synthetic reviewer',True) for r in (first,second)]
        origin=self.training_plan['scopes'][0]['work_id'];service,value=source_case(self,origin)
        service.confirm_source(value,'Synthetic reviewer','Suspend actual dependent learned parameters',True)
        for pipe in pipes:self.assertTrue(any(b['kind']=='MODEL' for b in blockers(self.store,pipe)))
        self.assertFalse(any(b['kind']=='PARSER' for b in blockers(self.store,pipes[0])))


class MajorRuleDependencyTests(unittest.TestCase):
    setUp=identities.QualityRuleIdentityTests.setUp
    approved=identities.QualityRuleIdentityTests.approved
    propose=identities.QualityRuleIdentityTests.propose
    def test_actual_rule_evidence_quarantines_equivalent_approved_rule_ids(self):
        first=self.approved();pending=self.propose(zone=dict(x=0,y=0,w=1,h=1));second=self.store.review_rules(self.store.rule_review_plan([pending['id']]),'APPROVE','Synthetic reviewer','Same current checked predicate',True,True)[0]
        pipes=[QualityPipelines(self.library).freeze('Actual rule alias '+r['id'],None,'Synthetic reviewer',True,rule_versions=[dict(id=r['id'],revision=r['revision'])]) for r in (first,second)]
        service,value=source_case(self,self.work['id']);service.confirm_source(value,'Synthetic reviewer','Suspend actual dependent rule behavior',True)
        for pipe in pipes:self.assertTrue(any(b['kind']=='RULE' for b in blockers(self.store,pipe)))
        current,invalid=self.store.active_noise_rules();self.assertFalse(current);self.assertEqual(set(invalid),{first['id'],second['id']})


class MajorGoldDeploymentTests(unittest.TestCase):
    setUp=releases.QualityRepairReleaseTests.setUp
    accepted=releases.QualityRepairReleaseTests.accepted
    install=releases.QualityRepairReleaseTests.install
    def test_source_gold_dependency_suspends_existing_accepted_runtime_without_rewriting_it(self):
        event=self.install()['event'];before=copy.deepcopy(event);pin=self.releases.pin();self.assertIsNotNone(pin)
        origin=self.store.db.execute("SELECT json_extract(payload,'$.work_id') FROM training_records WHERE kind='QUALITY_GOLD' ORDER BY rowid DESC LIMIT 1").fetchone()[0];service,value=source_case(self,origin);gold_ids=[n['key'].split(':')[1] for n in value['dependency_nodes'] if n['key'].startswith('GOLD:')];self.assertTrue(gold_ids)
        self.assertTrue(any(n['key']=='DEPLOYMENT:'+event['id'] for n in value['dependency_nodes']))
        service.confirm_source(value,'Synthetic reviewer','Quality source under serious new doubt; do not auto reuse old acceptance',True)
        for identity in gold_ids:self.assertFalse(QualityGold(self.library).validity(identity)['valid'])
        with self.assertRaises(ValueError):self.releases.pin()
        self.assertEqual(self.store.get('QUALITY_PIPELINE_DEPLOYMENT',event['id']),before)

if __name__=='__main__':unittest.main()

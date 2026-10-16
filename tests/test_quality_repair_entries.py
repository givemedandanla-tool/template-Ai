"""Persisted actual exception entry and historical rule/sample/dataset/geometry edges."""
import copy,unittest
import test_trusted_samples as fixtures
from test_rule_review import pending_rule
from test_noise_hits import activate
from test_trusted_samples import admitted
from test_dataset_learning import frozen
from template_ai.quality_rechecks import QualityRechecks
from template_ai.quality_repairs import QualityRepairs
from template_ai.automatic_training import AutomaticTraining


class QualityRepairEntryTests(unittest.TestCase):
    setUp=fixtures.TrustedSamplesTests.setUp

    def exception(self):
        facts=self.store.facts(self.work['id']);self.store.revoke_facts(self.work['id'],facts['revision'],'Explicit synthetic human re-review needed')
        auto=AutomaticTraining(self.library);unit,_=auto.process_work(self.work,dict(actor='Reviewer'));self.assertTrue(unit['issues'])
        return auto,unit

    def test_actual_exception_receipt_binds_same_work_and_rejects_invented_or_stale_preview(self):
        auto,unit=self.exception();service=QualityRepairs(self.library)
        preview=service.plan_source_issue(self.work['id'],'EXCEPTION',unit['id'],'Actual source facts exception under investigation')
        with self.assertRaises(ValueError):service.plan_source_issue(self.work['id'],'EXCEPTION','invented-unit','Cannot invent a failure')
        issue=service.create_source_issue(preview,'Reviewer','Locate actual persisted exception, no automatic repair',True)
        self.assertEqual(issue['evidence']['origin_reference']['kind'],'AUTO_UNIT')
        self.assertFalse(service.root_plan(issue['id'],'FIELD_OWNER_SEMANTICS','Unknown semantic root','Original truth still under human review')['can_prepare_candidate'])
        facts=self.store.facts(self.work['id']);observations=copy.deepcopy(facts['observations']);observations[0]['text']='Another synthetic source reading'
        self.store.save_facts(self.work['id'],observations,facts['revision'],self.work['revision']);auto.process_work(self.work,dict(actor='Reviewer'))
        with self.assertRaises(ValueError):service.create_source_issue(preview,'Reviewer','Stale actual exception preview',True)
        self.assertEqual(self.store.count('QUALITY_REPAIR_ISSUE'),1)

    def test_actual_approved_rule_sample_dataset_and_geometry_template_history_are_reachable(self):
        _,rule_work,pending=pending_rule(self.store,self.root,'rule-evidence.svg');rule=activate(self.store,pending)
        sample=admitted(self.store,self.work);self.assertIn(rule['id'],[r['id'] for r in sample['rule_dependencies']])
        dataset=frozen(self.store,[sample]);plan=self.store.geometry_learning_plan(dataset['id'],sample['id'],'Actual geometry draft from rule-filtered sample')
        template=self.store.learn_dataset_sample(plan,self.store.source_proof(self.work['id']),'Reviewer',True)
        before=self.library.db.total_changes;impact=QualityRechecks(self.library).source_dependencies(rule_work['id']);keys={node['key'] for node in impact['nodes']}
        self.assertIn('RULE:'+rule['id']+':'+str(rule['revision']),keys);self.assertIn('SAMPLE:'+sample['id'],keys)
        self.assertIn('DATASET:'+dataset['id'],keys);self.assertIn('TEMPLATE:'+template.id+':'+str(template.version),keys)
        edges={(edge['left'],edge['right']) for edge in impact['edges']}
        self.assertIn(('RULE:'+rule['id']+':'+str(rule['revision']),'SAMPLE:'+sample['id']),edges)
        self.assertEqual(self.library.db.total_changes,before)

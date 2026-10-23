"""Actual historical training-to-AUTO-to-template/customer reachability."""
import copy,unittest
import test_quality_provenance as fixtures
from template_ai.quality_rechecks import QualityRechecks
from template_ai.quality_repairs import QualityRepairs
from template_ai.demo import demo_template
from template_ai.customers import CustomerStore
from template_ai.input_graph import InputGraph
from template_ai.model import new_id


class QualityRepairImpactTests(unittest.TestCase):
    setUp=fixtures.QualityProducerProvenanceTests.setUp
    trained_model=fixtures.QualityProducerProvenanceTests.trained_model
    actual_work=fixtures.QualityProducerProvenanceTests.actual_work

    def test_actual_training_producer_and_historical_templates_reach_customer_without_writes(self):
        model=self.trained_model();produced=self.actual_work(1);template=demo_template()
        template.source_id=produced['source_id'];template.source_work_id=produced['id'];template.source_work_revision=produced['revision'];self.library.save_template(template)
        next_version=copy.deepcopy(template);next_version.id=new_id();next_version.version=2;self.library.save_template(next_version)
        customers=CustomerStore(self.library);graph=InputGraph.from_legacy([{'name':['Synthetic Impact'],'phone':['0100'],'company':'c1'}],[{'name':'Synthetic Company'}])
        customer=customers.create_graph('IMPACT01','Synthetic Impact',graph.data,next_version.id,approved=True)
        origin=self.training_plan['scopes'][0]['work_id'];before=self.library.db.total_changes
        plan=QualityRechecks(self.library).source_dependencies(origin);keys={n['key'] for n in plan['nodes']}
        self.assertIn('MODEL:'+model['id']+':'+str(model['revision']),keys);self.assertIn(produced['id'],plan['affected_work_ids'])
        self.assertIn('TEMPLATE:'+template.id+':1',keys);self.assertIn('TEMPLATE:'+next_version.id+':2',keys)
        self.assertIn('CUSTOMER:'+customer['id'],keys);self.assertTrue(plan['unknown_unrecorded_dependencies'])
        self.assertEqual(self.library.db.total_changes,before);self.assertFalse(plan['automatic_training'])

    def test_source_issue_can_preview_known_dependencies_without_inventing_a_pipeline(self):
        service=QualityRepairs(self.library)
        issue=service.create_source_issue(service.plan_source_issue(self.work['id'],'SOURCE_FACTS',self.work['id'],'Source facts issue with unknown producer version'),'Reviewer','Inspect source dependencies first',True)
        before=self.library.db.total_changes;plan=service.impact_plan(issue['id'])
        self.assertIn(self.work['id'],plan['dependencies']['affected_work_ids']);self.assertTrue(plan['dependencies']['complete_known_graph'])
        self.assertFalse(plan['automatic_quarantine']);self.assertFalse(plan['automatic_training']);self.assertEqual(self.library.db.total_changes,before)
        with self.assertRaises(ValueError):service.impact_plan(issue['id'],'MODEL')

    def test_missing_producer_revision_is_potential_and_cannot_be_presented_as_exact(self):
        model=self.trained_model();produced=self.actual_work(2);payload=copy.deepcopy(produced['payload'])
        payload['analysis_evidence']['semantic_model'].pop('model_revision')
        self.library.save_artwork(produced['id'],payload,produced['revision'])
        origin=self.training_plan['scopes'][0]['work_id'];plan=QualityRechecks(self.library).source_dependencies(origin)
        node=next(n for n in plan['nodes'] if n['key']=='WORK:'+produced['id'])
        self.assertEqual(node['dependency_match'],'POTENTIAL_MISSING_MODEL_REVISION')
        self.assertEqual(plan['unscanned_legacy_dependencies'],'UNKNOWN_NOT_ASSUMED_SAFE')

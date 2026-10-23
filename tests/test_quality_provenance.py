"""Real trained/activated AUTO producers must be reachable by major rechecks."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import test_quality_rechecks as recheck_fixture
import test_semantic_learning as semantic_fixture
from template_ai.semantic_learning import SemanticLearning
from template_ai.automatic_training import AutomaticTraining,run_automatic
from template_ai.training_pipeline import LIVE_OWNERS
from template_ai.quality_pipeline import QualityPipelines
from template_ai.quality_rechecks import blocked
from template_ai.coverage_batches import CoverageBatches
from template_ai.coverage_evidence import work_context
from template_ai.source_analysis import ANALYSER_VERSION
from template_ai.training_store import digest


class QualityProducerProvenanceTests(unittest.TestCase):
    setUp=recheck_fixture.QualityRecheckTests.setUp
    build=recheck_fixture.QualityRecheckTests.build
    critical=recheck_fixture.QualityRecheckTests.critical

    def trained_model(self):
        self.semantic=SemanticLearning(self.library)
        context=SimpleNamespace(root=self.root,library=self.library,service=self.semantic)
        train=semantic_fixture.SemanticLearningTests.work(context,'provenance-train',[
            ('title','資深雲端工程師'),('title','資深後端工程師'),('address','台中市西區公益路10號'),('address','台中市西區中正路20號')])
        validation=semantic_fixture.SemanticLearningTests.work(context,'provenance-validation',[
            ('title','資深前端工程師'),('address','台中市西區民生路30號')])
        self.training_plan=self.semantic.plan({train['id']:'TRAIN',validation['id']:'VALIDATION'})
        row=self.semantic.train(self.training_plan,'Synthetic trainer',True)
        self.semantic.activate(row['id'],row['revision'],0,'Reviewer','Explicit synthetic actual model activation',True)
        return self.store.get('SEMANTIC_MODEL',row['id'])

    def actual_work(self,index):
        path=self.root/f'actual-model-source-{index}.svg'
        path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 90 54"><rect id="paper" width="90" height="54" fill="white"/><text id="name" x="5" y="12" font-size="4">Name: Synthetic Person '+str(index)+'</text><text id="title" x="5" y="24" font-size="4">資深前端工程師</text></svg>')
        before=path.read_bytes();service=AutomaticTraining(self.library);job=service.create(service.preflight([path]),'Synthetic operator',True);claimed=service.claim(job['id'],job['revision'],True)
        try:done=run_automatic(self.library.root,claimed['id'],claimed['owner']['token'])
        finally:LIVE_OWNERS.discard(claimed['owner']['token'])
        self.assertEqual(done['phase'],'COMPLETED_WITH_EXCEPTIONS');self.assertEqual(done['items'][0]['state'],'WAITING_REVIEW');self.assertIsNone(done['items'][0].get('error'));self.assertEqual(path.read_bytes(),before)
        works=self.library.artworks(done['items'][0]['source_id']);self.assertTrue(works)
        return works[0]

    def failed_pair_with_actual_model(self,model_id):
        original=QualityPipelines.freeze
        def freeze(service,name,ignored_model,actor,approved=False,**kwargs):
            return original(service,name,model_id,actor,approved,**kwargs)
        with patch.object(QualityPipelines,'freeze',new=freeze):return self.critical()

    def test_actual_auto_parser_and_model_provenance_are_found_and_quarantined(self):
        model=self.trained_model();work=self.actual_work(1);payload=work['payload']
        self.assertEqual(payload['analysis_version'],ANALYSER_VERSION)
        self.assertEqual(payload['analysis_evidence']['semantic_model']['model_id'],model['id'])
        parser=self.failed_pair_with_actual_model(model['id']);self.assertIn(work['id'],[r['work_id'] for r in parser['rows']])
        plan=self.rechecks.plan(self.protocol['id'],'BASELINE','MODEL');row=next(r for r in plan['rows'] if r['work_id']==work['id'])
        self.assertEqual(row['source_semantic_model_id'],model['id']);self.assertFalse(row['legacy_dependency_versions_unknown'])
        before=self.library.artwork(work['id']);self.rechecks.confirm(plan,'Reviewer','Actual produced model dependency has known critical failure',True)
        self.assertTrue(blocked(self.store,work['id']));self.assertEqual(self.library.artwork(work['id']),before)

    def test_same_weights_other_version_is_potential_impact_and_review_keeps_actual_source_model(self):
        original=self.trained_model();first=self.actual_work(1)
        clone=self.semantic.train(self.training_plan,'Synthetic trainer',True)
        active=self.store.get('SEMANTIC_ACTIVE','local-text')
        self.semantic.activate(clone['id'],clone['revision'],active['revision'],'Reviewer','Explicit second actual version',True)
        clone=self.store.get('SEMANTIC_MODEL',clone['id']);second=self.actual_work(2)
        self.assertNotEqual(original['id'],clone['id']);self.assertEqual(original['weights_digest'],clone['weights_digest'])
        context=work_context(CoverageBatches(self.library),first['id'])['context']
        self.assertEqual(context['source_semantic_model_id'],original['id']);self.assertEqual(context['semantic_model_digest'],digest(clone))
        self.failed_pair_with_actual_model(original['id']);plan=self.rechecks.plan(self.protocol['id'],'BASELINE','MODEL')
        first_row=next(r for r in plan['rows'] if r['work_id']==first['id']);second_row=next(r for r in plan['rows'] if r['work_id']==second['id'])
        self.assertFalse(first_row['legacy_dependency_versions_unknown']);self.assertTrue(second_row['legacy_dependency_versions_unknown'])
        self.assertEqual(second_row['dependency_match'],'POTENTIAL_SAME_WEIGHTS_OTHER_MODEL_VERSION')

    def test_actual_model_reapproval_changes_review_context_but_not_independent_truth_dependencies(self):
        model=self.trained_model();work=self.actual_work(1)
        before_context,_,before_truth=self.gold.dependencies(work['id'])
        active=self.store.get('SEMANTIC_ACTIVE','local-text')
        self.semantic.activate(model['id'],model['revision'],active['revision'],'Reviewer','Same parameter version explicit renewed approval',True)
        after_context,_,after_truth=self.gold.dependencies(work['id'])
        self.assertNotEqual(before_context['context_digest'],after_context['context_digest'])
        self.assertEqual(before_truth,after_truth)
        self.assertEqual(self.store.count('QUALITY_GOLD'),0,'This checks dependency identity, not invented human Gold approval')

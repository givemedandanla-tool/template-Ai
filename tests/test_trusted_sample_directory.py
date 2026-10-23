"""Related-group admission safety and bounded actual correction-history paging."""
import copy,unittest
from unittest.mock import patch
import test_trusted_samples as fixture
import test_noise_authoring as noise_fixture
import test_quality_gold_sets as gold_fixture
from training_fixture import source_work
from template_ai.trusted_sample_pool import TrustedSamplePool
from template_ai.quality_gold import QualityGold
from template_ai.quality_groups import QualityGroups
from template_ai.quality_sets import QualitySets

class TrustedSampleDirectoryTests(unittest.TestCase):
    setUp=fixture.TrustedSamplesTests.setUp
    def test_actual_declared_near_duplicate_holdout_family_blocks_new_sample_admission(self):
        self.gold=QualityGold(self.library);gold=self.gold.confirm(gold_fixture.QualityGoldSetTests.plan(self),'Reviewer',True);sets=QualitySets(self.library);sets.create(sets.plan('Reserved actual source',[gold['id']],True,True,'Reviewed complete current source'),'Reviewer',True)
        source,work=source_work(self.library,self.root,'related.svg',note_text='Different bytes related family');noise_fixture.confirmed(self.store,work);groups=QualityGroups(self.library);groups.confirm_link(groups.link_plan('CONTENT:'+self.source['hash'],'CONTENT:'+source['hash'],'NEAR_DUPLICATE','Manually verified actual family','Synthetic source comparison'),'Reviewer',True)
        self.assertTrue(self.store.sample_approval_plan(work['id'],fixture.RIGHTS)['errors']);pool=TrustedSamplePool(self.library);candidate=next(r for r in self.store.records('SAMPLE_CANDIDATE') if r['work_id']==work['id']);self.assertTrue(pool.detail(candidate['id'])['errors']);self.assertEqual(self.store.count('SAMPLE'),0)

    def test_51_actual_saved_corrections_page_without_loading_images_models_or_promoting_diagnostics(self):
        for index in range(50):
            facts=self.store.facts(self.work['id']);observations=copy.deepcopy(facts['observations']);observations[0]['prior_prediction']='User-reported diagnostic '+str(index);saved=self.store.save_facts(self.work['id'],observations,facts['revision'],self.work['revision']);self.store.confirm_facts(self.work['id'],[o['id'] for o in observations],saved['revision'],saved['pins'],self.store.source_proof(self.work['id']),'Reviewer',True)
        pool=TrustedSamplePool(self.library)
        with patch('template_ai.importer.import_file',side_effect=AssertionError('No source reload for directory')),patch('template_ai.semantic_learning.CharacterModel',side_effect=AssertionError('No model load for directory')):
            page=pool.directory();tail=pool.directory(offset=50);diagnostics=pool.directory('CONFLICTS')
        self.assertEqual(page['total_candidates'],51);self.assertEqual(page['scanned'],50);self.assertEqual(len(page['rows']),50);self.assertFalse(page['complete_scan']);self.assertEqual(tail['scanned'],1);self.assertTrue(tail['complete_scan']);self.assertFalse(page['images_loaded']);self.assertTrue(diagnostics['rows']);self.assertEqual(self.store.count('SAMPLE'),0);self.assertEqual(self.store.count('AUTO_JOB'),0)

    def test_actual_owned_trace_pages_51_exact_manifests_by_name_without_loading_weights(self):
        from template_ai.quality_command import run_command
        sample=fixture.admitted(self.store,self.work)
        for index in range(51):self.store.create_dataset(self.store.dataset_plan('Synthetic exact manifest '+str(index),[dict(sample_id=sample['id'],role='TRAIN')]),'Reviewer',True)
        candidate=self.store.records('SAMPLE_CANDIDATE')[0]
        first=run_command(self.library.root,'SAMPLE_TRACE',dict(identity=candidate['id'],offset=0));tail=run_command(self.library.root,'SAMPLE_TRACE',dict(identity=candidate['id'],offset=50))
        self.assertEqual(first['counts_by_kind']['DATASET'],51);self.assertEqual(len(first['rows']),50);self.assertLessEqual(len(tail['rows']),50);self.assertEqual(first['total_nodes'],len(first['rows'])+len(tail['rows']));self.assertTrue(any('Synthetic exact manifest' in row['label'] for row in first['rows']));self.assertFalse(first['weights_loaded']);self.assertFalse(first['images_loaded']);self.assertTrue(first['unknown_unrecorded_dependencies']);self.assertEqual(self.store.count('JOB'),0)

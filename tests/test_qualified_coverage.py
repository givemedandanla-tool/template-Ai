"""Purpose-specific descriptive counts with actual source/alias/current-role boundaries."""
import unittest
from pathlib import Path
from unittest.mock import patch
import test_trusted_samples as fixture
import test_noise_authoring as noise_fixture
import test_quality_gold_sets as gold_fixture
from training_fixture import source_work
from template_ai.qualified_coverage import QualifiedCoverage
from template_ai.quality_gold import QualityGold
from template_ai.quality_sets import QualitySets

class QualifiedCoverageTests(unittest.TestCase):
    setUp=fixture.TrustedSamplesTests.setUp
    def report(self,**kwargs):return QualifiedCoverage(self.library).report(**kwargs)
    def sample(self,work=None):return fixture.admitted(self.store,work or self.work)
    def test_default_excludes_pending_and_independent_holdout_and_preserves_overlapping_unknown_facets(self):
        pending=self.report();self.assertEqual(pending['counts']['currently_verified_occurrences'],0);self.assertEqual(self.report(collection='CANDIDATE_PENDING')['counts']['matching_record_occurrences'],1)
        sample=self.sample();report=self.report();self.assertEqual(report['counts']['currently_verified_occurrences'],1);self.assertEqual(report['counts']['distinct_artworks'],1);self.assertEqual(report['facets']['size']['90×54mm'],[self.work['id']]);self.assertEqual(report['facets']['people']['1'],[self.work['id']]);self.assertIn('UNKNOWN',report['facets']['logo']);self.assertFalse(report['quality_pass_claim']);self.assertFalse(report['supplementation']);self.assertFalse(report['automatic_training'])
        self.store.create_dataset(self.store.dataset_plan('Reserved geometry source',[dict(sample_id=sample['id'],role='HOLDOUT')]),'Reviewer',True);self.assertEqual(self.report()['counts']['currently_verified_occurrences'],0)
    def test_same_byte_aliases_count_two_sources_but_one_exact_content_and_label_weight(self):
        original=self.sample()
        legacy=dict(original);legacy.pop('source_byte_size')
        with self.store.transaction():self.store._write('SAMPLE',legacy['id'],legacy,legacy['revision'],'synthetic_legacy_admission_with_real_source_stat')
        source,work=source_work(self.library,self.root,'alias.svg');noise_fixture.confirmed(self.store,work);self.sample(work);report=self.report()
        self.assertEqual(report['counts']['distinct_source_files'],2);self.assertEqual(report['counts']['distinct_artworks'],2);self.assertEqual(report['counts']['exact_content_groups'],1);self.assertEqual(report['counts']['deduplicated_approved_label_weights'],1);self.assertNotEqual(source['id'],self.source['id'])
    def test_exact_manifest_and_development_validation_do_not_become_trainable_totals(self):
        sample=self.sample();dataset=self.store.create_dataset(self.store.dataset_plan('Exact validation manifest',[dict(sample_id=sample['id'],role='VALIDATION')]),'Reviewer',True)
        self.assertEqual(self.report()['counts']['currently_verified_occurrences'],0);validation=self.report(collection='VALIDATION');self.assertEqual(validation['roles'],{'VALIDATION':1});exact=self.report(collection='EXACT_DATASET',dataset_id=dataset['id']);self.assertEqual(exact['counts']['currently_verified_occurrences'],1);self.assertEqual(exact['collection_label'],'Exact validation manifest');self.assertEqual(self.store.get('DATASET',dataset['id']),dataset)
    def test_saved_snapshot_keeps_old_counts_while_current_revoked_or_missing_source_is_excluded(self):
        sample=self.sample();before=self.report();identity=before['snapshot_id'];self.store.transition_sample(self.store.sample_transition_plan(sample['id'],'REVOKE'),'Reviewer','Permission changed',True);after=self.report();self.assertEqual(after['counts']['currently_verified_occurrences'],0)
        historical=QualifiedCoverage(self.library).historical(identity);self.assertEqual(historical['snapshot']['counts']['currently_verified_occurrences'],1);self.assertFalse(historical['current_eligibility_claim']);self.assertTrue(historical['requires_recalculation']);self.assertEqual(self.report(collection='EXCLUDED')['counts']['matching_record_occurrences'],1)
    def test_counts_do_not_load_source_images_models_or_create_training_and_readonly_option_is_real(self):
        self.sample();epoch=self.store.epoch
        with patch('template_ai.trusted_samples.healthy_source',side_effect=AssertionError('No rasterization')),patch('template_ai.semantic_learning.CharacterModel',side_effect=AssertionError('No model loading')):report=self.report(save_snapshot=False)
        self.assertEqual(report['counts']['currently_verified_occurrences'],1);self.assertEqual(self.store.epoch,epoch);self.assertFalse(report['images_loaded']);self.assertFalse(report['model_weights_loaded']);self.assertEqual(self.store.count('AUTO_JOB'),0)
        with self.assertRaises(ValueError):self.report(offset=-1)
        with self.assertRaises(ValueError):self.report(collection='SUPPLEMENTATION')
    def test_independent_gold_members_are_separate_and_exposure_is_not_new_quality_evidence(self):
        self.gold=QualityGold(self.library);gold=self.gold.confirm(gold_fixture.QualityGoldSetTests.plan(self),'Reviewer',True);sets=QualitySets(self.library);dataset=sets.create(sets.plan('Actual quality holdout',[gold['id']],True,True,'Reviewed whole source'),'Reviewer',True)
        report=self.report(collection='QUALITY_HOLDOUT');self.assertEqual(report['counts']['currently_verified_occurrences'],1);self.assertEqual(report['roles'],{'HOLDOUT':1});self.assertEqual(self.report()['counts']['currently_verified_occurrences'],0)
        with self.store.transaction():self.store._write('HOLDOUT_EXPOSED',dataset['id'],dict(reason='Actual answer disclosure receipt'),0,'synthetic_answer_disclosure')
        exposed=self.report(collection='QUALITY_HOLDOUT');self.assertEqual(exposed['counts']['exposed_or_consumed_holdout_members'],1);self.assertFalse(exposed['quality_pass_claim']);self.assertTrue(exposed['independence_unknown'])

    def test_51_approved_authorization_versions_page50_without_inflating_one_work_label_weight(self):
        for index in range(51):
            rights=dict(fixture.RIGHTS,reference='Synthetic explicit authorization version '+str(index));plan=self.store.sample_approval_plan(self.work['id'],rights);self.store.approve_sample(plan,self.store.source_proof(self.work['id']),'Reviewer',True)
        first=self.report();tail=self.report(offset=50);self.assertEqual(first['roster_total'],51);self.assertEqual(first['counts']['scanned_record_occurrences'],50);self.assertEqual(tail['counts']['scanned_record_occurrences'],1);self.assertFalse(first['scan_complete']);self.assertEqual(first['counts']['distinct_source_files'],1);self.assertEqual(first['counts']['distinct_artworks'],1);self.assertEqual(first['counts']['deduplicated_approved_label_weights'],1);self.assertEqual(self.store.count('AUTO_JOB'),0)

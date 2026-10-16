"""Actual persisted source-analysis receipts, never manually typed prediction authority."""
import copy,unittest,json
import test_automatic_training as fixture
from template_ai.trusted_sample_pool import TrustedSamplePool

class TrustedSamplePredictionTests(unittest.TestCase):
    setUp=fixture.AutomaticTrainingTests.setUp
    tearDown=fixture.AutomaticTrainingTests.tearDown
    job=fixture.AutomaticTrainingTests.job
    run_job=fixture.AutomaticTrainingTests.run_job
    def test_real_auto_source_receipt_is_bound_to_manual_correction_without_training(self):
        result=self.run_job(self.job());source=self.library.source(result['items'][0]['source_id']);work=self.library.artworks(source['id'])[0];store=self.service.store;pool=TrustedSamplePool(self.library);facts=store.facts(work['id']);original=copy.deepcopy(facts)
        self.assertEqual(store.count('SAMPLE_CANDIDATE'),0);observations=copy.deepcopy(facts['observations']);observations[0]['prior_prediction']='User reported another unproven result';saved=store.save_facts(work['id'],observations,facts['revision'],work['revision']);candidate=store.records('SAMPLE_CANDIDATE')[0];comparison=pool.comparison(candidate['id'])
        self.assertIsNotNone(comparison['actual_AI_prediction_version']);self.assertEqual(comparison['actual_AI_prediction_version']['observations'],original['observations']);self.assertEqual(comparison['actual_prediction_reference']['source_hash'],source['hash']);self.assertEqual(comparison['actual_prediction_reference']['artwork_revision'],1)
        self.assertEqual(comparison['user_supplied_prior_predictions'][0]['prediction'],'User reported another unproven result');self.assertFalse(comparison['model_prediction_is_gold']);self.assertEqual(store.count('SAMPLE'),0);self.assertTrue(pool.detail(candidate['id'])['errors'])
        raw=json.dumps(candidate,ensure_ascii=False);self.assertNotIn('User reported another',raw)

    def test_confirming_actual_source_proposal_collects_candidate_once_and_changed_receipt_loses_authority(self):
        result=self.run_job(self.job());source=self.library.source(result['items'][0]['source_id']);work=self.library.artworks(source['id'])[0];store=self.service.store;pool=TrustedSamplePool(self.library);facts=store.facts(work['id'])
        confirmed=store.confirm_facts(work['id'],[o['id'] for o in facts['observations']],facts['revision'],facts['pins'],store.source_proof(work['id']),'Synthetic human source reviewer',True);self.assertEqual(store.count('SAMPLE_CANDIDATE'),1);candidate=store.records('SAMPLE_CANDIDATE')[0];self.assertIsNotNone(pool.comparison(candidate['id'])['actual_AI_prediction_version'])
        store.confirm_facts(work['id'],[o['id'] for o in facts['observations']],confirmed['revision'],confirmed['pins'],store.source_proof(work['id']),'Synthetic human source reviewer',True);self.assertEqual(store.count('SAMPLE_CANDIDATE'),1)
        with store.transaction():
            history=store.db.execute("SELECT after_json FROM training_history WHERE kind='FACTS' AND id=? AND revision=1",(work['id'],)).fetchone();changed=json.loads(history[0]);changed['observations'][0]['text']='Injected changed prediction receipt';store.db.execute("UPDATE training_history SET after_json=? WHERE kind='FACTS' AND id=? AND revision=1",(json.dumps(changed),work['id']))
        comparison=pool.comparison(candidate['id']);self.assertIsNone(comparison['actual_AI_prediction_version']);self.assertIn('UNKNOWN',comparison['prior_AI_prediction']);self.assertEqual(store.count('SAMPLE'),0)

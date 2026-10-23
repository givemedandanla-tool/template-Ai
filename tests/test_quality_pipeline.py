import unittest
from unittest.mock import patch
import test_quality_gold_sets as fixtures
from template_ai.quality_pipeline import QualityPipelines


class QualityPipelineTests(unittest.TestCase):
    setUp=fixtures.QualityGoldSetTests.setUp
    def service(self):return QualityPipelines(self.library)

    def test_actual_source_pipeline_predicts_without_reading_holdout_facts_or_writing_business_rows(self):
        service=self.service();record=service.freeze('Actual QA vector parser',None,'Synthetic operator',True);before=self.store.epoch
        with patch.object(service.store,'facts',side_effect=AssertionError('holdout gold read during prediction')):
            result=service.predict_source(record['id'],self.source['id'])
        self.assertEqual(result['source_hash'],self.source['hash']);self.assertTrue(result['predictions']);self.assertIn('ACTUAL_EXECUTED',result['prediction_origin']);self.assertIsNone(result['quality_pass'])
        self.assertEqual(self.store.epoch,before);self.assertEqual(self.library.db.execute('SELECT count(*) FROM artworks').fetchone()[0],1);self.assertEqual(self.library.templates(),[])
        self.assertFalse(result['capabilities']['ocr_executed']);self.assertFalse(result['capabilities']['noise_rules_applied_using_holdout_gold'])

    def test_typed_model_label_cannot_impersonate_an_installed_model_or_quality_pass(self):
        with self.assertRaises(ValueError):self.service().freeze('Not a real model','typed-gpt-model-label','Reviewer',True)
        self.assertEqual(self.store.count('QUALITY_PIPELINE'),0)

    def test_exact_actual_environment_change_invalidates_frozen_pipeline_and_blocks_execution(self):
        service=self.service();record=service.freeze('Actual QA pipeline',None,'Reviewer',True)
        with patch('template_ai.quality_pipeline.font_environment',return_value=dict(complete=False,reason='SYNTHETIC_TEST_ENVIRONMENT_CHANGED')):
            self.assertFalse(service.validity(record['id'])['valid'])
            with self.assertRaises(ValueError):service.predict_source(record['id'],self.source['id'])
        self.assertEqual(self.store.get('QUALITY_PIPELINE',record['id']),record)

    def test_source_failure_does_not_become_empty_prediction_success(self):
        service=self.service();record=service.freeze('Actual QA pipeline',None,'Reviewer',True)
        from pathlib import Path
        Path(self.source['original_path']).unlink()
        with self.assertRaisesRegex(ValueError,'檔案分母'):service.predict_source(record['id'],self.source['id'])

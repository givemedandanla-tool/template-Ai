"""Actual selected-text model reconstruction and purpose withdrawal boundaries."""
import json,unittest
from unittest.mock import patch
import test_semantic_learning as fixture
from template_ai.trusted_sample_pool import TrustedSamplePool

class TrustedSemanticPrivacyTests(unittest.TestCase):
    setUp=fixture.SemanticLearningTests.setUp
    work=fixture.SemanticLearningTests.work
    def test_actual_trained_model_is_blocked_by_semantic_source_stop_but_not_geometry_stop(self):
        model=self.service.train(self.service.plan(self.roles),'Reviewer',True);self.assertIsNotNone(self.service.checked_model(model['id'])[1]);pool=TrustedSamplePool(self.library)
        pool.stop_use(pool.restriction_plan(self.train['id'],['GEOMETRY_TRAINING_LOCAL'],'STOP_USE',7),'Rights reviewer',True)
        self.assertIsNotNone(self.service.checked_model(model['id'])[1])
        pool.stop_use(pool.restriction_plan(self.train['id'],['SEMANTIC_CLASSIFICATION_LOCAL'],'STOP_USE',7),'Rights reviewer',True)
        with self.assertRaisesRegex(ValueError,'用途已停止'):self.service.checked_model(model['id'])
        self.assertEqual(self.service.store.get('SEMANTIC_MODEL',model['id']),model)

    def test_selected_model_text_and_all_its_history_are_logically_redacted_without_decontamination_claim(self):
        model=self.service.train(self.service.plan(self.roles),'Reviewer',True);subject=next(x['text'] for x in model['plan']['examples'] if x['role']=='TRAIN');pool=TrustedSamplePool(self.library)
        pool.stop_use(pool.restriction_plan(self.train['id'],['SEMANTIC_CLASSIFICATION_LOCAL'],'REQUEST_LOCAL_ERASURE',0),'Rights reviewer',True)
        plan=pool.redaction_plan(self.train['id'],[dict(kind='SEMANTIC_MODEL',id=model['id'])]);result=pool.redact_training_copies(plan,'Privacy operator',True)
        self.assertNotIn(subject,json.dumps(self.service.store.get('SEMANTIC_MODEL',model['id']),ensure_ascii=False));self.assertNotIn(subject,json.dumps(self.service.store.history('SEMANTIC_MODEL',model['id']),ensure_ascii=False));self.assertFalse(result['receipt']['model_decontaminated'])
        self.assertEqual(self.service.store.get('SEMANTIC_MODEL',model['id'])['weights_digest'],model['weights_digest'])
        with self.assertRaises(ValueError):self.service.checked_model(model['id'])
        self.assertTrue(self.service.store.facts(self.train['id'])['observations'][0]['text'])

    def test_redaction_requires_actual_matching_source_and_prior_purpose_stop(self):
        model=self.service.train(self.service.plan(self.roles),'Reviewer',True);pool=TrustedSamplePool(self.library)
        with self.assertRaisesRegex(ValueError,'先明確停止'):pool.redaction_plan(self.train['id'],[dict(kind='SEMANTIC_MODEL',id=model['id'])])
        plan=pool.restriction_plan(self.train['id'],['SEMANTIC_CLASSIFICATION_LOCAL'],'STOP_USE',1)
        with self.assertRaises(ValueError):pool.stop_use(plan,'Reviewer',False)
        self.assertEqual(self.service.store.count('SOURCE_USE_RESTRICTION'),0)

import copy
import unittest
from unittest.mock import patch
import test_quality_gold_sets as fixtures
import test_quality_domains as domain_fixture
from template_ai.customers import CustomerStore
from template_ai.model import Template, Slot, Rect
from template_ai.quality_mapping import catalog, predict, truth
from template_ai.quality_pipeline import QualityPipelines
from template_ai.quality_domains import evaluate_source


class QualityMappingTests(unittest.TestCase):
    setUp=fixtures.QualityGoldSetTests.setUp

    def configured(self):
        self.customers=CustomerStore(self.library)
        template=Template('Synthetic existing catalog style',90,54,[Slot('name','p1',Rect(1,1,20,5))]);self.library.save_template(template)
        self.customer=self.customers.create('example','Synthetic Catalog Identity',[dict(owner='p1',kind='name',value='Synthetic Catalog')],template.id,True)
        config=dict(code_pattern=r'(?P<code>.+)',maximum_size_error_mm=.02,customer_ids=[self.customer['id']])
        evidence=dict(customer_id=self.customer['id'],style_id=self.customer['styles'][0]['id'],review_reason='Manually reviewed synthetic exact catalog mapping')
        return config,evidence

    def test_actual_source_only_mapping_uses_frozen_catalog_and_never_reads_facts(self):
        config,evidence=self.configured();service=QualityPipelines(self.library)
        pipeline=service.freeze('Actual catalog lookup pipeline',None,'Synthetic reviewer',True,mapping_config=config)
        before=self.library.db.total_changes
        with patch.object(service.store,'facts',side_effect=AssertionError('No holdout facts as inputs')):
            result=service.predict_source(pipeline['id'],self.source['id'])
        self.assertEqual(result['predictions'][0]['mapping_prediction']['selected']['customer_id'],self.customer['id'])
        self.assertEqual(self.library.db.total_changes,before)

    def test_multiple_same_size_styles_abstain_instead_of_guessing_exact_version(self):
        config,evidence=self.configured();template=Template('Second exact style',90,54,[Slot('name','p1',Rect(2,2,20,5))]);self.library.save_template(template)
        self.customers.link_style(self.customers.get(self.customer['id']),template.id,True)
        result=predict(self.source,dict(work_width=90,work_height=54),catalog(self.library,config))
        self.assertEqual(len(result['candidates']),2);self.assertIsNone(result['selected'])

    def test_gold_mapping_is_separate_explicit_manual_truth_and_stales_with_catalog(self):
        config,evidence=self.configured();base=fixtures.QualityGoldSetTests.plan(self)
        plan=self.gold.plan(self.work['id'],base['rights'],base['domain_truth'],base['reason'],base['evidence'],mapping_truth=evidence)
        gold=self.gold.confirm(plan,'Synthetic reviewer',True)
        self.assertTrue(self.gold.validity(gold['id'])['valid'])
        self.library.db.execute('UPDATE customers SET revision=revision+1 WHERE id=?',(self.customer['id'],));self.library.db.commit()
        self.assertFalse(self.gold.validity(gold['id'])['valid'])

    def test_actual_frozen_pipeline_invalid_after_candidate_catalog_changes(self):
        config,evidence=self.configured();service=QualityPipelines(self.library);pipeline=service.freeze('Catalog version',None,'Synthetic reviewer',True,mapping_config=config)
        self.library.db.execute('UPDATE customers SET revision=revision+1 WHERE id=?',(self.customer['id'],));self.library.db.commit()
        self.assertFalse(service.validity(pipeline['id'])['valid'])

    def test_wrong_customer_is_critical_and_abstention_remains_false_negative(self):
        config,evidence=self.configured();oracle=truth(self.library,evidence)
        gold,prediction,policy=domain_fixture.QualityDomainTests.fixture(self);gold['mapping_truth']=oracle
        work=prediction['predictions'][0];wrong={key:oracle[key] for key in ('customer_id','style_id','template_id','template_hash')};wrong['customer_id']='different-customer'
        work['mapping_prediction']=dict(state='UNIQUE_SOURCE_CODE_AND_SIZE_CANDIDATE',selected=wrong)
        bad=evaluate_source([gold],prediction,policy,complete_source_gold=True)
        self.assertEqual(bad['critical_errors']['customer_owner_mismatch'],1)
        work['mapping_prediction']['selected']=None
        abstained=evaluate_source([gold],prediction,policy,complete_source_gold=True)
        self.assertEqual(abstained['domains']['customer_style_mapping']['metrics']['fn'],1)
        self.assertEqual(abstained['domains']['customer_style_mapping']['metrics']['recall'],0)

    def related_split(self):
        from training_fixture import source_work
        from test_noise_authoring import confirmed
        config,evidence=self.configured()
        source,work=source_work(self.library,self.root,'independent-bytes.svg',note_text='Different design bytes, same confirmed customer family')
        confirmed(self.store,work)
        base=fixtures.QualityGoldSetTests.plan(self,work)
        gold=self.gold.confirm(self.gold.plan(work['id'],base['rights'],base['domain_truth'],base['reason'],base['evidence'],mapping_truth=evidence),'Reviewer',True)
        plain=self.gold.confirm(fixtures.QualityGoldSetTests.plan(self),'Reviewer',True)
        dataset=self.sets.create(self.sets.plan('Initially unlinked holdout',[plain['id']],True,True,'Prior independence review'),'Reviewer',True)
        with self.store.transaction():self.store._write('GROUP_ROLE',source['hash'],dict(role='TRAIN'),0,'synthetic_preexisting_training_role')
        base=fixtures.QualityGoldSetTests.plan(self)
        plan=self.gold.plan(self.work['id'],base['rights'],base['domain_truth'],base['reason'],base['evidence'],mapping_truth=evidence)
        return dataset,plan

    def test_quality_only_mapping_truth_connects_customer_family_and_invalidates_old_split(self):
        dataset,plan=self.related_split()
        self.gold.confirm(plan,'Reviewer',True)
        self.assertIsNotNone(self.store.get('HOLDOUT_EXPOSED',dataset['id']))
        self.assertFalse(self.sets.validity(dataset['id'])['valid'])
        exists=self.library.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='customer_source_associations'").fetchone()
        if exists:self.assertEqual(self.library.db.execute('SELECT count(*) FROM customer_source_associations').fetchone()[0],0)

    def test_late_mapping_leakage_audit_failure_rolls_back_gold_and_holdout_invalidation(self):
        import sqlite3
        dataset,plan=self.related_split();before=self.store.count('QUALITY_GOLD');event=self.library.event
        def failed(identity,action):
            if action=='training_quality_holdout_invalidated_by_group_leakage':raise sqlite3.OperationalError('synthetic disk full on correlated split invalidation')
            return event(identity,action)
        with patch.object(self.library,'event',side_effect=failed):
            with self.assertRaises(sqlite3.OperationalError):self.gold.confirm(plan,'Reviewer',True)
        self.assertEqual(self.store.count('QUALITY_GOLD'),before)
        self.assertIsNone(self.store.get('HOLDOUT_EXPOSED',dataset['id']))

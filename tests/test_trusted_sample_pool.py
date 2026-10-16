"""Actual correction/admission transactions and source-scoped training-copy privacy."""
import copy,json,unittest
from unittest.mock import patch
import test_trusted_samples as fixture
import test_noise_authoring as noise_fixture
from training_fixture import source_work
from template_ai.trusted_sample_pool import TrustedSamplePool,CANDIDATE
from template_ai.quality_gold import QualityGold
from template_ai.quality_sets import QualitySets
import test_quality_gold_sets as gold_fixture


class TrustedSamplePoolTests(unittest.TestCase):
    setUp=fixture.TrustedSamplesTests.setUp
    def pool(self):return TrustedSamplePool(self.library)
    def candidate(self,work=None):
        wid=(work or self.work)['id'];return next(x for x in self.store.records(CANDIDATE) if x['work_id']==wid)
    def approve(self,work=None):
        candidate=self.candidate(work);pool=self.pool();plan=pool.batch_plan([dict(id=candidate['id'],action='APPROVE',high_risk_reviewed=True)],fixture.RIGHTS)
        self.assertEqual(plan['items'][0]['errors'],[]);return pool.confirm_batch(plan,'Synthetic reviewer',True)[0]

    def test_fact_save_collects_refs_without_admission_and_confirmed_correction_keeps_before_version(self):
        pool=self.pool();initial=self.candidate();self.assertEqual(initial['state'],'COLLECTED');self.assertEqual(self.store.count('SAMPLE'),0)
        obs=copy.deepcopy(self.facts['observations']);obs[0]['prior_prediction']='User-reported incorrect diagnostic'
        saved=self.store.save_facts(self.work['id'],obs,self.facts['revision'],self.work['revision'])
        rows=self.store.records(CANDIDATE);self.assertEqual(len(rows),2);new=next(x for x in rows if x['facts_revision']==saved['revision'])
        comparison=pool.comparison(new['id']);self.assertEqual(new['correction_kind'],'CONFIRMED_HUMAN_CORRECTION');self.assertEqual(new['previous_facts_revision'],self.facts['revision'])
        self.assertIn('USER_REPORTED',comparison['user_supplied_prior_predictions'][0]['evidence']);self.assertFalse(comparison['model_prediction_is_gold'])
        self.assertNotIn('User-reported',json.dumps(new));self.assertTrue(pool.detail(new['id'])['errors']);self.assertEqual(self.store.count('AUTO_JOB'),0);self.assertEqual(self.library.templates(),[])

    def test_batch_low_risk_reuses_confirmed_facts_but_requires_explicit_confirmation(self):
        pool=self.pool();candidate=self.candidate();plan=pool.batch_plan([dict(id=candidate['id'],action='APPROVE')],fixture.RIGHTS)
        self.assertEqual(plan['items'][0]['errors'],[])
        plan=pool.batch_plan([dict(id=candidate['id'],action='APPROVE',high_risk_reviewed=True)],fixture.RIGHTS)
        with self.assertRaises(ValueError):pool.confirm_batch(plan,'Reviewer',False)
        result=pool.confirm_batch(plan,'Reviewer',True)[0];self.assertEqual(result['state'],'ADMITTED');self.assertEqual(self.store.sample_state(result['sample_id']),'APPROVED');self.assertEqual(self.store.count('SEMANTIC_MODEL'),0)

    def test_changed_confirmation_invalidates_batch_and_late_audit_rolls_back_all_items(self):
        source,other=source_work(self.library,self.root,'other.svg',note_text='Different source evidence');noise_fixture.confirmed(self.store,other)
        pool=self.pool();first=self.candidate();second=self.candidate(other)
        items=[dict(id=first['id'],action='DEFER'),dict(id=second['id'],action='APPROVE',high_risk_reviewed=True)];plan=pool.batch_plan(items,fixture.RIGHTS);before=self.store.epoch;original=self.library.event
        def fail(identity,action):
            if action=='training_correction_candidate_approve':raise OSError('Injected late audit failure')
            return original(identity,action)
        with patch.object(self.library,'event',side_effect=fail):
            with self.assertRaises(OSError):pool.confirm_batch(plan,'Reviewer',True)
        self.assertEqual(self.store.epoch,before);self.assertEqual(self.store.get(CANDIDATE,first['id'])['state'],'COLLECTED');self.assertEqual(self.store.count('SAMPLE'),0)
        self.store.revoke_facts(other['id'],self.store.facts(other['id'])['revision'],'Changed source review')
        with self.assertRaises(ValueError):pool.confirm_batch(plan,'Reviewer',True)
        self.assertEqual(self.store.count('SAMPLE'),0)

    def test_equal_bytes_aliases_keep_sources_but_conflicting_current_truth_blocks_both(self):
        source,other=source_work(self.library,self.root,'alias.svg');facts=noise_fixture.confirmed(self.store,other);pool=self.pool()
        self.assertEqual(pool.conflicts(self.work['id'])['conflicting_work_ids'],[]);self.assertNotEqual(source['id'],self.source['id']);self.assertEqual(source['hash'],self.source['hash'])
        obs=copy.deepcopy(facts['observations']);obs[0]['text']='Conflicting independently confirmed label';saved=self.store.save_facts(other['id'],obs,facts['revision'],other['revision']);self.store.confirm_facts(other['id'],[o['id'] for o in obs],saved['revision'],saved['pins'],self.store.source_proof(other['id']),'Second reviewer',True)
        self.assertEqual(pool.conflicts(self.work['id'])['conflicting_work_ids'],[other['id']]);self.assertEqual(pool.conflicts(other['id'])['conflicting_work_ids'],[self.work['id']]);self.assertTrue(self.store.sample_approval_plan(self.work['id'],fixture.RIGHTS)['errors'])

    def test_actual_quality_holdout_cannot_be_admitted_through_new_or_legacy_flow(self):
        gold_service=QualityGold(self.library);self.gold=gold_service;plan=gold_fixture.QualityGoldSetTests.plan(self);gold=gold_service.confirm(plan,'Gold reviewer',True);sets=QualitySets(self.library);sets.create(sets.plan('Actual reserved source',[gold['id']],True,True,'Actual source-family review'),'Reviewer',True)
        pool=self.pool();plan=pool.batch_plan([dict(id=self.candidate()['id'],action='APPROVE',high_risk_reviewed=True)],fixture.RIGHTS)
        self.assertTrue(plan['items'][0]['errors']);self.assertTrue(self.store.sample_approval_plan(self.work['id'],fixture.RIGHTS)['errors']);self.assertEqual(self.store.count('SAMPLE'),0)

    def test_stop_geometry_use_blocks_alias_datasets_without_changing_original_sources(self):
        admitted=self.approve();sample=self.store.get('SAMPLE',admitted['sample_id']);dataset=self.store.create_dataset(self.store.dataset_plan('Exact approved version',[dict(sample_id=sample['id'],role='TRAIN')]),'Reviewer',True)
        pool=self.pool();before=self.library.artwork(self.work['id']);restriction=pool.restriction_plan(self.work['id'],['GEOMETRY_TRAINING_LOCAL'],'STOP_USE',30);rows=pool.stop_use(restriction,'Privacy reviewer',True)
        source,alias=source_work(self.library,self.root,'stopped-alias.svg');noise_fixture.confirmed(self.store,alias);self.assertTrue(self.store.sample_approval_plan(alias['id'],fixture.RIGHTS)['errors']);self.assertNotEqual(source['id'],self.source['id'])
        self.assertEqual(self.store.sample_state(sample['id']),'RESTRICTED_USE');self.assertTrue(self.store.dataset_plan('Blocked new version',[dict(sample_id=sample['id'],role='TRAIN')])['errors']);self.assertEqual(self.store.get('DATASET',dataset['id']),dataset);self.assertEqual(self.library.artwork(self.work['id']),before);self.assertFalse(rows[0]['model_decontaminated']);self.assertEqual(self.store.sample_usage_impact(sample['id'])['dataset_ids'],[dataset['id']])

    def test_explicit_local_copy_redaction_removes_subject_text_from_all_sample_history(self):
        row=self.approve();sid=row['sample_id'];sample=self.store.get('SAMPLE',sid);subject=sample['positive_labels'][0]['text'];facts=copy.deepcopy(self.store.facts(self.work['id']));pool=self.pool()
        pool.stop_use(pool.restriction_plan(self.work['id'],['GEOMETRY_TRAINING_LOCAL'],'REQUEST_LOCAL_ERASURE',0),'Privacy reviewer',True)
        plan=pool.redaction_plan(self.work['id'],[dict(kind='SAMPLE',id=sid)]);result=pool.redact_training_copies(plan,'Privacy reviewer',True)
        self.assertNotIn(subject,json.dumps(self.store.get('SAMPLE',sid),ensure_ascii=False));self.assertNotIn(subject,json.dumps(self.store.history('SAMPLE',sid),ensure_ascii=False));self.assertEqual(self.store.facts(self.work['id']),facts)
        receipt=result['receipt'];self.assertFalse(receipt['external_backups_deleted']);self.assertFalse(receipt['filesystem_secure_erasure']);self.assertFalse(receipt['model_decontaminated']);self.assertTrue(receipt['original_payload_hashes_retained'])

    def test_redaction_late_receipt_failure_restores_original_text_and_history(self):
        row=self.approve();sid=row['sample_id'];pool=self.pool();pool.stop_use(pool.restriction_plan(self.work['id'],['GEOMETRY_TRAINING_LOCAL'],'REQUEST_LOCAL_ERASURE',7),'Reviewer',True);plan=pool.redaction_plan(self.work['id'],[dict(kind='SAMPLE',id=sid)]);before=self.store.get('SAMPLE',sid);history=self.store.history('SAMPLE',sid);original=self.library.event
        def fail(identity,action):
            if action=='training_training_copy_minimization_receipt':raise OSError('Receipt persistence failed')
            return original(identity,action)
        with patch.object(self.library,'event',side_effect=fail):
            with self.assertRaises(OSError):pool.redact_training_copies(plan,'Reviewer',True)
        self.assertEqual(self.store.get('SAMPLE',sid),before);self.assertEqual(self.store.history('SAMPLE',sid),history);self.assertEqual(self.store.count('TRAINING_PRIVACY_REDACTION'),0)

    def test_directory_is_bounded_and_pending_defer_reject_are_distinct_from_training(self):
        pool=self.pool();row=self.candidate();self.assertEqual(pool.directory()['scanned'],1);self.assertFalse(pool.directory()['images_loaded']);self.assertEqual(pool.directory(query='unmatched-source-token')['rows'],[])
        plan=pool.batch_plan([dict(id=row['id'],action='DEFER')],{});pool.confirm_batch(plan,'Reviewer',True);self.assertEqual(pool.directory()['rows'][0]['state'],'DEFERRED')
        plan=pool.batch_plan([dict(id=row['id'],action='REJECT')],{});pool.confirm_batch(plan,'Reviewer',True);self.assertEqual(pool.directory()['rows'],[]);self.assertEqual(self.store.count('SAMPLE'),0)
        with self.assertRaises(ValueError):pool.directory(offset=-1)

    def test_actual_two_person_source_requires_individual_high_risk_review(self):
        import types
        import test_semantic_learning as semantic_fixture
        case=types.SimpleNamespace(root=self.root,library=self.library,service=types.SimpleNamespace(store=self.store))
        work=semantic_fixture.SemanticLearningTests.work(case,'two-human-source',[('name','Alex Synthetic'),('phone','+1 202 555 0101'),('name','Taylor Synthetic'),('phone','+1 202 555 0102')])
        payload=copy.deepcopy(work['payload'])
        for slot in payload['slots'][2:]:slot['owner']='p2'
        updated=self.library.save_artwork(work['id'],payload,work['revision']);facts=self.store.facts(work['id']);saved=self.store.save_facts(work['id'],facts['observations'],facts['revision'],updated['revision']);self.store.confirm_facts(work['id'],[o['id'] for o in saved['observations']],saved['revision'],saved['pins'],self.store.source_proof(work['id']),'Human source reviewer',True)
        candidate=next(c for c in self.store.records(CANDIDATE) if c['work_id']==work['id'] and c['facts_revision']==saved['revision']);pool=self.pool();self.assertEqual(pool.detail(candidate['id'])['risk'],'HIGH');plan=pool.batch_plan([dict(id=candidate['id'],action='APPROVE')],fixture.RIGHTS)
        self.assertTrue(any('高風險' in error for error in plan['items'][0]['errors']))
        with self.assertRaises(ValueError):pool.confirm_batch(plan,'Reviewer',True)
        self.assertEqual(self.store.count('SAMPLE'),0)

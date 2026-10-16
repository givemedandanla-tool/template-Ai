import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.quality_gold import QualityGold,DOMAINS,USE
from template_ai.quality_sets import QualitySets
from training_fixture import source_work
from test_noise_authoring import confirmed


class QualityGoldSetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.library=Library(self.root/'data');self.addCleanup(self.library.close);self.store=TrainingStore(self.library);self.gold=QualityGold(self.library);self.sets=QualitySets(self.library)
        self.source,self.work=source_work(self.library,self.root);confirmed(self.store,self.work)

    def plan(self,work=None):return self.gold.plan((work or self.work)['id'],dict(basis='OWNED',reference='Synthetic authored QA source,local evaluation only',use=USE),{domain:'MANUALLY_VERIFIED' if domain in ('field_types','source_readability') else 'INSUFFICIENT_EVIDENCE' for domain in DOMAINS},'Manual source/facts comparison','Original SVG page1 exact object regions;no native Illustrator certification')
    def approved(self,work=None):return self.gold.confirm(self.plan(work),'Synthetic Reviewer',True)

    def test_geometry_rights_or_unconfirmed_ai_candidates_cannot_be_gold(self):
        plan=self.plan();wrong=dict(plan['rights'],use='GEOMETRY_TRAINING_LOCAL')
        with self.assertRaisesRegex(ValueError,'另行明列'):self.gold.plan(self.work['id'],wrong,plan['domain_truth'],'Reason','Evidence')
        facts=self.store.facts(self.work['id']);self.store.save_facts(self.work['id'],facts['observations'],facts['revision'],self.work['revision'])
        with self.assertRaisesRegex(ValueError,'真正人工核對'):self.plan()
        self.assertEqual(self.store.count('QUALITY_GOLD'),0)

    def test_gold_is_local_immutable_reference_and_never_training_admission(self):
        gold=self.approved();self.assertTrue(gold['local_only']);self.assertTrue(gold['immutable']);self.assertFalse(gold['training_admission']);self.assertFalse(gold['model_prediction_is_gold'])
        self.assertEqual(self.store.count('SAMPLE'),0);self.assertEqual(self.store.count('USE_LEDGER'),0);self.assertEqual(len(gold['objects']),5)
        self.assertEqual(next(obj for obj in gold['objects'] if obj['id']=='note')['kind'],'ANNOTATION');self.assertTrue(self.gold.validity(gold['id'])['valid'])

    def test_candidate_model_change_does_not_rewrite_or_invalidate_independent_truth(self):
        gold=self.approved()
        with self.store.transaction():self.store._write('SEMANTIC_ACTIVE','local-text',dict(model_id='candidate-not-gold'),0,'synthetic_candidate_changed')
        self.assertTrue(self.gold.validity(gold['id'])['valid']);self.assertEqual(self.store.get('QUALITY_GOLD',gold['id']),gold)

    def test_stale_fact_cache_and_rights_withdrawal_fail_without_erasing_old_gold(self):
        gold=self.approved();self.gold.withdraw(gold['id'],gold['revision'],'Reviewer','Evaluation permission withdrawn',True)
        with patch('template_ai.quality_gold.healthy_source',side_effect=AssertionError('withdrawn source read')):
            self.assertFalse(self.gold.validity(gold['id'])['valid']);self.assertTrue(self.sets.plan('Withdrawn scope',[gold['id']])['errors'])
        self.assertEqual(self.store.get('QUALITY_GOLD',gold['id']),gold)
        fresh=self.approved();Path(self.library.source(self.source['id'])['svg']).write_text('<svg>changed cache</svg>')
        self.assertFalse(self.gold.validity(fresh['id'])['valid'])

    def test_unreviewed_independence_stays_unknown_even_with_correct_fields(self):
        gold=self.approved();plan=self.sets.plan('Unknown family audit',[gold['id']]);dataset=self.sets.create(plan,'Reviewer',True)
        self.assertFalse(dataset['quality_pass']);self.assertTrue(dataset['manifest']['unreviewed_near_duplicate_independence_unknown']);self.assertFalse(dataset['manifest']['whole_source_gold_complete']);self.assertFalse(dataset['manifest']['cloud_upload_allowed'])
        self.assertTrue(self.sets.validity(dataset['id'])['valid']);self.assertEqual(self.store.get('GROUP_ROLE',self.source['hash'])['role'],'HOLDOUT')

    def test_equal_bytes_aliases_keep_two_files_but_only_one_independent_group(self):
        first=self.approved();source,work=source_work(self.library,self.root,'alias.svg');confirmed(self.store,work);second=self.approved(work)
        plan=self.sets.plan('Exact alias scope',[first['id'],second['id']],True,True,'Reviewed whole sources and related family as one correlated group')
        self.assertEqual(plan['errors'],[]);self.assertEqual((plan['manifest']['file_count'],plan['manifest']['gold_work_count'],plan['manifest']['independent_group_count']),(2,2,1))
        dataset=self.sets.create(plan,'Reviewer',True);self.assertTrue(self.sets.validity(dataset['id'])['valid']);self.assertEqual(self.store.count('SAMPLE'),0)

    def test_train_locked_content_and_duplicate_gold_versions_cannot_be_holdout(self):
        gold=self.approved()
        with self.store.transaction():self.store._write('GROUP_ROLE',self.source['hash'],dict(role='TRAIN'),0,'synthetic_existing_train')
        plan=self.sets.plan('Cannot relabel used content',[gold['id']]);self.assertTrue(plan['errors'])
        with self.assertRaises(ValueError):self.sets.create(plan,'Reviewer',True)
        other=self.approved()
        with self.assertRaisesRegex(ValueError,'不同gold版本'):self.sets.plan('Conflicting gold',[gold['id'],other['id']])

    def test_audit_failure_rolls_back_gold_and_set_role_lock(self):
        plan=self.plan()
        with patch.object(self.library,'event',side_effect=sqlite3.OperationalError('disk full')):
            with self.assertRaises(sqlite3.OperationalError):self.gold.confirm(plan,'Reviewer',True)
        self.assertEqual(self.store.count('QUALITY_GOLD'),0)
        gold=self.approved();plan=self.sets.plan('Atomic set',[gold['id']]);event=self.library.event
        def fail(identity,action):
            if 'quality_set_frozen' in action:raise sqlite3.OperationalError('disk full after group role')
            event(identity,action)
        with patch.object(self.library,'event',side_effect=fail):
            with self.assertRaises(sqlite3.OperationalError):self.sets.create(plan,'Reviewer',True)
        self.assertEqual(self.store.count('QUALITY_SET'),0);self.assertIsNone(self.store.get('GROUP_ROLE',self.source['hash']))

    def test_new_work_after_gold_does_not_disappear_from_full_source_denominator(self):
        gold=self.approved();self.library.create_artwork(self.source['id'],'New source work',self.work['payload'])
        self.assertFalse(self.gold.validity(gold['id'])['valid']);plan=self.sets.plan('Old incomplete gold',[gold['id']],True,True,'Cannot hide new actual work')
        self.assertTrue(plan['errors'])
        with self.assertRaises(ValueError):self.sets.create(plan,'Reviewer',True)

    def test_new_relation_invalidates_quality_set_independence_while_gold_truth_stays_intact(self):
        from template_ai.importer import import_file
        from template_ai.quality_groups import QualityGroups
        gold=self.approved();dataset=self.sets.create(self.sets.plan('Exact holdout',[gold['id']],True,True,'Reviewed current source inventory and family scope'),'Reviewer',True)
        path=self.root/'related-train.svg';path.write_text(Path(self.source['original_path']).read_text()+'\n<!-- related synthetic training design -->');other=self.library.add_source(path,import_file(path,self.library.assets))
        with self.store.transaction():self.store._write('GROUP_ROLE',other['hash'],dict(role='TRAIN'),0,'synthetic_train_role')
        groups=QualityGroups(self.library);plan=groups.link_plan('CONTENT:'+self.source['hash'],'CONTENT:'+other['hash'],'NEAR_DUPLICATE','Source comparison reveals previous split was not independent','Synthetic original source visuals checked')
        groups.confirm_link(plan,'Reviewer',True)
        self.assertTrue(self.gold.validity(gold['id'])['valid']);self.assertFalse(self.sets.validity(dataset['id'])['valid']);self.assertIsNotNone(self.store.get('HOLDOUT_EXPOSED',dataset['id']))
        self.assertEqual(self.store.get('QUALITY_GOLD',gold['id']),gold)

    def test_declared_unparsed_file_without_gold_stays_in_denominator_and_is_not_read(self):
        gold=self.approved();unparsed=self.root/'not-yet-parsed.ai';unparsed.write_bytes(b'unknown source awaiting rights and parsing')
        from template_ai.source_links import verify_source
        reads=[]
        def checked(path,sha):reads.append(str(path));return verify_source(path,sha)
        with patch('template_ai.quality_sets.verify_source',side_effect=checked):plan=self.sets.plan('All declared sources',[gold['id']],True,True,'Reviewed known subset;unparsed remains unresolved',declared_paths=[self.source['original_path'],str(unparsed)])
        manifest=plan['manifest'];self.assertEqual(manifest['file_count'],2);self.assertIn(str(unparsed),manifest['unregistered_or_unparsed_files']);self.assertNotIn(str(unparsed),reads)
        self.assertIsNone(manifest['actual_whole_source_work_count']);self.assertFalse(manifest['whole_source_gold_complete']);self.assertFalse(manifest['independence_scope_ready'])
        dataset=self.sets.create(plan,'Reviewer',True);self.assertTrue(self.sets.validity(dataset['id'])['valid']);self.assertFalse(dataset['quality_pass'])

    def test_all_unparsed_scope_persists_unknown_instead_of_zero_over_zero_quality_pass(self):
        path=self.root/'unregistered.ai';path.write_bytes(b'unparsed')
        plan=self.sets.plan('No readable gold yet',[],declared_paths=[str(path)]);dataset=self.sets.create(plan,'Reviewer',True)
        self.assertEqual((dataset['manifest']['file_count'],dataset['manifest']['gold_object_count']),(1,0));self.assertIsNone(dataset['manifest']['actual_whole_source_work_count']);self.assertFalse(dataset['quality_pass'])
        path.write_bytes(b'changed unparsed version');self.assertFalse(self.sets.validity(dataset['id'])['valid'])

    def test_gold_outside_exact_declared_file_scope_cannot_be_silently_mixed(self):
        gold=self.approved();path=self.root/'different.ai';path.write_bytes(b'unknown')
        plan=self.sets.plan('Wrong scope',[gold['id']],declared_paths=[str(path)]);self.assertTrue(plan['errors'])
        with self.assertRaises(ValueError):self.sets.create(plan,'Reviewer',True)

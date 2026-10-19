"""Actual staged SQLite/model mechanics with authored source fixtures only."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from PySide6.QtWidgets import QApplication

from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.design_learning import CrossWorkLearning, USE
from template_ai.quality_groups import QualityGroups
from training_fixture import source_work
from test_noise_authoring import confirmed
from test_trusted_samples import admitted

APP = QApplication.instance() or QApplication([])


class CrossWorkLearningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.library=Library(self.root/'data')
        self.addCleanup(self.library.db.close);self.store=TrainingStore(self.library)
        self.learning=CrossWorkLearning(self.library);self.samples=[];self.works=[];self.sources=[]
        for i in range(8):
            source,work=source_work(self.library,self.root,name='authored-'+str(i)+'.svg',
                                    note_text='Authored training design '+str(i))
            confirmed(self.store,work);self.samples.append(admitted(self.store,work))
            self.works.append(work);self.sources.append(source)
        self.roles={sample['id']:'TRAIN' if i<6 else 'VALIDATION' if i==6 else 'HOLDOUT'
                    for i,sample in enumerate(self.samples)}
        self.permission=dict(use=USE,actor='Synthetic source author',
            basis='Explicit authored local cross-work-rule fixture use;not a real private corpus')

    def dataset(self):
        return self.learning.freeze_dataset(self.learning.dataset_plan(self.roles,self.permission),
                                            'Synthetic source author',True)

    def model(self):
        return self.learning.train(self.dataset()['id'],'Synthetic source author',approved=True)

    def test_freeze_uses_existing_store_and_pins_roles_without_creating_templates(self):
        plan=self.learning.dataset_plan(self.roles,self.permission)
        with self.assertRaises(ValueError):self.learning.freeze_dataset(plan,'Actor')
        dataset=self.learning.freeze_dataset(plan,'Actor',True)
        self.assertEqual(self.learning.checked_dataset(dataset['id']),dataset)
        self.assertEqual(self.library.templates(),[])
        self.assertEqual(self.store.count('DATASET'),1)
        self.assertEqual(self.store.get('GROUP_ROLE',self.sources[-1]['hash'])['role'],'HOLDOUT')

    def test_geometry_permission_cannot_silently_authorize_new_rule_learning(self):
        with self.assertRaises(ValueError):
            self.learning.dataset_plan(self.roles,dict(self.permission,use='GEOMETRY_TRAINING_LOCAL'))

    def test_cross_file_correlations_cannot_span_dataset_roles(self):
        a,b=self.sources[0],self.sources[-1];groups=QualityGroups(self.library)
        plan=groups.link_plan('CONTENT:'+a['hash'],'CONTENT:'+b['hash'],'NEAR_DUPLICATE',
                             'Authored correlated revisions','Synthetic author source review')
        groups.confirm_link(plan,'Reviewer',True)
        with self.assertRaises(ValueError):self.learning.dataset_plan(self.roles,self.permission)

    def test_train_builds_shared_family_and_profiles_without_individual_templates(self):
        model=self.model()
        self.assertEqual(model['state'],'PENDING')
        self.assertEqual(len(model['artifact']['family_model']['families']),1)
        self.assertEqual(model['artifact']['family_model']['families'][0]['independent_support'],6)
        self.assertTrue(model['artifact']['profile_model']['families'])
        self.assertEqual(self.library.templates(),[])
        self.assertEqual(self.store.count('DESIGN_USE'),8)

    def test_validation_and_holdout_do_not_change_weights_or_become_fake_labels(self):
        model=self.model();weights=model['weights_digest']
        report=self.learning.evaluate_family_descriptors(model['id'])
        self.assertEqual(report['total'],1);self.assertEqual(report['labeled'],0)
        self.learning.evaluate_family_descriptors(model['id'],'HOLDOUT')
        self.assertEqual(self.store.count('DESIGN_HOLDOUT_EXPOSURE'),1)
        self.assertEqual(self.learning.checked_model(model['id'])[0]['weights_digest'],weights)

    def test_activation_is_explicit_preview_only_and_weights_tamper_is_detected(self):
        model=self.model();policy=dict(version='fixture-1',basis='Authored preview mechanism checks',production=False)
        with self.assertRaises(ValueError):self.learning.activate(model['id'],0,'Actor',policy)
        with self.assertRaises(ValueError):self.learning.activate(model['id'],0,'Actor',dict(policy,production=True),True)
        active=self.learning.activate(model['id'],0,'Actor',policy,True)
        self.assertEqual(active['scope'],'EXPLORATORY_PREVIEW_ONLY')
        self.assertEqual(self.learning.active()[1]['state'],'ACTIVE')
        changed=deepcopy(model);changed['artifact']['version']='tampered'
        self.store.db.execute("UPDATE training_records SET payload=? WHERE kind='DESIGN_MODEL' AND id=?",
            (__import__('json').dumps({k:v for k,v in changed.items() if k not in ('id','revision')}),model['id']))
        self.store.db.commit()
        self.assertEqual(self.learning.active()[1]['state'],'STALE')

    def test_new_fact_revision_stales_frozen_model_and_does_not_rewrite_weights(self):
        model=self.model();work=self.works[0];facts=self.store.facts(work['id'])
        self.store.save_facts(work['id'],facts['observations'],facts['revision'],work['revision'])
        with self.assertRaises(ValueError):self.learning.checked_model(model['id'])
        self.assertEqual(self.store.get('DESIGN_MODEL',model['id'])['weights_digest'],model['weights_digest'])

    def test_reopen_preserves_model_and_feedback_does_not_change_global_policy(self):
        model=self.model()
        feedback=self.learning.feedback(dict(id='before'),dict(operation='SET_RELATION'),
            dict(id='after'),True,'ORDER','Fixture actor')
        self.assertFalse(feedback['global_policy_changed']);self.assertEqual(feedback['reason_status'],'UNKNOWN')
        reopened=Library(self.library.root)
        try:
            loaded=CrossWorkLearning(reopened).checked_model(model['id'])[0]
            self.assertEqual(loaded['weights_digest'],model['weights_digest'])
        finally:reopened.db.close()

    def test_cross_work_dataset_cannot_be_used_for_single_work_geometry_learning(self):
        dataset=self.dataset()
        with self.assertRaisesRegex(ValueError,'跨作品'):
            self.store.geometry_learning_plan(dataset['id'],self.samples[0]['id'],'Forbidden per-work template')

    def test_model_exposure_is_retained_after_group_role_record_is_removed(self):
        self.model()
        sha=self.sources[0]['hash']
        self.store.db.execute("DELETE FROM training_records WHERE kind='GROUP_ROLE' AND id=?",(sha,))
        self.store.db.commit()
        conflicts=QualityGroups(self.library).role_conflicts([(sha,'HOLDOUT')])
        self.assertTrue(conflicts)
        self.assertEqual(conflicts[0]['roles'],['HOLDOUT','TRAIN'])

    def test_source_withdrawal_lists_actual_shared_models_and_stales_them(self):
        model=self.model();sid=self.samples[0]['id']
        impact=self.store.sample_usage_impact(sid)
        self.assertEqual(impact['design_model_ids'],[model['id']])
        self.assertTrue(impact['current_cross_work_training_use'])
        self.store.transition_sample(self.store.sample_transition_plan(sid,'REVOKE'),
            'Source author','Withdraw authored test design',True)
        with self.assertRaises(ValueError):self.learning.checked_model(model['id'])

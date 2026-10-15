import copy
import json
import sqlite3
import unittest
from unittest.mock import patch
import test_coverage_batches as fixtures
from template_ai.quality_groups import QualityGroups,LINK


class QualityGroupTests(unittest.TestCase):
    setUp=fixtures.CoverageBatchTests.setUp
    source=fixtures.CoverageBatchTests.source

    def groups(self):return QualityGroups(self.library)
    def locked(self,source,role):
        with self.store.transaction():return self.store._write('GROUP_ROLE',source['hash'],dict(role=role),0,'synthetic_existing_role')
    def relation(self,a,b):return self.groups().link_plan('CONTENT:'+a['hash'],'CONTENT:'+b['hash'],'NEAR_DUPLICATE','Reviewed as highly related design','Two original source visuals independently checked')

    def test_equal_content_files_and_same_source_multiple_works_share_group_not_identity(self):
        a=self.source();b=self.source('alias.svg');graph,meta,sha=self.groups().graph_state()
        import networkx as nx
        self.assertTrue(nx.has_path(graph,'SOURCE:'+a['id'],'SOURCE:'+b['id']));self.assertNotEqual(a['id'],b['id'])
        conflicts=self.groups().role_conflicts([(a['hash'],'TRAIN'),(b['hash'],'HOLDOUT')]);self.assertEqual(len(conflicts),1)
        self.assertEqual(self.library.db.execute('SELECT count(*) FROM sources').fetchone()[0],2)

    def test_near_duplicate_transitive_groups_block_roles_but_do_not_merge_truth(self):
        a=self.source(content=b'A');b=self.source('b.svg',content=b'B');c=self.source('c.svg',content=b'C')
        self.groups().confirm_link(self.relation(a,b),'Reviewer',True);self.groups().confirm_link(self.relation(b,c),'Reviewer',True)
        conflicts=self.groups().role_conflicts([(a['hash'],'TRAIN'),(c['hash'],'HOLDOUT')]);self.assertEqual(len(conflicts),1)
        self.assertEqual(set(conflicts[0]['content_hashes']),{a['hash'],b['hash'],c['hash']});self.assertEqual(self.store.count('FACTS'),0)

    def test_link_needs_preview_approval_and_real_existing_nodes(self):
        a=self.source(content=b'A');b=self.source('b.svg',content=b'B');plan=self.relation(a,b)
        with self.assertRaises(ValueError):self.groups().confirm_link(plan,'Reviewer')
        changed=copy.deepcopy(plan);changed['relation']='SAME_DESIGN_FAMILY'
        with self.assertRaises(ValueError):self.groups().confirm_link(changed,'Reviewer',True)
        with self.assertRaises(ValueError):self.groups().link_plan('WORK:missing','CONTENT:'+a['hash'],'NEAR_DUPLICATE','Reason','Evidence')
        self.assertEqual(self.store.count(LINK),0)

    def test_new_discovery_saves_truth_and_invalidates_old_holdout_not_training_weights(self):
        a=self.source(content=b'A');b=self.source('b.svg',content=b'B');self.locked(a,'TRAIN');self.locked(b,'HOLDOUT')
        with self.store.transaction():self.store._write('DATASET','holdout-fixture',dict(entries=[dict(source_hash=b['hash'],role='HOLDOUT')]),0,'synthetic_holdout')
        plan=self.relation(a,b);self.assertTrue(plan['conflicts']);saved=self.groups().confirm_link(plan,'Reviewer',True)
        self.assertEqual(saved['state'],'ACTIVE');exposed=self.store.get('HOLDOUT_EXPOSED','holdout-fixture')
        self.assertEqual(exposed['state'],'INVALID_INDEPENDENCE_REQUIRES_NEW_DATA');self.assertEqual(self.store.get('GROUP_ROLE',a['hash'])['role'],'TRAIN')

    def test_revoke_preserves_historical_leakage_and_cannot_make_old_holdout_new(self):
        a=self.source(content=b'A');b=self.source('b.svg',content=b'B');saved=self.groups().confirm_link(self.relation(a,b),'Reviewer',True)
        revoked=self.groups().revoke_link(saved['id'],saved['revision'],'Reviewer','Correction retained for audit',True)
        self.assertIn('HISTORICAL_LEAKAGE',revoked['state']);self.assertTrue(self.groups().role_conflicts([(a['hash'],'TRAIN'),(b['hash'],'HOLDOUT')]))
        self.assertEqual(len(self.store.history(LINK,saved['id'])),2)

    def test_audit_failure_rolls_back_relation_and_holdout_invalidation(self):
        a=self.source(content=b'A');b=self.source('b.svg',content=b'B');self.locked(a,'TRAIN');self.locked(b,'HOLDOUT')
        with self.store.transaction():self.store._write('DATASET','holdout-fixture',dict(entries=[dict(source_hash=b['hash'],role='HOLDOUT')]),0,'synthetic_holdout')
        plan=self.relation(a,b);event=self.library.event
        def fail(entity,action):
            if 'invalidated_by_group' in action:raise sqlite3.OperationalError('disk full')
            event(entity,action)
        with patch.object(self.library,'event',side_effect=fail):
            with self.assertRaises(sqlite3.OperationalError):self.groups().confirm_link(plan,'Reviewer',True)
        self.assertEqual(self.store.count(LINK),0);self.assertIsNone(self.store.get('HOLDOUT_EXPOSED','holdout-fixture'))

    def test_stale_preview_and_second_connection_cannot_apply_old_relation(self):
        a=self.source(content=b'A');b=self.source('b.svg',content=b'B');plan=self.relation(a,b);self.locked(a,'TRAIN')
        with self.assertRaises(ValueError):self.groups().confirm_link(plan,'Reviewer',True)
        fresh=self.relation(a,b);self.groups().confirm_link(fresh,'Reviewer',True)
        with self.assertRaises(ValueError):self.groups().confirm_link(fresh,'Other reviewer',True)

    def test_unrelated_new_sources_can_work_despite_historical_conflict_elsewhere(self):
        a=self.source(content=b'A');b=self.source('b.svg',content=b'B');c=self.source('c.svg',content=b'C');self.locked(a,'TRAIN');self.locked(b,'HOLDOUT');self.groups().confirm_link(self.relation(a,b),'Reviewer',True)
        self.assertEqual(self.groups().role_conflicts([(c['hash'],'TRAIN')]),[])

    def test_graph_metadata_budget_fails_visibly_without_silent_truncation(self):
        self.source()
        with patch('template_ai.quality_groups.MAX_ROWS',0):
            with self.assertRaisesRegex(ValueError,'有界範圍'):self.groups().graph_state()

    def test_actual_dataset_api_rejects_discovered_near_duplicate_role_leakage(self):
        from pathlib import Path
        from template_ai.importer import import_file
        from training_fixture import source_work
        from test_noise_authoring import confirmed
        from test_trusted_samples import admitted
        from test_dataset_learning import frozen
        a,work_a=source_work(self.library,self.root);confirmed(self.store,work_a);sample_a=admitted(self.store,work_a)
        path=self.root/'visually-related.svg';path.write_text(Path(a['original_path']).read_text()+'\n<!-- synthetic distinct bytes, same reviewed design -->')
        b=self.library.add_source(path,import_file(path,self.library.assets));work_b=self.library.create_artwork(b['id'],'Related design',work_a['payload']);confirmed(self.store,work_b);sample_b=admitted(self.store,work_b)
        self.assertNotEqual(a['hash'],b['hash']);train=frozen(self.store,[sample_a],'TRAIN');holdout=frozen(self.store,[sample_b],'HOLDOUT')
        self.groups().confirm_link(self.relation(a,b),'Reviewer',True)
        self.assertFalse(self.store.dataset_validity(holdout['id'])['valid']);self.assertIsNotNone(self.store.get('HOLDOUT_EXPOSED',holdout['id']))
        plan=self.store.dataset_plan('Cannot silently reuse contaminated roles',[dict(sample_id=sample_b['id'],role='HOLDOUT')]);self.assertTrue(plan['errors'])
        with self.assertRaises(ValueError):self.store.create_dataset(plan,'Reviewer',True)
        self.assertFalse(self.store.get('SAMPLE',sample_a['id'])['used_for_training']);self.assertEqual(self.library.templates(),[])

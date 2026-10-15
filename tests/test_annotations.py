from copy import deepcopy
import unittest
from unittest.mock import patch
from template_ai.annotations import AnnotationSession,resegment
from template_ai.model import Rect
import test_automatic_training as automatic_fixture


class AnnotationTests(unittest.TestCase):
    run_job=automatic_fixture.AutomaticTrainingTests.run_job
    job=automatic_fixture.AutomaticTrainingTests.job
    tearDown=automatic_fixture.AutomaticTrainingTests.tearDown

    def setUp(self):
        automatic_fixture.AutomaticTrainingTests.setUp(self)
        result=self.run_job(self.job());self.source=self.library.source(result['items'][0]['source_id']);self.works=self.library.artworks(self.source['id'])

    def test_local_move_semantic_change_and_undo_redo_do_not_write_until_atomic_save(self):
        base=self.works[0];session=AnnotationSession(self.library,base['id']);slot=base['payload']['slots'][0]
        session.change(dict(operation='MOVE',ids=[slot['id']],dx=1,dy=1))
        self.assertEqual(self.library.artwork(base['id']),base);session.undo();self.assertEqual(session.payload,base['payload']);session.redo()
        saved=session.save();self.assertEqual(saved['revision'],base['revision']+1)
        observation=next(o for o in session.store.facts(base['id'])['observations'] if o['slot_id']==slot['id'])
        self.assertAlmostEqual(observation['region']['x'],slot['rect']['x']+1,places=4)
        self.assertIsNone(session.store.facts(base['id'])['confirmation']);self.assertFalse(self.library.templates())

    def test_explicit_new_and_delete_frames_keep_source_unchanged_and_company_logo_whole(self):
        before=self.path.read_bytes();session=AnnotationSession(self.library,self.works[0]['id'])
        identity=session.add(Rect(3,43,30,4),'email','p1','example@example.test');session.save()
        self.assertTrue(any(o['text']=='example@example.test' for o in session.observations))
        session.change(dict(operation='DELETE',ids=[identity]));session.save()
        self.assertFalse(any(o.get('slot_id')==identity for o in session.observations));self.assertEqual(self.path.read_bytes(),before)
        self.assertTrue(any(s['kind']=='logo' for s in session.payload['slots']))

    def test_stale_facts_or_artwork_and_late_event_failure_leave_every_table_unchanged(self):
        session=AnnotationSession(self.library,self.works[0]['id']);slot=session.payload['slots'][0]
        session.change(dict(operation='MOVE',ids=[slot['id']],dx=1,dy=0));before=session.store.facts(session.base['id'])
        with patch.object(self.library,'event',side_effect=OSError('Synthetic late audit failure')):
            with self.assertRaises(OSError):session.save()
        self.assertEqual(self.library.artwork(session.base['id']),session.base);self.assertEqual(session.store.facts(session.base['id']),before)
        other=AnnotationSession(self.library,session.base['id']);other.payload['visual_confirmed']=True;other.save()
        with self.assertRaisesRegex(ValueError,'已更新'):session.save()

    def test_explicit_merge_preserves_both_people_logo_and_unconfirmed_text_without_original_overwrite(self):
        before=self.path.read_bytes();merged=resegment(self.library,self.works,[Rect(0,0,190,54)],'TEST','Synthetic boundary correction',True)
        self.assertEqual(len(merged),1);slots=merged[0]['payload']['slots']
        self.assertEqual({s['owner'] for s in slots if s['kind']=='name'},{'p1','p2'})
        self.assertEqual(sum(s['kind']=='logo' for s in slots),1)
        self.assertEqual(self.path.read_bytes(),before)
        facts=self.service.store.facts(merged[0]['id']);self.assertIsNone(facts['confirmation']);self.assertTrue(any(o['text']=='Blair Example' for o in facts['observations']))
        self.assertTrue(all(self.library.artwork(w['id'])['payload']['segmentation_state']=='SUPERSEDED' for w in self.works))
        with self.assertRaisesRegex(ValueError,'取代'):AnnotationSession(self.library,self.works[0]['id'])

    def test_split_cannot_drop_cut_or_ambiguously_duplicate_a_field(self):
        snapshot=self.works[0]
        for regions in ([Rect(0,0,10,10)],[Rect(0,0,90,54),Rect(0,0,90,54)]):
            with self.assertRaisesRegex(ValueError,'遺失|跨多'):resegment(self.library,[snapshot],regions,'TEST','Synthetic incorrect region',True)
        self.assertEqual(self.library.artwork(snapshot['id']),snapshot)

    def test_segmentation_cas_and_late_failure_roll_back_new_and_superseded_works(self):
        count=self.library.db.execute('SELECT count(*) FROM artworks').fetchone()[0]
        with patch.object(self.library,'event',side_effect=OSError('Synthetic audit failure')):
            with self.assertRaises(OSError):resegment(self.library,self.works,[Rect(0,0,190,54)],'TEST','Synthetic merge',True)
        self.assertEqual(self.library.db.execute('SELECT count(*) FROM artworks').fetchone()[0],count)
        self.assertEqual([self.library.artwork(w['id']) for w in self.works],self.works)

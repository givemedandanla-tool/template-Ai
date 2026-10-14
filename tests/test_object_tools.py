"""Independent geometry oracles and real transactional persistence, then Qt end-to-end."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from template_ai.demo import demo_template
from template_ai.object_tools import propose,common_properties,protect_locked
from template_ai.storage import Library
from template_ai.model import Rect,Slot,Template
APP=QApplication.instance() or QApplication([])


class ObjectToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.lib=Library(self.root/'data');self.addCleanup(self.lib.close)
        self.t=demo_template();self.lib.save_template(self.t);self.ids=[s.id for s in self.t.slots]
        self.snap=self.lib.object_snapshot('TEMPLATE',self.t.id)
    def request(self,operation,ids=None,**kw):return dict(operation=operation,ids=ids or self.ids[:2],**kw)
    def apply(self,request):return self.lib.apply_object_edit(self.lib.object_snapshot('TEMPLATE',self.t.id),request,True)

    def test_six_alignments_independent_math_and_protected_fields(self):
        raw=copy.deepcopy(self.snap['payload']);raw['slots'][0]['rect']=Rect(4,5,20,8).__dict__;raw['slots'][1]['rect']=Rect(35,26,12,6).__dict__
        expected={'LEFT':(4,26),'HCENTER':(8,26),'RIGHT':(12,26),'TOP':(35,5),'VCENTER':(35,6),'BOTTOM':(35,7)}
        for direction,(x,y) in expected.items():
            result=propose(raw,'TEMPLATE',self.request('ALIGN',axis=direction,reference=self.ids[0]));new=result['after']['slots'][1]
            self.assertEqual((new['rect']['x'],new['rect']['y']),(x,y));self.assertEqual(new['rect']['w'],12);self.assertEqual(new['rect']['h'],6)
            for k,v in raw['slots'][1].items():
                if k!='rect':self.assertEqual(new[k],v)
            self.assertEqual(result['after']['slots'][2:],raw['slots'][2:]);self.assertEqual(raw['slots'][1]['rect']['x'],35)
        with self.assertRaisesRegex(ValueError,'基準'):propose(raw,'TEMPLATE',self.request('ALIGN',axis='LEFT'))

    def test_spacing_both_axes_stable_ties_and_group_displacement(self):
        raw=copy.deepcopy(self.snap['payload'])
        for s,r in zip(raw['slots'][:3],[Rect(0,0,10,8),Rect(20,15,5,5),Rect(60,40,10,8)]):s['rect']=r.__dict__
        p=propose(raw,'TEMPLATE',self.request('DISTRIBUTE',self.ids[:3],axis='HORIZONTAL',reference='SELECTION'))
        self.assertEqual(p['gap_mm'],22.5);self.assertEqual([s['rect']['x'] for s in p['after']['slots'][:3]],[0,32.5,60])
        p=propose(raw,'TEMPLATE',self.request('DISTRIBUTE',self.ids[:3],axis='VERTICAL',reference='SELECTION'))
        self.assertEqual(p['gap_mm'],13.5);self.assertEqual([s['rect']['y'] for s in p['after']['slots'][:3]],[0,21.5,40])
        p=propose(raw,'TEMPLATE',self.request('MOVE',self.ids[:3],dx=2,dy=-3))
        self.assertEqual([s['rect']['x'] for s in p['after']['slots'][:3]],[2,22,62]);self.assertEqual(p['after']['slots'][3],raw['slots'][3])
        for s in raw['slots'][:3]:s['rect']['x']=10
        p=propose(raw,'TEMPLATE',self.request('DISTRIBUTE',self.ids[:3],axis='HORIZONTAL',reference='SELECTION'))
        self.assertLess(p['gap_mm'],0);self.assertIn('負值',p['warnings'][0])
        reverse=copy.deepcopy(raw);reverse['slots'].reverse()
        q=propose(reverse,'TEMPLATE',self.request('DISTRIBUTE',self.ids[:3],axis='HORIZONTAL',reference='SELECTION'))
        self.assertEqual({s['id']:s['rect']['x'] for s in p['after']['slots']},{s['id']:s['rect']['x'] for s in q['after']['slots']})

    def test_mixed_dirty_patch_owner_scope_and_logo_aspect(self):
        raw=copy.deepcopy(self.snap['payload']);raw['slots'][1]['color']='#123456'
        common=common_properties(raw,self.ids[:2]);self.assertTrue(common['color']['mixed']);self.assertIsNone(common['color']['value'])
        p=propose(raw,'TEMPLATE',self.request('PATCH',patch={'align':'right'}))
        self.assertEqual(p['after']['slots'][1]['color'],'#123456');self.assertEqual(p['after']['slots'][0]['size_pt'],18)
        raw['slots'][1]['owner']='p2';raw['capacity']=2
        with self.assertRaisesRegex(ValueError,'跨人物'):propose(raw,'TEMPLATE',self.request('MOVE',dx=1,dy=0))
        p=propose(raw,'TEMPLATE',self.request('MOVE',dx=1,dy=0,cross_owner=True));self.assertEqual(p['after']['slots'][1]['owner'],'p2')
        with self.assertRaisesRegex(ValueError,'歸屬'):propose(raw,'TEMPLATE',self.request('PATCH',patch={'owner':'p1'},cross_owner=True))
        raw['slots'][0]['kind']='logo';raw['slots'][0]['owner']='c1'
        with self.assertRaisesRegex(ValueError,'Logo'):propose(raw,'TEMPLATE',self.request('PATCH',[self.ids[0]],patch={'color':'#ffffff'}))
        with self.assertRaisesRegex(ValueError,'等比'):propose(raw,'TEMPLATE',self.request('PATCH',[self.ids[0]],patch={'w':35}))
        p=propose(raw,'TEMPLATE',self.request('PATCH',[self.ids[0]],patch={'w':140,'h':22}));self.assertEqual(p['after']['slots'][0]['rect']['h'],22)

    def test_legacy_lock_policy_empty_invalid_and_noop_requests(self):
        raw=copy.deepcopy(self.snap['payload']);raw['slots'][0].pop('locked');raw['slots'][0].pop('font_style')
        p=propose(raw,'TEMPLATE',self.request('LOCK',[self.ids[0]],locked=True));self.assertTrue(p['after']['slots'][0]['locked'])
        for request in (self.request('MOVE',dx=1,dy=0),self.request('PATCH',patch={'x':10}),self.request('DELETE')):
            with self.assertRaisesRegex(ValueError,'鎖定'):propose(p['after'],'TEMPLATE',request)
        with self.assertRaisesRegex(ValueError,'解鎖'):protect_locked(p['after'],raw)
        for request in ({'operation':'MOVE','ids':[],'dx':1,'dy':1},self.request('MOVE',[self.ids[0]]*2,dx=1,dy=1),self.request('MOVE',['unknown'],dx=1,dy=1),self.request('MOVE',dx=float('nan'),dy=1),self.request('PATCH',patch={}),self.request('MOVE',dx=0,dy=0)):
            with self.assertRaises(ValueError):propose(raw,'TEMPLATE',request)
        self.assertEqual(self.lib.object_edit_history('TEMPLATE',self.t.id),[])

    def test_persistent_apply_undo_redo_reopen_and_unselected_identity(self):
        record=self.apply(self.request('MOVE',dx=1,dy=1));self.assertEqual(len(record['plan']['changes']),2)
        self.assertEqual(record['after']['slots'][2:],self.snap['payload']['slots'][2:])
        other=Library(self.root/'data');self.addCleanup(other.close)
        self.assertEqual(other.object_edit_history('TEMPLATE',self.t.id)[0]['id'],record['id'])
        undone=other.object_history_action(record['id'],'UNDO',True);self.assertEqual(other.object_snapshot('TEMPLATE',self.t.id)['payload'],self.snap['payload'])
        redone=other.object_history_action(record['id'],'REDO',True);self.assertEqual(redone['phase'],'APPLIED');self.assertEqual(other.object_snapshot('TEMPLATE',self.t.id)['payload'],record['after'])
        self.assertEqual(undone['expected_revision']+1,redone['expected_revision'])

    def test_cas_aba_publication_and_late_audit_atomic_rollback(self):
        original=copy.deepcopy(self.t);self.t.name='other edit';self.lib.save_template(self.t);self.lib.save_template(original)
        with self.assertRaisesRegex(ValueError,'ABA'):self.lib.apply_object_edit(self.snap,self.request('MOVE',dx=1,dy=1),True)
        before=self.lib.object_snapshot('TEMPLATE',self.t.id)
        with patch.object(self.lib,'event',side_effect=RuntimeError('late audit error')):
            with self.assertRaisesRegex(RuntimeError,'audit'):self.apply(self.request('MOVE',dx=1,dy=1))
        self.assertEqual(self.lib.object_snapshot('TEMPLATE',self.t.id),before);self.assertEqual(self.lib.object_edit_history('TEMPLATE',self.t.id),[])
        r=self.apply(self.request('MOVE',dx=1,dy=1));before=self.lib.object_snapshot('TEMPLATE',self.t.id)
        with patch.object(self.lib,'event',side_effect=RuntimeError('undo audit error')):
            with self.assertRaises(RuntimeError):self.lib.object_history_action(r['id'],'UNDO',True)
        self.assertEqual(self.lib.object_snapshot('TEMPLATE',self.t.id),before);self.assertEqual(self.lib.object_edit_history('TEMPLATE',self.t.id)[0]['phase'],'APPLIED')
        t=Template.from_dict(before['payload']);self.lib.publish(t)
        with self.assertRaises(ValueError):self.lib.object_history_action(r['id'],'UNDO',True)

    def test_source_revision_visual_revalidation_and_transaction_rollback(self):
        from template_ai.importer import import_file
        path=self.root/'anonymous.svg';path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm"><rect width="90mm" height="54mm" fill="white"/></svg>')
        src=self.lib.add_source(path,import_file(path,self.lib.assets));w=self.lib.create_artwork(src['id'],'anonymous',{'crop':Rect(0,0,90,54).__dict__,'work_width':90,'work_height':54,'slots':self.snap['payload']['slots'],'visual_confirmed':True})
        snap=self.lib.object_snapshot('ARTWORK',w['id']);r=self.lib.apply_object_edit(snap,self.request('MOVE',dx=1,dy=1),True)
        self.assertFalse(r['after']['visual_confirmed']);self.assertEqual(self.lib.artwork(w['id'])['revision'],2)
        with self.assertRaisesRegex(ValueError,'ABA'):self.lib.apply_object_edit(snap,self.request('MOVE',dx=1,dy=1),True)
        self.lib.object_history_action(r['id'],'UNDO',True);self.assertTrue(self.lib.artwork(w['id'])['payload']['visual_confirmed'])
        before=self.lib.object_snapshot('ARTWORK',w['id']);history=self.lib.artwork_history(w['id'])
        with patch.object(self.lib,'event',side_effect=RuntimeError('source audit failure')):
            with self.assertRaises(RuntimeError):self.lib.apply_object_edit(before,self.request('MOVE',dx=1,dy=1),True)
        self.assertEqual(self.lib.object_snapshot('ARTWORK',w['id']),before);self.assertEqual(self.lib.artwork_history(w['id']),history)

    def test_general_save_delete_and_font_transaction_cannot_bypass_lock(self):
        self.apply(self.request('LOCK',[self.ids[0]],locked=True));t=Template.from_dict(self.lib.object_snapshot('TEMPLATE',self.t.id)['payload']);t.slots[0].rect.x+=1
        with self.assertRaisesRegex(ValueError,'鎖定'):self.lib.save_template(t)
        t.slots.pop(0)
        with self.assertRaisesRegex(ValueError,'鎖定'):self.lib.save_template(t)
        r=self.apply(self.request('LOCK',[self.ids[0]],locked=False));self.assertFalse(r['after']['slots'][0]['locked'])
        self.lib.object_history_action(r['id'],'UNDO',True);self.assertTrue(self.lib.object_snapshot('TEMPLATE',self.t.id)['payload']['slots'][0]['locked'])

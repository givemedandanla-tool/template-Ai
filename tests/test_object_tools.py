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
        stale=copy.deepcopy(self.t)
        with self.assertRaisesRegex(ValueError,'鎖定'):self.lib.publish(stale)
        from template_ai.fonts import FontManager
        from template_ai.font_catalog import build_inventory
        from template_ai.font_review import evaluate_review,field_key,fingerprint
        manager=FontManager(self.lib);self.addCleanup(manager.close)
        asset=manager.import_font(Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'),approved=True);target=build_inventory([asset],[],[])['rows'][0]
        snapshot=self.lib.object_snapshot('TEMPLATE',self.t.id);key=field_key(self.t.id,self.ids[0])
        impact=evaluate_review([{'template':snapshot['payload'],'revision':snapshot['revision']}],target,{key:'Alex'})
        self.assertFalse(impact['rows'][0]['eligible']);self.assertIn('鎖定',' '.join(impact['rows'][0]['reasons']))
        unlocked=copy.deepcopy(snapshot['payload']);unlocked['slots'][0]['locked']=False
        forged=evaluate_review([{'template':unlocked,'revision':snapshot['revision']}],target,{key:'Alex'})['rows'][0]
        self.assertTrue(forged['eligible']);forged['template_hash']=fingerprint(snapshot['payload'])
        with self.assertRaisesRegex(ValueError,'鎖定'):self.lib._commit_font_change({'target':target,'rows':[forged]})



class ObjectToolsGuiTests(unittest.TestCase):
    def setUp(self):
        from template_ai.gui import MainWindow
        from template_ai.object_dialog import ObjectToolsDialog
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.w=MainWindow(self.root/'data');self.addCleanup(self.w.close);self.errors=[];self.w.error=lambda text:self.errors.append(text);self.w.inform=lambda text:self.errors.append(text)
        self.t=demo_template();self.t.slots[1].color='#123456';self.w.library.save_template(self.t);self.w.refresh_templates(self.t.id);self.w.tabs.setCurrentIndex(1)
        self.d=ObjectToolsDialog(self.w,'TEMPLATE',self.t.id);self.addCleanup(self.d.close);self.d.show();APP.processEvents();self.d.canvas.fit()
        self.ids=[s.id for s in self.t.slots];self.yes=patch('template_ai.object_dialog.QMessageBox.question',return_value=__import__('PySide6.QtWidgets',fromlist=['QMessageBox']).QMessageBox.Yes);self.yes.start();self.addCleanup(self.yes.stop)
    def selected(self):return sorted(i.data(__import__('PySide6.QtCore',fromlist=['Qt']).Qt.UserRole) for i in self.d.objects.selectedItems())

    def test_real_three_way_click_modifier_list_and_rubber_selection(self):
        from PySide6.QtCore import Qt,QPointF
        from PySide6.QtTest import QTest
        v=self.d.canvas;first=self.t.slots[0].rect;second=self.t.slots[1].rect
        p=lambda r:v.mapFromScene(QPointF(r.x+r.w/2,r.y+r.h/2))
        QTest.mouseClick(v.viewport(),Qt.LeftButton,pos=p(first));self.assertEqual(self.d.ids,[self.ids[0]]);self.assertEqual(self.selected(),self.d.ids)
        QTest.mouseClick(v.viewport(),Qt.LeftButton,Qt.ControlModifier,pos=p(second));self.assertEqual(set(self.d.ids),set(self.ids[:2]));self.assertIn('選取2件',self.d.properties.toPlainText())
        self.d.objects.clearSelection();self.d.objects.item(2).setSelected(True);APP.processEvents();self.assertEqual(self.d.ids,[self.ids[2]])
        a=v.mapFromScene(QPointF(6,4));b=v.mapFromScene(QPointF(80,27))
        QTest.mousePress(v.viewport(),Qt.LeftButton,pos=a);QTest.mouseMove(v.viewport(),b);QTest.mouseRelease(v.viewport(),Qt.LeftButton,pos=b);APP.processEvents()
        self.assertEqual(set(self.d.ids),set(self.ids[:2]));self.assertEqual(set(self.selected()),set(self.ids[:2]))
        self.d.select_ids([]);self.assertEqual(self.selected(),[]);self.assertFalse(self.d.editors['color'].isEnabled())
        self.d.select_ids(['not-this-template']);self.assertEqual(self.d.ids,[]);self.assertIn('身份',self.d.status.text())

    def test_mixed_dirty_only_panel_preserves_other_values_and_cancel(self):
        before=self.w.library.object_snapshot('TEMPLATE',self.t.id)
        self.d.select_ids(self.ids[:2]);self.assertEqual(self.d.editors['color'].text(),'');self.assertEqual(self.d.editors['size_pt'].value(),-2001)
        self.d.editors['align'].setCurrentIndex(self.d.editors['align'].findData('right'));self.d.preview_patch()
        self.assertEqual(self.d.request['patch'],{'align':'right'});self.assertTrue(self.d.apply_button.isEnabled());self.assertEqual(self.d.plan['after']['slots'][1]['color'],'#123456')
        self.d.invalidate();self.assertEqual(self.w.library.object_snapshot('TEMPLATE',self.t.id),before);self.assertFalse(self.d.apply_button.isEnabled())
        self.d.preview_patch();self.d.apply();after=self.w.library.object_snapshot('TEMPLATE',self.t.id)['payload']
        self.assertEqual(after['slots'][0]['size_pt'],18);self.assertEqual(after['slots'][1]['size_pt'],11);self.assertEqual(after['slots'][1]['color'],'#123456');self.assertEqual(after['slots'][2:],before['payload']['slots'][2:])

    def test_real_drag_only_candidate_group_and_locked_main_paths(self):
        from PySide6.QtCore import Qt,QPointF
        from PySide6.QtTest import QTest
        from template_ai.gui import Box
        self.d.select_ids(self.ids[:2]);v=self.d.canvas;r=self.t.slots[0].rect;start=v.mapFromScene(QPointF(r.x+20,r.y+5));end=start+__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(25,10)
        before=self.w.library.object_snapshot('TEMPLATE',self.t.id)
        QTest.mousePress(v.viewport(),Qt.LeftButton,pos=start);QTest.mouseMove(v.viewport(),end);QTest.mouseRelease(v.viewport(),Qt.LeftButton,pos=end);APP.processEvents()
        self.assertIsNotNone(self.d.plan);self.assertEqual(self.d.request['operation'],'MOVE');self.assertEqual(set(self.d.request['ids']),set(self.ids[:2]));self.assertEqual(self.w.library.object_snapshot('TEMPLATE',self.t.id),before)
        for item in v.scene().items():
            if isinstance(item,Box):self.assertEqual((item.pos().x(),item.pos().y()),v.base_positions[item.slot.id])
        self.d.invalidate();self.d.select_ids([self.ids[0]]);self.d.preview_lock(True);self.d.apply()
        locked=self.w.template.slots[0];self.assertTrue(locked.locked);self.w.select_slot(locked);self.assertFalse(self.w.property_button.isEnabled())
        self.w.coords[0].setValue(30);self.w.apply_properties();self.w.delete_slot();self.assertTrue(all('鎖定' in e for e in self.errors));self.assertEqual(self.w.template.slots[0].rect.x,8)
        box=next(i for i in self.w.edit_canvas.scene().items() if isinstance(i,Box) and i.slot.id==locked.id);box.setPos(25,25);self.assertEqual(box.pos(),QPointF(8,6))
        self.d.select_ids(self.ids[:2]);self.d.preview_request({'operation':'MOVE','ids':self.d.ids,'dx':1,'dy':0});self.assertIsNone(self.d.plan);self.assertIn('鎖定',self.d.status.text())

    def test_actual_apply_history_reopen_undo_redo_and_stale_controls(self):
        self.d.select_ids(self.ids[:2]);self.d.preview_request({'operation':'MOVE','ids':self.d.ids,'dx':1,'dy':1});self.d.apply()
        self.assertEqual(len(self.d.records),1);self.assertEqual(self.w.template.slots[0].rect.x,9);self.assertEqual(self.d.records[0]['phase'],'APPLIED')
        self.d.history.selectRow(0);self.d.history_action('UNDO');self.assertEqual(self.w.template.slots[0].rect.x,8)
        from template_ai.object_dialog import ObjectToolsDialog
        reopen=ObjectToolsDialog(self.w,'TEMPLATE',self.t.id);self.addCleanup(reopen.close);self.assertEqual(reopen.records[0]['phase'],'UNDONE')
        reopen.history.selectRow(0);reopen.history_action('REDO');self.assertEqual(self.w.template.slots[0].rect.x,9)
        self.d.reload();self.d.select_ids(self.ids[:2]);self.d.preview_request({'operation':'MOVE','ids':self.d.ids,'dx':1,'dy':0});self.d.editors['color'].setText('#abcdef');self.assertIsNone(self.d.plan);self.assertFalse(self.d.apply_button.isEnabled())
        self.d.preview_patch();other=copy.deepcopy(self.w.template);other.name='external edit';self.w.library.save_template(other);self.d.apply()
        self.assertIn('變更',self.d.status.text());self.assertTrue(self.d.apply_button.isEnabled());self.assertEqual(len(self.w.library.object_edit_history('TEMPLATE',self.t.id)),1)

    def test_late_failure_retry_publication_and_no_selection_do_not_write(self):
        before=self.w.library.object_snapshot('TEMPLATE',self.t.id);self.d.preview_lock(True);self.assertIsNone(self.d.plan)
        self.d.select_ids(self.ids[:2]);self.d.preview_request({'operation':'MOVE','ids':self.d.ids,'dx':1,'dy':1})
        with patch.object(self.w.library,'event',side_effect=RuntimeError('late GUI audit')):self.d.apply()
        self.assertIn('late GUI audit',self.d.status.text());self.assertTrue(self.d.apply_button.isEnabled());self.assertEqual(self.w.library.object_snapshot('TEMPLATE',self.t.id),before)
        self.d.apply();self.assertEqual(len(self.d.records),1)
        self.w.library.publish(self.w.template);self.d.reload();self.d.select_ids([self.ids[0]]);self.d.preview_lock(True)
        self.assertIsNone(self.d.plan);self.assertIn('唯讀',self.d.status.text());self.assertFalse(self.d.editors['x'].isEnabled())

    def test_both_mode_entries_source_history_and_unsaved_editor_protection(self):
        from template_ai.object_dialog import ObjectToolsDialog
        with patch.object(ObjectToolsDialog,'exec',return_value=0) as execute:self.w.object_tools();execute.assert_called_once()
        self.w.select_slot(self.w.template.slots[0])
        with patch.object(ObjectToolsDialog,'exec',return_value=0) as execute:self.w.object_tools();execute.assert_called_once()
        self.w.text_color.setText('#998877')
        with patch.object(ObjectToolsDialog,'exec',return_value=0) as execute:self.w.object_tools();execute.assert_not_called()
        self.assertIn('未套用',self.errors[-1])
        from PySide6.QtCore import QTimer
        from test_workbench_navigation import click_message
        QTimer.singleShot(0,lambda:click_message('放棄未套用輸入並切換'));self.w.select_slot(None);self.w.template.name='not saved'
        with patch.object(ObjectToolsDialog,'exec',return_value=0) as execute:self.w.object_tools();execute.assert_not_called()
        self.assertIn('未保存',self.errors[-1])
        from template_ai.importer import import_file
        path=self.root/'source.svg';path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm"><rect width="90mm" height="54mm" fill="white"/></svg>')
        source=self.w.library.add_source(path,import_file(path,self.w.library.assets));work=self.w.library.create_artwork(source['id'],'anon',{'crop':Rect(0,0,90,54).__dict__,'work_width':90,'work_height':54,'slots':[s.__dict__|{'rect':s.rect.__dict__} for s in self.t.slots],'visual_confirmed':True})
        self.w.template=None;self.w.refresh_sources(source['id']);self.w.load_work(work);self.w.tabs.setCurrentIndex(0)
        with patch.object(ObjectToolsDialog,'exec',return_value=0) as execute:self.w.object_tools();execute.assert_called_once()
        d=ObjectToolsDialog(self.w,'ARTWORK',work['id']);self.addCleanup(d.close);d.select_ids(self.ids[:2]);d.preview_request({'operation':'MOVE','ids':d.ids,'dx':1,'dy':1});d.apply()
        self.assertEqual(self.w.work['revision'],2);self.assertFalse(self.w.visual.isChecked());self.assertEqual(self.w.slots[0].rect.x,9)
        d.history.selectRow(0);d.history_action('UNDO');self.assertEqual(self.w.slots[0].rect.x,8);self.assertTrue(self.w.visual.isChecked())

    def test_legacy_undo_and_save_reject_external_aba_without_losing_manual_slots(self):
        # Legacy editor must not overwrite a newer DB edit, even when the value returns.
        self.w.select_slot(self.w.template.slots[0]);self.w.coords[0].setValue(9);self.w.apply_properties();self.w.save_draft()
        saved=copy.deepcopy(self.w.template)
        self.w.select_slot(self.w.template.slots[0]);self.w.coords[0].setValue(10);self.w.apply_properties()
        local=copy.deepcopy(self.w.template)
        external=copy.deepcopy(saved);external.name='external';self.w.library.save_template(external);self.w.library.save_template(saved)
        before=self.w.library.object_snapshot('TEMPLATE',self.t.id);self.w.undo()
        self.assertEqual(self.w.template.to_dict(),local.to_dict());self.assertEqual(self.w.library.object_snapshot('TEMPLATE',self.t.id),before)
        self.assertTrue(any('變更' in e or '過期' in e for e in self.errors))
        self.w.template.name='manual unsaved';self.w.save_draft()
        self.assertEqual(self.w.library.object_snapshot('TEMPLATE',self.t.id),before);self.assertEqual(self.w.template.name,'manual unsaved')

    def test_explicit_font_pin_style_patch_and_cross_owner_gui_gate(self):
        from template_ai.font_catalog import raw_asset
        font=Path('/usr/share/fonts/opentype/urw-base35/NimbusSans-Italic.otf')
        asset=self.w.font_manager.import_font(font,approved=True);raw=raw_asset(asset)
        self.d.reload();self.d.select_ids(self.ids[:2]);self.d.preview_request({'operation':'PATCH','ids':self.d.ids,'patch':{'font':raw.familyName(),'font_style':raw.styleName(),'font_asset':asset}});self.d.apply()
        result=self.w.library.object_snapshot('TEMPLATE',self.t.id)['payload'];self.assertEqual(result['slots'][0]['font_style'],raw.styleName());self.assertEqual(result['slots'][0]['size_pt'],18);self.assertEqual(result['slots'][1]['color'],'#123456')
        current=Template.from_dict(result);current.capacity=2;current.slots[1].owner='p2';self.w.library.save_template(current);self.d.reload();self.d.select_ids(self.ids[:2])
        self.d.preview_request({'operation':'MOVE','ids':self.d.ids,'dx':1,'dy':0});self.assertIsNone(self.d.plan);self.assertIn('跨人物',self.d.status.text())
        self.d.cross.setChecked(True);self.d.preview_request({'operation':'MOVE','ids':self.d.ids,'dx':1,'dy':0});self.assertTrue(self.d.plan);self.assertEqual(self.d.plan['scope']['owners'],['p1','p2'])

    def test_main_manual_mutation_during_confirmation_preserved_and_refresh_retry(self):
        from PySide6.QtWidgets import QMessageBox
        self.d.select_ids(self.ids[:2]);self.d.preview_request({'operation':'MOVE','ids':self.d.ids,'dx':1,'dy':1})
        before=self.w.library.object_snapshot('TEMPLATE',self.t.id)
        def mutate(*args,**kw):self.w.template.name='manual during prompt';return QMessageBox.Yes
        with patch('template_ai.object_dialog.QMessageBox.question',side_effect=mutate):self.d.apply()
        self.assertIn('手工',self.d.status.text());self.assertEqual(self.w.template.name,'manual during prompt');self.assertEqual(self.w.library.object_snapshot('TEMPLATE',self.t.id),before)
        self.w.template=Template.from_dict(before['payload']);external=copy.deepcopy(self.w.template);external.name='external saved';self.w.library.save_template(external)
        self.d.reload();self.d.select_ids(self.ids[:2]);self.d.preview_request({'operation':'MOVE','ids':self.d.ids,'dx':1,'dy':1});self.d.apply()
        self.assertIn('原子保存',self.d.status.text());self.assertEqual(self.w.template.name,'external saved')

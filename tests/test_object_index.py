import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox
from template_ai.demo import demo_template
from template_ai.model import Slot,Rect,template_errors
from template_ai.object_index import semantic_index,matching_ids,source_structure,MAX_XML_BYTES
from template_ai.gui import MainWindow,Box
from template_ai.object_dialog import ObjectToolsDialog
APP=QApplication.instance() or QApplication([])


class ObjectIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.t=demo_template();self.t.slots.append(Slot('logo','c1',Rect(60,5,20,10),id='shared-logo'));self.t.capacity=2;self.t.company_bindings={'p1':'c1','p2':'c1'}
    def test_shared_reference_graph_same_ids_stable_and_unknown(self):
        before=self.t.to_dict();roots=semantic_index(before)
        people=[n for n in roots if 'ROOT' in n['label']];self.assertEqual(len(people),2)
        self.assertEqual([n['children'][-1]['ids'] for n in people],[['shared-logo'],['shared-logo']]);self.assertEqual(self.t.to_dict(),before)
        reverse=copy.deepcopy(before);reverse['slots'].reverse();self.assertEqual(semantic_index(reverse),roots)
        reverse['company_bindings']={};self.assertIn('UNKNOWN',semantic_index(reverse)[0]['children'][-1]['label'])
    def test_search_intersection_locked_shared_problem_and_all_scope(self):
        self.t.slots[0].locked=True;self.t.slots[1].rect.x=1000;raw=self.t.to_dict()
        self.assertEqual(matching_ids(raw,'c1 logo','SHARED'),['shared-logo']);self.assertEqual(matching_ids(raw,'','LOCKED'),[self.t.slots[0].id])
        self.assertEqual(matching_ids(raw,'p1','PROBLEM'),[self.t.slots[1].id]);self.assertEqual(matching_ids(raw,'nothing'),[])
        self.assertTrue(template_errors(self.t));self.assertEqual(len(raw['slots']),5)
    def source(self,text):
        p=self.root/'source.svg';p.write_text(text);sha=hashlib.sha256(p.read_bytes()).hexdigest()
        return {'original_path':str(p),'hash':sha,'svg':str(p),'file_hashes':{'svg':sha}}
    def test_ordered_derivative_no_native_or_inferred_mapping(self):
        s=self.source('<svg xmlns="http://www.w3.org/2000/svg"><g id="group"><rect id="a"/><text id="b">Anon</text></g></svg>');report=source_structure(s)
        self.assertEqual(report['status'],'VERIFIED_DERIVATIVE');self.assertEqual(report['mapping'],'UNKNOWN');self.assertEqual(report['count'],4)
        nodes=report['nodes'][0]['children'][0]['children'];self.assertEqual([n['source_id'] for n in nodes],['a','b']);self.assertTrue(all(n['ids']==[] for n in nodes))
        self.assertIn('非 Illustrator',report['provenance'])
    def test_changed_ambiguous_xml_limits_and_unknown_refuse(self):
        self.assertEqual(source_structure(None)['status'],'UNKNOWN')
        for text in ['<svg><g id="a"/><g id="a"/></svg>','<!DOCTYPE svg [<!ENTITY x "x">]><svg/>','<svg>'+('<g>'*41)+('</g>'*41)+'</svg>','<svg>'+(' '*MAX_XML_BYTES)+'</svg>']:
            self.assertEqual(source_structure(self.source(text))['status'],'BLOCKED')
        s=self.source('<svg/>');Path(s['svg']).write_text('<svg><rect/></svg>');self.assertEqual(source_structure(s)['status'],'BLOCKED')


class ObjectIndexGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.window=MainWindow(Path(self.temp.name)/'data');self.addCleanup(self.window.close)
        t=demo_template();t.slots.append(Slot('logo','c1',Rect(60,5,20,10),id='shared-logo'));t.capacity=2;t.company_bindings={'p1':'c1','p2':'c1'};self.window.library.save_template(t);self.t=t
        self.dialog=ObjectToolsDialog(self.window,'TEMPLATE',t.id);self.dialog.show();APP.processEvents();self.addCleanup(self.dialog.close)
    def test_actual_shared_tree_click_list_and_view_filter_selection(self):
        d=self.dialog;leaves=[n for n in d.tree_nodes if n.data(0,Qt.UserRole)==['shared-logo']];self.assertGreaterEqual(len(leaves),3)
        d.index_tree.scrollToItem(leaves[0]);APP.processEvents()
        QTest.mouseClick(d.index_tree.viewport(),Qt.LeftButton,Qt.NoModifier,d.index_tree.visualItemRect(leaves[0]).center());APP.processEvents()
        self.assertEqual(d.ids,['shared-logo']);self.assertTrue(d.objects.selectedItems());self.assertIn('c1/logo',d.properties.toPlainText())
        boxes=[i for i in d.canvas.scene().selectedItems() if isinstance(i,Box)];self.assertEqual(len(boxes),1)
        d.search.setText('p1 name');APP.processEvents();self.assertEqual(d.ids,['shared-logo']);self.assertIn('篩選外 1',d.index_count.text())
        d.index_mode.setCurrentIndex(1);APP.processEvents();self.assertEqual(d.ids,['shared-logo']);self.assertEqual(d.search.text(),'p1 name')
        d.search.clear();d.select_ids([self.t.slots[0].id]);self.assertTrue(any(n.isSelected() for n in d.tree_nodes if n.data(0,Qt.UserRole)==d.ids))
    def test_viewport_no_db_or_gate_change_locked_hidden_still_blocked(self):
        d=self.dialog;lib=self.window.library;before=lib.object_snapshot('TEMPLATE',self.t.id);ids=[self.t.slots[0].id]
        d.select_ids(ids)
        for action in ['HIDE','DIM','ISOLATE','ALL']:
            d.viewport_action(action);self.assertEqual(lib.object_snapshot('TEMPLATE',self.t.id),before);self.assertEqual(d.ids,ids)
            self.assertEqual(template_errors(self.t),template_errors(type(self.t).from_dict(d.snapshot['payload'])))
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):d.preview_lock(True);d.apply()
        d.select_ids(ids);d.viewport_action('HIDE');d.preview_request({'operation':'MOVE','ids':ids,'dx':1,'dy':0});self.assertIsNone(d.plan);self.assertIn('鎖定',d.status.text())
        d.viewport_action('ALL');box=next(i for i in d.canvas.scene().items() if isinstance(i,Box) and i.slot.id==ids[0]);self.assertTrue(box.isVisible());self.assertEqual(box.opacity(),1)
    def test_both_entries_real_source_unknown_and_derivative_selection(self):
        from template_ai.importer import import_file
        p=Path(self.temp.name)/'anon.svg';p.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm"><g id="actual"><rect width="10" height="10"/></g></svg>')
        source=self.window.library.add_source(p,import_file(p,self.window.library.assets));work=self.window.library.create_artwork(source['id'],'Anon',{'crop':Rect(0,0,90,54).__dict__,'work_width':90,'work_height':54,'slots':[self.t.slots[0].__dict__ | {'rect':self.t.slots[0].rect.__dict__}],'visual_confirmed':False})
        other=ObjectToolsDialog(self.window,'ARTWORK',work['id']);self.addCleanup(other.close);other.show();APP.processEvents();self.assertEqual(other.structure['status'],'VERIFIED_DERIVATIVE')
        other.select_ids([self.t.slots[0].id]);other.index_mode.setCurrentIndex(1);node=next(n for n in other.tree_nodes if not n.data(0,Qt.UserRole));other.index_tree.clearSelection();node.setSelected(True);self.assertEqual(other.ids,[self.t.slots[0].id])
        self.assertEqual(other.snapshot['payload']['slots'][0]['owner'],'p1');self.assertEqual(len(self.window.library.list_sources()),1)
    def test_hidden_locked_intended_member_blocks_visible_group_drag(self):
        from PySide6.QtCore import QPointF
        d=self.dialog;locked=self.t.slots[0].id;visible=self.t.slots[1].id
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):d.select_ids([locked]);d.preview_lock(True);d.apply()
        d.select_ids([locked]);d.viewport_action('HIDE');d.select_ids([locked,visible]);self.assertEqual(set(d.ids),{locked,visible})
        box=next(i for i in d.canvas.scene().items() if isinstance(i,Box) and i.slot.id==visible);before=QPointF(box.pos());box.setPos(before+QPointF(1,0))
        self.assertEqual(box.pos(),before,'Hidden locked member must not be silently dropped from the retained selection intent')
        self.assertEqual(d.canvas.selection_intent,{locked,visible})

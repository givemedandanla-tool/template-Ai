"""Actual editor/graph changes during confirmation cannot retarget destructive actions."""
from copy import deepcopy
from dataclasses import asdict
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QMessageBox,QTableWidgetItem
import test_background_context as fixture_source
from template_ai.background import make_background
from template_ai.importer import import_file
from template_ai.input_graph import InputGraph
from template_ai.model import Rect,Slot

class ModalOperationContextTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_source.BackgroundContextTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups);self.w=self.fixture.w

    def switch_draft(self):
        replacement=deepcopy(self.w.template);replacement.id='authored-modal-replacement';replacement.family_id='authored-modal-family';replacement.name='Authored untouched replacement'
        self.w.library.save_template(replacement);self.w.open_catalog_editor(replacement.id);self.assertEqual(self.w.template.id,replacement.id)
        return self.w.library.object_snapshot('TEMPLATE',replacement.id)

    def test_clear_background_cannot_remove_another_registered_draft_background(self):
        asset=make_background(import_file(self.fixture.path,self.w.library.assets),90,54);asset['approved']=True;self.w.template.background=asset;self.w.save_current_template();old=self.w.library.object_snapshot('TEMPLATE',self.w.template.id);expected=[]
        def confirm(*args):expected.append(self.switch_draft());return QMessageBox.Yes
        with patch('template_ai.gui.QMessageBox.question',side_effect=confirm):self.w.clear_background()
        self.assertEqual(len(expected),1);self.assertEqual(self.w.library.object_snapshot('TEMPLATE',expected[0]['id']),expected[0]);self.assertEqual(self.w.library.object_snapshot('TEMPLATE',old['id']),old)

    def test_publish_cannot_publish_another_registered_draft(self):
        old=self.w.library.object_snapshot('TEMPLATE',self.w.template.id);expected=[]
        def confirm(*args):expected.append(self.switch_draft());return QMessageBox.Yes
        with patch.object(self.w,'ask_bindings',return_value=deepcopy(self.w.template.company_bindings)),patch('template_ai.gui.QMessageBox.question',side_effect=confirm):self.w.publish_template()
        self.assertEqual(len(expected),1);self.assertEqual(self.w.library.object_snapshot('TEMPLATE',expected[0]['id']),expected[0]);self.assertEqual(self.w.library.object_snapshot('TEMPLATE',old['id']),old)

    def work_pair(self):
        source=self.w.library.add_source(self.fixture.path,import_file(self.fixture.path,self.w.library.assets));slot=Slot('name','p1',Rect(4,4,30,8))
        payload=dict(crop=asdict(Rect(0,0,90,54)),work_width=90.,work_height=54.,slots=[asdict(slot)],visual_confirmed=False)
        a=self.w.library.create_artwork(source['id'],'Authored A',payload);b=self.w.library.create_artwork(source['id'],'Authored B',payload)
        b=self.w.library.save_artwork(b['id'],dict(payload,work_width=89.),b['revision']);self.w.library.select_artwork(source['id'],a['id']);self.w.refresh_sources(source['id']);self.w.tabs.setCurrentIndex(0)
        self.assertEqual(self.w.work['id'],a['id']);return a,b

    def switch_work(self,b):
        self.w.refresh_works();index=next(i for i,r in enumerate(self.w.works) if r['id']==b['id']);self.w.choose_work(index);self.assertEqual(self.w.work['id'],b['id'])

    def test_rename_does_not_rename_work_selected_during_name_prompt(self):
        a,b=self.work_pair()
        def name(*args,**kwargs):self.switch_work(b);return 'Must not rename B',True
        with patch('template_ai.gui.QInputDialog.getText',side_effect=name):self.w.rename_work()
        self.assertEqual(self.w.library.artwork(b['id']),b);self.assertEqual(self.w.library.artwork(a['id'])['name'],a['name'])

    def test_history_confirmation_does_not_restore_different_work(self):
        a,b=self.work_pair()
        def history(parent,title,label,choices,*args):return choices[-1],True
        def confirm(*args):self.switch_work(b);return QMessageBox.Yes
        with patch('template_ai.gui.QInputDialog.getItem',side_effect=history),patch('template_ai.gui.QMessageBox.question',side_effect=confirm):self.w.restore_work()
        self.assertEqual(self.w.work['id'],b['id']);self.assertEqual(self.w.library.artwork(b['id']),b)

    def test_learn_does_not_use_a_different_unconfirmed_work(self):
        a,b=self.work_pair();b=self.w.library.save_artwork(b['id'],dict(b['payload'],visual_confirmed=True),b['revision']);self.w.visual.setChecked(True);before=len(self.w.library.templates(True));seen=[]
        def name(*args):self.switch_work(b);seen.append(True);return 'Must not learn B',True
        with patch('template_ai.gui.QInputDialog.getText',side_effect=name),patch.object(self.w,'ask_bindings',return_value={}):self.w.learn_template()
        self.assertEqual(seen,[True]);self.assertEqual(len(self.w.library.templates(True)),before);self.assertEqual(self.w.work['id'],b['id'])

    def new_graph(self):
        graph=InputGraph.from_legacy([dict(name=['Authored keep this input'])],[]);self.w.adopt_input_graph(graph.data);return deepcopy(graph.data)

    def test_clear_input_does_not_erase_input_adopted_during_confirmation(self):
        expected=[]
        def confirm(*args):expected.append(self.new_graph());return QMessageBox.Yes
        with patch('template_ai.gui.QMessageBox.question',side_effect=confirm):self.w.clear_input_graph()
        self.assertEqual(len(expected),1);self.assertIsNotNone(self.w.active_input_graph);self.assertEqual(self.w.active_input_graph.data,expected[0])

    def test_demo_does_not_replace_new_input_during_confirmation(self):
        self.new_graph();expected=[]
        def confirm(*args):expected.append(self.new_graph());return QMessageBox.Yes
        with patch('template_ai.gui.QMessageBox.question',side_effect=confirm):self.w.demo_input()
        self.assertEqual(len(expected),1);self.assertEqual(self.w.active_input_graph.data,expected[0])

    def test_remove_row_does_not_delete_newly_selected_row(self):
        self.w.active_input_graph=None;self.w.people.setRowCount(2)
        self.w.people.setItem(0,0,QTableWidgetItem('Authored A'));self.w.people.setItem(1,0,QTableWidgetItem('Authored B'));self.w.people.setCurrentCell(0,0)
        def confirm(*args):self.w.people.setCurrentCell(1,0);return QMessageBox.Yes
        with patch('template_ai.gui.QMessageBox.question',side_effect=confirm):self.w.remove_row(self.w.people)
        self.assertEqual(self.w.people.rowCount(),2);self.assertEqual(self.w.people.item(1,0).text(),'Authored B')

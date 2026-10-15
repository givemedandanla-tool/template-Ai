"""Ownership, exact identity, Qt interaction and the unchanged output gates."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QMessageBox,QDialog,QTableWidget
from template_ai.input_graph import InputGraph,fingerprint
from template_ai.input_graph_dialog import InputGraphDialog
from template_ai.gui import MainWindow
from template_ai.model import Template,Slot,Rect,template_errors
from template_ai.layout import generate
from template_ai.object_index import semantic_index,matching_ids
APP=QApplication.instance() or QApplication([])


def fixture():
    g=InputGraph.from_legacy([dict(name=['Alex Example'],phone=['020-000-0100'],company='c1'),dict(name=['Casey Example'],phone=['020-000-0100'],company='c1')],[{'name':'Example Company'}])
    return g


class EntityGraphTests(unittest.TestCase):
    def test_equal_values_are_independent_and_delete_does_not_reassign_identity(self):
        g=fixture();a,b=[p['id'] for p in g.data['people']];fid=next(f['id'] for f in g.data['fields'] if f['owner_id']==b and f['kind']=='phone')
        g.command('delete_person',person_id=a,approved=True)
        self.assertEqual(g.compile()[0][0]['source_entity_id'],b);self.assertEqual(g.field(fid)['owner_id'],b);self.assertEqual(len(g.data['companies']),1)
        self.assertTrue(g.undo());self.assertEqual([p['id'] for p in g.data['people']],[a,b]);self.assertTrue(g.redo());self.assertEqual(g.data['people'][0]['id'],b)

    def test_many_companies_and_shared_contacts_preserve_owners_and_references(self):
        g=fixture();a,b=[p['id'] for p in g.data['people']];c=g.data['companies'][0]['id']
        g.command('add_company',person_id=a,name='Second Example Company');g.command('add_field',owner_id=c,kind='phone',value='Company Phone',approved=True)
        f=next(f for f in g.data['fields'] if f['owner_id']==a and f['kind']=='phone');g.command('link_field',field_id=f['id'],entity_id=b,approved=True)
        p,companies,l=g.compile();self.assertEqual(p[0]['companies'],['c1','c2']);self.assertEqual(p[1]['companies'],['c1']);self.assertEqual(companies[0]['phone'],['Company Phone'])
        self.assertEqual(g.field(f['id'])['owner_id'],a);self.assertEqual(set(g.field_impact(f['id'])),{a,b});self.assertEqual(len(p[1]['phone']),2)
        self.assertNotIn('Company Phone',p[0]['phone'])

    def test_shared_edit_requires_exact_fresh_preview_and_private_edit_is_immediate(self):
        g=fixture();a,b=[p['id'] for p in g.data['people']];cid=g.data['companies'][0]['id'];name=next(f['id'] for f in g.data['fields'] if f['owner_id']==cid)
        plan=g.make_plan('edit_field',field_id=name,value='Shared new')
        self.assertEqual(set(plan['affected']),{a,b,cid})
        with self.assertRaises(ValueError):g.apply(plan)
        private=next(f['id'] for f in g.data['fields'] if f['owner_id']==a and f['kind']=='phone');g.command('edit_field',field_id=private,value='New private')
        with self.assertRaisesRegex(ValueError,'過期'):g.apply(plan,True)
        self.assertNotEqual(g.label(cid),'Shared new');self.assertEqual(next(f['value'] for f in g.data['fields'] if f['owner_id']==b and f['kind']=='phone'),'020-000-0100')

    def test_copy_private_data_independent_and_company_mode_explicit(self):
        for mode in ('SHARED','INDEPENDENT'):
            g=fixture();a=g.data['people'][0]['id'];oldc=g.data['companies'][0]['id'];plan=g.command('copy_person',person_id=a,company_mode=mode,approved=True);pid=plan['params']['new_id']
            old=next(f for f in g.data['fields'] if f['owner_id']==a and f['kind']=='phone');new=next(f for f in g.data['fields'] if f['owner_id']==pid and f['kind']=='phone')
            self.assertNotEqual(old['id'],new['id']);g.command('edit_field',field_id=new['id'],value='Copy phone');self.assertNotEqual(g.field(old['id'])['value'],'Copy phone')
            cid=next(c for p,c in g.data['links'] if p==pid);self.assertEqual(cid==oldc,mode=='SHARED')
            if mode=='INDEPENDENT':
                f=next(f['id'] for f in g.data['fields'] if f['owner_id']==cid and f['kind']=='name');g.command('edit_field',field_id=f,value='Independent',approved=True);self.assertEqual(g.label(oldc),'Example Company')

    def test_unlink_delete_and_independent_copy_never_delete_other_references(self):
        g=fixture();a,b=[p['id'] for p in g.data['people']];c=g.data['companies'][0]['id'];before=copy.deepcopy(g.data)
        with self.assertRaisesRegex(ValueError,'仍被人物引用'):g.command('delete_company',company_id=c,approved=True)
        self.assertEqual(before,g.data);g.command('unlink_company',person_id=a,company_id=c,approved=True)
        self.assertIn([b,c],g.data['links']);self.assertEqual(g.label(c),'Example Company')
        g.command('independent_company',person_id=b,company_id=c,approved=True);self.assertTrue(any(x['id']==c for x in g.data['companies']))
        g.command('delete_company',company_id=c,approved=True);self.assertNotIn(c,[x['id'] for x in g.data['companies']]);self.assertEqual(len(g.data['companies']),1)

    def test_shared_contact_unlink_copy_delete_and_owner_deletion_protection(self):
        g=fixture();a,b=[p['id'] for p in g.data['people']];f=next(f for f in g.data['fields'] if f['owner_id']==a and f['kind']=='phone')
        g.command('link_field',field_id=f['id'],entity_id=b,approved=True)
        with self.assertRaisesRegex(ValueError,'共享欄位'):g.command('delete_person',person_id=a,approved=True)
        g.command('independent_field',field_id=f['id'],entity_id=b,approved=True);self.assertEqual(g.field(f['id'])['users'],[a]);self.assertEqual(len([x for x in g.data['fields'] if x['owner_id']==b and x['kind']=='phone']),2)
        g.command('link_field',field_id=f['id'],entity_id=b,approved=True);g.command('unlink_field',field_id=f['id'],entity_id=b,approved=True);self.assertEqual(g.field(f['id'])['users'],[a])
        g.command('link_field',field_id=f['id'],entity_id=b,approved=True);g.command('delete_field',field_id=f['id'],approved=True);self.assertFalse(any(x['id']==f['id'] for x in g.data['fields']))

    def test_schema_rejects_cross_entity_dangling_duplicate_and_forged_plans(self):
        g=fixture();f=g.data['fields'][0]
        for mutate in (lambda d:d['fields'][0].update(users=['missing']),lambda d:d['people'].append(d['people'][0]),lambda d:d['links'].append(['missing',d['companies'][0]['id']]),lambda d:d['fields'][0].update(value=1)):
            bad=copy.deepcopy(g.data);mutate(bad)
            with self.assertRaises(ValueError):InputGraph(bad)
        plan=g.make_plan('edit_field',field_id=f['id'],value='Allowed');plan['after']['people'].clear()
        with self.assertRaises(ValueError):g.apply(plan,True)
        self.assertEqual(len(g.data['people']),2)

    def test_multi_company_ports_company_contacts_exact_mapping_and_no_silent_loss(self):
        g=InputGraph.from_legacy([dict(name=['Alex'],companies=['c1','c2'])],[{'name':'One','phone':['101']},{'name':'Two'}]);p,c,l=g.compile()
        slots=[Slot('name','p1',Rect(3,3,40,7)),Slot('company','c1',Rect(3,13,35,7)),Slot('company','c2',Rect(43,13,35,7)),Slot('phone','c1',Rect(3,23,35,7))]
        t=Template('Multiple companies',90,54,slots,state='published',company_bindings={'p1':['c1','c2']});self.assertEqual(template_errors(t),[])
        candidate=generate(t,p,c,l);self.assertTrue(candidate.valid,candidate.issues);self.assertEqual(candidate.items[-1].text,'101')
        self.assertEqual([x.slot.size_pt for x in candidate.items],[s.size_pt for s in slots])
        bad=copy.deepcopy(p);bad[0]['companies']=['c1'];self.assertFalse(generate(t,bad,c,l).valid)
        no=copy.deepcopy(t);no.slots.pop();self.assertTrue(any('沒有可用模板框位' in s for s in generate(no,p,c,l).issues))
        roots=semantic_index(t.to_dict());self.assertEqual(len([x for x in roots[0]['children'] if x['label'].startswith('引用公司')]),2)

    def test_fixed_positions_empty_contacts_and_legacy_binding_remain_compatible(self):
        g=InputGraph.from_legacy([dict(name=['Alex'],phone=['','Second'])],[]);p,c,l=g.compile();self.assertEqual(p[0]['phone'],['','Second'])
        fid=g.data['fields'][-1]['id'];self.assertEqual(p[0]['field_ids']['phone'][1],fid)
        t=Template('Old binding',90,54,[Slot('name','p1',Rect(3,3,40,7)),Slot('company','c1',Rect(3,15,40,7))],state='published',company_bindings={'p1':'c1'})
        old=InputGraph.from_legacy([dict(name=['Alex'],company='c1')],[dict(name='Example')]);self.assertTrue(generate(t,*old.compile()).valid)


class EntityGuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.window=MainWindow(Path(self.tmp.name)/'library');self.addCleanup(self.window.library.db.close)
    def test_actual_cards_add_shared_edit_copy_unlink_undo_cancel_and_adopt(self):
        g=fixture();d=InputGraphDialog(self.window,g.data);self.addCleanup(d.deleteLater);d.show();APP.processEvents();a,b=[p['id'] for p in g.data['people']];cid=g.data['companies'][0]['id'];name=next(f['id'] for f in g.data['fields'] if f['owner_id']==cid and f['kind']=='name')
        self.assertEqual(len(d.cards),3);self.assertEqual(d.tree.topLevelItemCount(),2)
        d.cards[a].setChecked(False);self.assertIn(a,d.collapsed);d.cards[a].setChecked(True)
        before=copy.deepcopy(d.graph.data)
        with patch('template_ai.input_graph_dialog.QMessageBox.question',return_value=QMessageBox.No):self.assertFalse(d.execute('edit_field',field_id=name,value='Cancelled'))
        self.assertEqual(d.graph.data,before)
        with patch('template_ai.input_graph_dialog.QMessageBox.question',return_value=QMessageBox.Yes):
            self.assertTrue(d.execute('edit_field',field_id=name,value='Shared revised'));self.assertTrue(d.execute('copy_person',person_id=a,company_mode='INDEPENDENT'));self.assertTrue(d.execute('unlink_company',person_id=b,company_id=cid))
        self.assertEqual(len(d.graph.data['people']),3);self.assertEqual(len(d.graph.data['companies']),2);d.undo();self.assertIn([b,cid],d.graph.data['links']);d.redo();self.assertNotIn([b,cid],d.graph.data['links'])
        self.assertIsNone(self.window.active_input_graph);d.reject();self.assertIsNone(self.window.active_input_graph)
        generation=self.window.generation;self.window.adopt_input_graph(d.graph.data);self.assertGreater(self.window.generation,generation);self.assertFalse(self.window.export_button.isEnabled());self.assertEqual(len(self.window.input_data()[0]),3);self.assertEqual(self.window.people.editTriggers(),QTableWidget.NoEditTriggers)
        self.assertIn('穩定欄位',self.window.graph_status.text());d.hide()
    def test_actual_line_edit_private_no_confirmation_and_shared_confirmation(self):
        d=InputGraphDialog(self.window,fixture().data);self.addCleanup(d.deleteLater);a=d.graph.data['people'][0]['id'];private=next(f['id'] for f in d.graph.data['fields'] if f['owner_id']==a and f['kind']=='phone')
        with patch('template_ai.input_graph_dialog.QMessageBox.question') as ask:
            edit=d.field_editors[private];edit.setText('Private changed');edit.editingFinished.emit();ask.assert_not_called()
        self.assertEqual(d.graph.field(private)['value'],'Private changed')
        cid=d.graph.data['companies'][0]['id'];name=next(f['id'] for f in d.graph.data['fields'] if f['owner_id']==cid and f['kind']=='name')
        with patch('template_ai.input_graph_dialog.QMessageBox.question',return_value=QMessageBox.Yes) as ask:
            edit=d.field_editors[name];edit.setText('Company changed');edit.editingFinished.emit();self.assertTrue(ask.called);self.assertIn(a,ask.call_args.args[2])
        self.assertEqual(d.graph.label(cid),'Company changed')
    def test_adopt_preserves_source_graph_and_stale_report_and_no_database_writes(self):
        from template_ai.diagnostic_snapshot import context
        before=self.window.library.db.total_changes;g=fixture();self.window.adopt_input_graph(g.data);stamp=context(self.window,'input');original=fingerprint(g.data)
        f=next(f for f in g.data['fields'] if f['kind']=='phone');g.command('edit_field',field_id=f['id'],value='Changed');self.assertNotEqual(fingerprint(g.data),original)
        self.assertEqual(fingerprint(self.window.active_input_graph.data),original);self.window.adopt_input_graph(g.data);self.assertNotEqual(context(self.window,'input'),stamp);self.assertEqual(self.window.library.db.total_changes,before)

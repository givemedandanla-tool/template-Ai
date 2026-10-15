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

    def test_explicit_no_company_is_distinct_from_unknown_structure_mapping(self):
        t=Template('Empty binding',90,54,[Slot('name','p1',Rect(3,3,40,7))])
        self.assertIn('UNKNOWN',semantic_index(t.to_dict())[0]['children'][-1]['label'])
        t.company_bindings={'p1':[]}
        self.assertIn('明確確認',semantic_index(t.to_dict())[0]['children'][-1]['label'])
        self.assertNotIn('UNKNOWN',semantic_index(t.to_dict())[0]['children'][-1]['label'])

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


class EntityCustomerTests(unittest.TestCase):
    def setUp(self):
        from template_ai.customers import CustomerStore
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.window=MainWindow(Path(self.tmp.name)/'library');self.addCleanup(self.window.library.db.close);self.store=CustomerStore(self.window.library)
        self.template=Template('Two people exact',90,54,[Slot('name','p1',Rect(3,3,40,7)),Slot('name','p2',Rect(3,14,40,7))],capacity=2)
        self.window.library.save_template(self.template);self.graph=fixture();self.c=self.store.create_graph('00123','Example Client',self.graph.data,self.template.id,True)
    def test_normalized_master_identity_zero_code_two_people_many_companies_and_foreign_keys(self):
        g=InputGraph(self.c['graph']);self.assertEqual(self.c['code'],'00123');self.assertEqual(len(g.data['people']),2);self.assertEqual(len(g.data['companies']),1);self.assertEqual(len(g.data['links']),2)
        other=self.store.create_graph('00999','Same text distinct client',self.graph.data,self.template.id,True)
        self.assertTrue({f['id'] for f in self.c['fields']}.isdisjoint({f['id'] for f in other['fields']}));self.assertTrue({p['id'] for p in self.c['graph']['people']}.isdisjoint({p['id'] for p in other['graph']['people']}))
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError),self.store.db:
            self.store.db.execute('INSERT INTO customer_company_links VALUES(?,?,?)',(self.c['id'],self.c['graph']['people'][0]['id'],other['graph']['companies'][0]['id']))
        self.assertEqual(self.store.db.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertEqual(len(self.store.search('020-000-0100')),2);self.assertNotIn('purchased',self.c)
    def test_shared_writeback_impact_clear_vs_absent_and_late_failure_atomic(self):
        g=InputGraph(self.c['graph']);cid=g.data['companies'][0]['id'];f=next(f for f in g.data['fields'] if f['owner_id']==cid);phone=next(f for f in g.data['fields'] if f['kind']=='phone')
        values={f['id']:'Changed Company',phone['id']:''};plan=self.store.differences(self.c,values);shared=next(r for r in plan['rows'] if r['id']==f['id']);self.assertEqual(len(shared['affected_entities']),3)
        with patch.object(self.window.library,'event',side_effect=RuntimeError('late event')),self.assertRaises(RuntimeError):self.store.writeback(self.c,values,[f['id'],phone['id']],True)
        self.assertEqual(self.store.get(self.c['id']),self.c);self.assertEqual(self.store.history(self.c['id']),[])
        updated=self.store.writeback(self.c,values,[phone['id']],True);ug=InputGraph(updated['graph']);self.assertEqual(ug.field(phone['id'])['value'],'');self.assertEqual(ug.field(f['id'])['value'],f['value'])
        self.assertEqual(ug.field(phone['id'])['owner_id'],phone['owner_id'])
    def test_cross_entity_change_even_without_revision_bump_rejects_old_snapshot(self):
        f=self.c['fields'][0];cid=self.c['graph']['companies'][0]['id']
        with self.store.db:self.store.db.execute('UPDATE customer_entities SET logo_id=? WHERE id=?',('changed-asset-ref',cid))
        self.assertEqual(self.store.get(self.c['id'])['revision'],1)
        with self.assertRaisesRegex(ValueError,'主檔已更新'):self.store.writeback(self.c,{f['id']:'New name'},[f['id']],True)
        self.assertEqual(self.store.get(self.c['id'])['fields'][0]['value'],f['value'])
    def test_history_restore_new_cas_operation_and_old_values_not_automatic_search_aliases(self):
        f=next(f for f in self.c['fields'] if f['kind']=='phone');values={f['id']:'555-001-9999'}
        updated=self.store.writeback(self.c,values,[f['id']],True);change=self.store.history(self.c['id'])[0]
        self.assertEqual(updated['revision'],2);self.assertEqual(len(self.store.search('555-001-9999')),1)
        restored=self.store.restore_change(updated,change['id'],[f['id']],True);self.assertEqual(restored['revision'],3);self.assertEqual(InputGraph(restored['graph']).field(f['id'])['value'],f['value']);self.assertEqual(self.store.search('555-001-9999'),[])
        with self.assertRaisesRegex(ValueError,'主檔已更新'):self.store.restore_change(updated,change['id'],[f['id']],True)
        self.assertEqual(len(self.store.history(self.c['id'])),2)
    def test_reorder_exact_version_many_companies_readonly_and_no_master_or_template_mutation(self):
        before=self.store.db.total_changes;draft=self.store.reorder(self.c['id'],self.c['styles'][0]['id'],True)
        self.assertEqual(self.store.db.total_changes,before);self.assertEqual(draft['graph'],self.c['graph']);self.assertEqual(draft['people'][0]['company'],'c1')
        self.assertEqual(draft['people'][0]['companies'],['c1']);self.assertEqual(draft['companies'][0]['name'],'Example Company')
        g=InputGraph(draft['graph']);f=g.data['fields'][0];g.command('edit_field',field_id=f['id'],value='Work only');self.window.adopt_input_graph(g.data,draft['snapshot'])
        self.assertEqual(self.store.get(self.c['id']),self.c);self.assertFalse(self.window.export_button.isEnabled());self.assertEqual(self.window.library.templates()[0].to_dict(),self.template.to_dict())
    def test_idempotent_legacy_migration_preserves_field_ids_and_marks_ambiguous_without_data_loss(self):
        from template_ai.customers import CustomerStore
        from template_ai.model import new_id
        cid=new_id();fid=new_id();amb=new_id()
        with self.store.db:
            self.store.db.execute('INSERT INTO customers VALUES(?,?,?,1)',(cid,'00001','Legacy'))
            self.store.db.execute('INSERT INTO customer_fields VALUES(?,?,?,?,?)',(fid,cid,'p1','name','Alex Legacy'))
            self.store.db.execute('INSERT INTO customers VALUES(?,?,?,1)',(amb,'00002','Ambiguous'))
            self.store.db.executemany('INSERT INTO customer_fields VALUES(?,?,?,?,?)',[(new_id(),amb,'p1','name','First'),(new_id(),amb,'p1','name','Second')])
        store=CustomerStore(self.window.library);legacy=store.get(cid);self.assertEqual(legacy['graph']['fields'][0]['id'],fid);self.assertEqual(legacy['fields'][0]['value'],'Alex Legacy');self.assertEqual(store.get(amb)['ownership_state'],'LEGACY_OWNERSHIP_REVIEW_REQUIRED');self.assertIsNone(store.get(amb)['graph']);self.assertEqual(len(store.get(amb)['fields']),2)
        stable=copy.deepcopy(legacy);CustomerStore(self.window.library);self.assertEqual(store.get(cid),stable);self.assertEqual(self.store.db.execute('SELECT count(*) FROM customer_entities WHERE customer_id=?',(amb,)).fetchone()[0],0)
    def test_link_additional_exact_style_is_cas_and_never_edits_template_or_work(self):
        t=copy.deepcopy(self.template);t.id='other-exact-style';t.version=2;t.width_mm=100;self.window.library.save_template(t)
        updated=self.store.link_style(self.c,t.id,True);self.assertEqual(len(updated['styles']),2);self.assertEqual(updated['revision'],2);self.assertEqual(self.window.library.templates()[0].state,'draft');self.assertIsNone(self.window.active_input_graph)
        with self.assertRaisesRegex(ValueError,'主檔已更新'):self.store.link_style(self.c,t.id,True)
    def test_actual_customer_prefill_graph_edit_diff_selective_write_and_history(self):
        from template_ai.customer_dialog import CustomerDialog
        d=CustomerDialog(self.window);self.addCleanup(d.deleteLater);d.query.setText('00123');d.search();d.customers.selectRow(0);APP.processEvents()
        with patch('template_ai.customer_dialog.QInputDialog.getItem',side_effect=lambda parent,title,prompt,labels,*args:(labels[0],True)),patch('template_ai.customer_dialog.QMessageBox.question',return_value=QMessageBox.Yes):d.prefill()
        self.assertIsNotNone(self.window.active_input_graph);self.assertEqual(self.window.reorder_customer_snapshot,self.c)
        g=InputGraph(self.window.active_input_graph.data);phone=next(f for f in g.data['fields'] if f['kind']=='phone');g.command('edit_field',field_id=phone['id'],value='Work phone only');self.window.adopt_input_graph(g.data)
        d.select();row=next(i for i,f in enumerate(d.snapshot['fields']) if f['id']==phone['id']);self.assertEqual(d.fields.item(row,3).text(),'Work phone only');self.assertEqual(d.fields.item(row,0).checkState(),Qt.Unchecked)
        self.assertEqual(self.store.get(self.c['id']),self.c);d.fields.item(row,0).setCheckState(Qt.Checked)
        with patch('template_ai.customer_dialog.QMessageBox.question',return_value=QMessageBox.Yes):d.write()
        updated=self.store.get(self.c['id']);self.assertEqual(updated['revision'],2);self.assertEqual(InputGraph(updated['graph']).field(phone['id'])['value'],'Work phone only')
        d.fields.item(row,0).setCheckState(Qt.Checked)
        with patch('template_ai.customer_dialog.QInputDialog.getItem',side_effect=lambda parent,title,prompt,labels,*args:(labels[0],True)),patch('template_ai.customer_dialog.QMessageBox.question',return_value=QMessageBox.Yes):d.restore_history()
        self.assertEqual(self.store.get(self.c['id'])['revision'],3);self.assertEqual(self.window.active_input_graph.field(phone['id'])['value'],'Work phone only')


class EntityBoundaryTests(unittest.TestCase):
    def test_copy_single_field_and_literal_semicolon_not_parsed_or_shared(self):
        g=fixture();pid=g.data['people'][0]['id'];f=next(f for f in g.data['fields'] if f['owner_id']==pid and f['kind']=='phone');g.command('edit_field',field_id=f['id'],value='literal；one value');g.command('copy_field',field_id=f['id'],owner_id=pid)
        values=g.compile()[0][0]['phone'];self.assertEqual(values,['literal；one value']*2);self.assertEqual(len({x['id'] for x in g.data['fields']}),len(g.data['fields']))
        other=next(x for x in g.data['fields'] if x['owner_id']==pid and x['kind']=='phone' and x['id']!=f['id']);g.command('edit_field',field_id=other['id'],value='Only copy');self.assertEqual(g.field(f['id'])['value'],'literal；one value')
    def test_undo_identical_text_still_invalidates_preview_and_delete_lists_lost_information(self):
        g=fixture();pid=g.data['people'][0]['id'];fid=g.data['fields'][0]['id'];plan=g.make_plan('edit_field',field_id=fid,value='Future')
        g.command('edit_field',field_id=fid,value='Temporary');g.undo()
        with self.assertRaisesRegex(ValueError,'過期'):g.apply(plan,True)
        deletion=g.make_plan('delete_person',person_id=pid);lost=[d['before']['value'] for d in deletion['differences'] if d['after'] is None];self.assertIn('Alex Example',lost);self.assertIn('020-000-0100',lost);self.assertEqual(deletion['result_counts']['people'],1);self.assertTrue(deletion['link_changes']['removed'])
    def test_company_logo_gate_rejects_cross_size_or_wrong_company_after_independent_edit(self):
        g=InputGraph.from_legacy([dict(name=['Alex'],company='c1')],[dict(name='Example Company')]);t=Template('Logo exact',90,54,[Slot('name','p1',Rect(3,3,40,7)),Slot('logo','c1',Rect(3,14,40,10))],state='published',company_bindings={'p1':['c1']});p,c,l=g.compile()
        for company,w,h in [('Example Company',54,90),('Another Company',90,54)]:
            bad={'company':company,'width_mm':w,'height_mm':h,'approved':True};candidate=generate(t,p,c,{'c1':bad});self.assertFalse(candidate.valid);self.assertTrue(any('公司或矩形尺寸不符' in r for r in candidate.issues))
        self.assertFalse(generate(t,p,c,{}).valid);self.assertEqual(t.slots[0].size_pt,10)
    def test_limits_and_empty_graph_fail_without_partial_mutation(self):
        g=InputGraph.from_legacy([dict(name=['']) for i in range(20)],[]);before=copy.deepcopy(g.data)
        with self.assertRaisesRegex(ValueError,'20人物'):g.command('add_person')
        self.assertEqual(g.data,before);empty=InputGraph();self.assertEqual(empty.compile(),([],[],{}));self.assertFalse(empty.undo())
        from template_ai.input_diagnostics import diagnose
        report=diagnose([{'name':['']}],[],[],90,54);self.assertEqual(report['issues'][0]['code'],'MISSING_NAME');self.assertFalse(report['global_unsolvable'])


class EntityEntryTests(unittest.TestCase):
    def test_main_entry_actual_modal_adopt_and_cancel_without_master_writes(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QPushButton
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);w=MainWindow(Path(tmp.name)/'library');self.addCleanup(w.library.db.close)
        errors=[];observed=[];before=w.library.db.total_changes
        def interact():
            d=APP.activeModalWidget()
            try:
                self.assertIsInstance(d,InputGraphDialog);pid=d.graph.data['people'][0]['id'];f=d.graph.data['fields'][0]
                d.field_editors[f['id']].setText('Alex Example');d.field_editors[f['id']].editingFinished.emit()
                button=next(b for b in d.findChildren(QPushButton) if b.text()=='＋新增公司')
                with patch('template_ai.input_graph_dialog.QInputDialog.getText',return_value=('Example Company',True)):button.click()
                self.assertEqual(len(d.graph.data['links']),1);observed.append(pid)
            except BaseException as e:errors.append(e)
            finally:d.accept()
        QTimer.singleShot(0,interact);w.graph_button.click();self.assertEqual(errors,[]);self.assertTrue(observed);self.assertEqual(w.active_input_graph.data['people'][0]['id'],observed[0]);self.assertEqual(w.input_data()[0][0]['company'],'c1')
        snapshot=copy.deepcopy(w.active_input_graph.data)
        def cancel():
            d=APP.activeModalWidget();d.execute('add_field',owner_id=observed[0],kind='phone',value='Cancelled phone');d.reject()
        QTimer.singleShot(0,cancel);w.graph_button.click();self.assertEqual(w.active_input_graph.data,snapshot);self.assertEqual(w.library.db.total_changes,before)


class EntityAdoptionTests(unittest.TestCase):
    def test_undo_redo_survives_adopt_and_reopen_in_same_session_without_disk_history(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);w=MainWindow(Path(tmp.name)/'library');self.addCleanup(w.library.db.close);g=fixture();w.adopt_input_graph(g.data);d=InputGraphDialog(w);self.addCleanup(d.deleteLater)
        pid=g.data['people'][0]['id'];fid=next(f['id'] for f in g.data['fields'] if f['owner_id']==pid and f['kind']=='phone');d.execute('edit_field',field_id=fid,value='Adopted edit');w.adopt_input_graph(d.graph.data,history=d.graph)
        reopened=InputGraphDialog(w);self.addCleanup(reopened.deleteLater);self.assertTrue(reopened.undo_button.isEnabled());reopened.undo();self.assertEqual(reopened.graph.field(fid)['value'],'020-000-0100');reopened.redo();self.assertEqual(reopened.graph.field(fid)['value'],'Adopted edit')
        self.assertEqual(w.active_input_graph.field(fid)['value'],'Adopted edit');reopened.reject();self.assertEqual(w.active_input_graph.field(fid)['value'],'Adopted edit');self.assertFalse(any('input-graph' in p.name for p in w.library.root.rglob('*')))
    def test_company_contact_report_count_and_problem_location_use_graph_entry(self):
        from template_ai.diagnostic_snapshot import make_snapshot,locate
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);w=MainWindow(Path(tmp.name)/'library');self.addCleanup(w.library.db.close);g=fixture();cid=g.data['companies'][0]['id'];g.command('add_field',owner_id=cid,kind='phone',value='Company Example Phone',approved=True)
        t=Template('Anonymous scope',90,54,[Slot('name','p1',Rect(3,3,40,7)),Slot('name','p2',Rect(3,15,40,7))],capacity=2);w.library.publish(t);w.adopt_input_graph(g.data);s=make_snapshot(w,'input');self.assertEqual(s.data['scope']['fields'],len(g.data['fields']))
        index=next(i for i,target in enumerate(s.targets) if target and target.get('table')=='companies')
        with patch.object(w,'edit_input_graph') as entry:locate(w,s.data,index,s);entry.assert_called_once()
        self.assertNotIn('Company Example Phone',json_text(s.data))


def json_text(data):
    import json
    return json.dumps(data,ensure_ascii=False)

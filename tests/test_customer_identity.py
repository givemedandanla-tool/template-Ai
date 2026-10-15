from copy import deepcopy
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from template_ai.customer_identity import CustomerIdentity
from template_ai.customers import CustomerStore
from template_ai.demo import demo_template
from template_ai.input_graph import InputGraph
from template_ai.storage import Library
from pathlib import Path

APP=QApplication.instance() or QApplication([])


class CustomerIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.library=Library(self.temp.name);self.addCleanup(self.library.close)
        self.store=CustomerStore(self.library);self.identity=CustomerIdentity(self.store)
        self.template=demo_template();self.library.save_template(self.template)
        self.customers=[]
        for code,name,phone in [('000A','Alex Example','0100'),('000B','Blair Example','0200')]:
            graph=InputGraph.from_legacy([{'name':[name],'phone':[phone],'company':'c1'}],[{'name':'Shared Company'}])
            self.customers.append(self.store.create_graph(code,name,graph.data,self.template.id,approved=True))
        self.a,self.b=self.customers

    def merge(self):
        return self.identity.merge(self.identity.plan_merge(self.a['id'],self.b['id']),True,'synthetic reviewer','explicit synthetic identity decision')

    def test_merge_aliases_are_one_search_result_and_people_companies_fields_styles_remain_distinct(self):
        before=[self.store.get(c['id']) for c in self.customers];assets=self.library.template_snapshots()
        plan=self.identity.plan_merge(self.a['id'],self.b['id'])
        self.assertEqual([self.store.get(c['id']) for c in self.customers],before)
        with self.assertRaises(ValueError):self.identity.merge(plan)
        result=self.merge();merged=result['customer']
        self.assertEqual(len(merged['graph']['people']),2);self.assertEqual(len(merged['graph']['companies']),2)
        self.assertEqual({f['id'] for f in merged['fields']},{f['id'] for c in before for f in c['fields']})
        self.assertEqual({s['id'] for s in merged['styles']},{s['id'] for c in before for s in c['styles']})
        matches=self.store.search('000B',field='CODE');self.assertEqual(len(matches),1)
        self.assertEqual(matches[0]['id'],self.a['id']);self.assertIn('000B',matches[0]['identity_aliases'])
        self.assertEqual(self.store.get(self.b['id'])['id'],self.a['id'])
        self.assertEqual(self.library.template_snapshots(),assets)
        self.assertEqual(self.library.db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_each_original_style_prefills_only_its_original_stable_person_after_merge(self):
        self.merge()
        for c in self.customers:
            prefill=self.store.reorder(self.a['id'],c['styles'][0]['id'],approved=True)
            self.assertEqual([p['id'] for p in prefill['graph']['people']],[p['id'] for p in c['graph']['people']])
            self.assertEqual(len(prefill['people']),1)

    def test_stale_or_tampered_preview_cannot_merge_and_audit_failure_rolls_back_every_relation(self):
        plan=self.identity.plan_merge(self.a['id'],self.b['id']);bad=deepcopy(plan);bad['primary_code']='000B'
        with self.assertRaisesRegex(ValueError,'計畫'):self.identity.merge(bad,True,'test','test')
        phone=next(f for f in self.b['fields'] if f['kind']=='phone')['id']
        self.store.writeback(self.b,{phone:'0300'},[phone],approved=True)
        with self.assertRaisesRegex(ValueError,'已改變'):self.identity.merge(plan,True,'test','test')
        before=[self.store.get(c['id']) for c in self.customers]
        fresh=self.identity.plan_merge(self.a['id'],self.b['id'])
        with patch.object(self.library,'event',side_effect=RuntimeError('injected audit error')):
            with self.assertRaises(RuntimeError):self.identity.merge(fresh,True,'test','test')
        self.assertEqual([self.store.get(c['id']) for c in self.customers],before)
        self.assertEqual(self.identity.history(self.a['id']),[])

    def test_split_preserves_legitimate_later_values_and_restores_old_code_ownership(self):
        record=self.merge();current=self.store.get(self.a['id'])
        phone=next(f for f in self.b['fields'] if f['kind']=='phone')['id']
        self.store.writeback(current,{phone:'0999'},[phone],approved=True)
        plan=self.identity.plan_split(record['id'])
        self.assertTrue(plan['new_values_retained'])
        self.identity.split(plan,True,'test','confirmed split preserving new values')
        restored=self.store.get(self.b['id'])
        self.assertEqual(restored['id'],self.b['id']);self.assertEqual(restored['code'],'000B')
        self.assertEqual(next(f['value'] for f in restored['fields'] if f['id']==phone),'0999')
        self.assertEqual([c['id'] for c in self.store.search('000B',field='CODE')],[self.b['id']])
        self.assertEqual(len(self.store.get(self.a['id'])['graph']['people']),1)

    def test_swapped_primary_display_code_splits_back_and_stale_split_cannot_overwrite(self):
        record=self.identity.merge(self.identity.plan_merge(self.a['id'],self.b['id'],'000B'),True,'test','test')
        self.assertEqual(record['customer']['code'],'000B')
        plan=self.identity.plan_split(record['id']);current=self.store.get(self.a['id'])
        field=current['fields'][0]['id'];self.store.writeback(current,{field:'Later value'},[field],approved=True)
        with self.assertRaisesRegex(ValueError,'版本已改變'):self.identity.split(plan,True,'test','test')
        self.identity.split(self.identity.plan_split(record['id']),True,'test','test')
        self.assertEqual(self.store.get(self.a['id'])['code'],'000A');self.assertEqual(self.store.get(self.b['id'])['code'],'000B')

    def test_ambiguous_post_merge_cross_customer_company_link_is_blocked_without_data_loss(self):
        record=self.merge();graph=self.store.get(self.a['id'])['graph']
        person=self.a['graph']['people'][0]['id'];company=self.b['graph']['companies'][0]['id']
        with self.library.db:self.library.db.execute('INSERT INTO customer_company_links VALUES(?,?,?)',(self.a['id'],person,company))
        before=self.store.get(self.a['id'])
        with self.assertRaisesRegex(ValueError,'跨客戶'):self.identity.plan_split(record['id'])
        self.assertEqual(self.store.get(self.a['id']),before)

    def source_link(self):
        import test_customer_candidates as fixture
        from template_ai.customer_candidates import CustomerCandidates
        case=fixture.CustomerCandidateTests();case.library=self.library;case.root=Path(self.temp.name)
        case.candidates=CustomerCandidates(self.store)
        source,work,template=case.make_source('000B.svg')
        candidate=case.candidates.propose(source['id'])[0];customer=self.store.get(self.b['id'])
        reviewed=case.candidates.review(candidate['id'],candidate['revision'],candidate['graph'],'000B','LINK_EXISTING','test','Synthetic verified ownership',customer,[p['id'] for p in customer['graph']['people']],True)
        case.candidates.commit([{'id':reviewed['id'],'revision':reviewed['revision']}],True)
        return case.candidates,source,work,template

    def test_source_identity_unchanged_relation_moves_and_splits_with_exact_original_style_scope(self):
        candidates,source,work,template=self.source_link();before_source=self.library.source(source['id'])
        association=candidates.associations(self.b['id'])[0]
        record=self.merge();moved=candidates.associations(self.a['id'])[0]
        self.assertEqual(moved['id'],association['id']);self.assertEqual(moved['customer_id'],self.a['id'])
        self.assertEqual(moved['person_scope'],association['person_scope'])
        self.assertEqual(self.library.source(source['id']),before_source)
        self.identity.split(self.identity.plan_split(record['id']),True,'test','test')
        self.assertEqual(candidates.associations(self.b['id']),[association])
        self.assertEqual(self.library.source(source['id']),before_source)
        self.assertEqual(self.library.db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_changed_source_after_merge_preview_blocks_all_permanent_identity_changes(self):
        candidates,source,_,_=self.source_link()
        plan=self.identity.plan_merge(self.a['id'],self.b['id'])
        before=[self.store.get(c['id']) for c in self.customers]
        Path(self.library.source(source['id'])['current_path']).write_text('changed original')
        with self.assertRaises(ValueError):self.identity.merge(plan,True,'test','test')
        self.assertEqual([self.store.get(c['id']) for c in self.customers],before)
        self.assertEqual(self.identity.history(self.a['id']),[])

    def test_actual_gui_separates_preview_cancel_and_explicit_commit(self):
        from PySide6.QtWidgets import QMessageBox
        from template_ai.gui import MainWindow
        from template_ai.customer_dialog import CustomerDialog
        window=MainWindow(self.temp.name);self.addCleanup(window.close)
        dialog=CustomerDialog(window);self.addCleanup(dialog.deleteLater)
        dialog.identity_plan=dialog.identity_service().plan_merge(self.a['id'],self.b['id'])
        dialog.cancel_identity();self.assertIsNone(dialog.identity_plan)
        self.assertEqual(self.store.get(self.b['id'])['id'],self.b['id'])
        dialog.identity_plan=dialog.identity_service().plan_merge(self.a['id'],self.b['id'])
        dialog.show_identity_preview();APP.processEvents()
        self.assertFalse(dialog.identity_preview.confirm.isEnabled())
        dialog.identity_preview.ack.setChecked(True);dialog.identity_preview.confirm.click();APP.processEvents()
        with patch('template_ai.customer_dialog.QInputDialog.getText',side_effect=[('test',True),('Synthetic verified identity',True)]),patch('template_ai.customer_dialog.QMessageBox.question',return_value=QMessageBox.Yes):
            dialog.commit_identity()
        self.assertIsNone(dialog.identity_plan);self.assertEqual(self.store.get(self.b['id'])['id'],self.a['id'])
        self.assertIn('已完成',dialog.status.text())

    def test_review_decisions_persist_without_merging_and_normalized_third_party_code_conflict_blocks(self):
        before=[self.store.get(c['id']) for c in self.customers]
        for state in ('KEEP_SEPARATE','PENDING_REVIEW'):
            self.identity.record_review(self.a['id'],self.b['id'],state,'test','synthetic review')
        self.assertEqual([self.store.get(c['id']) for c in self.customers],before)
        self.assertEqual({r['state'] for r in self.identity.history(self.a['id'])},{'KEEP_SEPARATE','PENDING_REVIEW'})
        graph=InputGraph.from_legacy([{'name':['Third Person']}],[])
        self.store.create_graph('000b','Third customer',graph.data,self.template.id,approved=True)
        with self.assertRaisesRegex(ValueError,'正規化衝突'):self.identity.plan_merge(self.a['id'],self.b['id'])

    def test_local_audit_export_no_overwrite_and_closed_event_redaction_cannot_destroy_active_split_mapping(self):
        record=self.merge();target=Path(self.temp.name)/'private-local-audit.json'
        with self.assertRaises(ValueError):self.identity.export_event(record['id'],target)
        self.assertFalse(target.exists())
        self.identity.export_event(record['id'],target,True);original=target.read_bytes()
        self.assertIn(b'Alex Example',original)
        with self.assertRaises(FileExistsError):self.identity.export_event(record['id'],target,True)
        self.assertEqual(target.read_bytes(),original)
        with self.assertRaisesRegex(ValueError,'有效合併'):self.identity.redact_event(record['id'],'test','test',True)
        self.identity.split(self.identity.plan_split(record['id']),True,'test','test')
        before=[self.store.get(c['id']) for c in self.customers]
        for event in self.identity.history(self.a['id']):
            self.identity.redact_event(event['id'],'test','remove synthetic snapshots',True)
        for event in self.identity.history(self.a['id']):
            self.assertTrue(event['redacted']);self.assertNotIn('Alex Example',str(event));self.assertNotIn('0200',str(event))
        self.assertEqual([self.store.get(c['id']) for c in self.customers],before)

    def test_failed_split_audit_rolls_back_aliases_fields_scopes_and_history(self):
        record=self.merge();plan=self.identity.plan_split(record['id']);before=self.store.get(self.a['id'])
        history=self.identity.history(self.a['id'])
        with patch.object(self.library,'event',side_effect=RuntimeError('injected split audit')):
            with self.assertRaises(RuntimeError):self.identity.split(plan,True,'test','test')
        self.assertEqual(self.store.get(self.a['id']),before)
        self.assertEqual(self.store.get(self.b['id'])['id'],self.a['id'])
        self.assertEqual(self.identity.history(self.a['id']),history)
        self.assertEqual(self.library.db.execute('PRAGMA foreign_key_check').fetchall(),[])

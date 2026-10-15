import json,shutil,threading,time,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox,QTreeWidget
from template_ai.source_discovery import discover_source_roots
from template_ai.source_context import source_context,snapshot_contexts,presentation_rows
from template_ai.source_links import hash_source,verify_source
import test_batch_source_relink as batch_fixtures
import test_customer_candidates as customer_fixtures


class SourceRelinkScopeTests(unittest.TestCase):
    def batch(self):
        case=batch_fixtures.BatchSourceTests('test_one_candidate_hashed_once_for_independent_same_content_registrations');case.setUp();self.addCleanup(case.doCleanups);return case

    def customers(self):
        case=customer_fixtures.CustomerCandidateTests('test_filename_full_rule_and_actual_facts_propose_only_without_master_writes');case.setUp();self.addCleanup(case.tearDown);return case

    def test_disjoint_and_overlapping_explicit_roots_share_candidates_without_rehashing_nested_root(self):
        c=self.batch();nested=c.search/'nested';nested.mkdir();shutil.copyfile(c.candidate,nested/'copy.png')
        other=c.root/'other';other.mkdir();shutil.copyfile(c.candidate,other/'another-name.png')
        with patch('template_ai.source_discovery.hash_source',wraps=hash_source) as hasher:
            report=discover_source_roots(c.sources,[nested,c.search,other,c.search])
        self.assertEqual(report['status'],'COMPLETE');self.assertEqual(report['hashed_files'],3);self.assertEqual(hasher.call_count,3)
        self.assertEqual(len(report['roots']),2);self.assertEqual(report['overlapping_roots'],[str(nested)])
        self.assertEqual([len(row['candidates']) for row in report['rows']],[3,3]);self.assertEqual(c.library.relink_batches(),[])

    def test_entry_and_byte_budgets_are_global_and_leave_other_roots_explicitly_unsearched(self):
        c=self.batch();other=c.root/'other';other.mkdir();shutil.copyfile(c.candidate,other/'copy.png')
        report=discover_source_roots(c.sources,[c.search,other],max_entries=1)
        self.assertEqual(report['status'],'PARTIAL');self.assertEqual(report['entries'],1);self.assertEqual(len(report['unsearched_roots']),1)
        report=discover_source_roots(c.sources,[c.search,other],max_bytes=c.candidate.stat().st_size+1)
        self.assertEqual(report['status'],'PARTIAL');self.assertEqual(report['hashed_files'],1);self.assertLessEqual(report['bytes_budgeted'],c.candidate.stat().st_size+1)
        with self.assertRaises(ValueError):discover_source_roots(c.sources,[c.search]*17)

    def test_offline_roots_and_real_cancel_never_report_all_found_or_modify_source_indexes(self):
        c=self.batch();before=c.library.list_sources();report=discover_source_roots(c.sources,[c.search,c.root/'offline'])
        self.assertEqual(report['status'],'PARTIAL');self.assertEqual(len(report['errors']),1);self.assertTrue(report['rows'][0]['candidates'])
        cancelled=threading.Event();cancelled.set();report=discover_source_roots(c.sources,[c.search],cancelled)
        self.assertEqual(report['status'],'CANCELLED');self.assertEqual(report['hashed_files'],0);self.assertEqual(c.library.list_sources(),before)

    def test_same_length_changed_original_is_distinguished_from_same_content_relocation(self):
        c=self.batch();path=c.originals[0];data=path.read_bytes();path.write_bytes(bytes([data[0]^1])+data[1:])
        report=discover_source_roots(c.sources,[c.root]);row=next(r for r in report['rows'] if r['source']['original_path']==str(path))
        self.assertIn('內容已改變',row['availability']);self.assertIn(str(path),row['same_name_different']);self.assertNotIn(str(path),[p.path for p in row['candidates']]);self.assertEqual(c.library.relink_batches(),[])

    def test_same_content_customer_registrations_keep_distinct_actual_style_person_and_training_dependencies(self):
        c=self.customers();first=c.reviewed(c.candidates.propose(c.source['id'])[0]);c.commit([first])
        second,work,template=c.make_source('00002.svg');self.assertEqual(c.source['hash'],second['hash'])
        candidate=c.reviewed(c.candidates.propose(second['id'])[0]);c.commit([candidate])
        values=snapshot_contexts(c.library.root,[c.source['id'],second['id']]);a,b=[s['impacts'] for s in values]
        self.assertTrue(a['customer_ids']);self.assertTrue(b['customer_ids']);self.assertTrue(set(a['customer_ids']).isdisjoint(b['customer_ids']))
        self.assertTrue(set(a['style_ids']).isdisjoint(b['style_ids']));self.assertEqual(a['work_ids'],[c.work['id']]);self.assertEqual(b['work_ids'],[work['id']])
        self.assertTrue(a['training_ids']);self.assertTrue(a['context']['customer_style_scopes']);self.assertTrue(a['context']['customer_associations'])
        self.assertIn('版型',a['summary']);self.assertTrue(presentation_rows(a));self.assertEqual(c.library.relink_batches(),[])

    def test_context_cas_rejects_changed_customer_then_persists_exact_mapping_without_changing_original_bytes(self):
        c=self.customers();candidate=c.reviewed(c.candidates.propose(c.source['id'])[0]);result=c.commit([candidate])[0];customer=c.store.get(result['customer_id'])
        before=source_context(c.library,c.source['id']);path=Path(c.source['original_path']);original=path.read_bytes();moved=c.root/'moved.svg';moved.write_bytes(original)
        phone=next(f for f in customer['fields'] if f['kind']=='phone');c.store.writeback(customer,{phone['id']:'0200123456'},[phone['id']],approved=True)
        request=dict(source_id=c.source['id'],expected_revision=0,expected_context=before['context_sha256'],proof=verify_source(moved,c.source['hash']))
        with self.assertRaisesRegex(ValueError,'關聯已變更'):c.library.relink_sources([request],approved=True)
        self.assertEqual(c.library.source(c.source['id'])['link_revision'],0);self.assertEqual(c.library.relink_batches(),[])
        current=source_context(c.library,c.source['id']);request['expected_context']=current['context_sha256'];associations=c.library.db.execute('SELECT * FROM customer_source_associations').fetchall()
        record=c.library.relink_sources([request],approved=True);stored=c.library.relink_batch(record['id'])['items'][0]
        self.assertEqual(stored['impact_sha256'],current['context_sha256']);self.assertEqual(stored['impact_snapshot']['customer_associations'],current['context']['customer_associations'])
        self.assertEqual(c.library.db.execute('SELECT * FROM customer_source_associations').fetchall(),associations);self.assertEqual(path.read_bytes(),original);self.assertEqual(c.store.get(customer['id'])['fields'][0]['id'],customer['fields'][0]['id'])

    def test_declared_missing_assets_and_context_budget_are_explicit_and_snapshot_does_not_write(self):
        c=self.batch();source=c.sources[0];missing=c.root/'offline-font.ttf';payload=c.library.source(source['id']);payload['external_dependencies']=[dict(role='font',path=str(missing),hash='a'*64)]
        with c.library.db:c.library.db.execute('UPDATE sources SET payload=? WHERE id=?',(json.dumps(payload),source['id']))
        changes=c.library.db.total_changes;value=snapshot_contexts(c.library.root,[source['id']])[0]['impacts']
        self.assertIn('失聯',value['asset_availability'][str(missing)]);self.assertEqual(c.library.db.total_changes,changes)
        self.assertIn(str(missing),str(presentation_rows(value)))
        with patch('template_ai.source_context.MAX_CONTEXT_ROWS',0):
            with self.assertRaisesRegex(ValueError,'資產依賴'):source_context(c.library,source['id'])
        self.assertEqual(c.library.relink_batches(),[])

    def test_real_gui_worker_multi_root_preview_details_and_explicit_alternative_selection(self):
        c=batch_fixtures.BatchSourceGuiTests('test_background_preview_is_unselected_and_cancel_confirmation_writes_nothing');c.setUp();self.addCleanup(c.doCleanups)
        other=c.root/'other';other.mkdir();shutil.copyfile(c.search/'moved.png',other/'choice.png')
        with patch('template_ai.source_dialog.QFileDialog.getExistingDirectory',side_effect=[str(c.search),str(other)]):c.dialog.choose_root();c.dialog.choose_root()
        original=Path(c.window.library.list_sources()[0]['original_path']).read_bytes();c.dialog.search()
        def wait():
            deadline=time.monotonic()+10
            while c.dialog.busy or c.window.busy:
                QApplication.processEvents();QTest.qWait(10)
                if time.monotonic()>deadline:self.fail('actual Qt worker did not complete')
        wait();self.assertEqual(len(c.dialog.report['roots']),2);self.assertFalse(c.dialog.table.cellWidget(0,0).isChecked());self.assertIsNone(c.dialog.table.cellWidget(0,3).currentData())
        seen=[]
        def inspect(dialog):seen.append(dialog.findChild(QTreeWidget).topLevelItemCount());return 0
        with patch('template_ai.source_dialog.QDialog.exec',inspect):c.dialog.show_details()
        self.assertGreater(seen[0],1)
        combo=c.dialog.table.cellWidget(0,3);chosen=str(other/'choice.png');index=next(i for i in range(1,combo.count()) if combo.itemData(i).path==chosen);combo.setCurrentIndex(index);c.dialog.table.cellWidget(0,0).setChecked(True)
        with patch('template_ai.source_dialog.QMessageBox.question',return_value=QMessageBox.Yes):c.dialog.apply_selection();wait()
        source=c.window.library.list_sources()[0];self.assertEqual(source['current_path'],chosen);self.assertEqual(Path(source['original_path']).read_bytes(),original);self.assertEqual(len(c.window.library.relink_batches()),1)

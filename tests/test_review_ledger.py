from gui_wait import dispose_main_window
import json,unittest
from pathlib import Path
import test_automatic_training as fixtures
from template_ai.review_ledger import read_page
from template_ai.training_exceptions import exclude_work
from template_ai.training_store import digest
from template_ai.model import new_id
from training_fixture import source_work,observations


class ReviewLedgerTests(unittest.TestCase):
    def test_legacy_import_duplicate_content_stays_visible_as_unregistered_review_scope(self):
        from template_ai.batch_import import BatchStore,preflight
        alias=self.path.with_name('B0002.svg');alias.write_bytes(self.path.read_bytes());store=BatchStore(self.library);batch=store.create(preflight([self.path,alias],[]),True)
        self.assertTrue(any(item['status']=='SKIPPED' for item in batch['items']));result=read_page(self.library.root,'PENDING')
        self.assertEqual(result['total'],2);self.assertEqual(result['summary']['unregistered_preflight_scope_records'],2);self.assertEqual({row['kind'] for row in result['rows']},{'IMPORT_BATCH'});self.assertEqual(result['page_reviewed'],0);self.assertEqual(result['summary']['registered_source_pages'],0)
    setUp=fixtures.AutomaticTrainingTests.setUp
    tearDown=fixtures.AutomaticTrainingTests.tearDown
    job=fixtures.AutomaticTrainingTests.job
    run_job=fixtures.AutomaticTrainingTests.run_job

    def test_identical_bytes_different_filenames_keep_all_sources_works_and_independent_human_reviews(self):
        alias=self.path.with_name('B0002.svg');alias.write_bytes(self.path.read_bytes());self.run_job(self.job([self.path,alias]))
        before=self.library.db.total_changes;result=read_page(self.library.root);self.assertEqual(result['total'],2);self.assertEqual(result['summary']['actual_active_works'],4);self.assertEqual(len({row['source_id'] for row in result['rows']}),2)
        self.assertEqual(read_page(self.library.root,query='B0002')['total'],1)
        for source in result['rows']:
            works=read_page(self.library.root,'WORK',source_id=source['source_id']);self.assertEqual(works['total'],2);self.assertEqual(works['page_reviewed'],0);self.assertTrue(all(row['review_state']=='WAITING_HUMAN_REVIEW' for row in works['rows']));self.assertTrue(all(row['verified_analysis_cache'] for row in works['rows']))
        self.assertEqual(self.library.db.total_changes,before)

    def confirmed_work(self):
        source,work=source_work(self.library,self.root,'ledger-confirmed.svg');rows=observations(work);facts=self.service.store.save_facts(work['id'],rows,0,work['revision']);self.service.store.confirm_facts(work['id'],[row['id'] for row in rows],facts['revision'],facts['pins'],self.service.store.source_proof(work['id']),'SYNTHETIC_REVIEWER',True);return source,work

    def test_actual_source_change_keeps_approval_history_but_is_not_counted_as_current_review(self):
        source,work=self.confirmed_work();before=read_page(self.library.root,'WORK');self.assertEqual(before['page_reviewed'],1);self.assertEqual(before['rows'][0]['analysis_state'],'PENDING_ANALYSIS')
        path=Path(source['original_path']);path.write_bytes(path.read_bytes()+b'\n')
        after=read_page(self.library.root,'WORK');self.assertEqual(after['page_reviewed'],0);self.assertEqual(after['rows'][0]['review_state'],'STALE_REVIEW');self.assertIsNotNone(after['rows'][0]['source_error']);self.assertEqual(after['summary']['human_confirmation_records'],1)

    def test_explicit_human_exclusion_is_a_separate_visible_state_and_not_reviewed_or_deleted(self):
        source,work=self.confirmed_work();identity=digest(['automatic-work-unit',work['id']])
        with self.service.store.transaction():unit=self.service.store._write('AUTO_UNIT',identity,dict(work_id=work['id'],source_id=source['id'],state='WAITING_REVIEW',input_signature=None,template_ids=[]),0,'synthetic_pending_unit')
        exclude_work(self.service,identity,unit['revision'],'SYNTHETIC explicit out of scope',True);result=read_page(self.library.root,'WORK')
        self.assertEqual(result['page_reviewed'],0);self.assertEqual(result['page_excluded'],1);self.assertEqual(result['rows'][0]['review_state'],'EXPLICITLY_EXCLUDED');self.assertEqual(result['summary']['actual_active_works'],1);self.assertEqual(self.library.artwork(work['id']),work)

    def test_preflight_failed_and_unregistered_scopes_are_visible_and_not_counted_as_registered_files(self):
        bad=self.root/'unsupported.txt';bad.write_text('SYNTHETIC unsupported source format');job=self.job([self.path,bad]);result=read_page(self.library.root,'PENDING')
        self.assertEqual(result['total'],2);self.assertEqual(result['summary']['registered_source_pages'],0);self.assertTrue(any(row['analysis_state']=='FAILED' for row in result['rows']))
        self.run_job(job);result=read_page(self.library.root,'PENDING');self.assertEqual(result['total'],1);self.assertEqual(result['rows'][0]['analysis_state'],'FAILED');self.assertEqual(result['summary']['registered_source_pages'],1);self.assertEqual(result['page_reviewed'],0)

    def test_large_source_scope_pages_before_payload_read_and_preserves_full_denominator(self):
        source,work=source_work(self.library,self.root);rows=[]
        for index in range(122):
            identity=new_id();value=dict(source,id=identity,original_path=str(self.root/('SYNTHETIC-'+str(index)+'.svg')));rows.append((identity,source['hash'],value['original_path'],json.dumps(value)))
        with self.library.db:self.library.db.executemany('INSERT INTO sources VALUES(?,?,?,?)',rows)
        first=read_page(self.library.root);last=read_page(self.library.root,offset=100);self.assertEqual(first['total'],123);self.assertEqual(len(first['rows']),50);self.assertEqual(len(last['rows']),23);self.assertEqual(last['summary']['actual_active_works'],1);self.assertIsNone(last['summary']['current_verified_reviewed_total'])


class ReviewLedgerGuiTests(unittest.TestCase):
    confirmed_work=ReviewLedgerTests.confirmed_work

    def setUp(self):
        fixtures.AutomaticTrainingTests.setUp(self)
        from template_ai.gui import MainWindow
        from template_ai.review_ledger_dialog import ReviewLedgerDialog
        self.source,self.work=self.confirmed_work();self.window=MainWindow(self.library.root);self.dialog=ReviewLedgerDialog(self.window);self.dialog.show()

    def tearDown(self):
        self.dialog.close()
        if self.dialog.process:self.dialog.process.waitForFinished(2000)
        self.window.source=None;self.window.work=None;self.window.template=None;dispose_main_window(self.window);fixtures.AutomaticTrainingTests.tearDown(self)

    def wait(self,predicate):
        from PySide6.QtTest import QTest
        for _ in range(1000):
            fixtures.APP.processEvents()
            if predicate():return
            QTest.qWait(10)
        self.fail('bounded ledger query failed: '+self.dialog.status.text())

    def test_actual_asynchronous_gui_reads_source_then_works_without_changing_review_or_ownership(self):
        self.wait(lambda:self.dialog.snapshot is not None);before=self.library.db.execute('SELECT count(*) FROM reviews').fetchone()[0];self.assertEqual(self.dialog.table.rowCount(),1)
        self.dialog.table.selectRow(0);self.dialog.open_works();self.wait(lambda:self.dialog.snapshot['mode']=='WORK')
        self.assertEqual(self.dialog.snapshot['page_reviewed'],1);self.assertEqual(self.dialog.rows[0]['work_id'],self.work['id']);self.assertIn('全庫當前有效已審數尚未逐頁核實',self.dialog.summary.text())
        self.assertEqual(self.library.db.execute('SELECT count(*) FROM reviews').fetchone()[0],before)

    def test_closing_project_stops_pending_ledger_query_and_disables_original_context(self):
        self.window.library.close();fixtures.APP.processEvents();self.assertTrue(self.dialog.closed);self.assertFalse(self.dialog.locate.isEnabled());self.assertFalse(self.dialog.refresh_button.isEnabled())

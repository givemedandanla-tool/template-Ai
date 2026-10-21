from copy import deepcopy
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from template_ai.automatic_training import AutomaticTraining,run_automatic
from template_ai.source_analysis import analyse_source
from template_ai.storage import Library
from template_ai.importer import import_file
from template_ai.training_pipeline import LIVE_OWNERS
from training_fixture import source_work
from test_training_pipeline import pipeline_samples
from test_dataset_learning import frozen

APP=QApplication.instance() or QApplication([])


class AutomaticTrainingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.library=Library(self.root/'data');self.service=AutomaticTraining(self.library)
        self.path=self.root/'00001.svg'
        self.path.write_text('''<svg xmlns="http://www.w3.org/2000/svg" width="190mm" height="60mm" viewBox="0 0 190 60">
        <g id="cardA"><rect id="frameA" width="90" height="54" fill="white"/>
        <text id="nameA" x="5" y="12" font-size="4">姓名：Alex Example</text><text id="phoneA" x="5" y="22" font-size="3">020-000-0100</text>
        <g id="logoA"><rect x="45" y="32" width="8" height="8" fill="red"/><text x="55" y="38" font-size="3">Whole Brand</text></g></g>
        <g id="cardB" transform="translate(100 0)"><rect id="frameB" width="90" height="54" fill="white"/><text id="nameB" x="5" y="12" font-size="4">姓名：Blair Example</text></g></svg>''')
        self.tokens=[]

    def tearDown(self):
        for token in self.tokens:LIVE_OWNERS.discard(token)
        # Registered secondary windows own SQLite handles too. Close them before
        # removing their directory; Windows correctly rejects deleting open DBs.
        self.doCleanups()
        self.library.close();self.temp.cleanup()

    def job(self,paths=None):
        return self.service.create(self.service.preflight(paths or [self.path]),'SYNTHETIC_TEST',True)

    def run_job(self,job,cancel=None,progress=None):
        row=self.service.claim(job['id'],job['revision'],True);self.tokens.append(row['owner']['token'])
        return run_automatic(self.library.root,row['id'],row['owner']['token'],cancel,progress)

    def test_real_inkscape_two_work_hypotheses_keep_whole_logo_and_pending_facts(self):
        result=self.run_job(self.job());self.assertEqual(result['phase'],'COMPLETED_WITH_EXCEPTIONS')
        source=self.library.source(result['items'][0]['source_id']);works=self.library.artworks(source['id'])
        self.assertEqual(len(works),2);self.assertTrue(all(not w['payload']['visual_confirmed'] for w in works))
        for actual,expected in zip(sorted(w['payload']['crop']['x'] for w in works),(0,100)):
            self.assertAlmostEqual(actual,expected,delta=.001)
        facts=[self.service.store.facts(w['id']) for w in works]
        self.assertTrue(all(f['confirmation'] is None for f in facts));self.assertEqual(self.library.templates(),[])
        self.assertFalse(any(o['text']=='Whole Brand' for f in facts for o in f['observations']))
        self.assertTrue(any(o['classification']=='LOGO' for f in facts for o in f['observations']))
        self.assertEqual(self.path.read_bytes(),Path(source['current_path']).read_bytes())

    def test_different_names_same_bytes_keep_source_ids_and_reuse_only_analysis_assets(self):
        other=self.root/'00999.svg';other.write_bytes(self.path.read_bytes());job=self.job([self.path,other])
        result=self.run_job(job);ids=[i['source_id'] for i in result['items']]
        self.assertEqual(len(set(ids)),2);self.assertEqual(self.library.db.execute('SELECT count(*) FROM contents').fetchone()[0],1)
        self.assertEqual(len({self.library.source(s)['svg'] for s in ids}),1)
        self.assertEqual(self.library.db.execute('SELECT count(*) FROM artworks').fetchone()[0],4)
        self.assertFalse(self.library.db.execute("SELECT 1 FROM sqlite_master WHERE name='customers'").fetchone())

    def test_preflight_change_and_job_cas_do_not_overwrite_or_start(self):
        report=self.service.preflight([self.path]);self.path.write_text(self.path.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'預檢'):self.service.create(report,'TEST',True)
        job=self.job()
        with self.assertRaises(ValueError):self.service.claim(job['id'],job['revision']+1,True)
        self.assertEqual(self.service.get(job['id'])['phase'],'READY')

    def test_bad_source_is_isolated_and_other_source_finishes(self):
        bad=self.root/'bad.svg';bad.write_text('broken synthetic SVG')
        result=self.run_job(self.job([bad,self.path]))
        self.assertEqual({i['state'] for i in result['items']},{'FAILED','WAITING_REVIEW'})
        self.assertEqual(len(self.service.store.records('AUTO_UNIT')),2)
        self.assertEqual(result['phase'],'COMPLETED_WITH_EXCEPTIONS')

    def test_one_bad_work_is_isolated_and_same_source_other_work_continues(self):
        source,work=source_work(self.library,self.root)
        payload=deepcopy(work['payload']);other=self.library.create_artwork(source['id'],'Other synthetic work',payload)
        original=AutomaticTraining.process_work
        def process(service,unit,job):
            if unit['id']==work['id']:raise ValueError('Synthetic isolated owner ambiguity')
            return original(service,unit,job)
        with patch.object(AutomaticTraining,'process_work',process):result=self.run_job(self.job([source['current_path'] if 'current_path' in source else source['original_path']]))
        units=self.service.store.records('AUTO_UNIT');self.assertEqual({u['state'] for u in units},{'FAILED','WAITING_REVIEW'})
        self.assertEqual({u['work_id'] for u in units},{work['id'],other['id']})

    def test_cancel_before_start_and_resume_then_incremental_cache_reuses_units(self):
        job=self.job();event=threading.Event();event.set();result=self.run_job(job,event)
        self.assertEqual(result['phase'],'CANCELLED');self.assertFalse(self.library.list_sources())
        done=self.run_job(result);again=self.run_job(done)
        self.assertEqual(again['items'][0]['reused_units'],2);self.assertEqual(again['items'][0]['analysed_units'],0)
        self.assertEqual(len(self.library.list_sources()),1);self.assertEqual(self.library.db.execute('SELECT count(*) FROM artworks').fetchone()[0],2)

    def test_confirmed_train_sample_runs_learning_without_auto_publishing_or_re_admission(self):
        samples,works=pipeline_samples(self.service.store,self.root,1);dataset=frozen(self.service.store,samples)
        source=self.library.source(works[0]['source_id']);before=self.library.artwork(works[0]['id'])
        job=self.job([source['current_path']]);result=self.run_job(job)
        self.assertEqual(result['phase'],'COMPLETED');self.assertEqual(len(self.library.templates()),1)
        self.assertEqual(self.library.templates()[0].state,'draft');self.assertEqual(self.service.store.count('SAMPLE'),1)
        self.assertEqual(self.library.artwork(works[0]['id']),before)
        again=self.run_job(result);self.assertEqual(len(self.library.templates()),1);self.assertEqual(again['items'][0]['reused_units'],1)

    def test_sqlite_or_late_audit_failure_stops_worker_without_false_success(self):
        job=self.job();row=self.service.claim(job['id'],job['revision'],True);token=row['owner']['token'];self.tokens.append(token)
        import sqlite3
        with patch.object(AutomaticTraining,'run_source',side_effect=sqlite3.DatabaseError('Synthetic index corruption')):
            with self.assertRaises(sqlite3.DatabaseError):run_automatic(self.library.root,row['id'],token)
        failed=self.service.get(job['id']);self.assertEqual(failed['phase'],'FAILED_SYSTEM');self.assertFalse(self.service.store.get('WORKER','automatic-worker')['active'])

    def test_single_worker_lease_and_dead_owner_are_explicitly_recoverable(self):
        first=self.job();claimed=self.service.claim(first['id'],first['revision'],True);token=claimed['owner']['token'];self.tokens.append(token)
        second=self.job()
        with self.assertRaisesRegex(ValueError,'worker'):self.service.claim(second['id'],second['revision'],True)
        LIVE_OWNERS.discard(token);self.assertEqual(self.service.phase(self.service.get(first['id'])),'INTERRUPTED')
        resumed=self.service.claim(first['id'],claimed['revision'],True);self.tokens.append(resumed['owner']['token'])
        self.assertNotEqual(token,resumed['owner']['token'])

    def test_changed_source_cache_and_approved_work_revision_require_reanalysis(self):
        result=self.run_job(self.job());sid=result['items'][0]['source_id'];work=self.library.artworks(sid)[0]
        payload=deepcopy(work['payload']);payload['slots'][0]['rect']['x']+=.5
        self.library.save_artwork(work['id'],payload,work['revision'])
        again=self.run_job(result);self.assertEqual(again['items'][0]['analysed_units'],1);self.assertEqual(again['items'][0]['reused_units'],1)
        source=self.library.source(sid);Path(source['svg']).write_text('changed synthetic cache')
        broken=self.run_job(again);self.assertEqual(broken['items'][0]['state'],'FAILED')

    def test_exact_work_retry_does_not_reanalyse_other_source_work_and_stale_plan_is_rejected(self):
        result=self.run_job(self.job());sid=result['items'][0]['source_id'];works=self.library.artworks(sid)
        plan=self.service.retry_plan([works[0]['id']]);job=self.service.create_retry(plan,'TEST',True)
        before=self.service.store.get('AUTO_UNIT',result['items'][0]['unit_ids'][1])
        done=self.run_job(job);self.assertEqual(done['items'][0]['work_scope'],[works[0]['id']])
        self.assertEqual(self.service.store.get('AUTO_UNIT',result['items'][0]['unit_ids'][1]),before)
        payload=deepcopy(works[0]['payload']);payload['visual_confirmed']=True;self.library.save_artwork(works[0]['id'],payload,works[0]['revision'])
        with self.assertRaisesRegex(ValueError,'變更'):self.service.create_retry(plan,'TEST',True)


class AutomaticTrainingGuiTests(unittest.TestCase):
    setUp=AutomaticTrainingTests.setUp
    tearDown=AutomaticTrainingTests.tearDown

    def window(self):
        from template_ai.gui import MainWindow
        window=MainWindow(self.library.root)
        from runtime_fixture import controlled_resources
        controlled_resources(window)
        def close():
            window.input_timer.stop();window.font_manager.close();window.library.close();window.deleteLater()
        self.addCleanup(close);self._gui_wait_window=window;return window

    def wait(self,condition):
        from gui_wait import job_diagnostics,wait_for_gui
        if wait_for_gui(condition,10):return
        self.fail('Actual background workflow did not finish: '+job_diagnostics(getattr(self,'_gui_wait_window',None)))

    def test_actual_qt_preflight_once_start_creates_two_pending_works_and_restores_controls(self):
        from template_ai.automatic_training_dialog import AutomaticTrainingDialog
        from PySide6.QtWidgets import QMessageBox
        window=self.window();dialog=AutomaticTrainingDialog(window);self.addCleanup(dialog.deleteLater)
        dialog.preflight([str(self.path)]);self.wait(lambda:not window.busy)
        self.assertIsNotNone(dialog.report);self.assertTrue(dialog.start_button.isEnabled())
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):dialog.start();self.wait(lambda:not dialog.running)
        self.assertFalse(window.busy);self.assertEqual(dialog.table.rowCount(),1)
        self.assertEqual(self.service.store.count('AUTO_UNIT'),2);self.assertFalse(self.library.templates())
        self.assertFalse(dialog.cancel_button.isEnabled());self.assertTrue(dialog.resume_button.isEnabled())

    def test_actual_qt_confirmation_cancel_does_not_create_job_or_source(self):
        from template_ai.automatic_training_dialog import AutomaticTrainingDialog
        from PySide6.QtWidgets import QMessageBox
        window=self.window();dialog=AutomaticTrainingDialog(window);self.addCleanup(dialog.deleteLater)
        dialog.preflight([str(self.path)]);self.wait(lambda:not window.busy)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):dialog.start()
        self.assertEqual(self.service.store.count('AUTO_JOB'),0);self.assertFalse(self.library.list_sources())

    def test_actual_gui_preflight_waits_for_startup_admission_before_confirmation_cancel(self):
        from template_ai.automatic_training_dialog import AutomaticTrainingDialog
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QMessageBox
        window=self.window();window.runtime.ready_after=window.runtime.clock()+60
        dialog=AutomaticTrainingDialog(window);self.addCleanup(dialog.deleteLater)
        dialog.preflight([str(self.path)]);QTest.qWait(200);APP.processEvents()
        self.assertTrue(window.busy);self.assertIsNone(dialog.report);self.assertFalse(dialog.start_button.isEnabled())
        self.assertEqual(self.service.store.count('AUTO_JOB'),0);self.assertFalse(self.library.list_sources())
        window.runtime.ready_after=0;self.wait(lambda:not window.busy);self.assertIsNotNone(dialog.report)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):dialog.start()
        self.assertEqual(self.service.store.count('AUTO_JOB'),0);self.assertFalse(self.library.list_sources())

    def test_worker_start_failure_releases_lease_and_busy_controls_without_publishing(self):
        from template_ai.automatic_training_dialog import AutomaticTrainingDialog
        window=self.window();dialog=AutomaticTrainingDialog(window);self.addCleanup(dialog.deleteLater)
        job=self.service.create(self.service.preflight([self.path]),'TEST',True)
        with patch.object(window,'run_job',side_effect=RuntimeError('Synthetic pool failure')):dialog.start_job(job);self.wait(lambda:not dialog.running)
        self.assertFalse(dialog.running);self.assertFalse(window.busy)
        self.assertFalse(self.service.store.get('WORKER','automatic-worker')['active'])
        self.assertEqual(self.service.get(job['id'])['phase'],'FAILED_SYSTEM')

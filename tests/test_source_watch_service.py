import tempfile,time,threading,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtTest import QTest,QSignalSpy
from PySide6.QtWidgets import QApplication
from template_ai.gui import MainWindow
from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.source_scan import register_root,configure_root,candidate_page,scan_files
from template_ai.importer import import_file
APP=QApplication.instance() or QApplication([])
SVG=b'<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 900 540"><text x="20" y="60">Synthetic watch source</text></svg>'


class SourceWatchServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.directory=self.root/'sources';self.directory.mkdir();(self.directory/'A001.svg').write_bytes(SVG)
        self.window=MainWindow(self.root/'data');self.addCleanup(lambda:self.window.close());self.store=TrainingStore(self.window.library);self.watch=register_root(self.store,self.directory);self.service=self.window.source_watch
        APP.processEvents();self.service.timer.stop()

    def wait(self,predicate,seconds=10):
        end=time.monotonic()+seconds
        while not predicate():
            APP.processEvents();QTest.qWait(10)
            if time.monotonic()>end:self.fail('actual Qt source worker timed out: '+self.service.last_status)
        APP.processEvents()

    def enable(self):
        self.watch=configure_root(self.store,self.watch,mode='AUTO_PRECHECK',enabled=True);self.service.sync();self.service.dispatch();self.wait(lambda:not self.service.running and not self.window.busy)
        self.watch=self.store.get('SCAN_ROOT',self.watch['id'])

    def test_real_qt_directory_notification_creates_exact_new_candidates_and_preserves_alias_identity(self):
        self.enable();spy=QSignalSpy(self.service.watcher.directoryChanged);before=candidate_page(self.store);self.assertEqual(len(before),1)
        (self.directory/'B002.svg').write_bytes(SVG)
        self.wait(lambda:len(candidate_page(self.store))==2 and not self.service.running and not self.window.busy)
        self.assertGreater(spy.count(),0);after=candidate_page(self.store);self.assertEqual(len({c['id'] for c in after}),2);self.assertEqual(len({c['source_hash'] for c in after}),1)
        self.assertEqual(self.window.library.list_sources(),[]);self.assertEqual(self.store.count('AUTO_JOB'),0)

    def test_lost_notifications_and_restart_reconcile_without_duplicate_pending_or_fake_training(self):
        self.enable();ids={c['id'] for c in candidate_page(self.store)};self.service.watcher.removePaths(self.service.watcher.directories());(self.directory/'B002.svg').write_bytes(SVG)
        self.service.tick();self.wait(lambda:len(candidate_page(self.store))==2 and not self.service.running and not self.window.busy)
        self.window.close();(self.directory/'C003.svg').write_bytes(SVG);self.window=MainWindow(self.root/'data');self.service=self.window.source_watch;self.store=TrainingStore(self.window.library)
        self.wait(lambda:len(candidate_page(self.store))==3 and not self.service.running and not self.window.busy)
        self.assertTrue(ids.issubset({c['id'] for c in candidate_page(self.store)}));self.assertEqual(self.store.count('AUTO_JOB'),0)

    def test_busy_window_and_duplicate_hints_keep_one_fifo_root_without_counting_events_as_files(self):
        self.watch=configure_root(self.store,self.watch,mode='AUTO_PRECHECK',enabled=True);self.window.busy=True;self.service.sync()
        for _ in range(100):self.service.hint(str(self.directory))
        self.service.dispatch();self.assertFalse(self.service.running);self.assertEqual(list(self.service.pending),[self.watch['id']]);self.assertEqual(candidate_page(self.store),[])
        self.window.busy=False;self.service.dispatch();self.wait(lambda:not self.service.running and not self.window.busy)
        self.assertEqual(len(candidate_page(self.store)),1)

    def test_pause_during_real_worker_cancels_before_candidate_commit_then_disables_future_work(self):
        started=threading.Event();release=threading.Event()
        def gated(*args,**kwargs):started.set();release.wait(2);return scan_files(*args,**kwargs)
        self.watch=configure_root(self.store,self.watch,mode='AUTO_PRECHECK',enabled=True)
        with patch('template_ai.source_watch.scan_files',side_effect=gated):
            self.service.sync();self.service.dispatch();self.wait(started.is_set);self.service.pause(self.watch['id']);release.set();self.wait(lambda:not self.service.running and not self.window.busy)
        root=self.store.get('SCAN_ROOT',self.watch['id']);self.assertFalse(root['enabled']);self.assertEqual(candidate_page(self.store),[]);self.assertIsNone(root['last_success']);self.assertTrue((self.directory/'A001.svg').exists())

    def test_source_index_changed_during_scan_cannot_commit_a_stale_candidate_or_overwrite_real_new_source(self):
        def changed(*args,**kwargs):
            result=scan_files(*args,**kwargs);library=Library(self.root/'data')
            try:
                path=self.directory/'A001.svg';library.add_source(path,import_file(path,library.assets))
            finally:library.close()
            return result
        self.watch=configure_root(self.store,self.watch,mode='AUTO_PRECHECK',enabled=True)
        with patch('template_ai.source_watch.scan_files',side_effect=changed):
            self.service.sync();self.service.dispatch();self.wait(lambda:not self.service.running and not self.window.busy)
        self.assertIn('索引',self.service.last_result['error']);self.assertEqual(candidate_page(self.store),[]);self.assertEqual(len(self.window.library.list_sources()),1);self.assertIsNone(self.store.get('SCAN_ROOT',self.watch['id'])['last_success'])

    def test_shutdown_stops_qt_watchers_and_timers_before_library_close(self):
        self.enable();self.assertTrue(self.service.watcher.directories());self.window.close();self.assertTrue(self.service.closed);self.assertFalse(self.service.timer.isActive());self.assertFalse(self.service.debounce.isActive());self.assertEqual(self.service.watcher.directories(),[])
        self.service.tick();self.service.hint(str(self.directory));self.assertFalse(self.service.running)

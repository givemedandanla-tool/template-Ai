"""Background metadata reads must not create manual work during a paused import."""
import unittest
from PySide6.QtWidgets import QApplication
from template_ai.gui import MainWindow
from template_ai.importer import import_file
from template_ai.runtime_worker import run_isolated
from gui_wait import dispose_main_window
import test_automatic_training as training_fixtures
from test_runtime_execution import ALLOW, HOLD

APP = QApplication.instance() or QApplication([])


class RuntimeSourceRefreshTests(unittest.TestCase):
    def setUp(self):
        training_fixtures.AutomaticTrainingTests.setUp(self)
        self.window = MainWindow(self.library.root)

    def tearDown(self):
        dispose_main_window(self.window)
        training_fixtures.AutomaticTrainingTests.tearDown(self)

    job = training_fixtures.AutomaticTrainingTests.job

    def test_metadata_refresh_preserves_empty_editor_without_creating_a_manual_work(self):
        source = self.library.add_source(self.path, import_file(self.path, self.library.assets))
        before = self.window.library.db.total_changes
        self.window.refresh_sources(preserve_editor=True)
        self.assertIsNone(self.window.source)
        self.assertEqual(self.window.source_combo.currentIndex(), -1)
        self.assertEqual(self.library.artworks(source['id']), [])
        self.assertEqual(self.window.library.db.total_changes, before)
        # An explicit user selection still opens the existing legacy editor.
        self.window.source_combo.setCurrentIndex(0)
        self.assertEqual(self.window.source['id'], source['id'])
        self.assertEqual(len(self.library.artworks(source['id'])), 1)

    def test_pause_after_source_registration_refresh_then_resume_keeps_both_work_regions(self):
        alias = self.path.with_name('B0002.svg')
        alias.write_bytes(self.path.read_bytes())
        job = self.job([self.path, alias])
        claimed = self.service.claim(job['id'], job['revision'], True)
        paused = run_isolated(self.library.root, 'AUTO_JOB', job['id'], claimed['owner']['token'],
                              admission=lambda: HOLD if self.library.list_sources() else ALLOW)
        self.assertEqual(paused['phase'], 'PAUSED_RESOURCES')
        self.assertEqual(len(self.library.list_sources()), 1)
        self.assertEqual(self.service.store.count('AUTO_UNIT'), 0)
        self.window.refresh_sources(preserve_editor=True)
        self.assertEqual(self.library.artworks(self.library.list_sources()[0]['id']), [])
        claimed = self.service.claim(job['id'], paused['revision'], True)
        result = run_isolated(self.library.root, 'AUTO_JOB', job['id'], claimed['owner']['token'], admission=lambda: ALLOW)
        self.assertEqual(result['phase'], 'COMPLETED_WITH_EXCEPTIONS')
        self.assertEqual(len(self.library.list_sources()), 2)
        self.assertEqual(self.service.store.count('AUTO_UNIT'), 4)
        self.assertTrue(all(item['analysed_units'] == 2 for item in result['items']))

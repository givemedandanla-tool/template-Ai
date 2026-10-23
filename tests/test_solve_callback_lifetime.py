"""Real Qt signals must respect the lifetime and owner of the solve request."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from template_ai.gui import MainWindow
from template_ai.design_learning_dialog import DesignLearningDialog, DraftSolveWorker, DesignWorker


class SolveCallbackLifetimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.window = MainWindow(Path(self.temp.name) / 'library')
        self.dialog = DesignLearningDialog(self.window)
        self.addCleanup(self.cleanup)

    def cleanup(self):
        self.dialog.bound_to_main = False
        self.window.busy = False
        self.dialog.close()
        self.window.close()
        self.temp.cleanup()

    def worker(self):
        return DraftSolveWorker(self.window.library.root, 'authored-stale-session', 1, self.dialog)

    def test_queued_finish_after_close_cannot_read_closed_database(self):
        worker = self.worker()
        self.dialog.solve_worker = worker
        self.dialog.session_id = 'authored-stale-session'
        worker.finished.connect(self.dialog.solve_finished, Qt.QueuedConnection)
        errors = []
        previous = sys.excepthook
        sys.excepthook = lambda kind, error, traceback: errors.append((kind.__name__, str(error)))
        try:
            worker.finished.emit()
            self.assertTrue(self.dialog.close())
            self.assertTrue(self.window.close())
            self.assertTrue(self.window.library.closed)
            self.app.processEvents()
            self.assertEqual(errors, [])
        finally:
            sys.excepthook = previous

    def test_older_worker_finish_cannot_release_newer_worker_busy_state(self):
        old, current = self.worker(), self.worker()
        self.dialog.solve_worker = current
        self.dialog.bound_to_main = True
        self.dialog.set_solving(True)
        old.finished.connect(self.dialog.solve_finished)
        old.finished.emit()
        self.assertTrue(self.window.busy)
        self.assertTrue(self.dialog.cancel_solve_button.isEnabled())

    def test_current_worker_finish_still_releases_busy_state(self):
        current = self.worker()
        self.dialog.solve_worker = current
        self.dialog.bound_to_main = True
        self.dialog.set_solving(True)
        current.finished.connect(self.dialog.solve_finished)
        current.finished.emit()
        self.assertFalse(self.window.busy)
        self.assertFalse(self.dialog.cancel_solve_button.isEnabled())

    def test_queued_training_finish_after_close_cannot_refresh_closed_database(self):
        worker=DesignWorker(self.window.library.root,'authored-job','authored-token',self.dialog)
        self.dialog.worker=worker
        worker.finished.connect(self.dialog.worker_finished,Qt.QueuedConnection)
        errors=[];previous=sys.excepthook
        sys.excepthook=lambda kind,error,traceback:errors.append((kind.__name__,str(error)))
        try:
            worker.finished.emit()
            self.assertTrue(self.dialog.close());self.assertTrue(self.window.close())
            self.app.processEvents();self.assertEqual(errors,[])
        finally:sys.excepthook=previous

    def test_older_training_finish_cannot_enable_current_job_controls(self):
        old=DesignWorker(self.window.library.root,'old','token',self.dialog)
        current=DesignWorker(self.window.library.root,'current','token',self.dialog)
        self.dialog.worker=current;self.dialog.train_button.setEnabled(False)
        old.finished.connect(self.dialog.worker_finished);old.finished.emit()
        self.assertFalse(self.dialog.train_button.isEnabled())
        current.finished.connect(self.dialog.worker_finished);current.finished.emit()
        self.assertTrue(self.dialog.train_button.isEnabled())

    def test_old_solve_progress_cannot_overwrite_current_status(self):
        old,current=self.worker(),self.worker();self.dialog.solve_worker=current
        self.dialog.solve_status.setText('current request')
        old.progress.connect(self.dialog.solve_progress);old.progress.emit(dict(done=0,total=1))
        self.assertEqual(self.dialog.solve_status.text(),'current request')
        current.progress.connect(self.dialog.solve_progress);current.progress.emit(dict(done=0,total=1))
        self.assertIn('1／1',self.dialog.solve_status.text())

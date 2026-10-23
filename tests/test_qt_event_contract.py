"""Fail-first native event delivery and cancellation on the real size editor."""
import os
from pathlib import Path
import tempfile
import unittest
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from template_ai.gui import MainWindow
from template_ai.multi_size_dialog import MultiSizeDialog
from template_ai.multi_size_edit import SizeEditAdapter, SizeEditController


class QtEventContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_actual_qt_event_delivery_has_no_python_callback_error(self):
        with tempfile.TemporaryDirectory() as temp:
            window = MainWindow(Path(temp) / 'library')
            owner = MultiSizeDialog(window)
            adapter = SizeEditAdapter(owner, {'candidates': []}, 0)
            controller = SizeEditController(adapter)
            previous = sys.excepthook
            errors = []
            sys.excepthook = lambda kind, error, traceback: errors.append((kind.__name__, str(error)))
            try:
                QCoreApplication.sendEvent(controller, QEvent(QEvent.User))
                self.assertEqual(errors, [])
            finally:
                sys.excepthook = previous
                owner.close()
                window.close()

    def test_real_size_controller_accepts_native_events_and_retains_cancel_guard(self):
        with tempfile.TemporaryDirectory() as temp:
            window = MainWindow(Path(temp) / 'library')
            owner = MultiSizeDialog(window)
            adapter = SizeEditAdapter(owner, {'candidates': []}, 0)
            controller = SizeEditController(adapter)
            try:
                self.assertIsInstance(controller.event(QEvent(QEvent.User)), bool)
                self.assertIsInstance(QCoreApplication.sendEvent(controller, QEvent(QEvent.User)), bool)
                failures = []
                controller.failed.connect(lambda index, text: failures.append((index, text)))
                controller.cancel(0)
                self.assertEqual(failures[0][0], 0)
                with self.assertRaisesRegex(ValueError, '取消'):
                    controller.adopt_preview({}, None)
            finally:
                owner.close()
                window.close()

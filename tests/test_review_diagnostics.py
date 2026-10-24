"""Local synthetic diagnostics, privacy boundaries and worker IPC regressions."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import qInstallMessageHandler, qWarning
from template_ai.review_tool import diagnostics as d


class ReviewDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.previous = qInstallMessageHandler(lambda *args: None)
        self.addCleanup(lambda: qInstallMessageHandler(self.previous))
        self.addCleanup(self.temp.cleanup)

    def open(self):
        log = d.start_diagnostics(self.root, role='test')
        self.addCleanup(log.close)
        return log

    def test_disabled_by_default_creates_nothing(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(d.start_diagnostics())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_canary_and_native_warning_kept_locally_not_in_summary_or_stdout(self):
        output = io.StringIO()
        log = self.open()
        with contextlib.redirect_stdout(output):
            qWarning(d.CANARY)
            qWarning('SYNTHETIC DirectWrite FontSecret C:/synthetic/private.ai')
        summary = log.safe_summary()
        log.close()
        self.assertEqual(summary['canary_messages'], 1)
        self.assertEqual(summary['directwrite_messages'], 1)
        self.assertEqual(summary['font_messages'], 1)
        self.assertEqual(output.getvalue(), '')
        self.assertNotIn('FontSecret', json.dumps(summary))
        self.assertNotIn('private.ai', json.dumps(summary))
        events = [json.loads(line) for line in log.path.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(events[0]['event'], 'start')
        self.assertIn('FontSecret', events[2]['message'])
        self.assertEqual(events[-1]['event'], 'summary')

    def test_restores_previous_handler_and_never_overwrites_logs(self):
        seen = []
        qInstallMessageHandler(lambda kind, ctx, msg: seen.append(msg))
        first = self.open()
        qWarning('before-close')
        first.close()
        old_bytes = first.path.read_bytes()
        qWarning('after-close')
        second = self.open()
        second.close()
        self.assertNotEqual(first.path, second.path)
        self.assertEqual(first.path.read_bytes(), old_bytes)
        self.assertEqual(seen, ['before-close', 'after-close'])

    def test_bounded_log_records_dropped_messages(self):
        with patch.object(d, 'MAX_LOG_BYTES', 32768):
            log = self.open()
            for _ in range(30):
                qWarning('Synthetic text ' * 300)
            log.close()
        self.assertLess(log.path.stat().st_size, 32768)
        self.assertGreater(log.safe_summary()['dropped_messages'], 0)
        self.assertEqual(log.safe_summary()['qt_messages'], 30)

    def test_no_stderr_pythonw_does_not_allocate_console_or_use_stdout(self):
        qInstallMessageHandler(None)
        log = self.open()
        output = io.StringIO()
        with patch('sys.stderr', None), contextlib.redirect_stdout(output):
            qWarning(d.CANARY)
        self.assertEqual(output.getvalue(), '')
        self.assertEqual(log.safe_summary()['canary_messages'], 1)

    def test_remote_directory_rejected_before_file_creation(self):
        with self.assertRaises(Exception):
            d.start_diagnostics('https://example.invalid/diagnostics', role='test')
        self.assertEqual(list(self.root.iterdir()), [])

    def test_environment_opt_in_and_double_install_protection(self):
        with patch.dict(os.environ, {d.ENVIRONMENT_VARIABLE: str(self.root)}):
            log = d.start_diagnostics(role='test')
            self.addCleanup(log.close)
            with self.assertRaises(RuntimeError):
                d.start_diagnostics(role='test')
        self.assertTrue(log.path.is_file())


if __name__ == '__main__':
    unittest.main()

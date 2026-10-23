"""Subprocess tests retain the opt-in offline guard inside the launched process."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / 'tools' / 'local_start.py'


class LocalStartTests(unittest.TestCase):
    def run_launcher(self, *arguments, no_site=False):
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        command = [sys.executable]
        if no_site: command.append('-S')
        return subprocess.run([*command, str(LAUNCHER), *arguments], cwd=ROOT, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=75)

    def test_ready_preflight_does_not_create_working_data(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp) / 'not-created'
            result = self.run_launcher('--check', '--data-dir', str(data))
            self.assertEqual(result.returncode, 0, result.stdout[-2000:])
            self.assertIn('未建立私人資料庫', result.stdout)
            self.assertFalse(data.exists())

    def test_missing_dependencies_are_plain_and_never_installed(self):
        result = self.run_launcher('--check', no_site=True)
        self.assertEqual(result.returncode, 2, result.stdout[-2000:])
        self.assertIn('沒有下載或安裝任何套件', result.stdout)
        self.assertIn('PySide6 尚未安裝', result.stdout)
        self.assertNotIn('Traceback', result.stdout)

    def test_remote_location_is_rejected_before_preflight_or_launch(self):
        result = self.run_launcher('--check', '--data-dir', r'\\example.invalid\private-data')
        self.assertEqual(result.returncode, 2)
        self.assertIn('只接受本機', result.stdout)
        self.assertNotIn('example.invalid', result.stdout)

    def test_real_application_capture_and_manual_support_export(self):
        from template_ai.offline_support import read_support_bundle
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); data = root / 'private-local-data'; image = root / 'window.png'; report = root / 'support.zip'
            result = self.run_launcher('--data-dir', str(data), '--capture', str(image))
            self.assertEqual(result.returncode, 0, result.stdout[-2500:])
            self.assertTrue(image.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
            result = self.run_launcher('--data-dir', str(data), '--support-report', str(report))
            self.assertEqual(result.returncode, 0, result.stdout[-2500:])
            public = read_support_bundle(report.read_bytes())
            self.assertTrue(any(row['code'] == 'APP_STARTED' for row in public['events']))
            self.assertNotIn('private-local-data', str(public))

"""Actual launcher protocols: local JSON pipes and closed module allow-list."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from template_ai.launch import desktop_arguments, dispatch_worker

ROOT = Path(__file__).resolve().parents[1]


class FrozenLaunchTests(unittest.TestCase):
    def test_existing_worker_protocol_through_actual_app_keeps_json_stdout(self):
        with tempfile.TemporaryDirectory() as root:
            process = subprocess.run([sys.executable, str(ROOT / 'app.py'), '-m',
                'template_ai.coverage_command', root, 'BATCHES'], input=b'{}',
                capture_output=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stderr.decode('utf-8', 'replace')[-2000:])
            self.assertEqual(json.loads(process.stdout), dict(result=dict(rows=[], total=0, offset=0)))

    def test_untrusted_module_cannot_execute_through_desktop_launcher(self):
        with patch('runpy.run_module') as execute:
            with self.assertRaises(ValueError): dispatch_worker(['-m', 'os'])
            with self.assertRaises(ValueError): dispatch_worker(['-m'])
            execute.assert_not_called()

    def test_frozen_restore_opens_same_executable_without_nonexistent_app_script(self):
        with patch.object(sys, 'frozen', True, create=True):
            self.assertEqual(desktop_arguments(Path('test copy')), ['--data-dir', 'test copy'])

    def test_python_restore_retains_existing_app_script_entry(self):
        with patch.object(sys, 'frozen', False, create=True):
            arguments = desktop_arguments('data copy')
            self.assertEqual(Path(arguments[0]), ROOT / 'app.py')
            self.assertEqual(arguments[1:], ['--data-dir', 'data copy'])

    def test_gui_arguments_are_not_dispatched_as_background_work(self):
        self.assertFalse(dispatch_worker(['--data-dir', 'data']))

    def test_child_pipe_works_when_started_outside_the_source_checkout(self):
        with tempfile.TemporaryDirectory() as root:
            code = ('import sys;sys.path.insert(0,' + repr(str(ROOT)) + ');'
                    'from template_ai.coverage_command import run_command;'
                    'import json;print(json.dumps(run_command(' + repr(root) + ',"BATCHES",{})))')
            result = subprocess.run([sys.executable, '-c', code], cwd=root,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertEqual(json.loads(result.stdout)['total'], 0)

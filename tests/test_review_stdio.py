"""Real pipe ownership plus bounded windowless-worker bootstrap checks."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from template_ai.review_tool import stdio


class AuthoredHandles:
    """Use real local pipe descriptors to exercise duplicate ownership."""

    invalid_handle = -1

    def __init__(self, descriptor, file_type=3, fail_conversion=False):
        self.descriptor = descriptor
        self.kind = file_type
        self.fail_conversion = fail_conversion
        self.duplicates = []
        self.closed_handles = []

    def standard(self, identity):
        return self.descriptor

    def file_type(self, handle):
        return self.kind

    def duplicate(self, handle):
        duplicate = os.dup(handle)
        self.duplicates.append(duplicate)
        return duplicate

    def file_descriptor(self, handle):
        if self.fail_conversion:
            raise OSError('authored conversion failure')
        return handle

    def close_handle(self, handle):
        self.closed_handles.append(handle)
        os.close(handle)


class ReviewStdioTests(unittest.TestCase):
    def setUp(self):
        self.read_descriptor, self.write_descriptor = os.pipe()
        self.addCleanup(os.close, self.read_descriptor)
        self.addCleanup(os.close, self.write_descriptor)

    def test_restored_protocol_writes_utf8_and_closes_only_its_duplicate(self):
        handles = AuthoredHandles(self.write_descriptor)
        stream = stdio._open_redirected_stream(-11, handles)
        stream.write('{"message":"判讀進度"}\n')
        stream.close()
        self.assertEqual(os.read(self.read_descriptor, 256).decode('utf-8'),
                         '{"message":"判讀進度"}\n')
        os.fstat(self.write_descriptor)  # The parent's handle remains usable.
        with self.assertRaises(OSError):
            os.fstat(handles.duplicates[0])
        self.assertEqual(handles.closed_handles, [])

    def test_invalid_and_console_handles_are_never_duplicated(self):
        for descriptor, kind in [(None, 3), (0, 3), (-1, 3),
                                 (self.write_descriptor, 2),
                                 (self.write_descriptor, 0)]:
            with self.subTest(descriptor=descriptor, kind=kind):
                handles = AuthoredHandles(descriptor, file_type=kind)
                self.assertIsNone(stdio._open_redirected_stream(-11, handles))
                self.assertEqual(handles.duplicates, [])

    def test_conversion_failure_closes_duplicate_and_preserves_parent(self):
        handles = AuthoredHandles(self.write_descriptor, fail_conversion=True)
        self.assertIsNone(stdio._open_redirected_stream(-11, handles))
        self.assertEqual(handles.closed_handles, handles.duplicates)
        os.fstat(self.write_descriptor)
        with self.assertRaises(OSError):
            os.fstat(handles.duplicates[0])

    def test_stream_wrapper_failure_closes_owned_descriptor(self):
        handles = AuthoredHandles(self.write_descriptor)
        with patch.object(stdio.os, 'fdopen', side_effect=OSError('authored wrapper failure')):
            self.assertIsNone(stdio._open_redirected_stream(-11, handles))
        os.fstat(self.write_descriptor)
        with self.assertRaises(OSError):
            os.fstat(handles.duplicates[0])

    def test_existing_output_streams_are_not_replaced(self):
        output, error = io.StringIO(), io.StringIO()
        with patch.object(sys, 'stdout', output), patch.object(sys, 'stderr', error), \
                patch.object(stdio, '_WindowsHandles') as adapter:
            self.assertTrue(stdio.prepare_standard_streams(redirected=True))
            self.assertIs(sys.stdout, output)
            self.assertIs(sys.stderr, error)
            adapter.assert_not_called()

    def test_normal_gui_does_not_request_handles_or_require_stdout(self):
        with patch.object(sys, 'stdout', None), patch.object(sys, 'stderr', None), \
                patch.object(stdio, '_WindowsHandles') as adapter:
            self.assertFalse(stdio.prepare_standard_streams(redirected=False))
            adapter.assert_not_called()

    def test_worker_without_protocol_output_exits_immediately_before_reading_request(self):
        import review_app
        with patch.object(sys, 'argv', ['review_app.py', '--analysis-worker', 'not-read.json']), \
                patch.object(review_app, 'default_data_dir') as private_store, \
                patch.object(stdio, 'prepare_standard_streams', return_value=False):
            self.assertEqual(review_app.main(), stdio.WORKER_STDOUT_UNAVAILABLE)
            private_store.assert_not_called()

    def test_missing_windows_stream_recovers_through_owned_pipe_adapter(self):
        output = io.StringIO()
        with patch.object(stdio.os, 'name', 'nt'), patch.object(sys, 'stdout', None), \
                patch.object(sys, 'stderr', io.StringIO()), \
                patch.object(stdio, '_WindowsHandles') as adapter, \
                patch.object(stdio, '_open_redirected_stream', return_value=output) as recover:
            self.assertTrue(stdio.prepare_standard_streams(redirected=True))
            self.assertIs(sys.stdout, output)
            recover.assert_called_once_with(-11, adapter.return_value)

    @unittest.skipUnless(os.name == 'nt', 'native Windows pythonw/Win32 handles qualification')
    def test_native_pythonw_redirects_without_allocating_a_console(self):
        interpreter = Path(sys.executable).with_name('pythonw.exe')
        self.assertTrue(interpreter.is_file(), 'Windows Python must include pythonw.exe')
        code = (
            'import ctypes,json;'
            'from template_ai.review_tool.stdio import prepare_standard_streams;'
            'ready=prepare_standard_streams(redirected=True);'
            'print(json.dumps({"ready":ready,"console":bool(ctypes.windll.kernel32.GetConsoleWindow()),'
            '"message":"判讀進度"},ensure_ascii=False),flush=True)'
        )
        result = subprocess.run([str(interpreter), '-c', code],
            cwd=Path(__file__).resolve().parents[1], capture_output=True,
            timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
        self.assertEqual(json.loads(result.stdout.decode('utf-8')),
                         dict(ready=True, console=False, message='判讀進度'))


if __name__ == '__main__':
    unittest.main()

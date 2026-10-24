"""Synthetic Windows boundary tests. No installed-Illustrator fidelity claim."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtCore import QEventLoop, QProcess, QTimer, QSizeF
from PySide6.QtGui import QPainter, QPdfWriter, QPageSize, QFont
from PySide6.QtWidgets import QApplication, QFileDialog

from template_ai.review_tool import illustrator_bridge as bridge
from template_ai.review_tool.window import ReviewWindow

APP = QApplication.instance() or QApplication([])
NOTICE = ('This is an Adobe Illustrator File that was saved without PDF Content. '
          'Re-saved from Adobe Illustrator with Create PDF Compatible File option turned on.')


def pdf(path, text='SYNTHETIC ARTWORK', pages=1):
    writer = QPdfWriter(str(path))
    writer.setResolution(72)
    writer.setPageSize(QPageSize(QSizeF(600, 300), QPageSize.Unit.Point))
    painter = QPainter(writer)
    painter.setFont(QFont('Arial', 9))
    for page in range(pages):
        if page:
            writer.newPage()
        painter.drawText(20, 60, text)
        painter.drawRect(20, 90, 180, 90)
    painter.end()
    del writer


class IllustratorBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / '合成 $literal & artwork.ai'
        self.source.write_bytes(b'%!PS-Adobe-3.0\n%%Creator: Synthetic\n')
        self.original = self.source.read_bytes()

    def tearDown(self):
        APP.processEvents()
        self.temp.cleanup()

    def prepared(self):
        return bridge.prepare(self.source, self.root / 'bridge')

    def rejects(self, code, job, info, response='OK|1'):
        with self.assertRaises(bridge.BridgeError) as caught:
            bridge.validate_result(job, info, response)
        self.assertEqual(caught.exception.code, code)

    def test_unique_outputs_json_escape_and_original_preservation(self):
        job, info = self.prepared()
        second, _ = self.prepared()
        self.assertNotEqual(job, second)
        generated = (job / 'run.jsx').read_text(encoding='utf-8')
        self.assertIn(json.dumps(str(self.source.resolve()), ensure_ascii=True), generated)
        self.assertEqual(self.original, self.source.read_bytes())
        self.assertFalse(Path(info['request']['output']).exists())

    def test_rejects_non_ai_and_missing_source(self):
        for path in [self.root / 'missing.ai', self.root / 'input.pdf']:
            with self.assertRaises(bridge.BridgeError):
                bridge.prepare(path, self.root / 'bridge')

    def test_valid_two_page_pdf_and_private_provenance(self):
        job, info = self.prepared()
        pdf(job / 'compatible.pdf', pages=2)
        result = bridge.validate_result(job, info, 'OK|2')
        self.assertEqual(result, job / 'compatible.pdf')
        self.assertEqual(info['page_count'], 2)
        self.assertEqual(info['visual_fidelity'], 'NOT_VERIFIED')
        self.assertEqual(self.original, self.source.read_bytes())

    def test_page_mismatch_is_not_accepted(self):
        job, info = self.prepared()
        pdf(job / 'compatible.pdf')
        self.rejects('INVALID_PDF', job, info, 'OK|2')

    def test_missing_output_is_not_accepted(self):
        job, info = self.prepared()
        self.rejects('INVALID_PDF', job, info)

    def test_corrupt_output_is_not_accepted(self):
        job, info = self.prepared()
        (job / 'compatible.pdf').write_bytes(b'not a PDF')
        self.rejects('INVALID_PDF', job, info)

    def test_notice_copy_is_not_artwork(self):
        job, info = self.prepared()
        pdf(job / 'compatible.pdf', NOTICE)
        self.rejects('PLACEHOLDER', job, info)

    def test_changed_source_is_not_accepted(self):
        job, info = self.prepared()
        pdf(job / 'compatible.pdf')
        self.source.write_bytes(self.original + b'changed')
        self.rejects('SOURCE_CHANGED', job, info)

    def test_cancelled_late_output_is_not_accepted(self):
        job, info = self.prepared()
        pdf(job / 'compatible.pdf')
        (job / 'cancel').touch()
        self.rejects('CANCELLED', job, info)

    def test_raw_adobe_error_is_redacted(self):
        job, info = self.prepared()
        self.rejects('EXPORT_FAILED', job, info, 'Private filename / client content')
        self.assertNotIn('Private', str(bridge.BridgeError('Private filename')))

    def test_known_host_error_is_actionable(self):
        job, info = self.prepared()
        self.rejects('SOURCE_OPEN', job, info, 'SOURCE_OPEN')

    def test_no_install_does_not_create_job_or_start_process(self):
        adapter = bridge.IllustratorBridge(self.root / 'bridge')
        with patch.object(bridge, 'available', return_value=False):
            with self.assertRaises(bridge.BridgeError) as caught:
                adapter.start(self.source)
        self.assertEqual(caught.exception.code, 'NOT_INSTALLED')
        self.assertFalse((self.root / 'bridge').exists())
        self.assertFalse(adapter.is_running())

    def fake_host(self, mode='success'):
        adapter = bridge.IllustratorBridge(self.root / 'bridge')
        events = {'ready': [], 'failure': [], 'finished': 0}
        loop = QEventLoop()
        adapter.ready.connect(lambda *args: events['ready'].append(args))
        adapter.failure.connect(lambda value: events['failure'].append(value))
        def done():
            events['finished'] += 1
            loop.quit()
        adapter.finished.connect(done)
        set_program, set_arguments = QProcess.setProgram, QProcess.setArguments
        commands = []
        def program(process, value):
            commands.append(value)
            return set_program(process, sys.executable if mode != 'missing-host' else str(self.root / 'missing.exe'))
        def arguments(process, values):
            commands.append(values)
            code = "import time; time.sleep(0.1); print('OK|1',end='')"
            if mode == 'timeout':
                code = 'import time; time.sleep(20)'
            elif mode == 'overflow':
                code = "print('x'*2048,end='')"
            return set_arguments(process, ['-c', code])
        if mode == 'timeout':
            adapter.TIMEOUT_MS = 80
        with patch.object(bridge, 'available', return_value=True), patch.object(QProcess, 'setProgram', program), patch.object(QProcess, 'setArguments', arguments):
            adapter.start(self.source)
        pdf(adapter.job / 'compatible.pdf')
        if mode == 'cancel':
            QTimer.singleShot(20, adapter.stop)
        deadline = QTimer()
        deadline.setSingleShot(True)
        deadline.timeout.connect(loop.quit)
        deadline.start(7000)
        loop.exec()
        deadline.stop()
        if adapter.is_running():
            adapter.stop()
            adapter.process.waitForFinished(3000)
            self.fail('Synthetic helper did not finish')
        self.assertEqual(events['finished'], 1)
        self.assertEqual(commands[1][0], '-I')
        self.assertTrue(commands[1][1].endswith('illustrator_host.py'))
        return events

    def test_asynchronous_helper_success(self):
        events = self.fake_host()
        self.assertEqual(len(events['ready']), 1)
        self.assertEqual(events['failure'], [])

    def test_helper_timeout_ignores_existing_result(self):
        events = self.fake_host('timeout')
        self.assertEqual(events['ready'], [])
        self.assertEqual(events['failure'], [bridge.MESSAGES['TIMEOUT']])

    def test_helper_cancel_ignores_existing_result(self):
        events = self.fake_host('cancel')
        self.assertEqual(events['ready'], [])
        self.assertEqual(events['failure'], [bridge.MESSAGES['CANCELLED']])

    def test_helper_failed_start_is_reported_once(self):
        events = self.fake_host('missing-host')
        self.assertEqual(events['ready'], [])
        self.assertEqual(events['failure'], [bridge.MESSAGES['HOST_FAILED']])

    def test_helper_oversized_output_is_rejected(self):
        events = self.fake_host('overflow')
        self.assertEqual(events['ready'], [])
        self.assertEqual(events['failure'], [bridge.MESSAGES['HOST_FAILED']])

    def test_ui_copy_preserves_original_and_safe_report_redacts_provenance(self):
        window = ReviewWindow(self.root / 'session')
        try:
            original = window.add_files([self.source])[0]
            window.store.stage_status(original['id'], 'FAILED', 'synthetic failure')
            job, info = self.prepared()
            pdf(job / 'compatible.pdf')
            result = bridge.validate_result(job, info, 'OK|1')
            window._illustrator_ready(str(result), info)
            self.assertEqual(len(window.store.sources()), 2)
            self.assertEqual(original['status'], 'FAILED')
            self.assertIsNone(original['analysis'])
            self.assertEqual(window.store.sources()[1]['derived_from']['source_sha256'], bridge.digest(self.source))
            report = json.dumps(window.store.safe_report(), ensure_ascii=False)
            self.assertNotIn(str(self.source), report)
            self.assertNotIn(bridge.digest(self.source), report)
            self.assertIn('Illustrator', window.notice.text())
            window.store.save()
            from template_ai.review_tool.session import SessionStore
            reloaded = SessionStore(self.root / 'session')
            self.assertEqual(reloaded.sources()[1]['derived_from']['method'], 'illustrator-pdf-copy')
        finally:
            window._allow_close = True
            window.close()
            window.deleteLater()

    def test_ui_missing_install_no_dialog_or_mutation(self):
        window = ReviewWindow(self.root / 'session')
        try:
            with patch.object(bridge, 'available', return_value=False), patch.object(QFileDialog, 'getOpenFileName') as choose:
                window.import_with_illustrator()
                choose.assert_not_called()
            self.assertEqual(window.store.sources(), [])
            self.assertIn('未註冊', window.notice.text())
        finally:
            window._allow_close = True
            window.close()
            window.deleteLater()

    def test_com_host_sta_success_and_release(self):
        from types import SimpleNamespace
        from template_ai.review_tool import illustrator_host as host
        events = []
        class FakeComError(Exception):
            pass
        class App:
            def DoJavaScript(self, text):
                events.append(('script', text))
                return 'OK|2'
        application = App()
        com = SimpleNamespace(COINIT_APARTMENTTHREADED=2, CLSCTX_LOCAL_SERVER=4, IID_IDispatch='dispatch', com_error=FakeComError,
            CoInitializeEx=lambda mode: events.append(('initialize', mode)),
            MakeIID=lambda name: name,
            CoCreateInstance=lambda *args: events.append(('create', args)) or application,
            CoUninitialize=lambda: events.append(('uninitialize',)))
        modules = {'pythoncom': com, 'win32com.client': SimpleNamespace(dynamic=SimpleNamespace(Dispatch=lambda obj: obj))}
        script = self.root / 'safe.jsx'
        script.write_text('synthetic-script', encoding='utf-8')
        with patch.dict(sys.modules, modules), patch.object(host, 'registered_clsid', return_value='synthetic-clsid'):
            self.assertEqual(host.run(script), 'OK|2')
        self.assertEqual(events[0], ('initialize', 2))
        self.assertEqual(events[1][1], ('synthetic-clsid', None, 4, 'dispatch'))
        self.assertEqual(events[-1], ('uninitialize',))

    def test_com_host_missing_dependency_is_actionable(self):
        from template_ai.review_tool import illustrator_host as host
        with patch.dict(sys.modules, {'pythoncom': None}):
            self.assertEqual(host.run(self.root / 'unused'), 'MISSING_BRIDGE')

    def test_com_host_missing_registration_does_not_create_app(self):
        from types import SimpleNamespace
        from template_ai.review_tool import illustrator_host as host
        events = []
        class FakeComError(Exception):
            pass
        def missing(_):
            raise FakeComError('private registry message')
        com = SimpleNamespace(COINIT_APARTMENTTHREADED=2, com_error=FakeComError,
                              CoInitializeEx=lambda _: None, CLSIDFromProgID=missing,
                              CoUninitialize=lambda: events.append('release'))
        script = self.root / 'safe.jsx'
        script.write_text('synthetic', encoding='utf-8')
        with patch.dict(sys.modules, {'pythoncom':com, 'win32com.client':SimpleNamespace(dynamic=None)}), patch.object(host, 'registered_clsid', return_value=None):
            self.assertEqual(host.run(script), 'NOT_INSTALLED')
        self.assertEqual(events, ['release'])

    def test_installed_pywin32_host_no_registration(self):
        from template_ai.review_tool import illustrator_host as host
        if os.name != 'nt':
            self.skipTest('Windows COM runtime')
        try:
            import pythoncom
        except ImportError:
            self.skipTest('Optional pywin32 not installed')
        self.assertTrue(callable(pythoncom.MakeIID))
        script = self.root / 'safe.jsx'
        script.write_text('synthetic', encoding='utf-8')
        with patch.object(host, 'registered_clsid', return_value=None):
            self.assertEqual(host.run(script), 'NOT_INSTALLED')

    def test_network_path_rejected_before_resolution(self):
        with patch.object(Path, 'resolve', side_effect=AssertionError('Network path must not resolve')):
            with self.assertRaises((bridge.BridgeError, PermissionError)):
                bridge.local_path(r'\\server\private\source.ai')

    def test_overlong_windows_path_is_rejected(self):
        if os.name != 'nt':
            self.skipTest('Windows path constraint')
        with self.assertRaises(bridge.BridgeError) as caught:
            bridge.local_path(self.root / ('x' * 225 + '.ai'))
        self.assertEqual(caught.exception.code, 'LOCAL_IO')


    def test_jsx_control_flow_with_synthetic_adobe_dom(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node required for synthetic JSX control-flow harness; no Adobe qualification')
        harness = Path(__file__).parents[1] / 'tools/windows_review_dev/illustrator_bridge/jsx_harness.cjs'
        result = subprocess.run([node, str(harness)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['passed'], 14)


if __name__ == '__main__':
    unittest.main()

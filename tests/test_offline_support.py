import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

from PySide6.QtCore import Signal, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from template_ai.offline_runtime import OfflineAccessError, assert_local_document, assert_local_path
from template_ai.offline_support import (MAX_EVENTS, OfflineJournal, build_support_bundle,
    install_exception_reporting, missing_from_hint, read_support_bundle, save_support_bundle, validate_report)
from template_ai.offline_support_dialog import install_offline_support


APP = QApplication.instance() or QApplication([])


class OfflineSupportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.journal = OfflineJournal(self.root)

    def test_report_roundtrip_has_beginner_summary_and_no_private_content(self):
        canary = 'PRIVATE_CLIENT_王小明_0912345678_secret.ai'
        self.journal.record('IMPORT', 'ACTION_FAILED', error=ValueError(str(self.root / canary)), missing='FONT', duration_ms=25.5)
        raw = self.journal.bundle()
        data = read_support_bundle(raw)
        self.assertEqual(data['events'][-1]['error'], 'VALUE')
        self.assertEqual(data['events'][-1]['duration_ms'], 25.5)
        self.assertIn('本機字型', data['summary']['缺少資訊'])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertEqual(set(archive.namelist()), {'support.json', 'support.html', 'manifest.json'})
            for name in archive.namelist():
                body = archive.read(name)
                self.assertNotIn(canary.encode(), body)
                self.assertNotIn(str(self.root).encode(), body)
            self.assertIn('接下來怎麼做'.encode(), archive.read('support.html'))
        self.assertNotIn(canary, self.journal.path.read_text())

    def test_journal_survives_relaunch_and_marks_missing_normal_shutdown(self):
        self.journal.record('LEARNING', 'ACTION_STARTED')
        recovered = OfflineJournal(self.root)
        codes = [e['code'] for e in recovered.events]
        self.assertIn('PREVIOUS_SESSION_FOUND', codes)
        self.assertIn('PREVIOUS_SESSION_INTERRUPTED', codes)
        self.assertTrue(any(e['stage'] == 'LEARNING' for e in recovered.events))
        recovered.record('APPLICATION', 'APP_CLOSED')
        normal = OfflineJournal(self.root)
        self.assertNotEqual(normal.events[-1]['code'], 'PREVIOUS_SESSION_INTERRUPTED')

    def test_bounded_events_keep_latest_and_account_for_omitted_history(self):
        with patch.object(self.journal, '_persist'):
            for _ in range(MAX_EVENTS + 5):
                self.journal.record('INPUT', 'INPUT_CHANGED')
        self.assertEqual(len(self.journal.events), MAX_EVENTS)
        self.assertEqual(self.journal.omitted_events, 6)
        self.assertEqual(len(read_support_bundle(self.journal.bundle())['events']), MAX_EVENTS)

    def test_unknown_strings_and_private_fields_cannot_enter_report(self):
        for params in [('IMPORT', 'secret-source.ai', {}), ('PRIVATE_CLIENT', 'ACTION_FAILED', {}),
                       ('INPUT', 'ACTION_FAILED', {'missing': 'private@example.test'})]:
            with self.assertRaises(ValueError):
                self.journal.record(params[0], params[1], **params[2])
        report = self.journal.report()
        report['customer_data'] = 'private'
        with self.assertRaises(ValueError):
            validate_report(report)
        report = self.journal.report()
        report['events'][0]['source_path'] = str(self.root)
        with self.assertRaises(ValueError):
            validate_report(report)

    def test_corrupt_local_journal_is_not_copied_into_shareable_report(self):
        self.journal.path.write_text('{"private":"secret-message.ai"}')
        recovered = OfflineJournal(self.root)
        self.assertTrue(recovered.read_failed)
        self.assertIn('LOG_READ_FAILED', [e['code'] for e in recovered.events])
        self.assertNotIn(b'secret-message.ai', recovered.bundle())

    def test_storage_failure_still_allows_manual_report_export(self):
        with patch('template_ai.offline_support.os.replace', side_effect=PermissionError('private-path')):
            self.journal.record('LAYOUT', 'ACTION_STARTED')
        self.assertFalse(self.journal.persisted)
        data = read_support_bundle(self.journal.bundle())
        self.assertFalse(data['journal_persisted'])
        self.assertEqual(data['events'][-1]['code'], 'ACTION_STARTED')

    def test_save_is_atomic_exclusive_and_failure_leaves_no_partial_file(self):
        target = self.root / 'report.zip'
        raw = self.journal.bundle()
        save_support_bundle(target, raw)
        self.assertEqual(target.read_bytes(), raw)
        with self.assertRaises(FileExistsError):
            save_support_bundle(target, raw)
        failed = self.root / 'failed.zip'
        with patch('template_ai.safe_publish.publish_complete', side_effect=OSError('private')):
            with self.assertRaises(OSError):
                save_support_bundle(failed, raw)
        self.assertFalse(failed.exists())
        self.assertFalse(list(self.root.glob('.support-*.zip')))

    def test_tampered_html_and_extra_zip_entries_are_rejected(self):
        raw = self.journal.bundle()
        for mutate in ('html', 'extra'):
            out = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(raw)) as original, zipfile.ZipFile(out, 'w') as changed:
                for name in original.namelist():
                    body = original.read(name)
                    changed.writestr(name, body + b' changed' if mutate == 'html' and name == 'support.html' else body)
                if mutate == 'extra':
                    changed.writestr('../private.ai', b'secret')
            with self.assertRaises(ValueError):
                read_support_bundle(out.getvalue())

    def test_exception_hooks_store_type_without_message_or_private_trace_source(self):
        original = sys.excepthook
        notified = []
        restore = install_exception_reporting(self.journal, lambda: notified.append(True))
        try:
            with patch('sys.stderr', new_callable=io.StringIO) as stream:
                try:
                    raise ValueError('PRIVATE_EMAIL_person@example.test')
                except ValueError as error:
                    sys.excepthook(type(error), error, error.__traceback__)
                self.assertNotIn('person@example.test', stream.getvalue())
            self.assertEqual(notified, [True])
            event = self.journal.events[-1]
            self.assertEqual(event['code'], 'UNHANDLED_ERROR')
            self.assertEqual(event['error'], 'VALUE')
            self.assertIsNone(event['location'])
            self.assertNotIn(b'person@example.test', self.journal.bundle())
        finally:
            restore()
        self.assertIs(sys.excepthook, original)

    def test_unc_and_remote_paths_are_rejected_before_file_access(self):
        for path in ('//server/customer.ai', r'\\server\customer.ai', 'https://example.test/a.ai', 'file://server/share.ai'):
            with self.assertRaises(OfflineAccessError):
                assert_local_path(path)
        self.assertEqual(assert_local_path('C:/Design/local.ai'), 'C:/Design/local.ai')
        self.assertEqual(assert_local_path(self.root / 'local.ai'), self.root / 'local.ai')

    def test_remote_svg_references_are_blocked_but_displayed_urls_and_embedded_images_remain(self):
        svg = self.root / 'source.svg'
        samples = [('<image href="https://example.test/a.png"/>', 'utf-8'),
                   ('<image href="https&#58;//example.test/a.png"/>', 'utf-16'),
                   ('<style>image{fill:url(//example.test/a.svg)}</style>', 'utf-8'),
                   ('<style>@import "https://example.test/style.css"</style>', 'utf-8'),
                   ('<image href="data:image/svg+xml;base64,QQ=="/>', 'utf-8')]
        for body, encoding in samples:
            svg.write_bytes(('<svg xmlns="http://www.w3.org/2000/svg">' + body + '</svg>').encode(encoding))
            with self.assertRaises(OfflineAccessError):
                assert_local_document(svg)
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>https://example.test</text><image href="data:image/png;base64,iVBORw0KGgo="/></svg>')
        assert_local_document(svg)

    def test_svg_dependencies_cannot_hide_remote_resources_in_nested_or_disguised_svg(self):
        svg = self.root / 'source.svg'
        nested = self.root / 'inner.svg'
        nested.write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.test/a.png"/></svg>')
        disguised = self.root / 'inner.png'
        disguised.write_bytes(nested.read_bytes())
        for name in ('inner.svg', 'inner.png'):
            svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="' + name + '"/></svg>')
            with self.assertRaises(OfflineAccessError):
                assert_local_document(svg)
        svg.write_text('<?xml version="1.0"?><?xml-stylesheet type="text/css" href="local.css"?><svg xmlns="http://www.w3.org/2000/svg"/>')
        with self.assertRaises(OfflineAccessError):
            assert_local_document(svg)
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="data:image/png;base64,PHN2Zy8+"/></svg>')
        with self.assertRaises(OfflineAccessError):
            assert_local_document(svg)

    def test_local_raster_resource_is_retained_and_error_hint_is_only_a_safe_category(self):
        from PySide6.QtGui import QImage
        png = self.root / 'photo.png'
        image = QImage(4, 4, QImage.Format_RGB32)
        image.fill(Qt.white)
        self.assertTrue(image.save(str(png)))
        svg = self.root / 'source.svg'
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="photo.png"/></svg>')
        assert_local_document(svg)
        self.assertEqual(missing_from_hint('客戶PRIVATE_EMAIL@test字型未找到'), 'FONT')
        self.assertEqual(missing_from_hint('無法核對PRIVATE_EMAIL@test'), 'UNCLASSIFIED')
        report = self.journal.report()
        self.assertRegex(report['environment']['implementation_sha256'], r'^[0-9a-f]{64}$')
        self.assertEqual(report['environment']['implementation_scope'], 'APP_AND_PACKAGE_PY')

    def test_import_remote_svg_does_not_start_converter(self):
        from template_ai.importer import import_file
        svg = self.root / 'source.svg'
        svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.test/a.png"/></svg>')
        with patch('template_ai.importer._run') as run:
            with self.assertRaises(OfflineAccessError):
                import_file(svg, self.root / 'assets')
            run.assert_not_called()

    def test_python_network_guard_blocks_ipv4_ipv6_dns_and_unc_but_allows_unix(self):
        code = '''
import socket
from template_ai.offline_runtime import enable_offline_guard, OfflineAccessError
events=[]
enable_offline_guard(lambda: events.append('blocked'))
for operation in (lambda: socket.socket(socket.AF_INET), lambda: socket.socket(socket.AF_INET6), lambda: socket.getaddrinfo('example.test',443), lambda: open('//private-server/secret.ai')):
 try: operation()
 except OfflineAccessError: pass
 else: raise AssertionError('network operation was not blocked')
if hasattr(socket,'AF_UNIX'):
 s=socket.socket(socket.AF_UNIX);s.close()
assert len(events)==4,events
print('guard-pass')
'''
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('guard-pass', result.stdout)

    def test_headless_cli_exports_local_report_without_opening_main_window(self):
        target = self.root / 'cli-report.zip'
        result = subprocess.run([sys.executable, 'app.py', '--data-dir', str(self.root), '--support-report', str(target)],
                                capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = read_support_bundle(target.read_bytes())
        self.assertTrue(data['environment']['python_network_guard'])
        self.assertIn('APP_STARTED', [e['code'] for e in data['events']])
        self.assertNotIn(str(self.root), result.stdout + result.stderr)

    def test_report_export_still_works_without_site_packages_or_qt(self):
        target = self.root / 'no-qt-report.zip'
        result = subprocess.run([sys.executable, '-S', 'app.py', '--data-dir', str(self.root), '--support-report', str(target)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = read_support_bundle(target.read_bytes())
        self.assertEqual(report['environment']['pyside6'], 'UNAVAILABLE')
        self.assertTrue(report['environment']['python_network_guard'])


class Window(QMainWindow):
    inputs_invalidated = Signal(int)


class OfflineSupportGuiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.window = Window()
        self.window.library = types.SimpleNamespace(root=self.root)
        self.window.tabs = QTabWidget()
        self.window.setCentralWidget(self.window.tabs)
        self.controller = install_offline_support(self.window)
        self.panel = self.controller.create_panel(self.window)
        self.window.tabs.addTab(self.panel, '問題回報')
        self.window.resize(1000, 760)
        self.window.show()
        APP.processEvents()
        self.addCleanup(self.cleanup_window)

    def cleanup_window(self):
        self.controller.close()
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()

    def test_real_panel_marks_missing_information_and_exports_same_report(self):
        self.panel.stage.setCurrentIndex(self.panel.stage.findData('IMPORT'))
        self.panel.missing.setCurrentIndex(self.panel.missing.findData('FONT'))
        QTest.mouseClick(self.panel.mark_button, Qt.LeftButton)
        APP.processEvents()
        self.assertEqual(self.panel.data['events'][-1]['missing'], 'FONT')
        self.assertIn('本機字型', self.panel.overview.toPlainText())
        target = self.root / 'gui-support.zip'
        displayed = self.panel.raw
        with patch('template_ai.offline_support_dialog.QFileDialog.getSaveFileName', return_value=(str(target), '')):
            QTest.mouseClick(self.panel.export_button, Qt.LeftButton)
        self.assertEqual(target.read_bytes(), displayed)
        self.assertIn('沒有傳送', self.panel.status.text())
        QTest.mouseClick(self.panel.details_button, Qt.LeftButton)
        APP.processEvents()
        self.assertTrue(self.panel.details.isVisible())
        self.assertEqual(json.loads(self.panel.details.toPlainText()), read_support_bundle(displayed))

    def test_corrupt_report_and_cancelled_export_preserve_current_report(self):
        before = self.panel.raw
        invalid = self.root / 'invalid.zip'
        invalid.write_bytes(b'PRIVATE_BROKEN_ARCHIVE')
        with patch('template_ai.offline_support_dialog.QFileDialog.getOpenFileName', return_value=(str(invalid), '')):
            QTest.mouseClick(self.panel.open_button, Qt.LeftButton)
        self.assertEqual(self.panel.raw, before)
        self.assertIn('原有報告仍保留', self.panel.status.text())
        with patch('template_ai.offline_support_dialog.QFileDialog.getSaveFileName', return_value=('', '')):
            QTest.mouseClick(self.panel.export_button, Qt.LeftButton)
        self.assertIn('已取消', self.panel.status.text())

    def test_status_input_hooks_never_copy_private_visible_messages(self):
        self.window.statusBar().showMessage('PRIVATE_CUSTOMER_MAIL_secret@example.test')
        self.window.inputs_invalidated.emit(19)
        self.controller.flush()
        raw = self.controller.journal.bundle()
        self.assertNotIn(b'secret@example.test', raw)
        codes = [e['code'] for e in read_support_bundle(raw)['events']]
        self.assertIn('GUI_STATUS_CHANGED', codes)
        self.assertIn('INPUT_CHANGED', codes)
        self.assertIs(install_offline_support(self.window), self.controller)


if __name__ == '__main__':
    unittest.main()

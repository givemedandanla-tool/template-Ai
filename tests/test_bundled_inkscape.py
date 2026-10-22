"""Bundle selection contract; filesystem fixtures are not native engine proof."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from template_ai.importer import inkscape_path


class BundledInkscapeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='模板 runtime space ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root/'TemplateAI'
        self.engine = self.app/'engines/inkscape'
        self.bundle = self.engine/'bin/inkscape.exe'
        self.bundle.parent.mkdir(parents=True)
        self.bundle.write_bytes(b'MZAUTHORED_BUNDLE_ROUTING_FIXTURE_NOT_A_REAL_ENGINE')
        self.library = self.engine/'bin/dependency.dll'
        self.library.write_bytes(b'AUTHORED_PUBLIC_DEPENDENCY_FIXTURE')
        rows = [dict(path=p.relative_to(self.engine).as_posix(), bytes=p.stat().st_size,
                     sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [self.bundle,self.library]]
        record = dict(schema_version=1, kind='BUNDLED_INKSCAPE_RUNTIME', version='1.4.2',
                      executable='bin/inkscape.exe', files=rows)
        self.manifest = self.engine/'manifest.json'
        self.manifest.write_text(json.dumps(record), encoding='utf-8')
        (self.app/'release-info.json').write_text(json.dumps(dict(inkscape_runtime=dict(
            version='1.4.2', manifest_sha256=hashlib.sha256(self.manifest.read_bytes()).hexdigest()))),encoding='utf-8')
        self.external = self.root/'system installed/inkscape.exe'
        self.external.parent.mkdir()
        self.external.write_bytes(b'MZAUTHORED_SYSTEM_DECOY')

    def frozen(self):
        context = patch.multiple(sys, frozen=True, executable=str(self.app/'TemplateAI.exe'),
                                 _MEIPASS=str(self.app), create=True)
        return context

    def test_frozen_prefers_bundle_even_when_external_setting_and_path_exist(self):
        with self.frozen(), patch.dict(os.environ, {'TEMPLATE_AI_INKSCAPE':str(self.external)}), patch('shutil.which',return_value=str(self.external)):
            self.assertEqual(Path(inkscape_path()).resolve(), self.bundle.resolve())

    def test_missing_bundle_does_not_fall_back_to_installed_engine(self):
        self.bundle.unlink()
        with self.frozen(), patch.dict(os.environ, {'TEMPLATE_AI_INKSCAPE':str(self.external)}), patch('shutil.which',return_value=str(self.external)):
            with self.assertRaisesRegex(ValueError, '內附|bundled'):
                inkscape_path()

    def test_source_mode_keeps_existing_explicit_external_setup(self):
        with patch.object(sys,'frozen',False,create=True), patch.dict(os.environ,{'TEMPLATE_AI_INKSCAPE':str(self.external)}):
            self.assertEqual(Path(inkscape_path()).resolve(),self.external.resolve())

    def test_changed_executable_is_rejected_instead_of_using_external(self):
        self.bundle.write_bytes(b'MZCHANGED_ENGINE')
        with self.frozen(), patch.dict(os.environ,{'TEMPLATE_AI_INKSCAPE':str(self.external)}):
            with self.assertRaisesRegex(ValueError,'內附'):
                inkscape_path()

    def test_missing_dependency_is_rejected(self):
        self.library.unlink()
        with self.frozen():
            with self.assertRaisesRegex(ValueError,'內附'):
                inkscape_path()

    def test_dependency_changed_after_first_selection_invalidates_cached_validation(self):
        with self.frozen():
            self.assertEqual(Path(inkscape_path()),self.bundle)
            self.library.write_bytes(b'B'*self.library.stat().st_size)
            with self.assertRaisesRegex(ValueError,'校驗'):
                inkscape_path()

    def test_manifest_must_match_application_pin(self):
        record=json.loads(self.manifest.read_text());record['version']='9.0'
        self.manifest.write_text(json.dumps(record))
        with self.frozen():
            with self.assertRaisesRegex(ValueError,'版本'):
                inkscape_path()

    def test_unlisted_file_is_not_silently_trusted(self):
        (self.engine/'bin/extra.dll').write_bytes(b'UNLISTED')
        with self.frozen():
            with self.assertRaisesRegex(ValueError,'清單'):
                inkscape_path()

    def test_executable_same_size_content_change_is_detected(self):
        with self.frozen():
            inkscape_path()
            self.bundle.write_bytes(b'MZ'+b'X'*(self.bundle.stat().st_size-2))
            with self.assertRaisesRegex(ValueError,'校驗'):
                inkscape_path()

    def test_broken_bundle_remains_reportable_without_private_paths(self):
        from template_ai.inkscape_runtime import runtime_report
        self.bundle.unlink()
        with self.frozen():report=runtime_report()
        self.assertEqual(report['state'],'UNAVAILABLE')
        self.assertEqual(report['error_code'],'BUNDLED_RUNTIME_INVALID')
        self.assertNotIn(str(self.root),json.dumps(report))
        self.assertNotIn(str(self.external),json.dumps(report))

    def test_safe_report_keeps_legacy_environment_schema_readable(self):
        from template_ai.offline_support import OfflineJournal,validate_report,report_summary
        self.bundle.unlink()
        with self.frozen():report=OfflineJournal(self.root/'support').report()
        validate_report(report)
        self.assertIn('內附',report['summary']['缺少資訊'])
        report['environment'].pop('inkscape_runtime')
        report['summary']=report_summary(report)
        validate_report(report)


if __name__ == '__main__':
    unittest.main()

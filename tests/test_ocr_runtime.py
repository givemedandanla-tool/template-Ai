"""OCR selection/integrity fixtures; executable bytes below are not real OCR.

The final bounded test separately invokes the actual local/staged engine's
language loader. True recognition remains in the existing analysis/EXE probes.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from template_ai import ocr_runtime
from template_ai.logo_ocr import capability


def digest(data):
    return hashlib.sha256(data).hexdigest()


class OcrRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='ocr-runtime-fixture-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.app = self.root / 'app'
        self.runtime = self.app / 'engines/tesseract'
        self.models = self.app / 'engines/ocr-models'
        self.internal = self.app / '_internal'
        for path in (self.runtime, self.models, self.internal):
            path.mkdir(parents=True, exist_ok=True)
        self.program = self.app / 'TemplateAIReview.exe'
        self.program.write_bytes(b'MZ_SYNTHETIC_APPLICATION_NOT_EXECUTABLE')
        self.executable = self.runtime / 'tesseract.exe'
        self.executable.write_bytes(b'MZ_SYNTHETIC_OCR_NOT_EXECUTABLE')
        (self.runtime / 'libtesseract.dll').write_bytes(b'SYNTHETIC_DLL_NOT_EXECUTABLE')
        (self.runtime / 'LICENSE').write_bytes(b'SYNTHETIC_RUNTIME_LICENSE')
        model_pins = {}
        for name in ocr_runtime.MODEL_BLOBS:
            raw = ('SYNTHETIC_MODEL_NOT_TRAINED:' + name).encode()
            (self.models / name).write_bytes(raw)
            model_pins[name] = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        # Local fixture pins are deliberately scoped to this test. They never
        # modify the product's fixed official model pins or formal baseline.
        self.enterContext(patch.dict(ocr_runtime.MODEL_BLOBS, model_pins, clear=True))
        rows = [dict(path=p.name, bytes=p.stat().st_size, sha256=digest(p.read_bytes()))
                for p in sorted(self.runtime.iterdir())]
        self.manifest = self.runtime / 'BUNDLED_RUNTIME.json'
        self.manifest.write_text(json.dumps(dict(schema_version=1,
            kind='BUNDLED_TESSERACT_RUNTIME', version=ocr_runtime.VERSION,
            executable='tesseract.exe', files=rows)), encoding='utf-8')
        self.pin = dict(version=ocr_runtime.VERSION, manifest_sha256=digest(self.manifest.read_bytes()),
                        executable_sha256=digest(self.executable.read_bytes()), files=len(rows))
        self.release_info = self.internal / 'release-info.json'
        self.release_info.write_text(json.dumps(dict(tesseract_runtime=self.pin)), encoding='utf-8')
        self.pin_file = self.root / 'staged-pin.json'
        self.pin_file.write_text(json.dumps(self.pin), encoding='utf-8')
        self.external = self.root / 'host-tesseract.exe'
        self.external.write_bytes(b'MZ_FOREIGN_HOST_OCR_NOT_EXECUTABLE')

    @contextmanager
    def frozen(self):
        with patch.object(sys, 'frozen', True, create=True), \
                patch.object(sys, 'executable', str(self.program)), \
                patch.object(sys, '_MEIPASS', str(self.internal), create=True):
            yield

    def assert_bundle_unavailable_without_execution(self):
        with self.frozen(), patch('template_ai.logo_ocr.subprocess.run') as run, \
                patch('template_ai.ocr_runtime.shutil.which', return_value=str(self.external)) as which:
            context = capability()
        self.assertFalse(context['available'])
        self.assertEqual(context['runtime']['origin'], 'BUNDLED')
        self.assertEqual(context['runtime']['error_code'], 'BUNDLED_OCR_RUNTIME_INVALID')
        self.assertIn('重新完整解壓', context['reason'])
        self.assertNotIn(str(self.root), json.dumps(context, ensure_ascii=False))
        run.assert_not_called()
        which.assert_not_called()

    def test_frozen_ignores_host_path_executable_models_and_source_bundle_overrides(self):
        with self.frozen(), patch.dict(os.environ, {
                'TEMPLATE_AI_TESSERACT': str(self.external),
                'TEMPLATE_AI_TESSDATA': str(self.root / 'foreign-models'),
                'TEMPLATE_AI_BUNDLED_TESSERACT_ROOT': str(self.root / 'foreign-bundle'),
                'TEMPLATE_AI_BUNDLED_TESSERACT_PIN': str(self.root / 'foreign-pin.json')}), \
                patch('template_ai.ocr_runtime.shutil.which') as which:
            context = ocr_runtime.resolve_runtime()
        self.assertTrue(Path(context['executable']).samefile(self.executable))
        self.assertTrue(Path(context['data_dir']).samefile(self.models))
        self.assertEqual(context['origin'], 'BUNDLED')
        self.assertEqual(context['policy'], 'BUNDLED_ONLY')
        self.assertEqual(context['executable_sha256'], self.pin['executable_sha256'])
        which.assert_not_called()

    def test_selected_bundle_is_the_actual_language_probe_command(self):
        result = subprocess.CompletedProcess([], 0, 'List of available languages (2):\nchi_tra\neng\n', '')
        inspected = []
        def probe(*args, **kwargs):
            directory = Path(kwargs['cwd'])
            for language in ('eng', 'chi_tra'):
                name = language + '.traineddata'
                self.assertEqual((directory / name).read_bytes(), (self.models / name).read_bytes())
            inspected.append(True)
            return result
        with self.frozen(), patch('template_ai.logo_ocr.subprocess.run', side_effect=probe) as run:
            context = capability()
        self.assertTrue(context['available'])
        self.assertEqual(set(context['languages']), {'eng', 'chi_tra'})
        command = run.call_args.args[0]
        self.assertTrue(Path(command[0]).samefile(self.executable))
        self.assertEqual(command[command.index('--tessdata-dir') + 1], '.')
        self.assertEqual(inspected, [True])
        self.assertEqual(context['runtime']['state'], 'READY')
        self.assertNotIn(str(self.root), json.dumps(context['runtime']))

    def test_missing_runtime_refuses_external_fallback(self):
        self.executable.unlink()
        self.assert_bundle_unavailable_without_execution()

    def test_missing_dependency_refuses_external_fallback(self):
        (self.runtime / 'libtesseract.dll').unlink()
        self.assert_bundle_unavailable_without_execution()

    def test_same_size_runtime_change_after_success_is_detected(self):
        with self.frozen():
            ocr_runtime.resolve_runtime()
        self.executable.write_bytes(b'X' * self.executable.stat().st_size)
        self.assert_bundle_unavailable_without_execution()

    def test_same_size_dependency_change_is_detected(self):
        path = self.runtime / 'libtesseract.dll'
        path.write_bytes(b'X' * path.stat().st_size)
        self.assert_bundle_unavailable_without_execution()

    def test_manifest_changed_alongside_runtime_still_fails_embedded_pin(self):
        record = json.loads(self.manifest.read_text())
        self.executable.write_bytes(b'MZ_DIFFERENT_SYNTHETIC_OCR')
        row = next(row for row in record['files'] if row['path'] == 'tesseract.exe')
        row.update(bytes=self.executable.stat().st_size, sha256=digest(self.executable.read_bytes()))
        self.manifest.write_text(json.dumps(record))
        self.assert_bundle_unavailable_without_execution()

    def test_unlisted_dependency_is_not_silently_loaded(self):
        (self.runtime / 'foreign.dll').write_bytes(b'NOT_IN_MANIFEST')
        self.assert_bundle_unavailable_without_execution()

    def test_model_tamper_never_falls_back_to_host_language_files(self):
        path = self.models / 'chi_tra.traineddata'
        path.write_bytes(b'X' * path.stat().st_size)
        self.assert_bundle_unavailable_without_execution()

    def test_malformed_pinned_inventory_reports_plain_failure(self):
        record = json.loads(self.manifest.read_text())
        record['files'] = [42]
        self.manifest.write_text(json.dumps(record))
        self.pin['manifest_sha256'] = digest(self.manifest.read_bytes())
        self.release_info.write_text(json.dumps(dict(tesseract_runtime=self.pin)))
        self.assert_bundle_unavailable_without_execution()

    def test_bundle_requires_both_actual_language_loaders(self):
        result = subprocess.CompletedProcess([], 0, 'List of available languages (1):\neng\n', '')
        with self.frozen(), patch('template_ai.logo_ocr.subprocess.run', return_value=result):
            context = capability()
        self.assertFalse(context['available'])
        self.assertEqual(context['runtime']['error_code'], 'BUNDLED_OCR_LANGUAGES_INVALID')

    def test_source_explicit_staged_bundle_has_same_integrity_policy(self):
        with patch.object(sys, 'frozen', False, create=True), patch.dict(os.environ, {
                'TEMPLATE_AI_BUNDLED_TESSERACT_ROOT': str(self.runtime),
                'TEMPLATE_AI_BUNDLED_TESSERACT_PIN': str(self.pin_file),
                'TEMPLATE_AI_TESSDATA': str(self.models),
                'TEMPLATE_AI_TESSERACT': str(self.external)}):
            context = ocr_runtime.resolve_runtime()
            self.assertTrue(Path(context['executable']).samefile(self.executable))
            self.executable.unlink()
            with self.assertRaisesRegex(ValueError, '內附文字辨識'):
                ocr_runtime.resolve_runtime()

    def test_source_explicit_missing_engine_does_not_select_another_host_engine(self):
        with patch.object(sys, 'frozen', False, create=True), patch.dict(os.environ, {
                'TEMPLATE_AI_BUNDLED_TESSERACT_ROOT': '',
                'TEMPLATE_AI_TESSERACT': str(self.root / 'missing.exe')}), \
                patch('template_ai.ocr_runtime.shutil.which', return_value=str(self.external)) as which:
            context = capability()
        self.assertFalse(context['available'])
        self.assertEqual(context['runtime']['origin'], 'ENV_LOCAL')
        which.assert_not_called()

    def test_fixed_model_stage_preserves_exact_bytes_and_cleans_on_child_failure(self):
        from template_ai.ocr_runtime import model_directory
        directory = None
        with patch('template_ai.ocr_runtime.uses_model_stage', return_value=True):
            with self.assertRaisesRegex(RuntimeError, 'synthetic child failed'):
                with model_directory(str(self.models), require_fixed=True) as selected:
                    directory = Path(selected)
                    self.assertNotEqual(directory, self.models)
                    self.assertEqual({p.name for p in directory.iterdir()},
                                     {'eng.traineddata', 'chi_tra.traineddata'})
                    for name in ('eng.traineddata', 'chi_tra.traineddata'):
                        self.assertEqual((directory / name).read_bytes(), (self.models / name).read_bytes())
                    raise RuntimeError('synthetic child failed')
        self.assertIsNotNone(directory)
        self.assertFalse(directory.exists())

    def test_fixed_model_stage_rejects_changed_weights_and_source_custom_preserves_selection(self):
        from template_ai.ocr_runtime import model_directory, OcrProcessingError
        changed = self.models / 'eng.traineddata'
        changed.write_bytes(b'SOURCE_ONLY_CUSTOM_MODEL_NEVER_REPLACED')
        with patch('template_ai.ocr_runtime.uses_model_stage', return_value=True):
            with self.assertRaises(OcrProcessingError) as failed:
                with model_directory(str(self.models), require_fixed=True):
                    self.fail('Modified bundled model was accepted')
            self.assertEqual(failed.exception.code, 'OCR_MODEL_STAGE_UNAVAILABLE')
            self.assertNotIn(str(self.root), str(failed.exception))
            with model_directory(str(self.models), require_fixed=False) as selected:
                self.assertEqual((Path(selected) / changed.name).read_bytes(), changed.read_bytes())
        self.assertEqual(changed.read_bytes(), b'SOURCE_ONLY_CUSTOM_MODEL_NEVER_REPLACED')

    def test_default_source_model_location_needs_no_stage_or_new_model_selection(self):
        with patch('template_ai.ocr_runtime.uses_model_stage', return_value=True), \
                patch('template_ai.ocr_runtime.tempfile.TemporaryDirectory') as temporary:
            with ocr_runtime.model_directory(None) as selected:
                self.assertIsNone(selected)
        temporary.assert_not_called()

    def test_processing_error_classifies_model_failure_without_private_stderr(self):
        error = ocr_runtime.processing_error('Error opening data file C:/PRIVATE_CUSTOMER/fonts/eng.traineddata')
        self.assertEqual(error.code, 'OCR_MODEL_INITIALIZATION_FAILED')
        self.assertNotIn('PRIVATE_CUSTOMER', str(error))
        self.assertNotIn('C:/', str(error))


class ActualLocalLanguageLoaderTests(unittest.TestCase):
    def test_actual_local_or_staged_engine_loads_english_and_traditional_chinese(self):
        if not os.environ.get('TEMPLATE_AI_BUNDLED_TESSERACT_ROOT') and not shutil.which('tesseract'):
            self.skipTest('No actual source-mode local engine; EXE qualification must use the bundled engine')
        context = capability()
        self.assertTrue(context['available'], context.get('reason'))
        self.assertEqual(set(context['languages']), {'eng', 'chi_tra'})

    def test_product_language_pins_match_the_existing_fixed_installer(self):
        import importlib.util
        path = Path(__file__).resolve().parents[1] / 'tools/install_ocr_models.py'
        spec = importlib.util.spec_from_file_location('review_ocr_model_pins', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(ocr_runtime.MODEL_BLOBS, module.FILES)
        self.assertEqual(ocr_runtime.MODEL_COMMIT, module.COMMIT)

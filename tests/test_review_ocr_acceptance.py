"""Bilingual EXE acceptance cannot pass on empty or manual-only OCR output."""
import hashlib
import json
from pathlib import Path
from contextlib import contextmanager, redirect_stdout
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from template_ai.review_tool.release_check import (
    _AUTHORED_CJK_SVG_PATH, assert_bundled_ocr, assert_positive_ocr, authored_ocr_sources,
    authored_ocr_failure_diagnostics, missing_ocr_runtime, physical_ocr_fault,
)
from template_ai.ocr_runtime import VERSION


def authored_positive_source():
    texts = ('測試有限公司', 'REVIEW DEMO', '0900-000-000', 'hello@example.com')
    fields = [dict(id=str(i), text=text, owner=None,
                   rect=dict(x=2., y=3. + i * 6., w=32., h=4.),
                   prediction=dict(owner=None, owner_status='UNCONFIRMED_LEGACY_CANDIDATE',
                                   classification='OCR_CANDIDATE', semantic={
                                       'semantic_type': 'mobile' if i == 2 else 'email' if i == 3 else 'unknown'}))
              for i, text in enumerate(texts)]
    return dict(analysis=dict(capabilities=dict(ocr_available=True, ocr_executed=True,
                                               ocr_languages=['eng', 'chi_tra'])),
                works=[dict(crop=dict(x=0., y=0., w=60., h=30.), fields=fields)])


class ReviewOcrPositiveEvidenceTests(unittest.TestCase):
    def test_complete_authored_observation_accepts_actual_expected_candidates(self):
        proof = assert_positive_ocr(authored_positive_source())
        self.assertEqual(proof['owner'], 'UNKNOWN_UNTIL_HUMAN_ASSIGNMENT')
        self.assertEqual(len(proof['matches']), 4)
        self.assertFalse(proof['real_corpus_qualified'])

    def test_ocr_execution_flag_or_unrelated_nonempty_text_cannot_replace_expected_text(self):
        for fields in ([], [dict(text='unrelated noise')]):
            source = authored_positive_source()
            source['works'][0]['fields'] = fields
            with self.subTest(fields=fields), self.assertRaisesRegex(RuntimeError, 'recognize authored text'):
                assert_positive_ocr(source)

    def test_both_actual_language_models_are_required(self):
        source = authored_positive_source()
        source['analysis']['capabilities']['ocr_languages'] = ['eng']
        with self.assertRaisesRegex(RuntimeError, 'Traditional Chinese model'):
            assert_positive_ocr(source)

    def test_wrong_chinese_word_does_not_count_as_bilingual_success(self):
        source = authored_positive_source()
        source['works'][0]['fields'][0]['text'] = '測詩有限公司'
        with self.assertRaisesRegex(RuntimeError, 'recognize authored text'):
            assert_positive_ocr(source)

    def test_chinese_tokenization_spaces_do_not_change_expected_glyphs(self):
        source = authored_positive_source()
        source['works'][0]['fields'][0]['text'] = '測 試 有限 公司'
        self.assertIn('測試有限公司', assert_positive_ocr(source)['matches'])

    def test_whole_page_and_out_of_bounds_manual_fallback_are_rejected(self):
        for rect in (dict(x=0, y=0, w=60, h=30), dict(x=50, y=1, w=20, h=2),
                     dict(x=0, y=0, w=0, h=1), dict(x=float('nan'), y=0, w=1, h=1)):
            source = authored_positive_source()
            source['works'][0]['fields'][0]['rect'] = rect
            with self.subTest(rect=rect), self.assertRaises(RuntimeError):
                assert_positive_ocr(source)

    def test_source_text_or_fabricated_owner_cannot_masquerade_as_ocr_candidate(self):
        for edit in (dict(classification='SOURCE_TEXT'), dict(owner='guessed-person')):
            source = authored_positive_source()
            source['works'][0]['fields'][0]['prediction'].update(edit)
            with self.subTest(edit=edit), self.assertRaises(RuntimeError):
                assert_positive_ocr(source)

    def test_ocr_text_must_reach_existing_semantic_recognizer(self):
        source = authored_positive_source()
        source['works'][0]['fields'][3]['prediction']['semantic']['semantic_type'] = 'unknown'
        with self.assertRaisesRegex(RuntimeError, 'semantic candidate recognizer'):
            assert_positive_ocr(source)

    def test_embedded_six_glyph_outlines_match_recorded_open_font_provenance(self):
        path = Path(__file__).parent / 'fixtures/review_ocr_outline_provenance.json'
        provenance = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(provenance['text'], '測試有限公司')
        self.assertEqual(provenance['license'], 'SIL Open Font License 1.1')
        self.assertEqual(provenance['outline_sha256'], hashlib.sha256(_AUTHORED_CJK_SVG_PATH.encode()).hexdigest())
        self.assertGreater(len(_AUTHORED_CJK_SVG_PATH), 100)

    def test_bilingual_sources_enter_actual_import_contract_and_raster_pdf_has_no_text_layer(self):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtPdf import QPdfDocument
        from PySide6.QtCore import QBuffer, QIODevice
        from template_ai.review_tool.session import SessionStore

        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as raw:
            sources = authored_ocr_sources(raw)
            self.assertEqual([path.suffix for path in sources], ['.svg', '.pdf'])
            self.assertNotIn('<text', sources[0].read_text(encoding='utf-8'))
            session = SessionStore(Path(raw) / 'data')
            self.assertEqual(len(session.add_files([str(path) for path in sources])), 2)
            # QFile-backed PDF objects can retain a Windows handle until their
            # C++ destructor runs. Read the real file bytes into an owned memory
            # device and explicitly release the document before temp cleanup.
            device = QBuffer()
            device.setData(sources[1].read_bytes())
            self.assertTrue(device.open(QIODevice.OpenModeFlag.ReadOnly))
            document = QPdfDocument()
            try:
                document.load(device)
                self.assertEqual(document.status(), QPdfDocument.Status.Ready)
                selection = document.getAllText(0)
                self.assertEqual(selection.text(), '')
                del selection
            finally:
                document.close()
                del document
                device.close()
        self.assertIsNotNone(app)

    def test_failure_diagnostics_print_bounded_authored_text_and_refuse_nonfixture_data(self):
        from PySide6.QtGui import QImage

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = authored_positive_source()
            source['path'] = str(root / 'DEMO-bilingual-outline.svg')
            Path(source['path']).write_text('<svg/>', encoding='utf-8')
            with self.assertRaises(FileNotFoundError):
                authored_ocr_failure_diagnostics(source, root, {'executable': sys.executable})
            (root / 'SYNTHETIC_ONLY').write_text('NO_PRIVATE_DATA', encoding='ascii')
            image = root / 'preview.png'
            pixels = QImage(8, 8, QImage.Format.Format_RGB32)
            pixels.fill('white')
            self.assertTrue(pixels.save(str(image)))
            source['analysis']['pages'] = [dict(image=str(image), width_mm=2., height_mm=2.)]
            log = io.StringIO()
            with redirect_stdout(log):
                diagnostic = authored_ocr_failure_diagnostics(source, root, {'executable': sys.executable})
            self.assertEqual(diagnostic['actual_fields'][0]['text'], '測試有限公司')
            self.assertIn('AUTHORED_OCR_FAILURE_DIAGNOSTICS:', log.getvalue())
            self.assertEqual(diagnostic['scope'], 'AUTHORED_FIXTURE_ONLY_NOT_USER_DATA')
            self.assertNotIn(str(root), log.getvalue())
            page = diagnostic['pages'][0]
            self.assertEqual(page['image_path_features']['basename'], 'preview.png')
            self.assertEqual(page['image_path_features']['resolved_length'], len(str(image.resolve())))
            for key, transport in (('diagnostic_replay', 'LEGACY_FILENAME'),
                                   ('diagnostic_stdin_replay', 'STDIN_BINARY_IMAGE')):
                replay = page[key]
                self.assertEqual(replay['image_transport'], transport)
                self.assertTrue(replay['not_release_qualification'])
                self.assertEqual(replay['image_sha256'], page['image_sha256'])
                self.assertNotEqual(replay['exit_code'], 0)  # Python is deliberately not an OCR engine.
                self.assertTrue(replay['stderr'])
                self.assertLessEqual(len(replay['stderr']), 4096)


class ReviewOcrBundleEvidenceTests(unittest.TestCase):
    def fixture(self):
        pin = dict(version=VERSION, executable_sha256='a' * 64, manifest_sha256='b' * 64, files=27)
        models = dict(files=[dict(name='eng.traineddata', sha256='c' * 64),
                                 dict(name='chi_tra.traineddata', sha256='d' * 64)])
        source = authored_positive_source()
        source['analysis']['capabilities']['ocr_runtime'] = dict(
            origin='BUNDLED', policy='BUNDLED_ONLY', version=VERSION,
            executable_sha256=pin['executable_sha256'], runtime_manifest_sha256=pin['manifest_sha256'],
            verified_files=27)
        source['analysis']['pages'] = [dict(ocr_evidence=dict(executable_sha256='a' * 64,
            image_transport='STDIN_BINARY_IMAGE',
            models=[dict(language='eng', sha256='c' * 64), dict(language='chi_tra', sha256='d' * 64)]))]
        return source, pin, models

    def test_actual_version_binary_manifest_and_both_inference_models_match(self):
        source, pin, models = self.fixture()
        proof = assert_bundled_ocr(source, pin, models, 'tesseract v' + VERSION)
        self.assertEqual(proof['runtime_origin'], 'BUNDLED')
        self.assertEqual(proof['models'], ['eng', 'chi_tra'])

    def test_host_engine_wrong_version_and_changed_models_cannot_pass(self):
        for mutation in ('host', 'version', 'binary', 'model', 'filename', 'no-proof'):
            source, pin, models = self.fixture()
            version = 'tesseract v' + VERSION
            if mutation == 'host':
                source['analysis']['capabilities']['ocr_runtime']['origin'] = 'SYSTEM_PATH'
            elif mutation == 'version':
                version = 'tesseract v5.3.0'
            elif mutation == 'binary':
                source['analysis']['capabilities']['ocr_runtime']['executable_sha256'] = 'e' * 64
            elif mutation == 'model':
                source['analysis']['pages'][0]['ocr_evidence']['models'].pop()
            elif mutation == 'filename':
                source['analysis']['pages'][0]['ocr_evidence']['image_transport'] = 'LEGACY_FILENAME'
            else:
                source['analysis']['pages'] = []
            with self.subTest(mutation=mutation), self.assertRaises(RuntimeError):
                assert_bundled_ocr(source, pin, models, version)

    def test_absent_hashes_cannot_match_each_other_and_pass(self):
        source, pin, models = self.fixture()
        pin['executable_sha256'] = None
        source['analysis']['capabilities']['ocr_runtime']['executable_sha256'] = None
        with self.assertRaisesRegex(RuntimeError, 'hashes are missing'):
            assert_bundled_ocr(source, pin, models, 'tesseract v' + VERSION)


class ReviewOcrPhysicalFaultTests(unittest.TestCase):
    @contextmanager
    def source_stage_fixture(self):
        """Integrity fixture only; these bytes are deliberately not real OCR."""
        from template_ai import ocr_runtime

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            stage = root / 'build/review-release/ocr-runtime'
            stage.mkdir(parents=True)
            executable = stage / 'tesseract.exe'
            executable.write_bytes(b'SYNTHETIC_NOT_EXECUTABLE')
            manifest = stage / 'BUNDLED_RUNTIME.json'
            manifest.write_text(json.dumps(dict(schema_version=1, kind='BUNDLED_TESSERACT_RUNTIME',
                version=VERSION, executable='tesseract.exe', files=[dict(path='tesseract.exe',
                    bytes=executable.stat().st_size, sha256=hashlib.sha256(executable.read_bytes()).hexdigest())])),
                encoding='utf-8')
            pin = root / 'source-pin.json'
            pin.write_text(json.dumps(dict(version=VERSION, files=1,
                manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest())), encoding='utf-8')
            models = root / 'unchanged-models'
            models.mkdir()
            model_pins = {}
            for name in ocr_runtime.MODEL_BLOBS:
                data = ('SYNTHETIC_NOT_A_TRAINED_MODEL:' + name).encode()
                (models / name).write_bytes(data)
                model_pins[name] = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            authored = root / 'authored'
            authored.mkdir()
            (authored / 'SYNTHETIC_ONLY').write_text('NO_PRIVATE_DATA', encoding='ascii')
            selectors = {'TEMPLATE_AI_BUNDLED_TESSERACT_ROOT': str(stage),
                         'TEMPLATE_AI_BUNDLED_TESSERACT_PIN': str(pin), 'TEMPLATE_AI_TESSDATA': str(models)}
            with patch.dict(ocr_runtime.MODEL_BLOBS, model_pins, clear=True), patch.dict(os.environ, selectors):
                selected = ocr_runtime.resolve_runtime()
                capability = dict(executable=selected['executable'], runtime=ocr_runtime.runtime_report(selected))
                yield root, stage, models, authored, capability, selectors

    def test_source_stage_fault_uses_verified_owned_copy_and_restores_environment(self):
        from template_ai import ocr_runtime

        with self.source_stage_fixture() as (root, stage, models, authored, capability, selectors):
            original = {path.name: path.read_bytes() for path in stage.iterdir()}
            with self.assertRaisesRegex(RuntimeError, 'authored probe interruption'):
                with missing_ocr_runtime(capability, authored / 'ocr-quarantine'):
                    owned = Path(os.environ['TEMPLATE_AI_BUNDLED_TESSERACT_ROOT'])
                    self.assertTrue(owned.is_relative_to(authored))
                    self.assertEqual(owned.parts[-2:], ('engines', 'tesseract'))
                    self.assertFalse((owned / 'tesseract.exe').exists())
                    self.assertTrue((stage / 'tesseract.exe').is_file())
                    self.assertEqual(Path(os.environ['TEMPLATE_AI_TESSDATA']), models)
                    with self.assertRaises(ocr_runtime.OcrRuntimeError):
                        ocr_runtime.resolve_runtime()
                    raise RuntimeError('authored probe interruption')
            self.assertEqual({key: os.environ[key] for key in selectors}, selectors)
            self.assertEqual({path.name: path.read_bytes() for path in stage.iterdir()}, original)
            self.assertEqual((owned / 'tesseract.exe').read_bytes(), original['tesseract.exe'])
            self.assertEqual(ocr_runtime.resolve_runtime()['executable'], str((stage / 'tesseract.exe').resolve()))

    def test_changed_source_copy_is_rejected_before_probe_and_original_is_untouched(self):
        from template_ai import ocr_runtime

        original_copytree = shutil.copytree

        def changed_copy(source, destination):
            result = original_copytree(source, destination)
            (Path(destination) / 'tesseract.exe').write_bytes(b'AUTHORED_BAD_COPY')
            return result

        with self.source_stage_fixture() as (root, stage, models, authored, capability, selectors):
            before = (stage / 'tesseract.exe').read_bytes()
            with patch('template_ai.review_tool.release_check.shutil.copytree', side_effect=changed_copy):
                with self.assertRaises(ocr_runtime.OcrRuntimeError):
                    with missing_ocr_runtime(capability, authored / 'ocr-quarantine'):
                        self.fail('A changed copied executable must not reach the fault probe')
            self.assertEqual((stage / 'tesseract.exe').read_bytes(), before)
            self.assertEqual({key: os.environ[key] for key in selectors}, selectors)

    def test_physical_missing_and_corruption_restore_exact_original_bytes_after_failure(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            executable = root / 'package/engines/tesseract/tesseract.exe'
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b'AUTHORED_NOT_EXECUTABLE')
            manifest = executable.parent / 'BUNDLED_RUNTIME.json'
            original = b'{"AUTHORED_MANIFEST":"ORIGINAL"}'
            manifest.write_bytes(original)
            for mode in ('MISSING_EXECUTABLE', 'CORRUPT_MANIFEST'):
                with self.subTest(mode=mode), self.assertRaisesRegex(RuntimeError, 'expected probe failure'):
                    with physical_ocr_fault(executable, root / 'scratch', mode):
                        if mode == 'MISSING_EXECUTABLE':
                            self.assertFalse(executable.exists())
                        else:
                            self.assertNotEqual(manifest.read_bytes(), original)
                        raise RuntimeError('expected probe failure')
                self.assertEqual(executable.read_bytes(), b'AUTHORED_NOT_EXECUTABLE')
                self.assertEqual(manifest.read_bytes(), original)

    def test_fault_probe_refuses_external_or_system_executable(self):
        with tempfile.TemporaryDirectory() as raw:
            executable = Path(raw) / 'system/tesseract.exe'
            executable.parent.mkdir()
            executable.write_bytes(b'EXTERNAL')
            with self.assertRaisesRegex(RuntimeError, 'owned staged bundled runtime'):
                with physical_ocr_fault(executable, Path(raw) / 'scratch', 'MISSING_EXECUTABLE'):
                    self.fail('External runtime should never be modified')
            self.assertEqual(executable.read_bytes(), b'EXTERNAL')


if __name__ == '__main__':
    unittest.main()

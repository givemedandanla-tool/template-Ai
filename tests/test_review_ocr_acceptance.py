"""Bilingual EXE acceptance cannot pass on empty or manual-only OCR output."""
import hashlib
import json
from pathlib import Path
from contextlib import redirect_stdout
import io
import sys
import tempfile
import unittest

from template_ai.review_tool.release_check import (
    _AUTHORED_CJK_SVG_PATH, assert_bundled_ocr, assert_positive_ocr, authored_ocr_sources,
    authored_ocr_failure_diagnostics, physical_ocr_fault,
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
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = authored_positive_source()
            source['path'] = str(root / 'DEMO-bilingual-outline.svg')
            Path(source['path']).write_text('<svg/>', encoding='utf-8')
            with self.assertRaises(FileNotFoundError):
                authored_ocr_failure_diagnostics(source, root, {'executable': sys.executable})
            (root / 'SYNTHETIC_ONLY').write_text('NO_PRIVATE_DATA', encoding='ascii')
            log = io.StringIO()
            with redirect_stdout(log):
                diagnostic = authored_ocr_failure_diagnostics(source, root, {'executable': sys.executable})
            self.assertEqual(diagnostic['actual_fields'][0]['text'], '測試有限公司')
            self.assertIn('AUTHORED_OCR_FAILURE_DIAGNOSTICS:', log.getvalue())
            self.assertEqual(diagnostic['scope'], 'AUTHORED_FIXTURE_ONLY_NOT_USER_DATA')
            self.assertNotIn(str(root), log.getvalue())


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
            models=[dict(language='eng', sha256='c' * 64), dict(language='chi_tra', sha256='d' * 64)]))]
        return source, pin, models

    def test_actual_version_binary_manifest_and_both_inference_models_match(self):
        source, pin, models = self.fixture()
        proof = assert_bundled_ocr(source, pin, models, 'tesseract v' + VERSION)
        self.assertEqual(proof['runtime_origin'], 'BUNDLED')
        self.assertEqual(proof['models'], ['eng', 'chi_tra'])

    def test_host_engine_wrong_version_and_changed_models_cannot_pass(self):
        for mutation in ('host', 'version', 'binary', 'model', 'no-proof'):
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

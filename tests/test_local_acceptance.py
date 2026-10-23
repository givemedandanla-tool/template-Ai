from pathlib import Path
import tempfile
import unittest

from tools.local_learning_selftest import run as learning_selftest
from tools.run_source_file_scale import run as source_scale


class LocalSyntheticAcceptanceTests(unittest.TestCase):
    def test_actual_source_learning_capacity_novel_input_preview_and_stable_output(self):
        with tempfile.TemporaryDirectory() as directory:
            result=learning_selftest(Path(directory)/'isolated-test')
            self.assertEqual(result['status'],'PASS')
            self.assertEqual(result['shared_families'],2)
            self.assertEqual(result['global_templates'],0)
            self.assertEqual(result['actual_evaluated_cases'],10)
            self.assertTrue(result['actual_validation_capacity_calibrated'])
            self.assertEqual(result['maximum_validated_field_count'],4)
            self.assertEqual(result['production_qualification'],'NOT_GRANTED_SYNTHETIC_ONLY')

    def test_actual_pdf_compatible_ai_pipeline_pauses_reopens_and_fits_shared_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            result=source_scale(Path(directory)/'isolated-source-test',6)
            self.assertEqual(result['status'],'PASS');self.assertEqual(result['items'],6)
            self.assertGreaterEqual(result['actual_glyph_runs'],12)
            self.assertTrue(result['reopened_prefix_unchanged']);self.assertTrue(result['source_bytes_unchanged'])
            self.assertEqual(result['production_qualification'],'NOT_GRANTED_SYNTHETIC_BENCHMARK')

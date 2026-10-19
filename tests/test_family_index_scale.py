import unittest
from tools.benchmark_family_index import benchmark


class FamilyIndexScaleTests(unittest.TestCase):
    def test_actual_sqlite_three_thousand_metadata_rows_page_filter_reopen_without_source_claims(self):
        result=benchmark(3000)
        self.assertEqual(result['descriptor_rows'],3000)
        self.assertEqual(result['models'],300)
        self.assertEqual(result['page_size'],48)
        self.assertTrue(result['saved_query_reopened'])
        self.assertEqual(result['global_templates'],0)
        self.assertFalse(result['production_qualification'])
        self.assertEqual(result['all_source_states'],'STALE_INTENTIONALLY')

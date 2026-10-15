from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from template_ai.storage import Library
from template_ai.automatic_training import AutomaticTraining
from template_ai.similarity_preflight import structure_score,inspect_report
from template_ai.demo import demo_template
from template_ai.source_links import hash_source

APP=QApplication.instance() or QApplication([])

class SimilarityPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.library=Library(self.root/'data');self.addCleanup(self.library.close);self.service=AutomaticTraining(self.library)
        self.path=self.root/'10001.svg'
        self.path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="90mm" height="54mm" viewBox="0 0 90 54"><rect width="90" height="54" fill="white"/><text id="email" x="8" y="20" font-size="4">alex@example.test</text></svg>')

    def test_three_levels_keep_all_paths_original_bytes_and_database_unchanged(self):
        twin=self.root/'10002.svg';twin.write_bytes(self.path.read_bytes());near=self.root/'10003.svg';near.write_text(self.path.read_text().replace('alex@','a1ex@'))
        before=[(p,hash_source(p).hash) for p in [self.path,twin,near]];changes=self.library.db.total_changes
        report=self.service.preflight([self.path,twin,near]);self.assertEqual(len(report['items']),3);self.assertEqual(report['file_duplicates'],1)
        self.assertGreaterEqual(report['near_file_candidates'],1);self.assertGreaterEqual(report['artwork_duplicates'],1)
        self.assertEqual(report['template_similarity'],0);self.assertFalse(report['similarity']['automatic_merge']);self.assertEqual(self.library.db.total_changes,changes)
        for path,sha in before:self.assertEqual(hash_source(path).hash,sha)
        self.assertEqual(self.library.list_sources(),[])

    def test_exact_rendered_work_and_structure_are_separate_and_template_match_is_explicit(self):
        t=demo_template();self.library.save_template(t)
        # A deliberately different layout must not be promoted just because text matches.
        report=self.service.preflight([self.path]);self.assertEqual(report['template_similarity'],0)
        self.assertEqual(report['artwork_duplicates'],0)
        self.assertEqual(structure_score([('email',1,2,3,4)],[('email',1,2,3,4)]),1)
        self.assertEqual(structure_score([('email',1,2,3,4)],[('name',1,2,3,4)]),0)
        self.assertIsNone(structure_score([],[]))

    def test_renderer_failure_is_unknown_not_duplicate_zero_claim_or_lost_source(self):
        with patch('template_ai.similarity_preflight.import_file',side_effect=ValueError('synthetic unavailable renderer')):
            report=self.service.preflight([self.path])
        self.assertEqual(report['similarity_unknown'],1);self.assertIn('unavailable',report['similarity']['unknown'][0]['reason']);self.assertEqual(report['items'][0]['status'],'READY')

    def test_changed_source_after_preflight_is_rejected_before_job_creation(self):
        report=self.service.preflight([self.path]);self.path.write_text(self.path.read_text().replace('alex@','other@'))
        with self.assertRaisesRegex(ValueError,'預檢來源已變更'):self.service.create(report,'SYNTHETIC',True)
        self.assertEqual(self.service.store.records('AUTO_JOB'),[])

    def test_new_file_is_compared_with_registered_source_even_without_registered_works(self):
        from template_ai.importer import import_file
        self.library.add_source(self.path,import_file(self.path,self.library.assets));near=self.root/'10004.svg';near.write_text(self.path.read_text().replace('alex@','a1ex@'))
        report=self.service.preflight([near]);self.assertGreaterEqual(report['near_file_candidates'],1);self.assertTrue(any(row['left']==str(self.path) for row in report['similarity']['near_files']));self.assertEqual(len(self.library.list_sources()),1)

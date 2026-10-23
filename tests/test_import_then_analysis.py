"""An imported empty editing workspace must not suppress source analysis."""
from copy import deepcopy
import time
import unittest

from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from template_ai.gui import MainWindow
from template_ai.importer import import_file
from template_ai.demo import demo_template
from gui_wait import dispose_main_window, wait_for_gui
from training_fixture import source_work
from test_training_pipeline import pipeline_samples
import test_automatic_training as automatic_fixtures


APP = QApplication.instance() or QApplication([])


class ImportThenAnalysisTests(unittest.TestCase):
    def setUp(self):
        automatic_fixtures.AutomaticTrainingTests.setUp(self)
        self.window = MainWindow(self.library.root)

    def tearDown(self):
        dispose_main_window(self.window)
        automatic_fixtures.AutomaticTrainingTests.tearDown(self)

    job = automatic_fixtures.AutomaticTrainingTests.job
    run_job = automatic_fixtures.AutomaticTrainingTests.run_job

    def imported_workspace(self):
        self.window.source_imported(str(self.path), import_file(self.path, self.library.assets))
        self.assertIsNotNone(self.window.work)
        self.assertEqual(self.window.slots, [])
        return deepcopy(self.window.source), deepcopy(self.window.work)

    def analysed_candidates(self, source_id):
        return [work for work in self.library.artworks(source_id)
                if work['payload'].get('analysis_key')]

    def test_real_gui_import_then_source_analysis_creates_separate_labelled_candidates(self):
        source, blank = self.imported_workspace()
        before_source = self.path.read_bytes()
        result = self.run_job(self.job())
        self.assertEqual(result['phase'], 'COMPLETED_WITH_EXCEPTIONS')
        candidates = self.analysed_candidates(source['id'])
        self.assertEqual(len(candidates), 2)
        self.assertTrue(all(work['payload']['slots'] for work in candidates))
        self.assertTrue(all(work['id'] != blank['id'] for work in candidates))
        self.assertEqual(self.library.artwork(blank['id']), blank)
        self.assertEqual(self.path.read_bytes(), before_source)

    def test_same_crop_empty_workspace_does_not_hide_real_extracted_fields(self):
        self.path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="60mm" height="30mm" '
            'viewBox="0 0 60 30"><rect width="60" height="30" fill="white"/>'
            '<text x="4" y="10" font-size="4">Alex Example</text>'
            '<text x="4" y="20" font-size="3">alex@example.test</text></svg>')
        source, blank = self.imported_workspace()
        self.run_job(self.job())
        candidates = self.analysed_candidates(source['id'])
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['payload']['crop'], blank['payload']['crop'])
        self.assertTrue(candidates[0]['payload']['slots'])
        adjustment = candidates[0]['payload']['analysis_evidence']['page_boundary_adjustment']
        self.assertGreater(adjustment['original']['w'], blank['payload']['crop']['w'])
        self.assertEqual(adjustment['normalized'], blank['payload']['crop'])
        self.assertEqual(adjustment['maximum_mm'], .001)
        self.assertEqual(self.library.artwork(blank['id']), blank)

    def test_outer_background_overflow_does_not_block_valid_inner_artworks(self):
        text = self.path.read_text()
        text = text.replace('<g id="cardA">',
                            '<rect id="outer-background" width="190.01" height="60" fill="white"/>'
                            '<g id="cardA">', 1)
        self.path.write_text(text)
        source, blank = self.imported_workspace()
        result = self.run_job(self.job())
        self.assertEqual(result['items'][0]['state'], 'WAITING_REVIEW')
        candidates = self.analysed_candidates(source['id'])
        self.assertEqual(len(candidates), 2)
        self.assertTrue(all(work['payload']['slots'] for work in candidates))
        self.assertEqual(self.library.artwork(blank['id']), blank)

    def test_meaningful_page_overflow_is_rejected_without_silently_clamping(self):
        self.path.write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="60mm" height="30mm" '
            'viewBox="0 0 60 30"><rect width="60.01" height="30" fill="white"/>'
            '<text x="4" y="10" font-size="4">Alex Example</text>'
            '<text x="4" y="20" font-size="3">alex@example.test</text></svg>')
        source, blank = self.imported_workspace()
        result = self.run_job(self.job())
        self.assertEqual(result['items'][0]['state'], 'FAILED')
        self.assertIn('超出頁面', result['items'][0]['error'])
        self.assertEqual(self.analysed_candidates(source['id']), [])
        self.assertEqual(self.library.artwork(blank['id']), blank)

    def test_repeated_analysis_reuses_candidates_without_replacing_original_workspace(self):
        source, blank = self.imported_workspace()
        first = self.run_job(self.job())
        before = self.library.artworks(source['id'])
        self.assertEqual(len(self.analysed_candidates(source['id'])), 2)
        second = self.run_job(first)
        self.assertEqual(second['phase'], 'COMPLETED_WITH_EXCEPTIONS')
        self.assertEqual(self.library.artworks(source['id']), before)
        self.assertEqual(self.library.artwork(blank['id']), blank)

    def test_manual_populated_workspace_is_not_resegmented_or_overwritten(self):
        source, work = source_work(self.library, self.root, 'manual-populated.svg')
        self.assertTrue(work['payload']['slots'])
        self.run_job(self.job([self.library.source(source['id'])['current_path']]))
        self.assertEqual([row['id'] for row in self.library.artworks(source['id'])], [work['id']])
        self.assertEqual(self.library.artwork(work['id']), work)
        self.assertEqual(self.analysed_candidates(source['id']), [])

    def test_explicit_empty_manual_crop_confirmation_history_and_name_are_preserved(self):
        original = self.path.read_text()
        for intention in ('crop', 'visual', 'history', 'name'):
            with self.subTest(intention=intention):
                self.path = self.root / ('manual-' + intention + '.svg')
                self.path.write_text(original)
                source, blank = self.imported_workspace()
                payload = deepcopy(blank['payload'])
                if intention == 'crop':
                    payload['crop']['x'] = 5
                    payload['crop']['w'] -= 10
                    payload['work_width'] -= 10
                elif intention == 'visual':
                    payload['visual_confirmed'] = True
                elif intention == 'history':
                    payload['work_width'] -= 1
                else:
                    self.library.rename_artwork(blank['id'], 'Deliberately empty manual workspace')
                if intention != 'name':
                    saved = self.library.save_artwork(blank['id'], payload, blank['revision'])
                    if intention == 'history':
                        self.library.save_artwork(blank['id'], blank['payload'], saved['revision'])
                before = self.library.artwork(blank['id'])
                # Bring this test-owned editor to the revision deliberately
                # changed above, before a later subtest selects another source.
                self.window.load_work(before, source=source)
                self.run_job(self.job())
                self.assertEqual([row['id'] for row in self.library.artworks(source['id'])], [before['id']])
                self.assertEqual(self.library.artwork(before['id']), before)
                self.assertEqual(self.analysed_candidates(source['id']), [])

    def test_manual_pending_source_facts_are_not_treated_as_an_import_placeholder(self):
        source, blank = self.imported_workspace()
        facts = self.service.store.save_facts(blank['id'], [dict(
            id='manual-note', slot_id=None, text='Alex Example', object_type='TEXT',
            classification='ANNOTATION', region=dict(x=0, y=0, w=20, h=15))], 0, blank['revision'])
        self.run_job(self.job())
        self.assertEqual([row['id'] for row in self.library.artworks(source['id'])], [blank['id']])
        self.assertEqual(self.library.artwork(blank['id']), blank)
        self.assertEqual(self.service.store.get('FACTS', blank['id']), facts)
        self.assertEqual(self.analysed_candidates(source['id']), [])

    def test_approved_source_sample_and_artwork_remain_unchanged(self):
        samples, works = pipeline_samples(self.service.store, self.root, 1)
        work = works[0]
        source = self.library.source(work['source_id'])
        self.run_job(self.job([source['current_path']]))
        self.assertEqual([row['id'] for row in self.library.artworks(source['id'])], [work['id']])
        self.assertEqual(self.library.artwork(work['id']), work)
        self.assertEqual(self.service.store.get('SAMPLE', samples[0]['id']), samples[0])
        self.assertEqual(self.analysed_candidates(source['id']), [])

    def test_explicit_work_retry_does_not_expand_into_source_level_analysis(self):
        source, blank = self.imported_workspace()
        plan = self.service.retry_plan([blank['id']])
        result = self.run_job(self.service.create_retry(plan, 'SYNTHETIC_TEST', True))
        self.assertEqual(result['scope'], 'EXACT_CHANGED_WORKS_ONLY')
        self.assertEqual([row['id'] for row in self.library.artworks(source['id'])], [blank['id']])
        self.assertEqual(self.library.artwork(blank['id']), blank)
        self.assertEqual(self.analysed_candidates(source['id']), [])

    def test_real_queued_completion_refreshes_choices_without_discarding_unsaved_fields(self):
        from template_ai.automatic_training_dialog import AutomaticTrainingDialog
        source, blank = self.imported_workspace()
        self.assertEqual(self.window.work_combo.count(), 1)
        # The test actor has made a local edit, without saving it to the artwork.
        self.window.slots = [deepcopy(demo_template().slots[0])]
        unsaved = deepcopy(self.window.slots)
        dialog = AutomaticTrainingDialog(self.window)
        self.addCleanup(lambda: dialog.close() if isValid(dialog) else None)
        job = self.job()
        # The synchronous fixture import/preflight blocks Qt; let the real
        # heartbeat recover before submitting the real asynchronous worker.
        prepared = time.monotonic()
        self.assertTrue(wait_for_gui(
            lambda: self.window.runtime.last_pulse > prepared
            and self.window.runtime.admit('ANALYSIS', requested=True).allowed, 8))
        dialog.start_job(job)
        self.assertTrue(dialog.running)
        self.assertTrue(wait_for_gui(lambda: not dialog.running
                                    and self.window.execution_queue.active is None
                                    and not self.window.busy, 30))
        completed = self.service.get(job['id'])
        self.assertEqual(completed['phase'], 'COMPLETED_WITH_EXCEPTIONS',
                         str(completed.get('system_error'))[:1000])
        self.assertEqual(len(self.analysed_candidates(source['id'])), 2)
        self.assertEqual(self.window.work_combo.count(), 3)
        self.assertEqual(self.window.work_combo.currentData(), blank['id'])
        self.assertEqual(self.window.work['id'], blank['id'])
        self.assertEqual(self.window.slots, unsaved)
        self.assertEqual(self.library.artwork(blank['id']), blank)


if __name__ == '__main__':
    unittest.main()

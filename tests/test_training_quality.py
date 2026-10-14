import copy
from dataclasses import asdict
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from template_ai.demo import demo_template
from template_ai.model import Rect, Slot
from template_ai.training_quality import analyse_work, quality_rows
from template_ai.training_quality_dialog import TrainingQualityDialog
from template_ai.gui import MainWindow
from training_fixture import source_work
APP = QApplication.instance() or QApplication([])


class TrainingQualityTests(unittest.TestCase):
    def work(self):
        return {'id': 'work', 'source_id': 'source', 'name': 'Synthetic', 'revision': 1,
                'payload': {'crop': asdict(Rect(0, 0, 90, 54)), 'work_width': 90, 'work_height': 54,
                            'slots': [asdict(s) for s in demo_template().slots], 'visual_confirmed': True}}
    def test_known_semantics_do_not_invent_optional_email_or_claim_visual(self):
        work = self.work(); work['payload']['slots'] = work['payload']['slots'][:1]; before = copy.deepcopy(work)
        rows = analyse_work(work); self.assertFalse(any(r['severity'] == 'BLOCK' for r in rows)); self.assertEqual(work, before)
        self.assertIn('SOURCE_IDENTITY_UNKNOWN', [r['code'] for r in rows]); self.assertTrue(all(r['native_mapping'] == 'UNKNOWN' for r in rows))
    def test_duplicate_identity_mapping_bounds_and_bad_schema_explained(self):
        work = self.work(); work['payload']['slots'].append(copy.deepcopy(work['payload']['slots'][0])); work['payload']['slots'][1]['rect']['x'] = 999
        rows = analyse_work(work); codes = {r['code'] for r in rows}
        self.assertTrue({'DUPLICATE_ID', 'DUPLICATE_MAPPING', 'BOUNDS'} <= codes)
        self.assertFalse(next(r for r in rows if r['code'] == 'DUPLICATE_ID')['locatable'])
        work['payload']['slots'] = [{}]; self.assertEqual(analyse_work(work)[0]['code'], 'STABLE_ID')
    def test_logo_containment_is_uncertain_not_automatic_deletion(self):
        work = self.work(); work['payload']['slots'].append(asdict(Slot('logo', 'c1', Rect(5, 4, 76, 16), id='logo')))
        before = copy.deepcopy(work); rows = analyse_work(work)
        self.assertIn('CONTAINMENT_UNKNOWN', [r['code'] for r in rows]); self.assertEqual(work, before)
        self.assertTrue(all(r['severity'] == 'REVIEW' for r in rows if r['code'] == 'CONTAINMENT_UNKNOWN'))
        self.assertIn('COMPANY_BINDING', [r['code'] for r in rows])
    def test_invalid_dimensions_budget_owner_and_missing_person_name(self):
        work = self.work(); work['payload']['work_width'] = float('nan'); self.assertEqual(analyse_work(work)[0]['code'], 'DIMENSIONS')
        work = self.work(); work['payload']['slots'] *= 51; self.assertEqual(analyse_work(work)[0]['code'], 'OBJECT_BUDGET')
        work = self.work(); work['payload']['slots'][1]['owner'] = 'p2'; work['payload']['slots'][2]['owner'] = 'c_bad'
        codes = {r['code'] for r in analyse_work(work)}; self.assertTrue({'OWNER', 'MISSING_NAME'} <= codes)
    def test_stable_sort_independent_of_slot_order_and_source_bounds(self):
        work = self.work(); work['payload']['slots'][0]['rect']['x'] = -3; work['payload']['visual_confirmed'] = False
        rows = analyse_work(work); work['payload']['slots'].reverse(); self.assertEqual(analyse_work(work), rows)
        self.assertEqual(rows[0]['severity'], 'BLOCK'); self.assertEqual(analyse_work(self.work(), {'width_mm': 10, 'height_mm': 10})[0]['code'], 'SOURCE_CROP')
    def test_large_overlap_set_is_bounded_and_invalid_coordinate_not_crash(self):
        work = self.work(); base = copy.deepcopy(work['payload']['slots'][0])
        work['payload']['slots'] = [base | {'id': f'object-{i}', 'index': i} for i in range(200)]
        rows = analyse_work(work); self.assertLessEqual(len(rows), 401); self.assertIn('ISSUE_BUDGET', [r['code'] for r in rows])
        work = self.work(); work['payload']['slots'][0]['rect']['x'] = 'bad'
        self.assertIn('BOUNDS', [r['code'] for r in analyse_work(work)])


class TrainingQualityGuiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name)
        self.window = MainWindow(self.root/'data'); self.addCleanup(self.window.close)
        self.source, self.work = source_work(self.window.library, self.root, visual=False)
        payload = copy.deepcopy(self.work['payload']); payload['slots'][0]['rect']['x'] = 999
        self.work = self.window.library.save_artwork(self.work['id'], payload, self.work['revision'])
        self.d = TrainingQualityDialog(self.window); self.addCleanup(self.d.close); self.d.show(); APP.processEvents()
    def select(self, code='BOUNDS'):
        i = next(i for i, r in enumerate(self.d.rows) if r['code'] == code); self.d.table.selectRow(i); APP.processEvents()
    def test_actual_readonly_search_filter_navigation_and_stale_recovery(self):
        before = self.window.library.artwork(self.work['id']); self.select(); QTest.mouseClick(self.d.locate_button, Qt.LeftButton); APP.processEvents()
        self.assertEqual(self.window.work['id'], self.work['id']); self.assertEqual(self.window.current_slot.id, self.work['payload']['slots'][0]['id'])
        self.d.search.setText('no-match'); self.assertEqual(self.d.table.rowCount(), 0); self.d.search.setText('bounds'); self.select()
        payload = copy.deepcopy(before['payload']); payload['visual_confirmed'] = True; self.window.library.save_artwork(before['id'], payload, before['revision'])
        QTest.mouseClick(self.d.locate_button, Qt.LeftButton); self.assertIn('已變更', self.d.status.text()); self.assertTrue(self.d.reload_button.isEnabled())
        self.d.reload(); self.assertNotEqual(before, self.window.library.artwork(before['id']))
    def test_dirty_main_edit_and_backend_failure_preserve_content(self):
        self.select(); self.d.locate(); self.window.slots[0].rect.x = 8; before = copy.deepcopy(self.window.slots)
        QTest.mouseClick(self.d.locate_button, Qt.LeftButton); self.assertIn('未保存', self.d.status.text()); self.assertEqual(self.window.slots, before)
        with patch('template_ai.training_quality_dialog.quality_rows', side_effect=RuntimeError('forced index failure')): self.d.reload()
        self.assertEqual(self.d.table.rowCount(), 0); self.assertIn('未完成', self.d.status.text()); self.assertTrue(self.d.reload_button.isEnabled())
        self.d.reload(); self.assertGreater(self.d.table.rowCount(), 0)
    def test_paginated_report_and_source_entry_actual_dialog(self):
        result = quality_rows(self.window.library, offset=0, limit=1); self.assertEqual(result['scanned_works'], 1); self.assertFalse(result['full_quality_pass'])
        with self.assertRaises(ValueError): quality_rows(self.window.library, limit=201)
        with patch.object(TrainingQualityDialog, 'exec', autospec=True) as run: self.window.training_center(); self.assertEqual(run.call_count, 1)

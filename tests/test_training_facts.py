import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog
from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.gui import MainWindow
from template_ai.training_quality_dialog import TrainingQualityDialog
from training_fixture import source_work, observations
APP = QApplication.instance() or QApplication([])


class FactsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root = Path(self.tmp.name)
        self.library = Library(self.root/'data'); self.addCleanup(self.library.db.close); self.source, self.work = source_work(self.library, self.root); self.store = TrainingStore(self.library); self.obs = observations(self.work)
    def save(self): return self.store.save_facts(self.work['id'], self.obs, 0, self.work['revision'])
    def confirm(self, record): return self.store.confirm_facts(record['id'], [o['id'] for o in record['observations']], record['revision'], record['pins'], self.store.source_proof(record['id']), 'Synthetic Reviewer', True)
    def test_full_manual_text_unknown_native_and_reopen_history(self):
        before = self.library.artwork(self.work['id']); original = Path(self.source['original_path']).read_bytes(); record = self.save(); confirmed = self.confirm(record)
        self.assertEqual(self.store.facts_state(self.work['id']), 'CONFIRMED'); self.assertEqual(confirmed['confirmation']['scope'], 'EXACT_WORK_FACTS_ONLY; NOT_SAMPLE_OR_RULE_APPROVAL')
        self.assertTrue(all(o['native_mapping'] == 'UNKNOWN' for o in confirmed['observations'])); self.assertEqual(self.library.artwork(self.work['id']), before); self.assertEqual(Path(self.source['original_path']).read_bytes(), original)
        other = Library(self.library.root)
        try:
            reopened = TrainingStore(other); self.assertEqual(reopened.facts(self.work['id']), confirmed); self.assertEqual([h['action'] for h in reopened.history('FACTS', self.work['id'])], ['facts_confirmed', 'facts_saved'])
        finally: other.db.close()
        self.assertEqual(self.store.count('SAMPLE'), 0); self.assertEqual(self.store.count('RULE'), 0)
    def test_invalid_empty_duplicate_slot_region_and_prediction_fail_closed(self):
        invalids = [[], self.obs+[copy.deepcopy(self.obs[0])], [dict(self.obs[0], text='')], [dict(self.obs[0], slot_id='missing')], [dict(self.obs[0], region={'x': 91, 'y': 0, 'w': 1, 'h': 1})], [dict(self.obs[0], prior_prediction=42)], self.obs+[dict(self.obs[0], id='other')]]
        for invalid in invalids:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError): self.store.save_facts(self.work['id'], invalid, 0, self.work['revision'])
        self.assertEqual(self.store.count('FACTS'), 0)
    def test_confirmation_subset_and_unapproved_scope_are_separate(self):
        record = self.save(); proof = self.store.source_proof(record['id'])
        with self.assertRaises(ValueError): self.store.confirm_facts(record['id'], ['note'], record['revision'], record['pins'], proof, 'Reviewer')
        with self.assertRaises(ValueError): self.store.confirm_facts(record['id'], ['missing'], record['revision'], record['pins'], proof, 'Reviewer', True)
        confirmed = self.store.confirm_facts(record['id'], ['note'], record['revision'], record['pins'], proof, 'Reviewer', True); self.assertEqual(confirmed['confirmation']['observation_ids'], ['note'])
    def test_work_and_source_change_invalidate_confirmation(self):
        record = self.confirm(self.save()); payload = copy.deepcopy(self.work['payload']); payload['slots'][0]['rect']['x'] += 1
        self.library.save_artwork(self.work['id'], payload, self.work['revision']); self.assertEqual(self.store.facts_state(record['id']), 'STALE')
        with self.assertRaises(ValueError): self.store.confirm_facts(record['id'], ['note'], record['revision'], record['pins'], self.store.source_proof(record['id']), 'Reviewer', True)
    def test_source_changed_after_proof_and_record_CAS_rejected(self):
        record = self.save(); proof = self.store.source_proof(record['id']); Path(self.source['original_path']).write_text('changed')
        with self.assertRaises(ValueError): self.store.confirm_facts(record['id'], ['note'], record['revision'], record['pins'], proof, 'Reviewer', True)
        self.assertEqual(self.store.facts_state(record['id']), 'PENDING')
        with self.assertRaises(ValueError): self.store.save_facts(record['id'], self.obs, 0, self.work['revision'])
    def test_late_audit_failure_atomic_and_revocation_monotonic(self):
        record = self.save(); epoch = self.store.epoch
        with patch.object(self.library, 'event', side_effect=RuntimeError('late audit failure')), self.assertRaises(RuntimeError): self.confirm(record)
        self.assertEqual(self.store.facts(record['id']), record); self.assertEqual(self.store.epoch, epoch); self.assertEqual(len(self.store.history('FACTS', record['id'])), 1)
        confirmed = self.confirm(record); revoked = self.store.revoke_facts(record['id'], confirmed['revision'], 'needs correction'); self.assertEqual(self.store.facts_state(record['id']), 'REVOKED'); self.assertGreater(revoked['revision'], confirmed['revision'])


class FactsGuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root = Path(self.tmp.name); self.window = MainWindow(self.root/'data'); self.addCleanup(self.close)
        self.source, self.work = source_work(self.window.library, self.root); self.d = TrainingQualityDialog(self.window); self.p = self.d.facts_panel; self.addCleanup(self.d.close); self.d.show(); self.d.tabs.setCurrentWidget(self.p); APP.processEvents()
    def close(self):
        self.window.source = None; self.window.work = None; self.window.template = None; self.window.close()
    def wait(self):
        for _ in range(300):
            APP.processEvents()
            if not self.p.running: return
            QTest.qWait(10)
        self.fail('bounded background task did not finish')
    def seed(self):
        self.p.store.save_facts(self.work['id'], observations(self.work), 0, 1); self.p.load(); self.p.table.selectAll(); self.p.actor.setText('Synthetic Reviewer')
    def test_actual_add_confirm_cancel_revoke_and_entry(self):
        self.p.observed_text.setText('已校稿'); self.p.object_type.setCurrentText('ANNOTATION'); self.p.classification.setCurrentText('ANNOTATION')
        for spin, value in zip(self.p.coords, (8, 48, 20, 5)): spin.setValue(value)
        QTest.mouseClick(self.p.add_button, Qt.LeftButton); self.assertEqual(self.p.table.rowCount(), 1); self.p.table.selectRow(0); self.p.actor.setText('Synthetic Reviewer')
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.No): QTest.mouseClick(self.p.confirm_button, Qt.LeftButton); self.wait()
        self.assertIsNone(self.p.store.facts(self.work['id'])['confirmation']); self.assertTrue(self.p.confirm_button.isEnabled())
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes): QTest.mouseClick(self.p.confirm_button, Qt.LeftButton); self.wait()
        self.assertEqual(self.p.store.facts_state(self.work['id']), 'CONFIRMED')
        with patch.object(QInputDialog, 'getText', return_value=('synthetic revoke', True)): QTest.mouseClick(self.p.revoke_button, Qt.LeftButton)
        self.assertEqual(self.p.store.facts_state(self.work['id']), 'REVOKED')
        with patch.object(TrainingQualityDialog, 'exec', autospec=True) as run: self.window.training_center(); self.assertEqual(run.call_count, 1)
    def test_stale_scope_during_confirmation_and_failed_worker_controls_recover(self):
        self.seed()
        def changed(*args):
            current = self.p.store.facts(self.work['id']); self.p.store.save_facts(current['id'], current['observations'], current['revision'], 1); return QMessageBox.Yes
        with patch.object(QMessageBox, 'question', side_effect=changed): self.p.confirm(); self.wait()
        self.assertIn('版次', self.p.status.text()); self.assertIsNone(self.p.store.facts(self.work['id'])['confirmation']); self.p.load(); self.p.table.selectAll()
        with patch('template_ai.training_facts_panel.hash_source', side_effect=OSError('synthetic failure')): self.p.confirm(); self.wait()
        self.assertIn('失敗', self.p.status.text()); self.assertTrue(self.p.reload_button.isEnabled()); self.assertTrue(self.p.add_button.isEnabled())

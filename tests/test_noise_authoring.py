from gui_wait import dispose_main_window
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox
from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.noise import relative_region, normalized
from template_ai.noise_authoring_dialog import NoiseAuthoringDialog
from template_ai.gui import MainWindow
from template_ai.training_quality_dialog import TrainingQualityDialog
from training_fixture import source_work, observations
APP = QApplication.instance() or QApplication([])


def confirmed(store, work):
    facts = store.save_facts(work['id'], observations(work), 0, work['revision'])
    return store.confirm_facts(work['id'], [o['id'] for o in facts['observations']], facts['revision'], facts['pins'], store.source_proof(work['id']), 'Synthetic Reviewer', True)


class NoiseAuthorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root = Path(self.tmp.name); self.library = Library(self.root/'data'); self.addCleanup(self.library.db.close)
        self.source, self.work = source_work(self.library, self.root); self.store = TrainingStore(self.library); self.facts = confirmed(self.store, self.work)
    def propose(self, **kw):
        args = dict(work_id=self.work['id'], observation_id='note', counterexamples=[{'work_id': self.work['id'], 'observation_id': 'observation-0'}], zone=relative_region(self.work, next(o for o in self.facts['observations'] if o['id']=='note')), normalization='NONE', expected_facts_revision=self.facts['revision'], expected_epoch=self.store.epoch, actor='Synthetic Reviewer', approved=True)
        args.update(kw); return self.store.propose_noise_rule(**args)
    def test_local_and_remember_have_different_effects_preserve_source_and_slots(self):
        before = self.library.artwork(self.work['id']); original = Path(self.source['original_path']).read_bytes()
        self.store.local_noise(self.work['id'], ['note'], 0, self.facts['revision'], True); self.assertEqual(self.store.count('RULE'), 0)
        self.assertEqual(next(r for r in self.store.noise_candidates(self.work['id']) if r['observation_id']=='note')['state'], 'EXCLUDED_LOCAL')
        rule = self.propose(); self.assertEqual(rule['state'], 'PENDING'); self.assertIsNone(rule['review']); self.assertEqual(rule['literal'], '已校稿'); self.assertEqual(rule['scope']['source_extension'], '.svg')
        self.assertEqual(self.library.artwork(self.work['id']), before); self.assertEqual(Path(self.source['original_path']).read_bytes(), original); self.assertEqual(self.store.count('SAMPLE'), 0)
        other=Library(self.library.root)
        try: self.assertEqual(TrainingStore(other).get('RULE',rule['id']),rule)
        finally: other.db.close()
    def test_real_fields_logo_unknown_or_missing_confirmation_cannot_be_excluded(self):
        with self.assertRaises(ValueError): self.store.local_noise(self.work['id'], ['observation-0'], 0, self.facts['revision'], True)
        with self.assertRaises(ValueError): self.propose(observation_id='observation-0')
        updated=copy.deepcopy(self.facts['observations']); note=next(o for o in updated if o['id']=='note');note['classification']='UNKNOWN'; self.store.save_facts(self.work['id'], updated, self.facts['revision'],1)
        with self.assertRaises(ValueError): self.store.local_noise(self.work['id'], ['note'],0,self.facts['revision']+1,True)
    def test_full_unicode_normalization_explicit_zone_and_counterexamples(self):
        self.assertNotEqual(normalized('e\u0301','NONE'), 'é'); self.assertEqual(normalized('e\u0301','NFC'),'é'); self.assertNotEqual(normalized('Alex 已校稿','NONE'),'已校稿')
        for kwargs in ({'normalization':'NFC'},{'zone':{'x':0,'y':0,'w':0.1,'h':0.1}},{'counterexamples':[]},{'counterexamples':[{}]},{'counterexamples':[{'work_id':self.work['id'],'observation_id':'note'}]}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):self.propose(**kwargs)
        self.assertEqual(self.propose(normalization='NFC',normalization_approved=True)['normalization'],'NFC')
    def test_stale_preview_source_and_local_revision_fail_closed(self):
        epoch=self.store.epoch;self.store.local_noise(self.work['id'],['note'],0,self.facts['revision'],True)
        with self.assertRaises(ValueError):self.propose(expected_epoch=epoch)
        with self.assertRaises(ValueError):self.store.local_noise(self.work['id'],['note'],0,self.facts['revision'],True)
        Path(self.source['original_path']).write_text('changed')
        self.assertEqual(next(r for r in self.store.noise_candidates(self.work['id']) if r['observation_id']=='note')['state'],'STALE_LOCAL')
        with self.assertRaises(ValueError):self.propose()
    def test_rule_plus_local_late_audit_failure_rolls_back_both(self):
        epoch=self.store.epoch; event=self.library.event
        def late(entity,action):
            event(entity,action)
            if action=='training_local_noise_exclude':raise RuntimeError('late local audit')
        with patch.object(self.library,'event',side_effect=late),self.assertRaises(RuntimeError):self.propose()
        self.assertEqual(self.store.count('RULE'),0);self.assertEqual(self.store.count('LOCAL'),0);self.assertEqual(self.store.epoch,epoch)
    def test_local_undo_retains_history_and_does_not_activate_pending_rule(self):
        rule=self.propose();local=self.store.local_record(self.work['id']);self.store.clear_local_noise(self.work['id'],['note'],local['revision'],self.facts['revision'],True)
        self.assertEqual(next(r for r in self.store.noise_candidates(self.work['id']) if r['observation_id']=='note')['state'],'INCLUDED');self.assertEqual(self.store.get('RULE',rule['id'])['state'],'PENDING');self.assertEqual(self.store.history('LOCAL',self.work['id'])[0]['action'],'local_noise_cleared')


class NoiseAuthorGuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.window=MainWindow(self.root/'data');self.addCleanup(self.close)
        self.source,self.work=source_work(self.window.library,self.root);self.store=TrainingStore(self.window.library);self.facts=confirmed(self.store,self.work);self.d=TrainingQualityDialog(self.window);self.addCleanup(self.d.close);self.p=self.d.facts_panel;self.d.show();self.d.tabs.setCurrentWidget(self.p);APP.processEvents();self.p.actor.setText('Synthetic Reviewer')
    def close(self):self.window.source=None;self.window.work=None;self.window.template=None;dispose_main_window(self.window)
    def select_note(self):self.p.table.selectRow(next(i for i,o in enumerate(self.p.loaded['observations']) if o['id']=='note'));APP.processEvents()
    def test_actual_local_confirm_cancel_and_rule_authoring(self):
        self.select_note()
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):QTest.mouseClick(self.p.exclude_button,Qt.LeftButton)
        self.assertEqual(self.store.count('LOCAL'),0)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(self.p.exclude_button,Qt.LeftButton)
        self.assertEqual(self.store.count('RULE'),0)
        wizard=NoiseAuthoringDialog(self.store,self.work['id'],'note','Synthetic Reviewer',self.d);self.addCleanup(wizard.close);wizard.show();APP.processEvents();wizard.table.selectRow(0)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(wizard.save_button,Qt.LeftButton)
        self.assertEqual(wizard.saved_rule['state'],'PENDING');self.assertEqual(self.store.count('RULE'),1);self.assertEqual(self.window.library.artwork(self.work['id']),self.work)
    def test_actual_stale_wizard_and_entry_recover_without_loss(self):
        wizard=NoiseAuthoringDialog(self.store,self.work['id'],'note','Synthetic Reviewer',self.d);self.addCleanup(wizard.close);wizard.show();wizard.table.selectRow(0)
        def mutate(*args):self.store.local_noise(self.work['id'],['note'],0,self.facts['revision'],True);return QMessageBox.Yes
        with patch.object(QMessageBox,'question',side_effect=mutate):QTest.mouseClick(wizard.save_button,Qt.LeftButton)
        self.assertIsNone(wizard.saved_rule);self.assertTrue(wizard.save_button.isEnabled());self.assertIn('已变更',wizard.status.text());self.assertEqual(self.store.count('RULE'),0)
        self.select_note()
        with patch.object(NoiseAuthoringDialog,'exec',autospec=True) as run:QTest.mouseClick(self.p.remember_button,Qt.LeftButton);self.assertEqual(run.call_count,1)

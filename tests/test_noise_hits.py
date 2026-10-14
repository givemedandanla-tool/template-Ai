import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox
from template_ai.storage import Library
from template_ai.training_store import TrainingStore
from template_ai.gui import MainWindow
from template_ai.training_quality_dialog import TrainingQualityDialog
from training_fixture import source_work,observations
from test_rule_review import pending_rule
from test_noise_authoring import confirmed
APP=QApplication.instance() or QApplication([])


def activate(store,rule):return store.review_rules(store.rule_review_plan([rule['id']]),'APPROVE','Synthetic Reviewer','exact source scoped approval',True,True)[0]


class NoiseHitsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.library=Library(self.root/'data');self.addCleanup(self.library.db.close);self.store=TrainingStore(self.library);self.source,self.work,self.rule=pending_rule(self.store,self.root);self.rule=activate(self.store,self.rule)
    def future(self,name='future.svg',obs_changes=None):
        source,work=source_work(self.library,self.root,name);obs=observations(work)
        if obs_changes:obs_changes(obs)
        facts=self.store.save_facts(work['id'],obs,0,1);facts=self.store.confirm_facts(work['id'],[o['id'] for o in obs],facts['revision'],facts['pins'],self.store.source_proof(work['id']),'Synthetic Reviewer',True);return source,work,facts
    def test_once_approved_future_matches_automatically_exclude_and_reopen(self):
        source,work,facts=self.future();rows=self.store.noise_decisions(work['id']);note=next(r for r in rows if r['observation_id']=='note');self.assertEqual(note['state'],'EXCLUDED_RULE');self.assertEqual(note['rule_matches'][0]['revision'],self.rule['revision']);self.assertEqual(self.library.artwork(work['id']),work);self.assertTrue(all(r['state']=='KEPT_PROTECTED' for r in rows if r['observation_id']!='note'))
        other=Library(self.library.root)
        try:
            reopened=TrainingStore(other);self.assertEqual(reopened.noise_decisions(work['id']),rows);self.assertEqual(reopened.count('HIT'),10)
        finally:other.db.close()
    def test_exact_literal_type_region_real_fields_logo_unknown_never_broad_exclude(self):
        variants=[('prefix',lambda o:next(x for x in o if x['id']=='note').update(text='Alex 已校稿')),('type',lambda o:next(x for x in o if x['id']=='note').update(object_type='TEXT')),('zone',lambda o:next(x for x in o if x['id']=='note').update(region={'x':8,'y':1,'w':20,'h':5})),('field',lambda o:next(x for x in o if x['id']=='note').update(classification='FIELD')),('logo',lambda o:next(x for x in o if x['id']=='note').update(classification='LOGO',object_type='LOGO_PART')),('unknown',lambda o:next(x for x in o if x['id']=='note').update(classification='UNKNOWN'))]
        for name,change in variants:
            _,work,_=self.future(name+'.svg',change);note=next(r for r in self.store.noise_decisions(work['id']) if r['observation_id']=='note');self.assertFalse(note['state'].startswith('EXCLUDED'),note)
    def test_source_changed_or_support_revoked_keeps_and_stale_trace_is_not_current(self):
        source,work,facts=self.future();Path(source['original_path']).write_text('changed');self.assertEqual(next(r for r in self.store.noise_decisions(work['id']) if r['observation_id']=='note')['state'],'REVIEW_UNKNOWN')
        _,healthy,_=self.future('healthy.svg');positive=self.store.facts(self.work['id']);self.store.revoke_facts(self.work['id'],positive['revision'],'support withdrawn');self.assertEqual(next(r for r in self.store.noise_decisions(healthy['id']) if r['observation_id']=='note')['state'],'REVIEW_RULE_STALE')
    def test_multiple_active_matching_rules_conflict_keeps_candidate(self):
        _,_,duplicate=pending_rule(self.store,self.root,'duplicate.svg');activate(self.store,duplicate);_,work,_=self.future();note=next(r for r in self.store.noise_decisions(work['id']) if r['observation_id']=='note');self.assertEqual(note['state'],'REVIEW_CONFLICT');self.assertEqual(len(note['rule_matches']),2)
    def test_unlinked_annotation_overlapping_confirmed_name_cannot_evade_protection(self):
        _,work,facts=self.future('overlap.svg',lambda rows:next(o for o in rows if o['id']=='note').update(region=dict(rows[0]['region'])))
        note=next(o for o in facts['observations'] if o['id']=='note');self.assertTrue(self.store.protected_observation(work['id'],note))
        with self.assertRaises(ValueError):self.store.local_noise(work['id'],['note'],0,facts['revision'],True)
    def test_idempotent_refresh_and_late_hit_audit_roll_back_fact_confirmation(self):
        _,work,facts=self.future();rows=self.store.records('HIT');epoch=self.store.epoch;self.store.refresh_noise(work['id'],facts['revision']);self.assertEqual(self.store.epoch,epoch);self.assertEqual(self.store.records('HIT'),rows)
        _,new=source_work(self.library,self.root,'rollback.svg');pending=self.store.save_facts(new['id'],observations(new),0,1);epoch=self.store.epoch;old_event=self.library.event
        def late(entity,action):
            old_event(entity,action)
            if action=='training_noise_hit_recorded':raise RuntimeError('late hit audit')
        with patch.object(self.library,'event',side_effect=late),self.assertRaises(RuntimeError):self.store.confirm_facts(new['id'],[o['id'] for o in pending['observations']],pending['revision'],pending['pins'],self.store.source_proof(new['id']),'Reviewer',True)
        self.assertEqual(self.store.facts(new['id']),pending);self.assertEqual(self.store.epoch,epoch)


class NoiseHitsGuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.window=MainWindow(self.root/'data');self.addCleanup(self.close);self.store=TrainingStore(self.window.library);self.source,self.work,self.rule=pending_rule(self.store,self.root);self.rule=activate(self.store,self.rule);self.future_source,self.future_work=source_work(self.window.library,self.root,'future.svg');self.d=TrainingQualityDialog(self.window);self.addCleanup(self.d.close);self.d.show();APP.processEvents()
    def close(self):self.window.source=None;self.window.work=None;self.window.template=None;self.window.close()
    def test_actual_future_confirm_one_fact_prompt_no_rule_reapproval_and_hits_navigation(self):
        p=self.d.facts_panel;p.store.save_facts(self.future_work['id'],observations(self.future_work),0,1);p.reload();p.work_combo.setCurrentIndex(p.work_combo.findData(self.future_work['id']));self.d.tabs.setCurrentWidget(p);p.table.selectAll();p.actor.setText('Synthetic Reviewer')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes) as prompts:
            QTest.mouseClick(p.confirm_button,Qt.LeftButton)
            for _ in range(300):
                APP.processEvents()
                if not p.running:break
                QTest.qWait(10)
            self.assertFalse(p.running);self.assertEqual(prompts.call_count,1);self.assertIn('只确认',prompts.call_args.args[2])
        hits=self.d.hits_panel;self.d.tabs.setCurrentWidget(hits);hits.search.setText(self.future_work['id']+' 已校稿');self.assertEqual(hits.table.rowCount(),1);self.assertEqual(hits.rows[0]['current']['state'],'EXCLUDED_RULE');hits.table.selectRow(0);QTest.mouseClick(hits.locate_button,Qt.LeftButton);self.assertEqual(self.window.work['id'],self.future_work['id']);self.assertEqual(self.window.library.artwork(self.future_work['id']),self.future_work);self.assertIn(self.rule['id'],hits.details.toPlainText())
    def test_actual_current_unknown_counts_and_failed_refresh_controls(self):
        confirmed(self.store,self.future_work);hits=self.d.hits_panel;hits.search.setText(self.future_work['id']+' 已校稿');self.d.tabs.setCurrentWidget(hits);Path(self.future_source['original_path']).write_text('changed');hits.reload();hits.table.selectRow(0);self.assertEqual(hits.rows[0]['current']['state'],'REVIEW_UNKNOWN');self.assertFalse(hits.rows[0]['trace_current']);self.assertIn('疑義或歷史1',hits.count.text())
        with patch.object(hits.store,'refresh_noise',side_effect=RuntimeError('forced audit failure')):QTest.mouseClick(hits.refresh_button,Qt.LeftButton)
        self.assertIn('未保存',hits.status.text());self.assertTrue(hits.refresh_button.isEnabled());self.assertTrue(hits.reload_button.isEnabled())

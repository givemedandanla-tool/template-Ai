"""Real Qt candidate scopes, original worker, partial gates and safe selected inverse."""
import copy,unittest
from unittest.mock import patch
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QMessageBox
from sync_workflow_fixture import SyncWorkflowFixture,APP
from gui_wait import wait_for_gui
from template_ai.batch_objects import BatchObjectDialog
from template_ai.candidate_edit import plan_candidate,apply_candidate


class BatchCandidateGuiTests(unittest.TestCase):
    def setUp(self):
        self.f=SyncWorkflowFixture();self.addCleanup(self.f.close);self.d=BatchObjectDialog(self.f.w,origin=self.f.d);self.addCleanup(self.dispose);self.d.scope.setCurrentIndex(self.d.scope.findData('CANDIDATE'))
    def dispose(self):
        self.d.cancel()
        wait_for_gui(lambda:not self.d.running and not self.f.w.busy,15)
        self.d.deleteLater();APP.processEvents()
    def check(self,name,kind='phone',owner='p1'):
        candidate=self.f.candidate(name);slot=next(s for s in candidate.template.slots if s.kind==kind and s.owner==owner)
        item=next(self.d.table.item(i,0) for i in range(self.d.table.rowCount()) if (lambda r:r['id']==candidate.template.id and r['slot_ids']==[slot.id])(self.d.by_key[self.d.table.item(i,0).data(Qt.UserRole)]));item.setCheckState(Qt.Checked);return slot.id
    def wait(self):self.assertTrue(wait_for_gui(lambda:not self.d.running and not self.f.w.busy,20),self.d.status.text())
    def preview(self):self.d.preview();self.wait();self.assertIsNotNone(self.d.plan,self.d.status.text())
    def apply(self):
        with patch('template_ai.batch_candidate_ui.QMessageBox.question',return_value=QMessageBox.Yes):self.d.apply()
        self.wait()
    def test_sorted_hidden_checked_exact_targets_keep_their_own_coordinates(self):
        ids=[self.check('A90'),self.check('B90')];before={n:self.f.candidate(n).template.to_dict() for n in ('A90','B90')};self.d.table.sortItems(2,Qt.DescendingOrder);self.d.search.setText('not-visible');self.assertEqual(len(self.d.selected_rows()),2);self.preview();self.assertEqual(sum(r['state']=='READY' for r in self.d.plan['rows']),2);self.apply();self.assertEqual([r['outcome'] for r in self.d.results],['APPLIED_VALIDATED']*2)
        for n,slot_id in zip(('A90','B90'),ids):
            c=self.f.candidate(n);slot=next(s for s in c.template.slots if s.id==slot_id);old=next(s for s in before[n]['slots'] if s['id']==slot_id);self.assertEqual(slot.rect.x,old['rect']['x']);self.assertEqual(slot.align,'center');self.assertTrue(c.formal_eligible)
        self.assertFalse(self.f.candidate('C100').formal_eligible)
    def test_bad_size_and_logo_remain_manual_while_legal_card_applies(self):
        self.check('A90');self.check('C100');self.check('B90','logo','c1');self.preview();self.assertEqual(sum(r['state']=='READY' for r in self.d.plan['rows']),1);self.apply();self.assertEqual(sum(r['outcome']=='APPLIED_VALIDATED' for r in self.d.results),1);self.assertEqual(sum(r['outcome']=='NEEDS_MANUAL_REVIEW' for r in self.d.results),2);self.assertFalse(self.f.candidate('C100').formal_eligible)
    def test_selection_change_inside_confirmation_prevents_all_installations(self):
        self.check('A90');self.preview();before=copy.deepcopy(self.f.candidate('A90').template.to_dict())
        def change(*args,**kwargs):self.check('B90');return QMessageBox.Yes
        with patch('template_ai.batch_candidate_ui.QMessageBox.question',side_effect=change):self.d.apply()
        self.assertFalse(self.d.running);self.assertEqual(self.f.candidate('A90').template.to_dict(),before);self.assertIn('重新預檢',self.d.status.text())
    def test_new_manual_edit_after_preflight_is_preserved(self):
        slot_id=self.check('A90');self.preview();adapter,index=self.f.adapter('A90');apply_candidate(adapter,plan_candidate(adapter,index,[slot_id],.2,0),True);new=copy.deepcopy(self.f.candidate('A90').template.to_dict());self.apply();self.assertEqual(self.d.results[0]['outcome'],'STALE');self.assertEqual(self.f.candidate('A90').template.to_dict(),new)
    def test_retry_reads_original_receipt_without_duplicate_move(self):
        slot_id=self.check('A90');self.d.action.setCurrentIndex(1);self.d.dx.setValue(.1);self.preview();self.apply();first=copy.deepcopy(self.f.candidate('A90'));self.apply();self.assertEqual(self.d.results[0]['outcome'],'ALREADY_APPLIED');self.assertEqual(self.f.candidate('A90').template.to_dict(),first.template.to_dict());self.assertEqual(self.f.candidate('A90').risk_context['manual_history'],first.risk_context['manual_history'])
    def test_selected_partial_inverse_preserves_other_card(self):
        self.check('A90');self.check('B90');self.preview();self.apply();b=copy.deepcopy(self.f.candidate('B90').template.to_dict())
        for i in range(self.d.table.rowCount()):
            item=self.d.table.item(i,0);row=self.d.by_key[item.data(Qt.UserRole)]
            if row['id']==self.f.candidate('B90').template.id:item.setCheckState(Qt.Unchecked)
        with patch('template_ai.batch_candidate_ui.QMessageBox.question',return_value=QMessageBox.Yes):self.d.undo()
        self.wait();self.assertIn('已回復 1',self.d.status.text());self.assertEqual(self.f.candidate('B90').template.to_dict(),b);phone=next(s for s in self.f.candidate('A90').template.slots if s.kind=='phone' and s.owner=='p1');self.assertEqual(phone.align,'left')
    def test_cancel_between_card_installs_keeps_completed_and_stops_unstarted(self):
        self.check('A90');self.check('B90');self.preview();controller=self.d.candidate_batch
        original=controller.next_apply
        def step():
            if controller.position==1:self.d.cancel()
            original()
        with patch.object(controller,'next_apply',side_effect=step):self.apply()
        self.assertEqual([r['outcome'] for r in self.d.results],['APPLIED_VALIDATED','CANCELLED'])
    def test_x_ratio_uses_original_measurements_and_preserves_font(self):
        slot_id=self.check('A90');before=next(s for s in self.f.candidate('A90').template.slots if s.id==slot_id);font=before.size_pt;self.d.action.setCurrentIndex(3);self.d.ratio.setValue(90);self.preview();self.apply();after=next(s for s in self.f.candidate('A90').template.slots if s.id==slot_id);self.assertEqual(after.size_pt,font);self.assertEqual(self.d.results[0]['outcome'],'APPLIED_VALIDATED')

if __name__=='__main__':unittest.main()

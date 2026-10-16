"""Original UI061 concrete native scope: two people/companies, three/two candidates/sizes."""
import copy,unittest
from unittest.mock import patch
from types import SimpleNamespace
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox
from sync_workflow_fixture import SyncWorkflowFixture
from template_ai.candidate_edit import plan_candidate,plan_operation,plan_undo
from template_ai.candidate_sync_dialog import CrossPropertyDialog
from template_ai.source_change_impact import source_change_impact
from gui_wait import wait_for_gui


class SyncWorkflowTests(unittest.TestCase):
    def setUp(self):self.fx=SyncWorkflowFixture();self.addCleanup(self.fx.close)
    def test_authored_scope_has_two_real_qualified90_candidates_and_failed100_specific_logo(self):
        f=self.fx;self.assertEqual(len(f.w.active_input_graph.data['people']),2);self.assertEqual(len(f.w.active_input_graph.data['companies']),2);self.assertEqual(sum(len(e['candidates']) for e in f.d.service.entries),3);self.assertTrue(f.candidate('A90').formal_eligible);self.assertTrue(f.candidate('B90').formal_eligible);self.assertEqual(f.d.table.cellWidget(0,2).currentData(),f.templates['A90'].id);self.assertFalse(f.candidate('C100').formal_eligible);self.assertTrue(any(r['code']=='LOGO_MISSING' and r['owner']=='c2' for r in f.candidate('C100').diagnostics))
    def test_phone_a_updates_all_true_consumers_and_same_string_b_is_unchanged(self):
        f=self.fx;before=copy.deepcopy(f.w.active_input_graph.data);field=f.change_phone('+12025550999');rows=source_change_impact([(name,f.candidate(name)) for name in f.templates],before,f.w.active_input_graph.data);self.assertEqual(len(rows),3)
        for row,name in zip(rows,f.templates):self.assertEqual(row['affected_slot_ids'],[f.candidate(name).template.slots[1].id])
        self.assertFalse(f.d.is_current());self.assertTrue(all('待重驗' in f.d.table.item(row,3).text() for row in range(f.d.table.rowCount())));self.assertIn('歷史結果',f.d.details.toPlainText());f.sync()
        for name in f.templates:
            phones={item.slot.owner:item.text for item in f.candidate(name).items if item.slot.kind=='phone'};self.assertEqual(phones,dict(p1='+12025550999',p2='+12025550100'))
    def test_manual_a_only_and_single_undo_after_source_update_keep_b_c_geometry_and_current_phone(self):
        f=self.fx;before={name:f.candidate(name).template.to_dict() for name in f.templates};adapter,index,controller=f.controller('A90');identity=adapter.candidates[index].template.slots[0].id;controller.submit(plan_candidate(adapter,index,[identity],1,0));f.wait();self.assertEqual(f.candidate('A90').template.slots[0].rect.x,before['A90']['slots'][0]['rect']['x']+1);self.assertEqual(f.candidate('B90').template.to_dict(),before['B90']);self.assertEqual(f.candidate('C100').template.to_dict(),before['C100']);f.change_phone('+12025550999');f.sync();adapter,index,controller=f.controller('A90');controller.submit(plan_undo(adapter,index));f.wait();self.assertEqual(f.candidate('A90').template.to_dict(),before['A90']);self.assertIn('+12025550999',[item.text for item in f.candidate('A90').items]);self.assertEqual(f.candidate('B90').template.to_dict(),before['B90'])
    def test_actual_three_candidate_alignment_flow_does_not_copy_a_geometry_to_b_or_failed100(self):
        f=self.fx;adapter,index,controller=f.controller('A90');identity=adapter.candidates[index].template.slots[0].id;controller.submit(plan_operation(adapter,index,dict(operation='PATCH',ids=[identity],patch=dict(align='center'),cross_owner=False)));f.wait();f.select('A90');dialog=CrossPropertyDialog(f.d);dialog.show();before_b=f.candidate('B90').template.to_dict();before_c=f.candidate('C100').template.to_dict()
        for row in range(dialog.table.rowCount()):dialog.table.item(row,0).setCheckState(Qt.Checked)
        QTest.mouseClick(dialog.preview_button,Qt.LeftButton)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(dialog.apply_button,Qt.LeftButton)
        f.wait();self.assertEqual([r['state'] for r in dialog.results],['APPLIED_VERIFIED','VALIDATION_FAILED']);self.assertEqual(f.candidate('B90').template.slots[0].rect.x,before_b['slots'][0]['rect']['x']);self.assertEqual(f.candidate('B90').template.slots[0].align,'center');self.assertEqual(f.candidate('C100').template.to_dict(),before_c)
    def test_long_phone_after_locked_a_never_shrinks_or_moves_any_manual_geometry(self):
        f=self.fx;adapter,index,controller=f.controller('A90');identity=adapter.candidates[index].template.slots[0].id;controller.submit(plan_candidate(adapter,index,[identity],1,0));f.wait();controller.submit(plan_operation(adapter,index,dict(operation='LOCK',ids=[identity],locked=True,cross_owner=False)));f.wait();before={name:f.candidate(name).template.to_dict() for name in f.templates};f.change_phone('1234567890'*30);f.sync()
        for name in f.templates:self.assertEqual(f.candidate(name).template.to_dict(),before[name]);self.assertFalse(f.candidate(name).formal_eligible)
        self.assertTrue(f.candidate('A90').template.slots[0].locked)
    def test_esc_during_matrix_admission_cancels_without_deleting_active_owner(self):
        f=self.fx
        with patch.object(f.w.runtime,'admit',return_value=SimpleNamespace(allowed=False,reasons=['SYNTHETIC_HIGH_LOAD'])):
            f.d.sync_source();self.assertTrue(wait_for_gui(lambda:bool(f.w._waiting_launches),2));QTest.keyClick(f.d,Qt.Key_Escape);self.assertTrue(f.d.isVisible());self.assertTrue(f.d.stop.is_set());f.wait()
        self.assertFalse(f.d.running)

    def test_explicit_logo_from_different_same_named_company_cannot_match_by_string(self):
        from sync_workflow_fixture import REVIEW
        f=self.fx;other=f.store.create_company(f.registry[0]['name'],'Different legal synthetic identity with equal display label',True);plan=f.store.propose(f.payloads[0],90,54,company_id=other['id']);wrong=f.store.approve(plan['id'],plan['revision'],other['id'],REVIEW,True);graph=f.w.active_input_graph.clone();entity=graph.data['companies'][0]['id'];graph.apply(graph.preview('edit_logo',company_id=entity,logo_id=wrong['id']),True);f.w.adopt_input_graph(graph.data,history=graph);f.sync()
        for name in ('A90','B90'):
            self.assertFalse(f.candidate(name).formal_eligible);self.assertIsNone(next(item.logo for item in f.candidate(name).items if item.slot.kind=='logo' and item.slot.owner=='c1'))
        self.assertEqual(f.entry('A90')['logo_states']['c1'],'SELECTION_INVALID_NO_REPLACEMENT')
    def test_explicit_logo_without_confirmed_entity_binding_stays_unverified(self):
        f=self.fx;entity=f.w.active_input_graph.data['companies'][0]['id'];f.w.library.db.execute('DELETE FROM logo_entity_bindings WHERE entity_id=?',(entity,));f.w.library.db.commit();f.w.invalidate();f.sync();self.assertFalse(f.candidate('A90').formal_eligible);self.assertEqual(f.entry('A90')['logo_states']['c1'],'IDENTITY_REVIEW_REQUIRED')

"""Real candidate edit/undo, source isolation, current data and ABA version fencing."""
import copy,unittest
from unittest.mock import patch
from PySide6.QtWidgets import QMessageBox
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt
import test_seventy_ui as fixture
from gui_wait import wait_layout
from template_ai.candidate_edit import (plan_candidate,plan_operation,plan_undo,prepare_edit,calculate_edit,install_edit,apply_candidate,CandidateEditDialog)
APP=fixture.APP

class CandidateEditHistoryTests(unittest.TestCase):
    setUp=fixture.SeventyUiTests.setUp
    close_window=fixture.SeventyUiTests.close_window
    def ready(self):self.w.generate();wait_layout(self.w);return self.w.candidates[0]
    def move(self,index=0,slot=0,dx=1,dy=0):return apply_candidate(self.w,plan_candidate(self.w,index,[self.w.candidates[index].template.slots[slot].id],dx,dy),True)
    def test_move_and_real_undo_preserve_input_other_candidate_and_official_template(self):
        original=self.ready();self.w.candidates.append(copy.deepcopy(original));other=copy.deepcopy(self.w.candidates[1]);published=self.w.library.object_snapshot('TEMPLATE',original.template.id)['payload'];inputs=copy.deepcopy(self.w.input_data());before=original.template.to_dict();moved=self.move();self.assertEqual(moved.risk_context['manual_revision'],1);restored=apply_candidate(self.w,plan_undo(self.w,0),True);self.assertEqual(restored.template.to_dict(),before);self.assertEqual(restored.risk_context['manual_revision'],2);self.assertTrue(restored.formal_eligible);self.assertEqual(self.w.candidates[1],other);self.assertEqual(self.w.input_data(),inputs);self.assertEqual(self.w.library.object_snapshot('TEMPLATE',original.template.id)['payload'],published)
        with self.assertRaises(ValueError):plan_undo(self.w,0)
    def test_single_undo_keeps_earlier_different_object_change(self):
        original=self.ready();name_x=original.template.slots[0].rect.x;title_y=original.template.slots[1].rect.y;self.move();self.move(slot=1,dx=0,dy=.25);restored=apply_candidate(self.w,plan_undo(self.w,0),True);self.assertEqual(restored.template.slots[0].rect.x,name_x+1);self.assertEqual(restored.template.slots[1].rect.y,title_y);self.assertEqual(len([r for r in restored.risk_context['manual_history'] if not r['undone']]),1)
    def test_undo_after_input_change_keeps_new_text_and_cannot_make_long_phone_safe(self):
        original=self.ready();name_x=original.template.slots[0].rect.x;self.move();phone='1234567890'*20;self.w.people.item(0,2).setText(phone);restored=apply_candidate(self.w,plan_undo(self.w,0),True);self.assertEqual(restored.template.slots[0].rect.x,name_x);self.assertEqual(next(i.text for i in restored.items if i.slot.kind=='phone'),phone);self.assertEqual(restored.generation,self.w.generation);self.assertEqual(restored.risk['state'],'HARD_BLOCKED');self.assertFalse(self.w.export_button.isEnabled())
    def test_late_result_rejected_even_when_manual_roundtrip_returns_exact_same_geometry(self):
        original=self.ready();before=original.template.to_dict();plan=plan_candidate(self.w,0,[original.template.slots[0].id],.5,0);envelope=prepare_edit(self.w,plan);self.move();apply_candidate(self.w,plan_undo(self.w,0),True);self.assertEqual(self.w.candidates[0].template.to_dict(),before);old=calculate_edit(envelope,self.w.library)
        with self.assertRaisesRegex(ValueError,'較新的人工'):install_edit(self.w,envelope,old)
        self.assertEqual(self.w.candidates[0].template.to_dict(),before);self.assertEqual(self.w.candidates[0].risk_context['manual_revision'],2)
    def test_required_unknown_is_preserved_by_both_move_and_undo(self):
        c=self.ready();c.risk_context.setdefault('conditions',[]).append(dict(id='UNRESOLVED_SOURCE',status='UNKNOWN',reason='Synthetic essential evidence unresolved'));self.move();restored=apply_candidate(self.w,plan_undo(self.w,0),True);self.assertEqual(restored.risk['state'],'EVIDENCE_REQUIRED');self.assertFalse(restored.formal_eligible)
    def test_lock_resize_and_fixed_size_restriction_use_existing_proposal_engine(self):
        c=self.ready();identity=c.template.slots[0].id;apply_candidate(self.w,plan_operation(self.w,0,dict(operation='LOCK',ids=[identity],locked=True,cross_owner=False)),True)
        with self.assertRaises(ValueError):plan_candidate(self.w,0,[identity],1,0)
        apply_candidate(self.w,plan_undo(self.w,0),True);c=self.w.candidates[0];width=c.template.slots[0].rect.w;resized=apply_candidate(self.w,plan_operation(self.w,0,dict(operation='PATCH',ids=[identity],patch={'w':width-1},cross_owner=False)),True);self.assertEqual(resized.template.slots[0].rect.w,width-1);self.assertTrue(resized.formal_eligible)
        with self.assertRaises(ValueError):plan_operation(self.w,0,dict(operation='PATCH',ids=[identity],patch={'size_pt':9},cross_owner=False))
    def test_actual_dialog_undo_preview_then_explicit_apply_has_no_business_write(self):
        c=self.ready();before=c.template.to_dict();d=CandidateEditDialog(self.w);self.addCleanup(d.deleteLater);d.show();d.objects.item(0).setSelected(True);d.dx.setValue(1);d.preview()
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(d.apply_button,Qt.LeftButton);APP.processEvents()
        self.assertEqual(self.w.candidates[0].template.slots[0].rect.x,before['slots'][0]['rect']['x']+1);QTest.mouseClick(d.undo_button,Qt.LeftButton);self.assertEqual(d.plan['request']['operation'],'UNDO')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(d.apply_button,Qt.LeftButton);APP.processEvents()
        self.assertEqual(self.w.candidates[0].template.to_dict(),before);self.assertEqual(self.w.library.object_snapshot('TEMPLATE',c.template.id)['payload'],before)

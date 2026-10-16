"""Actual candidate-local dependencies and minimal inverses, never final permission."""
import copy,unittest
from template_ai.candidate_changes import affected,graph,merge_properties,manual_delta,inverse_delta
from template_ai.model import Slot,Rect,Template
from template_ai.layout import generate
import test_first_version as fixture

class CandidateChangeTests(unittest.TestCase):
    setUp=fixture.FirstVersionTests.setUp
    def people(self):return [dict(name=['Alex Example'],title=['Designer'],phone=['123'],email=['qa@example.test'])]
    def ids(self,kind):return sorted(s.id for s in self.template.slots if s.kind==kind)
    def test_phone_change_reaches_only_phone_slots_and_always_whole_card_gate(self):
        old=self.people();new=copy.deepcopy(old);new[0]['phone']=['456'];r=affected(self.template,old,[],new,[]);self.assertEqual(r['affected_slot_ids'],self.ids('phone'));self.assertTrue(r['whole_card_validation_required']);self.assertFalse(r['can_reuse_without_current_source_gate'])
    def test_stable_field_identity_change_is_not_hidden_by_equal_display_text(self):
        old=self.people();old[0]['field_ids']={'phone':['old-id']};new=copy.deepcopy(old);new[0]['field_ids']['phone']=['new-id'];r=affected(self.template,old,[],new,[]);self.assertEqual(r['affected_slot_ids'],self.ids('phone'));self.assertTrue(r['whole_card_validation_required'])
    def test_deleted_phone_still_names_previous_consumer_and_cannot_reuse_old_text(self):
        old=self.people();new=copy.deepcopy(old);new[0].pop('phone');r=affected(self.template,old,[],new,[]);self.assertEqual(r['affected_slot_ids'],self.ids('phone'));self.assertTrue(r['whole_card_validation_required'])
    def test_new_unmapped_input_reaches_global_lossless_gate_without_inventing_slot(self):
        old=self.people();new=copy.deepcopy(old);new[0]['address']=['Synthetic address'];r=affected(self.template,old,[],new,[]);self.assertEqual(r['affected_slot_ids'],[]);self.assertTrue(r['whole_card_validation_required']);self.assertFalse(r['can_reuse_without_current_source_gate'])
    def test_other_size_logo_has_no_consumer_but_same_size_logo_does(self):
        slot=Slot('logo','c1',Rect(70,40,15,10));self.template.slots.append(slot);people=self.people();r=affected(self.template,people,[],people,[],[('LOGO','c1',(100,60))]);self.assertEqual(r['affected_slot_ids'],[]);self.assertFalse(r['whole_card_validation_required']);r=affected(self.template,people,[],people,[],[('LOGO','c1',(90,54))]);self.assertEqual(r['affected_slot_ids'],[slot.id]);self.assertTrue(r['whole_card_validation_required'])
    def test_font_change_only_reaches_slots_using_that_exact_family_and_style(self):
        first=self.template.slots[0];first.font='Synthetic isolated face';p=self.people();r=affected(self.template,p,[],p,[],[('FONT',first.font,first.font_style)]);self.assertEqual(r['affected_slot_ids'],[first.id]);self.assertTrue(r['whole_card_validation_required'])
    def test_company_rebind_reaches_person_and_old_new_company_not_unrelated_company(self):
        logos=[Slot('logo',f'c{i}',Rect(60,i*12,10,10)) for i in (1,2,3)];self.template.slots+=logos;old=self.people();old[0]['company']='c1';new=copy.deepcopy(old);new[0]['company']='c2';companies=[dict(name='Synthetic '+str(i)) for i in (1,2,3)];r=affected(self.template,old,companies,new,companies);self.assertIn(logos[0].id,r['affected_slot_ids']);self.assertIn(logos[1].id,r['affected_slot_ids']);self.assertNotIn(logos[2].id,r['affected_slot_ids']);self.assertTrue(set(self.ids('name'))<=set(r['affected_slot_ids']))
    def test_capacity_change_conservatively_rechecks_all_slots(self):
        old=self.people();new=old+[copy.deepcopy(old[0])];r=affected(self.template,old,[],new,[]);self.assertEqual(r['affected_slot_ids'],sorted(s.id for s in self.template.slots));self.assertTrue(r['whole_card_validation_required'])
    def test_scope_budget_failure_never_returns_partial_safe_result(self):
        with self.assertRaises(ValueError):graph(self.template,[dict(phone=['x']*2001)],[])
        self.template.slots*=17
        with self.assertRaises(ValueError):graph(self.template,self.people(),[])
    def test_unchanged_input_is_only_potential_reuse_not_source_or_output_approval(self):
        p=self.people();r=affected(self.template,p,[],p,[]);self.assertEqual(r['changed_fields'],[]);self.assertEqual(r['affected_slot_ids'],[]);self.assertFalse(r['whole_card_validation_required']);self.assertFalse(r['can_reuse_without_current_source_gate'])
    def test_three_way_preserves_manual_x_and_proposes_disjoint_new_y_without_applying(self):
        r=merge_properties(dict(x=1,y=2),dict(x=3,y=2),dict(x=1,y=4));self.assertEqual(r['merged'],dict(x=3,y=4));self.assertEqual(r['conflicts'],[]);self.assertFalse(r['applied']);self.assertFalse(r['formal_allowed']);self.assertTrue(r['whole_card_recheck_required'])
    def test_three_way_divergence_retains_manual_value_and_names_conflict(self):
        r=merge_properties(dict(x=1),dict(x=3),dict(x=4));self.assertEqual(r['merged']['x'],3);self.assertEqual(r['conflicts'],['x'])
    def test_lock_blocks_real_new_move_but_does_not_reset_manual_to_unchanged_base(self):
        r=merge_properties(dict(x=1),dict(x=1),dict(x=4),locked=True);self.assertEqual(r['conflicts'],['x']);r=merge_properties(dict(x=1),dict(x=3),dict(x=1),locked=True);self.assertEqual(r['merged']['x'],3);self.assertEqual(r['conflicts'],[])
    def test_fixed_font_size_and_semantic_owner_are_never_automatic_merge_permissions(self):
        for current,new in ((10,9),(9,10)):
            r=merge_properties(dict(size_pt=10),dict(size_pt=current),dict(size_pt=new));self.assertEqual(r['conflicts'],['size_pt']);self.assertFalse(r['formal_allowed'])
        r=merge_properties(dict(owner='p1'),dict(owner='p1'),dict(owner='p2'));self.assertEqual(r['conflicts'],['owner']);self.assertEqual(r['merged']['owner'],'p1')
    def test_property_or_object_addition_is_review_instead_of_silent_merge(self):
        with self.assertRaises(ValueError):merge_properties(dict(x=1),dict(x=1),dict(x=1,y=2))
    def moved(self):
        before=self.template.to_dict();after=copy.deepcopy(before);after['slots'][0]['rect']['x']+=1;return before,after,manual_delta(before,after)
    def test_delta_contains_only_changed_coordinate_and_no_people_or_customer_snapshot(self):
        before,after,receipt=self.moved();self.assertEqual(len(receipt['changes']),1);self.assertEqual(receipt['changes'][0]['property'],'rect.x');self.assertEqual(receipt['scope'],'THIS_CANDIDATE_ONLY');self.assertNotIn('people',receipt);self.assertNotIn('customers',receipt);self.assertEqual(self.library.templates(),[])
    def test_actual_inverse_restores_geometry_then_whole_card_is_actually_regenerated(self):
        before,after,receipt=self.moved();result=inverse_delta(after,receipt);self.assertEqual(result['template'],before);self.assertFalse(result['applied']);self.assertFalse(result['formal_allowed']);self.assertTrue(result['whole_card_recheck_required']);candidate=generate(Template.from_dict(result['template']),self.people(),[],{},7);self.assertTrue(candidate.formal_eligible,candidate.issues);self.assertEqual(self.library.templates(),[])
    def test_inverse_preserves_later_untouched_coordinate_and_other_objects(self):
        before,after,receipt=self.moved();current=copy.deepcopy(after);current['slots'][0]['rect']['y']+=.25;current['slots'][1]['color']='#334455';result=inverse_delta(current,receipt)['template'];self.assertEqual(result['slots'][0]['rect']['x'],before['slots'][0]['rect']['x']);self.assertEqual(result['slots'][0]['rect']['y'],current['slots'][0]['rect']['y']);self.assertEqual(result['slots'][1],current['slots'][1]);self.assertTrue(generate(Template.from_dict(result),self.people(),[],{}).valid)
    def test_later_touched_property_receipt_tamper_and_repeated_undo_are_blocked(self):
        before,after,receipt=self.moved();current=copy.deepcopy(after);current['slots'][0]['rect']['x']+=1
        with self.assertRaises(ValueError):inverse_delta(current,receipt)
        tampered=copy.deepcopy(receipt);tampered['changes'][0]['before']=999
        with self.assertRaises(ValueError):inverse_delta(after,tampered)
        receipt['undone']=True
        with self.assertRaises(ValueError):inverse_delta(after,receipt)
    def test_delta_cannot_hide_font_source_size_owner_or_dimension_rewrite(self):
        before=self.template.to_dict()
        for key,value in (('size_pt',9),('font','Different face'),('owner','p2')):
            after=copy.deepcopy(before);after['slots'][0][key]=value
            with self.assertRaises(ValueError):manual_delta(before,after)
        after=copy.deepcopy(before);after['width_mm']=100
        with self.assertRaises(ValueError):manual_delta(before,after)
    def test_explicit_lock_inverse_reuses_existing_object_engine(self):
        before=self.template.to_dict();after=copy.deepcopy(before);after['slots'][0]['locked']=True;receipt=manual_delta(before,after);result=inverse_delta(after,receipt)['template'];self.assertEqual(result,before)
    def test_added_object_and_empty_action_never_create_fake_local_history(self):
        before=self.template.to_dict()
        with self.assertRaises(ValueError):manual_delta(before,before)
        after=copy.deepcopy(before);extra=copy.deepcopy(after['slots'][0]);extra['id']='new-synthetic-object';after['slots'].append(extra)
        with self.assertRaises(ValueError):manual_delta(before,after)

    def test_explicit_many_company_link_and_malformed_link_conservatively_recheck(self):
        logos=[Slot('logo',f'c{i}',Rect(60,i*12,10,10)) for i in (1,2,3)];self.template.slots+=logos;old=self.people();old[0]['companies']=['c1','c2'];new=copy.deepcopy(old);new[0]['companies']=['c2'];companies=[dict(name='Synthetic '+str(i)) for i in (1,2,3)];r=affected(self.template,old,companies,new,companies);self.assertIn(logos[0].id,r['affected_slot_ids']);self.assertIn(logos[1].id,r['affected_slot_ids']);self.assertNotIn(logos[2].id,r['affected_slot_ids'])
        old=self.people();old[0]['company']=1;new=copy.deepcopy(old);new[0]['company']=2;r=affected(self.template,old,companies,new,companies);self.assertEqual(r['affected_slot_ids'],sorted(s.id for s in self.template.slots));self.assertTrue(r['whole_card_validation_required'])

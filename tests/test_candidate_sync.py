"""UI061 cross-property preview is an exact stable-ID join, never geometric copy."""
import copy,unittest
from PySide6.QtWidgets import QApplication
from template_ai.input_graph import InputGraph
from template_ai.model import Template,Slot,Rect
from template_ai.layout import generate
from template_ai.candidate_sync import cross_property_plan,verify_cross_plan,field_reference
APP=QApplication.instance() or QApplication([])


class CandidateSyncTests(unittest.TestCase):
    def setUp(self):
        self.graph=InputGraph.from_legacy([dict(name=['Same name'],phone=['123'],company='c1'),dict(name=['Same name'],phone=['123'],company='c2')],[dict(name='Synthetic A'),dict(name='Synthetic B')]);self.inputs=self.graph.compile()
        def candidate(width,align='left'):
            slots=[Slot('name','p1',Rect(3,3,60,8),align=align),Slot('phone','p1',Rect(3,13,60,8),align=align),Slot('name','p2',Rect(3,25,60,8)),Slot('phone','p2',Rect(3,35,60,8))];t=Template('Synthetic '+str(width),width,54,slots,capacity=2,company_bindings={'p1':'c1','p2':'c2'});return generate(t,*copy.deepcopy(self.inputs),generation=7)
        self.source=candidate(90,'center');self.b=candidate(90);self.c=candidate(100);self.ids=[self.source.template.slots[0].id];self.targets=[('B',self.b),('C',self.c)]
    def plan(self,attributes=('align',)):return cross_property_plan(self.source,self.targets,self.ids,list(attributes))
    def test_same_names_and_phones_map_only_same_source_entity_field(self):
        plan=self.plan();self.assertTrue(all(r['state']=='READY_FOR_EXPLICIT_CONFIRMATION' for r in plan['targets']))
        for row in plan['targets']:
            target=dict(self.targets)[row['key']];changed={r['object_id'] for r in row['changes']};self.assertEqual(changed,{target.template.slots[0].id});self.assertEqual(row['after']['slots'][2]['align'],'left')
    def test_different_physical_sizes_keep_actual_geometry_unchanged(self):
        before=[copy.deepcopy(c.template.to_dict()) for _,c in self.targets];plan=self.plan()
        for row,original in zip(plan['targets'],before):
            self.assertEqual([s['rect'] for s in row['after']['slots']],[s['rect'] for s in original['slots']]);self.assertEqual(row['after']['width_mm'],original['width_mm'])
        self.assertEqual([c.template.to_dict() for _,c in self.targets],before);self.assertFalse(plan['applied']);self.assertFalse(plan['formal_allowed'])
    def test_equal_text_with_different_field_identity_is_incompatible(self):
        self.b.risk_context['input_snapshot']['people'][0]['field_ids']['name'][0]='DIFFERENT_STABLE_FIELD';row=self.plan()['targets'][0];self.assertEqual(row['state'],'INCOMPATIBLE');self.assertFalse(row['changes']);self.assertNotIn('after',row)
    def test_ambiguous_two_consumers_cannot_choose_one_by_slot_position(self):
        duplicate=copy.deepcopy(self.b.template.slots[0]);duplicate.id+='duplicate';self.b.template.slots.append(duplicate);row=self.plan()['targets'][0];self.assertEqual(row['state'],'INCOMPATIBLE');self.assertIn('唯一',row['reason']);self.assertNotIn('after',row)
    def test_missing_stable_source_identity_never_infers_name_match(self):
        del self.source.risk_context['input_snapshot']['people'][0]['source_entity_id']
        with self.assertRaisesRegex(ValueError,'實體ID'):self.plan()
    def test_partial_matching_of_multiple_source_slots_never_partially_changes_target(self):
        self.ids.append(self.source.template.slots[1].id);self.b.template.slots.pop(1);before=self.b.template.to_dict();row=self.plan()['targets'][0];self.assertEqual(row['state'],'INCOMPATIBLE');self.assertFalse(row['changes']);self.assertEqual(self.b.template.to_dict(),before)
    def test_locked_target_preserves_lock_and_other_ready_target_is_explicit(self):
        self.b.template.slots[0].locked=True;rows=self.plan()['targets'];self.assertEqual(rows[0]['state'],'INCOMPATIBLE');self.assertEqual(rows[1]['state'],'READY_FOR_EXPLICIT_CONFIRMATION');self.assertTrue(self.b.template.slots[0].locked)
    def test_coordinate_font_and_owner_copy_are_not_allowed_properties(self):
        for prop in ('x','w','rect','size_pt','font','owner'):
            with self.assertRaises(ValueError):self.plan([prop])
    def test_source_or_target_manual_change_invalidates_prior_plan(self):
        plan=self.plan();self.assertTrue(verify_cross_plan(plan,self.source,self.targets));self.c.template.slots[1].rect.x+=1
        with self.assertRaisesRegex(ValueError,'目標'):verify_cross_plan(plan,self.source,self.targets)
        plan=self.plan();self.source.template.slots[0].align='right'
        with self.assertRaisesRegex(ValueError,'來源'):verify_cross_plan(plan,self.source,self.targets)
    def test_unchanged_property_and_generation_conflict_have_named_per_target_states(self):
        self.b.template.slots[0].align='center';self.c.generation=8;rows=self.plan()['targets'];self.assertEqual(rows[0]['state'],'UNCHANGED');self.assertEqual(rows[1]['state'],'INCOMPATIBLE');self.assertIn('世代',rows[1]['reason'])

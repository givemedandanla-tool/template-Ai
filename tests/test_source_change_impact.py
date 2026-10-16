"""Exact consumers: same phone text never conflates two people's source IDs."""
import copy,unittest
import test_candidate_sync as fixture
from template_ai.input_graph import InputGraph
from template_ai.source_change_impact import source_change_impact


class SourceChangeImpactTests(unittest.TestCase):
    setUp=fixture.CandidateSyncTests.setUp
    def field(self):return next(f for f in self.graph.data['fields'] if f['owner_id']==self.graph.data['people'][0]['id'] and f['kind']=='phone')
    def candidates(self):return [('A90',self.source),('B90',self.b),('C100',self.c)]
    def test_only_person_a_phone_consumers_across_three_candidates_two_sizes(self):
        graph=self.graph.clone();graph.apply(graph.preview('edit_field',field_id=self.field()['id'],value='987654'),True);rows=source_change_impact(self.candidates(),self.graph.data,graph.data);self.assertEqual(len(rows),3)
        for row,(scope,candidate) in zip(rows,self.candidates()):self.assertEqual(row['affected_slot_ids'],[candidate.template.slots[1].id]);self.assertNotIn(candidate.template.slots[3].id,row['affected_slot_ids']);self.assertTrue(row['whole_card_validation_required'])
    def test_other_source_graph_equal_strings_never_become_same_person(self):
        other=InputGraph.from_legacy([dict(name=['Same name'],phone=['123'])],[]);new=other.clone();field=next(f for f in new.data['fields'] if f['kind']=='phone');new.apply(new.preview('edit_field',field_id=field['id'],value='987654'),True);self.assertEqual(source_change_impact(self.candidates(),other.data,new.data),[])
    def test_deleting_a_field_does_not_invalidate_other_person_due_to_global_array_shift(self):
        graph=self.graph.clone();graph.apply(graph.preview('delete_field',field_id=self.field()['id']),True);rows=source_change_impact(self.candidates(),self.graph.data,graph.data);self.assertEqual(len(rows),3)
        for row,(scope,candidate) in zip(rows,self.candidates()):self.assertEqual(row['affected_slot_ids'],[candidate.template.slots[1].id])

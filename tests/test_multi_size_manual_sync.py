"""Actual source synchronization retains per-size manual geometry and full gates."""
import copy,threading,unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_multi_size as fixture
from template_ai.input_graph import InputGraph
from template_ai.multi_size import MultiSizeWorkflow
from template_ai.candidate_edit import apply_candidate,plan_candidate,plan_operation


class MultiSizeManualSyncTests(unittest.TestCase):
    setUp=fixture.MultiSizeTests.setUp
    tearDown=fixture.MultiSizeTests.tearDown
    def adapter(self,index=0):
        entry=self.entries[index]
        return SimpleNamespace(library=self.library,candidates=entry['candidates'],generation=7,input_data=lambda:copy.deepcopy((self.workflow.people,self.workflow.companies,entry['resolved_logos'])),choose_candidate=lambda index:None)
    def move(self):
        adapter=self.adapter();slot=adapter.candidates[0].template.slots[0];return apply_candidate(adapter,plan_candidate(adapter,0,[slot.id],1,0),True)
    def changed_graph(self,value='Alex Updated'):
        graph=self.graph.clone();field=next(f for f in graph.data['fields'] if f['kind']=='name' and f['owner_id']==graph.data['people'][0]['id']);graph.apply(graph.preview('edit_field',field_id=field['id'],value=value),True);return graph
    def sync(self,graph=None,previous=None,generation=8,cancel=None):
        graph=graph or self.changed_graph();service=MultiSizeWorkflow(self.library,graph.compile(self.library.logos()),graph.data,generation);service.calculate_preserving([[90,54],[100,60]],previous or self.entries,cancel=cancel);return service
    def test_actual_output_revalidation_preserves_legal_manual_geometry_and_receipt(self):
        official=self.library.object_snapshot('TEMPLATE',self.templates[0].id);moved=self.move();fresh=self.workflow.revalidate(self.entries[0]);self.assertEqual(fresh.template.to_dict(),moved.template.to_dict());self.assertTrue(fresh.formal_eligible);self.assertEqual(fresh.risk_context['manual_revision'],1);self.assertEqual(self.library.object_snapshot('TEMPLATE',self.templates[0].id),official)
    def test_shared_name_update_keeps_manual_geometry_and_other_size_independent(self):
        moved=self.move();before_other=self.entries[1]['candidates'][0].template.to_dict();service=self.sync();current=service.selected(service.entries[0]);self.assertEqual(current.template.to_dict(),moved.template.to_dict());self.assertEqual(current.generation,8);self.assertIn('Alex Updated',[item.text for item in current.items]);self.assertTrue(current.formal_eligible);self.assertEqual(service.entries[1]['candidates'][0].template.to_dict(),before_other);self.assertIn('Alex Updated',[item.text for item in service.entries[1]['candidates'][0].items])
    def test_longer_source_never_shrinks_fixed_font_or_moves_locked_manual_frame(self):
        moved=self.move();adapter=self.adapter();identity=moved.template.slots[0].id;locked=apply_candidate(adapter,plan_operation(adapter,0,dict(operation='LOCK',ids=[identity],locked=True,cross_owner=False)),True);before=locked.template.to_dict();service=self.sync(self.changed_graph('LongName'*60));current=service.selected(service.entries[0]);self.assertEqual(current.template.to_dict(),before);self.assertTrue(current.template.slots[0].locked);self.assertEqual(current.risk['state'],'HARD_BLOCKED');self.assertFalse(current.formal_eligible)
    def test_new_equal_text_entity_cannot_inherit_old_person_manual_positions(self):
        moved=self.move();graph=InputGraph.from_legacy([dict(name=['Alex'],company='c1')],[dict(name='Synthetic Brand')]);service=self.sync(graph);current=service.selected(service.entries[0]);self.assertEqual(current.template.to_dict(),moved.template.to_dict());self.assertEqual(current.risk_context['edit_state'],'MANUAL_SOURCE_CONFLICT');self.assertFalse(current.formal_eligible);self.assertTrue(any(r['id']=='SHARED_SOURCE_SYNC_REQUIRED' for r in current.risk_context['conditions']))
    def test_restored_exact_source_reference_resolves_only_derived_sync_gap(self):
        self.move();other=InputGraph.from_legacy([dict(name=['Alex'],company='c1')],[dict(name='Synthetic Brand')]);conflicted=self.sync(other);restored=self.sync(self.graph.clone(),previous=conflicted.entries,generation=9);current=restored.selected(restored.entries[0]);self.assertTrue(current.formal_eligible);self.assertFalse(any(r['id']=='SHARED_SOURCE_SYNC_REQUIRED' for r in current.risk_context['conditions']));self.assertEqual(current.risk_context['manual_revision'],1)
    def test_missing_size_specific_logo_never_borrows_other_size_pass_after_sync(self):
        self.move();service=self.sync();self.assertTrue(service.selected(service.entries[0]).formal_eligible);second=service.selected(service.entries[1]);self.assertFalse(second.formal_eligible);self.assertFalse([item.logo for item in second.items if item.slot.kind=='logo' and item.logo]);self.assertEqual(second.template.width_mm,100)
    def test_cancelled_shared_sync_retains_manual_and_cancellation_state(self):
        moved=self.move();cancel=threading.Event();cancel.set();service=self.sync(cancel=cancel);first=service.entries[0];self.assertEqual(first['state'],'CANCELLED');self.assertEqual(service.selected(first).template.to_dict(),moved.template.to_dict());self.assertFalse(service.selected(first).formal_eligible)
    def test_candidate_budget_rejects_before_mutating_previous_collection(self):
        before=self.workflow.entries
        with patch.object(self.library,'templates',return_value=self.templates*101):
            with self.assertRaisesRegex(ValueError,'200候選'):self.workflow.calculate([[90,54],[100,60]])
        self.assertIs(self.workflow.entries,before)

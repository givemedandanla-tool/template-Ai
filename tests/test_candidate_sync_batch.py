"""Actual explicit cross-target adoption: safe target commits, failed one stays old."""
import copy,threading,unittest
from types import SimpleNamespace
import test_multi_size as fixture
from template_ai.model import new_id
from template_ai.candidate_sync import cross_property_plan,prepare_cross_batch,calculate_cross_batch,install_cross_batch
from template_ai.candidate_edit import apply_candidate,plan_operation,plan_candidate,plan_undo,plan_cross_properties


class CandidateSyncBatchTests(unittest.TestCase):
    def setUp(self):
        fixture.MultiSizeTests.setUp(self);self.alternate=copy.deepcopy(self.templates[0]);self.alternate.id=new_id();self.alternate.family_id=new_id();self.alternate.name='Synthetic alternative90';self.alternate.slots[0].rect.x+=2;self.library.publish(self.alternate);self.entries=self.workflow.calculate([[90,54],[100,60]]);self.a=self.adapter(0);self.source_index=next(i for i,c in enumerate(self.a.candidates) if c.template.id==self.templates[0].id);self.b_index=next(i for i,c in enumerate(self.a.candidates) if c.template.id==self.alternate.id);self.c=self.adapter(1);slot=self.a.candidates[self.source_index].template.slots[0]
        apply_candidate(self.a,plan_operation(self.a,self.source_index,dict(operation='PATCH',ids=[slot.id],patch=dict(align='center'),cross_owner=False)),True);self.adapters={'B90':(self.a,self.b_index),'C100':(self.c,0)}
    tearDown=fixture.MultiSizeTests.tearDown
    def adapter(self,index):
        entry=self.entries[index]
        return SimpleNamespace(library=self.library,candidates=entry['candidates'],generation=7,input_data=lambda:copy.deepcopy((self.workflow.people,self.workflow.companies,entry['resolved_logos'])),choose_candidate=lambda index:None)
    def source(self):return self.a.candidates[self.source_index]
    def targets(self):return [(key,adapter.candidates[index]) for key,(adapter,index) in self.adapters.items()]
    def prepare(self):
        source=self.source();plan=cross_property_plan(source,self.targets(),[source.template.slots[0].id],['align']);return prepare_cross_batch(plan,source,self.adapters,approved=True)
    def test_no_confirmation_cannot_prepare_adoption_or_mutate_any_target(self):
        source=self.source();before=[copy.deepcopy(c.template.to_dict()) for _,c in self.targets()];plan=cross_property_plan(source,self.targets(),[source.template.slots[0].id],['align'])
        with self.assertRaisesRegex(ValueError,'確認'):prepare_cross_batch(plan,source,self.adapters)
        self.assertEqual([c.template.to_dict() for _,c in self.targets()],before)
    def test_worker_only_returns_nonformal_copies_and_keeps_all_targets_unchanged(self):
        batch=self.prepare();before=[copy.deepcopy(c.template.to_dict()) for _,c in self.targets()];results=calculate_cross_batch(batch,self.library);self.assertEqual([r['state'] for r in results],['VERIFIED_PENDING_INSTALL','VALIDATION_FAILED']);self.assertTrue(all(not r['candidate'].formal_eligible for r in results));self.assertEqual([c.template.to_dict() for _,c in self.targets()],before)
    def test_only_qualified_target_applies_with_geometry_history_and_official_source_unchanged(self):
        batch=self.prepare();old_b=copy.deepcopy(self.a.candidates[self.b_index]);old_c=copy.deepcopy(self.c.candidates[0]);official=self.library.object_snapshot('TEMPLATE',self.alternate.id);results=install_cross_batch(batch,calculate_cross_batch(batch,self.library),self.source(),self.adapters);self.assertEqual([r['state'] for r in results],['APPLIED_VERIFIED','VALIDATION_FAILED']);new=self.a.candidates[self.b_index];self.assertEqual(new.template.slots[0].align,'center');self.assertEqual(new.template.slots[0].rect,old_b.template.slots[0].rect);self.assertEqual(self.c.candidates[0],old_c);self.assertEqual(new.risk_context['manual_revision'],1);self.assertTrue(new.formal_eligible);self.assertEqual(self.library.object_snapshot('TEMPLATE',self.alternate.id),official)
    def test_single_target_undo_never_reverts_source_or_other_size(self):
        batch=self.prepare();other=copy.deepcopy(self.c.candidates[0]);source=copy.deepcopy(self.source().template.to_dict());install_cross_batch(batch,calculate_cross_batch(batch,self.library),self.source(),self.adapters);restored=apply_candidate(self.a,plan_undo(self.a,self.b_index),True);self.assertEqual(restored.template.slots[0].align,'left');self.assertEqual(self.source().template.to_dict(),source);self.assertEqual(self.c.candidates[0],other);self.assertTrue(restored.formal_eligible)
    def test_new_source_manual_revision_rejects_previously_calculated_cross_batch(self):
        batch=self.prepare();results=calculate_cross_batch(batch,self.library);before=[copy.deepcopy(c.template.to_dict()) for _,c in self.targets()];source=self.source();apply_candidate(self.a,plan_candidate(self.a,self.source_index,[source.template.slots[0].id],.5,0),True);installed=install_cross_batch(batch,results,self.source(),self.adapters);self.assertTrue(all(r['state']=='STALE_IGNORED' for r in installed));self.assertEqual([c.template.to_dict() for _,c in self.targets()],before)
    def test_new_target_manual_revision_is_never_overwritten(self):
        batch=self.prepare();results=calculate_cross_batch(batch,self.library);target=self.a.candidates[self.b_index];apply_candidate(self.a,plan_candidate(self.a,self.b_index,[target.template.slots[0].id],.5,0),True);manual=copy.deepcopy(self.a.candidates[self.b_index]);installed=install_cross_batch(batch,results,self.source(),self.adapters);self.assertTrue(all(r['state']=='STALE_IGNORED' for r in installed));self.assertEqual(self.a.candidates[self.b_index],manual)
    def test_cancelled_batch_does_not_install_any_generated_result(self):
        batch=self.prepare();before=[copy.deepcopy(c.template.to_dict()) for _,c in self.targets()];cancel=threading.Event();cancel.set();results=install_cross_batch(batch,calculate_cross_batch(batch,self.library,cancel),self.source(),self.adapters);self.assertTrue(all(r['state']=='CANCELLED' for r in results));self.assertEqual([c.template.to_dict() for _,c in self.targets()],before)
    def test_required_unknown_target_cannot_become_safe_through_cross_alignment(self):
        target=self.a.candidates[self.b_index];target.risk_context.setdefault('conditions',[]).append(dict(id='SYNTHETIC_UNRESOLVED',status='UNKNOWN',reason='Synthetic required source evidence missing'));before=copy.deepcopy(target);batch=self.prepare();results=install_cross_batch(batch,calculate_cross_batch(batch,self.library),self.source(),self.adapters);self.assertEqual(results[0]['state'],'VALIDATION_FAILED');self.assertEqual(self.a.candidates[self.b_index],before);self.assertFalse(target.formal_eligible)
    def test_restricted_plan_cannot_smuggle_coordinate_or_font_changes(self):
        target=self.a.candidates[self.b_index];after=target.template.to_dict();after['slots'][0]['rect']['x']+=1
        with self.assertRaisesRegex(ValueError,'只接受'):plan_cross_properties(self.a,self.b_index,after,self.prepare()['plan']['source_pin'])
    def test_target_roundtrip_same_geometry_still_invalidates_old_cross_plan(self):
        batch=self.prepare();results=calculate_cross_batch(batch,self.library);target=self.a.candidates[self.b_index];before=target.template.to_dict();apply_candidate(self.a,plan_candidate(self.a,self.b_index,[target.template.slots[0].id],.5,0),True);apply_candidate(self.a,plan_undo(self.a,self.b_index),True);self.assertEqual(self.a.candidates[self.b_index].template.to_dict(),before);installed=install_cross_batch(batch,results,self.source(),self.adapters);self.assertTrue(all(r['state']=='STALE_IGNORED' for r in installed))

"""Original fixed-font candidate engine, exact identity/size seals and safe old-receipt inverse."""
import copy,unittest
from PySide6.QtWidgets import QDialog
from sync_workflow_fixture import SyncWorkflowFixture
from template_ai.batch_objects import prepare_candidate_target,calculate_candidate_target,install_candidate_target,fit_width_request
from template_ai.candidate_edit import plan_operation,plan_candidate,plan_undo,apply_candidate
from template_ai.object_tools import propose
from template_ai.model import Slot,Rect
from template_ai.demo import demo_template


class BatchCandidateAdapterTests(unittest.TestCase):
    def setUp(self):self.f=SyncWorkflowFixture();self.addCleanup(self.f.close);self.a,self.i=self.f.adapter('A90')
    def slot(self,kind='phone',owner='p1'):return next(s for s in self.a.candidates[self.i].template.slots if s.kind==kind and s.owner==owner)
    def target(self,kind='phone',owner='p1',align='center'):
        slot=self.slot(kind,owner);return prepare_candidate_target(self.a,self.i,dict(operation='PATCH',ids=[slot.id],patch={'align':align},cross_owner=False))
    def checked(self):return calculate_candidate_target(self.target(),self.a.library)
    def test_per_object_width_composition_preserves_individual_sizes_and_fixed_font_owner(self):
        t=demo_template();before=t.to_dict();ids=[t.slots[0].id,t.slots[2].id];request=dict(operation='PATCH_EACH',ids=ids,patches={ids[0]:dict(w=60),ids[1]:dict(w=50)},cross_owner=False);plan=propose(before,'TEMPLATE',request);self.assertEqual(t.to_dict(),before);self.assertEqual([plan['after']['slots'][i]['rect']['w'] for i in (0,2)],[60,50]);self.assertEqual([plan['after']['slots'][i]['size_pt'] for i in (0,2)],[18,10]);self.assertEqual({c['id'] for c in plan['changes']},set(ids))
    def test_per_object_patch_cannot_change_owner_font_or_anisotropic_whole_logo(self):
        t=demo_template();identity=t.slots[0].id;before=t.to_dict()
        with self.assertRaises(ValueError):propose(before,'TEMPLATE',dict(operation='PATCH_EACH',ids=[identity],patches={identity:dict(owner='p2')},cross_owner=False))
        t.slots.append(Slot('logo','c1',Rect(65,40,15,10)));logo=t.slots[-1]
        with self.assertRaises(ValueError):propose(t.to_dict(),'TEMPLATE',dict(operation='PATCH_EACH',ids=[logo.id],patches={logo.id:dict(w=20)},cross_owner=False))
        self.assertEqual(t.slots[0].owner,'p1');self.assertEqual(logo.rect.w,15)
    def test_fixed_x_ratio_uses_each_target_original_measurement_and_preserves_other_candidate_sizes(self):
        a,i=self.a,self.i;c=a.candidates[i];ids=[self.slot('name').id,self.slot().id];before=c.template.to_dict();other=self.f.candidate('B90').template.to_dict();size100=self.f.candidate('C100').template.to_dict();source=a.library.object_snapshot('TEMPLATE',c.template.id);request=fit_width_request(c,ids,.9);self.assertNotEqual(request['patches'][ids[0]]['w'],request['patches'][ids[1]]['w']);target=prepare_candidate_target(a,i,request);checked=calculate_candidate_target(target,a.library);self.assertEqual(checked['outcome'],'READY');result=install_candidate_target(a,checked,True);self.assertEqual(result['outcome'],'APPLIED_VALIDATED')
        current=a.candidates[i]
        for identity in ids:self.assertAlmostEqual(next(item.scale for item in current.items if item.slot.id==identity),.9,places=5)
        self.assertEqual([s.size_pt for s in current.template.slots],[s['size_pt'] for s in before['slots']]);self.assertEqual([s.owner for s in current.template.slots],[s['owner'] for s in before['slots']]);self.assertEqual(self.f.candidate('B90').template.to_dict(),other);self.assertEqual(self.f.candidate('C100').template.to_dict(),size100);self.assertFalse(self.f.candidate('C100').formal_eligible);self.assertEqual(a.library.object_snapshot('TEMPLATE',c.template.id),source)
    def test_floor_unknown_measurement_and_boolean_ratio_are_not_guessed(self):
        c=self.a.candidates[self.i];identity=self.slot().id
        for ratio in [.8,True,float('nan')]:
            with self.assertRaises(ValueError):fit_width_request(c,[identity],ratio)
        c=copy.deepcopy(c);c.measurements=[]
        with self.assertRaises(ValueError):fit_width_request(c,[identity],.9)
    def test_retry_reconciles_original_manual_receipt_without_second_edit_and_preserves_new_manual_move(self):
        checked=self.checked();first=install_candidate_target(self.a,checked,True);before=copy.deepcopy(self.a.candidates[self.i]);again=install_candidate_target(self.a,checked,True);self.assertEqual(again['outcome'],'ALREADY_APPLIED');self.assertEqual(first['receipt_id'],again['receipt_id']);self.assertEqual(self.a.candidates[self.i].risk_context['manual_revision'],1)
        identity=self.slot('name').id;apply_candidate(self.a,plan_candidate(self.a,self.i,[identity],.2,0),True);manual=self.a.candidates[self.i].template.to_dict();again=install_candidate_target(self.a,checked,True);self.assertEqual(again['outcome'],'APPLIED_BUT_CURRENT_CHANGED');self.assertEqual(self.a.candidates[self.i].template.to_dict(),manual);self.assertEqual(self.a.candidates[self.i].risk_context['manual_revision'],2)
    def test_manual_change_after_preflight_refuses_stale_install(self):
        checked=self.checked();identity=self.slot('name').id;apply_candidate(self.a,plan_candidate(self.a,self.i,[identity],.2,0),True);before=self.a.candidates[self.i].template.to_dict()
        with self.assertRaises(ValueError):install_candidate_target(self.a,checked,True)
        self.assertEqual(self.a.candidates[self.i].template.to_dict(),before)
    def test_changed_shared_input_after_preflight_never_retargets_old_field_or_installs(self):
        checked=self.checked();before=self.a.candidates[self.i].template.to_dict();self.f.change_phone('+12025550999')
        with self.assertRaises(ValueError):install_candidate_target(self.a,checked,True)
        self.assertEqual(self.a.candidates[self.i].template.to_dict(),before)
    def test_another_view_cannot_consume_exact_same_size_template_preflight(self):
        from template_ai.multi_size_edit import SizeEditAdapter
        checked=self.checked();other=QDialog(self.f.w);self.addCleanup(other.deleteLater);other.window=self.f.w;other.service=self.f.d.service;other.is_current=self.f.d.is_current;adapter=SizeEditAdapter(other,self.a.entry,self.i);before=self.a.candidates[self.i].template.to_dict()
        with self.assertRaisesRegex(ValueError,'視窗'):install_candidate_target(adapter,checked,True)
        self.assertEqual(self.a.candidates[self.i].template.to_dict(),before)
    def test_blocked_size100_missing_own_logo_cannot_inherit_size90_pass(self):
        adapter,index=self.f.adapter('C100');candidate=adapter.candidates[index];slot=next(s for s in candidate.template.slots if s.kind=='phone' and s.owner=='p1');before=candidate.template.to_dict();target=prepare_candidate_target(adapter,index,dict(operation='PATCH',ids=[slot.id],patch={'align':'center'},cross_owner=False));checked=calculate_candidate_target(target,adapter.library);self.assertEqual(checked['outcome'],'NEEDS_MANUAL_REVIEW')
        with self.assertRaises(ValueError):install_candidate_target(adapter,checked,True)
        self.assertEqual(adapter.candidates[index].template.to_dict(),before);self.assertTrue(self.f.candidate('A90').formal_eligible);self.assertFalse(adapter.candidates[index].formal_eligible)
    def test_same_phone_strings_still_have_distinct_person_and_field_references(self):
        c=self.a.candidates[self.i];items=[item for item in c.items if item.slot.kind=='phone'];self.assertEqual(items[0].text,items[1].text);a=self.target(owner='p1');b=self.target(owner='p2');self.assertNotEqual(a['references'],b['references'])
    def test_five_candidate_phone_alignments_use_own_geometry_and_no_first_candidate_coordinates(self):
        from template_ai.model import new_id
        from template_ai.layout import generate
        from template_ai.candidate_risk import bind_source
        from template_ai.multi_size_edit import SizeEditAdapter
        entry=self.a.entry
        for offset in (3,4,5):
            template=copy.deepcopy(self.f.templates['A90']);template.id=new_id();template.family_id=new_id();template.name='Authored independent '+str(offset)
            for slot in template.slots:
                if slot.owner.startswith('p'):slot.rect.x+=offset
            self.a.library.publish(template);candidate=generate(template,*self.a.input_data(),self.a.generation);bind_source(candidate,self.a.library,require_registered=True);entry['candidates'].append(candidate)
        self.assertEqual(len(entry['candidates']),5);targets=[];before=[]
        for index,candidate in enumerate(entry['candidates']):
            adapter=SizeEditAdapter(self.f.d,entry,index);slot=next(s for s in candidate.template.slots if s.kind=='phone' and s.owner=='p1');before.append(slot.rect.x);target=prepare_candidate_target(adapter,index,dict(operation='PATCH',ids=[slot.id],patch={'align':'center'},cross_owner=False));targets.append((adapter,calculate_candidate_target(target,adapter.library)))
        self.assertEqual(len({checked['target']['target_key'] for _,checked in targets}),5)
        for adapter,checked in targets:self.assertEqual(install_candidate_target(adapter,checked,True)['outcome'],'APPLIED_VALIDATED')
        self.assertEqual([next(s for s in c.template.slots if s.kind=='phone' and s.owner=='p1').rect.x for c in entry['candidates']],before);self.assertEqual(len(set(before)),5);self.assertFalse(self.f.candidate('C100').formal_eligible)
    def test_missing_stable_person_identity_is_manual_review_not_same_string_inference(self):
        candidate=copy.deepcopy(self.a.candidates[self.i]);candidate.risk_context['input_snapshot']['people'][0].pop('source_entity_id');self.a.candidates[self.i]=candidate
        with self.assertRaisesRegex(ValueError,'穩定來源'):self.target()
    def test_old_explicit_receipt_inverse_preserves_later_unrelated_manual_attribute(self):
        first=apply_candidate(self.a,plan_operation(self.a,self.i,dict(operation='PATCH',ids=[self.slot().id],patch={'align':'center'},cross_owner=False)),True);receipt=first.risk_context['manual_history'][-1]['id'];name=self.slot('name');oldx=name.rect.x;apply_candidate(self.a,plan_candidate(self.a,self.i,[name.id],.2,0),True);plan=plan_undo(self.a,self.i,receipt);result=apply_candidate(self.a,plan,True);self.assertEqual(next(s for s in result.template.slots if s.kind=='phone' and s.owner=='p1').align,'left');self.assertAlmostEqual(next(s for s in result.template.slots if s.id==name.id).rect.x,oldx+.2);self.assertTrue(next(r for r in result.risk_context['manual_history'] if r['id']==receipt)['undone'])
    def test_old_receipt_same_attribute_conflict_and_tampered_cached_result_do_not_overwrite(self):
        checked=self.checked();checked['candidate'].template.slots[0].rect.x+=1;before=self.a.candidates[self.i].template.to_dict()
        with self.assertRaises(ValueError):install_candidate_target(self.a,checked,True)
        self.assertEqual(self.a.candidates[self.i].template.to_dict(),before)
        first=apply_candidate(self.a,plan_operation(self.a,self.i,dict(operation='PATCH',ids=[self.slot().id],patch={'align':'center'},cross_owner=False)),True);receipt=first.risk_context['manual_history'][-1]['id'];apply_candidate(self.a,plan_operation(self.a,self.i,dict(operation='PATCH',ids=[self.slot().id],patch={'align':'right'},cross_owner=False)),True)
        with self.assertRaises(ValueError):plan_undo(self.a,self.i,receipt)

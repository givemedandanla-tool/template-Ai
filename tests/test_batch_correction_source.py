"""Precise source transactions, partial outcomes and existing-history inverse/retry."""
import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import test_seventy_ui as qt_fixture
from training_fixture import source_work
from template_ai.storage import Library
from template_ai.demo import demo_template
from template_ai.batch_objects import batch_plan,apply_batch,undo_batch,batch_summary,operation_id


class BatchCorrectionSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.lib=Library(self.root/'data');self.addCleanup(self.lib.close);self.serial=0
    def make(self):
        self.serial+=1;source,work=source_work(self.lib,self.root,f'card{self.serial}.svg',note_text=str(self.serial));return dict(id=work['id'],slot_ids=[work['payload']['slots'][0]['id']]),work
    def edit(self,work,**values):
        current=self.lib.artwork(work['id']);payload=copy.deepcopy(current['payload']);payload['slots'][0].update(values);return self.lib.save_artwork(work['id'],payload,current['revision'])
    def test_twelve_of_thirty_exact_sources_keep_same_text_entities_and_other_eighteen_unchanged(self):
        pairs=[self.make() for _ in range(30)];before={w['id']:self.lib.object_snapshot('ARTWORK',w['id']) for _,w in pairs};plan=batch_plan(self.lib,[t for t,_ in pairs[:12]],'center');results=apply_batch(self.lib,plan,True);self.assertEqual(len(results),12);self.assertTrue(all(r['outcome']=='APPLIED_PENDING_FULL_VALIDATION' for r in results))
        for index,(_,work) in enumerate(pairs):
            current=self.lib.object_snapshot('ARTWORK',work['id'])
            if index>=12:self.assertEqual(current,before[work['id']])
            else:
                self.assertEqual(current['payload']['slots'][0]['align'],'center');self.assertEqual(current['payload']['slots'][0]['size_pt'],18);self.assertEqual(current['payload']['slots'][0]['owner'],'p1')
        self.assertFalse(batch_summary(results)['formal_eligible'])
    def test_eight_applied_two_failed_one_manual_counts_are_exact_and_not_global_pass(self):
        pairs=[self.make() for _ in range(11)];self.edit(pairs[-1][1],locked=True);plan=batch_plan(self.lib,[t for t,_ in pairs],'center');real=self.lib.apply_object_edit;failed={pairs[8][1]['id'],pairs[9][1]['id']}
        def apply(snapshot,*args):
            if snapshot['id'] in failed:raise RuntimeError('authored per-item write failure')
            return real(snapshot,*args)
        with patch.object(self.lib,'apply_object_edit',side_effect=apply):results=apply_batch(self.lib,plan,True)
        summary=batch_summary(results);self.assertEqual(summary['checked'],11);self.assertEqual(summary['attempted'],10);self.assertEqual(summary['applied_pending_validation'],8);self.assertEqual(summary['failed'],2);self.assertEqual(summary['manual'],1);self.assertEqual(summary['status'],'PARTIAL_OR_BLOCKED');self.assertFalse(summary['formal_eligible'])
    def test_cancel_after_first_preserves_applied_result_and_cancels_only_unstarted(self):
        pairs=[self.make() for _ in range(3)];plan=batch_plan(self.lib,[t for t,_ in pairs],'center');events=[]
        results=apply_batch(self.lib,plan,True,cancel=lambda:any(r.get('history_id') for r in events),progress=events.append)
        self.assertEqual([r['outcome'] for r in results],['APPLIED_PENDING_FULL_VALIDATION','CANCELLED','CANCELLED']);self.assertEqual(self.lib.artwork(pairs[0][1]['id'])['payload']['slots'][0]['align'],'center');self.assertEqual([e['outcome'] for e in events].count('PROCESSING'),1)
        again=apply_batch(self.lib,plan,True,cancel=lambda:True);self.assertEqual(again[0]['state'],'ALREADY_APPLIED');self.assertEqual(again[0]['outcome'],'APPLIED_PENDING_FULL_VALIDATION')
    def test_relative_move_retry_reads_existing_operation_instead_of_moving_twice(self):
        target,work=self.make();target['request']=dict(operation='MOVE',ids=target['slot_ids'],dx=.2,dy=0,cross_owner=False);plan=batch_plan(self.lib,[target]);first=apply_batch(self.lib,plan,True);current=self.lib.artwork(work['id']);again=apply_batch(self.lib,plan,True)
        self.assertEqual(again[0]['state'],'ALREADY_APPLIED');self.assertEqual(first[0]['history_id'],again[0]['history_id']);self.assertEqual(self.lib.artwork(work['id']),current);self.assertAlmostEqual(current['payload']['slots'][0]['rect']['x'],8.2)
    def test_replay_after_newer_manual_change_is_explicit_and_preserves_new_values(self):
        target,work=self.make();plan=batch_plan(self.lib,[target],'center');apply_batch(self.lib,plan,True);self.edit(work,color='#abcdef');before=self.lib.artwork(work['id']);results=apply_batch(self.lib,plan,True);self.assertEqual(results[0]['outcome'],'APPLIED_BUT_CURRENT_CHANGED');self.assertFalse(results[0]['attempted']);self.assertEqual(self.lib.artwork(work['id']),before)
    def test_partial_undo_keeps_new_manual_edit_and_reverts_only_other_reversible_item(self):
        pairs=[self.make() for _ in range(2)];plan=batch_plan(self.lib,[t for t,_ in pairs],'center');results=apply_batch(self.lib,plan,True);self.edit(pairs[0][1],color='#abcdef');before=self.lib.artwork(pairs[0][1]['id']);undo=undo_batch(self.lib,plan,results,True)
        states={r['id']:r['outcome'] for r in undo};self.assertEqual(states[pairs[0][1]['id']],'UNDO_CONFLICT');self.assertEqual(states[pairs[1][1]['id']],'UNDONE_PENDING_FULL_VALIDATION');self.assertEqual(self.lib.artwork(pairs[0][1]['id']),before);self.assertEqual(self.lib.artwork(pairs[1][1]['id'])['payload']['slots'][0]['align'],'left')
    def test_single_explicit_inverse_does_not_undo_other_success_and_retry_cannot_redo_undone(self):
        pairs=[self.make() for _ in range(2)];plan=batch_plan(self.lib,[t for t,_ in pairs],'center');results=apply_batch(self.lib,plan,True);undo=undo_batch(self.lib,plan,results,True,[pairs[0][1]['id']]);self.assertEqual(len(undo),1);self.assertEqual(self.lib.artwork(pairs[1][1]['id'])['payload']['slots'][0]['align'],'center');again=apply_batch(self.lib,plan,True);self.assertEqual(again[0]['outcome'],'STALE');self.assertEqual(self.lib.artwork(pairs[0][1]['id'])['payload']['slots'][0]['align'],'left')
    def test_scope_or_library_changed_rejects_before_any_write(self):
        target,work=self.make();plan=batch_plan(self.lib,[target],'center');before=self.lib.artwork(work['id']);changed=copy.deepcopy(plan);changed['rows'][0]['request']['patch']['align']='right'
        with self.assertRaises(ValueError):apply_batch(self.lib,changed,True)
        other=Library(self.root/'other');self.addCleanup(other.close)
        with self.assertRaises(ValueError):apply_batch(other,plan,True)
        self.assertEqual(self.lib.artwork(work['id']),before)
    def test_locked_unknown_cross_person_logo_and_fixed_font_change_never_auto_approve(self):
        targets=[];works=[]
        for values in [dict(locked=True),dict(owner='UNKNOWN'),dict(kind='logo')]:
            target,work=self.make();self.edit(work,**values);targets.append(target);works.append(work)
        target,work=self.make();target['request']=dict(operation='PATCH',ids=target['slot_ids'],patch={'size_pt':10},cross_owner=False);targets.append(target);works.append(work)
        before=[self.lib.artwork(w['id']) for w in works];plan=batch_plan(self.lib,targets,'center');results=apply_batch(self.lib,plan,True);self.assertTrue(all(r['outcome']=='NEEDS_MANUAL_REVIEW' for r in results));self.assertEqual([self.lib.artwork(w['id']) for w in works],before)
    def test_noop_target_does_not_create_revision_or_history(self):
        target,work=self.make();plan=batch_plan(self.lib,[target],'left');before=self.lib.artwork(work['id']);results=apply_batch(self.lib,plan,True);self.assertEqual(results[0]['outcome'],'SKIPPED_PRECONDITION');self.assertFalse(results[0]['attempted']);self.assertEqual(self.lib.artwork(work['id']),before);self.assertEqual(self.lib.object_edit_history('ARTWORK',work['id']),[])
    def test_template_and_artwork_with_same_id_are_different_exact_undo_targets(self):
        target,work=self.make();template=demo_template();template.id=work['id'];self.lib.save_template(template);other=dict(kind='TEMPLATE',id=template.id,slot_ids=[template.slots[0].id]);plan=batch_plan(self.lib,[target,other],'center');results=apply_batch(self.lib,plan,True);self.assertEqual(len({r['target_key'] for r in results}),2)
        with self.assertRaises(ValueError):undo_batch(self.lib,plan,results,True,[work['id']])
        undo=undo_batch(self.lib,plan,results,True);self.assertTrue(all(r['outcome']=='UNDONE_PENDING_FULL_VALIDATION' for r in undo));self.assertEqual(len(undo),2)
    def test_false_or_truthy_nonboolean_approval_does_not_execute(self):
        target,work=self.make();plan=batch_plan(self.lib,[target],'center');before=self.lib.artwork(work['id'])
        for approved in [False,1,'yes']:
            with self.assertRaises(ValueError):apply_batch(self.lib,plan,approved)
        self.assertEqual(self.lib.artwork(work['id']),before)

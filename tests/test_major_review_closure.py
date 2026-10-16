"""Pinned case completion preserves blocked/unknown scopes and exact source repair history."""
import copy,unittest
import test_quality_source_review as fixture
from test_noise_authoring import confirmed
from template_ai.major_review_findings import plan as finding_plan,confirm as confirm_finding,reopen_plan,reopen
from template_ai.major_review_closure import plan,confirm
from template_ai.major_template_review import repair_plan,repair,plan as template_plan,confirm as confirm_template,CHECKS
from template_ai.training_store import digest
from template_ai.quality_rechecks import blocked


class MajorReviewClosureTests(unittest.TestCase):
    setUp=fixture.QualitySourceReviewTests.setUp
    source_plan=fixture.QualitySourceReviewTests.plan
    publish=fixture.QualitySourceReviewTests.publish
    def make(self,template=False):
        if template:self.template=self.publish();self.before=self.library.object_snapshot('TEMPLATE',self.template.id)
        self.case=self.service.confirm_source(self.source_plan(),'Synthetic reviewer','Explicit source scope review',True);self.unit=digest([self.case['id'],self.work['id']])
    def release_work(self):
        confirmed(self.store,self.work);return confirm_finding(self.service,finding_plan(self.service,self.case['id'],self.unit,'CHECKED_OK','All current source facts reviewed'),'Synthetic reviewer','Current full source truth',True)
    def test_unchecked_case_cannot_close_but_current_human_work_scope_can(self):
        self.make();value=plan(self.service,self.case['id']);self.assertFalse(value['can_close'])
        with self.assertRaises(ValueError):confirm(self.service,value,'Synthetic reviewer','Pending scope',True)
        self.release_work();value=plan(self.service,self.case['id']);self.assertTrue(value['can_close']);closed=confirm(self.service,value,'Synthetic reviewer','Only exact verified source scope',True);self.assertEqual(closed['state'],'SCOPED_REVIEW_COMPLETED');self.assertFalse(closed['whole_corpus_safe']);self.assertFalse(closed['models_decontaminated']);self.assertTrue(closed['completed']);self.assertFalse(blocked(self.store,self.work['id']))
    def test_exclusion_can_complete_defined_scope_while_source_remains_untrusted(self):
        self.make();value=finding_plan(self.service,self.case['id'],self.unit,'EXCLUDED_HOLD','Explicit source outside trusted-use scope, preserve hold');confirm_finding(self.service,value,'Synthetic reviewer','Auditable scope exclusion, no safe-source claim',True);value=plan(self.service,self.case['id']);self.assertTrue(value['can_close']);self.assertEqual(value['excluded_still_untrusted'],1);confirm(self.service,value,'Synthetic reviewer','Only excluded pinned scope completed',True);self.assertTrue(blocked(self.store,self.work['id']))
    def test_scope_version_change_after_closure_preview_is_refused(self):
        self.make();self.release_work();value=plan(self.service,self.case['id']);facts=self.store.facts(self.work['id']);self.store.save_facts(self.work['id'],facts['observations'],facts['revision'],self.work['revision'])
        with self.assertRaises(ValueError):confirm(self.service,value,'Synthetic reviewer','Stale closure',True)
        self.assertFalse(self.store.get('QUALITY_MAJOR_RECHECK',self.case['id'])['completed'])
    def test_case_completion_does_not_hide_unreviewed_template_and_can_reopen_exact_unit(self):
        self.make(True);self.release_work();value=plan(self.service,self.case['id']);self.assertFalse(value['can_close']);self.assertTrue(any(r['kind']=='QUALITY_TEMPLATE_QUARANTINE' for r in value['blockers']))
    def test_explicit_current_source_repair_draft_preserves_old_publication_and_provenance(self):
        self.make(True);self.release_work();unit=digest([self.case['id'],'TEMPLATE',self.template.id,self.template.version]);value=repair_plan(self.service,self.case['id'],unit,'Current source corrected draft',{});result=repair(self.service,value,'Synthetic reviewer','Explicit current source reconstruction, no old model geometry',True);draft=result['template'];self.assertEqual(draft['family_id'],self.template.family_id);self.assertEqual(draft['state'],'draft');self.assertEqual({s['id'] for s in draft['slots']},{s['id'] for s in self.work['payload']['slots']});self.assertEqual(self.library.object_snapshot('TEMPLATE',self.template.id),self.before);self.assertEqual(result['provenance']['action'],'CONFIRMED_SOURCE_REPAIR_DRAFT');again=repair(self.service,value,'Synthetic reviewer','Read exact repair receipt',True);self.assertTrue(again['replayed'])
    def test_reviewed_repair_version_can_complete_case_and_new_doubt_reopens_with_history(self):
        self.make(True);self.release_work();unit=digest([self.case['id'],'TEMPLATE',self.template.id,self.template.version]);draft=repair(self.service,repair_plan(self.service,self.case['id'],unit,'Current source draft',{}),'Synthetic reviewer','Explicit source draft',True)['template'];people=[dict(name=['Alex Example'],title=['Designer'],phone=['+1 202 555 0100'],email=['alex@example.test'])];value=template_plan(self.service,self.case['id'],unit,draft['id'],people,[],{},{k:True for k in CHECKS},'Full current source/size/fonts/mapping manually checked');self.assertTrue(value['can_release'],value['blockers']);confirm_template(self.service,value,'Synthetic reviewer','Exact source draft reviewed',True);value=plan(self.service,self.case['id']);self.assertTrue(value['can_close'],value['blockers']);closed=confirm(self.service,value,'Synthetic reviewer','Pinned source and exact draft version completed',True);history=self.store.history('QUALITY_MAJOR_RECHECK',self.case['id']) if hasattr(self.store,'history') else None;reopen(self.service,reopen_plan(self.service,self.case['id'],self.unit),'Synthetic reviewer','Later new source doubt',True);current=self.store.get('QUALITY_MAJOR_RECHECK',self.case['id']);self.assertEqual(current['state'],'REVIEW_REQUIRED');self.assertFalse(current['completed']);self.assertEqual(current['closure_receipt'],closed['closure_receipt']);self.assertTrue(blocked(self.store,self.work['id']))

if __name__=='__main__':unittest.main()

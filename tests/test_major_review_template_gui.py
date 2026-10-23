"""Actual major workbench exact template QA, source draft and pinned completion."""
import unittest
import test_major_review_gui as fixture
import test_quality_source_review as source_fixture
from test_noise_authoring import confirmed
from template_ai.input_graph import InputGraph
from template_ai.quality_rechecks import blocked
from template_ai.major_review_findings import plan as finding_plan,confirm as confirm_finding
from template_ai.training_store import digest
APP=fixture.APP


class MajorTemplateGuiTests(unittest.TestCase):
    setUp=fixture.MajorReviewGuiTests.setUp
    dispose=fixture.MajorReviewGuiTests.dispose
    wait=fixture.MajorReviewGuiTests.wait
    publish=source_fixture.QualitySourceReviewTests.publish
    def make(self,template=True):
        if template:self.template=self.publish()
        self.page.preview();self.wait();self.d.consent.setChecked(True);self.d.confirm();self.wait();self.case=self.page.case;confirmed(self.store,self.work);unit=digest([self.case['id'],self.work['id']]);confirm_finding(self.service,finding_plan(self.service,self.case['id'],unit,'CHECKED_OK','Manual current source complete facts'),'Synthetic reviewer','Only current source work cleared',True);self.page.load_case(0);self.wait()
        self.addCleanup(lambda:setattr(self.w.navigation,'confirm_close',lambda:True))
    def select_template(self):
        index=next(i for i,row in enumerate(self.page.rows) if row['kind']=='QUALITY_TEMPLATE_QUARANTINE');self.page.table.selectRow(index);self.page.use_template_unit();return self.page.rows[index]
    def fill(self):
        graph=InputGraph.from_legacy([dict(name=['Alex Example'],title=['Designer'],phone=['+1 202 555 0100'],email=['alex@example.test'])],[],{});self.w.adopt_input_graph(graph.data)
        for box in self.page.template_checks.values():box.setChecked(True)
        self.page.template_evidence.setText('Full exact source, owner fields, physical size, fonts and geometry checked')
    def save(self):self.d.consent.setChecked(True);self.d.confirm();self.wait()
    def test_actual_template_clearance_is_explicit_and_does_not_rewrite_original_version(self):
        self.make();before=self.library.object_snapshot('TEMPLATE',self.template.id);self.select_template();self.fill();self.page.preview_template();self.wait();self.assertIsNotNone(self.page.template_plan,self.d.status.text());self.assertTrue(self.page.template_plan['can_release'],self.page.template_plan['blockers']);self.save();self.library._template_provenance(self.template);self.assertEqual(self.library.object_snapshot('TEMPLATE',self.template.id),before);self.assertIn('修正後重新核准',self.page.counts.text())
    def test_missing_manual_check_or_current_input_failure_never_clears_template(self):
        self.make();self.select_template();self.page.template_evidence.setText('Not all manual checks completed');self.page.preview_template();self.wait();self.assertIsNone(self.page.template_plan)
        with self.assertRaises(ValueError):self.library._template_provenance(self.template)
        self.fill();self.w.adopt_input_graph(InputGraph.from_legacy([dict(name=['W'*150],title=['Designer'],phone=['+1 202 555 0100'],email=['alex@example.test'])],[],{}).data);self.page.preview_template();self.wait();self.assertIsNotNone(self.page.template_plan);self.assertFalse(self.page.template_plan['can_release']);self.d.consent.setChecked(True)
        with self.assertRaises(ValueError):self.d.confirm()
    def test_current_input_change_after_template_preview_does_not_use_old_qa(self):
        self.make();self.select_template();self.fill();self.page.preview_template();self.wait();self.w.adopt_input_graph(InputGraph.from_legacy([dict(name=['Newer human input'])],[],{}).data);self.d.consent.setChecked(True)
        with self.assertRaises(ValueError):self.d.confirm()
        self.assertEqual(self.store.count('QUALITY_TEMPLATE_CLEARANCE'),0)
    def test_actual_current_source_repair_saves_new_draft_and_keeps_old_reference_history(self):
        self.make();self.select_template();self.page.draft_name.setText('Authored current source correction');self.page.preview_repair();self.wait();self.assertIsNotNone(self.page.template_plan,self.d.status.text());identity=self.page.template_plan['template']['id'];self.save();self.assertEqual(self.page.template_target.text(),identity);snapshot=self.library.object_snapshot('TEMPLATE',identity);self.assertEqual(snapshot['payload']['state'],'draft');self.assertEqual(snapshot['payload']['source_work_id'],self.work['id']);self.assertEqual(self.library.object_snapshot('TEMPLATE',self.template.id)['payload']['state'],'published')
    def test_actual_source_only_scope_closes_with_unknown_corpus_and_model_quality_held_apart(self):
        self.make(False);self.page.preview_closure();self.wait();self.assertIsNotNone(self.page.template_plan,self.d.status.text());self.assertTrue(self.page.template_plan['can_close']);self.save();self.assertEqual(self.page.case['state'],'SCOPED_REVIEW_COMPLETED');self.assertFalse(self.page.case['whole_corpus_safe']);self.assertFalse(self.page.case['models_decontaminated']);self.assertFalse(blocked(self.store,self.work['id']))

if __name__=='__main__':unittest.main()

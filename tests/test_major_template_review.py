"""Exact source/style review, current whole-card checks and no renamed draft bypass."""
import copy,unittest
import test_quality_source_review as fixture
from test_noise_authoring import confirmed
from template_ai.major_review_findings import plan as finding_plan,confirm as confirm_finding
from template_ai.major_template_review import plan,confirm,CHECKS
from template_ai.template_versions import TemplateVersions
from template_ai.model import new_id
from template_ai.training_store import digest
from template_ai.candidate_risk import bind_source
from template_ai.layout import generate


class MajorTemplateReviewTests(unittest.TestCase):
    setUp=fixture.QualitySourceReviewTests.setUp
    source_plan=fixture.QualitySourceReviewTests.plan
    publish=fixture.QualitySourceReviewTests.publish
    candidate=fixture.QualitySourceReviewTests.candidate
    def make(self):
        self.template=self.publish();self.before=self.library.object_snapshot('TEMPLATE',self.template.id);self.case=self.service.confirm_source(self.source_plan(),'Synthetic reviewer','Exact published source and family review',True);self.work_unit=digest([self.case['id'],self.work['id']]);self.unit_id=digest([self.case['id'],'TEMPLATE',self.template.id,self.template.version]);confirmed(self.store,self.work);confirm_finding(self.service,finding_plan(self.service,self.case['id'],self.work_unit,'CHECKED_OK','All original source facts manually reverified'),'Synthetic reviewer','Only release source work, templates remain held',True);self.people=[dict(name=['Alex Example'],title=['Designer'],phone=['+1 202 555 0100'],email=['alex@example.test'])]
    def plan(self,target=None,people=None,checks=None):return plan(self.service,self.case['id'],self.unit_id,(target or self.template).id,people or self.people,[],{},checks if checks is not None else {key:True for key in CHECKS},'Exact source fields and full physical size manually inspected')
    def test_work_only_release_does_not_release_old_template_family_or_new_source_alias(self):
        self.make();versions=TemplateVersions(self.library);draft=versions.clone(versions.plan(self.template.id),'Synthetic reviewer','Explicit isolated new version draft',True)
        with self.assertRaises(ValueError):self.library.publish(draft)
        other=copy.deepcopy(draft);other.id=new_id();other.family_id=new_id();self.library.save_template(other)
        with self.assertRaises(ValueError):self.library.publish(other)
        self.assertEqual(self.library.object_snapshot('TEMPLATE',self.template.id),self.before)
    def test_exact_current_old_version_can_be_reverified_without_mutating_publication(self):
        self.make();value=self.plan();self.assertTrue(value['can_release'],value['blockers']);receipt=confirm(self.service,value,'Synthetic reviewer','Current exact template fully reverified',True);self.assertTrue(receipt['reviewed']);self.assertFalse(receipt['model_quality_released']);self.assertEqual(self.library.object_snapshot('TEMPLATE',self.template.id),self.before);self.library._template_provenance(self.template);candidate=self.candidate(self.template);self.assertTrue(candidate.formal_eligible,candidate.risk)
    def test_reviewed_new_draft_can_publish_but_another_unreviewed_version_remains_blocked(self):
        self.make();versions=TemplateVersions(self.library);draft=versions.clone(versions.plan(self.template.id),'Synthetic reviewer','Exact isolated correction draft',True);value=self.plan(draft);self.assertTrue(value['can_release'],value['blockers']);confirm(self.service,value,'Synthetic reviewer','Current draft physical/semantic source checks',True);self.library.publish(draft);self.assertEqual(self.library.object_snapshot('TEMPLATE',draft.id)['payload']['state'],'published');self.assertTrue(self.candidate(draft).formal_eligible)
        another=versions.clone(versions.plan(draft.id),'Synthetic reviewer','Next version still requires own checks',True)
        with self.assertRaises(ValueError):self.library.publish(another)
        with self.assertRaises(ValueError):self.library._template_provenance(self.template)
    def test_unsaved_geometry_cannot_reuse_old_exact_clearance_during_publication(self):
        self.make();draft=TemplateVersions(self.library).clone(TemplateVersions(self.library).plan(self.template.id),'Synthetic reviewer','Current draft',True);value=self.plan(draft);self.assertTrue(value['can_release'],value['blockers']);confirm(self.service,value,'Synthetic reviewer','Exact reviewed draft',True);draft.slots[0].rect.x+=.1
        with self.assertRaises(ValueError):self.library.publish(draft)
        self.assertEqual(self.library.object_snapshot('TEMPLATE',draft.id)['payload']['state'],'draft')
    def test_current_width_or_missing_manual_check_is_not_waived_by_old_publication(self):
        self.make();people=copy.deepcopy(self.people);people[0]['name']=['W'*150];value=self.plan(people=people);self.assertFalse(value['can_release']);self.assertTrue(value['blockers'])
        with self.assertRaises(ValueError):confirm(self.service,value,'Synthetic reviewer','Cannot waive current hard failure',True)
        checks={key:True for key in CHECKS};checks['whole_logo']=False
        with self.assertRaises(ValueError):self.plan(checks=checks)
    def test_changed_source_facts_after_template_preflight_prevent_clearance(self):
        self.make();value=self.plan();facts=self.store.facts(self.work['id']);self.store.save_facts(self.work['id'],facts['observations'],facts['revision'],self.work['revision'])
        with self.assertRaises(ValueError):confirm(self.service,value,'Synthetic reviewer','Stale current source facts',True)
        self.assertEqual(self.store.count('QUALITY_TEMPLATE_CLEARANCE'),0)
    def test_canonical_source_field_coverage_cannot_be_hidden_by_omitting_validation_input(self):
        self.make();draft=TemplateVersions(self.library).clone(TemplateVersions(self.library).plan(self.template.id),'Synthetic reviewer','Try changed shape scope',True);draft.slots=[s for s in draft.slots if s.kind!='phone'];self.library.save_template(draft);people=copy.deepcopy(self.people);people[0]['phone']=[];value=self.plan(draft,people=people);self.assertFalse(value['can_release']);self.assertTrue(any('標記集合' in reason for reason in value['blockers']))

if __name__=='__main__':unittest.main()

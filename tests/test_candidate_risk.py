"""Real fixed-font candidates and actual final/marked-preview exports under tri-state gates."""
import copy,unittest
from pathlib import Path
from unittest.mock import patch
import test_first_version as fixture
from template_ai.layout import generate
from template_ai.render import export
from template_ai.candidate_risk import assess,search_result,transient_draft,bind_source

class CandidateRiskTests(unittest.TestCase):
    setUp=fixture.FirstVersionTests.setUp
    def people(self):return [dict(name=['Alex Example'],title=['Designer'],phone=['+1 202 555 0100'],email=['qa@example.test'])]
    def candidate(self):return generate(self.template,self.people(),[],{},7)
    def test_manual_approved_rule_template_is_safe_without_arbitrary_sample_or_score_threshold(self):
        candidate=self.candidate();self.assertTrue(candidate.valid);candidate.score=.000001;candidate.risk_context.update(sample_count=0,confidence=None);result=assess(candidate);self.assertEqual(result['state'],'SAFE_RECOMMENDATION');self.assertTrue(result['formal_allowed']);self.assertFalse(result['automatic_learning']);self.assertFalse(result['supplementation']);self.assertEqual(result['score_kind'],'RULE_FITNESS_NOT_CALIBRATED_CONFIDENCE')
    def test_real_width_failure_is_hard_and_high_confidence_or_accepted_label_cannot_export(self):
        self.template.slots[0].rect.w=.1;candidate=self.candidate();self.assertFalse(candidate.valid);candidate.score=1e9;candidate.risk_context.update(accept_risk=True,confidence=1,display_state='SAFE_RECOMMENDATION');self.assertEqual(assess(candidate)['state'],'HARD_BLOCKED');target=self.root/'blocked-FINAL.png'
        with self.assertRaises(ValueError):export(candidate,target,150,False,7)
        self.assertFalse(target.exists());candidate.issues=[]
        with self.assertRaisesRegex(ValueError,'分級風險Gate'):export(candidate,target,150,False,7)
        self.assertFalse(target.exists())
    def test_missing_font_is_unknown_not_a_proven_unsatisfiable_search(self):
        self.template.slots[0].font='Definitely Missing Synthetic Face';candidate=self.candidate();result=assess(candidate);self.assertEqual(result['state'],'EVIDENCE_REQUIRED');self.assertFalse(result['known_hard_conditions_passed']);summary=search_result([candidate],scope_complete=True);self.assertFalse(summary['proven_unsatisfiable_in_declared_scope']);self.assertFalse(summary['global_unsolvable'])
    def test_explicit_transient_review_preserves_hard_pass_but_final_fails_and_preview_is_marked(self):
        candidate=self.candidate();before=self.template.to_dict();draft=transient_draft(candidate,'Non-hard style evidence needs explicit local human correction');self.assertTrue(draft.valid);self.assertEqual(assess(draft)['state'],'REVIEW_DRAFT');self.assertTrue(assess(draft)['known_hard_conditions_passed']);self.assertFalse(draft.formal_eligible)
        with self.assertRaises(ValueError):export(draft,self.root/'review-FINAL.png',150,False,7)
        path=export(draft,self.root/'review-PREVIEW.png',150,True,7);self.assertTrue(path.is_file());self.assertEqual(self.template.to_dict(),before);self.assertEqual(self.library.templates(),[])
    def test_required_source_gap_never_claims_hard_pass_or_becomes_safe_by_accepting_risk(self):
        candidate=self.candidate();candidate.risk_context['conditions']=[dict(id='SOURCE_SCOPE',status='UNKNOWN',reason='Actual source scope still missing')];candidate.risk_context['accept_risk']=True;result=assess(candidate);self.assertEqual(result['state'],'EVIDENCE_REQUIRED');self.assertFalse(result['known_hard_conditions_passed']);self.assertFalse(result['formal_allowed']);self.assertFalse(transient_draft(candidate,'Keep working without formal output').formal_eligible)
    def test_only_complete_nonempty_all_known_fail_scope_has_bounded_failure_certificate(self):
        self.template.slots[0].rect.w=.1;candidate=self.candidate();complete=search_result([candidate],scope_complete=True);self.assertTrue(complete['proven_unsatisfiable_in_declared_scope']);self.assertFalse(complete['all_possible_designs_checked'])
        for summary in (search_result([],scope_complete=True),search_result([candidate],scope_complete=False),search_result([candidate],scope_complete=True,unstarted=1),search_result([candidate],scope_complete=True,excluded=['Source missing'])):self.assertFalse(summary['proven_unsatisfiable_in_declared_scope'])
    def test_actual_source_provenance_rejection_is_required_unknown_without_mutating_template(self):
        candidate=self.candidate();before=candidate.template.to_dict()
        with patch.object(self.library,'_template_provenance',side_effect=ValueError('Actual provenance is no longer usable')):result=bind_source(candidate,self.library)
        self.assertEqual(result['state'],'EVIDENCE_REQUIRED');self.assertFalse(result['formal_allowed']);self.assertEqual(candidate.template.to_dict(),before)

    def test_mutated_input_template_placement_and_assets_require_regeneration(self):
        baseline=copy.deepcopy(self.template)
        for mutate in (lambda c:c.risk_context['input_snapshot']['people'][0]['name'].append('Unknown extra value'),lambda c:setattr(c.template.slots[0].rect,'w',.1),lambda c:setattr(c.items[0],'text','Altered after measurement')):
            self.template=copy.deepcopy(baseline);candidate=self.candidate();mutate(candidate)
            self.assertFalse(candidate.formal_eligible)
            with self.assertRaises(ValueError):export(candidate,self.root/'stale-FINAL.png',150,False,7)
        candidate=self.candidate();asset=self.root/'new-background.svg';asset.write_text('<svg/>');candidate.template.background={'path':str(asset)}
        self.assertFalse(candidate.formal_eligible)
    def test_clearing_diagnostics_cannot_skip_actual_engine_recheck(self):
        self.template.slots[0].rect.w=.1;candidate=self.candidate();candidate.issues=[];candidate.diagnostics=[]
        with self.assertRaisesRegex(ValueError,'重核不通過'):export(candidate,self.root/'tampered-FINAL.png',150,False,7)
        self.assertFalse((self.root/'tampered-FINAL.png').exists())
    def test_acceptance_flag_is_not_a_published_baseline_receipt(self):
        self.template.state='draft';candidate=self.candidate();candidate.risk_context['approved_base']=True
        self.assertEqual(candidate.risk['state'],'EVIDENCE_REQUIRED');self.assertFalse(candidate.risk['known_hard_conditions_passed'])
    def test_fresh_source_binding_does_not_silently_drop_explicit_review(self):
        candidate=transient_draft(self.candidate(),'Explicit unresolved style review')
        bind_source(candidate,self.library);self.assertEqual(candidate.risk['state'],'REVIEW_DRAFT');self.assertFalse(candidate.formal_eligible)

    def test_engine_or_rule_version_change_invalidates_old_candidate_and_requires_regeneration(self):
        candidate=self.candidate();self.assertTrue(candidate.formal_eligible)
        with patch('template_ai.candidate_risk.engine_digest',return_value='changed-explicit-rules'):
            self.assertFalse(candidate.formal_eligible);self.assertEqual(candidate.risk['state'],'EVIDENCE_REQUIRED')
            with self.assertRaises(ValueError):export(candidate,self.root/'old-engine-FINAL.png',150,False,7)
        self.assertTrue(candidate.formal_eligible)

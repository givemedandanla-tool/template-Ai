"""Current finite-scope recommendation: actual gates precede existing scores."""
import copy,unittest
from template_ai.model import new_id
from template_ai.layout import generate
from template_ai.candidate_risk import bind_source
from template_ai.candidate_results import recommendation,current_assessment
import test_seventy_ui as fixture
from gui_wait import wait_layout


class CandidateResultsTests(unittest.TestCase):
    setUp=fixture.SeventyUiTests.setUp
    close_window=fixture.SeventyUiTests.close_window
    def ready(self):self.w.generate();wait_layout(self.w);return self.w.candidates[0]
    def another(self,*,width=None):
        template=copy.deepcopy(self.t);template.id=new_id();template.family_id=new_id();template.name='Synthetic other candidate'
        if width is not None:template.slots[0].rect.w=width
        self.w.library.publish(template);candidate=generate(template,*self.w.input_data(),self.w.generation);bind_source(candidate,self.w.library,require_registered=True);self.w.candidates.append(candidate);self.w.candidate_list.addItem(template.name);return candidate
    def test_actual_completed_scope_recommends_only_current_qualified_rule_result(self):
        c=self.ready();state=recommendation(self.w);self.assertEqual(state['index'],0);self.assertTrue(state['scope_complete']);self.assertFalse(state['global_optimality_proven']);self.assertFalse(state['calibrated_confidence']);self.assertIn('不是模型信心',state['label']);self.assertIn(c.template.name,self.w.result_recommendation.text())
    def test_high_scoring_hard_block_never_becomes_recommendation(self):
        self.ready();bad=self.another(width=.1);bad.score=1e12;self.assertEqual(bad.risk['state'],'HARD_BLOCKED');self.assertEqual(recommendation(self.w)['index'],0)
    def test_partial_scope_does_not_claim_global_optimum_or_complete_search(self):
        self.ready();self.w.last_layout_summary.update(state='CANCELLED',total=3,checked=1,unstarted=2);state=recommendation(self.w);self.assertEqual(state['index'],0);self.assertFalse(state['scope_complete']);self.assertIn('未開始 2',state['scope_label']);self.assertFalse(state['global_optimality_proven'])
    def test_stale_generation_and_different_dimensions_never_recommend(self):
        self.ready();self.w.people.item(0,2).setText('1234567');self.assertIsNone(recommendation(self.w)['index']);self.w.candidates[0].generation=self.w.generation;self.assertFalse(current_assessment(self.w,0)['formal_allowed']);self.w.out_w.setValue(100);self.assertFalse(current_assessment(self.w,0)['formal_allowed'])
    def test_nonfinite_score_is_not_ranked_as_safe_confidence(self):
        c=self.ready();c.score=float('nan');self.assertIsNone(recommendation(self.w)['index']);c.score=float('inf');self.assertIsNone(recommendation(self.w)['index'])
    def test_finite_score_tie_is_deterministic_without_mutating_candidates(self):
        c=self.ready();other=self.another();c.score=other.score=42;before=[x.template.to_dict() for x in self.w.candidates];expected=min(range(2),key=lambda i:self.w.candidates[i].template.id);self.assertEqual(recommendation(self.w)['index'],expected);self.assertEqual(recommendation(self.w)['index'],expected);self.assertEqual([x.template.to_dict() for x in self.w.candidates],before)
    def test_actual_recommend_button_selects_safe_candidate_without_business_write(self):
        c=self.ready();bad=self.another(width=.1);self.w.candidate_list.setCurrentRow(1);self.assertFalse(self.w.export_button.isEnabled());before=self.w.library.object_snapshot('TEMPLATE',c.template.id);self.w.select_recommended_candidate();self.assertEqual(self.w.candidate_list.currentRow(),0);self.assertTrue(self.w.export_button.isEnabled());self.assertEqual(self.w.library.object_snapshot('TEMPLATE',c.template.id),before);self.assertFalse(bad.formal_eligible)
    def test_invalid_company_input_is_explicit_unknown_without_gui_exception(self):
        self.ready();self.w.people.item(0,7).setText('not-a-company');state=recommendation(self.w);self.assertIsNone(state['index']);self.w.refresh_input_problems();self.assertFalse(self.w.recommended_button.isEnabled())

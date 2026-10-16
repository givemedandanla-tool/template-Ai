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

    def test_native_comparison_is_nonformal_and_safe_selection_never_erases_blocks(self):
        from template_ai.candidate_results import ResultComparisonDialog
        c=self.ready();bad=self.another(width=.1);before=[x.template.to_dict() for x in self.w.candidates];dialog=ResultComparisonDialog(self.w);self.addCleanup(dialog.deleteLater);dialog.show();self.assertTrue(all(not x.formal_eligible for x in dialog.snapshots));self.assertTrue(any(dialog.gates.item(i,1).text()=='PASS' and dialog.gates.item(i,2).text()=='FAIL' for i in range(dialog.gates.rowCount())));self.assertTrue(dialog.select_side(1));self.assertEqual(self.w.candidate_list.currentRow(),1);self.assertFalse(self.w.export_button.isEnabled());self.assertEqual([x.template.to_dict() for x in self.w.candidates],before)
    def test_comparison_rejects_later_input_and_keeps_existing_manual_geometry(self):
        from template_ai.candidate_results import ResultComparisonDialog
        from template_ai.candidate_edit import apply_candidate,plan_candidate
        c=self.ready();self.another();apply_candidate(self.w,plan_candidate(self.w,0,[c.template.slots[0].id],1,0),True);manual=self.w.candidates[0].template.to_dict();dialog=ResultComparisonDialog(self.w);self.addCleanup(dialog.deleteLater);dialog.show();self.w.people.item(0,2).setText('1234567');self.assertFalse(dialog.check_current());self.assertFalse(dialog.select_side(1));self.assertIn('過期',dialog.status.text());self.assertEqual(self.w.candidates[0].template.to_dict(),manual)
    def test_typed_phone_problem_focuses_actual_legacy_owner_field_and_slot(self):
        from template_ai.candidate_results import problem_rows,locate_problem
        from template_ai.gui import Box
        self.ready();self.w.people.item(0,2).setText('1234567890'*20);self.w.generate();wait_layout(self.w);rows=problem_rows(self.w,0);phone=next(r for r in rows if r['code']=='WIDTH' and r['kind']=='phone');before=self.w.candidates[0].template.to_dict();result=locate_problem(self.w,phone);self.assertEqual(result['field']['owner'],'p1');self.assertEqual((self.w.people.currentRow(),self.w.people.currentColumn()),(0,2));self.assertEqual([i.slot.id for i in self.w.output_canvas.scene().selectedItems() if isinstance(i,Box)],phone['slot_ids']);self.assertEqual(self.w.candidates[0].template.to_dict(),before);self.assertFalse(self.w.export_button.isEnabled())
    def test_problem_from_old_generation_cannot_focus_reordered_current_input(self):
        from template_ai.candidate_results import problem_rows,locate_problem
        self.ready();bad=self.another(width=.1);row=next(r for r in problem_rows(self.w,1) if r['code']=='WIDTH');self.w.people.item(0,0).setText('Changed owner')
        with self.assertRaisesRegex(ValueError,'更新|過期'):locate_problem(self.w,row)
        self.assertFalse(self.w.export_button.isEnabled())
    def test_required_unknown_has_explicit_source_route_instead_of_invented_slot(self):
        from template_ai.candidate_results import problem_rows,locate_problem
        c=self.ready();c.risk_context.setdefault('conditions',[]).append(dict(id='SOURCE_GAP',status='UNKNOWN',reason='Synthetic required source proof missing'));row=next(r for r in problem_rows(self.w,0) if r['code']=='SOURCE_GAP');self.assertEqual(row['route'],'source');self.assertFalse(row['slot_ids']);result=locate_problem(self.w,row,open_input=False);self.assertIsNone(result['field']);self.assertFalse(self.w.export_button.isEnabled())
    def test_actual_problem_click_opens_existing_candidate_fix_entry(self):
        from unittest.mock import patch
        self.ready();self.another(width=.1);self.w.candidate_list.setCurrentRow(1);index=next(i for i in range(self.w.result_problem_items.count()) if self.w.result_problem_items.item(i).data(fixture.Qt.UserRole)['code']=='WIDTH');self.w.result_problem_items.setCurrentRow(index)
        with patch.object(self.w,'candidate_editor') as open_existing:self.w.fix_result_problem();open_existing.assert_called_once()
    def test_structured_input_problem_opens_exact_stable_field_without_adoption(self):
        from PySide6.QtCore import QTimer
        from template_ai.input_graph import InputGraph
        from template_ai.input_graph_dialog import InputGraphDialog
        from template_ai.candidate_results import problem_rows,locate_problem
        from unittest.mock import patch
        people,companies,logos=self.w.input_data();people[0]['phone']=['1234567890'*20];graph=InputGraph.from_legacy(people,companies,logos);self.w.adopt_input_graph(graph.data);self.w.generate();wait_layout(self.w);row=next(r for r in problem_rows(self.w,0) if r['code']=='WIDTH' and r['kind']=='phone');before=copy.deepcopy(self.w.active_input_graph.data);seen=[];real_exec=InputGraphDialog.exec
        def inspect_exec(dialog):
            def inspect():
                seen.append((dialog.selected_id,dialog.field_editors[dialog.selected_id].text()));dialog.reject()
            QTimer.singleShot(30,dialog,inspect);return real_exec(dialog)
        with patch.object(InputGraphDialog,'exec',inspect_exec):target=locate_problem(self.w,row)
        self.assertEqual(seen,[(target['field']['field_id'],'1234567890'*20)]);self.assertEqual(self.w.active_input_graph.data,before)

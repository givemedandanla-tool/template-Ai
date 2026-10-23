"""Native three-way candidate routing and explicit transient-only correction."""
from gui_wait import wait_layout,wait_candidate_edits
import copy,unittest
from unittest.mock import patch
from PySide6.QtWidgets import QTableWidgetItem,QInputDialog
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
import test_parent_navigation as fixture
from template_ai.demo import demo_template
from template_ai.candidate_risk import transient_draft
APP=fixture.APP

class CandidateRiskGuiTests(unittest.TestCase):
    setUp=fixture.ParentNavigationTests.setUp
    def seed(self):
        good=demo_template();good.name='Synthetic safe';bad=demo_template();bad.name='Synthetic hard block';bad.slots[0].rect.w=.1
        self.w.library.publish(good);self.w.library.publish(bad);self.w.people.setRowCount(1)
        for col,value in enumerate(('Alex Example','Designer','123','a@example.test','','','','')):self.w.people.setItem(0,col,QTableWidgetItem(value))
        self.w.tabs.setCurrentIndex(2);self.w.generate();wait_layout(self.w);APP.processEvents()
    def test_real_three_groups_marked_preview_and_explicit_recheck_without_database_writes(self):
        self.seed();before=[t.to_dict() for t in self.w.library.templates()];candidate=transient_draft(self.w.candidates[0],'Explicit local non-hard review');self.w.candidates.append(candidate);self.w.candidate_list.addItem('Synthetic review');self.w.choose_candidate(2)
        self.assertEqual((self.w.qualified_candidates.count(),self.w.review_candidates.count(),self.w.blocked_candidates.count()),(1,1,1));self.assertFalse(self.w.export_button.isEnabled());self.assertTrue(self.w.preview_button.isEnabled());self.assertIn('待確認草稿',self.w.issues.text());self.assertNotIn('數位排版檢查通過',self.w.issues.text())
        view=self.w.review_candidates;QTest.mouseClick(view.viewport(),Qt.LeftButton,pos=view.visualItemRect(view.item(0)).center());APP.processEvents();self.w.recheck_candidate();wait_candidate_edits(self.w);self.assertTrue(self.w.export_button.isEnabled());self.assertEqual([t.to_dict() for t in self.w.library.templates()],before)
    def test_actual_keep_draft_action_is_memory_only_and_invalidated_input_blocks_it(self):
        self.seed();self.w.candidate_list.setCurrentRow(0);before=[t.to_dict() for t in self.w.library.templates()]
        with patch.object(QInputDialog,'getText',return_value=('Need explicit style review',True)):self.w.keep_review_draft()
        self.assertTrue(self.w.candidates[0].risk_context['transient_only']);self.assertFalse(self.w.export_button.isEnabled());self.assertEqual([t.to_dict() for t in self.w.library.templates()],before)
        self.w.people.item(0,0).setText('Changed input');self.assertFalse(self.w.review_candidates.isEnabled());self.assertFalse(self.w.preview_button.isEnabled())
    def test_current_provenance_change_reclassifies_previously_safe_candidate(self):
        self.seed();self.assertTrue(self.w.export_button.isEnabled())
        with patch.object(self.w.library,'_template_provenance',side_effect=ValueError('Actual current source no longer valid')):self.w.choose_candidate(0)
        self.assertFalse(self.w.export_button.isEnabled());self.assertEqual(self.w.review_candidates.count(),1);self.assertIn('來源',self.w.issues.text());self.assertFalse(self.w.candidates[0].risk['known_hard_conditions_passed'])

    def test_explicit_recheck_cannot_clear_unresolved_required_evidence_by_acceptance(self):
        self.seed();candidate=self.w.candidates[0];candidate.risk_context.setdefault('conditions',[]).append(dict(id='ESSENTIAL_SOURCE_REVIEW',status='UNKNOWN',required=True,reason='Actual essential evidence is unresolved'));self.w.choose_candidate(0);self.assertFalse(self.w.export_button.isEnabled());self.w.recheck_candidate();wait_candidate_edits(self.w);self.assertFalse(self.w.export_button.isEnabled());self.assertEqual(self.w.candidates[0].risk['state'],'EVIDENCE_REQUIRED');self.assertTrue(any(c['id']=='ESSENTIAL_SOURCE_REVIEW' for c in self.w.candidates[0].risk['conditions']))

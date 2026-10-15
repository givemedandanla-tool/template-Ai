from copy import deepcopy
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QMessageBox,QTableWidgetItem
from PySide6.QtTest import QTest
from template_ai.storage import Library
from template_ai.demo import demo_template
from template_ai.custom_layout import CustomLayout
from template_ai.custom_layout_dialog import CustomLayoutDialog
from template_ai.layout import generate
from template_ai.gui import MainWindow
APP=QApplication.instance() or QApplication([])

class CustomLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.library=Library(self.root/'data');self.addCleanup(self.library.close);self.t=demo_template();self.t.slots[0].rect.w=20;self.library.publish(self.t);self.service=CustomLayout(self.library);self.people=[dict(name=['Alex Example'],title=['Designer'],phone=['123'],email=['a@example.test'])];self.policy=dict(move_mm=0,expand_mm=40,gap_mm=0)
    def plan(self):return self.service.plan(self.t.id,self.people,[],{},self.policy,7)
    def test_solver_bounded_geometry_keeps_owner_fonts_logo_and_source_then_requires_draft_publication(self):
        old=self.library.object_snapshot('TEMPLATE',self.t.id);plan=self.plan();self.assertEqual(plan['status'],'FEASIBLE_DRAFT');self.assertFalse(plan['preview_candidate'].valid);self.assertGreater(plan['draft']['slots'][0]['rect']['w'],20)
        for before,after in zip(self.t.to_dict()['slots'],plan['draft']['slots']):
            for key in set(before)-{'rect'}:self.assertEqual(before[key],after[key])
        with self.assertRaises(ValueError):self.service.create_draft(plan,self.people,[],{},'TEST','Synthetic policy')
        draft=self.service.create_draft(plan,self.people,[],{},'TEST','Synthetic policy',True);self.assertEqual((draft.state,draft.family_id,draft.version),('draft',self.t.family_id,2));self.assertEqual(self.library.object_snapshot('TEMPLATE',self.t.id),old);self.assertFalse(generate(draft,self.people,[],{}).valid);self.library.publish(draft);self.assertTrue(generate(draft,self.people,[],{}).valid)
    def test_no_solution_and_unknown_font_never_become_qualified_custom_candidates(self):
        policy=dict(move_mm=0,expand_mm=0,gap_mm=0);plan=self.service.plan(self.t.id,self.people,[],{},policy);self.assertEqual(plan['status'],'NO_SOLUTION_WITHIN_BOUNDS');self.assertIn('本次',plan['issues'][0])
        plan['status']='FEASIBLE_DRAFT'
        with self.assertRaisesRegex(ValueError,'變更'):self.service.create_draft(plan,self.people,[],{},'TEST','Forged state',True)
    def test_existing_qualified_template_prevents_unnecessary_custom_and_stale_input_never_creates_version(self):
        plan=self.plan();changed=deepcopy(self.people);changed[0]['name']=['Different Name']
        with self.assertRaisesRegex(ValueError,'變更'):self.service.create_draft(plan,changed,[],{},'TEST','Synthetic',True)
        other=demo_template();self.library.publish(other)
        with self.assertRaisesRegex(ValueError,'已有'):self.plan()
        self.assertEqual(len(self.library.templates()),2)
    def test_late_audit_failure_rolls_back_custom_geometry_version_and_provenance_together(self):
        plan=self.plan();old=self.library.template_snapshots();event=self.library.event
        def fail(entity,action):
            if action=='training_template_version_provenance_saved':raise ValueError('SYNTHETIC late failure')
            return event(entity,action)
        with patch.object(self.library,'event',side_effect=fail),self.assertRaisesRegex(ValueError,'late failure'):self.service.create_draft(plan,self.people,[],{},'TEST','Synthetic',True)
        self.assertEqual(self.library.template_snapshots(),old)
    def test_actual_gui_custom_preview_cancel_then_explicit_new_draft_does_not_publish(self):
        window=MainWindow(self.library.root);self.addCleanup(window.deleteLater);self.addCleanup(window.library.close);self.addCleanup(window.font_manager.close);self.addCleanup(window.input_timer.stop);window.people.setRowCount(1)
        for col,value in enumerate(('Alex Example','Designer','123','a@example.test','','','','')):window.people.setItem(0,col,QTableWidgetItem(value))
        d=CustomLayoutDialog(window);self.addCleanup(d.deleteLater);d.limits['expand_mm'].setValue(40);d.reason.setText('SYNTHETIC bounded design');d.preview()
        for _ in range(500):
            APP.processEvents();QTest.qWait(10)
            if not d.running:break
        self.assertFalse(d.running);self.assertEqual(d.plan['status'],'FEASIBLE_DRAFT');d.approve.setChecked(True)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.No):d.save()
        self.assertIsNone(d.created)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):d.save()
        self.assertIsNotNone(d.created);self.assertEqual(d.created.state,'draft');self.assertEqual(len(window.library.templates(True)),1)

    def test_missing_font_is_unknown_and_publication_does_not_silently_fallback(self):
        bad=demo_template();bad.slots[0].font='SYNTHETIC ABSENT FONT';self.library.save_template(bad)
        with self.assertRaisesRegex(ValueError,'字型未安裝'):self.library.publish(bad)
        with patch('template_ai.layout.QFontDatabase.families',return_value=[]):plan=self.plan()
        self.assertEqual(plan['status'],'UNVERIFIED');self.assertTrue(plan['issues']);self.assertEqual(len(self.library.templates(True)),1)

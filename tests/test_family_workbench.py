import hashlib
import os
import time
from unittest.mock import patch

from PySide6.QtCore import Qt, QEventLoop, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget, QDialog, QDoubleSpinBox

from family_fixture import FamilyFixture
from template_ai.design_learning_dialog import DesignLearningDialog
from template_ai.family_source_dialog import FamilySourceDialog
from template_ai.input_graph import InputGraph
from template_ai.family_workspace import reference

APP=QApplication.instance() or QApplication([])


class FamilyWorkbenchTests(FamilyFixture):
    def setUp(self):
        super().setUp()
        self.parent=QWidget();self.parent.library=self.library
        self.parent.input_data=lambda:([dict(name='Alex Example',title='Designer',phone='+1 202 555 0100',email='alex@example.test')],[],{})
        self.addCleanup(self.parent.deleteLater)
        self.dialog=DesignLearningDialog(self.parent);self.dialog.show();self.addCleanup(self.dialog.close)
        self.pane=self.dialog.family_workbench;self.dialog.tabs.setCurrentWidget(self.pane);APP.processEvents()

    def test_actual_native_entry_reuses_canvas_and_keeps_customer_controls_unchanged(self):
        from template_ai.object_dialog import ObjectCanvas
        self.assertEqual(self.dialog.tabs.count(),4)
        self.assertIsInstance(self.pane.canvas,ObjectCanvas)
        self.assertTrue(self.pane.ref)
        self.assertGreater(self.pane.roles.topLevelItemCount(),0)
        self.assertEqual(len(self.dialog.tabs.widget(2).findChildren(QDoubleSpinBox)),2)
        self.assertEqual(self.workspace.store.count('FAMILY_DRAFT'),0)
        self.assertEqual(len(self.library.templates()),0)

    def test_graphical_order_save_undo_redo_and_difference_review(self):
        item=self.pane.order.takeItem(self.pane.order.count()-1);self.pane.order.insertItem(0,item)
        QTest.mouseClick(self.pane.buttons['保存預設順序'],Qt.LeftButton)
        self.assertIsNotNone(self.pane.draft,self.dialog.status.text())
        self.assertEqual(self.pane.draft['cursor'],1)
        self.pane.show_differences();self.assertIn('預選',self.pane.report.toPlainText())
        self.pane.history('UNDO');self.assertEqual(self.pane.draft['cursor'],0)
        self.pane.history('REDO');self.assertEqual(self.pane.draft['cursor'],1)
        self.assertEqual(self.workspace.store.get('DESIGN_MODEL',self.model['id']),self.current_model)

    def test_role_tree_and_canvas_selection_are_synchronized(self):
        group=self.pane.roles.topLevelItem(0);item=group.child(group.childCount()-1)
        self.pane.roles.setCurrentItem(item);APP.processEvents()
        selected={i.slot.id for i in self.pane.canvas.scene().selectedItems() if hasattr(i,'slot')}
        self.assertEqual(selected,{item.data(0,Qt.UserRole)})
        first=group.child(0);self.pane.canvas.select_id(first.data(0,Qt.UserRole));APP.processEvents()
        self.assertEqual(self.pane.roles.currentItem(),first)

    def test_rule_candidate_requires_review_and_formal_activation_is_still_blocked(self):
        self.pane.apply_operation(self.reorder())
        with self.assertRaises(ValueError):self.pane.create_candidate()
        self.pane.reviewed.setChecked(True);self.pane.create_candidate()
        self.assertGreaterEqual(self.workspace.store.count('DESIGN_MODEL'),2)
        with self.assertRaises(ValueError):self.pane.activate_formal()
        self.assertEqual(len(self.library.templates()),0)

    def test_saved_workspace_reopens_same_draft_and_query(self):
        self.pane.apply_operation(self.reorder());identity=self.pane.draft['id']
        self.pane.query.setText('email');self.pane.remember();self.dialog.close()
        reopened=DesignLearningDialog(self.parent)
        try:
            self.assertEqual(reopened.family_workbench.draft['id'],identity)
            self.assertEqual(reopened.family_workbench.query.text(),'email')
        finally:reopened.close()

    def test_graphical_batch_preflight_preserves_exact_selection_and_requires_confirmation(self):
        self.pane.apply_operation(self.reorder());self.pane.preview_batch()
        self.assertGreater(self.pane.batch_table.rowCount(),0)
        with self.assertRaises(ValueError):self.pane.batches.submit(self.pane.batch_plan,'Reviewer',False)
        self.assertEqual(self.pane.batch_plan['items'][0]['ref'],self.pane.ref)

    def test_native_physical_filters_saved_workset_and_joint_variant_views(self):
        self.pane.filter_width.setValue(90);self.pane.filter_height.setValue(54)
        self.pane.filter_people.setValue(1);self.pane.filter_fields.setValue(4);self.pane.filter_support.setValue(5)
        self.pane.search();self.assertGreater(self.pane.result['total'],0)
        view=self.workspace.save_view('Physical workset',self.pane.query_value(),'Reviewer')
        self.pane.refresh();self.pane.views.setCurrentIndex(self.pane.views.findData(view['id']))
        self.pane.filter_width.setValue(100);self.pane.open_view()
        self.assertEqual(self.pane.filter_width.value(),90)
        self.pane.show_pattern(self.pane.patterns.item(0))
        self.assertIn('條件欄框',self.pane.scope.text())

    def test_native_family_comparison_uses_verified_source_crops_without_global_templates(self):
        from template_ai.family_compare import FamilyComparisonDialog
        draft=self.apply(self.draft(),self.reorder())
        candidate=self.rules.create_candidate(draft['id'],draft['revision'],'Reviewer',True)
        new_ref=reference(candidate,candidate['artifact']['profile_model']['families'][0])
        dialog=FamilyComparisonDialog(self.parent,[self.ref,new_ref],self.dialog)
        try:
            self.assertEqual(len(dialog.panes),2)
            self.assertTrue(all(p['result']['image'] is not None for p in dialog.panes))
            dialog.overlay.setChecked(True)
            self.assertTrue(all(p['canvas'].readonly for p in dialog.panes))
            self.assertEqual(len(self.library.templates()),0)
        finally:dialog.close()

    def test_worker_start_failure_releases_existing_job_lease(self):
        graph=InputGraph.from_legacy(*self.parent.input_data())
        case=self.pane.scenarios.save(self.ref,'Start failure',graph,90,54,'Reviewer')
        job=self.pane.batches.cases([case['id']],'Reviewer')
        with patch('template_ai.design_learning_dialog.DesignWorker',side_effect=RuntimeError('Owned start failure')):
            with self.assertRaises(RuntimeError):self.pane.start_job(job)
        self.assertIsNone(self.pane.worker)
        self.assertEqual(self.pane.batches.jobs.current(job['id'])['phase'],'FAILED')
        self.assertFalse(self.workspace.store.get('WORKER','design-worker')['active'])

    def test_close_during_worker_waits_for_boundary_and_leaves_resumable_job(self):
        graph=InputGraph.from_legacy(*self.parent.input_data())
        case=self.pane.scenarios.save(self.ref,'Close boundary',graph,90,54,'Reviewer')
        job=self.pane.batches.cases([case['id']],'Reviewer');self.pane.start_job(job)
        loop=QEventLoop();timer=QTimer();timer.setSingleShot(True);timer.timeout.connect(loop.quit)
        self.pane.worker.finished.connect(loop.quit);self.dialog.close();timer.start(60000);loop.exec();APP.processEvents();timer.stop()
        self.assertIsNone(self.pane.worker)
        self.assertIn(self.pane.batches.jobs.current(job['id'])['phase'],('PAUSED','COMPLETE'))
        self.assertFalse(self.dialog.isVisible())

    def test_saved_case_runs_in_worker_and_renders_actual_preview(self):
        graph=InputGraph.from_legacy(*self.parent.input_data())
        class AcceptedInput:
            def __init__(self,*args,**kwargs):self.graph=graph
            def exec(self):return QDialog.Accepted
        with patch('template_ai.input_graph_dialog.InputGraphDialog',AcceptedInput):self.pane.edit_case(True)
        self.assertTrue(self.pane.case_choice.currentData())
        self.pane.run_case()
        loop=QEventLoop();timer=QTimer();timer.setSingleShot(True)
        timer.timeout.connect(loop.quit);self.pane.worker.finished.connect(loop.quit)
        timer.start(60000);loop.exec();APP.processEvents();timer.stop()
        self.assertIsNone(self.pane.worker,self.dialog.status.text())
        self.assertTrue(self.pane.run_choice.currentData())
        self.pane.show_run();self.assertIn('FEASIBLE_PREVIEW',self.pane.case_status.text())
        if os.environ.get('TEMPLATE_AI_FAMILY_CAPTURE'):self.dialog.grab().save(os.environ['TEMPLATE_AI_FAMILY_CAPTURE'])

    def test_z_source_review_never_assumes_identity_and_commit_invalidates_old_model(self):
        entry=self.workspace.sources(self.ref)[0]
        dialog=FamilySourceDialog(self.parent,entry['work_id'],self.dialog)
        try:
            self.assertFalse(dialog.confirmed.isChecked())
            with self.assertRaises(ValueError):dialog.prepare()
            expected=hashlib.sha256(dialog.field_text.toPlainText().encode()).hexdigest()
            index=next(i for i,r in enumerate(dialog.runs) if r['text_sha256']==expected)
            dialog.run_choice.setCurrentIndex(index);dialog.font.setCurrentIndex(1)
            dialog.basis.setText('Authored exact source inspection');dialog.metrics.setChecked(True)
            dialog.label_kind.setCurrentIndex(dialog.label_kind.findData('NO_FIXED_LABEL'))
            dialog.confirmed.setChecked(True);dialog.add_span();dialog.prepare()
            before=self.workspace.store.get('DESIGN_MODEL',self.model['id'])
            dialog.commit()
            self.assertEqual(self.workspace.store.get('DESIGN_MODEL',self.model['id']),before)
            with self.assertRaises(ValueError):self.workspace.resolve(self.ref)
        finally:dialog.close()

"""Real local Qt workflows, with authored evidence kept separate from production."""
from copy import deepcopy

from PySide6.QtCore import Qt, QCoreApplication, QEvent, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton, QDialog

from family_fixture import FamilyFixture
from gui_wait import wait_for_gui
from template_ai.gui import MainWindow
from template_ai.guided_operations import GuidedOperationsDialog
from template_ai.input_graph import InputGraph


APP = QApplication.instance() or QApplication([])


class GuidedOperationsTests(FamilyFixture):
    def setUp(self):
        super().setUp()
        self.main = MainWindow(self.library.root)
        self.main.show()
        self.dialog = GuidedOperationsDialog(self.main)
        self.dialog.show()
        self.dialog.actor.setText('Authored local reviewer')
        self.graph = InputGraph.from_legacy([dict(name='Alex Example', title='Designer', phone='+1 202 555 0100', email='alex@example.test')], [])
        self.addCleanup(self.dispose)

    def dispose(self):
        dialog = self.dialog
        if dialog.worker and dialog.worker.isRunning():
            dialog.worker.cancel.set()
            self.assertTrue(wait_for_gui(lambda: dialog.worker is None or not dialog.worker.isRunning(), 90))
        for child in list(dialog.children_dialogs):
            child.close()
        APP.processEvents()
        dialog.close(); dialog.deleteLater()
        self.main.close(); self.main.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)

    def add_case(self, split='VALIDATION'):
        self.dialog.split.setCurrentIndex(self.dialog.split.findData(split))
        self.assertTrue(self.dialog.sample.currentData())
        self.dialog.set_case_graph(self.graph.data)
        self.dialog.case_basis.setText('Authored independent source/input correspondence')
        self.dialog.add_case()

    def complete_evaluation(self, split='VALIDATION'):
        self.add_case(split)
        self.dialog.eval_approved.setChecked(True)
        job = self.dialog.start_evaluation()
        self.assertTrue(wait_for_gui(lambda: self.dialog.worker is None or not self.dialog.worker.isRunning(), 90), self.dialog.summary.text())
        APP.processEvents()
        current = self.dialog.jobs.current(job['id'])
        self.assertEqual(current['phase'], 'COMPLETE', (current, self.dialog.summary.text()))
        return current

    def test_real_window_empty_guidance_opens_existing_source_and_family_tools(self):
        self.assertEqual(self.dialog.tabs.count(), 4)
        source = self.dialog.open_existing(0)
        self.assertEqual(source.tabs.currentIndex(), 0)
        self.assertIs(source.library, self.main.library)
        source.close(); APP.processEvents()
        family = self.dialog.open_existing(3)
        self.assertIs(family.tabs.currentWidget(), family.family_workbench)
        self.assertTrue(family.family_workbench.roles.topLevelItemCount())
        family.close(); APP.processEvents()
        self.assertEqual(len(self.main.library.templates()), 0)

    def test_pending_cases_persist_but_review_approval_does_not(self):
        self.add_case()
        self.dialog.eval_approved.setChecked(True)
        self.dialog.tabs.setCurrentIndex(1)
        self.dialog.close()
        reopened = GuidedOperationsDialog(self.main)
        try:
            self.assertEqual(reopened.cases, self.dialog.cases)
            self.assertEqual(reopened.case_model, self.model['id'])
            self.assertEqual(reopened.tabs.currentIndex(), 1)
            self.assertFalse(reopened.eval_approved.isChecked())
            self.assertEqual(reopened.case_list.count(), 1)
            self.assertEqual(reopened.actor.text(), 'Authored local reviewer')
        finally:
            reopened.close(); reopened.deleteLater()

    def test_actual_case_input_dialog_keeps_local_size_and_does_not_change_main_input(self):
        from template_ai.input_graph_dialog import InputGraphDialog
        before = deepcopy(self.main.input_data())
        self.dialog.width.setValue(85.); self.dialog.height.setValue(50.)
        seen = []; errors = []
        def enter():
            modal = APP.activeModalWidget()
            try:
                self.assertIsInstance(modal, InputGraphDialog)
                self.assertEqual(modal.window.out_w.value(), 85.)
                self.assertEqual(modal.window.out_h.value(), 50.)
                field = next(row for row in modal.graph.data['fields'] if row['kind'] == 'name')
                modal.field_editors[field['id']].setText('Authored Case Name')
                modal.accept(); seen.append(True)
            except Exception as error:
                errors.append(error)
                if isinstance(modal, QDialog): modal.reject()
        QTimer.singleShot(0, self.dialog, enter)
        self.dialog.edit_case()
        self.assertFalse(errors, errors)
        self.assertEqual(seen, [True])
        self.assertEqual(next(row['value'] for row in self.dialog.case_graph['fields'] if row['kind'] == 'name'), 'Authored Case Name')
        self.assertEqual(self.main.input_data(), before)

    def test_cases_require_real_input_correspondence_and_explicit_review(self):
        with self.assertRaisesRegex(ValueError, '資料'):
            self.dialog.add_case()
        self.dialog.set_case_graph(self.graph.data)
        with self.assertRaisesRegex(ValueError, '依據'):
            self.dialog.add_case()
        self.dialog.case_basis.setText('Authored independent source/input correspondence')
        self.dialog.add_case()
        with self.assertRaisesRegex(ValueError, '逐一核對'):
            self.dialog.start_evaluation()
        self.assertEqual(self.dialog.store.count('DESIGN_JOB'), 0)

    def test_validation_and_holdout_cannot_be_mixed_into_one_guided_task(self):
        self.add_case('VALIDATION')
        self.dialog.split.setCurrentIndex(self.dialog.split.findData('HOLDOUT'))
        self.dialog.set_case_graph(self.graph.data)
        self.dialog.case_basis.setText('Authored source/input correspondence')
        with self.assertRaisesRegex(ValueError, '不同集合'):
            self.dialog.add_case()
        self.assertEqual(len(self.dialog.cases), 1)

    def test_actual_background_task_pauses_and_resumes_saved_cases(self):
        self.add_case()
        self.dialog.eval_approved.setChecked(True)
        job = self.dialog.start_evaluation()
        QTest.mouseClick(self.dialog.pause_button, Qt.LeftButton)
        self.assertTrue(wait_for_gui(lambda: self.dialog.worker is None or not self.dialog.worker.isRunning(), 90))
        APP.processEvents()
        self.assertEqual(self.dialog.jobs.current(job['id'])['phase'], 'PAUSED')
        self.assertEqual(self.dialog.resume_jobs.currentData(), job['id'])
        self.dialog.resume()
        self.assertTrue(wait_for_gui(lambda: self.dialog.worker is None or not self.dialog.worker.isRunning(), 90))
        APP.processEvents()
        self.assertEqual(self.dialog.jobs.current(job['id'])['phase'], 'COMPLETE')
        self.assertEqual(len(self.dialog.jobs.results(job['id'])), 1)

    def test_actual_validation_worker_preview_style_review_and_capacity_api(self):
        model_before = deepcopy(self.dialog.store.get('DESIGN_MODEL', self.model['id']))
        job = self.complete_evaluation()
        self.assertEqual(self.dialog.capacity_jobs.currentData(), job['id'])
        self.assertEqual(self.dialog.capacity_cases.count(), 1)
        self.assertTrue(self.dialog.capacity_canvas.scene().items())
        self.dialog.style.setCurrentIndex(self.dialog.style.findData(True))
        self.dialog.style_basis.setText('Authored reviewer inspected actual rendered text and structure')
        reviewed = self.dialog.review_style()
        self.assertTrue(reviewed['qualified_style'])
        self.assertIn('已保存', self.dialog.capacity_result.text())
        self.dialog.capacity_approved.setChecked(True)
        calibrated = self.dialog.calibrate()
        self.assertEqual(calibrated['scope'], 'LOCAL_CALIBRATION_NOT_PRODUCTION_QUALIFICATION')
        self.assertEqual(calibrated['artifact']['maximum_validated_field_count'], None)
        self.assertTrue(all(row['status'] == 'INSUFFICIENT_OR_FAILED' for row in calibrated['artifact']['cells']))
        self.assertEqual(self.dialog.store.get('DESIGN_MODEL', self.model['id']), model_before)
        self.assertIsNone(self.dialog.store.get('DESIGN_ACTIVE', 'local-layout'))

    def test_synthetic_holdout_cannot_be_promoted_even_with_checked_boxes(self):
        job = self.complete_evaluation('HOLDOUT')
        self.assertEqual(self.dialog.qualification_jobs.currentData(), job['id'])
        self.assertIn('不能取得正式資格', self.dialog.qualification_jobs.currentText())
        self.assertTrue(self.dialog.learned_canvas.scene().items())
        self.dialog.real_authorized.setChecked(True)
        self.dialog.lineage_reviewed.setChecked(True)
        self.dialog.corpus_basis.setText('Authored test deliberately attempts promotion')
        with self.assertRaisesRegex(ValueError, 'synthetic'):
            self.dialog.review_corpus()
        self.assertEqual(self.dialog.store.count('DESIGN_CORPUS_REVIEW'), 0)
        self.assertEqual(self.dialog.store.count('DESIGN_QUALIFICATION'), 0)
        with self.assertRaises(ValueError):
            self.dialog.activate_qualified()

    def test_error_is_visible_and_core_state_is_retained(self):
        before = deepcopy(self.dialog.store.get('DESIGN_MODEL', self.model['id']))
        self.dialog.tabs.setCurrentIndex(3)
        # Actual click reaches the existing service guard through the UI helper.
        button = next(item for item in self.dialog.findChildren(QPushButton) if item.text() == '檢查並保存資格')
        QTest.mouseClick(button, Qt.LeftButton)
        self.assertTrue(self.dialog.summary.text())
        self.assertTrue(self.dialog.details.toPlainText())
        self.assertEqual(self.dialog.store.get('DESIGN_MODEL', self.model['id']), before)
        self.assertEqual(self.dialog.store.count('DESIGN_QUALIFICATION'), 0)

    def test_handled_core_failure_is_in_safe_manual_report_without_raw_message(self):
        from template_ai.offline_support import read_support_bundle
        self.dialog.attempt(self.dialog.activate_qualified)
        report = read_support_bundle(self.main.offline_support.journal.bundle())
        failed = [row for row in report['events'] if row['code'] == 'ACTION_FAILED']
        self.assertTrue(failed)
        self.assertEqual(failed[-1]['missing'], 'QUALIFICATION')
        self.assertEqual(failed[-1]['error'], 'VALUE')
        self.assertNotIn('請先選擇已有正式資格', str(report))
        self.assertEqual(self.dialog.store.count('DESIGN_QUALIFICATION'), 0)

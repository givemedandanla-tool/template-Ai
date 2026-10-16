import unittest
from unittest.mock import patch
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMessageBox
import test_quality_jobs as fixtures
import test_quality_dispatch as gui_fixture
from template_ai.quality_jobs import run_evaluation
from template_ai.quality_panel import QualityPanel,QualityCaseDialog
from template_ai.quality_setup import QualitySetupDialog
from template_ai.quality_diagnostics import QualityDiagnostics
from template_ai.quality_command import run_command
from template_ai.quality_protocol import QualityProtocols

APP=QApplication.instance() or QApplication([])


class QualityPanelTests(unittest.TestCase):
    setUp=fixtures.QualityJobTests.setUp
    build=fixtures.QualityJobTests.build
    window=gui_fixture.QualityDispatchTests.window

    def completed(self):
        for job in self.build().values():
            claimed=self.service.claim(job['id'],job['revision'],True);run_evaluation(self.library.root,job['id'],claimed['owner_token'])

    def wait(self,panel):
        for _ in range(600):
            APP.processEvents()
            if not panel.loading:return
            QTest.qWait(20)
        self.fail('Actual bounded quality command did not finish within12s')

    def panel(self):
        window=self.window();panel=QualityPanel(window);self.addCleanup(panel.deleteLater);panel.actor.setText('Synthetic reviewer');panel.reason.setText('Investigate fixed source test');panel.show();return panel

    def test_native_setup_is_lazy_and_never_prefills_production_thresholds_or_manual_truth(self):
        panel=self.panel();self.assertFalse(panel.active);self.assertEqual(panel.protocols.count(),0)
        dialog=QualitySetupDialog(panel);self.addCleanup(dialog.deleteLater)
        self.assertTrue(all(not box.isChecked() for box in dialog.truth.values()))
        self.assertEqual(dialog.confidence.text(),'');self.assertEqual(dialog.iou.text(),'')
        self.assertEqual(dialog.thresholds.item(0,1).text(),'')
        self.assertEqual(self.store.count('QUALITY_POLICY'),0)

    def test_actual_background_directory_and_side_stats_do_not_reveal_gold_answers(self):
        self.completed();panel=self.panel();panel.activate();self.wait(panel)
        self.assertEqual(panel.protocols.currentData(),self.protocol['id'])
        panel.load_status();self.wait(panel)
        self.assertGreater(panel.stats.rowCount(),0)
        self.assertIn('EVIDENCE_INSUFFICIENT',panel.status.text())
        self.assertEqual(self.store.count('HOLDOUT_EXPOSED'),0)

    def test_actual_answer_exposure_paged_diagnosis_and_readonly_source_canvas(self):
        self.completed();panel=self.panel();panel.activate();self.wait(panel)
        with self.assertRaises(ValueError):QualityDiagnostics(self.library).page(self.protocol['id'],'BASELINE')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):panel.expose()
        self.wait(panel);self.assertIsNotNone(self.store.get('HOLDOUT_EXPOSED',self.protocol['scope']['dataset_id']))
        self.assertGreater(panel.table.rowCount(),0);self.assertLessEqual(panel.table.rowCount(),50)
        row=panel.rows[0];detail=run_command(self.library.root,'DIAGNOSTIC_DETAIL',dict(protocol_id=self.protocol['id'],side='BASELINE',row=row))
        self.assertLessEqual(len(detail['golds']),1);self.assertLessEqual(len(detail['predictions']),1)
        dialog=QualityCaseDialog(self.library,detail,panel);self.addCleanup(dialog.deleteLater);dialog.show();APP.processEvents()
        self.assertEqual(len(dialog.canvases),2);self.assertTrue(all(canvas.readonly for canvas in dialog.canvases))
        self.assertTrue(all(canvas.scene().items() for canvas in dialog.canvases))

    def test_actual_global_case_query_and_facets_preserve_source_denominator(self):
        self.completed();QualityProtocols(self.library).expose(self.protocol['id'],'Reviewer','Diagnostic branch',True)
        service=QualityDiagnostics(self.library);all_rows=service.page(self.protocol['id'],'BASELINE',limit=2)
        self.assertLessEqual(len(all_rows['rows']),2);self.assertEqual(all_rows['whole_source_units'],1)
        empty=service.page(self.protocol['id'],'BASELINE',facets=dict(role='TRAIN'))
        self.assertEqual(empty['rows'],[]);self.assertEqual(empty['whole_source_units'],1)
        gold=service.page(self.protocol['id'],'BASELINE',facets=dict(role='HOLDOUT'))
        self.assertEqual(gold['total'],all_rows['total'])
        by_filename=service.page(self.protocol['id'],'BASELINE',query='example.svg')
        by_version=service.page(self.protocol['id'],'BASELINE',query='Actual baseline')
        self.assertEqual(by_filename['total'],all_rows['total']);self.assertEqual(by_version['total'],all_rows['total'])

    def test_predicted_work_tamper_is_rejected_even_with_unchanged_item_receipt(self):
        self.completed();QualityProtocols(self.library).expose(self.protocol['id'],'Reviewer','Inspect source prediction',True)
        service=QualityDiagnostics(self.library);row=service.page(self.protocol['id'],'BASELINE')['rows'][0]
        item=self.store.get('QUALITY_EVAL_ITEM',row['item_id']);prediction=self.store.get('QUALITY_PREDICTED_WORK',item['prediction_ids'][0])
        prediction['prediction']['work_width']=1
        with self.store.transaction():self.store._write('QUALITY_PREDICTED_WORK',prediction['id'],prediction,prediction['revision'],'synthetic_prediction_corruption')
        with self.assertRaisesRegex(ValueError,'指紋'):service.detail(self.protocol['id'],'BASELINE',row)

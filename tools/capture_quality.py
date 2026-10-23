"""Actual quality Qt/FIFO/SQLite source evidence; synthetic safety scope only."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]


def capture_quality(folder):
    from PySide6.QtCore import QTimer,QCoreApplication,QEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QMessageBox
    from unittest.mock import patch
    import psutil
    import test_quality_gold_sets as fixtures
    from quality_acceptance_fixture import actual_positive_pair
    from test_quality_ocr import QualityOcrTests
    from template_ai.gui import MainWindow
    from template_ai.training_quality_dialog import TrainingQualityDialog
    from template_ai.quality_panel import QualityCaseDialog
    from template_ai.quality_setup import QualitySetupDialog
    from template_ai.quality_reports import QualityReports
    from template_ai.quality_diagnostics import QualityDiagnostics
    from template_ai.quality_pipeline import QualityPipelines
    from template_ai.quality_jobs import EvaluationJobs
    from template_ai.quality_protocol import QualityProtocols
    from template_ai.runtime_panel import RuntimePanel
    app=QApplication.instance() or QApplication([]);case=fixtures.QualityGoldSetTests('runTest');case.setUp();folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    window=dialog=viewer=runtime_panel=setup=None;panel=None;ticks=[];rss=[];timer=QTimer();timer.setInterval(20);process=psutil.Process()
    def pulse():ticks.append(time.monotonic());rss.append(process.memory_info().rss)
    timer.timeout.connect(pulse)
    def wait(predicate,timeout=45):
        started=time.monotonic()
        while not predicate():
            app.processEvents();QTest.qWait(10)
            if time.monotonic()-started>timeout:raise RuntimeError('Actual quality capture timeout: '+(panel.status.text() if panel else 'initialization'))
    def settled():wait(lambda:not panel.loading)
    def shot(widget,name):
        widget.show();app.processEvents()
        if not widget.grab().save(str(folder/name)):raise RuntimeError('Actual quality Qt screenshot failed')
    try:
        fixture=actual_positive_pair(case,execute=False)
        source=QualityOcrTests.image_source(case);pipelines=QualityPipelines(case.library)
        ocr=pipelines.freeze('Actual OCR capture component',None,'SYNTHETIC_CAPTURE',True,ocr_config=dict(languages=['eng'],psm=6));probe=pipelines.predict_source(ocr['id'],source['id'])
        if not probe['capabilities']['ocr_executed']:raise RuntimeError('OCR was not actually executed')
        window=MainWindow(case.library.root);window.show();dialog=TrainingQualityDialog(window);dialog.resize(1500,1050);dialog.setWindowTitle('合成軟體自驗：品質與狀態轉移，非真實模型準確率')
        panel=dialog.quality_panel;panel.actor.setText('SYNTHETIC_CAPTURE');panel.reason.setText('Authored synthetic local software state-transition evidence only');dialog.tabs.setCurrentWidget(dialog.quality_scroll);dialog.show();settled();timer.start()
        setup=QualitySetupDialog(panel);setup.tabs.setCurrentIndex(1)
        if setup.confidence.text() or setup.iou.text() or any(box.isChecked() for box in setup.truth.values()):raise RuntimeError('Quality thresholds or manual truth silently defaulted')
        shot(setup,'remaining28-quality-explicit-empty-policy.png');setup.close();setup.deleteLater();setup=None
        window.runtime.set_paused(True);requests=[window.execution_queue.submit('EVAL_JOB',fixture['jobs'][side],'SYNTHETIC_CAPTURE') for side in ('BASELINE','CANDIDATE')]
        runtime_panel=RuntimePanel(window);runtime_panel.resize(1320,900);runtime_panel.refresh();shot(runtime_panel,'remaining28-quality-paused-fifo.png')
        if any(window.execution_queue.queue.get(request['id'])['state']!='WAITING' for request in requests):raise RuntimeError('Paused queue executed unexpectedly')
        runtime_panel.close();window.runtime.set_paused(False);started=time.monotonic();window.execution_queue.dispatch(requested=True)
        wait(lambda:all(window.execution_queue.queue.get(request['id'])['state']=='DONE' for request in requests),60);queue_seconds=time.monotonic()-started
        panel.protocols.setCurrentIndex(panel.protocols.findData(fixture['protocol']['id']));panel.load_status();settled();shot(dialog,'remaining28-quality-nine-domain-counts.png')
        for side in ('BASELINE','CANDIDATE'):
            job=EvaluationJobs(case.library).get(fixture['jobs'][side]['id']);result=case.store.get('QUALITY_EVAL_RESULT',job['result_id'])
            if not result['quality_pass']:raise RuntimeError('Authored acceptance fixture did not satisfy its explicit lenient synthetic policy')
        panel.compare();settled()
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):panel.confirm_preview()
        settled()
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):panel.decide()
        settled();decision=panel.decision_id.text()
        if not QualityReports(case.library).recommendation_status(decision)['quality_verified_recommendation_allowed']:raise RuntimeError('Explicit fixture acceptance not persisted')
        shot(dialog,'remaining28-quality-explicit-decision.png')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):panel.withdraw()
        settled()
        if QualityReports(case.library).recommendation_status(decision)['quality_verified_recommendation_allowed']:raise RuntimeError('Withdrawn decision still trusted')
        shot(dialog,'remaining28-quality-withdrawn-no-fallback.png')
        QualityProtocols(case.library).expose(fixture['protocol']['id'],'SYNTHETIC_CAPTURE','Local source diagnosis; no longer fresh holdout',True)
        panel.source_units();settled()
        if len(panel.rows)!=2:raise RuntimeError('Correct zero-error source samples hidden from source denominator')
        shot(dialog,'remaining28-quality-all-source-samples.png')
        detail=QualityDiagnostics(case.library).detail(fixture['protocol']['id'],'BASELINE',panel.rows[0]);viewer=QualityCaseDialog(case.library,detail,panel);shot(viewer,'remaining28-quality-gold-vs-actual-ai.png');viewer.close();viewer.deleteLater();viewer=None
        panel.load_status();settled()
        if '已失效' not in panel.status.text():raise RuntimeError('Historical PASS presented as currently valid after answer exposure')
        shot(dialog,'remaining28-quality-historical-pass-invalid.png')
        gaps=[b-a for a,b in zip(ticks,ticks[1:])]
        report=dict(status='PASS',parent='UI-053',kind='ACTUAL_QT_FIFO_CHILD_SQLITE_AUTHORED_SYNTHETIC_SELF_CHECK',declared_files=2,related_groups=1,domains=9,actual_children=2,source_units=4,actual_fifo_seconds=queue_seconds,actual_ocr_probe=True,ocr_before_gui_measurement=True,ocr_runtime=ocr['manifest']['ocr']['runtime'],ocr_model_hashes={m['language']:m['sha256'] for m in ocr['manifest']['ocr']['models']},explicit_accept_withdraw=True,zero_error_sources_visible=True,exposed_historical_pass_marked_invalid=True,all_source_count=2,one_work_each_canvas=True,manual_truth_not_defaulted=True,production_thresholds_not_defaulted=True,fixture_policy_intentionally_lenient_not_accuracy_calibration=True,gui_ticks=len(ticks),max_gui_tick_gap_ms=max(gaps,default=0)*1000,peak_parent_rss_bytes=max(rss,default=process.memory_info().rss),host=window.runtime.state(),reference_windows_16gb_gpu_verified=False,native_illustrator_certified=False,independent_review=False)
        (folder/'remaining28-quality-capture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report
    finally:
        timer.stop()
        for widget in (viewer,setup,runtime_panel,dialog):
            if widget is not None:widget.close();widget.deleteLater()
        if window is not None:window.close();window.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents();case.doCleanups()


if __name__=='__main__':print(json.dumps(capture_quality(Path(sys.argv[1])),ensure_ascii=False))

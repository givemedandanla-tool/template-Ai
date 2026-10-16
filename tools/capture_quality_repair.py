"""Actual seven-page Qt capture with real ordered source inference and deployment."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]


def capture_repair(folder):
    from PySide6.QtCore import QTimer,QCoreApplication,QEvent
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from types import SimpleNamespace
    import psutil
    from test_quality_repair_full_chain import QualityRepairFullChainTests
    from quality_repair_acceptance_fixture import actual_chain
    from test_semantic_learning import SemanticLearningTests
    from runtime_fixture import controlled_resources
    from template_ai.gui import MainWindow
    from template_ai.training_quality_dialog import TrainingQualityDialog
    from template_ai.quality_repair_dialog import QualityRepairDialog
    from template_ai.quality_repairs import QualityRepairs
    from template_ai.semantic_learning import SemanticLearning
    from template_ai.automatic_training import AutomaticTraining
    from template_ai.quality_repair_training import create
    from template_ai.quality_pipeline import QualityPipelines
    from template_ai.quality_repair_gates import QualityRepairGates
    from template_ai.quality_reports import QualityReports
    app=QApplication.instance() or QApplication([]);case=QualityRepairFullChainTests('runTest');case.setUp();folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    errors=[];old_hook=sys.excepthook;sys.excepthook=lambda kind,value,tb:errors.append(str(value))
    window=center=dialog=None;timer=QTimer();timer.setInterval(20);ticks=[];memory=[];process=psutil.Process();screens=[];started=time.monotonic()
    timer.timeout.connect(lambda:(ticks.append(time.monotonic()),memory.append(process.memory_info().rss)))
    def wait(predicate,seconds=60):
        deadline=time.monotonic()+seconds
        while not predicate():
            app.processEvents();QTest.qWait(10)
            if time.monotonic()>deadline:raise RuntimeError('Repair capture timeout: '+(dialog.status.text() if dialog else 'preparation'))
    def settled():wait(lambda:not center.quality_panel.loading and not window.busy)
    def shot(index,label,issue_id):
        dialog.tabs.setCurrentIndex(index);dialog.show();app.processEvents();name=f'remaining28-repair-{index+1:02d}-{label}.png'
        if not dialog.grab().save(str(folder/name)):raise RuntimeError('Actual seven-page Qt screenshot failed')
        screens.append(dict(file=name,tab=dialog.tabs.tabText(index),issue_id=issue_id,actual_native_widgets=True))
    try:
        chain=actual_chain(case);preparation_seconds=time.monotonic()-started
        # A second explicitly labelled semantic issue supplies real incremental
        # progress. It is never represented as the accepted parser repair.
        semantic=SemanticLearning(case.library);context=SimpleNamespace(root=case.root,library=case.library,service=semantic)
        train=SemanticLearningTests.work(context,'capture-semantic-train',[('title','資深雲端工程師'),('title','資深後端工程師'),('address','台中市西區公益路10號'),('address','台中市西區中正路20號')])
        validation=SemanticLearningTests.work(context,'capture-semantic-validation',[('title','資深前端工程師'),('address','台中市西區民生路30號')])
        repairs=QualityRepairs(case.library);training_issue=repairs.create_source_issue(repairs.plan_source_issue(train['id'],'SOURCE_FACTS',train['id'],'獨立示例：明列來源的局部語意訓練進度，尚未品質驗收'),'Synthetic author','Only explicit selected local examples; unrelated to accepted parser deployment',True)
        training_review=repairs.confirm_root(repairs.root_plan(training_issue['id'],'FIELD_OWNER_SEMANTICS','局部語意候選，只核對已選TRAIN／VALIDATION','Actual authored source facts and no holdout admission',True,True),'Synthetic author',True)
        training_plan=semantic.plan({train['id']:'TRAIN',validation['id']:'VALIDATION'});job=create(AutomaticTraining(case.library),training_review['id'],training_plan,'Synthetic author',True)
        window=MainWindow(case.library.root);controlled_resources(window);center=TrainingQualityDialog(window);panel=center.quality_panel;dialog=QualityRepairDialog(panel);dialog.actor.setText('Synthetic author');dialog.reason.setText('合法作者合成安全流程；不是生產準確率／原生Illustrator／實機效能證明')
        timer.start();original_issue=case.store.get('QUALITY_REPAIR_ISSUE',case.candidate['plan']['issue_id']);dialog.issue=original_issue;dialog.source_work.setText(original_issue['evidence']['work_id']);dialog.description.setText(original_issue['reason']);dialog.select_record(dialog.issues,original_issue['id'],original_issue['reason']);dialog.select_record(dialog.review,case.review['id'],case.review['plan']['hypothesis']);dialog.select_record(dialog.candidate,case.candidate['id'],'已通過順序驗證的實際解析器候選')
        dialog.status.setText('實際原問題：條件式故障解析器漏掉來源作品；原錯誤與不可變修復憑證均保留。');shot(0,'issues',original_issue['id'])
        dialog.layer.setCurrentIndex(dialog.layer.findData('WORK_SEGMENTATION'));dialog.hypothesis.setText(case.review['plan']['hypothesis']);dialog.evidence.setText(case.review['plan']['evidence']);dialog.original_reviewed.setChecked(True);dialog.truth_reviewed.setChecked(True);dialog.load_impact();settled();shot(1,'root-impact',original_issue['id'])
        dialog.issue=training_issue;dialog.select_record(dialog.issues,training_issue['id'],training_issue['reason']);dialog.select_record(dialog.review,training_review['id'],training_review['plan']['hypothesis']);dialog.roles=dict(training_plan['work_roles']);dialog.details.setPlainText('獨立的語意訓練示例：只使用明列且人工確認的TRAIN與VALIDATION；不使用原問題HOLDOUT答案。');dialog.work_page(0);settled();dialog.status.setText('此頁是另行明列的語意訓練示例；保留集停用，沒有將原問題答案寫回訓練。');shot(2,'selected-training',training_issue['id'])
        dialog.select_record(dialog.job,job['id'],'實際局部語意訓練');dialog.consent.setChecked(True);dialog.enqueue_train();wait(lambda:bool(case.store.get('AUTO_JOB',job['id']).get('candidate_id')));settled();dialog.job_page(0);shot(3,'actual-progress',training_issue['id'])
        done=case.store.get('AUTO_JOB',job['id']);model=case.store.get('SEMANTIC_MODEL',done['model_id']);case.assertEqual(model['state'],'PENDING');case.assertIsNone(case.store.get('SEMANTIC_ACTIVE','local-text'))
        dialog.issue=original_issue;dialog.select_record(dialog.issues,original_issue['id'],original_issue['reason']);dialog.select_record(dialog.review,case.review['id'],case.review['plan']['hypothesis']);dialog.select_record(dialog.protocol,chain['final']['plan']['protocol_id'],'新獨立保留集的實際固定雙側試驗');dialog.select_record(dialog.report,chain['final']['plan']['report_id'],'新獨立保留集固定差異');dialog.stage.setCurrentIndex(2)
        report=case.store.get('QUALITY_PAIR_REPORT',chain['final']['plan']['report_id']);dialog.details.setPlainText(dialog.summary(report['plan']));dialog.status.setText('原問題、關鍵對照、新保留集分開有憑證；品質比較只顯示統計，不揭露保留集逐案答案。');shot(4,'actual-quality-difference',original_issue['id'])
        dialog.select_record(dialog.final_gate,chain['final']['id'],'完整三階段PASS');dialog.select_record(dialog.decision,chain['decision']['id'],'具名品質接受，原始證據仍有效');dialog.select_record(dialog.impact_review,chain['impact']['id'],'已知歷史影響核對');dialog.release_status();settled();case.assertTrue(dialog.last_release_status['pin']);shot(5,'adopted-version',original_issue['id'])
        QualityReports(case.library).withdraw(chain['decision']['id'],'Synthetic author','Capture actual withdrawn proof; no safe old fallback assumed',True)
        dialog.select_record(dialog.old_event,chain['installed']['event']['id'],'曾採用版本：品質證據已明確撤回');dialog.rollback_plan();settled();case.assertIn('撤回',dialog.status.text());case.assertIsNone(dialog.pending);case.assertEqual(case.store.get('QUALITY_PIPELINE_ACTIVE','automatic-source')['event_id'],chain['installed']['event']['id']);shot(6,'blocked-recovery',original_issue['id'])
        if errors:raise RuntimeError('Unhandled native capture exceptions: '+str(errors))
        gaps=[(right-left)*1000 for left,right in zip(ticks,ticks[1:])]
        result=dict(status='PASS',parent='UI-054',kind='ACTUAL_NATIVE_QT_SAME_SQLITE_ORDERED_SOURCE_ENGINE_AND_SHARED_FIFO',screens=screens,
                    actual_ordered_parser_root_controls_fresh_holdout_deployment=True,actual_semantic_child_job=True,semantic_model_state=model['state'],semantic_activation=False,
                    explicit_withdrawal_blocks_recovery=True,original_and_published_data_modified=False,
                    preparation_seconds=preparation_seconds,gui_ticks=len(ticks),max_gui_tick_gap_ms=max(gaps,default=0),peak_parent_rss_bytes=max(memory,default=process.memory_info().rss),
                    admission='CONTROLLED_WORKFLOW_TEST_NOT_RESOURCE_CALIBRATION',gui_measurement_scope='NATIVE_EVENT_LOOP_AND_USER_OPERATIONS_EXCLUDES_PREPARATORY_CLI_AND_DUPLICATE_BACKEND_ASSERTIONS',fixture_policy='EXPLICIT_INTENTIONALLY_LENIENT_AUTHORED_SYNTHETIC_SOFTWARE_SAFETY_ONLY',
                    native_illustrator_certified=False,reference_windows_gpu_hardware_verified=False,production_accuracy_calibrated=False,independent_review=False,runtime_errors=errors)
        (folder/'remaining28-repair-capture.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
    finally:
        timer.stop();sys.excepthook=old_hook
        if window is not None:
            window.execution_queue.cancel_event.set();window.pool.waitForDone(5000);app.processEvents()
        for widget in (dialog,center):
            if widget is not None:widget.close();widget.deleteLater()
        if window is not None:window.font_manager.close();window.close();window.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents();case.doCleanups()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--artifacts-dir',required=True,type=Path);args=parser.parse_args()
    print(json.dumps(capture_repair(args.artifacts_dir),ensure_ascii=False))

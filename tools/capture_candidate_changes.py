"""Native synthetic UI059 edits/queued validation/comparison; no business writes."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]


def capture(folder):
    import threading,psutil
    from unittest.mock import patch
    from PySide6.QtCore import Qt,QTimer,QCoreApplication,QEvent
    from PySide6.QtWidgets import QApplication,QMessageBox
    from PySide6.QtTest import QTest
    from test_candidate_edit_dispatch import CandidateEditDispatchTests
    from template_ai.candidate_edit import CandidateEditDialog
    from template_ai.candidate_edit_dispatch import dispatcher,calculate_edit
    from gui_wait import wait_for_gui,wait_candidate_edits
    case=CandidateEditDispatchTests('runTest');case.setUp();w=case.w;folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);app=QApplication.instance();errors=[];old_hook=sys.excepthook;sys.excepthook=lambda typ,error,tb:errors.append(str(error));screens=[];ticks=[];rss=[];process=psutil.Process();timer=QTimer();timer.setInterval(20);timer.timeout.connect(lambda:(ticks.append(time.monotonic()),rss.append(process.memory_info().rss)));timer.start();release=threading.Event();dialog=None
    def shot(widget,name):
        app.processEvents();path=folder/('candidate-changes-'+name+'.png');assert widget.grab().save(str(path));screens.append(path.name)
    def approve(button):
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(button,Qt.LeftButton)
    try:
        w.resize(1360,940);w.show();w.tabs.setCurrentIndex(2);original=case.ready().template.to_dict();w.foreground_layout_session.hide();official=w.library.object_snapshot('TEMPLATE',original['id'])['payload'];inputs=w.input_data();dialog=CandidateEditDialog(w);dialog.show();dialog.current_canvas.select_id(w.candidates[0].template.slots[0].id);dialog.dx.setValue(1);QTest.mouseClick(dialog.preview_button,Qt.LeftButton);assert '核心元素' in dialog.details.toPlainText();shot(dialog,'01-core-difference-before-apply')
        started=threading.Event()
        def work(envelope,library):
            started.set()
            if not release.wait(10):raise AssertionError('Native capture did not release owned worker')
            return calculate_edit(envelope,library)
        with patch('template_ai.candidate_edit_dispatch.calculate_edit',side_effect=work):
            approve(dialog.apply_button);assert wait_for_gui(started.is_set,2);assert not w.candidates[0].formal_eligible;assert w.candidates[0].template.slots[0].rect.x==original['slots'][0]['rect']['x']+1;shot(dialog,'02-manual-kept-worker-pending');release.set();wait_candidate_edits(w)
        manual=w.candidates[0].template.to_dict();QTest.mouseClick(dialog.original_button,Qt.LeftButton);QTest.mouseClick(dialog.compare_button,Qt.LeftButton);wait_candidate_edits(w);assert dialog.adopt_button.isEnabled();assert w.candidates[0].template.to_dict()==manual;assert not dialog.compared[1].formal_eligible;shot(dialog,'03-verified-separate-nonformal-comparison');QTest.mouseClick(dialog.keep_button,Qt.LeftButton);assert w.candidates[0].template.to_dict()==manual;shot(dialog,'04-keep-manual-explicitly')
        w.people.item(0,2).setText('1234567');w.refresh_input_problems();w.candidate_scroll.ensureWidgetVisible(w.dependency_notice);app.processEvents();assert w.dependency_notice.visibleRegion().boundingRect().height()>=min(90,w.dependency_notice.height());assert 'phone' in w.dependency_notice.text();shot(w,'05-phone-dependency-stale-not-exportable');w.recheck_affected_candidates();wait_candidate_edits(w);assert w.candidates[0].template.to_dict()==manual
        phone='1234567890'*20;w.people.item(0,2).setText(phone);w.recheck_affected_candidates();wait_candidate_edits(w);assert w.candidates[0].risk['state']=='HARD_BLOCKED';assert w.candidates[0].template.to_dict()==manual;QTest.mouseClick(dialog.original_button,Qt.LeftButton);QTest.mouseClick(dialog.compare_button,Qt.LeftButton);wait_candidate_edits(w);assert not dialog.adopt_button.isEnabled();shot(dialog,'06-long-phone-conflict-no-auto-shrink');QTest.mouseClick(dialog.keep_button,Qt.LeftButton);assert not w.candidates[0].formal_eligible
        w.people.item(0,2).setText(inputs[0][0]['phone'][0]);w.recheck_affected_candidates();wait_candidate_edits(w);QTest.mouseClick(dialog.undo_button,Qt.LeftButton);approve(dialog.apply_button);wait_candidate_edits(w);assert w.candidates[0].template.to_dict()==original;assert w.candidates[0].formal_eligible;shot(dialog,'07-single-delta-undo-current-full-gate')
        dialog.current_canvas.select_id(w.candidates[0].template.slots[0].id);dialog.operation.setCurrentIndex(2);QTest.mouseClick(dialog.preview_button,Qt.LeftButton);approve(dialog.apply_button);wait_candidate_edits(w);assert w.candidates[0].template.slots[0].locked;shot(dialog,'08-explicit-lock-current-candidate-only');assert w.library.object_snapshot('TEMPLATE',original['id'])['payload']==official;assert not errors,errors
        report=dict(status='PASS',screens=screens,qt_uncaught=errors,scope='CONTROLLED_SYNTHETIC_NATIVE_WORKFLOW_NOT_REFERENCE_HARDWARE',peak_rss_bytes=max(rss,default=0),max_gui_timer_gap_ms=max(((b-a)*1000 for a,b in zip(ticks,ticks[1:])),default=0),timer_ticks=len(ticks),single_existing_pool=w.pool.maxThreadCount()==1,manual_geometry_preserved=True,comparison_only_never_formal=True,official_template_unchanged=True,automatic_training=False,paid_services=False)
        (folder/'candidate-changes-capture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report
    finally:
        release.set();timer.stop();w.pool.waitForDone(5000);app.processEvents();sys.excepthook=old_hook
        if dialog:dialog.deleteLater()
        case.doCleanups();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);args=parser.parse_args();result=capture(args.folder);print(json.dumps({k:v for k,v in result.items() if k!='screens'},ensure_ascii=False))

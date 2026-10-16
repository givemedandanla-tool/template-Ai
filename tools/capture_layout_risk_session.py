"""Actual synthetic native tri-state and single-worker encrypted recovery workflow."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]


def capture(folder):
    import psutil
    from unittest.mock import patch
    from types import SimpleNamespace
    from PySide6.QtCore import QTimer,QCoreApplication,QEvent
    from PySide6.QtWidgets import QApplication,QInputDialog,QMessageBox
    from test_layout_session_extended import LayoutSessionExtendedTests,pump_until
    from template_ai.layout_session import LayoutSessionDialog
    from template_ai.candidate_risk import transient_draft
    from template_ai.layout import generate
    from template_ai.demo import demo_template
    from template_ai.input_graph import InputGraph
    from gui_wait import wait_layout
    case=LayoutSessionExtendedTests('runTest');case.setUp();w=case.w;bad=demo_template();bad.name='Synthetic fixed-font width failure';bad.slots[0].rect.w=.1;w.library.publish(bad)
    from training_fixture import source_work
    source,work=source_work(w.library,case.root,'authored-missing-source.svg');unknown=demo_template();unknown.name='Synthetic source file missing';unknown.source_id=source['id'];unknown.source_work_id=work['id'];unknown.source_work_revision=work['revision'];w.library.publish(unknown);Path(w.library.source(source['id'])['current_path']).unlink()
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);app=QApplication.instance();errors=[];previous=sys.excepthook;sys.excepthook=lambda typ,error,tb:errors.append(str(error));screens=[];ticks=[];rss=[];process=psutil.Process();timer=QTimer();timer.setInterval(20);timer.timeout.connect(lambda:(ticks.append(time.monotonic()),rss.append(process.memory_info().rss)));timer.start();dialogs=[]
    def shot(widget,name):
        app.processEvents();path=folder/('layout-risk-session-'+name+'.png');assert widget.grab().save(str(path));screens.append(path.name)
    try:
        w.resize(1360,940);w.show();w.tabs.setCurrentIndex(2);w.generate();wait_layout(w);w.foreground_layout_session.hide();safe=next(i for i,c in enumerate(w.candidates) if c.formal_eligible);blocked=next(i for i,c in enumerate(w.candidates) if c.risk['state']=='HARD_BLOCKED');w.candidate_list.setCurrentRow(safe);shot(w,'01-safe-current-gates')
        w.candidate_list.setCurrentRow(blocked);assert not w.export_button.isEnabled();shot(w,'02-hard-blocked')
        draft=transient_draft(w.candidates[safe],'Synthetic explicit local style review; no hard-rule bypass');w.candidates.append(draft);w.candidate_list.addItem('Synthetic transient review');w.candidate_list.setCurrentRow(len(w.candidates)-1);assert not w.export_button.isEnabled();assert w.preview_button.isEnabled();shot(w,'03-review-draft-marked')
        uncertain=next(i for i,c in enumerate(w.candidates) if c.template.id==unknown.id);w.candidate_list.setCurrentRow(uncertain);assert w.candidates[uncertain].risk['state']=='EVIDENCE_REQUIRED';shot(w,'04-evidence-required')
        people,companies,logos=w.input_data();w.adopt_input_graph(InputGraph.from_legacy(people,companies,logos).data);d=LayoutSessionDialog(w);dialogs.append(d);d.resize(1320,760);d.show();calls=[];real=generate
        def calculate(*args,**kwargs):result=real(*args,**kwargs);calls.append(args[0].id);return result
        def admission(*args,**kwargs):return SimpleNamespace(allowed=not calls,reasons=('SYNTHETIC_MEMORY_PRESSURE',))
        with patch('template_ai.layout_session.generate',side_effect=calculate),patch.object(w.runtime,'admit',side_effect=admission):
            d.start();pump_until(lambda:len(d.rows)==1 and '資源不足' in d.status.text());assert d.running;assert d.list.count()==3;shot(d,'05-real-resource-wait-pending-scope');d.list.setCurrentRow(0);d.preview_selected();shot(w,'06-partial-preview-only');d.cancel();pump_until(lambda:not d.running)
        assert len(d.rows)==1;shot(d,'07-cancelled-valid-partial')
        with patch.object(QInputDialog,'getText',return_value=('authored-recovery-password',True)):d.save_recovery();pump_until(lambda:not w.busy)
        assert d.recovery.pending();assert b'Alex Example' not in d.recovery.path.read_bytes();shot(d,'08-encrypted-safe-save');reopened=LayoutSessionDialog(w);dialogs.append(reopened);reopened.resize(1320,760);reopened.show();assert reopened.rows==[];shot(reopened,'09-explicit-restore-prompt')
        with patch.object(QInputDialog,'getText',return_value=('authored-recovery-password',True)),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):reopened.restore_recovery();pump_until(lambda:not w.busy)
        assert reopened.rows and reopened.report_state=='CANCELLED';assert reopened.rows[0]['candidate'] is not None;shot(reopened,'10-restored-current-not-auto-adopted')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):reopened.clear_recovery()
        assert not reopened.recovery.pending();shot(reopened,'11-explicit-local-clear');assert not errors,errors
        report=dict(status='PASS',screens=screens,qt_uncaught=errors,scope='CONTROLLED_SYNTHETIC_NATIVE_WORKFLOW_NOT_REFERENCE_HARDWARE',peak_rss_bytes=max(rss,default=0),max_gui_timer_gap_ms=max(((b-a)*1000 for a,b in zip(ticks,ticks[1:])),default=0),timer_ticks=len(ticks),source_preparation_excluded=True,actual_source='Authored synthetic templates/input; no private Illustrator or production customer data',automatic_training=False,paid_services=False)
        (folder/'layout-risk-session-capture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report
    finally:
        timer.stop()
        for d in dialogs:
            if d.running:d.cancel()
        w.pool.waitForDone(5000);app.processEvents();sys.excepthook=previous
        for d in dialogs:d.deleteLater()
        case.doCleanups();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);args=parser.parse_args();result=capture(args.folder);print(json.dumps({k:v for k,v in result.items() if k!='screens'},ensure_ascii=False))

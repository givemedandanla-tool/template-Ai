"""Native current-result recommendation/comparison/problem location, synthetic only."""
import argparse,json,sys,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]


def capture(folder):
    from unittest.mock import patch
    from PySide6.QtCore import Qt,QTimer,QCoreApplication,QEvent
    from PySide6.QtWidgets import QApplication
    from test_candidate_results import CandidateResultsTests
    from template_ai.candidate_results import ResultComparisonDialog,problem_rows,locate_problem,recommendation
    from template_ai.input_graph import InputGraph
    from template_ai.input_graph_dialog import InputGraphDialog
    from gui_wait import wait_layout
    case=CandidateResultsTests('runTest');case.setUp();w=case.w;folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);app=QApplication.instance();errors=[];previous=sys.excepthook;sys.excepthook=lambda typ,error,tb:errors.append(str(error));screens=[];dialogs=[]
    def shot(widget,name):
        app.processEvents()
        if widget is w:w.output_canvas.fit();app.processEvents()
        path=folder/('candidate-results-'+name+'.png');assert widget.grab().save(str(path));screens.append(path.name)
    try:
        w.resize(1700,1060);w.show();w.tabs.setCurrentIndex(2);case.ready();w.foreground_layout_session.hide();assert recommendation(w)['scope_complete'];w.candidate_scroll.ensureWidgetVisible(w.result_recommendation);shot(w,'01-current-qualified-finite-recommendation');case.another(width=.1);w.generate();wait_layout(w);w.foreground_layout_session.hide();before=[c.template.to_dict() for c in w.candidates];assert recommendation(w)['index']==0
        comparison=ResultComparisonDialog(w);dialogs.append(comparison);comparison.show();assert all(not c.formal_eligible for c in comparison.snapshots);assert any(comparison.gates.item(i,1).text()=='PASS' and comparison.gates.item(i,2).text()=='FAIL' for i in range(comparison.gates.rowCount()));shot(comparison,'02-nonformal-gate-differences');assert comparison.select_side(1);assert not w.export_button.isEnabled();comparison.hide();w.candidate_scroll.ensureWidgetVisible(w.result_recommendation);shot(w,'03-blocked-selection-retains-qualified-recommendation');assert [c.template.to_dict() for c in w.candidates]==before
        row=next(r for r in problem_rows(w,1) if r['code']=='WIDTH');locate_problem(w,row);w.candidate_scroll.ensureWidgetVisible(w.result_problem_items);app.processEvents();point=w.people.viewport().mapToGlobal(w.people.visualRect(w.people.currentIndex()).center());assert w.legacy_table_scroll.viewport().rect().contains(w.legacy_table_scroll.viewport().mapFromGlobal(point));shot(w,'04-typed-name-field-and-frame-location');assert w.people.currentColumn()==0
        comparison.show();w.people.item(0,2).setText('1234567890'*20);assert not comparison.check_current();assert not comparison.select_side(0);shot(comparison,'05-stale-comparison-not-selected');comparison.hide();w.generate();wait_layout(w);w.foreground_layout_session.hide();assert recommendation(w)['index'] is None;row=next(r for r in problem_rows(w,0) if r['code']=='WIDTH' and r['kind']=='phone');locate_problem(w,row);assert w.people.currentColumn()==2;w.candidate_scroll.ensureWidgetVisible(w.result_recommendation);shot(w,'06-long-phone-no-safe-recommendation')
        people,companies,logos=w.input_data();graph=InputGraph.from_legacy(people,companies,logos);w.adopt_input_graph(graph.data);w.generate();wait_layout(w);w.foreground_layout_session.hide();row=next(r for r in problem_rows(w,0) if r['code']=='WIDTH' and r['kind']=='phone');real_exec=InputGraphDialog.exec;located=[];data_before=copy.deepcopy(w.active_input_graph.data)
        def inspect_exec(dialog):
            def inspect():
                located.append(dialog.selected_id);shot(dialog,'07-stable-field-in-actual-person-card');dialog.reject()
            QTimer.singleShot(30,dialog,inspect);return real_exec(dialog)
        with patch.object(InputGraphDialog,'exec',inspect_exec):target=locate_problem(w,row)
        assert located==[target['field']['field_id']];assert w.active_input_graph.data==data_before
        w.last_layout_summary.update(state='CANCELLED',total=3,checked=2,unstarted=1);w.refresh_candidate_views(w.candidate_list.currentRow());w.candidate_scroll.ensureWidgetVisible(w.result_recommendation);assert not recommendation(w)['scope_complete'];shot(w,'08-partial-scope-not-global-optimum');assert not errors,errors
        result=dict(status='PASS',screens=screens,qt_uncaught=errors,scope='CONTROLLED_SYNTHETIC_LINUX_NOT_REFERENCE_HOST',recommendation_rule='ARGMAX_FINITE_EXISTING_SCORE_OVER_CURRENT_QUALIFIED_ONLY',comparison_copies_nonformal=True,problem_location='Typed actual slot IDs and compiled stable field IDs, not name guessing',business_writes=False,source_preparation_excluded=True,automatic_training=False,paid_services=False)
        (folder/'candidate-results-capture.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
    finally:
        w.pool.waitForDone(5000);app.processEvents();sys.excepthook=previous
        for dialog in dialogs:dialog.deleteLater()
        case.doCleanups();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);args=parser.parse_args();result=capture(args.folder);print(json.dumps({k:v for k,v in result.items() if k!='screens'},ensure_ascii=False))

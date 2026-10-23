"""十父題新增流程的真實 Qt 擷取；只使用本機合成 fixture，不代替測試。"""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'tests')]
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from template_ai.gui import MainWindow
from template_ai.customer_candidates_dialog import CustomerCandidatesDialog
from template_ai.customer_sync_dialog import CustomerSyncDialog
from template_ai.logo_library_dialog import LogoLibraryDialog
from template_ai.logo_review_dialog import LogoReviewDialog
from template_ai.multi_size_dialog import MultiSizeDialog
from test_customer_candidates import CustomerCandidateTests
from test_logo_workflow_gui import LogoWorkflowGuiTests
from test_multi_size import MultiSizeTests,approve_formats
from gui_wait import dispose_main_window


def capture(root):
    app=QApplication.instance() or QApplication([]);root=Path(root);root.mkdir(parents=True,exist_ok=True)
    def shot(dialog,name):
        dialog.show();app.processEvents()
        if not dialog.grab().save(str(root/name)):raise ValueError('擷取失敗：'+name)
        dialog.hide();dialog.deleteLater()
    customer=CustomerCandidateTests();customer.setUp();w=None
    try:
        row=customer.candidates.propose(customer.source['id'])[0]
        w=MainWindow(customer.library.root)
        candidates=CustomerCandidatesDialog(w);candidates.table.setCurrentCell(0,1)
        shot(candidates,'fixed70-customer-source-candidates.png')
        assert not customer.store.search('00001',field='CODE')
        reviewed=customer.reviewed(row);cid=customer.commit([reviewed])[0]['customer_id'];snapshot=customer.store.get(cid)
        w.adopt_input_graph(snapshot['graph'],snapshot)
        sync=CustomerSyncDialog(w,customer.store,snapshot)
        field=next(f for f in sync.working['fields'] if f['kind']=='phone');field['value']='020-000-0999';sync.refresh()
        assert sync.plan['rows'] and not sync.selected()
        shot(sync,'fixed70-customer-selective-sync.png')
        assert customer.store.get(cid)==snapshot
    finally:
        if w:dispose_main_window(w)
        customer.tearDown()
    logo=LogoWorkflowGuiTests();logo.setUp()
    try:
        proposal=logo.proposal();review=LogoReviewDialog(logo.store,proposal)
        assert review.compare.available and not any(c.isChecked() for c in review.flags.values())
        shot(review,'fixed70-logo-source-review.png')
        library=LogoLibraryDialog(logo.window);library.views.setCurrentIndex(2)
        assert library.focus_proposal(proposal['id']);assert not logo.window.library.logos()
        shot(library,'fixed70-logo-size-library.png')
    finally:logo.tearDown()
    matrix=MultiSizeTests();matrix.setUp();w=None
    try:
        w=MainWindow(matrix.library.root);w.adopt_input_graph(matrix.graph.data)
        dialog=MultiSizeDialog(w);dialog.inputs=matrix.inputs;dialog.graph=matrix.graph;dialog.service=matrix.workflow
        dialog.render_rows();assert [e['state'] for e in dialog.service.entries]==['VALID','BLOCKED']
        shot(dialog,'fixed70-multi-size-overview.png')
        plan=matrix.workflow.plan(matrix.output,matrix.requests());approve_formats(matrix.workflow,plan,dpi=96);results=matrix.workflow.execute(plan,True,True,dpi=96)
        assert all(r['status']=='SUCCESS' for r in results) and len(results)==6
        import shutil
        for result in results:shutil.copyfile(result['path'],root/('fixed70-'+Path(result['path']).name))
    finally:
        if w:dispose_main_window(w)
        matrix.tearDown()
    audit=dict(kind='ACTUAL_QT_SYNTHETIC_TEN_PARENT_WORKFLOWS',source_candidates_do_not_write_master=True,
        selective_sync_default_unchecked_and_master_unchanged=True,logo_review_real_source_visible_flags_default_false=True,
        size_library_focus_exact_pending_candidate=True,multi_size_states=['VALID','BLOCKED'],
        actual_exports=6,export_modes=['FINAL','PREVIEW'],formats=['pdf','png','jpg'],
        no_customer_order_history=True,not_verified=['私人AI全面一致','實體印刷','Windows','獨立覆核'])
    (root/'fixed70-ten-gui-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(audit,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--artifacts-dir',type=Path,required=True)
    capture(parser.parse_args().artifacts_dir)

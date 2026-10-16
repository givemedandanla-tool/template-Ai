"""Actual synthetic Qt/files evidence for the 28-parent software clause audit."""
import argparse,json,os,sys,shutil,time
from pathlib import Path
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'tests')]
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QMessageBox,QTableWidgetItem
from PySide6.QtTest import QTest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from gui_wait import wait_layout

from template_ai.gui import MainWindow
from template_ai.automatic_training_dialog import AutomaticTrainingDialog
from template_ai.annotation_dialog import AnnotationDialog
from template_ai.text_policy_dialog import TextPolicyDialog
from template_ai.custom_layout_dialog import CustomLayoutDialog
from template_ai.output_batch_dialog import OutputBatchDialog
from template_ai.multi_size_dialog import MultiSizeDialog
from template_ai.input_graph import InputGraph
from template_ai.input_graph_dialog import InputGraphDialog
from template_ai.demo import demo_template
import test_automatic_pages as page_fixture
import test_automatic_training as automatic_fixture
import test_template_versions as version_fixture
import test_custom_layout as custom_fixture
import test_multi_size as multi_fixture


def capture(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);app=QApplication.instance() or QApplication([]);audit={};shots=[];errors=[];old_hook=sys.excepthook
    def hook(kind,value,tb):errors.append(str(value));old_hook(kind,value,tb)
    sys.excepthook=hook
    def shot(dialog,name):
        dialog.show();app.processEvents()
        if not dialog.grab().save(str(folder/name)):raise ValueError('Qt capture failed '+name)
        shots.append(name);dialog.hide()
    def wait(fn):
        end=time.monotonic()+15
        while not fn() and time.monotonic()<end:app.processEvents();QTest.qWait(10)
        if not fn():raise ValueError('bounded worker wait failed')
    def close(window):
        if window:window.input_timer.stop();window.font_manager.close();window.library.close();window.deleteLater();app.processEvents()
    pages=page_fixture.AutomaticPagesTests();pages.setUp();window=None
    try:
        path=pages.pages();report=pages.service.preflight([path]);assert len(report['items'])==2
        job=pages.service.create(report,'SYNTHETIC_EVIDENCE',True);result=pages.run_job(job);window=MainWindow(pages.library.root);dialog=AutomaticTrainingDialog(window);dialog.render(result);shot(dialog,'next28-all-readable-pages-persistent.png')
        audit['all_pages']=dict(readable_pages=[i['page'] for i in result['items']],separate_source_ids=len({i['source_id'] for i in result['items']}),native_artboard_mapping='UNKNOWN',jobs_not_auto_published=True)
    finally:close(window);pages.tearDown()
    auto=automatic_fixture.AutomaticTrainingTests();auto.setUp();window=None
    try:
        result=auto.run_job(auto.job());window=MainWindow(auto.library.root);work=window.library.artworks(result['items'][0]['source_id'])[0];marking=AnnotationDialog(window,work['id']);identity=marking.session.payload['slots'][0]['id'];marking.select([identity]);marking.session.change(dict(operation='MOVE',ids=[identity],dx=1,dy=0));marking.refresh();marking.compare();shot(marking.comparison,'next28-marking-linked-before-after.png');audit['annotation']=dict(geometry_draft_only=True,original_unchanged=True,actual_images_differ=marking.comparison.data['before_png']!=marking.comparison.data['after_png'],view_sync_can_be_disabled=True)
    finally:close(window);auto.tearDown()
    versions=version_fixture.TemplateVersionTests();versions.setUp();window=None
    try:
        draft=versions.service.clone(versions.service.plan(versions.t.id),'SYNTHETIC','Synthetic design review',True);window=MainWindow(versions.library.root);window.refresh_templates(draft.id);window.tabs.setCurrentIndex(1);window.editor_selection([draft.slots[1].id]);dialog=TextPolicyDialog(window);dialog.values[0].setValue(.2);dialog.values[2].setValue(.5);dialog.distribute.setChecked(True);dialog.reason.setText('Synthetic reviewed title-only policy');dialog.preview();shot(dialog,'next28-fixed-point-tracking-preview.png');assert window.library.object_snapshot('TEMPLATE',draft.id)['payload']['slots'][1]['tracking_mm']==0
        graph=InputGraph.from_legacy([dict(name=['Alex Example'],title=['Designer'])],[]);entry=InputGraphDialog(window,graph.data);fid=next(f['id'] for f in graph.data['fields'] if f['kind']=='name');entry.field_editors[fid].setText('W'*200);entry.pending_input[fid]='W'*200;entry.refresh_warnings();assert entry.warning_report['issues'];shot(entry,'next28-live-input-field-warning.png');entry.warning_timer.stop();audit['text_and_input']=dict(point_size_unchanged=True,tracking_preview_not_applied=True,inline_warning_and_exact_field_ids=True,estimated_risk_not_global_unsolvable=True)
        good=demo_template();good.name='Qualified synthetic';bad=demo_template();bad.name='Narrow diagnostic';bad.slots[0].rect.w=20;window.library.publish(good);window.library.publish(bad);window.people.setRowCount(1)
        for col,value in enumerate(('Alex Example','Designer','123','a@example.test','','','','')):window.people.setItem(0,col,QTableWidgetItem(value))
        window.tabs.setCurrentIndex(2);window.generate();wait_layout(window);assert window.qualified_candidates.count() and window.blocked_candidates.count();shot(window,'next28-qualified-diagnostic-separate.png');audit['candidates']=dict(qualified=window.qualified_candidates.count(),diagnostic=window.blocked_candidates.count(),separate_sections=True)
    finally:close(window);versions.doCleanups()
    custom=custom_fixture.CustomLayoutTests();custom.setUp();window=None
    try:
        window=MainWindow(custom.library.root);window.people.setRowCount(1)
        for col,value in enumerate(('Alex Example','Designer','123','a@example.test','','','','')):window.people.setItem(0,col,QTableWidgetItem(value))
        dialog=CustomLayoutDialog(window);dialog.limits['expand_mm'].setValue(40);dialog.reason.setText('Synthetic current-job geometry bounds');dialog.preview();wait(lambda:not dialog.running);assert dialog.plan['status']=='FEASIBLE_DRAFT';shot(dialog,'next28-cassowary-unpublished-custom.png');audit['custom']=dict(status=dialog.plan['status'],solver=dialog.plan['solver'],policy=dialog.plan['policy'],published=False,changed_slots=len(dialog.plan['changes']))
    finally:close(window);custom.doCleanups()
    multi=multi_fixture.MultiSizeTests();multi.setUp();window=None
    try:
        window=MainWindow(multi.library.root);window.adopt_input_graph(multi.graph.data);owner=MultiSizeDialog(window)
        for row in range(owner.table.rowCount()):owner.table.item(row,0).setCheckState(Qt.Checked)
        owner.start();wait(lambda:not owner.running);assert owner.service and owner.is_current();dialog=OutputBatchDialog(owner,owner.service.plan(multi.output,multi.requests()))
        for index,(_,action) in enumerate(dialog.controls):
            if index not in (1,4):action.setCurrentIndex(action.findData('SKIP'))
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):dialog.run(False)
        wait(lambda:not dialog.running);assert sum(r['status']=='SUCCESS' for r in dialog.engine.items)==2;shot(dialog,'next28-per-file-output-results.png')
        for row in dialog.engine.items:
            if row['status']=='SUCCESS':shutil.copyfile(row['path'],folder/('next28-safe-batch-'+row['mode'].lower()+'.png'))
        audit['output']=dict(statuses=[r['status'] for r in dialog.engine.items],exact_results=[{k:r.get(k) for k in ('mode','status','sha256','bytes','attempts')} for r in dialog.engine.items],preview_default_png=owner.preview_formats['png'].isChecked(),final_preview_separate=True)
    finally:close(window);multi.tearDown()
    app.processEvents();sys.excepthook=old_hook
    if errors:raise ValueError('Unhandled Qt capture callback: '+str(errors))
    audit.update(status='SELF_CAPTURED_SOFTWARE_CLAUSE_AUDIT_28',screenshots=shots,unhandled_qt_errors=errors,limitations=['Synthetic Linux/offscreen Qt only','No independent review','Native Illustrator unknown details remain unknown','No physical print or Windows hardware validation','No paid service/API'])
    (folder/'next28-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n');return audit

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--artifacts-dir',required=True);args=p.parse_args();result=capture(args.artifacts_dir);print(json.dumps(dict(status=result['status'],screenshots=len(result['screenshots']))))

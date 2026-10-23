"""Source-bound Qt evidence for the ongoing twenty-parent work, not completion."""
import argparse
import json
import os
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'tests')]
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from template_ai.gui import MainWindow
from template_ai.automatic_training_dialog import AutomaticTrainingDialog
from template_ai.annotation_dialog import AnnotationDialog
from template_ai.work_overview_dialog import WorkOverviewDialog,SourceRegionsDialog
from template_ai.semantic_learning_dialog import SemanticLearningDialog
from template_ai.template_versions_dialog import TemplateVersionsDialog
from template_ai.object_dialog import ObjectToolsDialog
import test_automatic_training as automatic_fixture
import test_semantic_learning as semantic_fixture
import test_template_versions as version_fixture


def capture(folder):
    folder=Path(folder);folder.mkdir(exist_ok=True,parents=True);app=QApplication.instance() or QApplication([]);audit={};shots=[]
    def shot(dialog,name):
        dialog.show();app.processEvents()
        if not dialog.grab().save(str(folder/name)):raise ValueError('Qt擷取失敗：'+name)
        shots.append(name);dialog.hide();dialog.deleteLater()
    def close(window):
        if window:window.input_timer.stop();window.font_manager.close();window.library.close();window.deleteLater();app.processEvents()
    automatic=automatic_fixture.AutomaticTrainingTests();automatic.setUp();window=None
    try:
        original=automatic.path.read_bytes();job=automatic.run_job(automatic.job());window=MainWindow(automatic.library.root);work=window.library.artworks(job['items'][0]['source_id'])[0]
        progress=AutomaticTrainingDialog(window);progress.render(job);shot(progress,'next20-automatic-source-work-stages.png')
        overview=WorkOverviewDialog(window);assert overview.table.rowCount()==2;shot(overview,'next20-source-work-overview.png')
        marking=AnnotationDialog(window,work['id']);marking.index_mode.setCurrentIndex(1);marking.select([work['payload']['slots'][0]['id']]);assert marking.ids and marking.tree_nodes;assert marking.session.facts['confirmation'] is None
        shot(marking,'next20-source-marking-and-evidence.png')
        regions=SourceRegionsDialog(window.library,work);from template_ai.model import Rect
        regions.add(Rect(0,0,90,54));regions.add(Rect(100,0,90,54));shot(regions,'next20-source-work-region-candidates.png')
        assert automatic.path.read_bytes()==original;assert not automatic.library.templates()
        audit['automatic']=dict(phase=job['phase'],sources=len(job['items']),units=automatic.service.store.count('AUTO_UNIT'),source_unchanged=True,facts_still_pending=True,templates_published=0)
    finally:close(window);automatic.tearDown()
    semantic=semantic_fixture.SemanticLearningTests();semantic.setUp();window=None
    try:
        candidate=semantic.candidate();window=MainWindow(semantic.library.root);dialog=SemanticLearningDialog(window);dialog.models.setCurrentIndex(dialog.models.findData(candidate['id']));shot(dialog,'next20-local-semantic-model-heldout.png')
        assert semantic.service.active()[0] is None
        audit['semantic']=dict(state=candidate['state'],metrics=candidate['metrics'],baseline_metrics=candidate['baseline_metrics'],vocabulary_size=candidate['vocabulary_size'],parameter_count=candidate['parameter_count'],weights_digest=candidate['weights_digest'],activated=False,fixture='SYNTHETIC_CONFIRMED_TEXT; NOT_REAL_WORLD_ACCURACY')
    finally:close(window);semantic.doCleanups()
    versions=version_fixture.TemplateVersionTests();versions.setUp();window=None
    try:
        original=versions.library.object_snapshot('TEMPLATE',versions.t.id);draft=versions.service.clone(versions.service.plan(versions.t.id),'SYNTHETIC_REVIEWER','Synthetic evidence new draft',True);draft.slots[0].rect.x+=1;versions.library.save_template(draft)
        window=MainWindow(versions.library.root);window.refresh_templates(draft.id);dialog=TemplateVersionsDialog(window);assert 'OBJECT' in dialog.details.toPlainText();shot(dialog,'next20-template-version-difference.png')
        editor=ObjectToolsDialog(window,'TEMPLATE',draft.id);editor.margin.setValue(10);editor.preview_margin();assert editor.plan and any('安全區' in r for r in editor.plan['warnings']);assert versions.library.object_snapshot('TEMPLATE',draft.id)['payload']['safe_margin_mm']==0
        shot(editor,'next20-canvas-safety-preview-unpublished.png');assert versions.library.object_snapshot('TEMPLATE',versions.t.id)==original
        audit['versions']=dict(published_version_unchanged=True,safety_zone_preview_only=True,difference_visible=True,rollback_requires_explicit_confirmation=True)
    finally:close(window);versions.doCleanups()
    audit.update(status='SELF_CAPTURED_ONGOING_TWENTY; NOT_PARENT_COMPLETION',screenshots=shots,limitations=['Linux/offscreen Qt','Synthetic sources only','No independent review','No real Illustrator native-layer claim','No paid LLM/API'])
    (folder/'next20-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n');return audit


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--artifacts-dir',required=True);args=parser.parse_args();result=capture(args.artifacts_dir);print(json.dumps(dict(status=result['status'],screenshots=len(result['screenshots']))))

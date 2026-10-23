"""Actual C-scope coverage views: current collections, exact manifest and old immutable counts."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]


def capture(folder):
    from PySide6.QtCore import QTimer,QCoreApplication,QEvent
    from PySide6.QtWidgets import QApplication
    from test_qualified_coverage_gui import QualifiedCoverageGuiTests
    from training_fixture import source_work,observations
    from test_noise_authoring import confirmed
    from test_trusted_samples import admitted
    from quality_acceptance_fixture import actual_positive_pair
    from template_ai.training_quality_dialog import TrainingQualityDialog
    import psutil
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);case=QualifiedCoverageGuiTests('runTest');case.setUp();base=admitted(case.store,case.work);source,alias=source_work(case.library,case.root,'authored-alias.svg');confirmed(case.store,alias);second=admitted(case.store,alias)
    source,validation=source_work(case.library,case.root,'authored-validation.svg',note_text='合成驗證來源');obs=observations(validation);obs[-1]['text']='合成驗證來源';facts=case.store.save_facts(validation['id'],obs,0,validation['revision']);case.store.confirm_facts(validation['id'],[o['id'] for o in obs],facts['revision'],facts['pins'],case.store.source_proof(validation['id']),'Synthetic author',True);sample=admitted(case.store,validation);dataset=case.store.create_dataset(case.store.dataset_plan('明列驗證用途的合成精確資料集',[dict(sample_id=sample['id'],role='VALIDATION')]),'Synthetic author',True);actual_positive_pair(case,execute=False)
    app=QApplication.instance() or QApplication([]);old=sys.excepthook;errors=[];sys.excepthook=lambda typ,value,tb:errors.append(str(value));timer=QTimer();timer.setInterval(20);ticks=[];rss=[];process=psutil.Process();timer.timeout.connect(lambda:(ticks.append(time.monotonic()),rss.append(process.memory_info().rss)));screens=[];timer.start();window=center=panel=None
    def settle():case.wait(center.quality_panel);assert panel.report is not None,panel.status.text()
    def shot(name):
        panel.tree.expandToDepth(1);app.processEvents();path=folder/('qualified-coverage-'+name+'.png');assert panel.grab().save(str(path));screens.append(path.name)
    try:
        window=case.window();center=TrainingQualityDialog(window);case.addCleanup(center.deleteLater);center.resize(1220,880);center.show();panel=center.coverage_panel;center.tabs.setCurrentWidget(panel);settle();assert panel.report['counts']['distinct_source_files']==2 and panel.report['counts']['deduplicated_approved_label_weights']==1;historical_id=panel.report['snapshot_id'];shot('01-trainable-alias-denominators')
        panel.collection.setCurrentIndex(panel.collection.findData('CANDIDATE_PENDING'));settle();assert panel.report['counts']['currently_verified_occurrences']==0;shot('02-pending-not-training')
        panel.collection.setCurrentIndex(panel.collection.findData('VALIDATION'));settle();assert panel.report['roles']=={'VALIDATION':1};shot('03-development-validation')
        panel.collection.setCurrentIndex(panel.collection.findData('QUALITY_HOLDOUT'));settle();assert panel.report['roles']=={'HOLDOUT':2} and 'TEXT_AND_VECTOR' in panel.report['facets']['logo'];shot('04-independent-set-is-separate')
        panel.collection.setCurrentIndex(panel.collection.findData('EXACT_DATASET'));case.wait(center.quality_panel);assert panel.dataset.currentData() is None;panel.dataset.setCurrentIndex(panel.dataset.findData(dataset['id']));settle();assert panel.report['roles']=={'VALIDATION':1};shot('05-exact-role-pinned-manifest')
        for selected in (base,second):case.store.transition_sample(case.store.sample_transition_plan(selected['id'],'REVOKE'),'Synthetic author','Explicitly revoke these two example admissions',True)
        panel.collection.setCurrentIndex(panel.collection.findData('APPROVED_TRAINABLE'));settle();assert panel.report['counts']['currently_verified_occurrences']==0;shot('06-revoked-current-empty')
        panel.histories();case.wait(center.quality_panel);panel.history.setCurrentIndex(panel.history.findData(historical_id));panel.load_history();settle();assert panel.historical and panel.report['counts']['currently_verified_occurrences']==2 and not panel.locate_button.isEnabled();shot('07-historical-not-current')
        report=dict(status='PASS',screens=screens,actual_owned_commands=True,source_files_before_revocation=2,exact_content_groups=1,deduplicated_label_weights=1,validation_and_holdout_separate=True,old_snapshot_retained=True,historical_snapshot_not_current=True,training_started=False,supplementation=False,quality_pass_claim=False,scope='Authored synthetic current-Linux controlled workflow only; not production accuracy/native Illustrator/reference hardware or independent review')
    finally:
        timer.stop();case.doCleanups();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents();sys.excepthook=old
    report.update(unhandled_runtime_errors=errors,parent_rss_peak=max(rss,default=process.memory_info().rss),max_gui_gap_ms=max((b-a for a,b in zip(ticks,ticks[1:])),default=0)*1000,gui_ticks=len(ticks),resource_profile='controlled_resources fixture; source preparation excluded; not hardware benchmark')
    if errors:raise AssertionError(str(errors))
    (folder/'qualified-coverage-capture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--artifacts-dir',type=Path,required=True);args=parser.parse_args();r=capture(args.artifacts_dir);print(json.dumps(dict(status=r['status'],screens=len(r['screens']),qt_errors=len(r['unhandled_runtime_errors']))))

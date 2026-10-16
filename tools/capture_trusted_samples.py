"""Actual native local sample review and privacy capture using authored synthetic data."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]


def capture(folder):
    from PySide6.QtCore import Qt,QTimer,QCoreApplication,QEvent
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from test_trusted_sample_gui import TrustedSampleGuiTests
    import psutil
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);case=TrustedSampleGuiTests('runTest');case.setUp();app=QApplication.instance() or QApplication([]);errors=[];old=sys.excepthook;sys.excepthook=lambda typ,value,tb:errors.append(str(value));screens=[];ticks=[];rss=[];timer=QTimer();timer.setInterval(20);process=psutil.Process();timer.timeout.connect(lambda:(ticks.append(time.monotonic()),rss.append(process.memory_info().rss)));timer.start();dialog=center=None
    def shot(name,index):
        dialog.tabs.setCurrentIndex(index);app.processEvents();path=folder/('trusted-samples-'+name+'.png');assert dialog.grab().save(str(path));screens.append(path.name)
    def settle():case.wait(center.quality_panel);assert not center.quality_panel.loading
    try:
        center,dialog=case.dialog();dialog.table.selectRow(0);dialog.detail();settle();shot('01-source-review',0)
        dialog.actor.setText('Synthetic source author');dialog.basis.setCurrentIndex(dialog.basis.findData('OWNED'));dialog.reference.setText('合法作者合成來源，只供本機流程驗證；不是生產準確率或實機效能證明');dialog.table.cellWidget(0,3).setCurrentIndex(1);dialog.preview_batch();settle();assert dialog.pending and not dialog.consent.isChecked();shot('02-exact-admission-preview',0)
        dialog.consent.setChecked(True);dialog.confirm();settle();assert case.store.count('SAMPLE')==1;dialog.collection.setCurrentIndex(dialog.collection.findData('ADMITTED'));settle();dialog.table.selectRow(0);dialog.detail();settle();shot('03-admitted-not-trained',0)
        sample=case.store.records('SAMPLE')[0];dataset=case.store.create_dataset(case.store.dataset_plan('Synthetic exact local geometry manifest',[dict(sample_id=sample['id'],role='TRAIN')]),'Synthetic author',True);geometry=case.store.learn_dataset_sample(case.store.geometry_learning_plan(dataset['id'],sample['id'],'Actual synthetic geometry draft'),case.store.source_proof(case.work['id']),'Synthetic author',True)
        dialog.trace();settle();assert 'DATASET:' in dialog.trace_details.toPlainText() and 'TEMPLATE:' in dialog.trace_details.toPlainText();shot('04-actual-use-lineage',1)
        dialog.purpose_checks[0][1].setChecked(True);dialog.privacy_action.setCurrentIndex(dialog.privacy_action.findData('REQUEST_LOCAL_ERASURE'));dialog.retention.setValue(0);dialog.preview_restriction();settle();assert dialog.pending;shot('05-stop-use-preview',2);dialog.consent.setChecked(True);dialog.confirm();settle();assert case.store.sample_state(sample['id'])=='RESTRICTED_USE'
        dialog.load_privacy_records();settle();assert dialog.privacy_records.count()==1 and dialog.privacy_records.item(0).checkState()==Qt.Unchecked;dialog.privacy_records.item(0).setCheckState(Qt.Checked);dialog.preview_redaction();settle();assert dialog.pending;shot('06-local-copy-redaction-preview',2);dialog.consent.setChecked(True);dialog.confirm();settle();assert case.store.get('SAMPLE',sample['id'])['local_training_text_redacted'];shot('07-minimal-privacy-receipt',2)
        report=dict(status='PASS',screens=screens,actual_owned_worker_commands=True,admitted_samples=1,actual_geometry_dataset=dataset['id'],actual_geometry_draft=geometry.id,model_training_started=False,automatic_production_activation=False,source_purpose_stopped=True,local_training_copy_text_logically_redacted=True,original_source_and_business_facts_deleted=False,external_backups_deleted=False,filesystem_secure_erasure=False,model_decontaminated=False,scope='Authored synthetic local workflow on current Linux host; no production/nativeAI/referencehardware or independent-review claim')
    finally:
        timer.stop();case.doCleanups();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents();sys.excepthook=old
    report.update(unhandled_runtime_errors=errors,parent_rss_peak=max(rss,default=process.memory_info().rss),max_gui_gap_ms=max((b-a for a,b in zip(ticks,ticks[1:])),default=0)*1000,gui_ticks=len(ticks),resource_profile='controlled_resources workflow fixture; not hardware benchmark')
    if errors:raise AssertionError('Actual Qt errors: '+str(errors))
    (folder/'trusted-samples-capture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--artifacts-dir',type=Path,required=True);args=parser.parse_args();report=capture(args.artifacts_dir);print(json.dumps(dict(status=report['status'],screens=len(report['screens']),qt_errors=len(report['unhandled_runtime_errors']))))

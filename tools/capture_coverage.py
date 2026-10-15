"""Actual UI052 Qt/process/SQLite captures with synthetic sources and host measurements."""
import json
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]


def capture_coverage(folder):
    from PySide6.QtCore import QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    import psutil
    import test_coverage_batches as fixtures
    from training_fixture import source_work,observations
    from test_noise_authoring import confirmed
    from template_ai.gui import MainWindow
    from template_ai.coverage_closure_panel import CoverageClosurePanel
    from template_ai.coverage_evidence import LAYERS
    app=QApplication.instance() or QApplication([]);case=fixtures.CoverageBatchTests('runTest');case.setUp();window=panel=None;folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    ticks=[];rss=[];process=psutil.Process();timer=QTimer();timer.setInterval(20)
    def pulse():
        ticks.append(time.monotonic());rss.append(process.memory_info().rss)
    timer.timeout.connect(pulse)
    def wait(predicate,timeout=35):
        start=time.monotonic()
        while not predicate():
            app.processEvents();QTest.qWait(10)
            if time.monotonic()-start>timeout:raise RuntimeError('UI052 capture did not reach real persisted state: '+(panel.status.text() if panel else 'initializing'))
    def settled():wait(lambda:not panel.loading)
    def shot(name):
        app.processEvents()
        if not panel.grab().save(str(folder/name)):raise RuntimeError('UI052 actual Qt screenshot failed')
    def review(member,work):
        plan=case.service.segmentation_plan(member['id'],[work['id']],'Synthetic selfcheck: full source page and actual single work boundary inspected')
        case.service.confirm_segmentation(plan,'Synthetic selfcheck',True)
        for layer in LAYERS:
            decision='VERIFIED_ABSENT' if layer in ('companies','whole_logo','customer') else 'NO_CANDIDATE_RETAINED' if layer=='styles' else 'CONFIRMED'
            plan=case.service.layer_plan(member['id'],work['id'],layer,decision,'Synthetic selfcheck: individually compare exact source layer','Page1 and actual SVG text/geometry; no production identity or publication approval')
            case.service.confirm_layer(plan,'Synthetic selfcheck',True)
    try:
        source,a=source_work(case.library,case.root,'A0001.svg');alias,b=source_work(case.library,case.root,'B0002.svg');confirmed(case.store,a);case.store.save_facts(b['id'],observations(b),0,b['revision'])
        batch=case.batch([source,alias]);members=case.service.members(batch['id'])['rows'];first=next(m for m in members if any(p['source_id']==source['id'] for p in m['frozen']['source_pins']));second=next(m for m in members if m['id']!=first['id']);review(first,a)
        window=MainWindow(case.library.root);window.show();panel=CoverageClosurePanel(window);panel.resize(1460,1150);panel.show();timer.start()
        wait(lambda:window.runtime.monitor.snapshot() is not None and window.runtime.monitor.snapshot().sequence>=2)
        panel.activate();settled();panel.batches.setCurrentIndex(panel.batches.findData(batch['id']));panel.load_batch();settled();panel.table.selectRow(next(i for i,m in enumerate(panel.rows) if m['id']==second['id']));panel.inspect();settled();shot('remaining28-coverage-alias-pending.png')
        panel.plan_close();settled();blocked=panel.pending[1]
        if blocked['closure_allowed'] or blocked['file_count']!=2 or blocked['file_disposition_rate']!=.5 or blocked['individually_reviewed_files']!=1:raise RuntimeError('same bytes incorrectly reused independent review')
        shot('remaining28-coverage-blocked-closure.png')
        facts=case.store.facts(b['id']);case.store.confirm_facts(b['id'],[o['id'] for o in facts['observations']],facts['revision'],facts['pins'],case.store.source_proof(b['id']),'Synthetic selfcheck',True);review(second,b)
        panel.plan_close();settled()
        if not panel.pending[1]['closure_allowed']:raise RuntimeError('all exact current review layers did not permit source disposition closure')
        panel.actor.setText('Synthetic selfcheck');panel.approved.setChecked(True);panel.confirm();settled();status=case.service.closure_status(batch['id'])
        if not status['current_complete']:raise RuntimeError('GUI did not persist actual closure receipt')
        receipt=case.store.get('COVERAGE_CLOSURE',status['receipt_id']);shot('remaining28-coverage-committed-receipt.png')
        Path(source['original_path']).write_text(Path(source['original_path']).read_text()+'\n<!-- synthetic changed version -->')
        panel.check_closure();settled();stale=case.service.closure_status(batch['id'])
        if stale['current_complete'] or case.store.get('COVERAGE_CLOSURE',receipt['id'])!=receipt:raise RuntimeError('old immutable receipt was reused or overwritten after source change')
        shot('remaining28-coverage-stale-source.png')
        (case.root/'bulk').mkdir();sources=[case.source(f'bulk/source-{i:04}.svg') for i in range(600)];bulk=case.batch(sources);start=time.monotonic();panel.list_batches();settled();panel.batches.setCurrentIndex(panel.batches.findData(bulk['id']));panel.offset=0;panel.query.clear();panel.load_batch();settled();page_elapsed=time.monotonic()-start
        if len(panel.rows)!=50 or panel.batch['file_count']!=600:raise RuntimeError('600-file page boundary incorrect')
        shot('remaining28-coverage-600-file-page.png');panel.query.setText('SOURCE-0599');panel.search();settled()
        if len(panel.rows)!=1 or not panel.rows[0]['frozen']['original_path'].endswith('0599.svg'):raise RuntimeError('global search was applied after page limit')
        host=window.runtime.state();intervals=[b-a for a,b in zip(ticks,ticks[1:])]
        report=dict(status='PASS',kind='ACTUAL_QT_SUBPROCESS_SQLITE_SYNTHETIC_SELF_CHECK',parent='UI-052',source_files=2,source_pages=2,actual_works=2,distinct_source_ids=[source['id'],alias['id']],shared_content_hash=source['hash'],same_bytes_independent_review_blocked=True,blocked_disposition_rate=blocked['file_disposition_rate'],committed_receipt_id=receipt['id'],source_change_state=stale['state'],immutable_old_receipt_preserved=True,publishes_rules_styles_or_output=False,bulk_files=600,page_rows=50,global_search_rows=1,measured_page_load_seconds=page_elapsed,measured_gui_heartbeat_max_interval_seconds=max(intervals,default=None),measured_parent_peak_rss_bytes=max(rss,default=None),actual_current_host=host,reference_hardware_claim=False,windows_verified=False,independent_review=False,real_personal_data=False)
        (folder/'remaining28-coverage-capture.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');return report
    finally:
        timer.stop()
        if panel:panel.cancel()
        if window:window.pool.waitForDone(5000);app.processEvents()
        if panel:panel.close()
        if window:window.source=None;window.work=None;window.template=None;window.close()
        case.doCleanups();app.processEvents()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--artifacts-dir',required=True);args=parser.parse_args();print(json.dumps(dict(status=capture_coverage(args.artifacts_dir)['status'])))

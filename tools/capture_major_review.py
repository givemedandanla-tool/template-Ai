"""Actual original major workbench, owned source job, human facts and version gates."""
import argparse,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]


def capture(folder):
    from PySide6.QtCore import QTimer,QCoreApplication,QEvent,Qt
    from PySide6.QtWidgets import QApplication,QMessageBox
    from test_major_review_template_gui import MajorTemplateGuiTests
    from test_major_review_job_gui import MajorReviewJobGuiTests
    from template_ai.training_quality_dialog import TrainingQualityDialog
    from template_ai.quality_rechecks import blocked
    from gui_wait import wait_for_gui
    app=QApplication.instance();case=MajorTemplateGuiTests('runTest');case.setUp();app=QApplication.instance();d=case.d;p=case.page;w=case.w;folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);screens=[];errors=[];old_hook=sys.excepthook;sys.excepthook=lambda typ,error,tb:errors.append(str(error));center=None
    def shot(name,anchor=None,widget=None):
        if anchor is not None:d.major_scroll.ensureWidgetVisible(anchor,0,40)
        app.processEvents();target=widget or d;path=folder/('major-review-'+name+'.png');assert target.grab().save(str(path));screens.append(path.name)
    def select_work():
        index=next(i for i,r in enumerate(p.rows) if r['kind']=='QUALITY_WORK_QUARANTINE');p.table.selectRow(index)
    def save():d.consent.setChecked(True);d.confirm();case.wait()
    def manual_facts(yes,name):
        facts=center.facts_panel;facts.focus(case.work['id'],[]);before_shots=len(screens);facts.actor.setText('Synthetic native reviewer');facts.table.selectAll();started=time.monotonic();timer=QTimer();timer.setInterval(20)
        def answer():
            box=QApplication.activeModalWidget()
            if isinstance(box,QMessageBox):
                try:assert box.defaultButton() is box.button(QMessageBox.No);shot(name,widget=box);box.button(QMessageBox.Yes if yes else QMessageBox.No).click()
                except BaseException as error:errors.append(str(error));box.reject()
                timer.stop()
            elif time.monotonic()-started>12:errors.append('Fact confirmation dialog missing');timer.stop()
        timer.timeout.connect(answer);timer.start();facts.confirm();assert wait_for_gui(lambda:not facts.running,15),facts.status.text();timer.stop();assert len(screens)>before_shots,'Actual fact confirmation dialog never appeared'
    try:
        case.template=case.publish();before=case.library.object_snapshot('TEMPLATE',case.template.id);w.resize(1360,940);d.resize(1360,940);w.show();d.show();p.preview();case.wait();assert p.plan
        shot('01-source-examples-sealed-scope',p.category);d.guard(d.confirm);assert not blocked(case.store,case.work['id']);shot('02-no-consent-no-quarantine',p.coverage)
        save();assert blocked(case.store,case.work['id']);shot('03-persisted-actual-scope-denominator',p.table);select_work();p.preview_job();case.wait();assert p.job_plan;shot('04-explicit-incremental-source-plan',p.job_notice)
        job=MajorReviewJobGuiTests.start(case);assert job['phase']=='COMPLETED';assert blocked(case.store,case.work['id']);p.load_case(0);case.wait();select_work();p.show_analysis();case.wait();assert '新分析' in d.details.toPlainText();shot('05-owned-job-old-new-no-auto-release',p.job_notice)
        center=TrainingQualityDialog(w);center.resize(1360,940);center.tabs.setCurrentWidget(center.facts_panel);center.show()
        from training_fixture import observations
        facts=center.facts_panel;facts.focus(case.work['id'],[])
        for observation in observations(case.work):
            facts.observed_text.setText(observation['text']);facts.object_type.setCurrentText(observation['object_type']);facts.classification.setCurrentText(observation['classification']);facts.slot_combo.setCurrentIndex(facts.slot_combo.findData(observation['slot_id']))
            for spin,key in zip(facts.coords,('x','y','w','h')):spin.setValue(observation['region'][key])
            facts.add()
        assert len(facts.loaded['observations'])==5;shot('05a-authored-observations-original-editor',widget=center)
        manual_facts(False,'06-real-default-no-fact-confirmation');assert blocked(case.store,case.work['id']);manual_facts(True,'07-real-yes-exact-source-human-facts');shot('08-original-source-facts-persisted',widget=center);center.hide();d.show()
        select_work();p.finding_evidence.setPlainText('Authored source: all exact observations, ownership and source version individually checked in original facts editor');p.preview_finding();case.wait();assert p.finding_plan,d.status.text();shot('09-new-human-finding-preview',p.finding_evidence);save();assert not blocked(case.store,case.work['id']);shot('10-work-cleared-template-still-held',p.table)
        case.select_template();case.fill();p.preview_template();case.wait();assert p.template_plan and p.template_plan['can_release'],d.status.text();shot('11-exact-old-template-physical-qa-preview',p.template_evidence)
        p.draft_name.setText('Authored current source corrected draft');p.preview_repair();case.wait();assert p.template_plan;new_id=p.template_plan['template']['id'];shot('12-controlled-current-source-draft-preview',p.draft_name);save();assert p.template_target.text()==new_id;assert case.library.object_snapshot('TEMPLATE',case.template.id)==before
        p.preview_template();case.wait();assert p.template_plan and p.template_plan['can_release'],d.status.text();shot('13-new-version-full-checks-no-global-release',p.template_evidence);save();assert p.case['completed'] is False
        p.preview_closure();case.wait();assert p.template_plan and p.template_plan['can_close'];shot('14-pinned-scope-completion-preview',p.template_evidence);save();assert p.case['completed'];assert not p.case['whole_corpus_safe'];assert not p.case['models_decontaminated'];closure=p.case['closure_receipt'];shot('15-completed-scope-model-corpus-unknown',p.table)
        select_work();p.preview_reopen();case.wait();save();assert blocked(case.store,case.work['id']);assert p.case['closure_receipt']==closure;assert p.case['state']=='REVIEW_REQUIRED';assert any(r['kind']=='QUALITY_TEMPLATE_QUARANTINE' and r['effective_state']=='STALE_REVIEW' for r in p.rows);shot('16-new-doubt-reopens-retains-old-receipt',p.table)
        assert not errors,errors
        result=dict(status='PASS',screens=screens,qt_errors=errors,actual_gui=True,actual_original_source_job=True,actual_original_facts_no_yes=True,old_publication_unchanged=True,scope='Authored Linux Qt source review and original FIFO; exact work/template QA, version repair, pinned scope close/reopen. No Windows hardware/native Illustrator corpus qualification; no model/global/output approval.',paid_services=False)
        (folder/'major-review-metadata.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');return result
    finally:
        sys.excepthook=old_hook
        if center is not None:center.deleteLater()
        # Only fixture disposal bypasses the unrelated authored input close prompt.
        # Source fact No/Yes and every product approval above remain actual GUI.
        w.navigation.confirm_close=lambda:True
        case.doCleanups();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',required=True);args=parser.parse_args();r=capture(args.folder);print(json.dumps({k:v for k,v in r.items() if k!='screens'},ensure_ascii=False))

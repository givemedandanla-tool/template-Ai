"""Actual synthetic Qt views and machine audits; media remain local by user publication policy."""
import copy
import json
import sys
from pathlib import Path


def capture_ten_packages(root):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests'))
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from unittest.mock import patch
    from template_ai.gui import MainWindow
    from template_ai.training_quality_dialog import TrainingQualityDialog
    from training_fixture import source_work, observations
    root = Path(root); window = MainWindow(root / 'ten-package-data')
    source, work = source_work(window.library, root, 'synthetic-ten.svg', visual=False)
    payload = copy.deepcopy(work['payload']); payload['slots'][0]['rect']['x'] = 99
    work = window.library.save_artwork(work['id'], payload, work['revision'])
    before = copy.deepcopy(work); dialog = TrainingQualityDialog(window)
    try:
        dialog.show(); QApplication.processEvents()
        row = next(i for i, r in enumerate(dialog.rows) if r['code'] == 'BOUNDS'); dialog.table.selectRow(row)
        QApplication.processEvents()
        if not dialog.grab().save(str(root / 'ten-quality-overview.png')): raise ValueError('實際品質GUI證據未保存')
        dialog.locate(); QApplication.processEvents()
        assert window.work['id'] == work['id'] and window.current_slot.id == payload['slots'][0]['id']
        assert window.library.artwork(work['id']) == before
        dialog.locate(); assert '已定位' in dialog.status.text()
        assert window.library.artwork(work['id']) == before
        audit = {'package': 1, 'actual_qt': True, 'rows': dialog.rows, 'selected': dialog.selected_row(),
                 'located_work': window.work['id'], 'located_slot': window.current_slot.id,
                 'db_markings_unchanged': True, 'source_mapping': 'UNKNOWN', 'full_quality_pass': False,
                 'scope': 'Anonymous source SVG, saved labels, actual Qt view; no native AI/visual equivalence claim'}
        source2, work2 = source_work(window.library, root, 'synthetic-facts.svg')
        facts = dialog.facts_panel; facts.store.save_facts(work2['id'], observations(work2), 0, 1); facts.reload(); facts.work_combo.setCurrentIndex(facts.work_combo.findData(work2['id'])); facts.table.selectAll(); facts.actor.setText('Synthetic Reviewer'); dialog.tabs.setCurrentWidget(facts)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            QTest.mouseClick(facts.confirm_button, Qt.LeftButton)
            for _ in range(300):
                QApplication.processEvents()
                if not facts.running: break
                QTest.qWait(10)
        assert not facts.running and facts.store.facts_state(work2['id']) == 'CONFIRMED'
        assert window.library.artwork(work2['id']) == work2
        QApplication.processEvents()
        if not dialog.grab().save(str(root/'ten-facts-confirmed.png')): raise ValueError('事實GUI未保存')
        audit['facts'] = {'actual_qt': True, 'confirmed': facts.store.facts(work2['id']), 'history': facts.store.history('FACTS', work2['id']), 'source_and_slots_unchanged': True, 'sample_count': facts.store.count('SAMPLE'), 'rule_count': facts.store.count('RULE')}
        from template_ai.noise_authoring_dialog import NoiseAuthoringDialog
        facts.table.selectRow(next(i for i, o in enumerate(facts.loaded['observations']) if o['id'] == 'note'))
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes): QTest.mouseClick(facts.exclude_button, Qt.LeftButton)
        wizard = NoiseAuthoringDialog(facts.store, work2['id'], 'note', 'Synthetic Reviewer', dialog)
        try:
            wizard.show(); wizard.table.selectRow(0); QApplication.processEvents()
            if not wizard.grab().save(str(root/'ten-noise-authoring.png')): raise ValueError('雜訊作者GUI未保存')
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes): QTest.mouseClick(wizard.save_button, Qt.LeftButton)
            assert wizard.saved_rule and wizard.saved_rule['state'] == 'PENDING'
            assert window.library.artwork(work2['id']) == work2
            audit['noise_authoring'] = {'actual_qt': True, 'rule': wizard.saved_rule, 'candidates': facts.store.noise_candidates(work2['id']), 'source_and_slots_unchanged': True, 'no_rule_activation': True}
        finally: wizard.close()
        rules = dialog.rules_panel; rules.reload(); dialog.tabs.setCurrentWidget(rules); rules.table.selectRow(next(i for i, r in enumerate(rules.rows) if r['id'] == wizard.saved_rule['id'])); rules.actor.setText('Synthetic Reviewer'); rules.reason.setText('exact scope and source examples checked'); QApplication.processEvents()
        if not dialog.grab().save(str(root/'ten-rule-review.png')): raise ValueError('規則審核GUI未保存')
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes): QTest.mouseClick(rules.approve_button, Qt.LeftButton)
        reviewed = facts.store.get('RULE', wizard.saved_rule['id']); assert reviewed['state'] == 'ACTIVE'
        assert window.library.artwork(work2['id']) == work2
        audit['rule_review'] = {'actual_qt': True, 'active_rule': reviewed, 'inspection': facts.store.inspect_rule(reviewed['id']), 'source_and_slots_unchanged': True}
        future_source, future_work = source_work(window.library, root, 'synthetic-future.svg')
        future_facts = facts.store.save_facts(future_work['id'], observations(future_work), 0, 1)
        future_facts = facts.store.confirm_facts(future_work['id'], [o['id'] for o in future_facts['observations']], future_facts['revision'], future_facts['pins'], facts.store.source_proof(future_work['id']), 'Synthetic Reviewer', True)
        hits = dialog.hits_panel; dialog.tabs.setCurrentWidget(hits); hits.search.setText(future_work['id']+' 已校稿'); assert len(hits.rows) == 1; hits.table.selectRow(0); QApplication.processEvents()
        assert hits.rows[0]['current']['state'] == 'EXCLUDED_RULE' and hits.rows[0]['trace_current']
        assert window.library.artwork(future_work['id']) == future_work
        if not dialog.grab().save(str(root/'ten-noise-auto-hit.png')): raise ValueError('自動命中GUI未保存')
        audit['auto_hits'] = {'actual_qt': True, 'future_work': future_work, 'hit': hits.selected_row(), 'counts': hits.count.text(), 'rule_reapproval_prompts': 0, 'source_and_slots_unchanged': True}
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes): QTest.mouseClick(hits.keep_button, Qt.LeftButton)
        assert hits.rows[0]['current']['state'] == 'KEPT_LOCAL'
        rules.reload(); dialog.tabs.setCurrentWidget(rules); rules.table.selectRow(next(i for i, r in enumerate(rules.rows) if r['id']==reviewed['id']))
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes): QTest.mouseClick(rules.disable_button, Qt.LeftButton)
        disabled=facts.store.get('RULE',reviewed['id']);assert disabled['state']=='DISABLED';rules.table.selectRow(next(i for i,r in enumerate(rules.rows) if r['id']==reviewed['id']))
        from PySide6.QtWidgets import QInputDialog
        with patch.object(QInputDialog,'getInt',return_value=(2,True)),patch.object(QMessageBox,'question',return_value=QMessageBox.Yes): QTest.mouseClick(rules.rollback_button,Qt.LeftButton)
        restored=facts.store.get('RULE',reviewed['id']);assert restored['state']=='PENDING' and restored['revision']>disabled['revision'];assert window.library.artwork(future_work['id'])==future_work;QApplication.processEvents()
        if not dialog.grab().save(str(root/'ten-noise-recovery.png')):raise ValueError('規則回滾GUI未保存')
        audit['noise_recovery']={'actual_qt':True,'local_keep':facts.store.local_record(future_work['id']),'disabled':disabled,'restored_pending':restored,'history':facts.store.history('RULE',reviewed['id']),'published_templates_unchanged':True,'model_decontamination_claim':False}
        samples=dialog.samples_panel;dialog.tabs.setCurrentWidget(samples);samples.reload();samples.work_combo.setCurrentIndex(samples.work_combo.findData(future_work['id']));samples.basis.setCurrentText('OWNED');samples.reference.setText('Anonymous synthetic SVG author record');samples.actor.setText('Synthetic Reviewer')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):
            QTest.mouseClick(samples.admit_button,Qt.LeftButton)
            for _ in range(300):
                QApplication.processEvents()
                if not samples.running:break
                QTest.qWait(10)
        assert not samples.running and samples.store.count('SAMPLE')==1;sample=samples.rows[0];samples.table.selectRow(0);QApplication.processEvents();assert samples.store.sample_state(sample['id'])=='APPROVED';assert not sample['used_for_training'] and window.library.templates()==[]
        if not dialog.grab().save(str(root/'ten-trusted-sample.png')):raise ValueError('可信樣本GUI未保存')
        audit['trusted_sample']={'actual_qt':True,'sample':sample,'positive_negative_separated':True,'not_trained':True,'state':'APPROVED','source_and_slots_unchanged':window.library.artwork(future_work['id'])==future_work}
        datasets=dialog.dataset_panel;dialog.tabs.setCurrentWidget(datasets);datasets.reload();datasets.actor.setText('Synthetic Reviewer');datasets.name.setText('Synthetic TRAIN geometry dataset');idx=next(i for i,r in enumerate(datasets.rows) if r['id']==sample['id']);datasets.table.item(idx,0).setCheckState(Qt.Checked);datasets.table.cellWidget(idx,1).setCurrentText('TRAIN')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):QTest.mouseClick(datasets.create_button,Qt.LeftButton)
        ds=facts.store.get('DATASET',datasets.dataset_combo.currentData());assert ds['entries'][0]['role']=='TRAIN';datasets.template_name.setText('Synthetic Geometry Draft')
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):
            QTest.mouseClick(datasets.learn_button,Qt.LeftButton)
            for _ in range(300):
                QApplication.processEvents()
                if not datasets.running:break
                QTest.qWait(10)
        assert not datasets.running and len(window.library.templates())==1;draft=window.library.templates()[0];assert draft.state=='draft' and draft.training_reference['sample_id']==sample['id'];assert window.library.artwork(future_work['id'])==future_work;datasets.load_dataset();QApplication.processEvents()
        if not dialog.grab().save(str(root/'ten-dataset-learned-draft.png')):raise ValueError('幾何學習GUI未保存')
        audit['dataset_geometry']={'actual_qt':True,'dataset':ds,'draft':draft.to_dict(),'use':facts.store.records('USE'),'not_published':True,'source_and_slots_unchanged':True,'neural_training_claim':False}
        coverage=dialog.inventory_panel;dialog.tabs.setCurrentWidget(coverage);coverage.reload();assert coverage.report['totals']['sources']==3 and coverage.report['totals']['artworks']==3;assert coverage.report['sample_states']=={'APPROVED':1};assert coverage.report['current_role_occurrences_in_scanned_scope']=={'TRAIN':1};assert not coverage.report['quality_pass_claim'] and not coverage.report['supplementation'];QApplication.processEvents()
        if not dialog.grab().save(str(root/'ten-coverage-distribution.png')):raise ValueError('覆蓋GUI未保存')
        audit['coverage']={'actual_qt':True,'report':coverage.report,'read_only':True,'no_quality_threshold_or_supplementation':True}
        extra_source,extra_work=source_work(window.library,root,'synthetic-queue.svg',note_text='佇列合成註記');extra_observations=observations(extra_work);next(o for o in extra_observations if o['id']=='note')['text']='佇列合成註記';extra_facts=facts.store.save_facts(extra_work['id'],extra_observations,0,1);facts.store.confirm_facts(extra_work['id'],[o['id'] for o in extra_observations],extra_facts['revision'],extra_facts['pins'],facts.store.source_proof(extra_work['id']),'Synthetic Reviewer',True);rights={'basis':'OWNED','reference':'Anonymous synthetic SVG author record','use':'GEOMETRY_TRAINING_LOCAL'};extra_sample=facts.store.approve_sample(facts.store.sample_approval_plan(extra_work['id'],rights),facts.store.source_proof(extra_work['id']),'Synthetic Reviewer',True);queue_ds=facts.store.create_dataset(facts.store.dataset_plan('Synthetic queue dataset',[{'sample_id':extra_sample['id'],'role':'TRAIN'}]),'Synthetic Reviewer',True)
        queue=dialog.queue_panel;dialog.tabs.setCurrentWidget(queue);queue.reload();queue.dataset_combo.setCurrentIndex(queue.dataset_combo.findData(queue_ds['id']));queue.prefix.setText('Synthetic Queue Draft');queue.actor.setText('Synthetic Reviewer');queue.items.item(0,0).setCheckState(Qt.Checked)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):
            QTest.mouseClick(queue.create_button,Qt.LeftButton)
            for _ in range(1000):
                QApplication.processEvents()
                if not queue.running:break
                QTest.qWait(10)
        assert not queue.running;job=facts.store.get('JOB',queue.current_job);assert job['phase']=='COMPLETED' and job['items'][0]['state']=='SUCCESS';assert len(window.library.templates())==2 and all(t.state=='draft' for t in window.library.templates());assert window.library.artwork(extra_work['id'])==extra_work;QApplication.processEvents()
        if not dialog.grab().save(str(root/'ten-training-queue-completed.png')):raise ValueError('真worker佇列GUI未保存')
        audit['training_queue']={'actual_qt':True,'real_worker_own_sqlite_connection':True,'job':job,'history':facts.store.history('JOB',job['id']),'progress':queue.progress_label.text(),'controls_restored':queue.create_button.isEnabled() and not window.busy,'source_and_slots_unchanged':True,'all_ten_workflows_integrated':True,'only_draft_geometry':True}
        from public_evidence import public_audit
        (root / '.private').mkdir(exist_ok=True)
        (root / '.private' / 'ten-packages-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n')
        (root / 'ten-packages-audit.json').write_text(json.dumps(public_audit(audit), ensure_ascii=False, indent=2)+'\n')
    finally:
        dialog.close(); window.source = None; window.work = None; window.template = None; window.close()

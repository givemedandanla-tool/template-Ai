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
        (root / 'ten-packages-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n')
    finally:
        dialog.close(); window.source = None; window.work = None; window.template = None; window.close()

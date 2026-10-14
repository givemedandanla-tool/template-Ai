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
        (root / 'ten-packages-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n')
    finally:
        dialog.close(); window.source = None; window.work = None; window.template = None; window.close()

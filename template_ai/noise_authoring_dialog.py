"""Scoped rule authoring: positive observation, explicit region and real counterexamples."""
import json
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QComboBox, QCheckBox, QDoubleSpinBox, QPlainTextEdit, QPushButton, QMessageBox
from .noise import relative_region


class NoiseAuthoringDialog(QDialog):
    def __init__(self, store, work_id, observation_id, actor, parent=None):
        super().__init__(parent); self.store = store; self.work_id = work_id; self.observation_id = observation_id; self.actor = actor; self.saved_rule = None; self.offset = 0
        self.facts, self.observation = store.observation(work_id, observation_id); self.epoch = store.epoch
        self.setWindowTitle('剔除並記住：只建立待審規則'); self.resize(1000, 720); outer = QVBoxLayout(self)
        self.status = QLabel('完整字串與來源type／作品相對區域；姓名、公司、Logo、未知保留。不直接啟用通用規則。'); self.status.setWordWrap(True); outer.addWidget(self.status)
        bar = QHBoxLayout(); self.mode = QComboBox(); self.mode.addItems(['NONE', 'NFC']); bar.addWidget(QLabel('文字正規化')); bar.addWidget(self.mode); self.nfc = QCheckBox('明確同意NFC對照（仍需審核）'); bar.addWidget(self.nfc); outer.addLayout(bar)
        zone = relative_region(store.library.artwork(work_id), self.observation); self.coords = []; bar = QHBoxLayout()
        for key in ('x', 'y', 'w', 'h'):
            bar.addWidget(QLabel(key)); spin = QDoubleSpinBox(); spin.setRange(0, 1); spin.setDecimals(6); spin.setValue(zone[key]); spin.valueChanged.connect(self.preview); self.coords.append(spin); bar.addWidget(spin)
        outer.addWidget(QLabel('明列適用區域（作品0～1，不用子字串黑名單）')); outer.addLayout(bar)
        outer.addWidget(QLabel('選取已人工確認且應保留的完整欄位／Logo反例')); self.table = QTableWidget(0, 4); self.table.setHorizontalHeaderLabels(['完整反例文字', '分類', '作品', '觀察ID']); self.table.setEditTriggers(QTableWidget.NoEditTriggers); self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setSelectionMode(QTableWidget.ExtendedSelection); self.table.itemSelectionChanged.connect(self.preview); outer.addWidget(self.table, 2)
        bar = QHBoxLayout(); self.previous_button = QPushButton('上一頁反例'); self.next_button = QPushButton('下一頁反例'); self.previous_button.clicked.connect(lambda: self.page(-200)); self.next_button.clicked.connect(lambda: self.page(200)); bar.addWidget(self.previous_button); bar.addWidget(self.next_button); outer.addLayout(bar)
        self.details = QPlainTextEdit(); self.details.setReadOnly(True); outer.addWidget(self.details, 1); bar = QHBoxLayout(); self.save_button = QPushButton('確認剔除此項＋建立PENDING規則'); self.save_button.clicked.connect(self.save); bar.addWidget(self.save_button); cancel = QPushButton('取消'); cancel.clicked.connect(self.reject); bar.addWidget(cancel); outer.addLayout(bar)
        self.mode.currentIndexChanged.connect(self.preview); self.nfc.toggled.connect(self.preview); self.reload()

    def page(self, delta):
        self.offset = max(0, self.offset+delta); self.reload()

    def reload(self):
        self.rows = []
        for facts in self.store.records('FACTS', self.offset):
            if self.store.facts_state(facts['id']) != 'CONFIRMED': continue
            for observation in facts['observations']:
                if observation['id'] in facts['confirmation']['observation_ids'] and self.store.protected_observation(facts['id'], observation) and observation['classification'] in ('FIELD', 'LOGO'):
                    self.rows.append({'work_id': facts['id'], 'observation_id': observation['id'], 'text': observation['text'], 'classification': observation['classification']})
        self.rows.sort(key=lambda r: (r['work_id'], r['observation_id'])); self.table.setRowCount(len(self.rows))
        for i, row in enumerate(self.rows):
            for j, value in enumerate((row['text'], row['classification'], row['work_id'], row['observation_id'])): self.table.setItem(i, j, QTableWidgetItem(value))
        self.previous_button.setEnabled(self.offset > 0); self.next_button.setEnabled(self.offset+200 < self.store.count('FACTS')); self.preview()

    def selected_refs(self):
        return [{'work_id': self.rows[r.row()]['work_id'], 'observation_id': self.rows[r.row()]['observation_id']} for r in self.table.selectionModel().selectedRows()]

    def preview(self, *_):
        if not hasattr(self, 'details'): return
        data = {'before': {'observation': self.observation, 'facts_revision': self.facts['revision']}, 'after': {'local': 'EXCLUDE_THIS_OBSERVATION_ONLY', 'rule': 'PENDING_NOT_ACTIVE', 'full_literal': self.observation['text'], 'normalization': self.mode.currentText(), 'zone': dict(zip(('x', 'y', 'w', 'h'), (s.value() for s in self.coords))), 'counterexamples': self.selected_refs()}, 'preserved': 'SOURCE_PIXELS_AND_FORMAL_SLOTS'}
        self.details.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))

    def save(self):
        self.save_button.setEnabled(False)
        try:
            self.preview()
            if QMessageBox.question(self, '只剔除此項並建立待審候選', self.details.toPlainText(), QMessageBox.Yes|QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
            self.saved_rule = self.store.propose_noise_rule(self.work_id, self.observation_id, self.selected_refs(), dict(zip(('x', 'y', 'w', 'h'), (s.value() for s in self.coords))), self.mode.currentText(), self.facts['revision'], self.epoch, self.actor, approved=True, normalization_approved=self.nfc.isChecked())
            self.accept()
        except Exception as error: self.status.setText('未保存：'+str(error))
        finally: self.save_button.setEnabled(True)

"""Human source observations and explicit work-fact confirmation, using the shared store."""
import copy
import json
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox, QDoubleSpinBox, QPushButton, QLabel, QTableWidget, QTableWidgetItem, QPlainTextEdit, QMessageBox, QInputDialog
from .model import new_id
from .source_links import hash_source
from .training_store import TrainingStore


class FactsPanel(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent); self.window = window; self.store = TrainingStore(window.library); self.loaded = None; self.running = False; self.jobs = {}; self.offset = 0
        outer = QVBoxLayout(self); bar = QHBoxLayout(); self.work_combo = QComboBox(); self.work_combo.currentIndexChanged.connect(self.load); bar.addWidget(self.work_combo, 1)
        self.reload_button = QPushButton('重載已保存作品'); self.reload_button.clicked.connect(self.reload); bar.addWidget(self.reload_button)
        self.previous_button = QPushButton('上一頁'); self.next_button = QPushButton('下一頁'); self.previous_button.clicked.connect(lambda: self.page(-200)); self.next_button.clicked.connect(lambda: self.page(200)); bar.addWidget(self.previous_button); bar.addWidget(self.next_button); outer.addLayout(bar)
        self.status = QLabel('人工來源觀察；原生映射UNKNOWN。事實確認、通用規則與樣本准入分開。'); self.status.setTextFormat(Qt.PlainText); self.status.setWordWrap(True); outer.addWidget(self.status)
        self.table = QTableWidget(0, 5); self.table.setHorizontalHeaderLabels(['完整來源文字', 'type／分類', 'exact框', '區域mm', '觀察ID']); self.table.setEditTriggers(QTableWidget.NoEditTriggers); self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setSelectionMode(QTableWidget.ExtendedSelection); self.table.itemSelectionChanged.connect(self.selected); outer.addWidget(self.table, 2)
        form = QFormLayout(); self.observed_text = QLineEdit(); form.addRow('完整來源文字（最多2048字資源預算，超限拒絕而不截斷）', self.observed_text)
        self.object_type = QComboBox(); self.object_type.addItems(['TEXT', 'ANNOTATION', 'LOGO_PART', 'UNKNOWN']); form.addRow('来源物件類型', self.object_type)
        self.classification = QComboBox(); self.classification.addItems(['FIELD', 'ANNOTATION', 'LOGO', 'UNKNOWN']); form.addRow('人工分類', self.classification)
        self.slot_combo = QComboBox(); form.addRow('連結已保存框（可無）', self.slot_combo)
        rect = QHBoxLayout(); self.coords = []
        for label in ('x', 'y', 'w', 'h'):
            rect.addWidget(QLabel(label)); spin = QDoubleSpinBox(); spin.setDecimals(3); spin.setRange(0, 2000); spin.setValue(1 if label in ('w', 'h') else 0); rect.addWidget(spin); self.coords.append(spin)
        form.addRow('來源毫米區域', rect); self.actor = QLineEdit(); self.actor.setMaxLength(120); self.actor.setPlaceholderText('確認者名稱（只存本機）'); form.addRow('事實確認者', self.actor); outer.addLayout(form)
        bar = QHBoxLayout(); self.add_button = QPushButton('新增觀察'); self.update_button = QPushButton('更新選中觀察'); self.remove_button = QPushButton('移除選中觀察'); self.confirm_button = QPushButton('确认選中作品事實'); self.revoke_button = QPushButton('撤銷事實確認')
        for button, handler in ((self.add_button, self.add), (self.update_button, self.update), (self.remove_button, self.remove), (self.confirm_button, self.confirm), (self.revoke_button, self.revoke)):
            button.clicked.connect(handler); bar.addWidget(button)
        outer.addLayout(bar); self.details = QPlainTextEdit(); self.details.setReadOnly(True); outer.addWidget(self.details, 1); self.reload()
        bar = QHBoxLayout(); self.exclude_button = QPushButton('只排除此作品的選中觀察'); self.remember_button = QPushButton('剔除並記住（待審候選）'); self.undo_noise_button = QPushButton('撤銷選中局部剔除'); self.exclude_button.clicked.connect(self.exclude); self.remember_button.clicked.connect(self.remember); self.undo_noise_button.clicked.connect(self.undo_noise); bar.addWidget(self.exclude_button); bar.addWidget(self.remember_button); bar.addWidget(self.undo_noise_button); outer.addLayout(bar); self.controls()
        self.repair_button=QPushButton('以已保存原稿事實預覽局部修復問題');self.repair_button.clicked.connect(self.open_repair);outer.addWidget(self.repair_button)
        self._editor_baseline=self.observation('editor-state')

    def open_repair(self):
        try:
            if not self.loaded or self.has_pending_observation():raise ValueError('先保存或保留待核對人工內容；不把未保存編輯當成修復真值')
            parent=self.parentWidget()
            while parent is not None and not hasattr(parent,'quality_panel'):parent=parent.parentWidget()
            if parent is None:raise ValueError('請由既有訓練／品質中心開啟修復')
            parent.quality_panel.open_repair(dict(origin='SOURCE_FACTS',origin_id=self.loaded['id'],work_id=self.loaded['id']))
        except (ValueError,KeyError) as error:self.status.setText(str(error))

    def page(self, delta):
        self.offset = max(0, self.offset+delta); self.reload()

    def reload(self):
        if self.running: return
        key = self.work_combo.currentData(); self.work_combo.blockSignals(True); self.work_combo.clear()
        try:
            rows = list(self.store.db.execute('SELECT id,name FROM artworks ORDER BY id LIMIT 200 OFFSET ?', (self.offset,)))
            for wid, name in rows: self.work_combo.addItem(name+' / '+wid, wid)
            index = self.work_combo.findData(key)
            if index >= 0: self.work_combo.setCurrentIndex(index)
            total = self.store.db.execute('SELECT count(*) FROM artworks').fetchone()[0]; self.previous_button.setEnabled(self.offset > 0); self.next_button.setEnabled(self.offset+len(rows) < total)
        except Exception as error: self.status.setText('載入失敗：'+str(error))
        finally: self.work_combo.blockSignals(False); self.load()

    def focus(self,work_id,observation_ids):
        from PySide6.QtWidgets import QTableWidgetSelectionRange
        if self.loaded and self.loaded['id']!=work_id and self.has_pending_observation():raise ValueError('來源事實有尚未套用的人工內容，先保存／保留後再切換作品')
        self.store.library.artwork(work_id)
        rank=self.store.db.execute('SELECT count(*) FROM artworks WHERE id<?',(work_id,)).fetchone()[0];self.offset=(rank//200)*200;self.reload();self.work_combo.setCurrentIndex(self.work_combo.findData(work_id));self.load()
        selected=set(observation_ids)
        for index,observation in enumerate(self.loaded['observations']):
            if observation['id'] in selected:self.table.setRangeSelected(QTableWidgetSelectionRange(index,0,index,4),True)

    def load(self, *_):
        if self.running: return
        try:
            wid = self.work_combo.currentData(); self.loaded = self.store.facts(wid) if wid else None; self.table.setRowCount(0); self.slot_combo.clear(); self.slot_combo.addItem('無框連結', None)
            if self.loaded:
                work = self.store.library.artwork(wid); self.work_revision = work['revision']
                for slot in work['payload']['slots']: self.slot_combo.addItem(slot.get('kind', '?')+' / '+slot.get('id', '?'), slot.get('id'))
                observations = self.loaded['observations']; self.table.setRowCount(len(observations))
                for i, o in enumerate(observations):
                    for j, value in enumerate((o['text'], o['object_type']+' / '+o['classification'], o['slot_id'] or 'UNKNOWN', str(o['region']), o['id'])):
                        item = QTableWidgetItem(value); item.setToolTip(value); self.table.setItem(i, j, item)
                self.status.setText(self.store.facts_state(wid)+f"／事實r{self.loaded['revision']}；確認範圍明列，沒有自動規則／樣本准入。")
            self.details.setPlainText(json.dumps({'facts': self.loaded, 'history': self.store.history('FACTS', wid) if wid else [], 'training_candidates': self.store.noise_candidates(wid) if wid else []}, ensure_ascii=False, indent=2))
        except Exception as error: self.loaded = None; self.status.setText('載入失敗：'+str(error))
        self.controls()

    def controls(self):
        enabled = bool(self.loaded) and not self.running and not self.window.busy
        for button in (self.add_button, self.update_button, self.remove_button, self.confirm_button, self.revoke_button): button.setEnabled(enabled)
        if hasattr(self, 'exclude_button'):
            self.exclude_button.setEnabled(enabled); self.remember_button.setEnabled(enabled); self.undo_noise_button.setEnabled(enabled)
        self.work_combo.setEnabled(not self.running); self.reload_button.setEnabled(not self.running)

    def indices(self):
        return sorted({r.row() for r in self.table.selectionModel().selectedRows()})

    def selected(self):
        rows = self.indices()
        if self.loaded and len(rows) == 1:
            item = self.loaded['observations'][rows[0]]; self.observed_text.setText(item['text']); self.object_type.setCurrentText(item['object_type']); self.classification.setCurrentText(item['classification']); self.slot_combo.setCurrentIndex(max(0, self.slot_combo.findData(item['slot_id'])))
            for spin, label in zip(self.coords, ('x', 'y', 'w', 'h')): spin.setValue(item['region'][label])
            self.repair_button=QPushButton('以已保存原稿事實預覽局部修復問題');self.repair_button.clicked.connect(self.open_repair);outer.addWidget(self.repair_button)
        self._editor_baseline=self.observation('editor-state')

    def has_pending_observation(self):
        current=self.observation('editor-state')
        return current!=getattr(self,'_editor_baseline',current)

    def observation(self, oid):
        return {'id': oid, 'slot_id': self.slot_combo.currentData(), 'text': self.observed_text.text(), 'object_type': self.object_type.currentText(), 'classification': self.classification.currentText(), 'region': dict(zip(('x', 'y', 'w', 'h'), (x.value() for x in self.coords)))}

    def save(self, observations):
        if self.running or self.window.busy: raise ValueError('背景工作尚未完成')
        self.store.save_facts(self.loaded['id'], observations, self.loaded['revision'], self.work_revision); self.load();self._editor_baseline=self.observation('editor-state')

    def add(self):
        try: self.save(self.loaded['observations']+[self.observation(new_id())])
        except Exception as error: self.status.setText('未新增：'+str(error)); self.controls()

    def update(self):
        try:
            rows = self.indices()
            if len(rows) != 1: raise ValueError('一次選一項更新')
            observations = copy.deepcopy(self.loaded['observations']); observations[rows[0]] = self.observation(observations[rows[0]]['id']); self.save(observations)
        except Exception as error: self.status.setText('未更新：'+str(error)); self.controls()

    def remove(self):
        try:
            rows = self.indices()
            if not rows: raise ValueError('先選取觀察')
            if QMessageBox.question(self, '移除觀察', f'只移除本作品{len(rows)}項觀察；事實確認將失效。原稿與欄位不刪。', QMessageBox.Yes|QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
            self.save([o for i, o in enumerate(self.loaded['observations']) if i not in rows])
        except Exception as error: self.status.setText('未移除：'+str(error)); self.controls()

    def confirm(self):
        if self.running or self.window.busy: return
        try:
            rows = self.indices()
            if not rows: raise ValueError('先明列選中觀察')
            from .training_store import text
            actor = text(self.actor.text(), '確認者', 120); record = copy.deepcopy(self.loaded); ids = [record['observations'][i]['id'] for i in rows]
            source = self.store.library.source(record['pins']['source_id']); path = source['current_path']
        except Exception as error: self.status.setText('未確認：'+str(error)); return
        self.running = True; self.controls(); self.status.setText('背景核對來源內容，尚未確認事實')
        from .gui import Job
        job = Job(lambda: hash_source(path, byte_limit=50_000_000)); token = new_id(); self.jobs[token] = job; job.signals.setParent(self)
        def release():
            self.running = False; self.jobs.pop(token, None); job.signals.deleteLater(); self.controls()
        def failed(error):
            self.status.setText('來源核對失敗：'+str(error)); release()
        def finished(proof):
            try:
                self.store.checked(record['id'], proof)
                scope = f"作品{record['id']}／事實r{record['revision']}／觀察{', '.join(ids)}\n來源SHA256 {record['pins']['source_hash']}\n只确认選中來源事實；不批准規則、不准入樣本。"
                if QMessageBox.question(self, '確認作品事實', scope, QMessageBox.Yes|QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                    self.status.setText('已取消，未確認事實'); return
                self.store.confirm_facts(record['id'], ids, record['revision'], record['pins'], proof, actor, approved=True); self.running = False; self.load()
            except Exception as error: self.status.setText('未確認：'+str(error))
            finally: release()
        job.signals.done.connect(finished, Qt.QueuedConnection); job.signals.error.connect(failed, Qt.QueuedConnection); QThreadPool.globalInstance().start(job)

    def revoke(self):
        try:
            reason, ok = QInputDialog.getText(self, '撤銷作品事實', '原因（保留歷史，不改原稿／欄位）')
            if not ok: return
            self.store.revoke_facts(self.loaded['id'], self.loaded['revision'], reason); self.load()
        except Exception as error: self.status.setText('未撤銷：'+str(error)); self.controls()

    def exclude(self):
        try:
            ids = [self.loaded['observations'][i]['id'] for i in self.indices()]
            if not ids: raise ValueError('先選取明確觀察')
            local = self.store.local_record(self.loaded['id']); revision = self.loaded['revision']
            if QMessageBox.question(self, '只排除此作品', f"作品{self.loaded['id']}／事實r{revision}／觀察{', '.join(ids)}\n只排除訓練候選；不刪原稿／正式欄位，不建立通用規則。", QMessageBox.Yes|QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
            self.store.local_noise(self.loaded['id'], ids, local['revision'], revision, approved=True); self.load()
        except Exception as error: self.status.setText('未剔除：'+str(error)); self.controls()

    def remember(self):
        try:
            rows = self.indices()
            if len(rows) != 1: raise ValueError('一次明列一個完整來源觀察作正例')
            from .noise_authoring_dialog import NoiseAuthoringDialog
            dialog = NoiseAuthoringDialog(self.store, self.loaded['id'], self.loaded['observations'][rows[0]]['id'], self.actor.text(), self)
            try: dialog.exec()
            finally: dialog.deleteLater()
            self.load()
        except Exception as error: self.status.setText('未建立：'+str(error)); self.controls()

    def undo_noise(self):
        try:
            ids = [self.loaded['observations'][i]['id'] for i in self.indices()]; local = self.store.local_record(self.loaded['id']); revision = self.loaded['revision']
            if not ids: raise ValueError('先選取明確觀察')
            if QMessageBox.question(self, '撤銷局部剔除', f"只撤銷作品{self.loaded['id']}／{', '.join(ids)}的局部決定，保留歷史。未啟用或回滾通用規則。", QMessageBox.Yes|QMessageBox.No, QMessageBox.No) != QMessageBox.Yes: return
            self.store.clear_local_noise(self.loaded['id'], ids, local['revision'], revision, approved=True); self.load()
        except Exception as error: self.status.setText('未撤銷局部剔除：'+str(error)); self.controls()

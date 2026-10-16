"""Readonly marking overview with stable issue selection and explicit navigation."""
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QPlainTextEdit, QDialogButtonBox,QScrollArea
from .training_quality import quality_rows
from .training_navigation import require_clean_navigation, locate_work


class TrainingQualityDialog(QDialog):
    def __init__(self, window):
        super().__init__(window); self.window = window; self.rows = []; self.loading = False; self.offset = 0; self.advance = 200; self.page_history = []
        self.setWindowTitle('標記完整性／衝突定位'); self.resize(1150, 800)
        outer = QVBoxLayout(self); self.tabs = QTabWidget(); outer.addWidget(self.tabs); quality = QWidget(); self.tabs.addTab(quality, '標記品質'); layout = QVBoxLayout(quality); self.status = QLabel('只讀已保存標記，未知來源內容不當PASS；發布Gate保持原範圍。'); self.status.setWordWrap(True); self.status.setTextFormat(Qt.PlainText); layout.addWidget(self.status)
        bar = QHBoxLayout(); self.search = QLineEdit(); self.search.setPlaceholderText('搜尋問題／作品／exact ID'); self.search.textChanged.connect(self.reload); bar.addWidget(self.search, 1)
        self.filter = QComboBox()
        for name in ('ALL', 'BLOCK', 'REVIEW', 'INFO'): self.filter.addItem(name, name)
        self.filter.currentIndexChanged.connect(self.reload); bar.addWidget(self.filter)
        self.reload_button = QPushButton('重新檢查已保存標記'); self.reload_button.clicked.connect(self.reload); bar.addWidget(self.reload_button); layout.addLayout(bar)
        self.count = QLabel(); layout.addWidget(self.count)
        self.table = QTableWidget(0, 5); self.table.setHorizontalHeaderLabels(['嚴重度', '作品', '類型／原因', 'exact物件', '來源ID'])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers); self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setSelectionMode(QTableWidget.SingleSelection); self.table.itemSelectionChanged.connect(self.selected); layout.addWidget(self.table, 2)
        self.details = QPlainTextEdit(); self.details.setReadOnly(True); layout.addWidget(self.details, 1)
        bar = QHBoxLayout(); self.previous_button = QPushButton('上一頁作品'); self.next_button = QPushButton('下一頁作品'); self.previous_button.clicked.connect(lambda: self.page(-200)); self.next_button.clicked.connect(lambda: self.page(200)); bar.addWidget(self.previous_button); bar.addWidget(self.next_button)
        self.locate_button = QPushButton('定位作品／exact框'); self.locate_button.clicked.connect(self.locate); bar.addWidget(self.locate_button)
        self.edit_button = QPushButton('在既有安全編輯器核對'); self.edit_button.clicked.connect(self.edit); bar.addWidget(self.edit_button); layout.addLayout(bar)
        close = QDialogButtonBox(QDialogButtonBox.Close); close.rejected.connect(self.reject); layout.addWidget(close)
        self.report_button=QPushButton('選取作品的問題報告');self.report_button.clicked.connect(self.report);layout.addWidget(self.report_button)
        self.reload()
        from .training_facts_panel import FactsPanel
        self.facts_panel = FactsPanel(window, self); self.tabs.addTab(self.facts_panel, '來源觀察／作品事實')
        from .rule_review_panel import RuleReviewPanel
        self.rules_panel = RuleReviewPanel(window, self); self.tabs.addTab(self.rules_panel, '規則審核中心')
        from .noise_hits_panel import NoiseHitsPanel
        self.hits_panel = NoiseHitsPanel(window, self); self.tabs.addTab(self.hits_panel, '雜訊命中追溯')
        from .trusted_samples_panel import TrustedSamplesPanel
        self.samples_panel=TrustedSamplesPanel(window,self);self.tabs.addTab(self.samples_panel,'可信樣本准入')
        from .dataset_panel import DatasetPanel
        self.dataset_panel=DatasetPanel(window,self);self.tabs.addTab(self.dataset_panel,'資料集／幾何學習')
        from .coverage_panel import CoveragePanel
        self.coverage_panel=CoveragePanel(window,self);self.tabs.addTab(self.coverage_panel,'覆蓋／分布')
        from .coverage_closure_panel import CoverageClosurePanel
        self.closure_panel=CoverageClosurePanel(window,self);self.tabs.addTab(self.closure_panel,'來源審核／安全結案')
        self.tabs.currentChanged.connect(lambda index:self.closure_panel.activate() if self.tabs.widget(index) is self.closure_panel else None)
        from .training_queue_panel import TrainingQueuePanel
        self.queue_panel=TrainingQueuePanel(window,self);self.tabs.addTab(self.queue_panel,'可恢復幾何訓練工作')
        from .quality_evaluation_panel import EvaluationPanel, RecheckPanel
        from .quality_panel import QualityPanel
        self.quality_panel=QualityPanel(window,self);self.quality_scroll=QScrollArea();self.quality_scroll.setWidgetResizable(True);self.quality_scroll.setWidget(self.quality_panel);self.tabs.addTab(self.quality_scroll,'獨立品質／實際版本A/B')
        self.tabs.currentChanged.connect(lambda index:self.quality_panel.activate() if self.tabs.widget(index) is self.quality_scroll else None)
        self.evaluation_panel=EvaluationPanel(window,self);self.tabs.addTab(self.evaluation_panel,'分類評估／隔離修復')
        self.recheck_panel=RecheckPanel(window,self);self.tabs.addTab(self.recheck_panel,'重大規則依賴重審')
        from .training_exceptions_panel import TrainingExceptionsPanel
        self.automatic_exceptions=TrainingExceptionsPanel(window,self);self.tabs.addTab(self.automatic_exceptions,'作品分析例外')
        from .rule_hints_panel import RuleHintsPanel
        self.rule_hints=RuleHintsPanel(window,self);self.tabs.addTab(self.rule_hints,'確認修正／待審規則線索')
        self.setWindowTitle('標記品質／來源事實與可信訓練')
    def report(self):
        from .diagnostic_dialog import DiagnosticReportDialog
        row=self.selected_row()
        if not row:self.status.setText('先選取問題，以確定本次只檢查哪個作品');return
        dialog=DiagnosticReportDialog(self.window,'training',row['work_id'],parent=self)
        try:dialog.exec()
        finally:dialog.deleteLater()
    def reject(self):
        if self.facts_panel.running or self.samples_panel.running or self.dataset_panel.running or self.queue_panel.running or self.closure_panel.loading or self.quality_panel.loading: self.status.setText('背景來源核對尚未結束；可先取消該核對'); return
        super().reject()
    def selected_row(self):
        rows = self.table.selectionModel().selectedRows()
        return self.rows[rows[0].row()] if rows and rows[0].row() < len(self.rows) else None
    def page(self, delta):
        if delta > 0:
            self.page_history.append(self.offset); self.offset += self.advance
        else: self.offset = self.page_history.pop() if self.page_history else 0
        self.reload()
    def reload(self, *_):
        if self.loading: return
        selected = self.selected_row(); key = selected['id'] if selected else None; self.loading = True
        try:
            report = quality_rows(self.window.library, query=self.search.text(), severity=self.filter.currentData(), offset=self.offset)
            self.rows = report['issues']; self.table.setRowCount(len(self.rows))
            self.advance = report['scanned_works']
            for i, row in enumerate(self.rows):
                for j, value in enumerate((row['severity'], row['work_name'], row['code']+'／'+row['reason'], ', '.join(row['slot_ids']), row['source_id'])):
                    item = QTableWidgetItem(value); item.setData(Qt.UserRole, row['id']); item.setToolTip(value); self.table.setItem(i, j, item)
            self.table.setColumnWidth(2, 430); self.table.setColumnWidth(1, 180)
            self.count.setText(f"作品分頁 {self.offset+1}起／已掃描{report['scanned_works']}／全部{report['total_works']}；{len(self.rows)}個符合問題；原生與Logo內容UNKNOWN")
            self.previous_button.setEnabled(self.offset > 0); self.next_button.setEnabled(report['has_more'])
            for i, row in enumerate(self.rows):
                if row['id'] == key: self.table.selectRow(i); break
        except Exception as error:
            self.rows = []; self.table.setRowCount(0); self.status.setText('檢查未完成：'+str(error)); self.count.setText('未取得結果，不當PASS')
        finally: self.loading = False; self.selected()
    def selected(self):
        if self.loading: return
        row = self.selected_row(); self.details.setPlainText(json.dumps(row, ensure_ascii=False, indent=2) if row else '')
        self.locate_button.setEnabled(bool(row) and not self.window.busy); self.edit_button.setEnabled(bool(row and row['locatable']) and not self.window.busy)
    def fresh_row(self):
        row = self.selected_row()
        if not row: raise ValueError('先選取明確問題')
        current = self.window.library.artwork(row['work_id'])
        if current['revision'] != row['work_revision']: raise ValueError('作品已變更，請重新檢查')
        require_clean_navigation(self.window)
        return row
    def locate(self):
        try:
            row = self.fresh_row(); locate_work(self.window, row['work_id'], row['slot_ids'] if row['locatable'] else ())
            self.status.setText('已定位exact作品；'+('多框需既有安全編輯器同時核對' if len(row['slot_ids']) > 1 else '未改標記／未核准訓練'))
        except Exception as error: self.status.setText('未定位：'+str(error))
    def edit(self):
        try:
            row = self.fresh_row()
            if not row['locatable']: raise ValueError('重複／未知ID不能自動選取任意物件')
            from .object_dialog import ObjectToolsDialog
            dialog = ObjectToolsDialog(self.window, 'ARTWORK', row['work_id'], self)
            try: dialog.select_ids(row['slot_ids']); dialog.exec()
            finally: dialog.deleteLater()
            self.reload()
        except Exception as error: self.status.setText('未開啟：'+str(error))


def open_repair_center(window,entry):
    """Same center and repair workbench for canvas and source-only exceptions."""
    from PySide6.QtCore import QTimer
    dialog=TrainingQualityDialog(window)
    from shiboken6 import isValid
    QTimer.singleShot(0,lambda:dialog.quality_panel.open_repair(entry) if isValid(dialog) else None)
    try:dialog.exec()
    finally:dialog.deleteLater()

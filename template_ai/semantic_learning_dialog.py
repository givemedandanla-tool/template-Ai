"""Explicit local semantic training / held-out evaluation / activation GUI."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gui import MainWindow
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QTableWidget,QTableWidgetItem,QComboBox,QPushButton,QPlainTextEdit,QMessageBox,QInputDialog)
from .semantic_learning import SemanticLearning


class SemanticLearningDialog(QDialog):
    def __init__(self,window,parent=None):
        super().__init__(parent or window);self.host_window: MainWindow=window;self.service=SemanticLearning(window.library);self.plan=None;self.offset=0;self.resize(1200,800);self.setWindowTitle('本機字串語意模型：訓練／留出／獨立啟用')
        layout=QVBoxLayout(self);self.status=QLabel('未接付費API／預訓練神經模型。確認文字需另行授權本機語意訓練；模型分數非校準機率。');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.table=QTableWidget(0,3);self.table.setHorizontalHeaderLabels(['確認作品／來源','確認文字數','本次角色']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);layout.addWidget(self.table,2)
        bar=QHBoxLayout()
        for label,fn in [('上一頁',lambda:self.page(-100)),('下一頁',lambda:self.page(100)),('重新讀取',self.reload),('預檢訓練與留出',self.preview),('授權文字用途並訓練候選',self.train),('核對並啟用／回退選中版本',self.activate)]:
            button=QPushButton(label);button.clicked.connect(fn);bar.addWidget(button)
        layout.addLayout(bar);self.models=QComboBox();self.models.currentIndexChanged.connect(self.model_selected);layout.addWidget(self.models);self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details,2);self.reload()

    def guarded(self,fn):
        try:
            if self.host_window.busy:raise ValueError('背景工作中，保留目前選擇稍後再處理')
            fn()
        except Exception as error:self.status.setText('未執行：'+str(error))

    def page(self,delta):self.offset=max(0,self.offset+delta);self.reload()

    def reload(self):
        self.plan=None;self.rows=[]
        records=self.host_window.library.db.execute('SELECT id FROM artworks ORDER BY id LIMIT 100 OFFSET ?',(self.offset,)).fetchall()
        for wid, in records:
            work=self.host_window.library.artwork(wid)
            if work['payload'].get('segmentation_state')!='SUPERSEDED' and self.service.store.facts_state(wid)=='CONFIRMED':self.rows.append(work)
        self.table.setRowCount(len(self.rows))
        for i,work in enumerate(self.rows):
            facts=self.service.store.facts(work['id']);self.table.setItem(i,0,QTableWidgetItem(work['name']+'／'+work['id']+'／'+work['source_id']));self.table.setItem(i,1,QTableWidgetItem(str(len((facts['confirmation'] or {}).get('observation_ids',[])))))
            role=QComboBox()
            for label,key in [('不使用','NONE'),('訓練','TRAIN'),('留出驗證','VALIDATION')]:role.addItem(label,key)
            role.currentIndexChanged.connect(self.invalidate);self.table.setCellWidget(i,2,role)
        self.models.blockSignals(True);self.models.clear()
        for row in self.service.store.records('SEMANTIC_MODEL',0,200):self.models.addItem(row['id']+'／'+row['state']+'／參數'+str(row['parameter_count']),row['id'])
        self.models.blockSignals(False);self.status.setText(f'本頁檢查100作品，列出{len(self.rows)}已確認作品；模型列出前200版。未核准、未確認者不納入。');self.model_selected()

    def invalidate(self,*_):self.plan=None

    def preview(self):
        def action():
            roles={work['id']:self.table.cellWidget(i,2).currentData() for i,work in enumerate(self.rows) if self.table.cellWidget(i,2).currentData()!='NONE'}
            self.plan=self.service.plan(roles);self.details.setPlainText(json.dumps({k:v for k,v in self.plan.items() if k!='examples'},ensure_ascii=False,indent=2));self.status.setText('已檢查已確認文字／來源隔離／字串去洩漏；尚未授權語意用途、訓練或啟用。')
        self.guarded(action)

    def train(self):
        def action():
            if not self.plan:raise ValueError('先預檢目前明確作品及角色')
            if QMessageBox.question(self,'另行授權本機文字語意訓練',f"本次{len(self.plan['examples'])}筆文字，限SEMANTIC_CLASSIFICATION_LOCAL。\n原稿不外傳；不沿用幾何限定用途；訓練後仍待獨立啟用。\n確認所列來源、作品、TRAIN與留出角色？")!=QMessageBox.Yes:return
            row=self.service.train(self.plan,'LOCAL_OPERATOR',True);self.reload();self.models.setCurrentIndex(self.models.findData(row['id']));self.status.setText('候選模型及留出結果已保存；尚未啟用。')
        self.guarded(action)

    def model_selected(self,*_):
        row=self.service.store.get('SEMANTIC_MODEL',self.models.currentData()) if self.models.currentData() else None
        if row:self.details.setPlainText(json.dumps({k:row[k] for k in ('id','revision','state','algorithm') if k in row}|{k:row[k] for k in ('metrics','baseline_metrics','parameter_count','vocabulary_size','weights_digest','scope')},ensure_ascii=False,indent=2))

    def activate(self):
        def action():
            identity=self.models.currentData()
            if not identity:raise ValueError('先選明確模型版本')
            row,model=self.service.checked_model(identity);active=self.service.store.get('SEMANTIC_ACTIVE','local-text');reason,ok=QInputDialog.getText(self,'逐版核對／回退理由','只影響新來源候選，既有人工事實保持；請先核對各類分母與錯誤')
            if ok and QMessageBox.question(self,'獨立核准本機模型版本',identity+'\n不代表真實準確率、跨作品人名公司身分或模板發布已核准。')==QMessageBox.Yes:
                self.service.activate(identity,row['revision'],active['revision'] if active else 0,'LOCAL_OPERATOR',reason,True);self.status.setText('明確版本已啟用／回退；僅供新來源待審候選，來源／確認失效即停止使用。')
        self.guarded(action)

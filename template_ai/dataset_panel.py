"""Explicit sample roles, frozen manifest and source-verified TRAIN-only geometry action."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gui import MainWindow
import json
import copy
from PySide6.QtCore import Qt,QThreadPool
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QComboBox,QPushButton,QTableWidget,QTableWidgetItem,QPlainTextEdit,QMessageBox
from .model import new_id
from .training_store import TrainingStore
from .source_links import hash_source
from .metadata_record import training_record


class DatasetPanel(QWidget):
    def __init__(self,window,parent=None):
        super().__init__(parent);self.host_window: MainWindow=window;self.store=TrainingStore(window.library);self.rows=[];self.offset=0;self.dataset_offset=0;self.running=False;self.jobs={};layout=QVBoxLayout(self);bar=QHBoxLayout();self.name=QLineEdit();self.name.setMaxLength(120);self.name.setPlaceholderText('新資料集名稱');self.actor=QLineEdit();self.actor.setMaxLength(120);self.actor.setPlaceholderText('人工確認者');bar.addWidget(self.name);bar.addWidget(self.actor);self.reload_button=QPushButton('重载样本／資料集');self.reload_button.clicked.connect(self.reload);bar.addWidget(self.reload_button);layout.addLayout(bar);self.status=QLabel('勾選本頁exact樣本與角色；同來源整檔SHA group不能跨集合。預設UNASSIGNED不訓練；來源身份保留、近似UNKNOWN。');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['選取樣本／目前資格','角色','來源group／尺寸','work ID','sample ID']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectRows);layout.addWidget(self.table,2);bar=QHBoxLayout();self.previous_button=QPushButton('上頁樣本');self.next_button=QPushButton('下頁樣本');self.previous_button.clicked.connect(lambda:self.page(-200));self.next_button.clicked.connect(lambda:self.page(200));self.preview_button=QPushButton('角色／重複／洩漏預覽');self.create_button=QPushButton('確認建立不可變資料集');self.preview_button.clicked.connect(self.preview);self.create_button.clicked.connect(self.create)
        for b in (self.previous_button,self.next_button,self.preview_button,self.create_button):bar.addWidget(b)
        layout.addLayout(bar);bar=QHBoxLayout();self.dataset_combo=QComboBox();self.dataset_combo.currentIndexChanged.connect(self.load_dataset);bar.addWidget(self.dataset_combo,1);self.dataset_previous=QPushButton('上頁資料集');self.dataset_next=QPushButton('下頁資料集');self.dataset_previous.clicked.connect(lambda:self.dataset_page(-200));self.dataset_next.clicked.connect(lambda:self.dataset_page(200));bar.addWidget(self.dataset_previous);bar.addWidget(self.dataset_next);layout.addLayout(bar);bar=QHBoxLayout();self.sample_combo=QComboBox();bar.addWidget(self.sample_combo,1);self.template_name=QLineEdit();self.template_name.setMaxLength(120);self.template_name.setPlaceholderText('新幾何草稿模板名稱');bar.addWidget(self.template_name);self.learn_button=QPushButton('明確啟動選中TRAIN的幾何學習');self.learn_button.clicked.connect(self.learn);bar.addWidget(self.learn_button);layout.addLayout(bar);self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details,2);self.reload()
    def page(self,delta):self.offset=max(0,self.offset+delta);self.reload()
    def dataset_page(self,delta):self.dataset_offset=max(0,self.dataset_offset+delta);self.reload()
    def controls(self):
        enabled=not self.running and not self.host_window.busy
        for b in (self.preview_button,self.create_button,self.learn_button):b.setEnabled(enabled)
        self.reload_button.setEnabled(not self.running);self.dataset_combo.setEnabled(not self.running);self.sample_combo.setEnabled(not self.running)
    def reload(self):
        if self.running:return
        try:
            self.rows=self.store.records('SAMPLE',self.offset);self.table.setRowCount(len(self.rows))
            for i,row in enumerate(self.rows):
                item=QTableWidgetItem(self.store.sample_state(row['id']));item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Unchecked);self.table.setItem(i,0,item);role=QComboBox();role.addItems(['UNASSIGNED','TRAIN','VALIDATION','HOLDOUT']);self.table.setCellWidget(i,1,role)
                values=(row.get('pins',{}).get('source_hash','UNKNOWN')[:16]+' / '+str(row.get('width_mm','?'))+'×'+str(row.get('height_mm','?')),row.get('work_id','UNKNOWN'),row['id'])
                for j,v in enumerate(values,2):self.table.setItem(i,j,QTableWidgetItem(v))
            self.previous_button.setEnabled(self.offset>0);self.next_button.setEnabled(self.offset+len(self.rows)<self.store.count('SAMPLE'));selected=self.dataset_combo.currentData();datasets=self.store.records('DATASET',self.dataset_offset);self.dataset_combo.blockSignals(True);self.dataset_combo.clear()
            for ds in datasets:self.dataset_combo.addItem(ds.get('manifest',{}).get('name',ds['id'])+' / '+ds['id'],ds['id'])
            index=self.dataset_combo.findData(selected)
            if index>=0:self.dataset_combo.setCurrentIndex(index)
            self.dataset_combo.blockSignals(False);self.dataset_previous.setEnabled(self.dataset_offset>0);self.dataset_next.setEnabled(self.dataset_offset+len(datasets)<self.store.count('DATASET'));self.load_dataset()
        except Exception as error:self.dataset_combo.blockSignals(False);self.status.setText('資料集載入失敗：'+str(error))
        self.controls()
    def assignments(self):return [{'sample_id':row['id'],'role':self.table.cellWidget(i,1).currentText()} for i,row in enumerate(self.rows) if self.table.item(i,0).checkState()==Qt.Checked]
    def preview(self):
        try:plan=self.store.dataset_plan(self.name.text(),self.assignments());self.details.setPlainText(json.dumps(plan,ensure_ascii=False,indent=2));self.status.setText('完整manifest可確認，尚未學習' if not plan['errors'] else '阻擋：'+'；'.join(plan['errors']))
        except Exception as error:self.status.setText('未預覽：'+str(error))
    def create(self):
        try:
            plan=self.store.dataset_plan(self.name.text(),self.assignments());self.details.setPlainText(json.dumps(plan,ensure_ascii=False,indent=2))
            if QMessageBox.question(self,'確認資料集角色與來源group',f"{plan['manifest']['name']}／{len(plan['manifest']['entries'])}樣本\nmanifest SHA {plan['manifest_digest']}\n整檔group分離，不合併來源或客戶身份。建立後不可改manifest，不啟動學習。",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            ds=self.store.create_dataset(plan,self.actor.text(),True);self.reload();self.dataset_combo.setCurrentIndex(self.dataset_combo.findData(ds['id']));self.status.setText('已建立FROZEN '+ds['id']+'；未訓練')
        except Exception as error:self.status.setText('未建立資料集：'+str(error));self.controls()
    def load_dataset(self,*_):
        if self.running:return
        self.sample_combo.clear();did=self.dataset_combo.currentData()
        if not did:return
        ds=self.store.get('DATASET',did)
        for entry in ds.get('entries',[]):self.sample_combo.addItem(entry['role']+' / '+entry['sample_id'],entry['sample_id'])
        uses=[training_record(row) for row in self.store.db.execute("SELECT id,revision,payload FROM training_records WHERE kind='USE' AND json_extract(payload,'$.dataset_id')=? ORDER BY id LIMIT 200",(did,))];total=self.store.db.execute("SELECT count(*) FROM training_records WHERE kind='USE' AND json_extract(payload,'$.dataset_id')=?",(did,)).fetchone()[0]
        self.details.setPlainText(json.dumps({'dataset':ds,'current_validity':self.store.dataset_validity(did),'actual_geometry_uses':uses,'total_geometry_uses':total,'uses_display_bounded':len(uses)<total},ensure_ascii=False,indent=2))
    def learn(self):
        if self.running or self.host_window.busy:return
        try:
            from .training_store import text
            actor=text(self.actor.text(),'啟動者',120);plan=self.store.geometry_learning_plan(self.dataset_combo.currentData(),self.sample_combo.currentData(),self.template_name.text());sample=self.store.get('SAMPLE',plan['entry']['sample_id']);source=copy.deepcopy(self.store.library.source(sample['pins']['source_id']))
        except Exception as error:self.status.setText('未啟動：'+str(error));return
        self.running=True;self.controls();self.status.setText('背景驗證選中來源，尚未生成模板')
        from .gui import Job
        job=Job(lambda:hash_source(source['current_path'],byte_limit=50_000_000));token=new_id();self.jobs[token]=job;job.signals.setParent(self)
        def release():self.running=False;self.jobs.pop(token,None);job.signals.deleteLater();self.controls()
        def failed(error):self.status.setText('來源核對失敗：'+str(error));release()
        def done(proof):
            try:
                self.details.setPlainText(json.dumps(plan,ensure_ascii=False,indent=2))
                if QMessageBox.question(self,'明確啟動本機幾何學習',f"資料集{plan['dataset_id']}／TRAIN樣本{plan['entry']['sample_id']} r{plan['sample_revision']}\n範圍SHA {plan['digest']}\n只從人工標記建立新DRAFT幾何模板，保留原作品与發布版，不是神經模型或自動發布。",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:self.status.setText('已取消，未學習');return
                template=self.store.learn_dataset_sample(plan,proof,actor,True);self.host_window.refresh_templates(preserve_editor=True);self.status.setText('已生成DRAFT '+template.id+'；dataset／sample來源與USE已保存；目前人工編輯保持');self.last_template=template
            except Exception as error:self.status.setText('學習未完成：'+str(error))
            finally:release()
        job.signals.done.connect(done,Qt.QueuedConnection);job.signals.error.connect(failed,Qt.QueuedConnection);QThreadPool.globalInstance().start(job)

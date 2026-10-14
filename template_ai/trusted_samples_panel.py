"""Candidate works and admitted samples stay separate; human confirmation never starts training."""
import copy
import json
from PySide6.QtCore import Qt,QThreadPool
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QComboBox,QLineEdit,QPushButton,QTableWidget,QTableWidgetItem,QPlainTextEdit,QMessageBox
from .model import new_id
from .training_store import TrainingStore
from .source_links import hash_source
from .batch_import import healthy_source


class TrustedSamplesPanel(QWidget):
    def __init__(self,window,parent=None):
        super().__init__(parent);self.window=window;self.store=TrainingStore(window.library);self.running=False;self.jobs={};self.offset=0;self.rows=[];self.work_offset=0;self.binding_widgets={};layout=QVBoxLayout(self);bar=QHBoxLayout();self.work_combo=QComboBox();self.work_combo.currentIndexChanged.connect(self.load_work);bar.addWidget(self.work_combo,1);self.reload_button=QPushButton('重載候選／樣本');self.reload_button.clicked.connect(self.reload);bar.addWidget(self.reload_button);self.work_previous=QPushButton('上頁作品');self.work_next=QPushButton('下頁作品');self.work_previous.clicked.connect(lambda:self.work_page(-200));self.work_next.clicked.connect(lambda:self.work_page(200));bar.addWidget(self.work_previous);bar.addWidget(self.work_next);layout.addLayout(bar)
        self.status=QLabel('作品是候選；只有明確准入且目前有效的樣本可供後續本機幾何學習。不自動訓練。');self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);layout.addWidget(self.status);form=QFormLayout();self.basis=QComboBox();self.basis.addItems(['未提供','OWNED','AUTHORIZED','OPEN_LICENSE']);form.addRow('來源權利依據',self.basis);self.reference=QLineEdit();self.reference.setMaxLength(512);self.reference.setPlaceholderText('本機許可／權利參考，不會上傳');form.addRow('可核對權利參考',self.reference);self.actor=QLineEdit();self.actor.setMaxLength(120);form.addRow('人工准入確認者',self.actor);layout.addLayout(form);self.binding_form=QFormLayout();layout.addLayout(self.binding_form)
        bar=QHBoxLayout();self.preview_button=QPushButton('准入條件／正負例預覽');self.preview_button.clicked.connect(self.preview);self.admit_button=QPushButton('明確准入選中作品（不啟動訓練）');self.admit_button.clicked.connect(self.admit);bar.addWidget(self.preview_button);bar.addWidget(self.admit_button);layout.addLayout(bar)
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['目前資格','保存狀態／版次','作品ID','用途／來源SHA','樣本ID']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.SingleSelection);self.table.itemSelectionChanged.connect(self.selected);layout.addWidget(self.table,2);self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details,2)
        bar=QHBoxLayout();self.previous_button=QPushButton('上一頁樣本');self.next_button=QPushButton('下一頁樣本');self.previous_button.clicked.connect(lambda:self.page(-200));self.next_button.clicked.connect(lambda:self.page(200));self.quarantine_button=QPushButton('隔離選中樣本');self.revoke_button=QPushButton('撤銷選中樣本准入');self.quarantine_button.clicked.connect(lambda:self.transition('QUARANTINE'));self.revoke_button.clicked.connect(lambda:self.transition('REVOKE'));bar.addWidget(self.previous_button);bar.addWidget(self.next_button);bar.addWidget(self.quarantine_button);bar.addWidget(self.revoke_button);layout.addLayout(bar);self.reason=QLineEdit();self.reason.setMaxLength(512);self.reason.setPlaceholderText('隔離／撤銷原因');layout.addWidget(self.reason);self.reload()
    def work_page(self,delta):self.work_offset=max(0,self.work_offset+delta);self.reload()
    def page(self,delta):self.offset=max(0,self.offset+delta);self.reload()
    def rights(self):return {'basis':self.basis.currentText(),'reference':self.reference.text(),'use':'GEOMETRY_TRAINING_LOCAL'}
    def bindings(self):return {p:combo.currentData() for p,combo in self.binding_widgets.items() if combo.currentData() is not None}
    def load_work(self,*_):
        self.binding_widgets={}
        while self.binding_form.rowCount():self.binding_form.removeRow(0)
        wid=self.work_combo.currentData()
        if not wid:return
        slots=self.store.library.artwork(wid)['payload']['slots'];people=sorted({s.get('owner') for s in slots if str(s.get('owner','')).startswith('p')});companies=sorted({s.get('owner') for s in slots if str(s.get('owner','')).startswith('c')})
        if companies:
            for person in people:
                combo=QComboBox();combo.addItem('未確認公司歸屬',None)
                for company in companies:combo.addItem(company,company)
                self.binding_form.addRow(person+'公司',combo);self.binding_widgets[person]=combo
    def reload(self):
        if self.running:return
        try:
            wid=self.work_combo.currentData();self.work_combo.blockSignals(True);self.work_combo.clear()
            works=list(self.store.db.execute('SELECT id,name FROM artworks ORDER BY id LIMIT 200 OFFSET ?',(self.work_offset,)))
            for key,name in works:self.work_combo.addItem(name+' / '+key,key)
            index=self.work_combo.findData(wid)
            if index>=0:self.work_combo.setCurrentIndex(index)
            self.work_combo.blockSignals(False);self.load_work();total=self.store.db.execute('SELECT count(*) FROM artworks').fetchone()[0];self.work_previous.setEnabled(self.work_offset>0);self.work_next.setEnabled(self.work_offset+len(works)<total)
            self.rows=self.store.records('SAMPLE',self.offset);self.table.setRowCount(len(self.rows))
            for i,row in enumerate(self.rows):
                values=(self.store.sample_state(row['id']),row.get('state','UNKNOWN')+' / r'+str(row['revision']),row.get('work_id','UNKNOWN'),row.get('rights',{}).get('use','UNKNOWN')+' / '+row.get('pins',{}).get('source_hash','UNKNOWN')[:12],row['id'])
                for j,v in enumerate(values):self.table.setItem(i,j,QTableWidgetItem(v))
            self.previous_button.setEnabled(self.offset>0);self.next_button.setEnabled(self.offset+len(self.rows)<self.store.count('SAMPLE'))
        except Exception as error:self.work_combo.blockSignals(False);self.rows=[];self.table.setRowCount(0);self.status.setText('載入失敗：'+str(error))
        self.controls()
    def selected_row(self):
        rows=self.table.selectionModel().selectedRows();return self.rows[rows[0].row()] if rows and rows[0].row()<len(self.rows) else None
    def selected(self):
        row=self.selected_row();self.details.setPlainText(json.dumps({'sample':row,'effective_state':self.store.sample_state(row['id']),'usage_impact':self.store.sample_usage_impact(row['id']),'history':self.store.history('SAMPLE',row['id'])},ensure_ascii=False,indent=2) if row else '');self.controls()
    def controls(self):
        enabled=not self.running and not self.window.busy;self.reload_button.setEnabled(not self.running);self.work_combo.setEnabled(not self.running);self.preview_button.setEnabled(enabled and bool(self.work_combo.currentData()));self.admit_button.setEnabled(enabled and bool(self.work_combo.currentData()));self.quarantine_button.setEnabled(enabled and bool(self.selected_row()));self.revoke_button.setEnabled(enabled and bool(self.selected_row()))
    def preview(self):
        try:plan=self.store.sample_approval_plan(self.work_combo.currentData(),self.rights(),self.bindings());self.details.setPlainText(json.dumps(plan,ensure_ascii=False,indent=2));self.status.setText('可進行來源健康核對' if not plan['errors'] else '待補：'+'；'.join(plan['errors']))
        except Exception as error:self.status.setText('預覽未完成：'+str(error))
    def admit(self):
        if self.running or self.window.busy:return
        try:
            from .training_store import text
            actor=text(self.actor.text(),'確認者',120);plan=self.store.sample_approval_plan(self.work_combo.currentData(),self.rights(),self.bindings())
            if plan['errors']:raise ValueError('；'.join(plan['errors']))
            source=copy.deepcopy(self.store.library.source(plan['pins']['source_id']))
        except Exception as error:self.status.setText('未准入：'+str(error));return
        self.running=True;self.controls();self.status.setText('背景核對原稿／分析快取，未准入／未訓練')
        from .gui import Job
        def verify():
            proof=hash_source(source['current_path'],byte_limit=50_000_000)
            if not healthy_source(source):raise ValueError('來源或分析快取不健康')
            return proof
        job=Job(verify);token=new_id();self.jobs[token]=job;job.signals.setParent(self)
        def release():self.running=False;self.jobs.pop(token,None);job.signals.deleteLater();self.controls()
        def failed(error):self.status.setText('健康核對失敗：'+str(error));release()
        def done(proof):
            try:
                self.details.setPlainText(json.dumps(plan,ensure_ascii=False,indent=2))
                if QMessageBox.question(self,'確認只准入可信樣本',f"作品{plan['work_id']}／當前work r{plan['pins']['work_revision']}／facts r{plan['facts_revision']}\n來源SHA {plan['pins']['source_hash']}\n准入範圍SHA {plan['digest']}\n權利{plan['rights']['basis']}，用途僅本機幾何學習。正例與原錯誤預測分開。准入不會自動訓練、發布模板。",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:self.status.setText('已取消，沒有准入');return
                sample=self.store.approve_sample(plan,proof,actor,True);self.running=False;self.reload();self.status.setText('已准入 '+sample['id']+'；尚未訓練')
            except Exception as error:self.status.setText('未准入：'+str(error))
            finally:release()
        job.signals.done.connect(done,Qt.QueuedConnection);job.signals.error.connect(failed,Qt.QueuedConnection);QThreadPool.globalInstance().start(job)
    def transition(self,action):
        try:
            row=self.selected_row()
            if not row or self.running or self.window.busy:raise ValueError('先選中exact樣本並結束背景工作')
            plan=self.store.sample_transition_plan(row['id'],action);self.details.setPlainText(json.dumps(plan,ensure_ascii=False,indent=2))
            if QMessageBox.question(self,'確認樣本隔離／撤銷',self.details.toPlainText(),QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            self.store.transition_sample(plan,self.actor.text(),self.reason.text(),True);self.reload();self.status.setText('已'+action+'；歷史與發布模板保留，沒有宣稱模型已解污染')
        except Exception as error:self.status.setText('未隔離／撤銷：'+str(error));self.controls()

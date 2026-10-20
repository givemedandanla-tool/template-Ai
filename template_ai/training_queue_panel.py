"""One persistent queue UI, current progress, cooperative cancellation and explicit resume."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gui import MainWindow
import json
import threading
from PySide6.QtCore import Qt,QObject,Signal,QRunnable,QThreadPool
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLineEdit,QComboBox,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QPlainTextEdit,QCheckBox,QMessageBox
from .training_store import TrainingStore
from .training_pipeline import run_training_job


class QueueSignals(QObject):
    progress=Signal(object);done=Signal(object);error=Signal(str)


class QueueTask(QRunnable):
    def __init__(self,root,job_id,token,cancel,admission=None):
        super().__init__();self.root=root;self.job_id=job_id;self.token=token;self.cancel=cancel;self.admission=admission;self.signals=QueueSignals()
    def run(self):
        try:self.signals.done.emit(run_training_job(self.root,self.job_id,self.token,self.cancel,self.signals.progress.emit,admission=self.admission))
        except BaseException as error:self.signals.error.emit(str(error))


class TrainingQueuePanel(QWidget):
    def __init__(self,window,parent=None):
        super().__init__(parent);self.host_window: MainWindow=window;self.store=TrainingStore(window.library);self.running=False;self.task=None;self.cancel_event=None;self.token=None;self.current_job=None;self.rows=[];self.offset=0;self.dataset_offset=0;layout=QVBoxLayout(self);bar=QHBoxLayout();self.dataset_combo=QComboBox();self.dataset_combo.currentIndexChanged.connect(self.load_dataset);bar.addWidget(self.dataset_combo,1);self.reload_button=QPushButton('重載持久工作／資料集');self.reload_button.clicked.connect(self.reload);bar.addWidget(self.reload_button);self.dataset_previous=QPushButton('上頁資料集');self.dataset_next=QPushButton('下頁資料集');self.dataset_previous.clicked.connect(lambda:self.dataset_page(-200));self.dataset_next.clicked.connect(lambda:self.dataset_page(200));bar.addWidget(self.dataset_previous);bar.addWidget(self.dataset_next);layout.addLayout(bar);bar=QHBoxLayout();self.prefix=QLineEdit();self.prefix.setMaxLength(100);self.prefix.setPlaceholderText('新幾何草稿名稱前綴');self.actor=QLineEdit();self.actor.setMaxLength(120);self.actor.setPlaceholderText('啟動者');bar.addWidget(self.prefix);bar.addWidget(self.actor);self.retry_failed=QCheckBox('續跑時明確重試FAILED（SUCCESS不重跑）');bar.addWidget(self.retry_failed);layout.addLayout(bar)
        self.status=QLabel('只處理exact有效TRAIN，幾何DRAFT而非深度模型；source／sample／rule／用途每項再驗。單worker，不發布。');self.status.setWordWrap(True);layout.addWidget(self.status);self.progress_label=QLabel();layout.addWidget(self.progress_label);self.items=QTableWidget(0,3);self.items.setHorizontalHeaderLabels(['明列選取／角色','sample ID／版次','source hash／group']);self.items.setEditTriggers(QTableWidget.NoEditTriggers);layout.addWidget(self.items,1);bar=QHBoxLayout();self.preview_button=QPushButton('預檢明列範圍');self.create_button=QPushButton('確認建立並啟動持久工作');self.preview_button.clicked.connect(self.preview);self.create_button.clicked.connect(self.create_start);bar.addWidget(self.preview_button);bar.addWidget(self.create_button);layout.addLayout(bar)
        self.jobs_table=QTableWidget(0,4);self.jobs_table.setHorizontalHeaderLabels(['目前phase／保存版次','SUCCESS／REUSED／FAILED／待處理','dataset ID','job ID']);self.jobs_table.setEditTriggers(QTableWidget.NoEditTriggers);self.jobs_table.setSelectionBehavior(QTableWidget.SelectRows);self.jobs_table.setSelectionMode(QTableWidget.SingleSelection);self.jobs_table.itemSelectionChanged.connect(self.selected);layout.addWidget(self.jobs_table,1);self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details,2);bar=QHBoxLayout();self.previous_button=QPushButton('上頁工作');self.next_button=QPushButton('下頁工作');self.previous_button.clicked.connect(lambda:self.page(-200));self.next_button.clicked.connect(lambda:self.page(200));self.resume_button=QPushButton('明確啟動／中斷續跑選中工作');self.cancel_button=QPushButton('合作取消目前工作');self.resume_button.clicked.connect(self.start_selected);self.cancel_button.clicked.connect(self.cancel)
        for b in (self.previous_button,self.next_button,self.resume_button,self.cancel_button):bar.addWidget(b)
        layout.addLayout(bar);self.reload();self.request_id=None
        dispatcher=getattr(window,'execution_queue',None)
        if dispatcher:dispatcher.progress.connect(self.queued_progress);dispatcher.finished.connect(self.queued_finished)
    def dataset_page(self,delta):self.dataset_offset=max(0,self.dataset_offset+delta);self.reload()
    def page(self,delta):self.offset=max(0,self.offset+delta);self.reload()
    def controls(self):
        for b in (self.preview_button,self.create_button,self.resume_button,self.reload_button):b.setEnabled(not self.running and not self.host_window.busy)
        self.cancel_button.setEnabled(self.running);self.dataset_combo.setEnabled(not self.running);self.retry_failed.setEnabled(not self.running)
    def reload(self):
        if self.running:return
        try:
            key=self.dataset_combo.currentData();datasets=self.store.records('DATASET',self.dataset_offset);self.dataset_combo.blockSignals(True);self.dataset_combo.clear()
            for ds in datasets:self.dataset_combo.addItem(ds.get('manifest',{}).get('name',ds['id'])+' / '+ds['id'],ds['id'])
            index=self.dataset_combo.findData(key)
            if index>=0:self.dataset_combo.setCurrentIndex(index)
            self.dataset_combo.blockSignals(False);self.dataset_previous.setEnabled(self.dataset_offset>0);self.dataset_next.setEnabled(self.dataset_offset+len(datasets)<self.store.count('DATASET'));self.load_dataset();self.rows=self.store.records('JOB',self.offset);self.jobs_table.setRowCount(len(self.rows))
            for i,job in enumerate(self.rows):
                states=[r.get('state') for r in job.get('items',[])];values=(self.store.training_job_state(job['id'])+' / r'+str(job['revision']),f"{states.count('SUCCESS')}／{states.count('REUSED')}／{states.count('FAILED')}／{states.count('READY')}",job.get('dataset_id','UNKNOWN'),job['id'])
                for j,v in enumerate(values):self.jobs_table.setItem(i,j,QTableWidgetItem(v))
            self.previous_button.setEnabled(self.offset>0);self.next_button.setEnabled(self.offset+len(self.rows)<self.store.count('JOB'))
        except Exception as error:self.dataset_combo.blockSignals(False);self.status.setText('工作讀取未完成：'+str(error))
        self.controls()
    def load_dataset(self,*_):
        if self.running:return
        ds=self.store.get('DATASET',self.dataset_combo.currentData()) if self.dataset_combo.currentData() else None;entries=ds.get('entries',[]) if ds else [];self.items.setRowCount(len(entries))
        for i,entry in enumerate(entries):
            item=QTableWidgetItem(entry.get('role','UNKNOWN'));item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Unchecked);self.items.setItem(i,0,item);self.items.setItem(i,1,QTableWidgetItem(entry['sample_id']+' / r'+str(entry.get('sample_revision','?'))));self.items.setItem(i,2,QTableWidgetItem(entry.get('source_hash','UNKNOWN')[:20]))
        self.entries=entries
    def ids(self):return [e['sample_id'] for i,e in enumerate(self.entries) if self.items.item(i,0).checkState()==Qt.Checked]
    def selected_job(self):
        selected=self.jobs_table.selectionModel().selectedRows();return self.rows[selected[0].row()] if selected and selected[0].row()<len(self.rows) else None
    def selected(self):
        job=self.selected_job()
        if job and not self.running:self.details.setPlainText(json.dumps({'stored':job,'current_phase':self.store.training_job_state(job['id']),'history':self.store.history('JOB',job['id'])},ensure_ascii=False,indent=2))
        self.controls()
    def preview(self):
        try:plan=self.store.training_job_plan(self.dataset_combo.currentData(),self.ids(),self.prefix.text());self.details.setPlainText(json.dumps(plan,ensure_ascii=False,indent=2));self.status.setText('預檢已完成；尚未訓練')
        except Exception as error:self.status.setText('預檢阻擋：'+str(error))
    def create_start(self):
        try:
            plan=self.store.training_job_plan(self.dataset_combo.currentData(),self.ids(),self.prefix.text());self.details.setPlainText(json.dumps(plan,ensure_ascii=False,indent=2))
            if QMessageBox.question(self,'確認exact持久訓練工作',self.details.toPlainText()+'\n只新增幾何DRAFT／或復用已知成果，不改原稿或發布版。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            job=self.store.create_training_job(plan,self.actor.text(),True);self.reload();self.start(job,True)
        except Exception as error:self.status.setText('未建立／啟動：'+str(error));self.controls()
    def start_selected(self):
        job=self.selected_job()
        if not job:self.status.setText('先選中exact持久工作');return
        self.start(self.store.get('JOB',job['id']),False)
    def start(self,job,already_confirmed=False):
        if self.running:return
        try:
            if not already_confirmed and QMessageBox.question(self,'明確啟動／續跑',json.dumps(job,ensure_ascii=False,indent=2)+'\nSUCCESS／REUSED不重跑；FAILED僅在勾選後重試。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            dispatcher=getattr(self.host_window,'execution_queue',None)
            if dispatcher:
                request=dispatcher.submit('JOB',job,self.actor.text() or job['actor'],self.retry_failed.isChecked());self.request_id=request['id'];self.current_job=job['id'];self.running=request['state'] not in ('DONE','BLOCKED','CANCELLED');self.cancel_event=dispatcher.cancel_event;self.status.setText('已保存先進先出執行請求；等待資源或目前工作完成，不代表已訓練。');self.controls();return
            supervisor=getattr(self.host_window,'runtime',None)
            if supervisor:
                decision=supervisor.admit('GEOMETRY',requested=True)
                if not decision.allowed:self.status.setText('未取得工作；等待背景資源：'+','.join(decision.reasons));return
            claimed=self.store.claim_training_job(job['id'],job['revision'],True,self.retry_failed.isChecked());self.current_job=claimed['id'];self.token=claimed['owner']['token'];self.running=True;self.host_window.busy=True;self.host_window.import_button.setEnabled(False);self.cancel_event=threading.Event();self.task=QueueTask(self.store.library.root,claimed['id'],self.token,self.cancel_event,(lambda:supervisor.admit('GEOMETRY')) if supervisor else None);self.task.signals.setParent(self);self.task.signals.progress.connect(self.progress,Qt.QueuedConnection);self.task.signals.done.connect(self.done,Qt.QueuedConnection);self.task.signals.error.connect(self.failed,Qt.QueuedConnection);self.controls();self.progress(claimed);QThreadPool.globalInstance().start(self.task)
        except Exception as error:self.status.setText('啟動／續跑阻擋：'+str(error));self.controls()
    def progress(self,job):
        states=[i['state'] for i in job['items']];self.progress_label.setText(f"{job['phase']}／實際SUCCESS{states.count('SUCCESS')}／REUSED{states.count('REUSED')}／FAILED{states.count('FAILED')}／READY{states.count('READY')}／全部{len(states)}／保存r{job['revision']}");self.details.setPlainText(json.dumps(job,ensure_ascii=False,indent=2))
    def queued_progress(self,identity,job):
        if identity!=self.request_id:return
        self.running=True;self.token=job['owner']['token'];self.progress(job);self.controls()
    def queued_finished(self,identity,job):
        if identity!=self.request_id:return
        self.running=False
        if 'items' in job:self.progress(job)
        self.status.setText('worker已停止／持久狀態：'+job['phase']+'；成果只為幾何DRAFT，未發布');self.reload();self.controls()
    def release(self):
        from .training_pipeline import LIVE_OWNERS
        LIVE_OWNERS.discard(self.token)
        self.running=False;self.host_window.busy=False;self.host_window.import_button.setEnabled(True);task=self.task;self.task=None
        if task:task.signals.deleteLater()
        self.host_window.refresh_templates(preserve_editor=True);self.reload();self.controls()
    def done(self,job):self.progress(job);self.status.setText('工作已保存 '+job['phase']+'；成果只為幾何DRAFT，未發布');self.release()
    def failed(self,error):self.status.setText('worker已停止：'+error+'；依持久結果／INTERRUPTED明確恢復，不宣稱成功');self.release()
    def cancel(self):
        if not self.running:return
        if self.request_id:
            try:self.host_window.execution_queue.cancel(self.request_id);self.status.setText('已請求安全取消／取消尚未啟動的執行請求')
            except Exception as error:self.status.setText('取消未保存：'+str(error))
            return
        self.cancel_event.set()
        try:self.store.request_training_cancel(self.current_job,self.token);self.status.setText('已請求合作取消：目前項可能完成且已原子保存，下一項前停止')
        except Exception as error:self.status.setText('本機取消已請求，持久請求失敗：'+str(error))

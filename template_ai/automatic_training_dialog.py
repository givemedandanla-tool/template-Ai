"""One preflight/start action with persistent, independently reviewed work units."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gui import MainWindow
import threading
from copy import deepcopy
from pathlib import Path
from PySide6.QtCore import QObject,Signal,Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QComboBox,QTableWidget,QTableWidgetItem,QPlainTextEdit,QFileDialog,QMessageBox,QLineEdit,QCheckBox)
from .automatic_training import AutomaticTraining,run_automatic
from .training_pipeline import LIVE_OWNERS


class Progress(QObject):
    updated=Signal(object)
    scanned=Signal(object)


class AutomaticTrainingDialog(QDialog):
    job_created=Signal(object)
    def __init__(self,window):
        super().__init__(window);self.host_window: MainWindow=window;self.service=AutomaticTraining(window.library)
        self.report=None;self.running=False;self.job_offset=0;self.cancel_event=threading.Event();self.progress_signal=Progress(self)
        self.progress_signal.updated.connect(self.render,Qt.QueuedConnection)
        self.progress_signal.scanned.connect(self.scan_progress,Qt.QueuedConnection)
        self.setWindowTitle('預檢後一鍵自動訓練／來源與作品持久進度');self.resize(1150,760)
        layout=QVBoxLayout(self);self.status=QLabel('一次核對後自動分析；未確認的作品／標記留待審，正式規則與模板仍需獨立核准。');self.status.setWordWrap(True);layout.addWidget(self.status)
        bar=QHBoxLayout();self.button(bar,'選多個來源檔',self.pick_files);self.button(bar,'選來源資料夾',self.pick_folder)
        self.actor=QLineEdit('LOCAL_OPERATOR');self.actor.setMaxLength(120);bar.addWidget(self.actor)
        self.start_button=self.button(bar,'確認預檢並開始訓練',self.start);self.start_button.setEnabled(False);layout.addLayout(bar)
        self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(['來源檔','頁次','實際狀態','已分析作品','重用作品','問題／待核對']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectRows);layout.addWidget(self.table,2)
        for column,width in enumerate((180,65,245,100,100,420)):self.table.setColumnWidth(column,width)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details,1)
        bar=QHBoxLayout();self.jobs=QComboBox();bar.addWidget(self.jobs,1);self.retry=QCheckBox('明確重試失敗項');bar.addWidget(self.retry)
        self.button(bar,'上一頁工作',lambda:self.job_page(-200));self.button(bar,'下一頁工作',lambda:self.job_page(200));self.button(bar,'讀回持久工作',self.reload);self.resume_button=self.button(bar,'繼續選定工作',self.resume)
        self.cancel_button=self.button(bar,'安全取消',self.cancel);self.cancel_button.setEnabled(False)
        self.button(bar,'開啟作品例外／品質中心',window.training_center);layout.addLayout(bar);self.reload();self.request_id=None
        dispatcher=getattr(window,'execution_queue',None)
        if dispatcher:dispatcher.progress.connect(self.queued_progress);dispatcher.finished.connect(self.queued_finished)

    def button(self,bar,label,fn):
        button=QPushButton(label);button.clicked.connect(fn);bar.addWidget(button);return button

    def pick_files(self):
        if self.running or self.host_window.busy:return
        paths,_=QFileDialog.getOpenFileNames(self,'選來源檔','','設計來源 (*.ai *.eps *.pdf *.svg *.png *.jpg *.jpeg)')
        if paths:self.preflight(paths)

    def pick_folder(self):
        if self.running or self.host_window.busy:return
        path=QFileDialog.getExistingDirectory(self,'選來源資料夾')
        if path:self.preflight([path])

    def preflight(self,paths,expected_hashes=None):
        if self.running or self.host_window.busy:return
        self.request_id=None
        root=self.host_window.library.root;self.start_button.setEnabled(False);self.report=None;self.running=True;self.cancel_event.clear();self.cancel_button.setEnabled(True);self.table.setRowCount(0);self.status.setText('掃描來源中，取消在目前檔案步驟完成後生效')
        def worker():
            from .storage import Library
            library=None
            try:
                library=Library(root);report=AutomaticTraining(library).preflight(paths,cancel=self.cancel_event,progress=self.progress_signal.scanned.emit)
                if expected_hashes is not None and any(expected_hashes.get(i['path'])!=i.get('expected_hash') for i in report['items']):raise ValueError('SOURCE_CHANGED：監看候選來源／清單已變更，請返回重新掃描核對')
                return dict(report=report)
            except Exception as error:
                from .source_links import ScanCancelled
                return dict(error='使用者已取消預檢；未建立學習工作' if isinstance(error,ScanCancelled) else str(error))
            finally:
                if library:library.close()
        def finished(result):
            self.running=False;self.cancel_button.setEnabled(False)
            if result.get('error'):self.status.setText('預檢未完成：'+result['error']);return
            self.report=result['report'];self.start_button.setEnabled(any(i['status'] in ('READY','SKIPPED') for i in self.report['items']));self.render(dict(items=self.report['items'],phase='PREFLIGHT'));self.status.setText(f"預檢完成：{len(self.report['items'])}來源，失敗{sum(i['status']=='FAILED' for i in self.report['items'])}；開始仍需明確確認，近似僅候選。")
            import json
            r=self.report
            self.details.setPlainText(f"檔案位元重複{r['file_duplicates']}；健康快取可重用{r['reuse_candidates']}；近似檔案候選{r['near_file_candidates']}；作品重複候選{r['artwork_duplicates']}；模板結構相似{r['template_similarity']}；未核實{r['similarity_unknown']}。\n近似不等於相同；不刪除來源或合併客戶。\n"+json.dumps(r['similarity'],ensure_ascii=False,indent=2))
        try:self.host_window.run_job('掃描及來源預檢',worker,finished,on_error=self.job_error,cancel=self.cancel_event)
        except Exception as error:self.running=False;self.cancel_button.setEnabled(False);self.status.setText('預檢無法啟動：'+str(error))

    def scan_progress(self,progress):
        self.status.setText(f"{progress['stage']}：已完成{progress['done']}／{progress['total']}檔；{Path(progress['path']).name}；尚未開始學習或發布")

    def job_page(self,delta):
        if self.running:return
        count=self.service.store.count('AUTO_JOB');self.job_offset=max(0,min(max(0,((count-1)//200)*200),self.job_offset+delta));self.reload()

    def reload(self):
        if self.running:return
        identity=self.jobs.currentData();self.jobs.clear()
        for job in self.service.store.records('AUTO_JOB',offset=self.job_offset):self.jobs.addItem(self.service.phase(job)+'／'+job['id'],job['id'])
        index=self.jobs.findData(identity)
        if index>=0:self.jobs.setCurrentIndex(index)

    def focus_job(self,identity):
        if self.running:
            self.status.setText('已有工作進行中；請先安全暫停，再切換其他工作。')
            return False
        job=self.service.get(identity)
        self.reload()
        index=self.jobs.findData(identity)
        if index<0:
            self.jobs.insertItem(0,self.service.phase(job)+'／'+job['id'],job['id'])
            index=0
        self.jobs.setCurrentIndex(index)
        self.report=None;self.start_button.setEnabled(False)
        self.render(job)
        self.details.setPlainText('已讀回既有工作 '+job['id']+'。如需接續，請選「繼續選定工作」；這次讀取沒有開始訓練。')
        return True

    def render(self,job):
        items=job['items'];self.table.setRowCount(len(items))
        for row,item in enumerate(items):
            state=item.get('state',item.get('status','UNKNOWN'));label={'READY':'待啟動核對','SKIPPED':'共用解析，保留獨立來源','RUNNING':'處理中','SUCCESS':'此來源階段已完成','WAITING_REVIEW':'待必要審核','FAILED':'失敗待處理','CANCELLED':'已安全取消'}.get(state,state)
            reason=('同位元內容，啟動後仍各自保留來源登錄／檔名，客戶歸屬待核對' if job['phase']=='PREFLIGHT' and state=='SKIPPED' else None)
            values=(Path(item['path']).name,str(item['page']),label,str(item.get('analysed_units','尚未分析')),str(item.get('reused_units','尚未分析')),reason or item.get('error') or item.get('reason') or ('作品資料待核對' if item.get('state')=='WAITING_REVIEW' else ''))
            for col,value in enumerate(values):
                cell=QTableWidgetItem(value);cell.setToolTip(item['path'] if col==0 else value);self.table.setItem(row,col,cell)
        if job['phase']!='PREFLIGHT':self.status.setText(job['phase']+f"；來源{len(items)}，成功{sum(i.get('state')=='SUCCESS' for i in items)}，待核對{sum(i.get('state')=='WAITING_REVIEW' for i in items)}，失敗{sum(i.get('state')=='FAILED' for i in items)}。未自動發布。")

    def start(self):
        if not self.report or self.running or self.host_window.busy:return
        try:
            if QMessageBox.question(self,'確認預檢並一鍵開始',f"來源{len(self.report['items'])}，位元重複{self.report['file_duplicates']}。\n自動作品候選、標記、品質與已授權幾何學習；不核准新事實、不建立真實客戶、不發布。")==QMessageBox.Yes:self.prepare_job()
        except Exception as error:self.status.setText('未開始：'+str(error))

    def prepare_job(self):
        self.request_id=None
        root=self.host_window.library.root;report=deepcopy(self.report);actor=self.actor.text();self.running=True;self.cancel_event.clear();self.cancel_button.setEnabled(True);self.start_button.setEnabled(False)
        def worker():
            from .storage import Library
            from .source_links import ScanCancelled
            library=None
            try:
                library=Library(root);job=AutomaticTraining(library).create(report,actor,True,cancel=self.cancel_event);return dict(job_id=job['id'])
            except Exception as error:return dict(error='已取消啟動核對；未假稱已訓練' if isinstance(error,ScanCancelled) else str(error))
            finally:
                if library:library.close()
        def finished(result):
            self.running=False;self.cancel_button.setEnabled(False)
            if result.get('error'):self.status.setText('未開始：'+result['error']);self.start_button.setEnabled(self.report is not None);return
            self.job_created.emit(self.service.get(result['job_id']))
            if self.cancel_event.is_set():self.status.setText('啟動已取消；已保存READY工作未執行，可稍後明確續跑');self.reload();self.start_button.setEnabled(self.report is not None);return
            self.start_job(self.service.get(result['job_id']))
        try:self.host_window.run_job('背景核對完整來源／頁次清單',worker,finished,on_error=self.job_error,cancel=self.cancel_event)
        except Exception as error:self.running=False;self.cancel_button.setEnabled(False);self.start_button.setEnabled(True);self.status.setText('未開始：'+str(error))

    def resume(self):
        if self.running or self.host_window.busy or not self.jobs.currentData():return
        job=self.service.get(self.jobs.currentData())
        if QMessageBox.question(self,'接續確切持久工作',job['id']+'\n保留既有成果，只重分析變更單元；失敗項依勾選重試。')==QMessageBox.Yes:self.start_job(job)

    def start_job(self,job):
        if self.running:return
        claimed=None
        try:
            dispatcher=getattr(self.host_window,'execution_queue',None)
            if dispatcher:
                request=dispatcher.submit('AUTO_JOB',job,self.actor.text() or job['actor'],self.retry.isChecked());self.request_id=request['id'];self.running=True;self.start_button.setEnabled(False);self.resume_button.setEnabled(False);self.cancel_button.setEnabled(True);self.status.setText('執行範圍已持久確認，依先進先出等待資源；尚未宣稱分析或人審完成');return
            supervisor=getattr(self.host_window,'runtime',None)
            if supervisor:
                decision=supervisor.admit('ANALYSIS',requested=True)
                if not decision.allowed:self.status.setText('未取得工作；等待背景資源：'+','.join(decision.reasons));return
            claimed=self.service.claim(job['id'],job['revision'],True,self.retry.isChecked());self.running=True;self.cancel_event.clear()
            self.start_button.setEnabled(False);self.resume_button.setEnabled(False);self.cancel_button.setEnabled(True)
            root=self.host_window.library.root;identity=claimed['id'];token=claimed['owner']['token'];cancel=self.cancel_event;signal=self.progress_signal.updated
            def worker():
                try:return dict(job=run_automatic(root,identity,token,cancel,signal.emit,admission=(lambda:supervisor.admit('ANALYSIS')) if supervisor else None))
                except Exception as error:return dict(error=str(error))
            def finished(result):
                self.running=False;self.cancel_button.setEnabled(False);self.resume_button.setEnabled(True);self.start_button.setEnabled(self.report is not None)
                if result.get('job'):self.render(result['job'])
                else:self.status.setText('工作未完成：'+result['error']+'；依持久狀態接續')
                self.reload();self.host_window.refresh_sources(preserve_editor=True);self.host_window.refresh_templates(preserve_editor=True)
            self.host_window.run_job('來源→作品→標記→品質→學習候選',worker,finished)
        except Exception as error:
            if claimed:
                try:self.service.finish(claimed['id'],claimed['owner']['token'],'FAILED_SYSTEM',str(error))
                finally:LIVE_OWNERS.discard(claimed['owner']['token'])
            self.running=False;self.cancel_button.setEnabled(False);self.resume_button.setEnabled(True);self.start_button.setEnabled(self.report is not None);self.status.setText('啟動失敗：'+str(error))

    def queued_progress(self,identity,job):
        if identity!=self.request_id:return
        self.running=True;self.render(job);self.cancel_button.setEnabled(True)

    def queued_finished(self,identity,job):
        if identity!=self.request_id:return
        self.running=False;self.cancel_button.setEnabled(False);self.resume_button.setEnabled(True);self.start_button.setEnabled(self.report is not None)
        if 'items' in job:self.render(job)
        self.status.setText('已保存執行狀態：'+job['phase']+'；分析與人工審核分開');self.reload()

    def cancel(self):
        if self.request_id:
            try:self.host_window.execution_queue.cancel(self.request_id)
            except Exception as error:self.status.setText('取消未保存：'+str(error))
        else:self.cancel_event.set()

    def job_error(self,error):
        self.running=False;self.cancel_button.setEnabled(False);self.resume_button.setEnabled(True);self.start_button.setEnabled(self.report is not None);self.status.setText('工作未完成：'+str(error)+'；已保存資料保留，可明確重試')

    def reject(self):
        if self.running:self.cancel();self.status.setText('安全取消中；等待目前檔案步驟完成再關閉。');return
        super().reject()

    def closeEvent(self,event):
        if self.running:self.cancel();self.status.setText('安全取消中，當前原子步驟完成後可關閉。');event.ignore()
        else:super().closeEvent(event)

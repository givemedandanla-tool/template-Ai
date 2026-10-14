"""One confirmation, actual per-item progress, cooperative cancel and durable resume."""
from collections import Counter
from pathlib import Path
import threading
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QTableWidget,QTableWidgetItem,QComboBox,QSpinBox,QFileDialog,QMessageBox,QDialogButtonBox,QProgressBar)
from .batch_import import preflight,convert_item
from .font_review import fingerprint
import copy


class BatchImportDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.store=window.import_store;self.paths=[];self.report=None;self.batch=None;self.busy=False;self.running=False;self.cancel_requested=False;self.cancel_event=threading.Event()
        self.setWindowTitle('批次只讀来源匯入／恢復');self.resize(1180,740);layout=QVBoxLayout(self)
        self.status=QLabel('預檢確認後才匯入；不是自動辨識／訓練或模板發布。');self.status.setTextFormat(Qt.PlainText);self.status.setWordWrap(True);layout.addWidget(self.status)
        row=QHBoxLayout();self.choose_files=QPushButton('選擇多個來源');self.choose_files.clicked.connect(self.select_files);row.addWidget(self.choose_files)
        self.choose_folder=QPushButton('選擇單一資料夾');self.choose_folder.clicked.connect(self.select_folder);row.addWidget(self.choose_folder)
        self.page=QSpinBox();self.page.setRange(1,1000);self.page.setPrefix('指定頁 ');row.addWidget(self.page)
        self.scan_button=QPushButton('只讀預檢');self.scan_button.clicked.connect(self.scan);row.addWidget(self.scan_button);layout.addLayout(row)
        self.summary=QLabel();self.summary.setWordWrap(True);self.summary.setTextFormat(Qt.PlainText);layout.addWidget(self.summary)
        self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(['來源／頁次','預檢hash','狀態','attempt','結果來源ID','原因／未驗範圍']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectRows);layout.addWidget(self.table,1)
        self.progress=QProgressBar();layout.addWidget(self.progress)
        row=QHBoxLayout();self.start_button=QPushButton('核對摘要並啟動來源匯入');self.start_button.clicked.connect(self.start_confirmed);row.addWidget(self.start_button)
        self.cancel_button=QPushButton('取消（目前項保存後停止）');self.cancel_button.clicked.connect(self.cancel);row.addWidget(self.cancel_button);layout.addLayout(row)
        row=QHBoxLayout();self.history=QComboBox();self.history.currentIndexChanged.connect(self.load_history);row.addWidget(self.history,1);self.resume_button=QPushButton('明確續跑尚未開始項');self.resume_button.clicked.connect(self.resume);row.addWidget(self.resume_button);layout.addLayout(row)
        self.locate_button=QPushButton('載入所選已保存來源');self.locate_button.clicked.connect(self.locate);layout.addWidget(self.locate_button)
        close=QDialogButtonBox(QDialogButtonBox.Close);close.rejected.connect(self.reject);layout.addWidget(close);self.page.valueChanged.connect(self.reset_input);self.refresh_history();self.controls()
    def controls(self):
        idle=not self.busy and not self.running and not self.window.busy
        for widget in (self.choose_files,self.choose_folder,self.page,self.scan_button,self.history):widget.setEnabled(idle)
        self.start_button.setEnabled(idle and bool(self.report));self.resume_button.setEnabled(idle and bool(self.batch) and any(r['status']=='READY' for r in self.batch['items']) and self.batch['phase']!='RUNNING')
        self.cancel_button.setEnabled(self.busy or self.running);self.locate_button.setEnabled(idle and bool(self.batch))
    def select_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,'選取已授權來源','','Sources (*.ai *.eps *.pdf *.svg *.png *.jpg *.jpeg)')
        if paths:self.paths=paths;self.reset_input()
    def select_folder(self):
        folder=QFileDialog.getExistingDirectory(self,'選取已授權單一本機資料夾')
        if folder:self.paths=[folder];self.reset_input()
    def reset_input(self,*_):
        self.report=None;self.batch=None;self.table.setRowCount(0);self.summary.setText('已選取 '+str(len(self.paths))+' 路徑，請預檢');self.controls()
    def run_background(self,message,function,callback):
        if self.busy or self.window.busy:return
        self.busy=True;self.status.setText(message);self.controls()
        def work():
            try:return {'value':function()}
            except Exception as error:return {'error':str(error) or type(error).__name__}
        def done(result):
            self.busy=False
            try:callback(result)
            except Exception as error:
                self.running=False;self.status.setText('未完成：'+str(error)+'；持久執行項未冒稱成功，需核對恢復。')
                if self.batch:
                    try:
                        b=self.store.get(self.batch['id']);self.batch=self.store.interrupt_owned(b['id'],b['revision'],error);self.render(self.batch['items']);self.refresh_history()
                    except Exception as blocked:self.status.setText(self.status.text()+'／資料完整性仍阻擋：'+str(blocked))
            finally:self.controls()
        try:self.window.run_job(message,work,done)
        except Exception as error:
            self.busy=False;self.running=False;self.status.setText(str(error))
            if self.batch:
                try:
                    b=self.store.get(self.batch['id']);self.batch=self.store.interrupt_owned(b['id'],b['revision'],error)
                except Exception as blocked:self.status.setText(str(error)+'／恢復仍阻擋：'+str(blocked))
            self.controls()
    def scan(self):
        if self.running or self.window.busy:return
        self.report=None;self.batch=None;self.cancel_event.clear();paths=list(self.paths);sources=self.window.library.list_sources();page=self.page.value()
        def done(result):
            if 'error' in result:self.status.setText('預檢未完成：'+result['error']);return
            self.report=result['value'];self.render(self.report['items']);self.summary.setText(f"{len(self.report['items'])}件；檔案exact重複 {self.report['file_duplicates']}，健康重用 {self.report['reuse_candidates']}；作品重複 UNKNOWN，模板相似 UNKNOWN")
            self.status.setText('預檢完成；未改原檔／未學習／未發布，請核對每列摘要。')
        self.run_background('只讀掃描與SHA-256預檢',lambda:preflight(paths,sources,page,self.cancel_event),done)
    def render(self,items):
        self.table.setRowCount(len(items))
        for i,r in enumerate(items):
            for c,value in enumerate((r['path']+'／p'+str(r['page']),r.get('expected_hash') or 'UNKNOWN',r['status'],str(r['attempts']),r.get('source_id') or '未登錄',r['reason'])):
                display=Path(r['path']).name+'／p'+str(r['page'])+' · '+r['path'] if c==0 else value
                cell=QTableWidgetItem(display);cell.setData(Qt.UserRole,r['id']);cell.setToolTip(value);self.table.setItem(i,c,cell)
        self.table.setColumnWidth(0,240);self.table.setColumnWidth(1,130);self.table.setColumnWidth(2,115);self.table.setColumnWidth(4,140);self.table.setColumnWidth(5,360)
        counts=Counter(r['status'] for r in items);self.progress.setRange(0,len(items));self.progress.setValue(len(items)-counts['READY']-counts['RUNNING']);self.progress.setFormat(f"%v/%m 已有單件結果 · {dict(counts)}")
    def start_confirmed(self):
        if self.busy or self.running or not self.report or self.window.busy:return
        report=self.report;prepared=copy.deepcopy(report);before=fingerprint(report)
        message=self.summary.text()+'\n本次全部 '+str(len(report['items']))+' 項均在可捲動列表；完整路徑在每列提示。\n'+'\n'.join(Path(r['path']).name+' p'+str(r['page'])+' '+r['status'] for r in report['items'][:8])+'\n只啟動來源預覽；未同意訓練／發布。'
        if QMessageBox.question(self,'確認精確預檢範圍',message,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        if report is not self.report or fingerprint(report)!=before or self.window.busy:self.status.setText('確認期間預檢範圍異動，請重新核對');return
        try:self.batch=self.store.create(prepared,True);self.report=None;self.start_run()
        except Exception as error:self.status.setText(str(error));self.controls()
    def start_run(self):
        self.running=True;self.cancel_requested=False;self.controls();QTimer.singleShot(0,self.advance)
    def advance(self):
        if not self.running:return
        try:
            current=self.store.get(self.batch['id'])
            if current['revision']!=self.batch['revision']:raise ValueError('批次revision異動，停止且保留已完成結果')
            self.batch=current;item=next((r for r in current['items'] if r['status']=='READY'),None)
            if self.window.busy:raise ValueError('其他背景工作正在執行，保留READY項，稍後續跑')
            if self.cancel_requested or not item:
                self.batch=self.store.stop(current['id'],current['revision'],self.cancel_requested);self.running=False;self.render(self.batch['items']);self.refresh_history();self.status.setText('批次 '+self.batch['phase']+'；結果保存，失敗仍隔離，未核准訓練／規則。');self.controls();return
            self.batch=self.store.claim(current['id'],current['revision'],item['id']);item=next(r for r in self.batch['items'] if r['id']==item['id']);claimed_revision=self.batch['revision'];self.render(self.batch['items'])
            def done(result):
                self.batch=self.store.finish(current['id'],claimed_revision,item['id'],result.get('value'),result.get('error'));self.render(self.batch['items']);QTimer.singleShot(0,self.advance)
            self.run_background('正在匯入 '+Path(item['path']).name+'；單worker／目前項保存才停止',lambda:convert_item(item,self.window.library.assets),done)
        except Exception as error:
            self.running=False;self.status.setText('批次安全停止：'+str(error))
            if self.batch:
                try:
                    b=self.store.get(self.batch['id'])
                    if b['revision']==self.batch['revision'] and not any(r['status']=='RUNNING' for r in b['items']):self.batch=self.store.stop(b['id'],b['revision']);self.refresh_history()
                except Exception:pass
            self.controls()
    def cancel(self):
        self.cancel_event.set();self.cancel_requested=True;self.status.setText('取消已請求；目前轉換與保存後停止，不強殺或刪除已完成資料。')
    def resume(self):
        if self.busy or self.running or self.window.busy or not self.batch:return
        if QMessageBox.question(self,'續跑精確範圍','只處理 READY；FAILED／INTERRUPTED需另行明確重試。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        if self.window.busy:return
        current=self.store.get(self.batch['id'])
        if current['revision']!=self.batch['revision']:self.status.setText('批次異動，請重載');return
        self.start_run()
    def refresh_history(self):
        selected=self.batch['id'] if self.batch else None;self.history.blockSignals(True);self.history.clear();self.history.addItem('選取持久批次',None)
        for b in self.store.list():self.history.addItem(b['phase']+'／'+str(len(b['items']))+'件／'+b['id'],b['id'])
        if selected:self.history.setCurrentIndex(self.history.findData(selected))
        self.history.blockSignals(False)
    def load_history(self,*_):
        if self.busy or self.running:return
        bid=self.history.currentData();self.report=None;self.batch=self.store.get(bid) if bid else None
        if self.batch:self.render(self.batch['items']);self.summary.setText('保存批次 '+bid+'／revision '+str(self.batch['revision']));self.status.setText('歷史 '+self.batch['phase']+'；沒有自動開始。')
        self.controls()
    def locate(self):
        if self.busy or self.running or not self.batch:return
        row=self.table.currentRow()
        if row<0:return
        sid=self.batch['items'][row].get('source_id')
        if not sid:self.status.setText('尚未有保存來源；失敗保留原路徑與錯誤，不猜測作品');return
        if not navigation_clean(self.window):self.status.setText('主工作台有尚未套用的手工屬性，請先明確保存或取消，再定位來源。');return
        self.window.refresh_sources(sid);self.window.tabs.setCurrentIndex(0);self.status.setText('已定位來源，視覺／訓練／發布未核准。')
    def reject(self):
        if self.running or self.busy:self.cancel();return
        super().reject()
    def closeEvent(self,event):
        if self.running or self.busy:self.cancel();event.ignore()
        else:super().closeEvent(event)


def navigation_clean(window):
    if window.current_slot:
        try:return window.make_slot(window.current_slot.rect,preserve=True)==window.current_slot
        except Exception:return False
    return True

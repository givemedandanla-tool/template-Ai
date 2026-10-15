"""One reader/preview for the original issue panels, with a pure-data background encoder."""
import copy
from pathlib import Path
from PySide6.QtCore import QObject, QRunnable, Signal, Qt, QTimer
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTabWidget,
                              QTextBrowser,QPlainTextEdit,QListWidget,QFileDialog)
from .diagnostic_bundle import build_bundle,read_bundle,save_bundle,report_html,encoded,MAX_BYTES
from .diagnostic_schema import MESSAGES
from .diagnostic_snapshot import make_snapshot,locate,LocatorStore


class ReportSignals(QObject):
    finished=Signal(object)


class ReportWorker(QRunnable):
    def __init__(self,data):
        super().__init__();self.setAutoDelete(False);self.data=copy.deepcopy(data);self.signals=ReportSignals()
    def run(self):
        try:result={'raw':build_bundle(self.data)}
        except Exception:result={'error':'報告封裝失敗；可重新產生，原工作與正式輸出未變'}
        self.signals.finished.emit(result)


class DiagnosticReportDialog(QDialog):
    def __init__(self,window,kind='input',work_id=None,session=None,loaded=None,parent=None):
        super().__init__(parent or window);self.window=window;self.kind=kind;self.work_id=work_id;self.session=session
        self.snapshot=None;self.data=None;self.raw=None;self.worker=None;self.running=False;self.external=loaded is not None
        self.setWindowTitle('問題／證據報告 · 安全交接版');self.resize(1050,780)
        layout=QVBoxLayout(self);self.status=QLabel('按需報告；歷史／非正式，未檢查不是PASS。');self.status.setTextFormat(Qt.PlainText);self.status.setWordWrap(True);layout.addWidget(self.status)
        self.tabs=QTabWidget();layout.addWidget(self.tabs,2);self.human=QTextBrowser();self.human.setOpenLinks(False);self.human.setOpenExternalLinks(False);self.tabs.addTab(self.human,'人類閱讀／實際保存內容')
        self.machine=QPlainTextEdit();self.machine.setReadOnly(True);self.tabs.addTab(self.machine,'JSON／完整數值與範圍')
        self.issues=QListWidget();layout.addWidget(self.issues)
        bar=QHBoxLayout();self.refresh_button=QPushButton('依目前範圍重新產生');self.refresh_button.clicked.connect(self.refresh);bar.addWidget(self.refresh_button)
        self.save_button=QPushButton('另存安全報告ZIP');self.save_button.clicked.connect(self.save);bar.addWidget(self.save_button)
        self.locate_button=QPushButton('核對版本並定位選取問題');self.locate_button.clicked.connect(self.locate_selected);bar.addWidget(self.locate_button)
        close=QPushButton('關閉');close.clicked.connect(self.reject);bar.addWidget(close);layout.addLayout(bar)
        self.controls()
        if loaded is not None:
            self.raw=loaded;self.data=read_bundle(loaded);self.display();self.status.setText('已開啟歷史報告；校驗不代表可信作者或當前PASS。');self.controls()
        else:QTimer.singleShot(0,self.refresh)
    def controls(self):
        self.refresh_button.setEnabled(not self.running and not self.external)
        self.save_button.setEnabled(not self.running and self.raw is not None)
        self.locate_button.setEnabled(not self.running and self.data is not None)
    def refresh(self):
        if self.running or self.external:return
        self.raw=None;self.data=None;self.snapshot=None;self.human.clear();self.machine.clear();self.issues.clear()
        try:
            self.snapshot=make_snapshot(self.window,self.kind,self.work_id,self.session)
            self.running=True;self.controls();self.status.setText('已取得同次診斷快照；正在背景封裝安全內容。')
            self.worker=ReportWorker(self.snapshot.data);self.worker.signals.finished.connect(self.on_finished,Qt.QueuedConnection)
            try:self.window.pool.start(self.worker)
            except Exception:self.running=False;raise
        except Exception as error:
            self.status.setText('未產生報告：'+str(error));self.running=False;self.controls()
    def on_finished(self,result):
        self.running=False
        try:
            if 'error' in result:raise ValueError(result['error'])
            self.raw=result['raw'];self.data=read_bundle(self.raw);self.display()
            self.status.setText('預覽即實際保存內容；原始文字／路徑／原圖不在交接包。保存前會再核對版本。')
        except Exception as error:
            self.raw=None;self.data=None;self.status.setText('未完成：'+str(error))
        self.controls()
    def display(self):
        # Rebuild only validated static content; never load the supplied HTML into the widget.
        self.human.setHtml(report_html(self.data).decode());self.machine.setPlainText(encoded(self.data).decode());self.issues.clear()
        for row in self.data['issues']:self.issues.addItem(row['target']+'／'+','.join(row['fields'])+' · '+MESSAGES[row['code']])
        if self.issues.count():self.issues.setCurrentRow(0)
    def save(self):
        if self.running or self.raw is None:return
        try:
            if self.snapshot:self.snapshot.check(self.window)
            name='DIAGNOSTIC_'+self.data['created_utc'][:10]+'_'+self.data['report_id']+'.zip'
            path,_=QFileDialog.getSaveFileName(self,'保存安全診斷報告',name,'診斷報告 (*.zip)')
            if not path:self.status.setText('已取消保存；未建立檔案。');return
            check=(lambda:self.snapshot.check(self.window)) if self.snapshot else (lambda:None)
            save_bundle(path,self.raw,check)
            self.status.setText('已完整保存安全報告；可解壓HTML供人閱讀、JSON供GPT分析。')
            if self.snapshot:
                try:LocatorStore(self.window.library).remember(self.snapshot)
                except Exception:self.status.setText('安全報告已保存；本機定位索引未保存，仍可離線閱讀。')
        except Exception as error:self.status.setText('未保存：'+str(error))
        self.controls()
    def locate_selected(self):
        try:
            if self.data is None:raise ValueError('先產生或開啟報告')
            locate(self.window,self.data,self.issues.currentRow(),self.snapshot)
            self.status.setText('已核對版本並定位；未修復、未改主檔、未放行輸出。')
        except Exception as error:self.status.setText('未定位：'+str(error))
    def reject(self):
        if self.running:self.status.setText('背景封裝尚未結束，請待安全結束後關閉。');return
        super().reject()


def open_saved_report(window):
    path,_=QFileDialog.getOpenFileName(window,'開啟歷史安全報告','','診斷報告 (*.zip)')
    if not path:return
    p=Path(path)
    if not p.is_file() or p.stat().st_size>MAX_BYTES+65536:raise ValueError('報告檔案超出大小預算')
    with p.open('rb') as stream:raw=stream.read(MAX_BYTES+65537)
    read_bundle(raw)
    dialog=DiagnosticReportDialog(window,loaded=raw)
    try:dialog.exec()
    finally:dialog.deleteLater()

import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QComboBox,QPlainTextEdit,QFileDialog,QCheckBox
from .training_store import TrainingStore
from .source_scan import register_root,scan_files,save_scan
from .gui import Job

class SourceScanDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.store=TrainingStore(window.library);self.running=False;self.worker=None;self.setWindowTitle('來源根目錄／手動安全增量核對');self.resize(950,700);l=QVBoxLayout(self);self.status=QLabel('只讀兩次核對；不自動匯入／訓練。事件監看尚未實作。');self.status.setWordWrap(True);l.addWidget(self.status);self.roots=QComboBox();l.addWidget(self.roots);self.recursive=QCheckBox('新根目錄明確包含子資料夾（預設不包含）');l.addWidget(self.recursive);bar=QHBoxLayout();self.add_button=QPushButton('選定新來源根目錄');self.add_button.clicked.connect(self.add);bar.addWidget(self.add_button);self.scan_button=QPushButton('立即重新掃描');self.scan_button.clicked.connect(self.scan);bar.addWidget(self.scan_button);l.addLayout(bar);self.details=QPlainTextEdit();self.details.setReadOnly(True);l.addWidget(self.details);self.reload()
    def reload(self):
        self.roots.clear()
        for r in self.store.records('SCAN_ROOT'):self.roots.addItem(r['path']+'／MANUAL_ONLY',r['id'])
    def add(self):
        try:
            path=QFileDialog.getExistingDirectory(self,'明確指定來源根目錄')
            if path:r=register_root(self.store,path,self.recursive.isChecked());self.reload();self.roots.setCurrentIndex(self.roots.findData(r['id']))
        except Exception as e:self.status.setText('未新增：'+str(e))
    def scan(self):
        if self.running or self.window.busy:self.status.setText('已有背景工作，未開始');return
        try:
            root=self.store.get('SCAN_ROOT',self.roots.currentData())
            if not root:raise ValueError('先選取來源根目錄')
            self.root_snapshot=root;known={s['current_path']:s['hash'] for s in (self.window.library.source(r['id']) for r in self.window.library.list_sources())};self.worker=Job(lambda:scan_files(root,known));self.worker.signals.done.connect(self.done_scan,Qt.QueuedConnection);self.worker.signals.error.connect(self.failed_scan,Qt.QueuedConnection);self.running=True;self.window.busy=True;self.scan_button.setEnabled(False);self.add_button.setEnabled(False)
            try:self.window.pool.start(self.worker)
            except Exception:self.release();raise
        except Exception as e:self.status.setText('未開始：'+str(e))
    def release(self):self.running=False;self.window.busy=False;self.scan_button.setEnabled(True);self.add_button.setEnabled(True)
    def done_scan(self,result):
        self.release()
        try:save_scan(self.store,self.root_snapshot,result);self.details.setPlainText(json.dumps(result,ensure_ascii=False,indent=2));self.status.setText(result['state']+f"／實際{result['scanned_entries']}目錄項；未自動匯入，離線不當刪除")
        except Exception as e:self.status.setText('結果未保存：'+str(e))
    def failed_scan(self,message):self.release();self.status.setText('掃描未完成：'+message)
    def reject(self):
        if self.running:self.status.setText('等待有界掃描完成；來源只讀');return
        super().reject()

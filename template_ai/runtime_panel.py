"""Measured runtime state; pausing background work never approves analysis results."""
import json
from PySide6.QtCore import QTimer,Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPlainTextEdit,QPushButton


class RuntimePanel(QDialog):
    def __init__(self,window):
        super().__init__(window);self.supervisor=window.runtime;self.setWindowTitle('低負載執行／背景暫停');self.resize(760,560)
        layout=QVBoxLayout(self);self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);layout.addWidget(self.status)
        layout.addWidget(QLabel('單一重型工作；先讓介面回應。分析完成與人工審核分開，暫停不變更客戶、模板或核准。'))
        bar=QHBoxLayout();self.pause=QPushButton('保存背景暫停');self.resume=QPushButton('保存背景恢復');bar.addWidget(self.pause);bar.addWidget(self.resume);layout.addLayout(bar)
        self.pause.clicked.connect(lambda:self.change(True));self.resume.clicked.connect(lambda:self.change(False));self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details)
        self.timer=QTimer(self);self.timer.setInterval(500);self.timer.timeout.connect(self.refresh);self.timer.start();self.refresh()
        window.library.observe_close(self.context_closed)

    def change(self,paused):
        try:self.supervisor.set_paused(paused);self.status.setText('已寫入並提交背景'+('暫停' if paused else '恢復')+'策略；執行中工作於安全單位邊界停止。')
        except Exception as error:self.status.setText('未保存成功：'+str(error))
        self.refresh()

    def refresh(self):
        state=self.supervisor.state();self.details.setPlainText(json.dumps(state,ensure_ascii=False,indent=2))
        self.pause.setEnabled(not state['closed']);self.resume.setEnabled(not state['closed'] and not state['policy_error'])
        if state['closed']:self.context_closed()

    def context_closed(self):
        self.timer.stop();self.pause.setEnabled(False);self.resume.setEnabled(False);self.status.setText('原專案已關閉；不讀寫其他專案。')

    def closeEvent(self,event):self.timer.stop();super().closeEvent(event)

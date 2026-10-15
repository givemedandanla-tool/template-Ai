"""Measured runtime state; pausing background work never approves analysis results."""
import json
from PySide6.QtCore import QTimer,Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPlainTextEdit,QPushButton,QTableWidget,QTableWidgetItem,QLineEdit,QCheckBox,QMessageBox
from shiboken6 import isValid


class RuntimePanel(QDialog):
    def __init__(self,window):
        super().__init__(window);self.supervisor=window.runtime;self.dispatcher=window.execution_queue;self.offset=0;self.rows=[];self.setWindowTitle('低負載執行／持久佇列／安全恢復');self.resize(1000,760)
        layout=QVBoxLayout(self);self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);layout.addWidget(self.status)
        layout.addWidget(QLabel('單一重型工作；先讓介面回應。分析完成與人工審核分開，暫停不變更客戶、模板或核准。'))
        bar=QHBoxLayout();self.pause=QPushButton('保存背景暫停');self.resume=QPushButton('保存背景恢復');bar.addWidget(self.pause);bar.addWidget(self.resume);layout.addLayout(bar)
        self.pause.clicked.connect(lambda:self.change(True));self.resume.clicked.connect(lambda:self.change(False));self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details)
        self.summary=QLabel();self.summary.setWordWrap(True);layout.addWidget(self.summary);self.queue_table=QTableWidget(0,5);self.queue_table.setHorizontalHeaderLabels(['到達序','執行狀態／結果','工作種類／ID','確認範圍','訊息']);self.queue_table.setEditTriggers(QTableWidget.NoEditTriggers);self.queue_table.setSelectionBehavior(QTableWidget.SelectRows);self.queue_table.setSelectionMode(QTableWidget.SingleSelection);layout.addWidget(self.queue_table,2)
        bar=QHBoxLayout();self.actor=QLineEdit();self.actor.setMaxLength(120);self.actor.setPlaceholderText('本次恢復操作者');bar.addWidget(self.actor);self.retry=QCheckBox('明確重試FAILED');bar.addWidget(self.retry)
        self.previous=QPushButton('上頁請求');self.next=QPushButton('下頁請求');self.restore=QPushButton('核對後恢復選中範圍');self.cancel=QPushButton('安全取消選中請求')
        for button in (self.previous,self.next,self.restore,self.cancel):bar.addWidget(button)
        self.previous.clicked.connect(lambda:self.page(-50));self.next.clicked.connect(lambda:self.page(50));self.restore.clicked.connect(self.resume_selected);self.cancel.clicked.connect(self.cancel_selected);layout.addLayout(bar)
        self.timer=QTimer(self);self.timer.setInterval(500);self.timer.timeout.connect(self.refresh);self.timer.start();self.refresh()
        window.library.observe_close(self.context_closed)

    def change(self,paused):
        try:self.supervisor.set_paused(paused);self.status.setText('已寫入並提交背景'+('暫停' if paused else '恢復')+'策略；執行中工作於安全單位邊界停止。')
        except Exception as error:self.status.setText('未保存成功：'+str(error))
        self.refresh()

    def refresh(self):
        state=self.supervisor.state();self.details.setPlainText(json.dumps(state,ensure_ascii=False,indent=2))
        self.pause.setEnabled(not state['closed']);self.resume.setEnabled(not state['closed'] and not state['policy_error'])
        if state['closed']:self.context_closed();return
        if self.dispatcher.library is not self.supervisor.library:self.context_closed();return
        try:
            old=self.selected();selected_id=old['id'] if old else None;self.rows=self.dispatcher.queue.page(self.offset,50)
            total=self.dispatcher.library.db.execute('SELECT count(*) FROM runtime_requests').fetchone()[0];self.queue_table.setRowCount(len(self.rows))
            for index,row in enumerate(self.rows):
                consent='本次範圍已確認' if row['consent_session']==self.dispatcher.session else '重啟／其他作用域：需明確恢復' if row['state'] in ('WAITING','PAUSED_RESOURCES','INTERRUPTED') else '此請求已結束／人工處理'
                for column,value in enumerate((row['seq'],row['state']+' / '+row.get('result_phase',''),row['kind']+' / '+row['job_id'],consent,row.get('message') or '')):self.queue_table.setItem(index,column,QTableWidgetItem(str(value)))
                if row['id']==selected_id:self.queue_table.selectRow(index)
            self.previous.setEnabled(self.offset>0);self.next.setEnabled(self.offset+50<total);self.summary.setText(f'執行請求 {self.offset+1 if total else 0}–{self.offset+len(self.rows)}／{total}；單一worker；等待人工審核與失敗不占執行權。'+(self.dispatcher.error or self.dispatcher.last_wait or ''))
        except Exception as error:self.status.setText('佇列未能讀取，未宣稱工作成功：'+str(error))

    def selected(self):
        selected=self.queue_table.selectionModel().selectedRows()
        return self.rows[selected[0].row()] if selected and selected[0].row()<len(self.rows) else None

    def page(self,delta):self.offset=max(0,self.offset+delta);self.refresh()

    def resume_selected(self):
        try:
            row=self.selected()
            if not row or not self.actor.text().strip():raise ValueError('先選執行請求並填本次操作者')
            job=self.dispatcher.queue.store.get(row['kind'],row['job_id'])
            if not job:raise ValueError('原工作失聯，先到來源／品質中心診斷')
            preview=dict(kind=row['kind'],job_id=job['id'],scope_digest=row['scope_digest'],source_or_sample_count=len(job['items']),items=[{k:item.get(k) for k in ('path','page','source_hash','sample_id','work_scope','state')} for item in job['items']])
            if QMessageBox.question(self,'確認原範圍續跑',json.dumps(preview,ensure_ascii=False,indent=2)+'\n已有效保存的單位不重做；FAILED只在勾選時重試。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            self.dispatcher.submit(row['kind'],job,self.actor.text(),self.retry.isChecked());self.status.setText('已保存明確恢復請求；尚未宣稱執行或人工審核完成')
        except Exception as error:self.status.setText('未恢復：'+str(error))
        self.refresh()

    def cancel_selected(self):
        try:
            row=self.selected()
            if not row:raise ValueError('先選執行請求')
            self.dispatcher.cancel(row['id']);self.status.setText('已請求安全取消；保留有效成果及工作歷史')
        except Exception as error:self.status.setText('未保存取消：'+str(error))
        self.refresh()

    def context_closed(self):
        if not isValid(self):return
        self.timer.stop()
        for button in (self.pause,self.resume,self.restore,self.cancel,self.previous,self.next):button.setEnabled(False)
        self.status.setText('原專案已關閉；不讀寫其他專案。')

    def closeEvent(self,event):self.timer.stop();super().closeEvent(event)

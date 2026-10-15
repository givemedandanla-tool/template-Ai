"""Bounded asynchronous read-only ledger; existing editors keep all approval authority."""
import json,sys
from PySide6.QtCore import Qt,QProcess,QTimer,Signal
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QComboBox,QPushButton,QTableWidget,QTableWidgetItem,QPlainTextEdit,QHeaderView
from pathlib import Path
from .runtime_labels import label
from shiboken6 import isValid
from .review_ledger import MAX_BYTES


class ReviewLedgerDialog(QDialog):
    loaded=Signal(object)

    def __init__(self,window):
        super().__init__(window);self.window=window;self.library=window.library;self.offset=0;self.rows=[];self.process=None;self.closed=False;self.snapshot=None;self.setWindowTitle('逐來源／實際作品／分析與人工審核');self.resize(1190,790)
        layout=QVBoxLayout(self);bar=QHBoxLayout();self.mode=QComboBox();self.mode.addItem('來源登錄頁','SOURCE');self.mode.addItem('實際作品及核實審核','WORK');self.mode.addItem('索引／預檢範圍（另計）','PENDING');bar.addWidget(self.mode)
        self.query=QLineEdit();self.query.setMaxLength(500);self.query.setPlaceholderText('全庫搜尋ID／檔名／作品');bar.addWidget(self.query,1);self.source_filter=QLineEdit();self.source_filter.setMaxLength(128);self.source_filter.setPlaceholderText('作品模式可限定來源ID');bar.addWidget(self.source_filter);self.refresh_button=QPushButton('核實／刷新');self.refresh_button.clicked.connect(self.reload);bar.addWidget(self.refresh_button);layout.addLayout(bar)
        self.summary=QLabel('來源／作品分母尚未讀回；未以分析成功取代人工審核');self.summary.setWordWrap(True);layout.addWidget(self.summary);self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);layout.addWidget(self.status)
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['來源／作品ID','路徑／名稱／頁','實際作品／分析狀態','審核／歸屬（獨立）','理由／下一步']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.SingleSelection);self.table.itemSelectionChanged.connect(self.show_detail);self.table.cellDoubleClicked.connect(lambda *_:self.open_works());layout.addWidget(self.table,2)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details,1);bar=QHBoxLayout();self.previous=QPushButton('上一頁');self.next=QPushButton('下一頁');self.works=QPushButton('查看此來源實際作品');self.locate=QPushButton('核對版次後定位原畫布')
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for button in (self.previous,self.next,self.works,self.locate):bar.addWidget(button)
        self.previous.clicked.connect(lambda:self.page(-50));self.next.clicked.connect(lambda:self.page(50));self.works.clicked.connect(self.open_works);self.locate.clicked.connect(self.locate_work);layout.addLayout(bar)
        self.debounce=QTimer(self);self.debounce.setSingleShot(True);self.debounce.setInterval(300);self.debounce.timeout.connect(self.reset_search)
        self.query.textChanged.connect(lambda:self.debounce.start());self.source_filter.textChanged.connect(lambda:self.debounce.start());self.mode.currentIndexChanged.connect(self.reset_search);self.library.observe_close(self.shutdown);self.reload()

    def reset_search(self):self.offset=0;self.reload()
    def page(self,delta):self.offset=max(0,self.offset+delta);self.reload()

    def reload(self):
        if self.closed or self.library.closed or self.window.library is not self.library:self.shutdown();return
        if self.process:self.process.kill()
        process=QProcess(self);self.process=process;output=bytearray();errors=bytearray();flags=dict(failed=False)
        self.status.setText('背景核實本頁，主介面可用；尚未把此階段宣稱完成。來源內容／快取只在作品頁核實。')
        def stdout():
            output.extend(bytes(process.readAllStandardOutput()))
            if len(output)>MAX_BYTES:flags['failed']=True;process.kill();self.status.setText('讀回超過4MiB，保留上次快照；請縮小搜尋，未截斷分母')
        def stderr():
            errors.extend(bytes(process.readAllStandardError()));del errors[:-4096]
        def done(code,*_):
            if self.closed or self.process is not process or self.library.closed or self.window.library is not self.library:process.deleteLater();return
            self.process=None;stdout();stderr()
            try:
                if flags['failed']:return
                value=json.loads(output)
                if code!=0 or value.get('error'):raise ValueError(value.get('error') or errors.decode('utf-8','replace') or '核實程序未完成')
                self.snapshot=value;self.rows=value['rows'];self.table.setRowCount(len(self.rows))
                for index,row in enumerate(self.rows):
                    title=Path(row.get('path') or '').name+'／頁'+str(row.get('page','未知'))
                    state=('已登錄作品紀錄 '+str(row['actual_works'])+'；' if 'actual_works' in row else '')+label(row.get('analysis_state','未知'));review=label(row.get('review_state','未知'))+'；'+row.get('ownership','')
                    for column,text in enumerate((row.get('name') or row['id'],title,state,review,row.get('source_error') or row.get('exclusion_reason') or row['next'])):
                        item=QTableWidgetItem(text);item.setToolTip(text+'\n'+row['id']);self.table.setItem(index,column,item)
                    self.table.setRowHeight(index,66)
                summary=value['summary'];self.summary.setText(f"登錄來源頁{summary['registered_source_pages']}／原始路徑{summary['registered_original_paths']}；已登錄作品紀錄{summary['actual_active_works']}（另存已取代歷史{summary['superseded_work_history']}）；另有未登錄預檢／匯入範圍{summary['unregistered_preflight_scope_records']}筆、索引候選{summary['indexed_candidates']}筆（另計）；已存人工核准紀錄{summary['human_confirmation_records']}，全庫當前有效已審數尚未逐頁核實。作品紀錄含未核對候選，不宣稱已覆蓋所有原稿作品。此頁有效已審{value['page_reviewed']}／明確排除{value['page_excluded']}，兩者分開。")
                self.status.setText(f"已核實只讀快照；本頁{len(self.rows)}／符合{value['total']}，起點{value['offset']}。候選／預檢另計，不用內容去重減少來源；正式輸出仍走原Gate。")
                self.previous.setEnabled(self.offset>0);self.next.setEnabled(self.offset+50<value['total']);self.show_detail();self.loaded.emit(value)
            except Exception as error:self.status.setText('核實未完成，保留上次有效快照：'+str(error))
            finally:process.deleteLater()
        def timeout():
            if self.process is process and process.state()!=QProcess.NotRunning:flags['failed']=True;process.kill();self.status.setText('核實超過30秒，已隔離停止；上次快照保留，未宣稱已審')
        def failed(error):
            if error==QProcess.FailedToStart and self.process is process:self.process=None;self.status.setText('無法啟動核實；保留上次快照');process.deleteLater()
        process.readyReadStandardOutput.connect(stdout);process.readyReadStandardError.connect(stderr);process.finished.connect(done);process.errorOccurred.connect(failed);QTimer.singleShot(30000,process,timeout)
        process.setProgram(sys.executable);process.setArguments(['-m','template_ai.review_ledger','--root',str(self.library.root),'--mode',self.mode.currentData(),'--query',self.query.text(),'--source',self.source_filter.text().strip(),'--offset',str(self.offset)]);process.start()

    def current(self):
        row=self.table.currentRow();return self.rows[row] if 0<=row<len(self.rows) else None
    def show_detail(self):
        row=self.current();self.details.setPlainText(json.dumps(row,ensure_ascii=False,indent=2) if row else '')
    def open_works(self):
        row=self.current()
        if not row or not row.get('source_id'):return
        self.source_filter.setText(row['source_id']);self.mode.setCurrentIndex(self.mode.findData('WORK'));self.reset_search()
    def locate_work(self):
        try:
            row=self.current()
            if not row or not row.get('work_id'):raise ValueError('先選作品；候選不等於已登錄作品')
            from .training_navigation import require_clean_navigation
            require_clean_navigation(self.window);work=self.library.artwork(row['work_id'])
            if work['revision']!=row['work_revision']:raise ValueError('作品版次已改變，先刷新')
            self.window.refresh_sources(select=row['source_id']);self.window.load_work(work);self.window.tabs.setCurrentIndex(0);self.status.setText('已定位原作品，尚未改寫或核准')
        except Exception as error:self.status.setText('未定位：'+str(error))
    def shutdown(self):
        if not isValid(self) or self.closed:return
        self.closed=True;self.debounce.stop()
        if self.process:self.process.kill()
        for widget in (self.mode,self.query,self.source_filter,self.refresh_button,self.previous,self.next,self.works,self.locate):widget.setEnabled(False)
    def closeEvent(self,event):self.shutdown();super().closeEvent(event)

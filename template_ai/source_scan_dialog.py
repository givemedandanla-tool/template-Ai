"""Shared watcher workbench; explicit root permissions and candidate-to-UI003 handoff."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gui import MainWindow
from pathlib import Path
import sqlite3
from shiboken6 import isValid
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QPushButton,QComboBox,QPlainTextEdit,QFileDialog,QCheckBox,QLineEdit,QTreeWidget,QTreeWidgetItem,QMessageBox,QDialogButtonBox,QInputDialog,QWidget,QTabWidget)
from .worker_callbacks import JobCallbacks
from .training_store import TrainingStore,digest
from .source_scan import (register_root,configure_root,active_roots,candidate_page,review_candidate,record_dispatch,DEFAULT_EXCLUDES,EXTENSIONS)
from .source_links import verify_source

LABELS={'NEW_CANDIDATE':'新來源候選','DUPLICATE_ALIAS_KEEP_IDENTITY':'異名同內容，身份仍獨立待審','CONTENT_CHANGED_REVIEW_REQUIRED':'同名內容改變，需人工核對','UNCHANGED':'內容未變，是否完成另依來源／作品狀態','MISSING_OR_MOVED_REVIEW_REQUIRED':'失聯或搬移，需定位','READ_ERROR':'不可讀，需重試','WAIT_STABLE':'等待寫入穩定','QUEUED_FOR_UI003_PREFLIGHT':'已入預檢待辦，未開始訓練','FOUND_NOT_QUEUED':'手動發現，未自動入隊','REVIEW_REQUIRED':'修改版待人工核對','REVIEWED_NEW_VERSION_CANDIDATE':'修改版已核對，可作新候選','STALE_SOURCE_CHANGED':'舊候選內容已變，暫停使用','SOURCE_REGISTERED_REVIEW_PENDING':'來源已登錄，歸屬依原審核紀錄','DISPATCHED':'已交接實際一鍵工作，成果另查'}
CONFIG_KEYS=['path','recursive','extensions','excludes','mode','archived','requires_reconnect']


class SourceScanDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.host_window: MainWindow=window;self.store=TrainingStore.bind(window.library);self.service=window.source_watch;self.running=False;self.offset=0;self.scan_offset=0;self.dirty=False;self.loading=True;self.root_snapshot=None;self.training_dialog=None;self.dispatch_context=None;self._context_error=None
        self.setWindowTitle('來源監看／安全增量候選');self.resize(1120,740);layout=QVBoxLayout(self)
        note=QLabel('僅明列本機範圍。事件只是提示，程式開啟時600ms去抖、30秒與重啟補掃；最多128個即時提示點。單次500項／雙讀取256MiB，超額明示部分。候選持久保存，真正訓練仍須既有一鍵預檢確認；每頁50筆，只交接本頁明列勾選。');note.setWordWrap(True);layout.addWidget(note)
        self.status=QLabel('選取來源根目錄；掃描只讀原稿，離線不當作刪除。');self.status.setTextFormat(Qt.PlainText);self.status.setWordWrap(True);layout.addWidget(self.status)
        self.roots=QComboBox();self.roots.currentIndexChanged.connect(self.load_root);layout.addWidget(self.roots)
        self.tabs=QTabWidget();layout.addWidget(self.tabs,1);scan_widget=QWidget();scan=QVBoxLayout(scan_widget);settings_widget=QWidget();settings=QVBoxLayout(settings_widget)
        controls=QHBoxLayout();self.scan_button=self.button(controls,'立即安全補掃',self.scan);self.button(controls,'取消本次／待掃',self.cancel);self.button(controls,'重新載入狀態',self.reload);scan.addLayout(controls)
        self.only_changed=QCheckBox('掃描摘要只顯示變更／問題（總數保留）');self.only_changed.toggled.connect(self.reset_scan_page);scan.addWidget(self.only_changed)
        inspect_row=QHBoxLayout();self.scan_items=QComboBox();inspect_row.addWidget(self.scan_items,1);self.button(inspect_row,'查看原來源完整影響',self.inspect_source);self.button(inspect_row,'重核未變來源／快取',self.recheck_existing);scan.addLayout(inspect_row)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);self.details.setMaximumHeight(125);scan.addWidget(self.details)
        scan_pages=QHBoxLayout();self.button(scan_pages,'掃描摘要上一頁',lambda:self.scan_page(-1));self.button(scan_pages,'掃描摘要下一頁',lambda:self.scan_page(1));scan.addLayout(scan_pages)
        self.candidates=QTreeWidget();self.candidates.setHeaderLabels(['選取／檔名／編號線索','候選狀態','內容版本／實際工作','來源位置']);scan.addWidget(self.candidates,1)
        for column,width in enumerate((190,250,280,350)):self.candidates.setColumnWidth(column,width)
        actions=QHBoxLayout();self.button(actions,'候選上一頁50筆',lambda:self.page(-1));self.button(actions,'候選下一頁50筆',lambda:self.page(1));self.button(actions,'核對修改版為新候選',self.review);self.button(actions,'交既有一鍵預檢／開啟工作',self.launch);scan.addLayout(actions)
        self.actor=QLineEdit('本機操作人');actor_form=QFormLayout();actor_form.addRow('修改版核對人',self.actor);scan.addLayout(actor_form)
        form=QFormLayout();self.mode=QComboBox();self.mode.addItems(['僅手動重新掃描','監看事件＋補掃＋安全候選預檢']);form.addRow('監看模式',self.mode)
        self.recursive=QCheckBox('明確包含子資料夾');form.addRow('搜尋範圍',self.recursive)
        self.formats=QLineEdit(','.join(sorted(EXTENSIONS)));form.addRow('支援格式（逗號分隔）',self.formats)
        self.excludes=QPlainTextEdit('\n'.join(DEFAULT_EXCLUDES));self.excludes.setMaximumHeight(150);form.addRow('排除相對路徑／檔名（每行一項）',self.excludes);settings.addLayout(form)
        root_actions=QHBoxLayout();self.add_button=self.button(root_actions,'選定新來源根目錄',self.add);self.button(root_actions,'保存設定',self.save_settings);self.button(root_actions,'開始監看／套用設定',self.start_watch);self.button(root_actions,'暫停監看',self.pause);self.button(root_actions,'移除此監看來源',self.remove);settings.addLayout(root_actions)
        explanation=QLabel('新增根目錄預設為手動。明確開始監看才可自動核對並保存安全候選；暫停／移除會停止未來監看，保留來源、客戶、版型與訓練。關閉程式時不在背景執行，下次開啟補掃。監看提示不保證涵蓋斷線、休眠或所有子目錄變動。');explanation.setWordWrap(True);settings.addWidget(explanation);settings.addStretch()
        self.tabs.addTab(scan_widget,'掃描／候選／交接');self.tabs.addTab(settings_widget,'根目錄／格式／排除')
        close=QDialogButtonBox(QDialogButtonBox.Close);close.button(QDialogButtonBox.Close).setText('關閉');close.rejected.connect(self.reject);layout.addWidget(close)
        for signal in [self.mode.currentIndexChanged,self.recursive.toggled,self.formats.textEdited,self.excludes.textChanged]:signal.connect(self.changed)
        self.service.updated.connect(self.service_updated);self.store.library.observe_close(self.context_closed);self.loading=False;self.reload()

    def button(self,row,label,callback):
        button=QPushButton(label);button.clicked.connect(callback);row.addWidget(button);return button

    def changed(self,*args):
        if not self.loading:self.dirty=True

    def reload(self):
        if not self.valid_context():return
        selected=self.roots.currentData();self.loading=True;self.roots.blockSignals(True);self.roots.clear()
        for root in active_roots(self.store):self.roots.addItem(root['path']+'／'+('監看中' if root.get('enabled') else '暫停／手動'),root['id'])
        index=self.roots.findData(selected);self.roots.setCurrentIndex(index if index>=0 else 0);self.roots.blockSignals(False);self.loading=False
        self.load_root(force=True)

    def load_root(self,*args,force=False):
        if not self.valid_context():return
        identity=self.roots.currentData();root=self.store.get('SCAN_ROOT',identity) if identity else None
        if self.dirty and self.root_snapshot and identity!=self.root_snapshot['id'] and not force:
            if QMessageBox.question(self,'切換來源設定','目前設定尚未保存。明確捨棄這些輸入並切換？')!=QMessageBox.Yes:
                self.roots.blockSignals(True);self.roots.setCurrentIndex(self.roots.findData(self.root_snapshot['id']));self.roots.blockSignals(False);return
        if root and (not self.dirty or not self.root_snapshot or self.root_snapshot['id']!=root['id']):
            self.loading=True;self.root_snapshot=root;self.mode.setCurrentIndex(1 if root.get('mode')=='AUTO_PRECHECK' else 0);self.recursive.setChecked(root.get('recursive',False));self.formats.setText(','.join(root.get('extensions',sorted(EXTENSIONS))));self.excludes.setPlainText('\n'.join(root.get('excludes',DEFAULT_EXCLUDES)));self.loading=False;self.dirty=False
        if not root:self.root_snapshot=None
        self.offset=0;self.scan_offset=0;self.render_current()

    def form_options(self):return dict(recursive=self.recursive.isChecked(),extensions=[s.strip().lower() for s in self.formats.text().split(',') if s.strip()],excludes=[s.strip() for s in self.excludes.toPlainText().splitlines() if s.strip()])

    def add(self):
        if not self.valid_context():return
        if self.host_window.busy:self.status.setText('背景工作中；原設定保留，稍後新增');return
        try:
            path=QFileDialog.getExistingDirectory(self,'明確選擇已授權本機來源根目錄')
            if not path:return
            root=register_root(self.store,path,**self.form_options());self.dirty=False;self.reload();self.roots.setCurrentIndex(self.roots.findData(root['id']));self.status.setText('根目錄已保存，預設手動；開始監看仍需明確操作')
        except Exception as error:self.status.setText('未新增：'+str(error))

    def commit_settings(self,start=False):
        if not self.valid_context():return
        if self.host_window.busy:self.status.setText('請先安全暫停目前背景工作，再保存設定；輸入保留');return
        try:
            root=self.store.get('SCAN_ROOT',self.roots.currentData())
            if not root:raise ValueError('先選取來源根目錄')
            if self.root_snapshot and digest({k:root.get(k) for k in CONFIG_KEYS})!=digest({k:self.root_snapshot.get(k) for k in CONFIG_KEYS}):raise ValueError('另一介面已改監看設定，保留輸入；需重新載入核對')
            mode='AUTO_PRECHECK' if start or self.mode.currentIndex()==1 else 'MANUAL_ONLY'
            configure_root(self.store,root,mode=mode,enabled=True if start else bool(root.get('enabled') and mode=='AUTO_PRECHECK'),**self.form_options());self.dirty=False;self.reload();self.service.sync();self.status.setText('設定已持久保存；'+('已啟用監看，來源仍須實際核對' if start else '候選／原資料保留'))
        except Exception as error:self.status.setText('設定未套用：'+str(error))

    def save_settings(self):self.commit_settings(False)
    def start_watch(self):self.commit_settings(True)
    def pause(self):
        try:self.service.pause(self.roots.currentData());self.reload()
        except Exception as error:self.status.setText('未暫停：'+str(error))
    def remove(self):
        identity=self.roots.currentData()
        if identity and QMessageBox.question(self,'停止此來源後續掃描','只移除監看設定；不刪來源、候選歷史、客戶、已發布模板或訓練。確認？')==QMessageBox.Yes:
            try:self.service.remove(identity);self.dirty=False;self.reload()
            except Exception as error:self.status.setText('未移除：'+str(error))
    def scan(self):
        if not self.valid_context():return
        try:
            self.running=True;self.scan_button.setEnabled(False);self.status.setText('已排入本次安全補掃；等待共用背景工作空檔');self.service.request_manual(self.roots.currentData())
        except Exception as error:self.running=False;self.status.setText('未排入掃描：'+str(error))
    def cancel(self):self.service.cancel_root(self.roots.currentData())

    def service_updated(self,payload):
        if not self.valid_context():return
        if payload['root_id'] not in (self.roots.currentData(),'SERVICE','WATCH_CAPACITY'):return
        self.status.setText(payload['message'])
        try:
            if payload['state'] in ('REMOVED','PAUSED'):
                if payload['state']=='REMOVED':self.dirty=False
                self.reload()
            if payload['state'] not in ('SCANNING','WAITING_BACKGROUND_SLOT','PAUSING','PAUSED_RESOURCES'):
                self.running=False;self.render_current()
            self.scan_button.setEnabled(not self.running)
        except sqlite3.Error as error:
            self._context_error='資料庫暫不能安全讀寫：'+str(error);self.valid_context()

    def render_current(self,*args):
        if not self.valid_context():return
        identity=self.roots.currentData();root=self.store.get('SCAN_ROOT',identity) if identity else None
        checked={(c['id'],c['revision'],c['source_hash'],c['state']) for c in self.selected()};self.candidates.clear()
        if not root:self.details.setPlainText('尚無有效來源根目錄');return
        attempt=root.get('latest_attempt') or root.get('last_scan') or {};rows=attempt.get('entries',[]);shown=[r for r in rows if not self.only_changed.isChecked() or r['state']!='UNCHANGED']
        from datetime import datetime
        last=datetime.fromtimestamp(root['last_success']).astimezone().strftime('%Y-%m-%d %H:%M:%S %Z') if root.get('last_success') else '尚無'
        scan_label={'SCANNED':'本次掃描核對完成','PARTIAL':'部分範圍／仍需處理','ROOT_OFFLINE':'根目錄離線，來源數未知','CANCELLED':'本次已取消'}.get(attempt.get('state'),'尚未掃描')
        lines=[f"上次完整掃描核對時間：{last}；目前結果 {scan_label}；本次顯示{len(shown)}／{len(rows)}檔案處置；已核對目錄項{attempt.get('scanned_entries','未知')}。",'檔案數不是作品數；未變不是已學習／已核准。']
        selected=self.scan_items.currentText();self.scan_items.clear()
        for row in shown[self.scan_offset:self.scan_offset+50]:self.scan_items.addItem(Path(row['path']).name+'／'+LABELS.get(row['state'],row['state']),row)
        index=self.scan_items.findText(selected)
        if index>=0:self.scan_items.setCurrentIndex(index)
        for row in shown[self.scan_offset:self.scan_offset+50]:
            count=row.get('artwork_count');work_label=f'{count}筆已登錄作品記錄' if type(count) is int else '作品尚未解析，數量未知'
            lines.append(f"{row['path']}\n  {LABELS.get(row['state'],row['state'])}；SHA {row.get('verified_hash',row.get('hash','尚未核驗'))}；{work_label}；原來源{','.join(row.get('affected_source_ids',[])) or '未登錄'}；{row.get('reason','')}")
        if len(shown)>50:lines.append(f'掃描摘要本頁{self.scan_offset+1}～{min(self.scan_offset+50,len(shown))}／{len(shown)}；可翻頁核對；完整結果與候選已持久保存，不代表全部已處置。')
        self.details.setPlainText('\n'.join(lines))
        for candidate in candidate_page(self.store,identity,self.offset):
            item=QTreeWidgetItem([Path(candidate['path']).name+'\n編號線索：'+candidate.get('customer_code_candidate',Path(candidate['path']).stem)+'（待核對）',LABELS.get(candidate['state'],candidate['state']),candidate['source_hash']+'／'+str(candidate.get('auto_job_id','未建立訓練工作')),candidate['path']]);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(0,Qt.Checked if (candidate['id'],candidate['revision'],candidate['source_hash'],candidate['state']) in checked else Qt.Unchecked);item.setData(0,Qt.UserRole,candidate)
            for column in range(4):item.setToolTip(column,item.text(column))
            item.setToolTip(0,item.text(0)+'\nsource_file_id：'+(','.join(candidate.get('source_ids',[])) or '尚未登錄')+'\n候選版次：'+str(candidate['revision']))
            self.candidates.addTopLevelItem(item)

    def reset_scan_page(self,*args):self.scan_offset=0;self.render_current()
    def scan_page(self,direction):self.scan_offset=max(0,self.scan_offset+direction*50);self.render_current()
    def page(self,direction):self.offset=max(0,self.offset+direction*50);self.render_current()
    def selected(self):return [self.candidates.topLevelItem(i).data(0,Qt.UserRole) for i in range(self.candidates.topLevelItemCount()) if self.candidates.topLevelItem(i).checkState(0)==Qt.Checked]

    def inspect_source(self):
        if not self.valid_context():return
        row=self.scan_items.currentData()
        if self.host_window.busy or not row:self.status.setText('先選取本頁來源，並等待背景空閒');return
        ids=row.get('affected_source_ids',[]) or row.get('registered_source_ids',[])
        if not ids:self.status.setText('此檔尚未登錄原來源／作品；請先由候選核對預檢');return
        identity=ids[0]
        if len(ids)>1:
            identity,accepted=QInputDialog.getItem(self,'選取保留來源版本','只查看確切來源ID，不改客戶映射',ids,0,False)
            if not accepted:return
        data_root=self.host_window.library.root
        def work():
            from .source_context import snapshot_contexts
            try:return dict(source=snapshot_contexts(data_root,[identity])[0])
            except Exception as error:return dict(error=str(error))
        def done(payload):
            if not self.valid_context():return
            if payload.get('error'):self.status.setText('影響查詢未完成：'+payload['error']);return
            from .source_dialog import SourceRelinkDialog
            from .source_discovery import availability
            source=payload['source'];preview=SourceRelinkDialog(self.host_window);preview.setParent(self,Qt.Dialog)
            preview.show_report(dict(status='COMPLETE',roots=[],entries=0,hashed_files=0,errors=[],rows=[dict(source=source,availability=availability(source),candidates=[],same_name_different=[])]))
            preview.show_details();preview.close();preview.deleteLater()
        try:self.host_window.run_job('唯讀核對原來源關聯',work,JobCallbacks(done,lambda error:done({'error':str(error)})))
        except Exception as error:self.status.setText('未開始影響查詢：'+str(error))

    def recheck_existing(self):
        if not self.valid_context():return
        row=self.scan_items.currentData()
        if self.host_window.busy or not row or not row.get('registered') or row['state']!='UNCHANGED':self.status.setText('只對已核驗且未變的既有來源重核；修改版請先人工核對新候選');return
        from .automatic_training_dialog import AutomaticTrainingDialog
        self.dispatch_context=None;dialog=self.training_view();dialog.preflight([row['path']],expected_hashes={row['path']:row['verified_hash']})
        self.status.setText('已交既有管線重核解析／規則／模型／作品依賴；只重算失效單元，是否重用以實際預檢為準')

    def review(self):
        if not self.valid_context():return
        values=self.selected()
        if self.host_window.busy or len(values)!=1 or values[0]['state']!='REVIEW_REQUIRED':self.status.setText('請只勾選一筆修改版待審，並等待背景空閒');return
        candidate=values[0]
        if QMessageBox.question(self,'核對獨立新來源候選',f"{candidate['path']}\n原SHA {candidate.get('previous_hash')}\n新SHA {candidate['source_hash']}\n只核准新來源候選進預檢，保留舊版型與客戶歸屬待審，沒有核准正式模板。確認？")!=QMessageBox.Yes:return
        actor=self.actor.text();self.running=True
        def work():
            try:return dict(proof=verify_source(candidate['path'],candidate['source_hash']))
            except Exception as error:return dict(error=str(error))
        def done(payload):
            self.running=False
            try:
                if payload.get('error'):raise ValueError(payload['error'])
                review_candidate(self.store,candidate,payload['proof'],actor,True);self.render_current();self.status.setText('修改版已核對為新來源候選；請交既有預檢，客戶／模板仍未批准')
            except Exception as error:self.status.setText('未核准候選：'+str(error))
        try:self.host_window.run_job('核對修改版實際內容',work,JobCallbacks(done,lambda error:done({'error':str(error)})))
        except Exception as error:self.running=False;self.status.setText('未開始候選核對：'+str(error))

    def launch(self):
        if not self.valid_context():return
        values=self.selected()
        if self.host_window.busy or not values:self.status.setText('先明列勾選候選，並等待背景空閒');return
        from .automatic_training_dialog import AutomaticTrainingDialog
        allowed={'QUEUED_FOR_UI003_PREFLIGHT','FOUND_NOT_QUEUED','REVIEWED_NEW_VERSION_CANDIDATE'}
        existing={v.get('auto_job_id') for v in values if v['state']=='DISPATCHED'}
        if any(v['state'] not in allowed|{'DISPATCHED'} for v in values) or (existing and (len(existing)!=1 or any(v['state']!='DISPATCHED' for v in values))):self.status.setText('修改版先個別核對；失效／已登錄來源請依原審核流程，既有工作與新候選分開選取');return
        self.dispatch_context=None;dialog=self.training_view()
        if existing:
            identity=next(iter(existing))
            if not identity or not self.store.get('AUTO_JOB',identity):dialog.close();self.status.setText('交接憑證找不到實際工作，請重新核對');return
            if not dialog.focus_job(identity):self.status.setText('已有工作進行中；請先安全暫停，再開啟這筆既有工作。');return
            self.status.setText('已開啟確切既有工作，成果與續跑以該介面為準');return
        self.dispatch_context=values;dialog.preflight([v['path'] for v in values],expected_hashes={v['path']:v['source_hash'] for v in values});self.status.setText('已交既有預檢，真正開始訓練仍須在該介面明確確認')

    def training_view(self):
        from .automatic_training_dialog import AutomaticTrainingDialog
        if self.training_dialog is None:
            self.training_dialog=AutomaticTrainingDialog(self.host_window);self.training_dialog.setParent(self,Qt.Dialog);self.training_dialog.job_created.connect(self.training_created)
        self.training_dialog.show();self.training_dialog.raise_();return self.training_dialog

    def training_created(self,job):
        if self.dispatch_context is None:return
        try:record_dispatch(self.store,self.dispatch_context,job['id']);self.render_current();self.status.setText('已交接實際持久工作；進度與成果以一鍵管線實際結果為準')
        except Exception as error:self.status.setText('實際工作已建立；候選交接憑證未保存：'+str(error))

    def context_closed(self):
        self._context_error='資料庫已關閉；本頁已停止讀寫，請重新開啟專案環境'
        if isValid(self):
            self.running=False;self.scan_button.setEnabled(False);self.status.setText(self._context_error)

    def valid_context(self):
        if not isValid(self):return False
        if self.store.library is not self.host_window.library:self._context_error='專案環境已切換，保留本頁輸入但停止舊作用範圍讀寫；請重新開啟'
        if getattr(self.store.library,'closed',False):self._context_error='資料庫已關閉；本頁已停止讀寫，請重新開啟專案環境'
        if not self._context_error:
            try:self.store.db.in_transaction
            except sqlite3.ProgrammingError:self._context_error='資料庫連線已關閉，本頁停止讀寫'
        if self._context_error:
            self.running=False;self.scan_button.setEnabled(False);self.status.setText(self._context_error);return False
        return True

    def reject(self):
        if self.running or self.host_window.busy:self.status.setText('背景工作中，請安全取消或等待完成後關閉');return
        if self.dirty and QMessageBox.question(self,'尚有未保存設定','捨棄目前未保存的根目錄設定並關閉？')!=QMessageBox.Yes:return
        super().reject()

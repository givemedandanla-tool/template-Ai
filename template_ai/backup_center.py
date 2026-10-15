"""One shared backup manager and serialized, application-open local scheduler."""
from datetime import datetime,timezone
from pathlib import Path
import json
import tempfile
import threading
import time
import sys

from PySide6.QtCore import QObject,Signal,QTimer,Qt,QProcess
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QWidget,QLabel,QPushButton,
    QLineEdit,QCheckBox,QComboBox,QSpinBox,QTabWidget,QTreeWidget,QTreeWidgetItem,QProgressBar,
    QFileDialog,QMessageBox,QInputDialog)

from .storage import Library
from .model import new_id
from . import relational_backup as bundle,backup_policy as policy,backup_service as service


def progress_emitter(signal):
    previous={'phase':None,'time':0.0}
    def emit(event):
        now=time.monotonic();finished=event.get('total') is not None and event.get('completed')==event['total']
        if event['phase']!=previous['phase'] or finished or now-previous['time']>=.05:
            previous.update(phase=event['phase'],time=now);signal.emit(event)
    return emit


class BackupScheduler(QObject):
    changed=Signal(str)
    phase=Signal(object)

    def __init__(self,window):
        super().__init__(window);self.window=window;self.running=False;self.closed=False
        self._password=None;self.cancel_event=threading.Event();self.last_output=None;self.status='排程未啟用'
        self.timer=QTimer(self);self.timer.setInterval(30000);self.timer.timeout.connect(self.tick)
        self.refresh()

    def refresh(self):
        if self.closed:return
        record=policy.schedule(self.window.library)
        if record and record.get('enabled'):self.timer.start();QTimer.singleShot(0,self.tick)
        else:self.timer.stop();self.set_status('排程未啟用；程式關閉時不執行')

    def set_status(self,message):self.status=message;self.changed.emit(message)

    def set_session_password(self,password):
        if not isinstance(password,str) or not 12<=len(password)<=1024:raise ValueError('密碼需12至1024字')
        self._password=password;self.refresh()

    def clear_password(self):self._password=None

    def tick(self,now=None):
        if self.closed or self.running:return
        record=policy.schedule(self.window.library)
        state=policy.due_state(record,now,self._password is not None,self.window.busy)
        labels={'DISABLED':'排程未啟用；程式關閉時不執行','WAITING':'等待已設定時間；僅此程式開啟期間可執行',
                'PASSWORD_REQUIRED':'備份已到期：本次開啟尚無密碼，請到管理中心提供或手動補做',
                'DESTINATION_OFFLINE':'備份已到期：目的地離線，未建立新備份，可接回磁碟後手動補做',
                'WAITING_IDLE':'備份已到期：等待目前背景工作完成，尚未建立新備份',
                'CLOCK_ROLLBACK_REVIEW':'系統時鐘回退，先核對排程時間；上次成功紀錄保留'}
        if state!='DUE':self.set_status(labels[state]);return
        password=self._password;root=str(self.window.library.root);snapshot=json.loads(json.dumps(record));self.cancel_event.clear();self.running=True
        emit=progress_emitter(self.phase)
        filename='template-Ai-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+new_id()[:8]+'.tabi'
        target=Path(snapshot['directory'])/filename
        def work():
            library=None
            try:
                library=Library(root)
                if policy.schedule(library)!=snapshot:raise ValueError('排程已更新，舊工作未執行')
                return {'value':service.perform_backup(library,target,password,options=snapshot['options'],
                    allow_partial=snapshot.get('allow_partial',False),retention_settings=snapshot,cancel=self.cancel_event.is_set,progress=emit)}
            except Exception as error:return {'error':str(error),'cancelled':self.cancel_event.is_set()}
            finally:
                if library:library.close()
        def done(payload):
            self.running=False;self.last_output=payload
            try:
                result=payload.get('value',{}).get('backup')
                policy.update_attempt(self.window.library,snapshot,result,payload.get('error'))
                if result:
                    extra='；憑證未能保存，請檢查成功檔' if payload['value']['history_state']!='RECORDED' else ''
                    self.set_status('排程備份實際建立且加密驗證通過'+extra)
                else:self.set_status('排程未完成：'+payload['error']+'；上次成功紀錄保留，可手動補做')
            except Exception as error:self.set_status('已取得實際結果；排程狀態未改寫：'+str(error))
        self.set_status('已送本機背景佇列，完成前不宣稱成功')
        try:self.window.run_job('本機排程備份',work,done)
        except Exception:self.running=False;raise

    def shutdown(self):
        self.closed=True;self.timer.stop();self.cancel_event.set();self._password=None


class BackupManagerDialog(QDialog):
    phase=Signal(object)

    def __init__(self,window):
        super().__init__(window);self.window=window;self.scheduler=window.backup_scheduler
        self.running=False;self.backup_plan=None;self.restore_plan=None;self.last_restore=None
        self.cancel_event=threading.Event();self.password_failures=0;self.failures={};self.offset=0;self.emit_progress=progress_emitter(self.phase)
        self.setWindowTitle('本機完整關聯備份／驗證／安全還原');self.resize(1120,820)
        layout=QVBoxLayout(self)
        notice=QLabel('只備份已保存的客戶、模板／尺寸Logo庫、來源與訓練狀態；當次未保存輸入不在範圍內。備份預設留本機。密碼遺失可能無法還原，沒有萬用解鎖。');notice.setWordWrap(True);layout.addWidget(notice)
        row=QHBoxLayout();row.addWidget(QLabel('本次加密／解密密碼'))
        self.password=QLineEdit();self.password.setEchoMode(QLineEdit.Password);self.password.setPlaceholderText('12至1024字，不寫入設定、日誌或備份');self.password.textChanged.connect(self.invalidate_restore);row.addWidget(self.password,1)
        self.remember=QCheckBox('此程式開啟期間供排程使用');self.remember.toggled.connect(self.remember_changed);row.addWidget(self.remember);layout.addLayout(row)
        self.tabs=QTabWidget();layout.addWidget(self.tabs,1)
        self.build_backup();self.build_restore();self.build_schedule();self.build_history()
        self.status=QLabel('請先核對範圍及依賴，再建立或還原；驗證不等於正式輸出通過。');self.status.setTextFormat(Qt.PlainText);self.status.setWordWrap(True);layout.addWidget(self.status)
        self.progress=QProgressBar();self.progress.setRange(0,1);self.progress.setValue(0);layout.addWidget(self.progress)
        bar=QHBoxLayout();cancel=QPushButton('安全取消目前備份／還原');cancel.clicked.connect(self.cancel_work);bar.addWidget(cancel)
        close=QPushButton('關閉');close.clicked.connect(self.reject);bar.addWidget(close);layout.addLayout(bar)
        self.phase.connect(self.show_phase,Qt.QueuedConnection);self.scheduler.phase.connect(self.show_phase,Qt.QueuedConnection)
        self.scheduler.changed.connect(self.show_schedule_status);self.refresh_history();self.load_schedule(True)

    def button(self,bar,text,action):
        button=QPushButton(text);button.clicked.connect(action);bar.addWidget(button);return button

    def build_backup(self):
        widget=QWidget();layout=QVBoxLayout(widget);self.groups={}
        for key,text in [('customers','客戶主檔、別名、人物／公司及確切版型關聯'),('templates','模板全部版本、各實體尺寸獨立Logo庫與資產'),('training','來源索引、規則／模型、標記及訓練檢查點')]:
            check=QCheckBox(text+'（共用一致性資料庫）');check.setChecked(True);check.toggled.connect(self.invalidate_backup);layout.addWidget(check);self.groups[key]=check
        self.sources=QCheckBox('已確認有權一併保存登錄的原始來源／外部資產');self.sources.toggled.connect(self.invalidate_backup);layout.addWidget(self.sources)
        self.fonts=QCheckBox('已確認有權在本機備份及移轉匯入字型；不安裝系統字型');self.fonts.toggled.connect(self.invalidate_backup);layout.addWidget(self.fonts)
        bar=QHBoxLayout();bar.addWidget(QLabel('單包資料預算'))
        self.limit=QComboBox()
        for amount in (16,64,256):self.limit.addItem(f'{amount} MiB',amount*1024*1024)
        self.limit.setCurrentIndex(1);self.limit.currentIndexChanged.connect(self.invalidate_backup);bar.addWidget(self.limit)
        self.partial=QCheckBox('明確接受部分包：不能完整離線還原');bar.addWidget(self.partial);layout.addLayout(bar)
        bar=QHBoxLayout();self.button(bar,'核對範圍／依賴與實際資產',self.preview_backup);self.create_button=self.button(bar,'確認範圍並立即加密備份',self.create);self.create_button.setEnabled(False);layout.addLayout(bar)
        self.backup_tree=QTreeWidget();self.backup_tree.setHeaderLabels(['項目','實際隨包帶入','外部／缺失或原因','狀態']);layout.addWidget(self.backup_tree,1)
        self.tabs.addTab(widget,'立即備份')

    def build_restore(self):
        widget=QWidget();layout=QVBoxLayout(widget);row=QHBoxLayout()
        self.archive=QLineEdit();self.archive.setPlaceholderText('選擇可信的本機.tabi備份');self.archive.textChanged.connect(self.archive_changed);row.addWidget(self.archive,1);self.button(row,'選取備份',self.choose_archive);layout.addLayout(row)
        self.trusted=QCheckBox('已核對來源可信，並有權還原及使用其中個資／資產');self.trusted.toggled.connect(self.invalidate_restore);layout.addWidget(self.trusted)
        self.mode=QComboBox();self.mode.addItems(['還原到新空位置','現有環境先比對，再還原到獨立新副本']);self.mode.currentIndexChanged.connect(self.invalidate_restore);layout.addWidget(self.mode)
        label=QLabel('兩種模式均保留目前較新的資料。現有版本差異只供核對，無自動合併、回寫或覆蓋；新副本需重新檢查字型／來源／學習有效性及正式輸出。');label.setWordWrap(True);layout.addWidget(label)
        self.restore_tree=QTreeWidget();self.restore_tree.setHeaderLabels(['分類','備份資料量','目前資料量','版本／缺失差異']);layout.addWidget(self.restore_tree,1)
        self.restore_ack=QCheckBox('已逐類核對差異；接受隔離副本及未驗證項目，保留目前環境');layout.addWidget(self.restore_ack)
        row=QHBoxLayout();self.button(row,'解密驗證與還原前差異預覽',self.preview_restore);self.restore_button=self.button(row,'確認並還原到新位置',self.restore);self.restore_button.setEnabled(False)
        self.open_button=self.button(row,'在獨立視窗檢查還原副本',self.open_copy);self.open_button.setEnabled(False);layout.addLayout(row)
        self.tabs.addTab(widget,'還原／移轉')

    def build_schedule(self):
        widget=QWidget();layout=QVBoxLayout(widget);form=QFormLayout()
        self.destination=QLineEdit();row=QHBoxLayout();row.addWidget(self.destination,1);self.button(row,'選擇本機／外接磁碟位置',self.choose_destination);form.addRow('備份目的地',row)
        self.interval=QSpinBox();self.interval.setRange(1,525600);self.interval.setValue(1440);form.addRow('間隔分鐘',self.interval)
        self.keep=QSpinBox();self.keep.setRange(1,100);self.keep.setValue(3);form.addRow('至少保留最新份數',self.keep)
        self.days=QSpinBox();self.days.setRange(0,36500);form.addRow('另外保留最近天數（0不加）',self.days)
        layout.addLayout(form);self.enabled=QCheckBox('啟用本機排程及明列的安全保留政策');layout.addWidget(self.enabled)
        label=QLabel('只在此程式開啟、已有本次密碼且背景空閒時執行。關閉、休眠、目的地離線或密碼不足可能錯過；不註冊作業系統排程、不儲存密碼。輪替只處理本程式已記錄的同內容檔，至少保留可驗證完整備份。');label.setWordWrap(True);layout.addWidget(label)
        self.schedule_status=QLabel(self.scheduler.status);self.schedule_status.setTextFormat(Qt.PlainText);self.schedule_status.setWordWrap(True);layout.addWidget(self.schedule_status)
        row=QHBoxLayout();self.button(row,'保存排程（沿用立即備份頁已明列範圍）',self.save_schedule);self.button(row,'提供本次密碼／檢查到期',self.arm);self.button(row,'立即補做已到期排程',self.run_due);self.button(row,'按設定核對並輪替舊檔',self.prune);layout.addLayout(row)
        layout.addStretch();self.tabs.addTab(widget,'排程／保留')

    def build_history(self):
        widget=QWidget();layout=QVBoxLayout(widget)
        label=QLabel('最近最多500個成功憑證，每頁50筆；先前建立成功不等於目前檔案仍完整。移轉帶入的舊憑證不會自動取得刪檔權利。');label.setWordWrap(True);layout.addWidget(label)
        self.history_tree=QTreeWidget();self.history_tree.setHeaderLabels(['檔名／建立時間','範圍','上次狀態／還原測試','目前位置']);layout.addWidget(self.history_tree,1)
        row=QHBoxLayout();self.button(row,'上一頁',lambda:self.page(-1));self.button(row,'下一頁',lambda:self.page(1));self.button(row,'重新讀取憑證',self.refresh_history);self.button(row,'以本次密碼重新驗證',self.verify);self.button(row,'真正隔離測試還原',self.test_restore);self.button(row,'使用所選包做還原預覽',self.use_record);self.button(row,'檢視輪替恢復區',self.show_recovery);layout.addLayout(row)
        self.tabs.addTab(widget,'備份清單／驗證')

    def options(self):return dict(include_sources=self.sources.isChecked(),include_fonts=self.fonts.isChecked(),limit_bytes=self.limit.currentData(),**{k:w.isChecked() for k,w in self.groups.items()})
    def secret(self):
        value=self.password.text() or (self.scheduler._password if self.remember.isChecked() else '')
        if not isinstance(value,str) or not 12<=len(value)<=1024:raise ValueError('請先提供12至1024字的本次密碼；遺失無法保證還原')
        return value

    def secret_for(self,archive):
        if self.failures.get(str(Path(archive).resolve()),0)>=3:raise ValueError('本次此包驗證已失敗3次，請先核對密碼／來源，不自動重試')
        return self.secret()

    def guarded(self,work):
        try:return work()
        except Exception as error:self.status.setText('未完成：'+str(error))

    def invalidate_backup(self,*_):
        self.backup_plan=None
        if hasattr(self,'create_button'):self.create_button.setEnabled(False)

    def invalidate_restore(self,*_):
        self.restore_plan=None
        if hasattr(self,'restore_ack'):self.restore_ack.setChecked(False)
        if hasattr(self,'restore_button'):self.restore_button.setEnabled(False)

    def archive_changed(self,*_):self.invalidate_restore()

    def remember_changed(self,checked):
        if not checked:self.scheduler.clear_password()

    def start(self,message,work,done,clear_secret=False,archive_key=None):
        if self.running or self.window.busy:self.status.setText('已有背景工作；保留輸入，尚未開始');return
        self.running=True;self.cancel_event.clear();self.emit_progress=progress_emitter(self.phase);self.tabs.setEnabled(False);self.progress.setRange(0,0);self.status.setText(message)
        root=str(self.window.library.root)
        def run():
            library=None
            try:library=Library(root);return {'value':work(library)}
            except Exception as error:return {'error':str(error),'cancelled':self.cancel_event.is_set()}
            finally:
                if library:library.close()
        def finished(payload):
            self.running=False;self.tabs.setEnabled(True);self.progress.setRange(0,1);self.progress.setValue(0)
            if 'error' in payload:
                self.status.setText('未完成：'+payload['error'])
                if '密碼錯誤或備份損壞' in payload['error']:
                    self.password_failures+=1
                    if archive_key:self.failures[str(Path(archive_key).resolve())]=self.failures.get(str(Path(archive_key).resolve()),0)+1
            else:
                try:
                    done(payload['value']);self.progress.setValue(1)
                    if archive_key:self.failures[str(Path(archive_key).resolve())]=0
                except Exception as error:self.status.setText('結果未套用：'+str(error))
            if clear_secret and not self.remember.isChecked():self.password.clear()
            self.refresh_history()
            self.window.statusBar().showMessage(self.status.text().splitlines()[0])
        try:self.window.run_job(message,run,finished)
        except Exception:
            self.running=False;self.tabs.setEnabled(True);self.progress.setRange(0,1);raise

    def show_phase(self,event):
        labels={'PLAN_VERIFY':'核對實際來源／資產','DATABASE_SNAPSHOT':'建立並檢查SQLite一致性快照','PACK_ASSETS':'封裝已核對資產','ENCRYPT':'加密完整封裝','AUTHENTICATE':'驗證加密內容','PUBLISH_VERIFY':'發布前再次核對版本／磁碟檔','RESTORE_AUTHENTICATE':'解密並核對每個實際成員','RESTORE_EXTRACT':'重建隔離資產','RESTORE_RELATIONS':'檢查／移轉本機關聯與路徑','RESTORE_PUBLISH_ISOLATED':'完成隔離副本，保留目前環境'}
        message=labels.get(event['phase'],'安全處理中')
        if 'completed' in event:message+=f" · 實際 {event['completed']}/{event['total']} 資產；整項尚未完成"
        elif 'verified_assets' in event:message+=f" · 已核對{event['verified_assets']}資產"
        self.status.setText(message)

    def preview_backup(self):
        options=self.options()
        self.start('核對已保存資料與所有必要資產',lambda lib:bundle.plan_backup(lib,**options,cancel=self.cancel_event.is_set,progress=self.emit_progress),self.show_backup_plan)

    def show_backup_plan(self,plan):
        self.backup_plan=plan;self.backup_tree.clear()
        if plan['state']!='PLANNED':self.status.setText('範圍被關聯依賴阻擋：'+'；'.join(plan['reasons']));return
        sources=sum(s['included'] for s in plan['sources']);notes=plan['notes']
        for values in [('一致性資料庫',f"{plan['database_bytes']/1024/1024:.2f} MiB",'客戶／模板與Logo／訓練共用完整快照','已核對'),
                       ('實際資產',str(len({e['member'] for e in plan['entries']})),f"{plan['asset_bytes']/1024/1024:.2f} MiB",'已核對bytes／指紋'),
                       ('原始來源',str(sources),str(len(plan['sources'])-sources)+'份未帶入','各source ID／原名保留'),
                       ('資源估計',f"封裝緩衝估算{plan['estimated_extra_memory_bytes']/1024/1024:.1f} MiB",f"暫存磁碟約{plan['estimated_stage_disk_bytes']/1024/1024:.1f} MiB",'非完整RAM上限／硬體實測')]:self.backup_tree.addTopLevelItem(QTreeWidgetItem(values))
        assets=QTreeWidgetItem(['逐件資產清單','','','已核對，建立時才實際封裝']);self.backup_tree.addTopLevelItem(assets)
        for entry in plan['entries']:
            node=QTreeWidgetItem([Path(entry['origin']).name,f"{entry['bytes']} bytes",entry['origin'],'預定隨包帶入']);node.setToolTip(3,entry['sha256']);assets.addChild(node)
        registrations=QTreeWidgetItem(['逐件來源登錄','','','相同bytes不合併source ID／原名']);self.backup_tree.addTopLevelItem(registrations)
        for source in plan['sources']:registrations.addChild(QTreeWidgetItem([Path(source['original_path']).name,'預定隨包帶入' if source['included'] else '只有外部索引',source['current_path'],source['id']]))
        for note in notes:self.backup_tree.addTopLevelItem(QTreeWidgetItem(['必要外部／缺失',note.get('source_id',''),note.get('path',''),{'FONT_BACKUP_RIGHTS_NOT_CONFIRMED':'字型備份權利未勾選','ORIGINAL_BACKUP_RIGHTS_NOT_CONFIRMED':'原始來源未勾選','EXTERNAL_ASSET_RIGHTS_NOT_CONFIRMED':'外部資產未勾選','REFERENCED_ASSET_MISSING':'必要資產失聯'}.get(note['state'],'未帶入／需核對')]))
        self.create_button.setEnabled(True);self.status.setText('完整關聯資產可帶入；建立後仍需隔離還原測試' if plan['complete'] else '部分範圍／缺資產：不能完整離線還原；可修正或明確選擇部分包')

    def create(self):
        def action():
            if not self.backup_plan or self.backup_plan['state']!='PLANNED':raise ValueError('先核對完整範圍／依賴')
            plan=self.backup_plan;password=self.secret();partial=self.partial.isChecked()
            path,_=QFileDialog.getSaveFileName(self,'選擇本機新備份檔；不覆寫既有檔','','關聯加密備份 (*.tabi)')
            if not path:return
            if not path.lower().endswith('.tabi'):path+='.tabi'
            if QMessageBox.question(self,'確認備份範圍',f"{'完整資產包' if plan['complete'] else '部分包，無法完整離線還原'}；{len(plan['entries'])}個資產映射。\n已確認資料及來源／字型保存權利？密碼與備份分開保管，遺失可能無法還原。")!=QMessageBox.Yes:return
            self.start('建立完整加密備份，完成前不顯示成功',lambda lib:service.perform_backup(lib,path,password,plan=plan,allow_partial=partial,cancel=self.cancel_event.is_set,progress=self.emit_progress),self.backup_done,True)
        self.guarded(action)

    def backup_done(self,result):
        self.invalidate_backup();artifact=result['backup']
        self.status.setText(f"已建立並驗證加密備份：{artifact['path']}\n{'完整資產範圍' if artifact['complete'] else '部分包'}；尚未完成隔離測試還原。"+('憑證未保存，請保留成功檔並檢查磁碟。' if result['history_state']!='RECORDED' else '成功憑證已保存。'))

    def choose_archive(self):
        path,_=QFileDialog.getOpenFileName(self,'選擇可信本機備份','','關聯加密備份 (*.tabi)')
        if path:self.archive.setText(path)

    def preview_restore(self):
        def action():
            archive=self.archive.text();password=self.secret_for(archive);trusted=self.trusted.isChecked();existing=str(self.window.library.root) if self.mode.currentIndex()==1 else None
            self.start('核對備份來源、加密及現有版本差異',lambda lib:bundle.inspect_restore(archive,password,trusted,existing,self.cancel_event.is_set),self.show_restore_plan,archive_key=archive)
        self.guarded(action)

    def show_restore_plan(self,plan):
        self.restore_plan=plan;self.restore_ack.setChecked(False);self.restore_tree.clear()
        for row in plan['database_rows']:
            label={'customers':'客戶主檔','customer_fields':'人物／公司欄位','customer_styles':'尺寸／版型關聯','sources':'原始來源索引','artworks':'作品／標記','templates':'模板全部版本','logos':'尺寸Logo庫','font_assets':'匯入字型','training_records':'模型／規則／檢查點','customer_code_aliases':'舊客戶碼別名'}.get(row['category'],row['category'])
            text={'IDENTICAL_ROWS':'資料相同','BACKUP_ONLY':'只在備份中','CURRENT_ONLY':'僅目前環境','SCHEMA_DIFFERENT':'格式版本不同，需另行核對','DIFFERENT_REQUIRES_REVIEW':'有新值／版本差異，保留目前資料'}.get(row['state'],'未核對')
            if row['different_rows'] is not None:text+=f"；不同{row['different_rows']}／僅備份{row['only_backup']}／僅目前{row['only_current']}"
            self.restore_tree.addTopLevelItem(QTreeWidgetItem([label,str(row['backup_rows']),str(row['current_rows']),text]))
        for note in plan['missing_or_external']:self.restore_tree.addTopLevelItem(QTreeWidgetItem(['外部／缺資產','未隨包帶入','',note.get('path',note.get('state','未知'))]))
        self.restore_button.setEnabled(True);self.status.setText('還原前預覽完成；目前環境未修改。核對後另行確認新位置，缺資產仍不能宣稱完整可用。')

    def restore(self):
        def action():
            if not self.restore_plan or not self.restore_ack.isChecked():raise ValueError('先完成還原前逐類預覽及明確核對')
            plan=self.restore_plan;password=self.secret_for(plan['archive']);partial=self.partial.isChecked()
            parent=QFileDialog.getExistingDirectory(self,'選擇新副本的上層本機資料夾')
            if not parent:return
            name,ok=QInputDialog.getText(self,'新副本資料夾','不存在的新資料夾名稱',text='template-Ai-restored-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
            if not ok:return
            if not name or len(name)>80 or len(Path(name).parts)!=1 or not bundle._portable_member(name):raise ValueError('需可移轉Windows的單一新資料夾名稱')
            target=Path(parent)/name
            if target.resolve().is_relative_to(self.window.library.root):raise ValueError('新副本請放目前資料庫之外，不嵌入現在環境')
            if QMessageBox.question(self,'確認隔離還原','目前資料與較新進度保留。只在明列的新目錄重建；不自動合併，不安裝系統字型。新副本還須重新驗證來源／學習與正式輸出。是否確認？')!=QMessageBox.Yes:return
            def work(lib):
                result=bundle.restore_bundle(plan['archive'],target,password,True,partial,self.cancel_event.is_set,self.emit_progress,plan['archive_sha256'])
                result['relations']=service.relational_checks(result['library_root']);return result
            self.start('隔離重建新副本；原環境保留',work,self.restore_done,True,plan['archive'])
        self.guarded(action)

    def restore_done(self,result):
        self.last_restore=result;self.open_button.setEnabled(True);self.invalidate_restore()
        self.status.setText(f"隔離還原完成：{result['library_root']}\n資料庫完整性通過；{'資產完整' if result['complete_assets'] else '部分資產，需補檔'}；{result['relations']['state']}。學習／正式輸出仍需新鮮驗證，尚未切換目前環境。")

    def open_copy(self):
        def action():
            if not self.last_restore:raise ValueError('先完成隔離還原')
            root=Path(self.last_restore['library_root'])
            if (root.parent/'RESTORE_STAGING_NOT_ACTIVE').exists() or not (root.parent/'RESTORE_COMPLETE.json').is_file():raise ValueError('副本尚未完整完成，不能啟用')
            started=QProcess.startDetached(sys.executable,[str(Path(__file__).resolve().parents[1]/'app.py'),'--data-dir',str(root)])
            if not (started[0] if isinstance(started,tuple) else started):raise ValueError('獨立視窗未啟動，目前環境仍保留')
            self.status.setText('已要求在獨立視窗檢查副本；目前環境保留，可關閉副本返回。啟動不代表品質已通過。')
        self.guarded(action)

    def choose_destination(self):
        path=QFileDialog.getExistingDirectory(self,'選擇本機／外接磁碟備份資料夾')
        if path:self.destination.setText(path)

    def load_schedule(self,initial=False):
        record=policy.schedule(self.window.library)
        if record:
            self.destination.setText(record['directory']);self.interval.setValue(max(1,record['interval_seconds']//60));self.keep.setValue(record['retain_count']);self.days.setValue(record['retain_days']);self.enabled.setChecked(record['enabled'])
            stamp=lambda value:datetime.fromtimestamp(value,timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if value else '尚無'
            self.schedule_status.setText(self.scheduler.status+f"\n上次成功：{stamp(record.get('last_success'))}；下次計畫：{stamp(record['next_due'])}；關閉程式執行能力：不支援")
            if initial:
                options=record['options'];self.sources.setChecked(options.get('include_sources',False));self.fonts.setChecked(options.get('include_fonts',False));self.partial.setChecked(record.get('allow_partial',False))
                for key,control in self.groups.items():control.setChecked(options.get(key,True))
                index=self.limit.findData(options.get('limit_bytes',64*1024*1024))
                if index>=0:self.limit.setCurrentIndex(index)

    def show_schedule_status(self,message):
        record=policy.schedule(self.window.library)
        if record:
            stamp=lambda value:datetime.fromtimestamp(value,timezone.utc).strftime('%Y-%m-%d %H:%M UTC') if value else '尚無'
            message+=f"\n上次成功：{stamp(record.get('last_success'))}；下次計畫：{stamp(record['next_due'])}；程式關閉時不執行"
        self.schedule_status.setText(message)

    def save_schedule(self):
        def action():
            if self.window.busy:raise ValueError('先在目前工作面板安全取消並等完成，再保存排程')
            old=policy.schedule(self.window.library);options=self.options()
            if not all(options[k] for k in ('customers','templates','training')):raise ValueError('這三類共用一致性資料庫；先恢復完整資料庫範圍')
            if QMessageBox.question(self,'確認本機排程與保留','沿用立即備份頁明列的來源／字型權利及資料預算。只在程式開啟且已提供本次密碼時執行；依最新份數與天數輪替本程式成功備份，至少保留可驗證完整包。是否保存？')!=QMessageBox.Yes:return
            policy.configure(self.window.library,self.destination.text(),self.interval.value()*60,self.keep.value(),self.days.value(),options,self.enabled.isChecked(),(old or {}).get('revision',0),allow_partial=self.partial.isChecked())
            self.invalidate_backup();self.scheduler.refresh()
            if self.remember.isChecked():self.scheduler.set_session_password(self.secret())
            self.load_schedule();self.status.setText('排程／保留已保存；密碼未持久化，不代表關閉程式也會執行。')
        self.guarded(action)

    def arm(self):
        def action():
            password=self.secret();self.remember.setChecked(True);self.scheduler.set_session_password(password);self.scheduler.tick();self.load_schedule()
        self.guarded(action)

    def run_due(self):
        def action():
            password=self.secret();self.remember.setChecked(True);self.scheduler.set_session_password(password);self.scheduler.tick();self.load_schedule()
        self.guarded(action)

    def prune(self):
        def action():
            record=policy.schedule(self.window.library)
            if not record:raise ValueError('先保存目的地與保留政策')
            password=self.secret()
            if QMessageBox.question(self,'確認精確保留範圍','只處理所設目的地內，本程式成功憑證與目前sha完全相符的舊備份；未知／異動檔保留，至少留可驗證完整包。是否執行？')!=QMessageBox.Yes:return
            self.start('核對並輪替已記錄舊備份',lambda lib:policy.retention(lib,record['directory'],password,record['retain_count'],record['retain_days'],True,cancel=self.cancel_event.is_set),lambda result:self.status.setText('保留處置：'+result['state']+f"；實際釋放{result['space_reclaimed']} bytes，異動／失敗保留恢復區"),True)
        self.guarded(action)

    def refresh_history(self):
        if self.running:return
        self.history_tree.clear();rows=list(reversed(policy.history(self.window.library)));self.offset=min(self.offset,max(0,((len(rows)-1)//50)*50))
        for record in rows[self.offset:self.offset+50]:
            state=record['state']+('（移轉帶入，無自動刪檔權利）' if not record.get('owned_by_app') else '')
            node=QTreeWidgetItem([Path(record['path']).name+' · '+datetime.fromtimestamp(record['created']).isoformat(timespec='seconds'),record['scope'],state+('／已測試還原' if record['test_restore'] else '／未測試還原'),record['path']]);node.setData(0,Qt.UserRole,record);self.history_tree.addTopLevelItem(node)

    def selected_record(self):
        node=self.history_tree.currentItem()
        if not node:raise ValueError('先選一個確切成功憑證')
        return node.data(0,Qt.UserRole)

    def page(self,delta):self.offset=max(0,self.offset+50*delta);self.refresh_history()

    def verify(self):
        def action():
            record=self.selected_record();password=self.secret_for(record['path'])
            self.start('重新驗證實際備份檔與密碼',lambda lib:policy.verify_record(record,password),lambda result:self.status.setText('實際密碼／內容及資料庫完整性通過；尚未執行隔離還原，未宣稱可直接正式輸出。'),True,record['path'])
        self.guarded(action)

    def test_restore(self):
        def action():
            record=self.selected_record();password=self.secret_for(record['path'])
            self.start('真正建立隔離測試副本並驗證關聯',lambda lib:service.test_restore(lib,record,password,self.cancel_event.is_set,self.emit_progress),lambda result:self.status.setText('隔離測試還原已完成，暫時副本已移除；'+result['validation']['state']+'；原備份保留，正式輸出仍須驗證。'),True,record['path'])
        self.guarded(action)

    def use_record(self):
        def action():
            self.archive.setText(self.selected_record()['path']);self.tabs.setCurrentIndex(1)
        self.guarded(action)

    def show_recovery(self):
        def action():
            record=policy.schedule(self.window.library)
            if not record:raise ValueError('先選擇備份目的地')
            rows=policy.recovery_entries(record['directory']);self.status.setText(f'輪替恢復區有{len(rows)}筆意圖／結果；保留的.tabi可從還原頁明確選取，未自動刪除。')
        self.guarded(action)

    def cancel_work(self):
        if self.running:self.cancel_event.set();self.status.setText('已請求在安全階段停止；成功檔不會被連帶刪除')
        elif self.scheduler.running:self.scheduler.cancel_event.set();self.status.setText('已請求停止排程；以實際已完成結果為準')

    def reject(self):
        if self.running:self.cancel_work();return
        self.password.clear();super().reject()

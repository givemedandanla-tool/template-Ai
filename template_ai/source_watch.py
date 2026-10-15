"""Qt notifications are bounded hints; one shared worker reconciles persisted explicit roots."""
from collections import deque
from pathlib import Path
import threading,time
from PySide6.QtCore import QObject,QFileSystemWatcher,QTimer,Signal
from .training_store import TrainingStore,digest
from .source_scan import active_roots,known_sources,scan_files,save_scan,configure_root
from .source_links import ScanCancelled


class SourceWatchService(QObject):
    updated=Signal(object)

    def __init__(self,window):
        super().__init__(window);self.window=window;self.closed=False;self.running=False;self.current_root=None;self.last_result=None;self.last_status='尚未掃描'
        self.pending=deque();self.reasons={};self.roots={};self.configs={};self.pause_pending=set();self.remove_pending=set();self.cancel_event=threading.Event();self.statuses={}
        self.watcher=QFileSystemWatcher(self);self.watcher.directoryChanged.connect(self.hint);self.watcher.fileChanged.connect(self.hint)
        self.debounce=QTimer(self);self.debounce.setSingleShot(True);self.debounce.setInterval(600);self.debounce.timeout.connect(self.dispatch)
        self.timer=QTimer(self);self.timer.setInterval(30_000);self.timer.timeout.connect(self.tick);self.timer.start()
        QTimer.singleShot(0,self.startup)

    def status(self,identity,state,message):
        self.last_status=message;self.statuses[identity]=dict(root_id=identity,state=state,message=message,time=time.time());self.updated.emit(self.statuses[identity])

    def sync(self):
        if self.closed:return
        store=TrainingStore.bind(self.window.library);roots=active_roots(store);self.roots={r['id']:r for r in roots};wanted=set()
        for root in roots:
            identity=root['id'];config=digest({k:root.get(k) for k in ['path','recursive','extensions','excludes','mode','enabled','requires_reconnect']})
            enabled=root.get('enabled') and root.get('mode')=='AUTO_PRECHECK' and not root.get('requires_reconnect') and identity not in self.pause_pending
            if enabled:
                if self.configs.get(identity)!=config:self.mark(identity,'STARTUP_OR_CONFIGURATION')
                directories=[root['path']]+((root.get('last_scan') or {}).get('directories',[]) if root.get('recursive') else [])
                for value in directories:
                    path=Path(value)
                    if not path.is_symlink() and path.is_dir() and path.resolve().is_relative_to(Path(root['path']).resolve()):wanted.add(str(path))
            self.configs[identity]=config
        existing=set(self.watcher.directories())|set(self.watcher.files());chosen=set(sorted(wanted)[:128]);removed=existing-chosen
        if removed:self.watcher.removePaths(sorted(removed))
        failed=self.watcher.addPaths(sorted(chosen-existing)) if chosen-existing else []
        if failed or len(wanted)>128:self.status('WATCH_CAPACITY','PERIODIC_FALLBACK','部分提示點不可監看／超過128個；仍每30秒有界補掃，通知不代表新增檔案數')
        self.pending=deque(identity for identity in self.pending if identity in self.roots);self.reasons={i:r for i,r in self.reasons.items() if i in self.roots}

    def startup(self):
        if self.closed:return
        try:self.sync();self.dispatch()
        except Exception as error:self.status('SERVICE','BLOCKED','監看尚未啟動：'+str(error))

    def mark(self,identity,reason):
        if self.closed or identity in self.pause_pending:return
        if identity not in self.reasons:self.reasons[identity]=set();self.pending.append(identity)
        self.reasons[identity].add(reason)
        if not self.debounce.isActive():self.debounce.start()

    def hint(self,path):
        if self.closed:return
        for identity,root in self.roots.items():
            if root.get('enabled') and root.get('mode')=='AUTO_PRECHECK' and Path(path).is_relative_to(Path(root['path'])):self.mark(identity,'FILESYSTEM_HINT')

    def tick(self):
        if self.closed:return
        try:
            self.sync()
            for identity,root in self.roots.items():
                if root.get('enabled') and root.get('mode')=='AUTO_PRECHECK' and not root.get('requires_reconnect'):self.mark(identity,'PERIODIC_RECONCILIATION')
            self.dispatch()
        except Exception as error:self.status('SERVICE','BLOCKED','補掃未完成：'+str(error))

    def request_manual(self,identity):
        self.sync()
        if identity not in self.roots:raise ValueError('來源根目錄已移除，未掃描')
        self.mark(identity,'MANUAL');self.dispatch()

    def pause(self,identity):
        if self.running and self.current_root==identity:
            self.pause_pending.add(identity);self.cancel_event.set();self.status(identity,'PAUSING','正在安全取消本次工作，完成後停用後續監看');return
        root=TrainingStore.bind(self.window.library).get('SCAN_ROOT',identity)
        configure_root(TrainingStore.bind(self.window.library),root,enabled=False);self.reasons.pop(identity,None);self.pending=deque(i for i in self.pending if i!=identity);self.sync();self.status(identity,'PAUSED','已暫停監看；來源、客戶、既有訓練與候選保留')

    def remove(self,identity):
        if self.running and self.current_root==identity:
            self.remove_pending.add(identity);self.pause(identity);return
        store=TrainingStore.bind(self.window.library);root=store.get('SCAN_ROOT',identity)
        configure_root(store,root,archive=True);self.reasons.pop(identity,None);self.pending=deque(i for i in self.pending if i!=identity);self.sync();self.status(identity,'REMOVED','已停止此根目錄後續掃描；原來源、客戶、模板、訓練及候選歷史均保留')

    def dispatch(self):
        if self.closed or self.running or not self.pending:return
        if self.window.busy:
            self.status('SERVICE','WAITING_BACKGROUND_SLOT','其他背景工作執行中；保留先進先出待掃根目錄');self.debounce.start(1000);return
        self.debounce.stop()
        identity=self.pending.popleft();reasons=self.reasons.pop(identity,set());root=TrainingStore.bind(self.window.library).get('SCAN_ROOT',identity)
        automatic='MANUAL' not in reasons
        if not root or root.get('archived') or identity in self.pause_pending:return
        if automatic and (not root.get('enabled') or root.get('mode')!='AUTO_PRECHECK' or root.get('requires_reconnect')):return
        self.running=True;self.current_root=identity;self.cancel_event.clear();data_root=self.window.library.root
        def work():
            from .storage import Library
            library=None
            try:
                library=Library(data_root);store=TrainingStore(library)
                if store.get('SCAN_ROOT',identity)!=root:raise ValueError('根目錄設定已改變，未開始掃描')
                known,index=known_sources(library,root)
                result=scan_files(root,known,self.cancel_event.is_set,content_lookup=lambda content:library.db.execute('SELECT 1 FROM contents WHERE hash=?',(content,)).fetchone() is not None)
                result.update(source_index_digest=index,timestamp=result.get('timestamp',time.time()))
                if self.cancel_event.is_set():return dict(result=result,cancelled=True)
                saved=save_scan(store,root,result,automatic=automatic,cancel=self.cancel_event.is_set)
                return dict(result=result,root=saved,automatic=automatic)
            except ScanCancelled:return dict(cancelled=True)
            except Exception as error:return dict(error=str(error),cancelled=self.cancel_event.is_set())
            finally:
                if library:library.close()
        def done(payload):
            self.running=False;self.current_root=None;self.last_result=payload
            if self.closed:return
            if identity in self.pause_pending:
                self.pause_pending.remove(identity)
                try:
                    if identity in self.remove_pending:self.remove_pending.remove(identity);self.remove(identity)
                    else:self.pause(identity)
                except Exception as error:self.status(identity,'PAUSE_FAILED','本次已取消；停用設定未保存：'+str(error))
            elif payload.get('cancelled'):self.status(identity,'CANCELLED','本次已取消；原資料保留，監看設定維持，可暫停後續工作')
            elif payload.get('error'):self.status(identity,'FAILED','掃描／候選保存失敗：'+payload['error'])
            else:
                result=payload['result'];self.status(identity,result['state'],f"本次核對{result['scanned_entries']}個目錄項／{len(result['entries'])}個檔案處置；"+('已保存候選；未開始訓練' if result.get('complete') else '仍有離線／未核驗／部分範圍，不宣稱完成'))
            self.window.statusBar().showMessage(self.last_status)
            try:self.sync()
            except Exception as error:self.status(identity,'REFRESH_FAILED','結果已取得，監看清單需重新載入：'+str(error))
            if self.pending:self.debounce.start(600)
        self.status(identity,'SCANNING','核對實際內容與版本中；檔案通知只是提示，尚未完成')
        try:self.window.run_job('來源安全增量補掃',work,done)
        except Exception:
            self.running=False;self.current_root=None;self.mark(identity,'WORKER_START_RETRY');raise

    def cancel(self):self.cancel_event.set()

    def cancel_root(self,identity):
        if self.running and self.current_root==identity:self.cancel()
        else:
            self.reasons.pop(identity,None);self.pending=deque(i for i in self.pending if i!=identity);self.status(identity,'CANCELLED','已取消待掃請求，監看設定維持')

    def shutdown(self):
        self.closed=True;self.cancel_event.set();self.timer.stop();self.debounce.stop();paths=self.watcher.directories()+self.watcher.files()
        if paths:self.watcher.removePaths(paths)
        self.pending.clear();self.reasons.clear()

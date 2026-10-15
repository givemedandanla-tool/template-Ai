"""Qt heartbeat and thread-safe admission. Runtime policy is separate from learning epochs."""
from collections import deque
import json,math,sqlite3,threading,time
from PySide6.QtCore import QObject,QTimer,QEvent
from PySide6.QtWidgets import QApplication,QWidget
from shiboken6 import isValid
from .runtime_resources import ResourceMonitor,AdmissionControl,ResourceDecision

KEY='runtime_execution_policy'
DEFAULT=dict(version=1,profile='LOW_LOAD',paused=False,revision=0)


class RuntimeSupervisor(QObject):
    def __init__(self,window,monitor=None,clock=time.monotonic,start=True):
        super().__init__(window);self.window=window;self.library=window.library;self.clock=clock;self.closed_event=threading.Event();self.pause_event=threading.Event();self.monitor=monitor or ResourceMonitor(self.library.root);self.control=AdmissionControl(clock=clock);self.foreground_control=AdmissionControl(clock=clock)
        self.policy=dict(DEFAULT);self.policy_raw=None;self.policy_error=None;self.pending_pause=False;self.lag_samples=deque(maxlen=20);self.lag_ewma=0.0;self.last_pulse=clock();self.last_interaction=-math.inf;self.last_policy_check=-math.inf;self.ready_after=clock()+.25
        self.timer=QTimer(self);self.timer.setInterval(250);self.timer.timeout.connect(self.pulse);self.library.observe_close(self.shutdown)
        stopped=self.closed_event;probe=self.monitor
        self.destroyed.connect(lambda *_:(stopped.set(),probe.close()))
        app=QApplication.instance()
        if app:app.installEventFilter(self)
        try:self.refresh_policy()
        except (sqlite3.Error,ValueError,TypeError) as error:self.policy_error=str(error);self.pause_event.set()
        if start:self.monitor.start();self.timer.start()

    def eventFilter(self,watched,event):
        if event.type() in (QEvent.KeyPress,QEvent.MouseButtonPress,QEvent.Wheel) and isinstance(watched,QWidget) and (watched is self.window or self.window.isAncestorOf(watched)):self.last_interaction=self.clock()
        return False

    def context_active(self):
        return not self.closed_event.is_set() and self.window.library is self.library and not self.library.closed

    def refresh_policy(self):
        if not self.context_active():return
        row=self.library.db.execute('SELECT value FROM preferences WHERE key=?',(KEY,)).fetchone();raw=row[0] if row else None
        if raw is not None and len(raw.encode())>8192:raise ValueError('資源策略過大，停止新背景工作')
        policy=json.loads(raw) if raw is not None else dict(DEFAULT)
        if not isinstance(policy,dict) or policy.get('version')!=1 or policy.get('profile')!='LOW_LOAD' or type(policy.get('paused')) is not bool or type(policy.get('revision')) is not int or policy['revision']<0:raise ValueError('資源策略版本／內容不支援，未自動套用')
        self.policy=policy;self.policy_raw=raw
        if policy['paused'] or self.pending_pause:self.pause_event.set()
        else:self.pause_event.clear()

    def pulse(self):
        if not self.context_active() or not isValid(self):self.shutdown();return
        now=self.clock();late=max(0,now-self.last_pulse-.25);self.last_pulse=now;self.lag_samples.append(late);self.lag_ewma=.2*late+.8*self.lag_ewma
        if now-self.last_policy_check>=1:
            try:self.refresh_policy();self.last_policy_check=now
            except (sqlite3.Error,ValueError,TypeError) as error:self.policy_error=str(error);self.pause_event.set()

    def gui_lag(self):
        ordered=sorted(self.lag_samples);p95=ordered[max(0,math.ceil(len(ordered)*.95)-1)] if ordered else 0
        return max(self.lag_ewma,p95)

    def admit(self,kind='ANALYSIS',*,foreground=False,requested=False,estimated_peak_bytes=0,estimated_write_bytes=0):
        # May be called by a worker: no Qt calls and no access to the GUI SQLite connection.
        reason=None
        if not self.context_active():reason='PROJECT_CONTEXT_CLOSED_OR_CHANGED'
        elif self.policy_error:reason='RESOURCE_POLICY_UNSAFE'
        elif not foreground and self.pause_event.is_set():reason='BACKGROUND_PAUSED_BY_OPERATOR'
        elif self.clock()<self.ready_after:reason='GUI_STARTUP_WARMUP'
        if reason:return ResourceDecision(False,'PAUSED_RESOURCES',(reason,),0,estimated_peak_bytes,None)
        result=(self.foreground_control if foreground else self.control).decide(self.monitor.snapshot(),kind,estimated_peak_bytes,estimated_write_bytes,self.gui_lag(),not (foreground or requested) and self.clock()-self.last_interaction<1.5)
        if result.allowed and requested:self.last_interaction=-math.inf
        return result

    def set_paused(self,paused):
        if type(paused) is not bool:raise ValueError('背景暫停需明確布林選擇')
        if not self.context_active():raise ValueError('專案已關閉或切換，未保存資源策略')
        if paused:self.pending_pause=True;self.pause_event.set()
        if self.policy_error:raise ValueError('資源策略尚有錯誤，請先診斷，未宣稱保存成功')
        if self.library.db.in_transaction:raise ValueError('現有交易尚未完成，暫停僅在本次生效、尚未保存')
        value=dict(self.policy,paused=paused,revision=self.policy['revision']+1);encoded=json.dumps(value,sort_keys=True)
        self.library.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.library.db.execute('SELECT value FROM preferences WHERE key=?',(KEY,)).fetchone()
            if (row[0] if row else None)!=self.policy_raw:raise ValueError('其他視窗已改資源策略，請重新核對')
            self.library.db.execute('INSERT INTO preferences VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(KEY,encoded));self.library.event('runtime-policy','background_pause_saved' if paused else 'background_resume_saved');self.library.db.commit()
        except BaseException:self.library.db.rollback();raise
        self.policy=value;self.policy_raw=encoded;self.pending_pause=False
        if paused:self.pause_event.set()
        else:self.pause_event.clear()
        return value

    def state(self):
        value=self.monitor.snapshot()
        return dict(profile='LOW_LOAD',background_paused=self.pause_event.is_set(),pause_request_not_persisted=self.pending_pause,policy_error=self.policy_error,gui_lag_seconds=self.gui_lag(),snapshot=value.to_dict() if value else None,reference_hardware_verified=False,heavy_worker_limit=1,closed=self.closed_event.is_set())

    def shutdown(self):
        if self.closed_event.is_set():return
        self.closed_event.set();self.pause_event.set();self.monitor.close()
        if isValid(self):
            self.timer.stop();app=QApplication.instance()
            if app:app.removeEventFilter(self)

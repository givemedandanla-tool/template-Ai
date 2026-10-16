"""GUI-owned FIFO scheduler; computation keeps the existing per-worker SQLite connection."""
from PySide6.QtCore import QObject,QTimer,Signal
from shiboken6 import isValid
from .runtime_queue import RuntimeQueue
from .training_pipeline import LIVE_OWNERS,run_training_job
from .automatic_training import run_automatic
from .runtime_worker import run_isolated,WorkerTimeout
from .model import new_id
import threading


class RuntimeDispatch(QObject):
    changed=Signal()
    progress=Signal(str,object)
    finished=Signal(str,object)

    def __init__(self,window,start=True):
        super().__init__(window);self.window=window;self.library=window.library;self.queue=RuntimeQueue(self.library);self.session=new_id();self.active=None;self.closed=False;self.error=None;self.last_wait=None
        self.cancel_event=threading.Event();LIVE_OWNERS.add(self.session);self.queue.recover_dead();self.timer=QTimer(self);self.timer.setInterval(1000);self.timer.timeout.connect(self.dispatch)
        self.library.observe_close(self.shutdown)
        if start:self.timer.start()

    def submit(self,kind,job,actor,retry_failed=False):
        if self.closed:raise ValueError('專案已關閉，未加入執行佇列')
        request=self.queue.enqueue(kind,job['id'],actor,self.session,True,retry_failed);self.changed.emit();QTimer.singleShot(0,self,lambda:self.dispatch(requested=True));return request

    def dispatch(self,requested=False):
        if self.closed or self.library.closed or self.window.library is not self.library or self.active or self.window.busy or self.error:return
        try:
            requests=self.queue.eligible();admissible=[]
            for request in requests:
                decision=self.window.runtime.admit('GEOMETRY' if request['kind']=='JOB' else 'ANALYSIS',requested=requested and request['consent_session']==self.session)
                if decision.allowed:admissible.append(request)
                elif request['consent_session']==self.session:self.last_wait=','.join(decision.reasons)
            if not admissible or admissible[0]['consent_session']!=self.session:return
            request=admissible[0]
            try:claimed=self.queue.claim(request,self.session,[row['id'] for row in admissible])
            except ValueError as error:
                # A live worker in another window is temporary; corrupt/stale work is isolated.
                from .training_pipeline import owner_alive
                live=any((lease:=self.queue.store.get('WORKER',kind)) and lease.get('active') and owner_alive(lease.get('owner')) for kind in ('geometry-worker','automatic-worker'))
                if live:self.last_wait='其他視窗的既有工作仍執行';return
                self.queue.block(self.queue.get(request['id']),str(error));self.changed.emit();return
            if claimed is None:self.changed.emit();return
            identity=request['id'];token=claimed['owner']['token'];kind=request['kind'];self.active=(identity,token);self.last_wait=None;self.changed.emit()
            runtime=self.window.runtime;self.cancel_event.clear();self.progress.emit(identity,claimed)
            def work():
                admission=lambda:runtime.admit('GEOMETRY' if kind=='JOB' else 'ANALYSIS')
                progress=lambda value:self.progress.emit(identity,value)
                try:
                    result=run_isolated(self.library.root,kind,claimed['id'],token,cancel=self.cancel_event,progress=progress,admission=admission)
                    return dict(result=result)
                except WorkerTimeout as error:return dict(error=str(error),unit_timeout=True)
                except BaseException as error:return dict(error=str(error))
            def done(payload):
                self.active=None
                if self.closed or self.library.closed:LIVE_OWNERS.discard(token);return
                try:
                    result=payload.get('result')
                    if payload.get('unit_timeout'):
                        try:result=self.queue.isolate_timed_out(identity,token,payload['error'])
                        except ValueError as error:payload['error']+='；'+str(error)
                    if payload.get('launch_failed'):
                        if kind=='JOB':
                            with self.queue.store.transaction():result=self.queue.store._finish_training_job(claimed['id'],token,'FAILED_SYSTEM',payload['error'])
                        elif kind=='EVAL_JOB':
                            from .quality_jobs import EvaluationJobs
                            result=EvaluationJobs(self.library).finish(claimed['id'],token,'FAILED_SYSTEM',payload['error'])
                        else:
                            from .automatic_training import AutomaticTraining
                            result=AutomaticTraining(self.library).finish(claimed['id'],token,'FAILED_SYSTEM',payload['error'])
                    LIVE_OWNERS.discard(token)
                    saved=self.queue.finish(identity,token,result,payload.get('error'));self.finished.emit(identity,result or dict(phase='INTERRUPTED',error=payload.get('error')));self.changed.emit()
                    self.window.refresh_sources(preserve_editor=True);self.window.refresh_templates(preserve_editor=True)
                except Exception as error:LIVE_OWNERS.discard(token);self.error='執行結果未寫入佇列收據；保留工作與已存單位：'+str(error);self.changed.emit()
            try:self.window.run_job('持久工作先進先出 · '+kind,work,done,on_error=lambda error:done(dict(error=error,launch_failed=True)),resource_kind='GEOMETRY' if kind=='JOB' else 'ANALYSIS',cancel=self.cancel_event)
            except Exception as error:done(dict(error=str(error),launch_failed=True))
        except Exception as error:self.error='排程停止，尚未宣稱成功：'+str(error);self.changed.emit()

    def cancel(self,identity):
        if self.closed:raise ValueError('原專案已關閉')
        request=self.queue.get(identity)
        if not request:raise ValueError('執行請求已失聯')
        if self.active and self.active[0]==identity:
            self.cancel_event.set()
            if request['kind']=='JOB':self.queue.store.request_training_cancel(request['job_id'],self.active[1])
            self.last_wait='已請求安全取消；當前原子單位仍可能完成';self.changed.emit();return
        self.queue.cancel_waiting(identity,request['revision']);self.finished.emit(identity,dict(phase='CANCELLED_BEFORE_CLAIM'));self.changed.emit()

    def recover_scheduler(self):
        if self.closed or self.library.closed or self.active or self.window.busy:raise ValueError('先等目前工作安全停止；原專案需保持開啟')
        self.window.runtime.refresh_policy();self.queue.recover_dead();proof=new_id()
        with self.queue.transaction():self.library.event(proof,'runtime_scheduler_recovery_write_checked')
        if not self.library.db.execute("SELECT 1 FROM reviews WHERE entity=? AND action='runtime_scheduler_recovery_write_checked'",(proof,)).fetchone():raise ValueError('沒有可核對的保存憑證，未解除排程故障')
        self.window.runtime.policy_error=None;self.error=None;self.last_wait='已核對可讀寫及工作收據；未完成範圍仍需明確恢復';self.changed.emit()

    def shutdown(self):
        if self.closed:return
        self.closed=True;self.cancel_event.set();LIVE_OWNERS.discard(self.session)
        if isValid(self):self.timer.stop()

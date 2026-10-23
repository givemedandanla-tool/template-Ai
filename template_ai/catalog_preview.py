"""One bounded worker queue, plain DTOs, stale-result rejection on the GUI thread."""
from collections import OrderedDict,deque
import threading
from PySide6.QtCore import QObject,QRunnable,Signal,Slot
from .catalog import source_preview,preview_request


class PreviewSignals(QObject):
    done=Signal(object)


class PreviewJob(QRunnable):
    def __init__(self,epoch,entry,request):
        super().__init__();self.epoch=epoch;self.entry=entry;self.request=request;self.cancel=threading.Event();self.signals=PreviewSignals()
    def run(self):
        try:result=source_preview(self.request,self.cancel)
        except Exception:result=dict(status='FAILED_SYSTEM',reason='背景預覽失敗；可重新整理，未更動任何資料',image=None,proofs=[])
        self.signals.done.emit(dict(epoch=self.epoch,id=self.entry['id'],signature=self.entry['signature'],result=result))


class PreviewController(QObject):
    result=Signal(object)
    idle=Signal()
    def __init__(self,window,parent=None):
        super().__init__(parent);self.window=window;self.epoch=0;self.queue=deque();self.active=None;self.closed=False;self.cache=OrderedDict()
    def reset(self,entries):
        self.epoch+=1;self.queue.clear()
        if self.active:self.active.cancel.set()
        for e in entries[:48]:self.queue.append(e)
        self.start_next()
    def prioritize(self,entry):
        if self.closed:return
        self.queue=deque(e for e in self.queue if e['id']!=entry['id']);self.queue.appendleft(entry);self.start_next()
    def close(self):
        self.closed=True;self.epoch+=1;self.queue.clear()
        if self.active:self.active.cancel.set()
    def start_next(self):
        if self.active or self.closed:return
        if not self.queue:self.idle.emit();return
        entry=self.queue.popleft()
        try:
            request=preview_request(self.window.library,entry);job=PreviewJob(self.epoch,entry,request);self.active=job
            self.window._background_jobs['catalog-'+str(id(self))]=job
            job.signals.done.connect(self.completed);self.window.pool.start(job)
        except Exception:
            self.active=None;self.window._background_jobs.pop('catalog-'+str(id(self)),None)
            self.result.emit(dict(epoch=self.epoch,id=entry['id'],signature=entry['signature'],result=dict(status='FAILED_SYSTEM',reason='無法啟動預覽；可重新整理',image=None,proofs=[])))
            self.queue.clear();self.idle.emit()
    @Slot(object)
    def completed(self,message):
        self.active=None;self.window._background_jobs.pop('catalog-'+str(id(self)),None)
        if not self.closed and message['epoch']==self.epoch:
            self.cache[message['id']]=message;self.cache.move_to_end(message['id'])
            while len(self.cache)>16:self.cache.popitem(last=False)
            self.result.emit(message)
        self.start_next()

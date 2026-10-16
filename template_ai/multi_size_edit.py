"""Reuse candidate editor in the existing multi-size matrix and original worker.

An ephemeral target adapter/controller has no queue, thread pool or storage.
"""
import copy,threading
from types import SimpleNamespace
from PySide6.QtCore import QObject,Signal
from PySide6.QtWidgets import QWidget
from shiboken6 import isValid
from .customers import digest
from .candidate_edit import prepare_edit,calculate_edit,review_context_token
from .candidate_edit_dispatch import provisional,envelope_current


class SizeEditAdapter(QWidget):
    def __init__(self,owner,entry,index):
        super().__init__(owner);self.owner=owner;self.service=owner.service;self.entry=entry;self.library=owner.window.library;self.candidates=entry['candidates'];self.editor_closed=False;self.candidate_list=SimpleNamespace(currentRow=lambda:index)
    @property
    def generation(self):return self.owner.window.generation
    def input_data(self):
        if self.owner.window.library is not self.library or self.owner.service is not self.service or not self.owner.is_current():raise ValueError('多尺寸來源已變，先同步重驗；不採用舊快照')
        return copy.deepcopy((self.service.people,self.service.companies,self.entry['resolved_logos']))
    def choose_candidate(self,index):
        candidate=self.candidates[index];self.entry['selected']=candidate.template.id;self.entry['state']='VALID' if candidate.formal_eligible else 'BLOCKED';self.owner.render_rows();self.owner.export_button.setEnabled(self.owner.is_current())


class SizeEditController(QObject):
    completed=Signal(int,object)
    failed=Signal(int,str)
    preview_ready=Signal(int,object,object)
    def __init__(self,adapter):
        super().__init__(adapter);self.adapter=adapter;self.owner=adapter.owner;self.active=False;self.event=threading.Event()
    def release(self):
        if isValid(self.adapter) and self.adapter.editor_closed and not self.active:self.adapter.deleteLater()
    def error(self,index,message):
        self.active=False
        if isValid(self.adapter):self.failed.emit(index,str(message));self.release()
    def begin(self,plan,compare=False):
        if self.active or self.owner.running or self.owner.window.busy:raise ValueError('原背景工作尚未完成；保留人工內容，完成後再套用')
        envelope=prepare_edit(self.adapter,plan);self.event=threading.Event();index=plan['index'];self.active=True
        if compare:
            pending=None;envelope.update(mode='COMPARE_ONLY',target_revision=plan['manual_revision'],target_digest=plan['before_digest'],context_token=envelope['before_context_token'])
        else:
            pending=provisional(envelope);envelope.update(target_revision=pending.risk_context['manual_revision'],target_digest=digest(pending.template.to_dict()),context_token=review_context_token(pending.risk_context));self.adapter.candidates[index]=pending;self.adapter.choose_candidate(index)
        def work(library):return calculate_edit(envelope,library)
        def done(candidate):
            self.active=False
            if not isValid(self.adapter):return
            if self.event.is_set():self.error(index,'已取消重驗；人工版面保留且禁止正式輸出');return
            if not envelope_current(self.adapter,envelope):self.error(index,'來源／人工版本已更新，舊重驗結果已忽略');return
            if compare:
                candidate.risk_context['comparison_gate']=candidate.risk;candidate.risk_context['comparison_only']=True;self.preview_ready.emit(index,envelope,candidate)
            else:self.adapter.candidates[index]=candidate;self.adapter.choose_candidate(index);self.completed.emit(index,candidate)
            self.release()
        try:self.owner.background('目前尺寸人工版面整張重驗',work,done,resource_kind='GEOMETRY',cancel=self.event,on_error=lambda message:self.error(index,message),require_current=True)
        except Exception as error:self.error(index,error);raise
        return envelope if compare else pending
    def submit(self,plan):return self.begin(plan)
    def preview(self,plan):return self.begin(plan,True)
    def adopt_preview(self,envelope,candidate):
        from .candidate_risk import bind_source
        if self.active or self.event.is_set() or not envelope_current(self.adapter,envelope):raise ValueError('比較已過期／取消，先重新核對')
        candidate=copy.deepcopy(candidate);candidate.risk_context.pop('comparison_only',None);candidate.risk_context.pop('comparison_gate',None);bind_source(candidate,self.adapter.library,require_registered=True)
        if not candidate.formal_eligible:raise ValueError('此尺寸建議未通過完整Gate，不採用')
        index=envelope['plan']['index'];self.adapter.candidates[index]=candidate;self.adapter.choose_candidate(index);self.completed.emit(index,candidate);return candidate
    def cancel(self,index):
        self.event.set();self.failed.emit(index,'取消此重驗／建議；保留人工版面與風險')

"""Coalesce transient candidate rechecks on the existing MainWindow single worker.

No persistent queue/job kind/second thread pool. Manual geometry remains visible
and explicitly UNKNOWN until a current whole-card result can be installed.
"""
import copy,threading
from PySide6.QtCore import QObject,QTimer,Signal
from .customers import digest
from .candidate_edit import prepare_edit,calculate_edit,dependency_token,review_context_token
from .model import Template


def provisional(envelope):
    from .training_store import digest as pin_digest
    from .diagnostic_schema import issue
    candidate=copy.deepcopy(envelope['before']);candidate.template=Template.from_dict(copy.deepcopy(envelope['after']));slots={s.id:s for s in candidate.template.slots};candidate.generation=envelope['plan']['generation']
    people={f'p{i+1}':p for i,p in enumerate(envelope['people'])};companies={f'c{i+1}':p for i,p in enumerate(envelope['companies'])}
    for item in candidate.items:
        item.slot=slots[item.slot.id];data=(companies if item.slot.owner.startswith('c') else people).get(item.slot.owner,{});key='name' if item.slot.kind in ('logo','company') else item.slot.kind;values=data.get(key,[]);values=values if isinstance(values,list) else [values];item.text=str(values[item.slot.index]) if item.slot.index<len(values) else ''
        if item.slot.kind=='logo' and item.logo!=envelope['logos'].get(item.slot.owner):item.logo=None
    candidate.risk_context.update(copy.deepcopy(envelope['manual_metadata']));snapshot=copy.deepcopy(dict(people=envelope['people'],companies=envelope['companies'],logos=envelope['logos']));candidate.risk_context.update(input_snapshot=snapshot,input_digest=pin_digest(snapshot),edit_state='PENDING_MANUAL_RECHECK');candidate.risk_context.setdefault('conditions',[]).append(dict(id='MANUAL_RECHECK_PENDING',status='UNKNOWN',reason='人工設定尚待目前輸入與來源的整張重驗'))
    candidate.risk_context['last_verified_issue_codes']=[r.get('code') for r in candidate.diagnostics];candidate.issues=['人工版面保留，完整數位Gate尚待重驗'];candidate.diagnostics=[issue('DEPENDENCY_CHANGED')];candidate.measurements=[];return candidate


class CandidateEditDispatcher(QObject):
    completed=Signal(int,object)
    failed=Signal(int,str)
    preview_ready=Signal(int,object,object)
    def __init__(self,window):
        super().__init__(window);self.window=window;self.pending={};self.active=None;self.timer=QTimer(self);self.timer.setInterval(50);self.timer.timeout.connect(self.tick)
    def submit(self,plan):
        if len(self.pending)>=200 and plan['index'] not in self.pending:raise ValueError('超過當次200候選重驗預算')
        envelope=prepare_edit(self.window,plan);candidate=provisional(envelope);envelope.update(target_revision=candidate.risk_context['manual_revision'],target_digest=digest(candidate.template.to_dict()),context_token=review_context_token(candidate.risk_context),cancel=threading.Event());self.pending[plan['index']]=envelope;self.window.candidates[plan['index']]=candidate;self.window.choose_candidate(plan['index']);self.timer.start();return candidate
    def current(self,envelope):
        w=self.window;p=envelope['plan'];index=p['index']
        try:
            if w.library.closed or str(w.library.root)!=envelope['root'] or w.generation!=p['generation'] or digest(w.input_data())!=envelope['input_digest']:return False
            if dependency_token(w,Template.from_dict(envelope['after']),envelope['logos'])!=envelope['dependency_token']:return False
        except (ValueError,OSError,TypeError,KeyError):return False
        if not 0<=index<len(w.candidates):return False
        candidate=w.candidates[index]
        if review_context_token(candidate.risk_context)!=envelope['context_token']:return False
        return candidate.template.id==p['template_id'] and candidate.risk_context.get('manual_revision',0)==envelope['target_revision'] and digest(candidate.template.to_dict())==envelope['target_digest']
    def preview(self,plan):
        if len(self.pending)>=200 and (plan['index'],'COMPARE_ONLY') not in self.pending:raise ValueError('超過當次200候選重驗預算')
        envelope=prepare_edit(self.window,plan);envelope.update(mode='COMPARE_ONLY',target_revision=plan['manual_revision'],target_digest=plan['before_digest'],context_token=envelope['before_context_token'],cancel=threading.Event());self.pending[(plan['index'],'COMPARE_ONLY')]=envelope;self.timer.start();return envelope
    def adopt_preview(self,envelope,result):
        from .candidate_risk import bind_source
        if envelope.get('mode')!='COMPARE_ONLY' or envelope['cancel'].is_set() or not self.current(envelope):raise ValueError('比較已過期或取消，請重新比較')
        result=copy.deepcopy(result);result.risk_context.pop('comparison_only',None);result.risk_context.pop('comparison_gate',None);bind_source(result,self.window.library,require_registered=True)
        if not result.formal_eligible:raise ValueError('建議尚未通過完整Gate；保留人工版面與風險')
        index=envelope['plan']['index'];result.risk_context.pop('comparison_only',None);self.window.candidates[index]=result;self.window.choose_candidate(index);self.completed.emit(index,result);return result
    def tick(self):
        w=self.window
        if w.library.closed:self.pending.clear();self.timer.stop();return
        if self.active is not None or w.busy:return
        if not self.pending:self.timer.stop();return
        key=next(iter(self.pending));envelope=self.pending.pop(key);index=envelope['plan']['index']
        if not self.current(envelope):self.failed.emit(index,'輸入／人工版本已更新，過期重驗要求已忽略；請重新核對');return
        self.active=envelope
        if envelope.get('mode')!='COMPARE_ONLY':w.candidates[index].risk_context['edit_state']='RECOMPUTING';w.refresh_dependency_notice()
        def work():
            from .storage import Library
            library=Library(envelope['root'])
            try:return calculate_edit(envelope,library)
            finally:library.close()
        def done(result):
            self.active=None
            if envelope['cancel'].is_set():self.failed.emit(index,'已取消此次重驗；人工版面保留且禁止正式輸出');return
            if not self.current(envelope):
                if envelope.get('mode')!='COMPARE_ONLY' and index<len(w.candidates):
                    current=w.candidates[index]
                    if current.risk_context.get('manual_revision',0)==envelope['target_revision'] and digest(current.template.to_dict())==envelope['target_digest']:current.risk_context['edit_state']='PENDING_MANUAL_RECHECK'
                self.failed.emit(index,'較新的輸入／來源／規則或人工版本已存在，過期結果已忽略／可重新比較');return
            if envelope.get('mode')=='COMPARE_ONLY':
                result.risk_context['comparison_gate']=result.risk;result.risk_context['comparison_only']=True;self.preview_ready.emit(index,envelope,result);return
            w.candidates[index]=result;w.choose_candidate(index);self.completed.emit(index,result);w.statusBar().showMessage('候選整張重驗完成：'+result.risk['label'])
        def failed(message):
            self.active=None
            if self.current(envelope) and envelope.get('mode')!='COMPARE_ONLY':w.candidates[index].risk_context['edit_state']='PENDING_MANUAL_RECHECK'
            self.failed.emit(index,'重驗未完成：'+str(message)+'；人工版面保留，未放行正式輸出')
        try:w.run_job('當次候選／人工設定整張重驗',work,done,on_error=failed,resource_kind='GEOMETRY',cancel=envelope['cancel'])
        except Exception as error:failed(str(error))
    def cancel(self,index):
        for key,envelope in list(self.pending.items()):
            if envelope['plan']['index']==index:self.pending.pop(key)['cancel'].set()
        if self.active and self.active['plan']['index']==index:self.active['cancel'].set()
        if 0<=index<len(self.window.candidates) and self.window.candidates[index].risk_context.get('edit_state')=='RECOMPUTING':self.window.candidates[index].risk_context['edit_state']='PENDING_MANUAL_RECHECK'
        self.failed.emit(index,'已取消此候選重驗；保留人工設定，仍需完整Gate')


def dispatcher(window):
    if not hasattr(window,'candidate_edit_dispatcher'):window.candidate_edit_dispatcher=CandidateEditDispatcher(window)
    return window.candidate_edit_dispatcher

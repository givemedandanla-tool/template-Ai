"""One transient foreground layout session: copied inputs, one worker, true item counts."""
import copy
import threading
from PySide6.QtCore import QObject,QRunnable,Signal,Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QListWidget,QPlainTextEdit,QMessageBox
from .layout import generate
from .customers import digest

class SessionSignals(QObject):
    progress=Signal(object)
    finished=Signal(object)

class LayoutWorker(QRunnable):
    def __init__(self,templates,people,companies,logos,generation,pause,cancel):
        super().__init__();self.setAutoDelete(False);self.templates=templates;self.people=people;self.companies=companies;self.logos=logos;self.generation=generation;self.pause=pause;self.cancel=cancel;self.signals=SessionSignals()
    def run(self):
        rows=[];state='COMPLETED'
        try:
            for i,t in enumerate(self.templates):
                while self.pause.is_set() and not self.cancel.is_set():self.cancel.wait(.05)
                if self.cancel.is_set():state='CANCELLED';break
                self.signals.progress.emit({'phase':'STARTED','index':i,'total':len(self.templates),'template_id':t.id})
                try:c=generate(t,self.people,self.companies,self.logos,self.generation);row={'candidate':c,'template_id':t.id,'state':'CALCULATED_PENDING_ADOPTION'}
                except Exception as e:row={'candidate':None,'template_id':t.id,'state':'FAILED','error':str(e)}
                rows.append(row);self.signals.progress.emit({'phase':'ITEM_FINISHED','index':i+1,'total':len(self.templates),'row':row})
            if self.cancel.is_set():state='CANCELLED'
        except Exception as e:state='FAILED_SYSTEM';rows.append({'candidate':None,'state':'FAILED_SYSTEM','error':str(e)})
        finally:self.signals.finished.emit({'state':state,'rows':rows})

class LayoutSessionDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.running=False;self.report_state='NOT_CHECKED';self.rows=[];self.worker=None;self.pause_event=threading.Event();self.cancel_event=threading.Event();self.setWindowTitle('當次排版／真實進度與安全停止');self.resize(900,650);l=QVBoxLayout(self)
        self.status=QLabel('只保留當次記憶體候選；未保存跨啟動恢復，不寫客戶主檔。');self.status.setWordWrap(True);l.addWidget(self.status);self.list=QListWidget();l.addWidget(self.list);self.details=QPlainTextEdit();self.details.setReadOnly(True);l.addWidget(self.details)
        bar=QHBoxLayout();self.start_button=QPushButton('快照預檢後開始');self.start_button.clicked.connect(self.start);bar.addWidget(self.start_button)
        self.pause_button=QPushButton('暫停');self.pause_button.clicked.connect(self.pause);bar.addWidget(self.pause_button);self.resume_button=QPushButton('繼續');self.resume_button.clicked.connect(self.resume);bar.addWidget(self.resume_button);self.cancel_button=QPushButton('取消此次計算');self.cancel_button.clicked.connect(self.cancel);bar.addWidget(self.cancel_button);self.adopt_button=QPushButton('明確採用已算候選至既有畫布');self.adopt_button.clicked.connect(self.adopt);bar.addWidget(self.adopt_button);self.report_button=QPushButton('當次進度／問題報告');self.report_button.clicked.connect(self.report);bar.addWidget(self.report_button);l.addLayout(bar);self.controls()
    def controls(self):
        self.start_button.setEnabled(not self.running);self.pause_button.setEnabled(self.running and not self.pause_event.is_set());self.resume_button.setEnabled(self.running and self.pause_event.is_set());self.cancel_button.setEnabled(self.running);self.adopt_button.setEnabled(bool(self.rows) and not self.running)
    def start(self):
        if self.running or self.window.busy:self.status.setText('已有背景工作；未開始');return
        try:
            w=self.window;self.generation=w.generation;self.people,self.companies,self.logos=copy.deepcopy(w.input_data());self.size=(w.out_w.value(),w.out_h.value());self.input_digest=digest((self.people,self.companies,self.logos,self.size));templates=[]
            for t in w.library.templates(True):
                if (t.width_mm,t.height_mm)!=self.size or t.capacity!=len(self.people) or (getattr(w,'reorder_template_id',None) and w.reorder_template_id!=t.id):continue
                w.library._template_provenance(t);templates.append(copy.deepcopy(t))
            if len(templates)>200:raise ValueError('超過單次200候選預算；請縮小模板範圍，未開始亦未宣稱全部檢查')
            self.template_digests={t.id:digest(t.to_dict()) for t in templates};self.rows=[];self.list.clear();self.pause_event.clear();self.cancel_event.clear();self.worker=LayoutWorker(templates,self.people,self.companies,self.logos,self.generation,self.pause_event,self.cancel_event);self.worker.signals.progress.connect(self.progress,Qt.QueuedConnection);self.worker.signals.finished.connect(self.on_finished,Qt.QueuedConnection);self.report_state='RUNNING';self.running=True;w.busy=True;self.controls();self.status.setText(f'已核對{len(templates)}個同尺寸同容量模板，單worker；未遍歷完成前不是全域最佳')
            try:w.pool.start(self.worker)
            except BaseException:self.running=False;w.busy=False;self.controls();raise
        except Exception as e:self.report_state='FAILED_SYSTEM';self.rows=[];self.worker=None;self.status.setText('未開始：'+str(e));self.controls()
    def progress(self,event):
        self.status.setText(f"實際階段{event['phase']}：{event['index']}/{event['total']}；取消／暫停在候選邊界生效")
        if event['phase']=='ITEM_FINISHED':
            r=event['row'];self.rows.append(r);self.list.addItem(r['template_id']+' · '+r['state']+(' · 阻擋' if r['candidate'] and not r['candidate'].valid else ''));self.details.setPlainText('\n'.join(r['candidate'].issues) if r['candidate'] else r.get('error',''))
    def on_finished(self,result):
        self.report_state=result['state'];self.running=False;self.window.busy=False;self.rows=result['rows'];self.status.setText(result['state']+f'；實際完成{len(self.rows)}，結果僅對原快照有效／正式輸出仍需Gate');self.controls()
    def pause(self):
        self.pause_event.set();self.status.setText('暫停要求已提出，當前候選可能尚在安全結束');self.controls()
    def resume(self):
        if self.window.generation!=getattr(self,'generation',None):self.status.setText('輸入版本已改變，不能續算；請取消並重新開始');return
        self.pause_event.clear();self.controls()
    def cancel(self):
        self.cancel_event.set();self.pause_event.clear();self.status.setText('正在安全取消；已完成計算仍保留，未聲稱撤銷');self.controls()
    def adopt(self):
        try:
            if self.running:raise ValueError('先結束當次工作')
            w=self.window
            if w.generation!=self.generation or digest((*w.input_data(),(w.out_w.value(),w.out_h.value())))!=self.input_digest:raise ValueError('輸入／人工版本已改變；結果過期')
            current={t.id:t for t in w.library.templates(True)};results=[r['candidate'] for r in self.rows if r['candidate']]
            for c in results:
                t=current.get(c.template.id)
                if not t or digest(t.to_dict())!=self.template_digests[t.id]:raise ValueError('模板版本已改變；需重算')
                w.library._template_provenance(t)
            if QMessageBox.question(self,'採用候選','使用這些已完成候選取代目前結果？未遍歷項不代表無解。')!=QMessageBox.Yes:return
            total=len(self.worker.templates);checked=sum('template_id' in r for r in self.rows);failed=sum('template_id' in r and r.get('candidate') is None for r in self.rows)
            w.last_layout_summary=dict(state=self.report_state,total=total,checked=checked,calculated=max(0,checked-failed),failed=failed,unstarted=max(0,total-checked),global_unsolvable=False)
            w.candidates=sorted(results,key=lambda c:(not c.valid,-c.score,c.template.id));w.candidate_list.clear()
            for c in w.candidates:w.candidate_list.addItem(c.template.name+' · 當次已計算／待最終輸出Gate')
            if w.candidates:w.candidate_list.setCurrentRow(0)
            self.status.setText('已明確採用當前版本結果；無主檔／模板／來源修改')
        except Exception as e:self.status.setText('未採用：'+str(e))
    def report(self):
        from .diagnostic_dialog import DiagnosticReportDialog
        dialog=DiagnosticReportDialog(self.window,'session',session=self,parent=self)
        try:dialog.exec()
        finally:dialog.deleteLater()
    def reject(self):
        if self.running:self.cancel();self.status.setText('請等待安全結束後關閉；控制未宣稱已恢復');return
        super().reject()

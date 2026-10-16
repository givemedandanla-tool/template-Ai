"""One transient foreground layout session: copied inputs, one worker, true item counts."""
import copy
import threading
from PySide6.QtCore import QObject,QRunnable,Signal,Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QListWidget,QPlainTextEdit,QMessageBox,QInputDialog,QLineEdit,QListWidgetItem
from .layout import generate
from .candidate_risk import bind_source,search_result
from dataclasses import asdict
from .layout_recovery import LayoutRecovery,encode_candidate
from .model import Template
from .customers import digest

PHASE_LABELS=dict(INPUT_SOURCE_PRECHECK='輸入／來源預檢',LOSSLESS_OWNER_FIELD_MATCH='人物／公司／欄位無損配對',FIXED_FONT_GEOMETRY='固定字級／框位及受限字寬適配',SIZE_LOGO_FONT_CHECK='此尺寸Logo／字型核對',CANDIDATE_RISK_GATE='安全／草稿／硬性阻擋Gate',STARTED='計算中',PAUSED_OPERATOR='已在安全邊界暫停',PAUSED_RESOURCES='資源不足，暫緩下一候選',RESTORED_CURRENT_PENDING_ADOPTION='已恢復且版本一致／待明確採用',RESTORED_REVIEW_OR_EVIDENCE_REQUIRED='已恢復草稿／來源待核實',STALE_RECALCULATE='需重新計算',CALCULATED_PENDING_ADOPTION='已完成計算／待採用')

class SessionSignals(QObject):
    progress=Signal(object)
    finished=Signal(object)

class LayoutWorker(QRunnable):
    def __init__(self,templates,people,companies,logos,generation,pause,cancel,admission=None,completed=None,library_root=None):
        super().__init__();self.setAutoDelete(False);self.templates=templates;self.people=people;self.companies=companies;self.logos=logos;self.generation=generation;self.pause=pause;self.cancel=cancel;self.signals=SessionSignals();self.admission=admission;self.completed=list(completed or []);self.library_root=library_root
    def run(self):
        library=None;source_cache={}
        rows=list(self.completed);checked={row.get('template_id') for row in rows};state='COMPLETED'
        try:
            if self.library_root:
                from .storage import Library
                library=Library(self.library_root)
            for i,t in enumerate(self.templates):
                if t.id in checked:continue
                waiting=None
                while not self.cancel.is_set():
                    decision=self.admission() if self.admission else None
                    reason='PAUSED_OPERATOR' if self.pause.is_set() else 'PAUSED_RESOURCES' if decision and not decision.allowed else None
                    if not reason:break
                    if waiting!=reason:
                        self.signals.progress.emit(dict(phase=reason,index=i,total=len(self.templates),template_id=t.id,reasons=list(decision.reasons) if decision and not decision.allowed else []));waiting=reason
                    self.cancel.wait(.1)
                if self.cancel.is_set():state='CANCELLED';break
                self.signals.progress.emit(dict(phase='STARTED',index=i,total=len(self.templates),template_id=t.id))
                def phase(name,slot_id=None):self.signals.progress.emit(dict(phase=name,index=i,total=len(self.templates),template_id=t.id,slot_id=slot_id))
                try:
                    c=generate(t,self.people,self.companies,self.logos,self.generation,progress=phase)
                    c.risk_context['source_template_pin']=dict(id=t.id,version=t.version,digest=digest(t.to_dict()))
                    if library:
                        from .candidate_risk import verify_original_source
                        try:verify_original_source(c,library,source_cache)
                        except (ValueError,OSError):pass
                        bind_source(c,library,require_registered=True)
                    row=dict(candidate=c,template_id=t.id,state='CALCULATED_PENDING_ADOPTION')
                except Exception as error:row=dict(candidate=None,template_id=t.id,state='FAILED',error=str(error))
                rows.append(row);self.signals.progress.emit(dict(phase='ITEM_FINISHED',index=len(rows),total=len(self.templates),row=row))
            if self.cancel.is_set():state='CANCELLED'
        except Exception as error:state='FAILED_SYSTEM';rows.append(dict(candidate=None,state='FAILED_SYSTEM',error=str(error)))
        finally:
            if library:library.close()
            self.signals.finished.emit(dict(state=state,rows=rows))


def canvas_stamp(window):
    return digest([(c.template.to_dict(),[asdict(i) for i in c.items],c.generation) for c in window.candidates])

class LayoutSessionDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.running=False;self.report_state='NOT_CHECKED';self.rows=[];self.worker=None;self.pause_event=threading.Event();self.cancel_event=threading.Event();self.setWindowTitle('當次排版／真實進度與安全停止');self.resize(900,650);l=QVBoxLayout(self)
        self.recovery=LayoutRecovery(window.library.root)
        try:pending=self.recovery.pending()
        except ValueError:pending=True
        self.status=QLabel('恢復上一次未完成的排版？需密碼與明確選擇；尚未載入內容。' if pending else '預設只保留當次記憶體；可安全取消後明確加密暫存24小時，不寫客戶主檔。');self.status.setWordWrap(True);l.addWidget(self.status);self.list=QListWidget();l.addWidget(self.list);self.details=QPlainTextEdit();self.details.setReadOnly(True);l.addWidget(self.details)
        bar=QHBoxLayout();self.start_button=QPushButton('快照預檢後開始');self.start_button.clicked.connect(self.start);bar.addWidget(self.start_button)
        self.pause_button=QPushButton('暫停');self.pause_button.clicked.connect(self.pause);bar.addWidget(self.pause_button);self.resume_button=QPushButton('繼續');self.resume_button.clicked.connect(self.resume);bar.addWidget(self.resume_button);self.cancel_button=QPushButton('取消此次計算');self.cancel_button.clicked.connect(self.cancel);bar.addWidget(self.cancel_button);self.adopt_button=QPushButton('明確採用已算候選至既有畫布');self.adopt_button.clicked.connect(self.adopt);bar.addWidget(self.adopt_button);self.preview_button=QPushButton('預覽已算部分候選');self.preview_button.clicked.connect(self.preview_selected);bar.addWidget(self.preview_button);self.report_button=QPushButton('當次進度／問題報告');self.report_button.clicked.connect(self.report);bar.addWidget(self.report_button);l.addLayout(bar)
        recovery_bar=QHBoxLayout();self.save_recovery_button=QPushButton('安全停止後加密暫存（24小時）');self.save_recovery_button.clicked.connect(self.save_recovery);recovery_bar.addWidget(self.save_recovery_button);self.restore_button=QPushButton('恢復上一次未完成的排版？');self.restore_button.clicked.connect(self.restore_recovery);recovery_bar.addWidget(self.restore_button);self.clear_recovery_button=QPushButton('放棄並清除暫存');self.clear_recovery_button.clicked.connect(self.clear_recovery);recovery_bar.addWidget(self.clear_recovery_button);l.addLayout(recovery_bar);self.controls()
    def initialize_scope(self,templates):
        self.list.clear();self.scope_items={}
        for template in templates:
            item=QListWidgetItem(template.name+f' v{template.version} · 尚未開始');item.setData(Qt.UserRole,template.id);self.list.addItem(item);self.scope_items[template.id]=(item,template.name+f' v{template.version}')

    def scope_status(self,identity,status):
        entry=getattr(self,'scope_items',{}).get(identity)
        if entry:entry[0].setText(entry[1]+' · '+PHASE_LABELS.get(status,status))

    def controls(self):
        self.start_button.setEnabled(not self.running);self.pause_button.setEnabled(self.running and not self.pause_event.is_set());self.resume_button.setEnabled((self.running and self.pause_event.is_set()) or (not self.running and self.report_state=='CANCELLED' and self.worker is not None));self.cancel_button.setEnabled(self.running);self.adopt_button.setEnabled(any(r.get('candidate') for r in self.rows));self.preview_button.setEnabled(any(r.get('candidate') for r in self.rows))
        self.save_recovery_button.setEnabled(not self.running and self.report_state=='CANCELLED' and bool(self.worker));self.restore_button.setEnabled(not self.running);self.clear_recovery_button.setEnabled(not self.running)
    def start(self,auto_apply=False):
        if self.running or self.window.busy:self.status.setText('已有背景工作；未開始');return
        try:
            self.auto_apply=auto_apply is True;self.auto_first_adopted=False
            w=self.window;self.generation=w.generation;self.people,self.companies,self.logos=copy.deepcopy(w.input_data());self.size=(w.out_w.value(),w.out_h.value());self.input_digest=digest((self.people,self.companies,self.logos,self.size));self.canvas_stamp=canvas_stamp(w);self.graph_snapshot=copy.deepcopy(w.active_input_graph.data if w.active_input_graph else None);templates=[]
            from .diagnostic_snapshot import selected_templates
            for t in selected_templates(w):
                if (t.width_mm,t.height_mm)!=self.size or t.capacity!=len(self.people) or (getattr(w,'reorder_template_id',None) and w.reorder_template_id!=t.id):continue
                templates.append(copy.deepcopy(t))
            if len(templates)>200:raise ValueError('超過單次200候選預算；請縮小模板範圍，未開始亦未宣稱全部檢查')
            self.template_digests={t.id:digest(t.to_dict()) for t in templates};self.rows=[];self.initialize_scope(templates);self.pause_event.clear();self.cancel_event.clear();self.worker=LayoutWorker(templates,self.people,self.companies,self.logos,self.generation,self.pause_event,self.cancel_event,lambda:w.runtime.admit('GEOMETRY',foreground=True),library_root=w.library.root);self.worker.signals.progress.connect(self.progress,Qt.QueuedConnection);self.worker.signals.finished.connect(self.on_finished,Qt.QueuedConnection);self.report_state='RUNNING';self.running=True;w.busy=True;self.controls();self.status.setText(f'已核對{len(templates)}個同尺寸同容量模板，單worker；未遍歷完成前不是全域最佳')
            try:w.pool.start(self.worker)
            except BaseException:self.running=False;w.busy=False;self.controls();raise
        except Exception as e:self.report_state='FAILED_SYSTEM';self.rows=[];self.worker=None;self.status.setText('未開始：'+str(e));self.controls()
    def progress(self,event):
        self.status.setText(f"實際階段{PHASE_LABELS.get(event['phase'],event['phase'])}：{event['index']}/{event['total']}；目前已完成部分候選，尚未比對所有模板"+'；'.join(event.get('reasons',[])))
        if event.get('template_id'):self.scope_status(event['template_id'],PHASE_LABELS.get(event['phase'],event['phase'])+'（已完成'+str(len(self.rows))+'/'+str(event['total'])+'）')
        if event['phase']=='ITEM_FINISHED':
            r=event['row']
            if r.get('candidate'):bind_source(r['candidate'],self.window.library)
            self.rows.append(r);self.scope_status(r['template_id'],r['candidate'].risk['label'] if r.get('candidate') else '發生錯誤：'+r.get('error','未知錯誤'));self.details.setPlainText(r['candidate'].risk['label']+'\n'+'\n'.join(r['candidate'].issues) if r['candidate'] else r.get('error',''))
        self.controls()
        if event['phase']=='ITEM_FINISHED' and getattr(self,'auto_apply',False) and not self.auto_first_adopted:
            self.adopt(confirmed=True);self.auto_first_adopted=True
    def on_finished(self,result):
        self.report_state=result['state'];self.running=False;self.window.busy=False;self.rows=result['rows']
        finished={row.get('template_id') for row in self.rows}
        for template in self.worker.templates:
            if template.id not in finished:self.scope_status(template.id,'已取消／尚未計算' if self.report_state=='CANCELLED' else '尚未計算')
        if self.report_state=='COMPLETED':
            try:self.recovery.clear()
            except OSError as error:self.status.setText('計算完成但暫存清理失敗：'+str(error));self.controls();return
        self.status.setText(result['state']+f'；實際完成{len(self.rows)}，結果僅對原快照有效／正式輸出仍需Gate');self.controls()
        if getattr(self,'auto_apply',False):self.adopt(confirmed=True)
        if not self.rows and getattr(self,'auto_apply',False):
            self.window.export_button.setEnabled(False);self.window.preview_button.setEnabled(False);self.window.issues.setText('無已計算候選；請核對尺寸／容量／已發布模板與來源，不推論所有設計均無解。')
    def pause(self):
        self.pause_event.set();self.status.setText('暫停要求已提出，當前候選可能尚在安全結束');self.controls()
    def resume(self):
        try:self.check_current()
        except ValueError as error:self.status.setText('不能續算：'+str(error));return
        if not self.running:
            self.rows=[r for r in self.rows if r.get('state')!='STALE_RECALCULATE'];self.initialize_scope(self.worker.templates)
            for row in self.rows:self.scope_status(row.get('template_id'),row['state'])
            self.cancel_event.clear();self.pause_event.clear();w=self.window
            self.worker=LayoutWorker(self.worker.templates,self.people,self.companies,self.logos,self.generation,self.pause_event,self.cancel_event,lambda:w.runtime.admit('GEOMETRY',foreground=True),completed=self.rows,library_root=w.library.root)
            self.worker.signals.progress.connect(self.progress,Qt.QueuedConnection);self.worker.signals.finished.connect(self.on_finished,Qt.QueuedConnection);self.running=True;self.report_state='RUNNING';w.busy=True
            try:w.pool.start(self.worker)
            except BaseException:self.running=False;w.busy=False;self.controls();raise
        self.pause_event.clear();self.controls()
    def cancel(self):
        self.cancel_event.set();self.pause_event.clear();self.status.setText('正在安全取消；已完成計算仍保留，未聲稱撤銷');self.controls()
    def adopt(self,confirmed=False):
        try:
            w=self.window
            if canvas_stamp(w)!=getattr(self,'canvas_stamp',canvas_stamp(w)):raise ValueError('目前畫布已有人工修正／新結果，保留差異，不覆寫；請取消後重新檢查')
            if w.generation!=self.generation or digest((*w.input_data(),(w.out_w.value(),w.out_h.value())))!=self.input_digest:raise ValueError('輸入／人工版本已改變；結果過期')
            current={}
            for saved in self.worker.templates:
                try:template=Template.from_dict(w.library.object_snapshot('TEMPLATE',saved.id)['payload'])
                except ValueError:continue
                if template.state=='published':current[template.id]=template
            results=[r['candidate'] for r in self.rows if r.get('candidate')]
            for c in results:
                t=current.get(c.template.id)
                if not t or digest(t.to_dict())!=self.template_digests[t.id]:raise ValueError('模板版本已改變；需重算')
                w.library._template_provenance(t)
            if confirmed is not True and QMessageBox.question(self,'採用候選','使用這些已完成候選取代目前結果？未遍歷項不代表無解。')!=QMessageBox.Yes:return
            total=len(self.worker.templates);checked=sum('template_id' in r for r in self.rows);failed=sum('template_id' in r and r.get('candidate') is None for r in self.rows)
            w.last_layout_risk_summary=search_result(results,scope_complete=self.report_state=='COMPLETED' and checked==total and not failed,unstarted=max(0,total-checked),excluded=[r.get('error','計算失敗') for r in self.rows if not r.get('candidate')])
            w.last_layout_summary=dict(state=self.report_state,total=total,checked=checked,calculated=max(0,checked-failed),failed=failed,unstarted=max(0,total-checked),global_unsolvable=False)
            for candidate in results:bind_source(candidate,w.library)
            w.candidates=sorted(results,key=lambda c:(not c.formal_eligible,-c.score,c.template.id));w.candidate_list.clear()
            for c in w.candidates:w.candidate_list.addItem(c.template.name+' · 當次已計算／待最終輸出Gate')
            if w.candidates:w.candidate_list.setCurrentRow(0)
            self.canvas_stamp=canvas_stamp(w)
            self.status.setText('已明確採用當前版本的部分候選；尚未比對者不代表無解，無主檔／模板／來源修改')
        except Exception as e:self.status.setText('未採用：'+str(e))
    def check_current(self):
        w=self.window
        if w.generation!=self.generation or digest((*w.input_data(),(w.out_w.value(),w.out_h.value())))!=self.input_digest:raise ValueError('輸入版本已改變，需重新開始')
        current={}
        for saved in self.worker.templates:
            try:template=Template.from_dict(w.library.object_snapshot('TEMPLATE',saved.id)['payload'])
            except ValueError:continue
            if template.state=='published':current[template.id]=template
        for t in self.worker.templates:
            if t.id not in current or digest(current[t.id].to_dict())!=self.template_digests[t.id]:raise ValueError('模板版本已改變，需重新計算')
            w.library._template_provenance(current[t.id])
        for row in self.rows:
            if row.get('candidate') and any(c['status']!='PASS' for c in row['candidate'].risk['conditions'] if c['id']=='SNAPSHOT_FRESHNESS'):raise ValueError('字型／Logo／來源指紋已變更，需重新計算')

    def preview_selected(self):
        item=self.list.currentItem()
        if item is None:return
        row=next((row for row in self.rows if row.get('template_id')==item.data(Qt.UserRole)),None)
        if row is None:self.status.setText('所選候選尚未開始／未計算，沒有可預覽結果');return
        candidate=row.get('candidate')
        if not candidate:return
        try:
            self.check_current();bind_source(candidate,self.window.library)
            from .render import render_image,preview_height
            image=render_image(candidate,96,True);self.window.output_canvas.set_content(candidate.template.width_mm,preview_height(candidate),image);self.window.output_canvas.fit();self.window.export_button.setEnabled(False)
            self.status.setText('僅預覽此已算部分候選；尚未遍歷完整範圍，正式輸出仍需另行採用與重核')
        except ValueError as error:self.status.setText('未預覽：'+str(error))

    def recovery_payload(self):
        return dict(state=self.report_state,generation=self.generation,people=copy.deepcopy(self.people),companies=copy.deepcopy(self.companies),logos=copy.deepcopy(self.logos),size=list(self.size),input_digest=self.input_digest,graph=copy.deepcopy(getattr(self,'graph_snapshot',None)),templates=[t.to_dict() for t in self.worker.templates],template_digests=copy.deepcopy(self.template_digests),rows=[dict(**{k:v for k,v in row.items() if k!='candidate'},candidate=encode_candidate(row['candidate']) if row.get('candidate') else None) for row in self.rows])

    def save_recovery(self):
        if self.running or self.window.busy or self.report_state!='CANCELLED':self.status.setText('先安全取消並等待結束，才可保存實際已算快照；目前未保存');return
        password,ok=QInputDialog.getText(self,'本機短期恢復','設定12字以上密碼；不儲存密碼，遺失無法恢復。24小時後失效，可隨時清除。',QLineEdit.Password)
        if not ok:return
        payload=self.recovery_payload()
        def done(receipt):self.status.setText('已實際驗證加密並落盤，24小時有效；未保存的後續進度不保證可恢復。');self.controls()
        self.window.run_job('保存短期加密排版快照',lambda:self.recovery.save(payload,password),done,on_error=lambda error:self.status.setText('未保存：'+str(error)),resource_kind='RESTORE')

    def clear_recovery(self):
        if self.running or self.window.busy:return
        if QMessageBox.question(self,'放棄並清除暫存','只刪除本機短期排版恢復資訊，不修改原稿、模板、客戶主檔。確認？')!=QMessageBox.Yes:return
        try:self.recovery.clear();self.status.setText('已清除短期恢復暫存；不是磁碟安全抹除')
        except OSError as error:self.status.setText('清除失敗：'+str(error))

    def restore_recovery(self):
        if self.running or self.window.busy:return
        password,ok=QInputDialog.getText(self,'恢復上一次未完成的排版？','輸入原密碼；先核實版本，確認後才替換當次輸入。',QLineEdit.Password)
        if not ok:return
        generation=self.window.generation;before=canvas_stamp(self.window);root=self.window.library.root
        def work():
            from .storage import Library
            payload=self.recovery.load(password);library=Library(root)
            try:rows=self.recovery.validate(library,payload)
            finally:library.close()
            return payload,rows
        def done(result):
            payload,rows=result;w=self.window
            if w.generation!=generation or canvas_stamp(w)!=before:self.status.setText('解密期間當次輸入／人工編輯已改變，保留目前工作，未套用');return
            if QMessageBox.question(self,'核對恢復範圍',f"已核對{len(rows)}個已算紀錄；過期候選需重算。替換目前當次輸入？不寫客戶／模板，舊PASS不當正式輸出授權。")!=QMessageBox.Yes:return
            from .input_graph import InputGraph
            graph=payload.get('graph') or InputGraph.from_legacy(payload['people'],payload['companies'],payload['logos']).data
            w.adopt_input_graph(graph);self.graph_snapshot=copy.deepcopy(graph);w.out_w.setValue(payload['size'][0]);w.out_h.setValue(payload['size'][1]);self.generation=w.generation;self.people,self.companies,self.logos=copy.deepcopy(w.input_data());self.size=tuple(payload['size']);self.input_digest=digest((self.people,self.companies,self.logos,self.size));self.canvas_stamp=canvas_stamp(w);self.template_digests=payload['template_digests'];templates=[Template.from_dict(t) for t in payload['templates']]
            self.worker=LayoutWorker(templates,self.people,self.companies,self.logos,self.generation,self.pause_event,self.cancel_event);self.rows=rows;self.report_state='CANCELLED';self.initialize_scope(templates)
            for row in rows:
                if row.get('candidate'):
                    if digest(dict(people=self.people,companies=self.companies,logos=self.logos))!=row['candidate'].risk_context.get('input_digest'):row.update(candidate=None,state='STALE_RECALCULATE',reason='恢復後輸入／Logo映射需重算')
                    else:row['candidate'].generation=self.generation
                self.scope_status(row.get('template_id'),row['state'])
            self.status.setText('已明確恢復已落盤且可核實的部分計算；未自動採用、續算或輸出。過期者需重新開始。');self.controls()
        self.window.run_job('解密核實短期排版恢復',work,done,on_error=lambda error:self.status.setText('未恢復：'+str(error)),resource_kind='RESTORE')

    def report(self):
        from .diagnostic_dialog import DiagnosticReportDialog
        dialog=DiagnosticReportDialog(self.window,'session',session=self,parent=self)
        try:dialog.exec()
        finally:dialog.deleteLater()
    def reject(self):
        if self.running:self.cancel();self.status.setText('請等待安全結束後關閉；控制未宣稱已恢復');return
        super().reject()

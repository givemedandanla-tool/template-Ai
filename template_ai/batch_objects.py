"""Bounded text-alignment batch adapter: reuse proposals, CAS, history and per-item commits."""
import json,copy,sqlite3
from PySide6.QtCore import Qt,Signal
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QPlainTextEdit,QMessageBox,QComboBox,QLineEdit,QDoubleSpinBox
from .customers import digest
from .object_tools import propose,select_slots,NoObjectChange
from .model import new_id

def batch_plan(library,targets,align='left'):
    if not isinstance(targets,list) or not 1<=len(targets)<=50 or len({(t.get('kind','ARTWORK'),t['id']) for t in targets})!=len(targets):raise ValueError('明確選取1至50個不同作品／草稿；同一實體先合併明確選取範圍')
    rows=[]
    for target in targets:
        row=dict(id=target['id'],kind=target.get('kind','ARTWORK'),state='BLOCKED',risk='HIGH',formal_eligible=False)
        row['selected_slot_ids']=copy.deepcopy(target.get('slot_ids',[]))
        row['target_key']=row['kind']+':'+row['id']
        try:
            snapshot=library.object_snapshot(row['kind'],row['id']);ids=target['slot_ids'];selected=select_slots(snapshot['payload'],ids)
            if row['kind']=='ARTWORK' and snapshot['payload'].get('visual_confirmed') is not True:raise ValueError('來源標記尚待人工確認，不自動批次核准')
            if any(s.locked or s.kind=='logo' or not s.owner or s.owner.upper()=='UNKNOWN' for s in selected) or len({s.owner for s in selected})!=1:raise ValueError('鎖定／Logo／未知或跨人物公司歸屬須走既有逐筆人工核對，不批次自動核准')
            request=copy.deepcopy(target.get('request') or dict(operation='PATCH',ids=ids,patch={'align':align},cross_owner=False))
            request.setdefault('ids',list(ids));request.setdefault('cross_owner',False)
            if sorted(request['ids'])!=sorted(ids):raise ValueError('請求物件與明確選取範圍不同')
            validate_request(request)
            plan=propose(snapshot['payload'],row['kind'],request)
            if plan['warnings'] and any('重疊' in w or '邊界' in w for w in plan['warnings']):raise ValueError('作品幾何待人工處理')
            row.update(state='READY',risk='LOW' if request['operation']=='PATCH' and set(request['patch'])<={'align','color'} else 'CONFIRM',snapshot=snapshot,request=request,changes=plan['changes'],warnings=plan['warnings'])
            if not plan['changes']:row.update(state='UNCHANGED',risk='NONE',reason='目前已是相同值；未建立重複寫入')
        except NoObjectChange as e:row.update(state='UNCHANGED',risk='NONE',snapshot=snapshot,request=request,reason=str(e))
        except (ValueError,KeyError,TypeError,OSError,sqlite3.Error) as e:row['reason']=str(e)
        rows.append(row)
    plan=dict(operation_id=new_id(),rows=rows,scope='EXACT_SELECTED_DRAFT_METADATA_ONLY',count=len(targets),root_digest=digest(str(library.root.resolve())),schema=2)
    plan['seal']=digest(plan);return plan


def validate_request(request):
    if request.get('operation') not in ('PATCH','MOVE','ALIGN','DISTRIBUTE') or request.get('cross_owner') is not False:raise ValueError('批次不能解鎖、刪除或跨人物公司；請逐筆人工核對')
    if request['operation']=='PATCH' and (not request.get('patch') or set(request['patch'])-{'align','color','x','y','w','h'}):raise ValueError('批次不可修改人物／公司／字級／字型／文字下限或Logo')


def check_batch(library,plan,approved):
    if approved is not True:raise ValueError('需明確確認範圍與逐項差異')
    if plan.get('root_digest')!=digest(str(library.root.resolve())) or plan.get('seal')!=digest({k:v for k,v in plan.items() if k!='seal'}):raise ValueError('批次來源／精確範圍或預覽已變更，重新預檢')


def operation_id(plan,row):return 'batch:'+digest([plan['operation_id'],row['kind'],row['id']])


def reconcile_item(library,plan,row):
    raw=library.db.execute('SELECT payload FROM object_edits WHERE id=?',(operation_id(plan,row),)).fetchone()
    if not raw:return None
    record=json.loads(raw[0]);snapshot=row['snapshot']
    if record['kind']!=row['kind'] or record['entity_id']!=row['id'] or record['plan']['request']!=row['request'] or record['before_revision']!=snapshot['revision'] or record['before']!=snapshot['payload']:raise ValueError('歷史操作ID與原核對範圍不同')
    if record['phase']!='APPLIED':raise ValueError('此操作已復原；不能將安全重試當成重新套用')
    current=library.object_snapshot(row['kind'],row['id']);unchanged=current['revision']==record['expected_revision'] and current['payload']==record['after']
    return dict(id=row['id'],kind=row['kind'],target_key=row['target_key'],state='ALREADY_APPLIED',outcome='APPLIED_PENDING_FULL_VALIDATION' if unchanged else 'APPLIED_BUT_CURRENT_CHANGED',history_id=record['id'],attempted=False,formal_eligible=False,reason='核實原操作已保存；目前資格仍須整作品重驗' if unchanged else '原操作確有歷史，但目前已有新編輯；保留新版，未重複套用')

def apply_batch(library,plan,approved=False,cancel=lambda:False,progress=lambda row:None):
    check_batch(library,plan,approved)
    results=[]
    for row in plan['rows']:
        result=dict(id=row['id'],kind=row['kind'],target_key=row['target_key'],attempted=False,formal_eligible=False)
        try:
            previous=reconcile_item(library,plan,row) if row['state']=='READY' else None
            if previous:result=previous
            elif cancel():result.update(state='CANCELLED',outcome='CANCELLED',reason='尚未執行；既有完成項不因此撤銷')
            elif row['state']=='UNCHANGED':
                current=library.object_snapshot(row['kind'],row['id']);fresh=current==row['snapshot'];result.update(state='BLOCKED',outcome='SKIPPED_PRECONDITION' if fresh else 'STALE',reason=row['reason'] if fresh else '預檢後來源已變更；未猜測重試')
            elif row['state']!='READY':result.update(state='BLOCKED',outcome='SKIPPED_PRECONDITION' if row['state']=='UNCHANGED' else 'NEEDS_MANUAL_REVIEW',reason=row['reason'])
            else:
                progress(dict(result,outcome='PROCESSING'))
                request=row['request'];validate_request(request)
                recalculated=propose(row['snapshot']['payload'],row['kind'],request)
                if recalculated['changes']!=row['changes']:raise ValueError('預覽範圍已被改變')
                result['attempted']=True;r=library.apply_object_edit(row['snapshot'],request,True,operation_id(plan,row))
                result.update(state='APPLIED_PENDING_FULL_VALIDATION',outcome='APPLIED_PENDING_FULL_VALIDATION',history_id=r['id'],reason='只保存選取草稿／標記差異；尚未核實當前整作品印前條件')
        except Exception as e:
            try:
                reconciled=reconcile_item(library,plan,row) if row['state']=='READY' else None
                if reconciled:result=reconciled
                else:
                    current=library.object_snapshot(row['kind'],row['id']);stale=row.get('snapshot') and (current['revision']!=row['snapshot']['revision'] or current['payload']!=row['snapshot']['payload'])
                    result.update(state='FAILED_OR_STALE',outcome='STALE' if stale else 'FAILED',reason=str(e))
            except (ValueError,KeyError,TypeError,OSError,sqlite3.Error):result.update(state='FAILED_OR_STALE',outcome='STALE' if isinstance(e,ValueError) else 'RESULT_UNVERIFIED',reason=str(e)+'；結果未安全核實，不盲目重試')
        results.append(result);progress(copy.deepcopy(result))
    return results


def undo_batch(library,plan,results,approved=False,selected=None,cancel=lambda:False,progress=lambda row:None):
    check_batch(library,plan,approved);known={r['target_key']:r for r in plan['rows']};requested={r['target_key'] for r in results if r.get('history_id')}
    if selected is not None:
        requested=set()
        for value in selected:
            choices=[key for key,row in known.items() if value in (key,row['id'])]
            if len(choices)!=1:raise ValueError('回復實體ID不明確；請使用完整類型與ID')
            requested.add(choices[0])
    if not requested.issubset(known):raise ValueError('回復範圍含未核對目標')
    receipts={r['target_key']:r for r in results};out=[]
    for identity in reversed([r['target_key'] for r in plan['rows'] if r['target_key'] in requested]):
        row=known[identity];result=dict(id=row['id'],kind=row['kind'],target_key=identity,formal_eligible=False)
        try:
            if receipts.get(identity,{}).get('history_id')!=operation_id(plan,row):raise ValueError('沒有此目標原操作的已核實歷史')
            raw=library.db.execute('SELECT payload FROM object_edits WHERE id=?',(operation_id(plan,row),)).fetchone();record=json.loads(raw[0]) if raw else None
            current_snapshot=library.object_snapshot(row['kind'],row['id'])
            if record and record['phase']=='UNDONE' and current_snapshot['revision']==record['expected_revision'] and current_snapshot['payload']==record['before']:
                result.update(outcome='ALREADY_UNDONE',history_id=record['id']);out.append(result);progress(copy.deepcopy(result));continue
            if cancel():result.update(outcome='UNDO_CANCELLED');out.append(result);progress(copy.deepcopy(result));continue
            progress(dict(result,outcome='PROCESSING'))
            current=reconcile_item(library,plan,row)
            if current is None or current['outcome']=='APPLIED_BUT_CURRENT_CHANGED':raise ValueError('此目標後已有新編輯／版本；未覆寫，請人工核對')
            record=library.object_history_action(current['history_id'],'UNDO',True);result.update(outcome='UNDONE_PENDING_FULL_VALIDATION',history_id=record['id'],attempted=True)
        except Exception as error:result.update(outcome='UNDO_CONFLICT',reason=str(error))
        out.append(result);progress(copy.deepcopy(result))
    return out


def batch_summary(results):
    from collections import Counter
    counts=dict(Counter(r.get('outcome',r.get('state')) for r in results));applied=counts.get('APPLIED_PENDING_FULL_VALIDATION',0);changed=counts.get('APPLIED_BUT_CURRENT_CHANGED',0)
    return dict(checked=len(results),attempted=sum(bool(r.get('attempted')) for r in results),applied_pending_validation=applied,current_changed=changed,failed=counts.get('FAILED',0)+counts.get('RESULT_UNVERIFIED',0),stale=counts.get('STALE',0),manual=counts.get('NEEDS_MANUAL_REVIEW',0),cancelled=counts.get('CANCELLED',0)+counts.get('UNDO_CANCELLED',0),undone=counts.get('UNDONE_PENDING_FULL_VALIDATION',0)+counts.get('ALREADY_UNDONE',0),undo_conflicts=counts.get('UNDO_CONFLICT',0),skipped=counts.get('SKIPPED_PRECONDITION',0),outcomes=counts,status='APPLIED_PENDING_REVALIDATION' if applied==len(results) and results else 'PARTIAL_OR_BLOCKED',formal_eligible=False)

class BatchObjectDialog(QDialog):
    batch_progress=Signal(object)
    def __init__(self,window):
        import threading
        super().__init__(window);self.window=window;self.library=window.library;self.plan=None;self.results=[];self.running=False;self.cancel_event=threading.Event();self.ticket=None
        self.setWindowTitle('批次修正：明確範圍與逐筆結果');self.resize(1200,850);layout=QVBoxLayout(self)
        self.status=QLabel('只改明確勾選的草稿／標記；高風險逐筆核對，不自動發布／正式輸出／學習。');self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);layout.addWidget(self.status)
        bar=QHBoxLayout();self.scope=QComboBox();self.scope.addItem('來源作品標記','ARTWORK');self.scope.addItem('未發布模板草稿','TEMPLATE');bar.addWidget(self.scope);self.search=QLineEdit();self.search.setPlaceholderText('作品／來源ID／人物公司／欄位／尺寸');bar.addWidget(self.search);self.state_filter=QComboBox();self.state_filter.addItems(['全部狀態','待預檢','可核對套用','需人工核對','已處理／待整卡重驗','失敗／過期']);bar.addWidget(self.state_filter);layout.addLayout(bar)
        self.counts=QLabel();self.coverage=QLabel()
        for label in [self.counts,self.coverage]:label.setWordWrap(True);layout.addWidget(label)
        self.table=QTableWidget(0,7);self.table.setHorizontalHeaderLabels(['勾選','作品／來源','確切物件ID','欄位／歸屬','實體尺寸','風險','逐筆狀態']);self.table.setSelectionBehavior(QTableWidget.SelectRows);layout.addWidget(self.table)
        bar=QHBoxLayout();self.action=QComboBox();self.action.addItems(['文字對齊','框位相對位移','框寬／高（固定字級）']);self.align=QComboBox();self.align.addItems(['center','left','right']);bar.addWidget(self.action);bar.addWidget(self.align)
        self.dx=QDoubleSpinBox();self.dy=QDoubleSpinBox();self.width=QDoubleSpinBox();self.height=QDoubleSpinBox()
        for name,spin in [('ΔX',self.dx),('ΔY',self.dy),('寬（0保持）',self.width),('高（0保持）',self.height)]:spin.setRange(-2000 if spin in (self.dx,self.dy) else 0,2000);spin.setDecimals(3);spin.setSuffix(' mm');bar.addWidget(QLabel(name));bar.addWidget(spin)
        layout.addLayout(bar);self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details);bar=QHBoxLayout()
        for name,title,slot in [('preview_button','預檢／逐項差異',self.preview),('apply_button','核對後套用／安全重試',self.apply),('cancel_button','停止尚未執行項',self.cancel),('undo_button','核對回復所選交易',self.undo),('locate_button','定位目前列／既有工具',self.locate)]:button=QPushButton(title);setattr(self,name,button);bar.addWidget(button);button.clicked.connect(slot)
        layout.addLayout(bar);self.batch_progress.connect(self.progress,Qt.QueuedConnection);self.scope.currentIndexChanged.connect(self.reload);self.search.textChanged.connect(self.filter_rows);self.state_filter.currentIndexChanged.connect(self.filter_rows);self.table.itemChanged.connect(self.filter_rows)
        for control in [self.action,self.align,self.dx,self.dy,self.width,self.height]:(control.valueChanged if isinstance(control,QDoubleSpinBox) else control.currentIndexChanged).connect(self.update_counts)
        self.reload()
    def valid_context(self):
        if self.library.closed or self.window.library is not self.library:raise ValueError('Library已切換／關閉；未對其他資料套用')
    def reload(self,*_):
        if self.running:return
        if self.library.closed or self.window.library is not self.library:self.status.setText('來源已切換，請回到原工作核對。');return
        self.plan=None;self.results=[];self.rows=[];self.by_key={};kind=self.scope.currentData();more=False;query=('SELECT id,name,payload FROM artworks' if kind=='ARTWORK' else "SELECT id,'' AS name,payload FROM templates")+' ORDER BY id LIMIT 201'
        for identity,name,raw in self.library.db.execute(query):
            payload=json.loads(raw)
            if kind=='TEMPLATE' and payload.get('state')!='draft':continue
            for slot in payload['slots']:
                if len(self.rows)>=200:more=True;break
                key=kind+':'+identity+':'+slot['id'];row=dict(key=key,id=identity,kind=kind,slot_ids=[slot['id']],name=payload.get('name') or name or identity,slot=slot,size=[payload.get('width_mm',payload.get('work_width')),payload.get('height_mm',payload.get('work_height'))],state='待預檢',risk='待預檢');self.rows.append(row);self.by_key[key]=row
            if more:break
        self.table.blockSignals(True);self.table.setSortingEnabled(False);self.table.setRowCount(len(self.rows))
        for i,row in enumerate(self.rows):
            item=QTableWidgetItem();item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable|Qt.ItemIsSelectable);item.setCheckState(Qt.Unchecked);item.setData(Qt.UserRole,row['key']);self.table.setItem(i,0,item)
            values=[row['name']+'／'+row['id'],row['slot_ids'][0],row['slot']['kind']+'／'+row['slot']['owner'],str(row['size'][0])+'×'+str(row['size'][1])+' mm',row['risk'],row['state']]
            for j,value in enumerate(values,1):item=QTableWidgetItem(value);item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable);self.table.setItem(i,j,item)
        self.table.setSortingEnabled(True);self.table.blockSignals(False);self.coverage.setText('已載入 '+str(len(self.rows))+' 個標記，最多200筆；不是全庫問題掃描。'+('還有未載入項目，不能計為已檢查。' if more else '只代表本次載入範圍。'));self.details.clear();self.filter_rows()
    def selected_rows(self):return [self.by_key[self.table.item(i,0).data(Qt.UserRole)] for i in range(self.table.rowCount()) if self.table.item(i,0).checkState()==Qt.Checked]
    def parameters(self):return [self.action.currentIndex(),self.align.currentText(),self.dx.value(),self.dy.value(),self.width.value(),self.height.value()]
    def selection_pin(self):return sorted(r['key'] for r in self.selected_rows())
    def filter_rows(self,*_):
        terms=self.search.text().casefold().split();wanted=self.state_filter.currentText()
        for i in range(self.table.rowCount()):
            row=self.by_key[self.table.item(i,0).data(Qt.UserRole)];text=' '.join(self.table.item(i,j).text() for j in range(1,7)).casefold();state=row['state'];match=all(t in text for t in terms)
            if wanted!='全部狀態':match=match and (state==wanted or (wanted=='失敗／過期' and any(s in state for s in ('失敗','過期','衝突','未核實'))))
            self.table.setRowHidden(i,not match)
        self.update_counts()
    def update_counts(self,*_):
        selected=self.selected_rows();safe=0
        if self.plan and not self.results and self.selection_pin()==self.selected_ids and self.parameters()==self.preview_parameters:safe=sum(len(r.get('changes',[])) for r in self.plan['rows'] if r['state']=='READY')
        visible=sum(not self.table.isRowHidden(i) for i in range(self.table.rowCount()));hidden=sum(self.table.isRowHidden(i) and self.table.item(i,0).checkState()==Qt.Checked for i in range(self.table.rowCount()));self.counts.setText(f'符合篩選 {visible} 筆／實際勾選 {len(selected)} 筆（篩選外仍勾選 {hidden}）／預檢可修改 {safe} 筆；不是印前PASS。')
    def request(self,ids):
        if self.action.currentIndex()==0:return dict(operation='PATCH',ids=ids,patch={'align':self.align.currentText()},cross_owner=False)
        if self.action.currentIndex()==1:return dict(operation='MOVE',ids=ids,dx=self.dx.value(),dy=self.dy.value(),cross_owner=False)
        return dict(operation='PATCH',ids=ids,patch={key:spin.value() for key,spin in [('w',self.width),('h',self.height)] if spin.value()>0},cross_owner=False)
    def paint(self,entity_key,state,risk=None):
        self.table.blockSignals(True);sorting=self.table.isSortingEnabled();self.table.setSortingEnabled(False)
        plan=getattr(self,'execution_plan',None) if self.running else self.plan
        scope=next((r.get('selected_slot_ids',r.get('request',{}).get('ids',[])) for r in (plan or {}).get('rows',[]) if r['target_key']==entity_key),[])
        for i in range(self.table.rowCount()):
            row=self.by_key[self.table.item(i,0).data(Qt.UserRole)]
            if row['kind']+':'+row['id']==entity_key and row['slot_ids'][0] in scope:
                row['state']=state;self.table.item(i,6).setText(state)
                if risk is not None:row['risk']=risk;self.table.item(i,5).setText(risk)
        self.table.setSortingEnabled(sorting);self.table.blockSignals(False)
    def preview(self):
        if self.running:self.status.setText('正在處理固定範圍；未重新預檢或重入。');return
        try:
            self.valid_context()
            from .training_navigation import require_clean_navigation
            require_clean_navigation(self.window);groups={}
            for row in self.selected_rows():groups.setdefault((row['kind'],row['id']),[]).extend(row['slot_ids'])
            targets=[dict(kind=kind,id=identity,slot_ids=ids,request=self.request(ids)) for (kind,identity),ids in groups.items()];self.plan=batch_plan(self.library,targets,self.align.currentText());self.preview_parameters=self.parameters();self.selected_ids=self.selection_pin();self.results=[];lines=[]
            for row in self.plan['rows']:
                risk={'LOW':'低風險','CONFIRM':'需核對幾何','HIGH':'需逐筆人工核對','NONE':'無實際差異'}[row['risk']];state='可核對套用' if row['state']=='READY' else '需人工核對' if row['state']=='BLOCKED' else '無實際差異／跳過';self.paint(row['target_key'],state,risk);lines.append(row['kind']+'/'+row['id']+'；'+risk+'；'+state+'\n'+row.get('reason','來源版本 '+str(row['snapshot']['revision']) if row.get('snapshot') else '來源待核實'))
                for change in row.get('changes',[]):
                    def rect(r):return 'X '+str(r['x'])+'／Y '+str(r['y'])+'／寬 '+str(r['w'])+'／高 '+str(r['h'])+' mm'
                    lines.append(change['owner']+'/'+change['kind']+'/'+change['id']+'\n原 '+rect(change['before']['rect'])+' → 新 '+rect(change['after']['rect'])+'；固定字級 '+str(change['before']['size_pt'])+' → '+str(change['after']['size_pt'])+' pt；對齊 '+str(change['before']['align'])+' → '+str(change['after']['align']))
                lines.extend(row.get('warnings',[]))
            self.details.setPlainText('\n'.join(lines));self.status.setText('已預檢本次原子交易範圍；高風險不自動核准，整作品印前仍待完整驗證。');self.filter_rows()
        except Exception as error:self.plan=None;self.status.setText('未預檢：'+str(error))
    def apply(self):
        try:
            if self.running:self.status.setText('正在處理固定範圍；未重複提交。');return
            self.valid_context()
            if self.window.busy:raise ValueError('既有工作正在處理，先保留此批範圍')
            if not self.plan or self.parameters()!=self.preview_parameters or self.selected_ids!=self.selection_pin():raise ValueError('範圍改變或沒有預覽，請重新預檢')
            from .training_navigation import require_clean_navigation
            require_clean_navigation(self.window);frozen=copy.deepcopy(self.plan)
            if QMessageBox.question(self,'批次差異確認','請逐項核對已預檢差異。僅處理 '+str(len(frozen['rows']))+' 個確切草稿／標記交易，不自動發布、正式輸出或學習。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            self.valid_context()
            if self.plan!=frozen or self.parameters()!=self.preview_parameters or self.selected_ids!=self.selection_pin():raise ValueError('確認期間範圍／預覽已變更；未提交，請重新預檢')
            self.start(frozen,False)
        except Exception as error:self.status.setText('未套用：'+str(error))
    def start(self,plan,inverse):
        self.cancel_event.clear();self.running=True;self.inverse=inverse;self.ticket=new_id();ticket=self.ticket;self.execution_plan=plan
        self.status.setText('已核對範圍；等待既有單一工作序列／資源，尚未執行或保存。')
        for control in [self.scope,self.preview_button,self.apply_button,self.undo_button]:control.setEnabled(False)
        progress=lambda row:self.batch_progress.emit(dict(ticket=ticket,row=row))
        root=str(self.library.root);cancel=self.cancel_event;results=copy.deepcopy(self.results);selected=list(self.undo_selected) if inverse else None
        def work():
            # Same existing single-worker/owned-connection pattern as candidate_edit_dispatch.
            from .storage import Library
            library=Library(root)
            try:return undo_batch(library,plan,results,True,selected,cancel=cancel.is_set,progress=progress) if inverse else apply_batch(library,plan,True,cancel.is_set,progress)
            finally:library.close()
        self.window.run_job('批次回復' if inverse else '批次修正',work,lambda rows:self.finished(rows,inverse),on_error=self.failed,cancel=self.cancel_event)
    def progress(self,value):
        if not self.running or value['ticket']!=self.ticket:return
        row=value['row'];state=self.state_label(row.get('outcome'));self.paint(row['target_key'],state);self.status.setText('本輪固定預檢範圍：'+row['id']+'／'+state+'；不宣稱整批通過。');self.filter_rows()
    @staticmethod
    def state_label(outcome):return {'PROCESSING':'正在處理','APPLIED_PENDING_FULL_VALIDATION':'已處理／待整卡重驗','APPLIED_BUT_CURRENT_CHANGED':'原操作已保存／目前另有新編輯','NEEDS_MANUAL_REVIEW':'需人工核對','SKIPPED_PRECONDITION':'無實際差異／跳過','STALE':'版本過期','FAILED':'失敗','RESULT_UNVERIFIED':'結果未核實','CANCELLED':'已取消未開始項','UNDONE_PENDING_FULL_VALIDATION':'已回復／待整卡重驗','ALREADY_UNDONE':'已核實原交易已回復','UNDO_CANCELLED':'已取消未開始回復','UNDO_CONFLICT':'回復衝突／未覆寫'}.get(outcome,str(outcome))
    def finished(self,rows,inverse=False):
        self.running=False
        for control in [self.scope,self.preview_button,self.apply_button,self.undo_button]:control.setEnabled(True)
        if not inverse:self.results=rows
        lines=[]
        for row in rows:self.paint(row['target_key'],self.state_label(row.get('outcome')));lines.append(row['kind']+'/'+row['id']+'：'+self.state_label(row.get('outcome'))+'\n'+row.get('reason','沿用既有歷史核對，尚須整作品重驗')+('\n歷史 '+row['history_id'] if row.get('history_id') else ''))
        self.details.setPlainText('\n'.join(lines));summary=batch_summary(rows);self.status.setText(f'逐項結果：核對 {summary["checked"]} 個交易、嘗試 {summary["attempted"]}；套用待重驗 {summary["applied_pending_validation"]}、失敗 {summary["failed"]}、過期 {summary["stale"]}、需人工 {summary["manual"]}、跳過 {summary["skipped"]}、取消 {summary["cancelled"]}、另有新版 {summary["current_changed"]}、已回復 {summary["undone"]}、回復衝突 {summary["undo_conflicts"]}。不是印前PASS。')
        if self.window.library is self.library and not self.library.closed:self.window.invalidate()
        self.filter_rows()
    def failed(self,text):
        try:rows=undo_batch(self.library,self.execution_plan,self.results,True,self.undo_selected,cancel=lambda:True) if self.inverse else apply_batch(self.library,self.execution_plan,True,cancel=lambda:True)
        except Exception:rows=[]
        self.finished(rows,self.inverse);self.status.setText('工作未正常完成：'+str(text)+'；依既有操作ID核對已保存項，其餘結果未安全保存，不承諾全批恢復。')
    def cancel(self):self.cancel_event.set();self.status.setText('已要求停止尚未執行項；已保存差異不因此撤銷。')
    def undo(self):
        try:
            self.valid_context()
            if self.running or self.window.busy:raise ValueError('既有工作進行中，未重複回復')
            if not self.plan or not self.results:raise ValueError('先檢視本批已核實歷史')
            selected={r['kind']+':'+r['id'] for r in self.selected_rows()};self.undo_selected=sorted(selected)
            if not selected:raise ValueError('請明確勾選要回復的交易；同交易全部差異需一併核對')
            frozen=copy.deepcopy(self.plan);scope='\n'.join(r['kind']+'/'+r['id']+'／'+','.join(c['id'] for c in r.get('changes',[])) for r in frozen['rows'] if r['target_key'] in selected)
            if QMessageBox.question(self,'核對合法部分回復','只回復仍可逆的原子交易。同組全部差異如下；新人工編輯／版本衝突不強行覆寫。\n'+scope,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            self.valid_context()
            if self.plan!=frozen or selected!={r['kind']+':'+r['id'] for r in self.selected_rows()}:raise ValueError('回復確認期間範圍已改，未執行')
            self.start(frozen,True)
        except Exception as error:self.status.setText('未回復：'+str(error))
    def locate(self):
        try:
            self.valid_context()
            if self.running:raise ValueError('先停止並核對逐筆結果')
            item=self.table.item(self.table.currentRow(),0)
            if item is None:raise ValueError('請先選取一列')
            row=self.by_key[item.data(Qt.UserRole)];snapshot=self.library.object_snapshot(row['kind'],row['id'])
            if row['slot_ids'][0] not in {s['id'] for s in snapshot['payload']['slots']}:raise ValueError('物件引用已過期，未定位其他物件')
            from .training_navigation import require_clean_navigation
            require_clean_navigation(self.window);w=self.window;w.navigation.begin('批次修正問題定位')
            if row['kind']=='ARTWORK':work=self.library.artwork(row['id']);w.tabs.setCurrentIndex(0);w.refresh_sources(work['source_id']);w.load_work(work);w.train_canvas.select_id(row['slot_ids'][0])
            else:w.tabs.setCurrentIndex(1);w.template_stack.setCurrentIndex(1);w.template=None;w.refresh_templates(row['id']);w.editor_selection(row['slot_ids'])
            w.navigation.finish();self.accept()
        except Exception as error:self.status.setText('未定位：'+str(error))
    def reject(self):
        if self.running:self.cancel();return
        super().reject()
    def closeEvent(self,event):
        if self.running:self.cancel();event.ignore();return
        super().closeEvent(event)

"""Bounded text-alignment batch adapter: reuse proposals, CAS, history and per-item commits."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gui import MainWindow
import json,copy,sqlite3
from PySide6.QtCore import Qt,Signal
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QPlainTextEdit,QMessageBox,QComboBox,QLineEdit,QDoubleSpinBox
from .customers import digest
from .object_tools import propose,select_slots,NoObjectChange
from .model import new_id,KINDS

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
    if request.get('operation') not in ('PATCH','PATCH_EACH','MOVE','ALIGN','DISTRIBUTE') or request.get('cross_owner') is not False:raise ValueError('批次不能解鎖、刪除或跨人物公司；請逐筆人工核對')
    if request['operation']=='PATCH' and (not request.get('patch') or set(request['patch'])-{'align','color','x','y','w','h'}):raise ValueError('批次不可修改人物／公司／字級／字型／文字下限或Logo')


def fit_width_request(candidate,ids,ratio):
    import math
    if type(ratio) not in (int,float) or not math.isfinite(ratio) or not 0<ratio<=1:raise ValueError('X比例需為有限且大於0、至多100%')
    slots=select_slots(candidate.template.to_dict(),ids);patches={}
    for slot in slots:
        if slot.kind=='logo' or slot.locked or ratio<slot.min_scale:raise ValueError('固定字級／X下限／完整Logo或鎖定條件不可放寬')
        rows=[row for row in candidate.measurements if row.get('slot_ids')==[slot.id]]
        width=rows[0].get('parameters',{}).get('text_width_mm') if len(rows)==1 else None
        if type(width) not in (float,int) or not math.isfinite(width) or width<=0:raise ValueError('此確切文字框缺原引擎字寬量測，不猜測比例')
        patches[slot.id]=dict(w=width*ratio)
    return dict(operation='PATCH_EACH',ids=list(ids),patches=patches,cross_owner=False)


def candidate_target_seal(target):
    from .layout_recovery import encode_candidate
    envelope=target['envelope']
    return digest(dict(key=target['target_key'],references=target['references'],before_pin=target['before_pin'],envelope={k:(encode_candidate(v) if k=='before' else v) for k,v in envelope.items()}))


def candidate_origin_key(window,index):
    owner=getattr(window,'owner',window)
    if not hasattr(owner,'_batch_scope_id'):owner._batch_scope_id=new_id()
    parts=['MAIN',owner._batch_scope_id]
    if hasattr(window,'entry'):
        service=window.service
        if not hasattr(service,'_batch_scope_id'):service._batch_scope_id=new_id()
        parts=['SIZE',owner._batch_scope_id,service._batch_scope_id,window.entry['key']]
    return ':'.join(parts+[str(index),window.candidates[index].template.id])


def prepare_candidate_target(window,index,request,*,key=None,cross_confirmed=False):
    from .candidate_edit import plan_operation,prepare_edit
    from .candidate_sync import candidate_pin,field_reference
    if window.library.closed or not 0<=index<len(window.candidates):raise ValueError('候選來源不可用')
    origin=candidate_origin_key(window,index)
    if key is not None and key!=origin:raise ValueError('候選工作視窗／尺寸來源標識不符')
    candidate=window.candidates[index];slots=select_slots(candidate.template.to_dict(),request.get('ids'));request=copy.deepcopy(request)
    if any(s.kind=='logo' or s.locked for s in slots):raise ValueError('完整Logo／鎖定框須逐筆核對，不自動核准')
    references=[field_reference(candidate,slot) for slot in slots]
    if request.get('cross_owner') is True and cross_confirmed is not True:raise ValueError('跨人物公司範圍尚未明確核對')
    validate_request({**request,'cross_owner':False})
    snapshot=candidate.risk_context.get('input_snapshot',{});inputs=window.input_data()
    if digest(inputs)!=digest(tuple(snapshot.get(k) for k in ('people','companies','logos'))):raise ValueError('當前資料與候選人物／欄位快照不一致，先同步重驗')
    plan=plan_operation(window,index,request);envelope=prepare_edit(window,plan)
    target=dict(kind='CANDIDATE',id=candidate.template.id,index=index,target_key=origin,size=[candidate.template.width_mm,candidate.template.height_mm],before_pin=candidate_pin(candidate),references=references,envelope=envelope)
    target['seal']=candidate_target_seal(target);return target


def calculate_candidate_target(target,library):
    from .candidate_edit import calculate_edit
    from .layout_recovery import encode_candidate
    if target['seal']!=candidate_target_seal(target) or str(library.root)!=target['envelope']['root']:raise ValueError('候選預檢來源／精確範圍已變更')
    result=calculate_edit(copy.deepcopy(target['envelope']),library);outcome='READY' if result.formal_eligible else 'NEEDS_MANUAL_REVIEW'
    checked=dict(target=copy.deepcopy(target),candidate=result,outcome=outcome,formal_eligible=False)
    checked['seal']=digest(dict(target=target['seal'],candidate=encode_candidate(result),outcome=outcome));return checked


def candidate_target_current(window,target):
    from .candidate_sync import candidate_pin
    from .candidate_edit import dependency_token
    envelope=target['envelope'];index=target['index']
    try:
        return (not window.library.closed and str(window.library.root)==envelope['root'] and window.generation==envelope['plan']['generation']
            and candidate_origin_key(window,index)==target['target_key'] and candidate_pin(window.candidates[index])==target['before_pin']
            and digest(window.input_data())==envelope['input_digest'] and dependency_token(window,window.candidates[index].template,envelope['logos'])==envelope['dependency_token'])
    except (ValueError,IndexError,KeyError,TypeError,AttributeError):return False


def prepare_candidate_undo(window,target,receipt_id):
    from .candidate_edit import plan_undo,prepare_edit
    from .candidate_sync import candidate_pin,field_reference
    index=target['index']
    if candidate_origin_key(window,index)!=target['target_key']:raise ValueError('原候選／尺寸來源已變更')
    candidate=window.candidates[index];ids=target['envelope']['plan']['request']['ids']
    references=[field_reference(candidate,s) for s in select_slots(candidate.template.to_dict(),ids)]
    if digest(references)!=digest(target['references']):raise ValueError('原人物／公司欄位已變更，不回復到其他實體')
    envelope=prepare_edit(window,plan_undo(window,index,receipt_id))
    inverse=dict(target, before_pin=candidate_pin(candidate),envelope=envelope);inverse['seal']=candidate_target_seal(inverse);return inverse


def install_candidate_target(window,checked,approved=False):
    from .candidate_edit import install_edit,dependency_token
    from .candidate_sync import candidate_pin
    from .layout_recovery import encode_candidate
    if approved is not True:raise ValueError('需明確確認此候選與尺寸差異')
    target=checked['target'];envelope=target['envelope'];index=target['index']
    if target['seal']!=candidate_target_seal(target) or checked['seal']!=digest(dict(target=target['seal'],candidate=encode_candidate(checked['candidate']),outcome=checked['outcome'])):raise ValueError('預檢差異或結果已變更，未套用')
    if checked['outcome']!='READY':raise ValueError('未完成合法整卡預檢，不自動核准硬性失敗／缺證據')
    if not checked['candidate'].formal_eligible:raise ValueError('目前來源／重審／完整Gate已變更，原預檢需重新核對；未套用')
    if window.library.closed or str(window.library.root)!=envelope['root'] or window.generation!=envelope['plan']['generation'] or not 0<=index<len(window.candidates):raise ValueError('來源／候選世代已變更')
    if candidate_origin_key(window,index)!=target['target_key']:raise ValueError('候選工作視窗／尺寸服務已換代，未套至其他實體')
    current=window.candidates[index];inverse=envelope['plan']['request']['operation']=='UNDO'
    expected=next(r for r in envelope['manual_metadata']['manual_history'] if r['id']==envelope['plan']['request']['receipt_id']) if inverse else envelope['manual_metadata']['manual_history'][-1]
    history=current.risk_context.get('manual_history',[]);existing=next((r for r in history if r['id']==expected['id']),None)
    if inverse:
        if existing and existing.get('undone'):
            if candidate_pin(current)!=candidate_pin(checked['candidate']):raise ValueError('原回復後已有新編輯；不覆寫目前版本')
            return dict(target_key=target['target_key'],outcome='ALREADY_UNDONE',formal_eligible=False,receipt_id=expected['id'])
        if not candidate_target_current(window,target):raise ValueError('回復預檢後目前版面／資料已變更')
        result=install_edit(window,copy.deepcopy(envelope),copy.deepcopy(checked['candidate']))
        return dict(target_key=target['target_key'],outcome='UNDONE_VALIDATED',formal_eligible=result.formal_eligible,receipt_id=expected['id'])
    if existing:
        if existing.get('undone'):raise ValueError('此批操作已回復；安全重試不能盲目重做')
        unchanged=existing==expected and candidate_pin(current)==candidate_pin(checked['candidate']) and digest(window.input_data())==envelope['input_digest'] and dependency_token(window,current.template,envelope['logos'])==envelope['dependency_token']
        return dict(target_key=target['target_key'],outcome='ALREADY_APPLIED' if unchanged else 'APPLIED_BUT_CURRENT_CHANGED',formal_eligible=False,receipt_id=existing['id'])
    if candidate_pin(current)!=target['before_pin']:raise ValueError('較新人工變更／核對已存在，不覆寫舊預檢')
    result=install_edit(window,copy.deepcopy(envelope),copy.deepcopy(checked['candidate']))
    return dict(target_key=target['target_key'],outcome='APPLIED_VALIDATED' if result.formal_eligible else 'APPLIED_BLOCKED',formal_eligible=result.formal_eligible,receipt_id=expected['id'])


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
    return dict(checked=len(results),attempted=sum(bool(r.get('attempted')) for r in results),applied_pending_validation=applied,current_changed=changed,failed=counts.get('FAILED',0),unverified=counts.get('RESULT_UNVERIFIED',0),stale=counts.get('STALE',0),manual=counts.get('NEEDS_MANUAL_REVIEW',0)+counts.get('APPLIED_BLOCKED',0),cancelled=counts.get('CANCELLED',0)+counts.get('UNDO_CANCELLED',0),undone=counts.get('UNDONE_PENDING_FULL_VALIDATION',0)+counts.get('ALREADY_UNDONE',0)+counts.get('UNDONE_VALIDATED',0),undo_conflicts=counts.get('UNDO_CONFLICT',0),skipped=counts.get('SKIPPED_PRECONDITION',0),validated=counts.get('APPLIED_VALIDATED',0)+counts.get('UNDONE_VALIDATED',0),already_applied=counts.get('ALREADY_APPLIED',0),outcomes=counts,status='APPLIED_PENDING_REVALIDATION' if applied==len(results) and results else 'PARTIAL_OR_BLOCKED',formal_eligible=False)

class BatchObjectDialog(QDialog):
    batch_progress=Signal(object)
    def __init__(self,window,origin=None):
        import threading
        super().__init__(window);self.host_window: MainWindow=window;self.library=window.library;self.plan=None;self.results=[];self.running=False;self.cancel_event=threading.Event();self.ticket=None;self.preflight_text='';self.last_result_text=''
        self.setWindowTitle('批次修正：明確範圍與逐筆結果');self.resize(1200,850);layout=QVBoxLayout(self)
        self.status=QLabel('只改明確勾選的草稿／標記；高風險逐筆核對，不自動發布／正式輸出／學習。');self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);layout.addWidget(self.status)
        bar=QHBoxLayout();self.scope=QComboBox();self.scope.addItem('來源作品標記','ARTWORK');self.scope.addItem('未發布模板草稿','TEMPLATE');bar.addWidget(self.scope);self.search=QLineEdit();self.search.setPlaceholderText('作品／來源ID／人物公司／欄位／尺寸');bar.addWidget(self.search);self.state_filter=QComboBox();self.state_filter.addItems(['全部狀態','待預檢','可核對套用','需人工核對','已處理／待整卡重驗','失敗／過期']);bar.addWidget(self.state_filter);layout.addLayout(bar)
        self.counts=QLabel();self.coverage=QLabel()
        for label in [self.counts,self.coverage]:label.setWordWrap(True);layout.addWidget(label)
        self.table=QTableWidget(0,7);self.table.setHorizontalHeaderLabels(['勾選','作品／來源','確切物件ID','欄位／歸屬','實體尺寸','風險','逐筆狀態']);self.table.setSelectionBehavior(QTableWidget.SelectRows);layout.addWidget(self.table)
        bar=QHBoxLayout();self.action=QComboBox();self.action.addItems(['文字對齊','框位相對位移','框寬／高（固定字級）']);self.align=QComboBox();[self.align.addItem(label,value) for label,value in [('置中','center'),('靠左','left'),('靠右','right')]];bar.addWidget(self.action);bar.addWidget(self.align)
        self.dx=QDoubleSpinBox();self.dy=QDoubleSpinBox();self.width_input=QDoubleSpinBox();self.height_input=QDoubleSpinBox()
        for name,spin in [('ΔX',self.dx),('ΔY',self.dy),('寬（0保持）',self.width_input),('高（0保持）',self.height_input)]:spin.setRange(-2000 if spin in (self.dx,self.dy) else 0,2000);spin.setDecimals(3);spin.setSuffix(' mm');bar.addWidget(QLabel(name));bar.addWidget(spin)
        layout.addLayout(bar);self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details);bar=QHBoxLayout()
        for name,title,slot in [('preview_button','預檢／逐項差異',self.preview),('apply_button','核對後套用／安全重試',self.apply),('cancel_button','停止尚未執行項',self.cancel),('undo_button','核對回復所選交易',self.undo),('locate_button','定位目前列／既有工具',self.locate)]:button=QPushButton(title);setattr(self,name,button);bar.addWidget(button);button.clicked.connect(slot)
        layout.addLayout(bar);self.batch_progress.connect(self.progress,Qt.QueuedConnection);self.scope.currentIndexChanged.connect(self.reload);self.search.textChanged.connect(self.filter_rows);self.state_filter.currentIndexChanged.connect(self.filter_rows);self.table.itemChanged.connect(self.filter_rows)
        for control in [self.action,self.align,self.dx,self.dy,self.width_input,self.height_input]:(control.valueChanged if isinstance(control,QDoubleSpinBox) else control.currentIndexChanged).connect(self.update_counts)
        view_bar=QHBoxLayout()
        for title,slot in [('查看本批原預檢差異',lambda:self.details.setPlainText(self.preflight_text)),('查看最新逐筆結果',lambda:self.details.setPlainText(self.last_result_text))]:button=QPushButton(title);button.clicked.connect(slot);view_bar.addWidget(button)
        layout.insertLayout(layout.indexOf(self.details),view_bar)
        from .batch_candidate_ui import CandidateBatchController
        self.candidate_batch=CandidateBatchController(self,origin or window)
        self.scope.blockSignals(True);self.scope.addItem('目前候選／尺寸（獨立預檢）','CANDIDATE');self.scope.blockSignals(False)
        self.action.blockSignals(True);self.action.addItem('文字X比例（固定字級）');self.action.blockSignals(False);self.ratio=QDoubleSpinBox();self.ratio.setRange(1,100);self.ratio.setValue(90);self.ratio.setSuffix(' % X');bar.addWidget(self.ratio);self.ratio.valueChanged.connect(self.update_counts)
        from .batch_recovery import BatchRecoveryController
        self.recovery_controller=BatchRecoveryController(self);recovery_bar=QHBoxLayout()
        for title,slot in [('保存停止快照（24小時加密）',self.recovery_controller.save),('核對已保存批次',self.recovery_controller.restore),('清除批次暫存',self.recovery_controller.clear)]:
            button=QPushButton(title);button.clicked.connect(slot);recovery_bar.addWidget(button)
        layout.addLayout(recovery_bar)
        self.graphic_button=QPushButton('目前列：原／新圖形差異（唯讀）');self.graphic_button.clicked.connect(self.graphic_preview);layout.addWidget(self.graphic_button)
        self.table.cellDoubleClicked.connect(lambda *_:self.locate())
        self.reload()
    def valid_context(self):
        if self.library.closed or self.host_window.library is not self.library:raise ValueError('Library已切換／關閉；未對其他資料套用')
    def reload(self,*_):
        if self.running:return
        if self.library.closed or self.host_window.library is not self.library:self.status.setText('來源已切換，請回到原工作核對。');return
        self.plan=None;self.results=[];self.rows=[];self.by_key={};kind=self.scope.currentData();more=False;query=('SELECT id,name,payload FROM artworks' if kind=='ARTWORK' else "SELECT id,'' AS name,payload FROM templates")+' ORDER BY id LIMIT 201'
        if kind=='CANDIDATE':
            try:self.rows,more=self.candidate_batch.rows();self.by_key={r['key']:r for r in self.rows}
            except Exception as error:self.status.setText(str(error))
        for identity,name,raw in ([] if kind=='CANDIDATE' else self.library.db.execute(query)):
            payload=json.loads(raw)
            if kind=='TEMPLATE' and payload.get('state')!='draft':continue
            for slot in payload['slots']:
                if len(self.rows)>=200:more=True;break
                key=kind+':'+identity+':'+slot['id'];row=dict(key=key,id=identity,kind=kind,slot_ids=[slot['id']],name=payload.get('name') or name or identity,slot=slot,size=[payload.get('width_mm',payload.get('work_width')),payload.get('height_mm',payload.get('work_height'))],state='待預檢',risk='待預檢');self.rows.append(row);self.by_key[key]=row
            if more:break
        self.table.blockSignals(True);self.table.setSortingEnabled(False);self.table.setRowCount(len(self.rows))
        for i,row in enumerate(self.rows):
            item=QTableWidgetItem();item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable|Qt.ItemIsSelectable);item.setCheckState(Qt.Unchecked);item.setData(Qt.UserRole,row['key']);self.table.setItem(i,0,item)
            values=[row['name']+'／'+row['id'],row['slot_ids'][0],KINDS.get(row['slot']['kind'],row['slot']['kind'])+'／'+row['slot']['owner'],str(row['size'][0])+'×'+str(row['size'][1])+' mm',row['risk'],row['state']]
            for j,value in enumerate(values,1):item=QTableWidgetItem(value);item.setToolTip(value+'\n'+row.get('context',''));item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable);self.table.setItem(i,j,item)
        for column,width in enumerate([44,220,250,140,100,135,240]):self.table.setColumnWidth(column,width)
        self.table.horizontalHeader().setStretchLastSection(True);self.table.setWordWrap(False)
        self.preflight_text='';self.last_result_text=''
        self.table.setSortingEnabled(True);self.table.blockSignals(False);self.coverage.setText('已載入 '+str(len(self.rows))+' 個標記，最多200筆；不是全庫問題掃描。'+('還有未載入項目，不能計為已檢查。' if more else '只代表本次載入範圍。'));self.details.clear();self.filter_rows()
    def selected_rows(self):return [self.by_key[self.table.item(i,0).data(Qt.UserRole)] for i in range(self.table.rowCount()) if self.table.item(i,0).checkState()==Qt.Checked]
    def parameters(self):return [self.action.currentIndex(),self.align.currentData(),self.dx.value(),self.dy.value(),self.width_input.value(),self.height_input.value(),self.ratio.value()]
    def selection_pin(self):return sorted(r['key'] for r in self.selected_rows())
    def filter_rows(self,*_):
        terms=self.search.text().casefold().split();wanted=self.state_filter.currentText()
        for i in range(self.table.rowCount()):
            row=self.by_key[self.table.item(i,0).data(Qt.UserRole)];text=(' '.join(self.table.item(i,j).text() for j in range(1,7))+' '+row['slot']['kind']+' '+row['slot']['owner']+' '+row.get('context','')).casefold();state=row['state'];match=all(t in text for t in terms)
            if wanted!='全部狀態':match=match and (state==wanted or (wanted=='失敗／過期' and any(s in state for s in ('失敗','過期','衝突','未核實'))))
            self.table.setRowHidden(i,not match)
        self.update_counts()
    def update_counts(self,*_):
        candidate=self.scope.currentData()=='CANDIDATE';action=self.action.currentIndex()
        self.align.setEnabled(action==0);self.dx.setEnabled(action==1);self.dy.setEnabled(action==1);self.width_input.setEnabled(action==2);self.height_input.setEnabled(action==2);self.ratio.setEnabled(candidate and action==3)
        selected=self.selected_rows();safe=0
        if self.plan and not self.results and self.selection_pin()==self.selected_ids and self.parameters()==self.preview_parameters:safe=sum(len(r.get('changes',[])) for r in self.plan['rows'] if r['state']=='READY')
        visible=sum(not self.table.isRowHidden(i) for i in range(self.table.rowCount()));hidden=sum(self.table.isRowHidden(i) and self.table.item(i,0).checkState()==Qt.Checked for i in range(self.table.rowCount()));self.counts.setText(f'符合篩選 {visible} 筆／實際勾選 {len(selected)} 筆（篩選外仍勾選 {hidden}）／預檢可修改 {safe} 筆；不是印前PASS。')
    def request(self,ids):
        if self.action.currentIndex()==0:return dict(operation='PATCH',ids=ids,patch={'align':self.align.currentData()},cross_owner=False)
        if self.action.currentIndex()==1:return dict(operation='MOVE',ids=ids,dx=self.dx.value(),dy=self.dy.value(),cross_owner=False)
        return dict(operation='PATCH',ids=ids,patch={key:spin.value() for key,spin in [('w',self.width_input),('h',self.height_input)] if spin.value()>0},cross_owner=False)
    def paint(self,entity_key,state,risk=None):
        self.table.blockSignals(True);sorting=self.table.isSortingEnabled();self.table.setSortingEnabled(False)
        plan=getattr(self,'execution_plan',None) if self.running else self.plan
        scope=next((r.get('selected_slot_ids',r.get('request',{}).get('ids',[])) for r in (plan or {}).get('rows',[]) if r['target_key']==entity_key),[])
        for i in range(self.table.rowCount()):
            row=self.by_key[self.table.item(i,0).data(Qt.UserRole)]
            if row.get('scope_key',row['kind']+':'+row['id'])==entity_key and row['slot_ids'][0] in scope:
                row['state']=state;self.table.item(i,6).setText(state)
                if risk is not None:row['risk']=risk;self.table.item(i,5).setText(risk)
        self.table.setSortingEnabled(sorting);self.table.blockSignals(False)
    def preview(self):
        if self.scope.currentData()=='CANDIDATE':return self.candidate_batch.preview()
        if self.running:self.status.setText('正在處理固定範圍；未重新預檢或重入。');return
        try:
            self.valid_context()
            from .training_navigation import require_clean_navigation
            require_clean_navigation(self.host_window);groups={}
            for row in self.selected_rows():groups.setdefault((row['kind'],row['id']),[]).extend(row['slot_ids'])
            targets=[dict(kind=kind,id=identity,slot_ids=ids,request=self.request(ids)) for (kind,identity),ids in groups.items()];self.plan=batch_plan(self.library,targets,self.align.currentData());self.preview_parameters=self.parameters();self.selected_ids=self.selection_pin();self.results=[];lines=[]
            for row in self.plan['rows']:
                risk={'LOW':'低風險','CONFIRM':'需核對幾何','HIGH':'需逐筆人工核對','NONE':'無實際差異'}[row['risk']];state='可核對套用' if row['state']=='READY' else '需人工核對' if row['state']=='BLOCKED' else '無實際差異／跳過';self.paint(row['target_key'],state,risk);lines.append(row['kind']+'/'+row['id']+'；'+risk+'；'+state+'\n'+row.get('reason','來源版本 '+str(row['snapshot']['revision']) if row.get('snapshot') else '來源待核實'))
                for change in row.get('changes',[]):
                    def rect(r):return 'X '+str(r['x'])+'／Y '+str(r['y'])+'／寬 '+str(r['w'])+'／高 '+str(r['h'])+' mm'
                    lines.append(change['owner']+'/'+change['kind']+'/'+change['id']+'\n原 '+rect(change['before']['rect'])+' → 新 '+rect(change['after']['rect'])+'；固定字級 '+str(change['before']['size_pt'])+' → '+str(change['after']['size_pt'])+' pt；對齊 '+str(change['before']['align'])+' → '+str(change['after']['align']))
                lines.extend(row.get('warnings',[]))
            self.preflight_text='\n'.join(lines);self.last_result_text='';self.details.setPlainText(self.preflight_text);self.status.setText('已預檢本次原子交易範圍；高風險不自動核准，整作品印前仍待完整驗證。');self.filter_rows()
        except Exception as error:self.plan=None;self.status.setText('未預檢：'+str(error))
    def apply(self):
        if self.scope.currentData()=='CANDIDATE':return self.candidate_batch.apply()
        try:
            if self.running:self.status.setText('正在處理固定範圍；未重複提交。');return
            self.valid_context()
            if self.host_window.busy:raise ValueError('既有工作正在處理，先保留此批範圍')
            if not self.plan or self.parameters()!=self.preview_parameters or self.selected_ids!=self.selection_pin():raise ValueError('範圍改變或沒有預覽，請重新預檢')
            from .training_navigation import require_clean_navigation
            require_clean_navigation(self.host_window);frozen=copy.deepcopy(self.plan);self.details.setPlainText(self.preflight_text)
            if QMessageBox.question(self,'批次差異確認','請核對下方原預檢差異。已完成項依操作紀錄讀回，不重複套用；尚未完成項仍須當前前置條件一致。僅處理 '+str(len(frozen['rows']))+' 個確切草稿／標記交易，不自動發布、正式輸出或學習。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
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
        self.host_window.run_job('批次回復' if inverse else '批次修正',work,lambda rows:self.finished(rows,inverse),on_error=self.failed,cancel=self.cancel_event)
    def progress(self,value):
        if not self.running or value['ticket']!=self.ticket:return
        row=value['row'];state=self.state_label(row.get('outcome'));self.paint(row['target_key'],state);self.status.setText('本輪固定預檢範圍：'+row['id']+'／'+state+'；不宣稱整批通過。');self.filter_rows()
    @staticmethod
    def state_label(outcome):return {'APPLIED_VALIDATED':'已套用／本尺寸整卡合格','ALREADY_APPLIED':'已核實原候選操作／未重複套用','APPLIED_BLOCKED':'已套用／仍受阻擋','UNDONE_VALIDATED':'已回復／本尺寸整卡合格','PROCESSING':'正在處理','APPLIED_PENDING_FULL_VALIDATION':'已處理／待整卡重驗','APPLIED_BUT_CURRENT_CHANGED':'原操作已保存／目前另有新編輯','NEEDS_MANUAL_REVIEW':'需人工核對','SKIPPED_PRECONDITION':'無實際差異／跳過','STALE':'版本過期','FAILED':'失敗','RESULT_UNVERIFIED':'結果未核實','CANCELLED':'已取消未開始項','UNDONE_PENDING_FULL_VALIDATION':'已回復／待整卡重驗','ALREADY_UNDONE':'已核實原交易已回復','UNDO_CANCELLED':'已取消未開始回復','UNDO_CONFLICT':'回復衝突／未覆寫'}.get(outcome,str(outcome))
    def finished(self,rows,inverse=False,*,invalidate=True):
        self.running=False
        for control in [self.scope,self.preview_button,self.apply_button,self.undo_button]:control.setEnabled(True)
        if not inverse:self.results=rows
        lines=[]
        for row in rows:
            self.paint(row['target_key'],self.state_label(row.get('outcome')))
            reason=row.get('reason') or ('已依目前資料重驗此候選與尺寸；正式輸出仍走既有授權。' if row.get('outcome') in ('APPLIED_VALIDATED','UNDONE_VALIDATED') else '已核實原操作與版面，未重複修改；正式輸出仍核對目前Gate。' if row.get('outcome')=='ALREADY_APPLIED' else '沿用既有歷史核對，尚須整作品重驗')
            lines.append(row['kind']+'/'+row['id']+'：'+self.state_label(row.get('outcome'))+'\n'+reason+('\n歷史 '+row['history_id'] if row.get('history_id') else ''))
        self.last_result_text='\n'.join(lines);self.details.setPlainText(self.last_result_text);summary=batch_summary(rows);self.status.setText(f'逐項結果：核對 {summary["checked"]} 個交易、嘗試 {summary["attempted"]}；本尺寸合格 {summary["validated"]}、原操作已核實 {summary["already_applied"]}、套用待重驗 {summary["applied_pending_validation"]}、失敗 {summary["failed"]}、未核實 {summary["unverified"]}、過期 {summary["stale"]}、需人工 {summary["manual"]}、跳過 {summary["skipped"]}、取消 {summary["cancelled"]}、另有新版 {summary["current_changed"]}、已回復 {summary["undone"]}、回復衝突 {summary["undo_conflicts"]}。不是印前PASS。')
        if invalidate and self.host_window.library is self.library and not self.library.closed:self.host_window.invalidate()
        self.filter_rows()
    def failed(self,text):
        try:rows=undo_batch(self.library,self.execution_plan,self.results,True,self.undo_selected,cancel=lambda:True) if self.inverse else apply_batch(self.library,self.execution_plan,True,cancel=lambda:True)
        except Exception:rows=[]
        self.finished(rows,self.inverse);self.status.setText('工作未正常完成：'+str(text)+'；依既有操作ID核對已保存項，其餘結果未安全保存，不承諾全批恢復。')
    def cancel(self):self.cancel_event.set();self.status.setText('已要求停止尚未執行項；已保存差異不因此撤銷。')
    def undo(self):
        if self.scope.currentData()=='CANDIDATE':return self.candidate_batch.undo()
        try:
            self.valid_context()
            if self.running or self.host_window.busy:raise ValueError('既有工作進行中，未重複回復')
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
            if self.scope.currentData()=='CANDIDATE':return self.candidate_batch.locate()
            self.valid_context()
            if self.running:raise ValueError('先停止並核對逐筆結果')
            item=self.table.item(self.table.currentRow(),0)
            if item is None:raise ValueError('請先選取一列')
            row=self.by_key[item.data(Qt.UserRole)];snapshot=self.library.object_snapshot(row['kind'],row['id'])
            if row['slot_ids'][0] not in {s['id'] for s in snapshot['payload']['slots']}:raise ValueError('物件引用已過期，未定位其他物件')
            from .training_navigation import require_clean_navigation
            require_clean_navigation(self.host_window);w=self.host_window;w.navigation.begin('批次修正問題定位')
            if row['kind']=='ARTWORK':work=self.library.artwork(row['id']);w.tabs.setCurrentIndex(0);w.refresh_sources(work['source_id']);w.load_work(work);w.train_canvas.select_id(row['slot_ids'][0])
            else:w.tabs.setCurrentIndex(1);w.template_stack.setCurrentIndex(1);w.template=None;w.refresh_templates(row['id']);w.editor_selection(row['slot_ids'])
            w.navigation.finish();self.accept()
        except Exception as error:self.status.setText('未定位：'+str(error))

    def make_graphic_preview(self):
        from .batch_preview import make_preview
        return make_preview(self)
    def graphic_preview(self):
        try:
            dialog=self.make_graphic_preview()
            try:dialog.exec()
            finally:dialog.deleteLater()
        except Exception as error:self.status.setText('未顯示圖形差異：'+str(error))
    def reject(self):
        if self.running:self.cancel();return
        super().reject()
    def closeEvent(self,event):
        if self.running:self.cancel();event.ignore();return
        super().closeEvent(event)

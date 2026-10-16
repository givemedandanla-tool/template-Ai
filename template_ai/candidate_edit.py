"""Edit one transient candidate instance through the existing geometry proposal engine."""
import copy,json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QListWidget,QListWidgetItem,QDoubleSpinBox,QPushButton,QPlainTextEdit,QLabel,QMessageBox
from .customers import digest
from .model import Template
from .object_tools import propose
from .layout import generate

def plan_operation(window,index,request,*,allow_stale=False):
    if not 0<=index<len(window.candidates):raise ValueError('候選不存在')
    c=window.candidates[index]
    if c.generation!=window.generation and not allow_stale:raise ValueError('候選版本已過期')
    if request.get('operation') not in ('MOVE','PATCH','LOCK'):raise ValueError('此處只處理當次幾何、屬性與明確鎖定')
    if request.get('operation')=='PATCH' and set(request.get('patch',{}))&{'size_pt','font','font_asset','font_style','kind','owner','index'}:raise ValueError('不能在當次快速編輯修改固定字級、字型來源或人物歸屬；請用既有核對入口')
    before=c.template.to_dict();local=copy.deepcopy(before);local['state']='draft';proposal=propose(local,'TEMPLATE',request)
    return dict(index=index,generation=window.generation,manual_revision=c.risk_context.get('manual_revision',0),before_digest=digest(before),template_id=c.template.id,size=[c.template.width_mm,c.template.height_mm],request=copy.deepcopy(request),changes=proposal['changes'],warnings=proposal['warnings'],scope='ONLY_THIS_CANDIDATE_SIZE',unaffected_candidates=len(window.candidates)-1)


def plan_candidate(window,index,ids,dx,dy):
    return plan_operation(window,index,dict(operation='MOVE',ids=list(ids),dx=dx,dy=dy,cross_owner=False))


def plan_undo(window,index):
    from .candidate_changes import inverse_delta
    if not 0<=index<len(window.candidates):raise ValueError('候選不存在')
    c=window.candidates[index];history=c.risk_context.get('manual_history',[]);receipt=next((row for row in reversed(history) if not row.get('undone')),None)
    if receipt is None:raise ValueError('此候選沒有可核對的未復原單筆變動')
    result=inverse_delta(c.template.to_dict(),receipt)
    return dict(index=index,generation=window.generation,manual_revision=c.risk_context.get('manual_revision',0),before_digest=digest(c.template.to_dict()),template_id=c.template.id,size=[c.template.width_mm,c.template.height_mm],request=dict(operation='UNDO',receipt_id=receipt['id']),after=result['template'],changes=result['actual_changes'],warnings=['只復原這筆實際屬性，保留其他變動；仍需以目前輸入重驗整張作品'],scope='ONLY_THIS_CANDIDATE_SIZE',unaffected_candidates=len(window.candidates)-1)


def prepare_edit(window,plan):
    fresh=plan_undo(window,plan['index']) if plan['request']['operation']=='UNDO' else plan_operation(window,plan['index'],plan['request'])
    if fresh!=plan:raise ValueError('候選／人工版本或輸入已改變，重新預覽')
    c=copy.deepcopy(window.candidates[plan['index']]);local=c.template.to_dict();local['state']='draft'
    after=copy.deepcopy(plan['after']) if plan['request']['operation']=='UNDO' else propose(local,'TEMPLATE',plan['request'])['after'];after['state']=c.template.state
    if not c.risk_context.get('source_template_pin'):
        from .training_store import digest as pin_digest
        try:base=window.library.object_snapshot('TEMPLATE',c.template.id)['payload']
        except ValueError:base=None
        if base and base['state']=='published' and pin_digest(base)==pin_digest(c.template.to_dict()):c.risk_context['source_template_pin']=dict(id=base['id'],version=base['version'],digest=pin_digest(base))
    inputs=copy.deepcopy(window.input_data())
    return dict(plan=copy.deepcopy(plan),before=c,after=after,people=inputs[0],companies=inputs[1],logos=inputs[2],input_digest=digest(inputs),root=str(window.library.root))


def calculate_edit(envelope,library):
    from .candidate_changes import manual_delta
    from .candidate_risk import bind_source,verify_original_source
    from .training_store import digest as pin_digest
    plan=envelope['plan'];before=envelope['before'];t=Template.from_dict(copy.deepcopy(envelope['after']));result=generate(t,envelope['people'],envelope['companies'],envelope['logos'],plan['generation'])
    for key in ('source_template_pin','original_source_proof','approved_base'):
        if key in before.risk_context:result.risk_context[key]=copy.deepcopy(before.risk_context[key])
    result.risk_context['conditions']=[copy.deepcopy(row) for row in before.risk_context.get('conditions',[]) if row['id']!='MANUAL_RECHECK_PENDING'];history=copy.deepcopy(before.risk_context.get('manual_history',[]))
    if plan['request']['operation']=='UNDO':
        for row in history:
            if row['id']==plan['request']['receipt_id']:row['undone']=True;row['digest']=pin_digest({k:v for k,v in row.items() if k!='digest'})
    else:history.append(manual_delta(before.template.to_dict(),result.template.to_dict()))
    result.risk_context.update(manual_history=history[-20:],manual_revision=plan['manual_revision']+1,manual_edit_receipt=copy.deepcopy(plan))
    try:verify_original_source(result,library)
    except (ValueError,OSError):pass
    bind_source(result,library,require_registered=True);result.reasons.append('僅當次候選的明確屬性變動，已以目前輸入重新檢查整張作品；未改模板、客戶或其他候選')
    return result


def install_edit(window,envelope,result):
    plan=envelope['plan'];index=plan['index']
    if window.generation!=plan['generation'] or digest(window.input_data())!=envelope['input_digest']:raise ValueError('較新的輸入已存在，過期結果已忽略')
    if not 0<=index<len(window.candidates):raise ValueError('候選清單已改變，過期結果已忽略')
    current=window.candidates[index]
    if current.template.id!=plan['template_id'] or digest(current.template.to_dict())!=plan['before_digest'] or current.risk_context.get('manual_revision',0)!=plan['manual_revision']:raise ValueError('目前已有較新的人工修改，過期結果已忽略')
    window.candidates[index]=result;window.choose_candidate(index);return result


def apply_candidate(window,plan,approved=False):
    if approved is not True:raise ValueError('需明確確認此候選尺寸差異')
    envelope=prepare_edit(window,plan);return install_edit(window,envelope,calculate_edit(envelope,window.library))


class CandidateEditDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.index=window.candidate_list.currentRow();self.plan=None;self.setWindowTitle('當次候選／尺寸局部位移（不改模板）');l=QVBoxLayout(self);self.status=QLabel('只處理目前候選尺寸；不跨候選複製座標，不回寫模板。每次變動分別保留版本，可預覽後復原單筆；正式輸出仍需完整重驗。');l.addWidget(self.status);self.objects=QListWidget();self.objects.setSelectionMode(QListWidget.ExtendedSelection);l.addWidget(self.objects)
        if 0<=self.index<len(window.candidates):
            for s in window.candidates[self.index].template.slots:
                item=QListWidgetItem(s.owner+'／'+s.kind+'／'+s.id);item.setData(Qt.UserRole,s.id);self.objects.addItem(item)
        bar=QHBoxLayout();self.dx=QDoubleSpinBox();self.dy=QDoubleSpinBox()
        for spin in (self.dx,self.dy):spin.setRange(-2000,2000);spin.setDecimals(4);spin.setSuffix(' mm');bar.addWidget(spin)
        b=QPushButton('預覽exact差異');b.clicked.connect(self.preview);bar.addWidget(b);self.apply_button=QPushButton('確認當次局部套用');self.apply_button.clicked.connect(self.apply);bar.addWidget(self.apply_button);self.undo_button=QPushButton('預覽復原本次單筆變動');self.undo_button.clicked.connect(self.preview_undo);bar.addWidget(self.undo_button);l.addLayout(bar);self.details=QPlainTextEdit();self.details.setReadOnly(True);l.addWidget(self.details);self.resize(900,650)
    def preview(self):
        try:self.plan=plan_candidate(self.window,self.index,[i.data(Qt.UserRole) for i in self.objects.selectedItems()],self.dx.value(),self.dy.value());self.details.setPlainText(json.dumps(self.plan,ensure_ascii=False,indent=2));self.status.setText('差異待確認；其他候選／尺寸不受影響')
        except Exception as e:self.plan=None;self.status.setText('未預覽：'+str(e))
    def preview_undo(self):
        try:self.plan=plan_undo(self.window,self.index);self.details.setPlainText(json.dumps(self.plan,ensure_ascii=False,indent=2));self.status.setText('僅復原最後一筆可核對變動；其他座標、物件、輸入與尺寸保留，套用後整張重驗')
        except ValueError as error:self.plan=None;self.status.setText('未預覽復原：'+str(error))
    def apply(self):
        try:
            if not self.plan:raise ValueError('先預覽')
            current=plan_undo(self.window,self.index) if self.plan['request']['operation']=='UNDO' else plan_candidate(self.window,self.index,[i.data(Qt.UserRole) for i in self.objects.selectedItems()],self.dx.value(),self.dy.value())
            if current!=self.plan:raise ValueError('控制值已變，重新預覽')
            if QMessageBox.question(self,'當次作用範圍',self.details.toPlainText())!=QMessageBox.Yes:return
            apply_candidate(self.window,self.plan,True);self.plan=None;self.status.setText('僅當次候選已改並重驗；未改模板及其他候選')
        except Exception as e:self.status.setText('未套用：'+str(e))

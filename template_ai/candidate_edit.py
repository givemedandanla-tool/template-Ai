"""Edit one transient candidate instance through the existing geometry proposal engine."""
import copy,json
from PySide6.QtCore import Qt,Slot,QTimer
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QListWidget,QListWidgetItem,QDoubleSpinBox,QPushButton,QPlainTextEdit,QLabel,QMessageBox,QComboBox,QSplitter
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


def plan_recheck(window,index):
    if not 0<=index<len(window.candidates):raise ValueError('候選不存在')
    c=window.candidates[index]
    return dict(index=index,generation=window.generation,manual_revision=c.risk_context.get('manual_revision',0),before_digest=digest(c.template.to_dict()),template_id=c.template.id,size=[c.template.width_mm,c.template.height_mm],request=dict(operation='RECHECK'),after=c.template.to_dict(),changes=[],warnings=['保留人工框位，以目前輸入與來源重新核實整張作品'],scope='ONLY_THIS_CANDIDATE_SIZE',unaffected_candidates=len(window.candidates)-1)


def plan_original(window,index):
    """Explicitly compare original geometry; never silently reset human edits."""
    from .candidate_changes import manual_delta
    plan=plan_recheck(window,index);candidate=window.candidates[index]
    base=candidate.risk_context.get('manual_base_template')
    if base is None:raise ValueError('沒有可核對的編輯前框位；不能推測原始版本')
    receipt=manual_delta(candidate.template.to_dict(),base)
    plan.update(request=dict(operation='ORIGINAL_GEOMETRY'),after=copy.deepcopy(base),changes=receipt['changes'],warnings=['此建議會回到本次人工編輯前框位；須逐項比較，不會自動移動姓名、公司或Logo'])
    return plan


def manual_metadata(envelope):
    from .candidate_changes import manual_delta
    from .training_store import digest as pin_digest
    before=envelope['before'];plan=envelope['plan'];operation=plan['request']['operation'];history=copy.deepcopy(before.risk_context.get('manual_history',[]))
    if operation=='UNDO':
        for row in history:
            if row['id']==plan['request']['receipt_id']:row['undone']=True;row['digest']=pin_digest({k:v for k,v in row.items() if k!='digest'})
    elif operation!='RECHECK':history.append(manual_delta(before.template.to_dict(),envelope['after']))
    result=dict(conditions=[copy.deepcopy(row) for row in before.risk_context.get('conditions',[]) if row['id']!='MANUAL_RECHECK_PENDING'],manual_history=history[-20:],manual_revision=plan['manual_revision']+(operation!='RECHECK'),manual_base_template=copy.deepcopy(before.risk_context.get('manual_base_template',before.template.to_dict())))
    if operation!='RECHECK':result['manual_edit_receipt']=copy.deepcopy(plan)
    elif before.risk_context.get('manual_edit_receipt'):result['manual_edit_receipt']=copy.deepcopy(before.risk_context['manual_edit_receipt'])
    return result


def dependency_token(window,template,logos):
    from .candidate_risk import engine_digest
    from .layout import layout_dependency
    try:source=window.library.object_snapshot('TEMPLATE',template.id)['payload']
    except ValueError:source=None
    try:link=window.library.source(template.source_id) if template.source_id else None
    except ValueError:link=None
    return digest(dict(engine=engine_digest(),assets=layout_dependency(template,logos),source=source,link=link))


def prepare_edit(window,plan):
    fresh=plan_undo(window,plan['index']) if plan['request']['operation']=='UNDO' else plan_recheck(window,plan['index']) if plan['request']['operation']=='RECHECK' else plan_original(window,plan['index']) if plan['request']['operation']=='ORIGINAL_GEOMETRY' else plan_operation(window,plan['index'],plan['request'])
    if fresh!=plan:raise ValueError('候選／人工版本或輸入已改變，重新預覽')
    c=copy.deepcopy(window.candidates[plan['index']]);local=c.template.to_dict();local['state']='draft'
    after=copy.deepcopy(plan['after']) if plan['request']['operation'] in ('UNDO','RECHECK','ORIGINAL_GEOMETRY') else propose(local,'TEMPLATE',plan['request'])['after'];after['state']=c.template.state
    if not c.risk_context.get('source_template_pin'):
        from .training_store import digest as pin_digest
        try:base=window.library.object_snapshot('TEMPLATE',c.template.id)['payload']
        except ValueError:base=None
        if base and base['state']=='published' and pin_digest(base)==pin_digest(c.template.to_dict()):c.risk_context['source_template_pin']=dict(id=base['id'],version=base['version'],digest=pin_digest(base))
    inputs=copy.deepcopy(window.input_data())
    envelope=dict(plan=copy.deepcopy(plan),before=c,after=after,people=inputs[0],companies=inputs[1],logos=inputs[2],input_digest=digest(inputs),root=str(window.library.root));envelope['manual_metadata']=manual_metadata(envelope);envelope['dependency_token']=dependency_token(window,Template.from_dict(after),inputs[2]);return envelope


def calculate_edit(envelope,library):
    from .candidate_changes import manual_delta
    from .candidate_risk import bind_source,verify_original_source
    from .training_store import digest as pin_digest
    plan=envelope['plan'];before=envelope['before'];t=Template.from_dict(copy.deepcopy(envelope['after']));result=generate(t,envelope['people'],envelope['companies'],envelope['logos'],plan['generation'])
    for key in ('source_template_pin','original_source_proof','approved_base'):
        if key in before.risk_context:result.risk_context[key]=copy.deepcopy(before.risk_context[key])
    result.risk_context.update(copy.deepcopy(envelope['manual_metadata']))
    try:verify_original_source(result,library)
    except (ValueError,OSError):pass
    bind_source(result,library,require_registered=True)
    from .candidate_changes import affected
    old=before.risk_context.get('input_snapshot',{});nodes=[('SLOT',row.get('object_id',row.get('id'))) for row in plan['changes']]
    for slot in t.slots:
        if slot.kind=='logo' and old.get('logos',{}).get(slot.owner)!=envelope['logos'].get(slot.owner):nodes.append(('LOGO',slot.owner,(t.width_mm,t.height_mm)))
    if any(row['status']!='PASS' for row in before.risk['conditions'] if row['id']=='SNAPSHOT_FRESHNESS'):nodes.extend(('SLOT',slot.id) for slot in t.slots)
    result.risk_context['recompute_impact']=affected(t,old.get('people',[]),old.get('companies',[]),envelope['people'],envelope['companies'],nodes)
    result.risk_context['edit_state']='MANUAL_INPUT_CONFLICT' if not result.valid and result.risk_context.get('manual_edit_receipt') else 'RECHECKED'
    result.reasons.append('僅當次候選的明確屬性變動，已以目前輸入重新檢查整張作品；未改模板、客戶或其他候選')
    return result


def install_edit(window,envelope,result):
    plan=envelope['plan'];index=plan['index']
    if window.generation!=plan['generation'] or digest(window.input_data())!=envelope['input_digest']:raise ValueError('較新的輸入已存在，過期結果已忽略')
    if dependency_token(window,result.template,envelope['logos'])!=envelope['dependency_token']:raise ValueError('來源／字型／Logo／規則版本已更新，過期結果已忽略')
    if not 0<=index<len(window.candidates):raise ValueError('候選清單已改變，過期結果已忽略')
    current=window.candidates[index]
    if current.template.id!=plan['template_id'] or digest(current.template.to_dict())!=plan['before_digest'] or current.risk_context.get('manual_revision',0)!=plan['manual_revision']:raise ValueError('目前已有較新的人工修改，過期結果已忽略')
    window.candidates[index]=result;window.choose_candidate(index);return result


def apply_candidate(window,plan,approved=False):
    if approved is not True:raise ValueError('需明確確認此候選尺寸差異')
    envelope=prepare_edit(window,plan);return install_edit(window,envelope,calculate_edit(envelope,window.library))


class CandidateEditDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.index=window.candidate_list.currentRow();self.plan=None;self.compared=None
        self.setWindowTitle('當次候選／人工框位與差異');layout=QVBoxLayout(self)
        self.status=QLabel('只修改目前候選尺寸。人工位置保留；未完成整張重驗時禁止正式輸出。');self.status.setWordWrap(True);layout.addWidget(self.status)
        from .gui import Canvas
        views=QSplitter();self.current_canvas=Canvas();self.proposal_canvas=Canvas()
        for title,canvas in (('目前人工版面（待驗證時保留風險）',self.current_canvas),('新建議比較（非正式，不會自動套用）',self.proposal_canvas)):
            canvas.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);canvas.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            pane=QDialog();box=QVBoxLayout(pane);box.addWidget(QLabel(title));box.addWidget(canvas);views.addWidget(pane)
        layout.addWidget(views,2);self.current_canvas.selected.connect(self.canvas_selected)
        self.objects=QListWidget();self.objects.setSelectionMode(QListWidget.ExtendedSelection);layout.addWidget(self.objects)
        if 0<=self.index<len(window.candidates):
            for obj in window.candidates[self.index].template.slots:
                item=QListWidgetItem(obj.owner+'／'+obj.kind+'／'+obj.id);item.setData(Qt.UserRole,obj.id);self.objects.addItem(item)
            self.show_canvas(self.current_canvas,window.candidates[self.index])
        self.objects.itemSelectionChanged.connect(self.object_selected)
        bar=QHBoxLayout();self.operation=QComboBox();self.operation.addItems(['移動','框位尺寸','鎖定','解除鎖定']);bar.addWidget(self.operation)
        self.dx=QDoubleSpinBox();self.dy=QDoubleSpinBox();self.width=QDoubleSpinBox();self.height=QDoubleSpinBox()
        for title,spin in (('水平位移',self.dx),('垂直位移',self.dy),('框寬',self.width),('框高',self.height)):
            spin.setRange(-2000 if spin in (self.dx,self.dy) else .001,2000);spin.setDecimals(4);spin.setSuffix(' mm');bar.addWidget(QLabel(title));bar.addWidget(spin)
        layout.addLayout(bar);bar=QHBoxLayout()
        actions=[('預覽差異',self.preview,'preview_button'),('確認人工修改',self.apply,'apply_button'),('預覽復原單筆',self.preview_undo,'undo_button'),('比較編輯前框位',self.preview_original,'original_button')]
        for title,callback,name in actions:
            button=QPushButton(title);button.clicked.connect(callback);setattr(self,name,button);bar.addWidget(button)
        layout.addLayout(bar);bar=QHBoxLayout()
        actions=[('以完整Gate檢查建議',self.compare,'compare_button'),('採用已通過Gate的建議',self.adopt,'adopt_button'),('保留人工位置',self.keep_manual,'keep_button'),('取消本次建議／重驗',self.cancel_recheck,'cancel_button')]
        for title,callback,name in actions:
            button=QPushButton(title);button.clicked.connect(callback);setattr(self,name,button);bar.addWidget(button)
        self.adopt_button.setEnabled(False);layout.addLayout(bar);self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details);self.resize(1180,850)
        from .candidate_edit_dispatch import dispatcher
        manager=dispatcher(window);manager.completed.connect(self.edit_completed);manager.failed.connect(self.edit_failed);manager.preview_ready.connect(self.comparison_ready)
    def resizeEvent(self,event):
        super().resizeEvent(event);QTimer.singleShot(0,self.fit_views)
    def fit_views(self):
        self.current_canvas.fit();self.proposal_canvas.fit()
        if self.current_canvas.scene().items() and self.proposal_canvas.scene().items():
            common=min(self.current_canvas.transform().m11(),self.proposal_canvas.transform().m11())
            for canvas in (self.current_canvas,self.proposal_canvas):canvas.scale(common/canvas.transform().m11(),common/canvas.transform().m11())
    def show_canvas(self,canvas,candidate):
        from .gui import Box
        from PySide6.QtWidgets import QGraphicsItem
        from .render import render_image
        try:
            image=render_image(candidate,dpi=100,preview=True)
            # The canvas shows the card at its physical coordinate system.
            # Risk notes already have visible UI text; the export footer must
            # never be squeezed into card height and misalign the object overlay.
            image=image.copy(0,0,image.width(),max(1,round(candidate.template.height_mm*100/25.4)))
        except (ValueError,OSError):image=None
        canvas.set_content(candidate.template.width_mm,candidate.template.height_mm,image,candidate.template.slots)
        for item in canvas.scene().items():
            if isinstance(item,Box):item.setFlag(QGraphicsItem.ItemIsSelectable,True);item.setFlag(QGraphicsItem.ItemIsMovable,False)
        self.fit_views()
    def canvas_selected(self,slot):
        if slot is None:return
        self.objects.blockSignals(True)
        try:
            for i in range(self.objects.count()):self.objects.item(i).setSelected(self.objects.item(i).data(Qt.UserRole)==slot.id)
        finally:self.objects.blockSignals(False)
        self.width.setValue(slot.rect.w);self.height.setValue(slot.rect.h)
    def object_selected(self):
        selected=self.objects.selectedItems()
        if not selected:return
        identity=selected[0].data(Qt.UserRole);self.current_canvas.blockSignals(True)
        try:self.current_canvas.select_id(identity)
        finally:self.current_canvas.blockSignals(False)
        slot=next(s for s in self.window.candidates[self.index].template.slots if s.id==identity);self.width.setValue(slot.rect.w);self.height.setValue(slot.rect.h)
    def current_plan(self):
        ids=[i.data(Qt.UserRole) for i in self.objects.selectedItems()];operation=self.operation.currentIndex()
        if operation==0:return plan_candidate(self.window,self.index,ids,self.dx.value(),self.dy.value())
        request=dict(ids=ids,cross_owner=False)
        if operation==1:request.update(operation='PATCH',patch=dict(w=self.width.value(),h=self.height.value()))
        else:request.update(operation='LOCK',locked=operation==2)
        return plan_operation(self.window,self.index,request)
    def show_plan(self,plan):
        from .candidate_changes import manual_delta
        from .candidate_edit_dispatch import provisional
        envelope=prepare_edit(self.window,plan);delta=manual_delta(envelope['before'].template.to_dict(),envelope['after']);slots={s.id:s for s in envelope['before'].template.slots};lines=['只影響此候選尺寸；其他候選不變。以下是實際屬性差異：']
        for row in delta['changes']:
            obj=slots[row['object_id']];core='【核心元素】' if obj.kind in ('name','company','logo') else ''
            lines.append(core+obj.owner+'／'+obj.kind+'／'+obj.id+'：'+row['property']+' '+str(row['before'])+' → '+str(row['after']))
        lines.extend(['未列出的物件不會因這次操作相對位移。','固定字級、字型與人物／公司歸屬不會被這個入口改寫。','尚未通過整張Gate；衝突不能用保留／忽略動作放行正式輸出。']+plan['warnings']);self.details.setPlainText('\n'.join(lines));self.show_canvas(self.proposal_canvas,provisional(envelope));self.plan=plan;self.compared=None;self.adopt_button.setEnabled(False)
    @Slot(int,object)
    def edit_completed(self,index,candidate):
        if index!=self.index:return
        self.status.setText('整張重驗完成：'+candidate.risk['label']);self.show_canvas(self.current_canvas,candidate)
        impact=candidate.risk_context.get('recompute_impact',{});self.details.appendPlainText('\n重驗涉及物件：'+', '.join(impact.get('affected_slot_ids',[]))+'\n整張不變條件：仍已重新驗證；局部依賴不能取代輸出Gate。')
    @Slot(int,str)
    def edit_failed(self,index,message):
        if index==self.index:self.status.setText('人工版面保留：'+message)
    @Slot(int,object,object)
    def comparison_ready(self,index,envelope,candidate):
        if index!=self.index:return
        self.compared=(envelope,candidate);self.show_canvas(self.proposal_canvas,candidate);gate=candidate.risk_context.get('comparison_gate',{});self.adopt_button.setEnabled(bool(gate.get('formal_allowed')));self.status.setText('非正式比較／數位檢查：'+gate.get('label','待驗證')+'；目前人工版面尚未更動。');self.details.appendPlainText('\n比較檢查：'+'；'.join(candidate.issues or ['完整Gate通過，仍需明確採用']))
    def preview(self):
        try:self.show_plan(self.current_plan());self.status.setText('差異待確認；尚未套用或放行正式輸出')
        except Exception as error:self.plan=None;self.status.setText('未預覽：'+str(error))
    def preview_undo(self):
        try:self.show_plan(plan_undo(self.window,self.index));self.status.setText('僅復原最後一筆變動；套用後須整張重驗')
        except ValueError as error:self.plan=None;self.status.setText('未預覽復原：'+str(error))
    def preview_original(self):
        try:self.show_plan(plan_original(self.window,self.index));self.status.setText('編輯前框位僅供比較；不會自動覆寫人工位置')
        except ValueError as error:self.plan=None;self.status.setText('未建立比較：'+str(error))
    def compare(self):
        try:
            if self.plan is None:raise ValueError('先預覽實際差異')
            from .candidate_edit_dispatch import dispatcher
            dispatcher(self.window).preview(self.plan);self.status.setText('建議排隊重驗中；人工版面保留，結果只供非正式比較')
        except Exception as error:self.status.setText('未比較：'+str(error))
    def adopt(self):
        try:
            if self.compared is None:raise ValueError('先完成建議的完整Gate')
            if QMessageBox.question(self,'確認採用逐項差異',self.details.toPlainText())!=QMessageBox.Yes:return
            from .candidate_edit_dispatch import dispatcher
            dispatcher(self.window).adopt_preview(*self.compared);self.compared=None;self.plan=None;self.adopt_button.setEnabled(False)
        except Exception as error:self.status.setText('未採用：'+str(error))
    def keep_manual(self):
        self.cancel_recheck();self.status.setText('保留人工位置與目前風險；此動作不會消除衝突或放行輸出')
    def cancel_recheck(self):
        from .candidate_edit_dispatch import dispatcher
        if self.compared:self.compared[0]['cancel'].set()
        dispatcher(self.window).cancel(self.index);self.compared=None;self.plan=None;self.adopt_button.setEnabled(False)
    def apply(self):
        try:
            if not self.plan:raise ValueError('先預覽')
            operation=self.plan['request']['operation'];current=plan_undo(self.window,self.index) if operation=='UNDO' else plan_original(self.window,self.index) if operation=='ORIGINAL_GEOMETRY' else self.current_plan()
            if current!=self.plan:raise ValueError('控制值已變，重新預覽')
            if QMessageBox.question(self,'當次作用範圍',self.details.toPlainText())!=QMessageBox.Yes:return
            from .candidate_edit_dispatch import dispatcher
            pending=dispatcher(self.window).submit(self.plan);self.show_canvas(self.current_canvas,pending);self.plan=None;self.status.setText('人工版面已保留，等待整張重驗；未通過前禁止正式輸出')
        except Exception as error:self.status.setText('未套用：'+str(error))

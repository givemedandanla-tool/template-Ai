"""View policy and explicit pending-property ownership for existing GUI controls."""
import json,sqlite3
from dataclasses import asdict
from PySide6.QtCore import QSignalBlocker,Qt,QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QMessageBox,QDoubleSpinBox,QComboBox,QLineEdit
from shiboken6 import isValid
from .customers import digest


def property_values(window):
    family=window.font.currentFont().family();display=getattr(window,'_selected_font_display',None);slot=window.current_slot
    if slot and display and display['slot_id']==slot.id and family==display['display']:family=slot.font
    return dict(coords=[s.value() for s in window.coords],kind=window.kind.currentData(),owner=window.owner.currentData(),
                index=window.index.value(),font=family,pt=window.pt.value(),color=window.text_color.text().strip(),
                scale=window.scale.value(),align=window.align.currentData(),required=window.required.isChecked(),incomplete=dict(getattr(window,'_property_raw_inputs',{})))


def pending_main(window,mode=None):
    baseline=getattr(window,'_property_form_baseline',None)
    mode=window.tabs.currentIndex() if mode is None else mode
    return bool(window.current_slot and baseline is not None and window._property_mode==mode and property_values(window)!=baseline)


def numeric_controls(window):return dict(zip(('x','y','w','h'),window.coords),pt=window.pt,scale=window.scale,index=window.index)


def capture_incomplete(window,key):
    if window.current_slot is None:return
    control=numeric_controls(window)[key]
    if control.hasAcceptableInput():window._property_raw_inputs.pop(key,None)
    else:window._property_raw_inputs[key]=control.lineEdit().text()[:80]


def restore_incomplete(window):
    for key,text in window._property_raw_inputs.items():
        if key in numeric_controls(window):numeric_controls(window)[key].lineEdit().setText(text)


def source_pin(window,mode):
    if mode==0 and window.work:return [str(window.library.root),'ARTWORK',window.work['id'],window.work['revision']]
    if mode==1 and window.template:return [str(window.library.root),'TEMPLATE',window.template.id,window.template_revision,window.template_base_hash]
    return None


def discard_pending_selection(parent,action='切換'):
    box=QMessageBox(parent);box.setWindowTitle('目前物件有待套用輸入')
    box.setText('目前輸入尚未套用至原物件。切換選取不會把這些值套用至另一個物件。')
    stay=box.addButton('返回目前物件繼續編輯',QMessageBox.RejectRole)
    discard=box.addButton('放棄未套用輸入並'+action,QMessageBox.DestructiveRole)
    box.setDefaultButton(stay);box.exec();return box.clickedButton()==discard


def restore_main_selection(window):
    slot=window.current_slot
    if slot is None:return
    if window.tabs.currentIndex()==0:
        with QSignalBlocker(window.train_canvas):window.train_canvas.select_id(slot.id)
    elif window.tabs.currentIndex()==1:
        with QSignalBlocker(window.edit_canvas):window.edit_canvas.select_ids([slot.id])
        with QSignalBlocker(window.editor_tree):
            for item in getattr(window,'editor_tree_nodes',[]):item.setSelected(item.data(0,Qt.UserRole)==[slot.id])
    restore_incomplete(window)


def retain_pending_main(window):
    """A bounded diagnostic of layout controls, never customer text or a draft DB."""
    slot=window.current_slot
    window.pending_property_conflict=dict(slot_id=slot.id,mode=window.tabs.currentIndex(),root=str(window.library.root),values=property_values(window))
    window.statusBar().showMessage('原物件已變更；未套用屬性保留供核對，未套至新物件。')


TOOL_GROUPS={'text','geometry','identity'}


def load_tool_pins(library):
    row=library.db.execute("SELECT value FROM preferences WHERE key='property_tool_pins'").fetchone()
    try:
        value=json.loads(row[0]) if row else []
        if not isinstance(value,list) or any(not isinstance(x,str) or x not in TOOL_GROUPS for x in value):raise ValueError('工具偏好不合法')
        return set(value)
    except (ValueError,TypeError):return set()


def save_tool_pins(library,pins):
    if not set(pins)<=TOOL_GROUPS:raise ValueError('未知工具群組')
    with library.db:library.db.execute("INSERT INTO preferences VALUES('property_tool_pins',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps(sorted(pins)),))


class RightPropertyContext:
    """Arrange the original widgets; canonical objects and existing gates stay authoritative."""
    def __init__(self,window):
        self.w=window;self.loading=True;self.pins=load_tool_pins(window.library)
        self.timer=QTimer(window);self.timer.setSingleShot(True);self.timer.timeout.connect(self.sync)
        for key,check in window.property_pin_checks.items():
            check.setChecked(key in self.pins);check.toggled.connect(lambda checked,k=key:self.pin(k,checked))
        window.all_property_tools.toggled.connect(self.expand_all)
        self.controls=dict(geometry=window.coords,text=[window.font,window.pt,window.text_color,window.scale,window.align,window.property_policy_button],identity=[window.kind,window.owner,window.index,window.required])
        for controls in self.controls.values():
            for control in controls:
                from .viewport_controls import guard_control_wheel
                guard_control_wheel(control)
                for name in ('currentFontChanged','valueChanged','textChanged','currentIndexChanged','stateChanged'):
                    signal=getattr(control,name,None)
                    if signal is not None:signal.connect(self.schedule);break
        for key,control in numeric_controls(window).items():
            control.lineEdit().textEdited.connect(lambda text,k=key:self.numeric_edited(k))
        window.property_conflict.clicked.connect(self.inspect_conflict);window.property_problem.clicked.disconnect();window.property_problem.clicked.connect(self.fix_local_problem)
        window.tabs.currentChanged.connect(self.schedule);window.inputs_invalidated.connect(self.schedule)
        window.candidate_list.currentRowChanged.connect(self.schedule);window.output_canvas.scene().selectionChanged.connect(self.schedule)
        window.result_problem_items.currentRowChanged.connect(self.schedule)
        self.loading=False;self.sync()

    def schedule(self,*args):
        if not self.loading and isValid(self.w) and isValid(self.timer) and not self.w.library.closed:self.timer.start(0)

    def numeric_edited(self,key):
        if not self.loading:capture_incomplete(self.w,key);self.schedule()

    def pin(self,key,checked):
        self.pins.add(key) if checked else self.pins.discard(key)
        try:save_tool_pins(self.w.library,self.pins)
        except (ValueError,OSError,sqlite3.Error):self.w.property_edit_state.setText('工具偏好保存失敗；本次可見性保留，工作資料未更動。')
        self.sync()

    def expand_all(self,checked):
        if checked:
            for group in self.w.property_groups.values():group.setChecked(True)
        self.sync()

    def selected(self):
        w=self.w;mode=w.tabs.currentIndex();fresh=True;size=None;version=None
        if mode==2:
            index=w.candidate_list.currentRow()
            if not 0<=index<len(w.candidates):return [],None,True,True,None,None,None
            c=w.candidates[index];payload=c.template.to_dict();size=(c.template.width_mm,c.template.height_mm);version=c.template.version
            from .candidate_results import current_assessment
            assessment=current_assessment(w,index);fresh=not any(row['id']=='CURRENT_RESULT_CONTEXT' and row['status']!='PASS' for row in assessment['conditions'])
            ids={item.slot.id for item in w.output_canvas.scene().selectedItems() if hasattr(item,'slot')}
            return [row for row in payload['slots'] if row['id'] in ids],payload,True,fresh,size,version,assessment
        if mode==1:
            if w.template is None:return [],None,True,True,None,None,None
            payload=w.template.to_dict();size=(w.template.width_mm,w.template.height_mm);version=w.template.version;readonly=w.template.state!='draft' or w.template_stack.currentIndex()==0
            snapshot=w.library.object_snapshot('TEMPLATE',w.template.id)
            from .font_review import fingerprint
            fresh=snapshot['revision']==w.template_revision and fingerprint(snapshot['payload'])==w.template_base_hash
            ids=set(w.edit_canvas.selection_intent)
        else:
            if not w.work:return [],None,True,True,None,None,None
            payload=dict(w.work['payload'],slots=[asdict(s) for s in w.slots]);size=(payload['work_width'],payload['work_height']);version=w.work['revision'];readonly=w.source is None
            snapshot=w.library.object_snapshot('ARTWORK',w.work['id']);fresh=snapshot['revision']==w.work['revision'] and snapshot['payload']==w.work['payload']
            ids={item.slot.id for item in w.train_canvas.scene().selectedItems() if hasattr(item,'slot')}
        if len(ids)<=1 and w.current_slot and w.current_slot.id in {row['id'] for row in payload['slots']}:ids={w.current_slot.id}
        return [row for row in payload['slots'] if row['id'] in ids],payload,readonly,fresh,size,version,None

    def fill_readonly(self,rows,payload):
        w=self.w
        if not rows:
            for control in w.coords+[w.pt,w.scale,w.index]:control.clear()
            for control in (w.kind,w.owner,w.align,w.font):control.setCurrentIndex(-1)
            w.text_color.clear();return
        from .object_tools import common_properties
        common=common_properties(payload,[row['id'] for row in rows]);controls=dict(zip(('x','y','w','h'),w.coords));controls.update(size_pt=w.pt,min_scale=w.scale,index=w.index)
        for key,control in controls.items():
            value=common[key]['value']
            if value is None:control.clear()
            else:control.setValue(value*100 if key=='min_scale' else value+1 if key=='index' else value)
        for key,control in [('kind',w.kind),('owner',w.owner),('align',w.align)]:control.setCurrentIndex(control.findData(common[key]['value']) if not common[key]['mixed'] else -1)
        w.text_color.setText(common['color']['value'] or '')
        if common['font']['value']:w.font.setCurrentFont(QFont(common['font']['value']))
        else:w.font.setCurrentIndex(-1)

    def sync(self,*args):
        if not isValid(self.w):return
        if self.loading:return
        w=self.w
        if w.library.closed:return
        self.loading=True
        try:
            try:rows,payload,readonly,fresh,size,version,assessment=self.selected()
            except (ValueError,OSError,KeyError,sqlite3.Error):rows,payload,readonly,fresh,size,version,assessment=[],None,True,False,None,None,None
            count=len(rows);text=bool(rows) and all(row['kind']!='logo' for row in rows);logo=count==1 and rows[0]['kind']=='logo'
            if fresh and count==1 and w.tabs.currentIndex()!=2 and w.current_slot:
                canonical=next((slot for slot in w.current_slots() if slot.id==rows[0]['id']),None)
                if canonical is not None and (digest(asdict(canonical))!=getattr(w,'_property_loaded_pin',None) or source_pin(w,w.tabs.currentIndex())!=getattr(w,'_property_loaded_source',None) or w.current_slot is not canonical):w.select_slot(canonical)
            if not fresh and w.current_slot and w.tabs.currentIndex()!=2:
                if pending_main(w):retain_pending_main(w)
                w.current_slot=None;w._property_form_baseline=None
            if not rows or not fresh or count>1 or w.tabs.currentIndex()==2:self.fill_readonly(rows if fresh else [],payload)
            locked=any(row.get('locked',False) for row in rows);editable=count==1 and fresh and not readonly and not locked
            title='選取已失效／需重新核對' if not fresh else '尚未選取物件' if not rows else '多選；混合值依各欄判斷' if count>1 else '完整公司 Logo；文字工具不適用' if logo else '文字物件；固定字級不自動縮小'
            suffix=(f' ｜ {size[0]:g}×{size[1]:g} mm ｜ 版本 {version}' if size else '')
            if locked:title+=' ｜ 包含鎖定物件'
            w.property_context_label.setText(title+suffix)
            if assessment:
                w.property_context_label.setText(w.property_context_label.text()+'\n'+assessment['label']+'；輸出前仍須核對目前作品。')
            if logo:
                if w.tabs.currentIndex()!=2:detail='公司欄位 '+rows[0]['owner']+'；尺寸專用資產尚未核實，完整框不等於素材已核准。'
                else:
                    candidate=w.candidates[w.candidate_list.currentRow()];placed=next((item for item in candidate.items if item.slot.id==rows[0]['id']),None);asset=placed.logo if placed else None
                    detail=('本次放置 '+str(asset.get('company','公司身分待核對'))+'／版本 '+str(asset.get('version','待核對'))+'；尺寸與身分仍依整張檢查。') if asset else '本次缺已核對尺寸專用 Logo；不可由框位推定素材合格。'
                w.property_context_label.setText(w.property_context_label.text()+'\n'+detail)
            self.problem_row=None
            if w.tabs.currentIndex()==2 and fresh:
                selected_ids={row['id'] for row in rows};items=[w.result_problem_items.item(i) for i in range(w.result_problem_items.count())]
                if selected_ids:self.problem_row=next((item.data(Qt.UserRole) for item in items if selected_ids.intersection(item.data(Qt.UserRole).get('slot_ids',[]))),None)
                elif w.result_problem_items.currentItem():self.problem_row=w.result_problem_items.currentItem().data(Qt.UserRole)
                if self.problem_row:w.property_context_label.setText(w.property_context_label.text()+'\n'+('物件問題：' if self.problem_row.get('slot_ids') else '作品問題：')+self.problem_row['reason'])
            if w.tabs.currentIndex()==2:
                w.selected_info.setVisible(True)
                if not fresh:w.selected_info.setText('來源已過期；未顯示舊物件文字，請重新驗證並選取。')
                elif not rows:w.selected_info.setText('未選取物件；請由目前作品定位，沒有預設任何人物欄位。')
                else:
                    candidate=w.candidates[w.candidate_list.currentRow()];placed={item.slot.id:item for item in candidate.items}
                    details=[]
                    for row in rows[:8]:
                        item=placed.get(row['id']);value=str(item.text) if item is not None and row['kind']!='logo' else None
                        content=('本次文字：'+value[:256]+('…（節錄）' if len(value)>256 else '')) if value is not None else '文字內容未核實／Logo不拆分圖文'
                        details.append(row['id']+'／'+row['owner']+'／'+row['kind']+'\n'+content)
                    if len(rows)>8:details.append('其餘 '+str(len(rows)-8)+' 件請由既有共同屬性工具逐項核對。')
                    w.selected_info.setText('目前確切選取（唯讀；修改沿用既有流程）\n'+'\n'.join(details))
            w.property_fields.setVisible(bool(rows) or bool(self.pins) or w.all_property_tools.isChecked());w.property_pinned_box.setVisible(bool(self.pins))
            order=['text','geometry','identity'] if text else ['geometry','identity','text']
            positions=dict(pinned=0,context=0)
            for key in order:
                group=w.property_groups[key];area='pinned' if key in self.pins else 'context';target=w.property_pinned_layout if key in self.pins else w.property_context_layout
                if target.indexOf(group)!=positions[area]:
                    w.property_pinned_layout.removeWidget(group);w.property_context_layout.removeWidget(group);target.insertWidget(positions[area],group)
                positions[area]+=1
                group.setVisible(key in self.pins or w.all_property_tools.isChecked() or (bool(rows) and (key!='text' or text)))
                group.setTitle({'text':'文字工具'+('（不適用／唯讀）' if not text else ''),'geometry':'框位與完整比例','identity':'類型與人物／公司歸屬'}[key])
                for control in self.controls[key]:control.setEnabled(editable and (key!='text' or text))
            w.property_button.setEnabled(editable and not w._property_raw_inputs and all(control.hasAcceptableInput() for control in numeric_controls(w).values()));w.property_object_tools.setEnabled(bool(rows) and fresh and w.tabs.currentIndex()!=2)
            w.property_candidate_edit.setVisible(w.tabs.currentIndex()==2);w.property_candidate_edit.setEnabled(fresh and bool(w.candidates))
            w.property_problem.setVisible(w.tabs.currentIndex()==2);w.property_problem.setEnabled(fresh and self.problem_row is not None)
            w.property_conflict.setVisible(w.pending_property_conflict is not None)
            if pending_main(w):state='輸入中／待套用：仍屬目前物件，切選不會自動轉移。'
            elif not fresh:state='需重新驗證／重新選取；舊控制不可套用。'
            elif not rows:state='尚未選取物件；可新增標記或由目前畫布選取，未啟用修改。'
            elif count>1:state='共同值／混合值僅供核對；修改請用既有共同屬性工具。'
            elif readonly or locked:state='唯讀；鎖定或已發布資料須走既有受控修改流程。'
            else:state='顯示目前值；尚無待套用修改。正式保存與輸出另行核對。'
            w.property_edit_state.setText(state)
        finally:self.loading=False

    def fix_local_problem(self):
        row=getattr(self,'problem_row',None)
        if row is None:return
        from .candidate_results import fix_problem
        try:fix_problem(self.w,row)
        except ValueError as error:self.w.property_edit_state.setText('問題引用已更新，請重新定位：'+str(error))

    def inspect_conflict(self):
        value=self.w.pending_property_conflict
        if value is None:return
        box=QMessageBox(self.w);box.setWindowTitle('保留的未套用屬性（唯讀）');box.setText('原物件版本已變，這些輸入未套至任何新物件。請先重新核對原工作。')
        box.setDetailedText(json.dumps(value['values'],ensure_ascii=False,indent=2));box.addButton('保留供核對',QMessageBox.RejectRole);discard=box.addButton('明確放棄這份未套用輸入',QMessageBox.DestructiveRole);box.exec()
        if box.clickedButton()==discard:self.w.pending_property_conflict=None;self.sync()

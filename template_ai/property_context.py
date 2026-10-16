"""View policy and explicit pending-property ownership for existing GUI controls."""
import json,sqlite3
from dataclasses import asdict
from PySide6.QtCore import QSignalBlocker,Qt,QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QMessageBox,QDoubleSpinBox,QComboBox,QLineEdit
from .customers import digest


def property_values(window):
    family=window.font.currentFont().family();display=getattr(window,'_selected_font_display',None);slot=window.current_slot
    if slot and display and display['slot_id']==slot.id and family==display['display']:family=slot.font
    return dict(coords=[s.value() for s in window.coords],kind=window.kind.currentData(),owner=window.owner.currentData(),
                index=window.index.value(),font=family,pt=window.pt.value(),color=window.text_color.text().strip(),
                scale=window.scale.value(),align=window.align.currentData(),required=window.required.isChecked())


def pending_main(window):
    baseline=getattr(window,'_property_form_baseline',None)
    return bool(window.current_slot and baseline is not None and window._property_mode==window.tabs.currentIndex() and property_values(window)!=baseline)


def discard_pending_selection(parent):
    box=QMessageBox(parent);box.setWindowTitle('目前物件有待套用輸入')
    box.setText('目前輸入尚未套用至原物件。切換選取不會把這些值套用至另一個物件。')
    stay=box.addButton('返回目前物件繼續編輯',QMessageBox.RejectRole)
    discard=box.addButton('放棄未套用輸入並切換',QMessageBox.DestructiveRole)
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
                for name in ('currentFontChanged','valueChanged','textChanged','currentIndexChanged','stateChanged'):
                    signal=getattr(control,name,None)
                    if signal is not None:signal.connect(self.schedule);break
        window.property_conflict.clicked.connect(self.inspect_conflict)
        window.tabs.currentChanged.connect(self.schedule);window.inputs_invalidated.connect(self.schedule)
        window.candidate_list.currentRowChanged.connect(self.schedule);window.output_canvas.scene().selectionChanged.connect(self.schedule)
        self.loading=False;self.sync()

    def schedule(self,*args):
        if not self.loading:self.timer.start(0)

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
        if self.loading:return
        w=self.w
        if w.library.closed:return
        self.loading=True
        try:
            try:rows,payload,readonly,fresh,size,version,assessment=self.selected()
            except (ValueError,OSError,KeyError,sqlite3.Error):rows,payload,readonly,fresh,size,version,assessment=[],None,True,False,None,None,None
            count=len(rows);text=bool(rows) and all(row['kind']!='logo' for row in rows);logo=count==1 and rows[0]['kind']=='logo'
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
            w.property_fields.setVisible(True);w.property_pinned_box.setVisible(bool(self.pins))
            order=['text','geometry','identity'] if text else ['geometry','identity','text']
            for key in order:
                group=w.property_groups[key];w.property_pinned_layout.removeWidget(group);w.property_context_layout.removeWidget(group)
                (w.property_pinned_layout if key in self.pins else w.property_context_layout).addWidget(group)
                group.setVisible(key in self.pins or w.all_property_tools.isChecked() or (bool(rows) and (key!='text' or text)))
                group.setTitle({'text':'文字工具'+('（不適用／唯讀）' if not text else ''),'geometry':'框位與完整比例','identity':'類型與人物／公司歸屬'}[key])
                for control in self.controls[key]:control.setEnabled(editable and (key!='text' or text))
            w.property_button.setEnabled(editable);w.property_object_tools.setEnabled(bool(rows) and fresh and w.tabs.currentIndex()!=2)
            w.property_candidate_edit.setVisible(w.tabs.currentIndex()==2);w.property_candidate_edit.setEnabled(fresh and bool(w.candidates) and not w.busy)
            w.property_problem.setVisible(w.tabs.currentIndex()==2);w.property_problem.setEnabled(fresh and w.result_problem_items.currentItem() is not None)
            w.property_conflict.setVisible(w.pending_property_conflict is not None)
            if pending_main(w):state='輸入中／待套用：仍屬目前物件，切選不會自動轉移。'
            elif not fresh:state='需重新驗證／重新選取；舊控制不可套用。'
            elif not rows:state='尚未選取物件；可新增標記或由目前畫布選取，未啟用修改。'
            elif count>1:state='共同值／混合值僅供核對；修改請用既有共同屬性工具。'
            elif readonly or locked:state='唯讀；鎖定或已發布資料須走既有受控修改流程。'
            else:state='顯示目前值；尚無待套用修改。正式保存與輸出另行核對。'
            w.property_edit_state.setText(state)
        finally:self.loading=False

    def inspect_conflict(self):
        value=self.w.pending_property_conflict
        if value is None:return
        box=QMessageBox(self.w);box.setWindowTitle('保留的未套用屬性（唯讀）');box.setText('原物件版本已變，這些輸入未套至任何新物件。請先重新核對原工作。')
        box.setDetailedText(json.dumps(value['values'],ensure_ascii=False,indent=2));box.addButton('保留供核對',QMessageBox.RejectRole);discard=box.addButton('明確放棄這份未套用輸入',QMessageBox.DestructiveRole);box.exec()
        if box.clickedButton()==discard:self.w.pending_property_conflict=None;self.sync()

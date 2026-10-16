"""Two-mode advanced object editor: stable selection, dirty patch, previews and durable history."""
import copy
import json
from PySide6.QtCore import Qt,QPointF,QRectF,Signal
from PySide6.QtGui import QColor,QPen,QImage
from PySide6.QtWidgets import (QDialog,QDialogButtonBox,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QListWidget,QListWidgetItem,QFormLayout,QDoubleSpinBox,QComboBox,QCheckBox,QLineEdit,QSplitter,QWidget,QTableWidget,QTableWidgetItem,QMessageBox,QGraphicsItem,QScrollArea,QPlainTextEdit,QTreeWidget,QTreeWidgetItem)
from .gui import Canvas,Box
from .model import Slot,Rect,KINDS,Template
from .object_tools import propose,common_properties,warnings_for
from .font_review import fingerprint


class ObjectCanvas(Canvas):
    selection_ids=Signal(object)
    drag_proposal=Signal(object)
    preview_proposal=Signal(object)
    def __init__(self):
        self.resetting=True;super().__init__();self.allow_multi_drag=True;self.resetting=False;self.base_positions={};self.overlays=[];self.selection_intent=set()
        self.snap_enabled=False;self.guides_enabled=True;self.safety_visible=True;self.safe_margin_mm=0.;self.resize_enabled=True;self.nudge_mm=.1;self.resize_state=None;self.snap_lines=[];self.pan_restore=None
    def selection_changed(self):
        if self.resetting:return
        self.selection_ids.emit(sorted(i.slot.id for i in self.scene().selectedItems() if isinstance(i,Box)))
    def set_content(self,*args,**kw):
        self.resetting=True;self.selection_intent=set()
        self.resize_state=None;self.snap_lines=[]
        self.safe_margin_mm=kw.pop('safe_margin_mm',0.)
        try:
            super().set_content(*args,**kw)
            self.base_positions={i.slot.id:(i.pos().x(),i.pos().y()) for i in self.scene().items() if isinstance(i,Box)}
            self.setSceneRect(QRectF(-2010,-2010,6020,6020))
            self.overlays=[];self.mode='edit';self.setDragMode(Canvas.RubberBandDrag)
            for i in self.scene().items():
                if isinstance(i,Box):i.setFlag(QGraphicsItem.ItemIsSelectable,True);i.setFlag(QGraphicsItem.ItemIsMovable,not self.readonly and not i.slot.locked)
        finally:self.resetting=False
    def fit(self):self.fitInView(QRectF(-5,-5,self.width_mm+10,self.height_mm+10),Qt.KeepAspectRatio);self.view_changed.emit()
    def select_ids(self,ids):
        self.resetting=True;self.selection_intent=set(ids)
        try:
            for i in self.scene().items():
                if isinstance(i,Box):i.setSelected(i.slot.id in ids)
        finally:self.resetting=False
        self.viewport().update()

    def set_mode(self,mode):
        super().set_mode(mode)
        if self.mode=='edit':self.setDragMode(Canvas.RubberBandDrag)

    def selected_boxes(self):return [i for i in self.scene().items() if isinstance(i,Box) and i.slot.id in self.selection_intent]

    def snap(self,dx,dy):
        boxes=self.selected_boxes();self.snap_lines=[]
        if not self.snap_enabled or not boxes:return dx,dy
        original=[(self.base_positions[b.slot.id][0],self.base_positions[b.slot.id][1],b.slot.rect.w,b.slot.rect.h) for b in boxes]
        x=min(r[0] for r in original);y=min(r[1] for r in original);w=max(r[0]+r[2] for r in original)-x;h=max(r[1]+r[3] for r in original)-y
        references=[[0,self.width_mm/2,self.width_mm],[0,self.height_mm/2,self.height_mm]]
        for item in self.scene().items():
            if isinstance(item,Box) and item.slot.id not in self.selection_intent:
                r=item.slot.rect;references[0].extend((r.x,r.x+r.w/2,r.x+r.w));references[1].extend((r.y,r.y+r.h/2,r.y+r.h))
        tolerance=6/max(.0001,self.transform().m11());deltas=[dx,dy]
        for axis,(start,size) in enumerate(((x,w),(y,h))):
            choices=[(abs(ref-(start+deltas[axis]+offset)),ref-(start+deltas[axis]+offset),ref) for ref in references[axis] for offset in (0,size/2,size)]
            distance,adjust,reference=min(choices)
            if distance<=tolerance:deltas[axis]+=adjust;self.snap_lines.append((axis,reference))
        return tuple(deltas)

    def resize_request(self,point):
        box=self.resize_state;r=box.slot.rect;x,y=self.base_positions[box.slot.id];w=max(.01,point.x()-x);h=max(.01,point.y()-y)
        self.snap_lines=[]
        if self.snap_enabled:
            references=[[0,self.width_mm/2,self.width_mm],[0,self.height_mm/2,self.height_mm]]
            for item in self.scene().items():
                if isinstance(item,Box) and item.slot.id!=box.slot.id:
                    q=item.slot.rect;references[0].extend((q.x,q.x+q.w/2,q.x+q.w));references[1].extend((q.y,q.y+q.h/2,q.y+q.h))
            for axis,edge in ((0,x+w),(1,y+h)):
                reference=min(references[axis],key=lambda v:abs(v-edge))
                if abs(reference-edge)<=6/max(.0001,self.transform().m11()):
                    if axis==0:w=max(.01,reference-x)
                    else:h=max(.01,reference-y)
                    self.snap_lines.append((axis,reference))
        if box.slot.kind=='logo':
            scale=max(.001,(w*r.w+h*r.h)/(r.w*r.w+r.h*r.h));w,h=r.w*scale,r.h*scale
            # Aspect-ratio projection can move away from a snapped line. Display
            # only references actually reached by the constrained geometry.
            self.snap_lines=[(axis,value) for axis,value in self.snap_lines if abs((x+w if axis==0 else y+h)-value)<1e-6]
        return dict(operation='PATCH',ids=[box.slot.id],patch=dict(w=w,h=h))

    def mousePressEvent(self,event):
        boxes=self.selected_boxes()
        if self.mode=='edit' and self.resize_enabled and not self.readonly and len(boxes)==1 and not boxes[0].slot.locked and event.button()==Qt.LeftButton:
            box=boxes[0];r=box.slot.rect;point=self.mapToScene(event.position().toPoint());corner=QPointF(box.pos().x()+r.w,box.pos().y()+r.h)
            if (point-corner).manhattanLength()<=9/max(.0001,self.transform().m11()):self.resize_state=box;event.accept();return
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self.resize_state:
            self.preview_proposal.emit(self.resize_request(self.mapToScene(event.position().toPoint())));event.accept();return
        super().mouseMoveEvent(event)
        if event.buttons()&Qt.LeftButton and self.mode=='edit':
            boxes=self.selected_boxes()
            if boxes and not self.readonly and not any(b.slot.locked for b in boxes):
                first=boxes[0];x,y=self.base_positions[first.slot.id];dx,dy=self.snap(first.pos().x()-x,first.pos().y()-y)
                if abs(dx)+abs(dy)>1e-6:
                    for box in boxes:
                        bx,by=self.base_positions[box.slot.id];box.setPos(bx+dx,by+dy)
                    self.preview_proposal.emit(dict(operation='MOVE',ids=sorted(self.selection_intent),dx=dx,dy=dy))
        self.viewport().update()

    def mouseReleaseEvent(self,event):
        if self.resize_state:
            request=self.resize_request(self.mapToScene(event.position().toPoint()));self.resize_state=None;self.drag_proposal.emit(request);event.accept();return
        super().mouseReleaseEvent(event)
        changed=[]
        for i in self.scene().items():
            if isinstance(i,Box) and i.slot.id in self.base_positions:
                x,y=self.base_positions[i.slot.id];dx,dy=i.pos().x()-x,i.pos().y()-y
                if abs(dx)+abs(dy)>1e-6:changed.append((i.slot.id,dx,dy))
                i.setPos(x,y);i.slot.rect.x,i.slot.rect.y=x,y
        if changed:
            ids=sorted(self.selection_intent)
            dx,dy=self.snap(*changed[0][1:])
            self.drag_proposal.emit({'operation':'MOVE','ids':ids,'dx':dx,'dy':dy})

    def keyPressEvent(self,event):
        if event.key()==Qt.Key_Space and not event.isAutoRepeat():
            self.pan_restore=(self.mode,set(self.selection_intent));self.resetting=True;self.set_mode('pan');self.resetting=False;event.accept();return
        directions={Qt.Key_Left:(-1,0),Qt.Key_Right:(1,0),Qt.Key_Up:(0,-1),Qt.Key_Down:(0,1)}
        if event.key() in directions and self.mode=='edit' and self.selection_intent and not self.readonly:
            dx,dy=directions[event.key()];step=self.nudge_mm*(10 if event.modifiers()&Qt.ShiftModifier else 1)
            self.drag_proposal.emit(dict(operation='MOVE',ids=sorted(self.selection_intent),dx=dx*step,dy=dy*step));event.accept();return
        super().keyPressEvent(event)

    def keyReleaseEvent(self,event):
        if event.key()==Qt.Key_Space and self.pan_restore and not event.isAutoRepeat():
            mode,ids=self.pan_restore;self.pan_restore=None;self.resetting=True;self.set_mode(mode);self.resetting=False;self.select_ids(ids);event.accept();return
        super().keyReleaseEvent(event)

    def drawForeground(self,painter,rect):
        super().drawForeground(painter,rect);painter.save()
        if self.safety_visible:
            pen=QPen(QColor('#dc2626'),1,Qt.DashLine);pen.setCosmetic(True);painter.setPen(pen);margin=self.safe_margin_mm;painter.drawRect(QRectF(margin,margin,self.width_mm-2*margin,self.height_mm-2*margin))
        if self.guides_enabled:
            pen=QPen(QColor('#9333ea'),1,Qt.DashLine);pen.setCosmetic(True);painter.setPen(pen)
            painter.drawLine(QPointF(self.width_mm/2,0),QPointF(self.width_mm/2,self.height_mm));painter.drawLine(QPointF(0,self.height_mm/2),QPointF(self.width_mm,self.height_mm/2))
            for axis,value in self.snap_lines:
                if axis==0:painter.drawLine(QPointF(value,0),QPointF(value,self.height_mm))
                else:painter.drawLine(QPointF(0,value),QPointF(self.width_mm,value))
        boxes=self.selected_boxes()
        if self.resize_enabled and self.mode=='edit' and not self.readonly and len(boxes)==1 and not boxes[0].slot.locked:
            box=boxes[0];r=box.slot.rect;size=7/max(.0001,self.transform().m11());painter.setPen(QPen(QColor('#1d4ed8'),0));painter.setBrush(QColor('#ffffff'));painter.drawRect(QRectF(box.pos().x()+r.w-size/2,box.pos().y()+r.h-size/2,size,size))
        painter.restore()
    def clear_preview(self):
        for item in self.overlays:
            if item.scene():self.scene().removeItem(item)
        self.overlays=[]
    def show_preview(self,plan):
        self.clear_preview()
        for c in plan['changes']:
            if not c['after']:continue
            r=c['after']['rect'];pen=QPen(QColor('#16a34a'),2);pen.setCosmetic(True)
            item=self.scene().addRect(QRectF(r['x'],r['y'],r['w'],r['h']),pen);item.setZValue(9);item.setAcceptedMouseButtons(Qt.NoButton);self.overlays.append(item)


def canvas_controls(canvas,library=None):
    if library is not None:
        from .editor_settings import load
        for key,value in load(library).items():setattr(canvas,key,value)
    widget=QWidget();outer=QVBoxLayout(widget);from .viewport_controls import navigation_controls
    outer.addWidget(navigation_controls(canvas));bar=QHBoxLayout();outer.addLayout(bar);bar.setContentsMargins(0,0,0,0);canvas.preference_widgets={}
    for label,attribute in [('邊界／中心吸附','snap_enabled'),('對齊參考線','guides_enabled'),('作品邊界疊圖','safety_visible'),('單框縮放控制點','resize_enabled')]:
        checkbox=QCheckBox(label);checkbox.setChecked(getattr(canvas,attribute));checkbox.toggled.connect(lambda value,key=attribute:(setattr(canvas,key,value),canvas.viewport().update()));bar.addWidget(checkbox);canvas.preference_widgets[attribute]=checkbox
    bar.addWidget(QLabel('微調mm（Shift×10）'));step=QDoubleSpinBox();step.setRange(.01,10);step.setDecimals(2);step.setValue(canvas.nudge_mm);step.valueChanged.connect(lambda value:setattr(canvas,'nudge_mm',value));bar.addWidget(step);canvas.preference_widgets['nudge_mm']=step;bar.addWidget(QLabel('Space暫時平移；疊圖開關不改驗證'));return widget


class ObjectToolsDialog(QDialog):
    def __init__(self,window,kind,entity_id,parent=None):
        super().__init__(parent or window);self.window=window;self.library=window.library;self.kind=kind;self.entity_id=entity_id
        self.ids=[];self.dirty=set();self.loading=True;self.plan=None;self.request=None;self.generation=0;self._preview_generation=None;self.retained_patch=None;self.incomplete_inputs={}
        self.hidden_ids=set();self.dim_ids=set();self.structure={'status':'UNKNOWN','nodes':[]};self.tree_nodes=[]
        self.setWindowTitle('安全多選／精確對齊 · 候選、鎖定與持久歷史');self.resize(1450,1000)
        layout=QVBoxLayout(self);self.status=QLabel();self.status.setTextFormat(Qt.PlainText);self.status.setWordWrap(True);layout.addWidget(self.status)
        zone=QHBoxLayout();zone.addWidget(QLabel('全模板設計安全邊距 mm（0=作品邊界；不預設印刷標準）'));self.margin=QDoubleSpinBox();self.margin.setRange(0,999);self.margin.setDecimals(3);self.margin.valueChanged.connect(self.invalidate);zone.addWidget(self.margin);self.margin_button=QPushButton('預覽全模板安全區差異');self.margin_button.clicked.connect(self.preview_margin);zone.addWidget(self.margin_button);layout.addLayout(zone)
        bar=QHBoxLayout()
        for title,fn in (('重新載入',self.reload),('全矩形',lambda:self.canvas.fit()),('定位選取',self.focus_selection),('鎖定選取',lambda:self.preview_lock(True)),('明確解鎖選取',lambda:self.preview_lock(False)),('刪除選取候選',lambda:self.preview_request({'operation':'DELETE','ids':self.ids}))):
            b=QPushButton(title);b.clicked.connect(fn);bar.addWidget(b)
        layout.addLayout(bar)
        body=QSplitter();left=QWidget();index_layout=QVBoxLayout(left)
        self.index_mode=QComboBox();self.index_mode.addItems(['人物／公司語意樹','來源結構（衍生 SVG）']);self.index_mode.currentIndexChanged.connect(self.rebuild_index);index_layout.addWidget(self.index_mode)
        self.search=QLineEdit();self.search.setPlaceholderText('owner／種類／ID／字型／來源名稱');self.search.textChanged.connect(self.filter_index);index_layout.addWidget(self.search)
        self.index_filter=QComboBox()
        for title,value in [('全部','ALL'),('已鎖定','LOCKED'),('共享公司','SHARED'),('框位問題','PROBLEM')]:self.index_filter.addItem(title,value)
        self.index_filter.currentIndexChanged.connect(self.filter_index);index_layout.addWidget(self.index_filter)
        self.index_count=QLabel();self.index_count.setWordWrap(True);index_layout.addWidget(self.index_count)
        self.index_tree=QTreeWidget();self.index_tree.setMinimumHeight(140);self.index_tree.setHeaderLabel('索引／對應不確定性');self.index_tree.setSelectionMode(QTreeWidget.ExtendedSelection);self.index_tree.itemSelectionChanged.connect(self.tree_changed);index_layout.addWidget(self.index_tree,2)
        self.objects=QListWidget();self.objects.setMinimumHeight(65);self.objects.setMaximumHeight(130);self.objects.setSelectionMode(QListWidget.ExtendedSelection);self.objects.itemSelectionChanged.connect(self.list_changed);index_layout.addWidget(self.objects,1)
        for title,action in [('暫時隱藏選取框','HIDE'),('淡化選取框','DIM'),('隔離選取框','ISOLATE'),('顯示所有框／解除隔離','ALL')]:
            b=QPushButton(title);b.clicked.connect(lambda _,a=action:self.viewport_action(a));index_layout.addWidget(b)
        body.addWidget(left)
        self.canvas=ObjectCanvas();self.canvas.selection_ids.connect(self.select_ids);self.canvas.drag_proposal.connect(self.preview_request);self.canvas.preview_proposal.connect(self.preview_request);body.addWidget(self.canvas)
        layout.addWidget(canvas_controls(self.canvas,self.library))
        right=QWidget();form=QFormLayout(right);self.context_form=form;self.editors={}
        self.context_status=QLabel('未選取／未知上下文');self.context_status.setWordWrap(True);form.addRow(self.context_status)
        from .property_context import load_tool_pins
        self.pin_text=QCheckBox('釘選文字工具（不適用仍禁止操作）');self.pin_text.setChecked('text' in load_tool_pins(self.library));self.pin_text.toggled.connect(self.pin_changed);form.addRow(self.pin_text)
        self.retained_button=QPushButton('查看舊版本未套用屬性');self.retained_button.clicked.connect(self.inspect_pending);self.retained_button.hide();form.addRow(self.retained_button)
        self.all_properties=QCheckBox('展開全部屬性');self.all_properties.toggled.connect(self.update_context);form.addRow(self.all_properties)
        for key,name in (('x','X'),('y','Y'),('w','寬'),('h','高'),('size_pt','固定字級pt'),('min_scale','水平比例下限')):
            spin=QDoubleSpinBox();spin.setRange(-2001,2000);spin.setDecimals(4);spin.setSpecialValueText('混合／未提供');spin.valueChanged.connect(lambda value,k=key:self.changed(k));self.editors[key]=spin;form.addRow(name,spin)
            spin.lineEdit().textEdited.connect(lambda text,k=key:self.numeric_edited(k))
        for key,name,choices in (('kind','類型',list(KINDS.items())),('owner','歸屬',[(f'{p}{n}',f'{p}{n}') for p in ('p','c') for n in range(1,21)]),('align','對齊',[('left','靠左'),('center','置中'),('right','靠右')])):
            combo=QComboBox();combo.setPlaceholderText('混合／各不相同')
            for value,title in choices:combo.addItem(title,value)
            combo.currentIndexChanged.connect(lambda value,k=key:self.changed(k));self.editors[key]=combo;form.addRow(name,combo)
        self.index=QDoubleSpinBox();self.index.setDecimals(0);self.index.setRange(-1,19);self.index.setSpecialValueText('混合');self.index.valueChanged.connect(lambda _:self.changed('index'));self.editors['index']=self.index;form.addRow('映射序號（0起）',self.index)
        self.index.lineEdit().textEdited.connect(lambda text:self.numeric_edited('index'))
        color=QLineEdit();color.setMaxLength(7);color.setPlaceholderText('混合色彩');color.textChanged.connect(lambda _:self.changed('color'));self.editors['color']=color;form.addRow('文字色彩',color)
        self.required=QCheckBox();self.required.stateChanged.connect(lambda _:self.changed('required'));self.editors['required']=self.required;form.addRow('必要欄位',self.required)
        self.font_choice=QComboBox();self.font_choice.addItem('保持每個物件的原pin／style',None)
        from .font_catalog import raw_asset
        for asset in self.library.fonts():
            try:
                raw=raw_asset(asset);self.font_choice.addItem(raw.familyName()+' / '+raw.styleName(),{'font':raw.familyName(),'font_style':raw.styleName(),'font_asset':copy.deepcopy(asset)})
            except ValueError:pass
        self.font_choice.currentIndexChanged.connect(lambda _:self.changed('font_asset'));form.addRow('明確核准字面',self.font_choice)
        self.properties=QPlainTextEdit();self.properties.setReadOnly(True);self.properties.setMaximumHeight(130);form.addRow(self.properties)
        patch=QPushButton('預覽明確修改的共同屬性');patch.clicked.connect(self.preview_patch);form.addRow(patch)
        self.cross=QCheckBox('已核對跨人物／公司及共享關聯範圍');self.cross.toggled.connect(self.invalidate);form.addRow(self.cross)
        self.reference=QComboBox();self.reference.currentIndexChanged.connect(self.invalidate);form.addRow('明確基準',self.reference)
        self.direction=QComboBox()
        for title,op,axis in (('靠左','ALIGN','LEFT'),('水平置中','ALIGN','HCENTER'),('靠右','ALIGN','RIGHT'),('靠上','ALIGN','TOP'),('垂直置中','ALIGN','VCENTER'),('靠下','ALIGN','BOTTOM'),('水平等邊界間距','DISTRIBUTE','HORIZONTAL'),('垂直等邊界間距','DISTRIBUTE','VERTICAL')):self.direction.addItem(title,(op,axis))
        self.direction.currentIndexChanged.connect(self.invalidate);form.addRow('操作方向',self.direction)
        align=QPushButton('預覽對齊／等距分布');align.clicked.connect(self.preview_geometry);form.addRow(align)
        self.dx=QDoubleSpinBox();self.dy=QDoubleSpinBox()
        for key,spin in (('群組ΔX mm',self.dx),('群組ΔY mm',self.dy)):spin.setRange(-2000,2000);spin.setDecimals(4);spin.valueChanged.connect(self.invalidate);form.addRow(key,spin)
        move=QPushButton('預覽整組位移');move.clicked.connect(lambda:self.preview_request({'operation':'MOVE','ids':self.ids,'dx':self.dx.value(),'dy':self.dy.value()}));form.addRow(move)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(right);scroll.setMinimumWidth(330);body.addWidget(scroll);body.setSizes([230,780,350]);layout.addWidget(body,3)
        self.summary=QPlainTextEdit();self.summary.setReadOnly(True);self.summary.setMaximumHeight(105);layout.addWidget(self.summary)
        self.diff=QTableWidget(0,5);self.diff.setMaximumHeight(140);self.diff.setHorizontalHeaderLabels(['精確物件／歸屬','原X／Y／W／H','候選X／Y／W／H','ΔX／ΔY mm','屬性差異']);self.diff.setEditTriggers(QTableWidget.NoEditTriggers);layout.addWidget(self.diff,1)
        actions=QHBoxLayout();cancel=QPushButton('取消候選，不寫入');cancel.clicked.connect(self.invalidate);actions.addWidget(cancel)
        self.apply_button=QPushButton('核對範圍並原子套用');self.apply_button.clicked.connect(self.apply);self.apply_button.setEnabled(False);actions.addWidget(self.apply_button);layout.addLayout(actions)
        self.history=QTableWidget(0,3);self.history.setMaximumHeight(110);self.history.setHorizontalHeaderLabels(['歷史階段／操作','物件／歸屬','clock／批次']);self.history.setSelectionBehavior(QTableWidget.SelectRows);self.history.setSelectionMode(QTableWidget.SingleSelection);self.history.setEditTriggers(QTableWidget.NoEditTriggers);layout.addWidget(self.history,1)
        bar=QHBoxLayout()
        for title,action in (('核對並復原歷史','UNDO'),('核對並重做歷史','REDO')):
            b=QPushButton(title);b.clicked.connect(lambda _,a=action:self.history_action(a));bar.addWidget(b)
        close=QDialogButtonBox(QDialogButtonBox.Close);close.rejected.connect(self.reject);bar.addWidget(close);layout.addLayout(bar)
        self.loading=False;self.reload()

    def showEvent(self,event):
        super().showEvent(event);self.canvas.fit()

    def invalidate(self,*_):
        if self.loading:return
        self.generation+=1;self.plan=None;self.request=None;self._preview_generation=None;self.canvas.clear_preview();self.diff.setRowCount(0);self.apply_button.setEnabled(False)
        self.summary.setPlainText('候選已清除；只影響明確選取且可編輯物件，未核驗字形／原稿內容不冒稱PASS。')
    def changed(self,key):
        if self.loading:return
        self.dirty.add(key);self.invalidate();self.status.setText('輸入中／待套用：只屬目前明確選取，先預覽差異再確認。')
        self.update_context()
    def numeric_edited(self,key):
        if self.loading:return
        editor=self.editors[key]
        if editor.hasAcceptableInput():self.incomplete_inputs.pop(key,None)
        else:self.incomplete_inputs[key]=editor.lineEdit().text()[:80]
        self.changed(key)
    def restore_incomplete(self):
        for key,text in self.incomplete_inputs.items():self.editors[key].lineEdit().setText(text)
    def reload(self):
        if self.dirty or self.retained_patch:
            from .property_context import discard_pending_selection
            if not discard_pending_selection(self,'重新載入'):self.restore_incomplete();return
            self.dirty.clear();self.retained_patch=None;self.incomplete_inputs.clear();self.retained_button.hide()
        try:
            self.snapshot=self.library.object_snapshot(self.kind,self.entity_id);self.invalidate();self.loading=True
            self.objects.clear();payload=self.snapshot['payload'];self.canvas.readonly=self.kind=='TEMPLATE' and payload['state']!='draft'
            slots=[Slot(**{**s,'rect':Rect(**s['rect'])}) for s in payload['slots']]
            w,h=(payload['width_mm'],payload['height_mm']) if self.kind=='TEMPLATE' else (payload['work_width'],payload['work_height'])
            image=None
            if self.kind=='TEMPLATE' and payload.get('background'):
                from .render import render_background
                image=render_background(Template.from_dict(payload),96)
            elif self.kind=='ARTWORK':
                source=self.library.source(self.library.artwork(self.entity_id)['source_id']);original=QImage(source['image']);c=payload['crop']
                if not original.isNull():image=original.copy(QRectF(c['x']*original.width()/source['width_mm'],c['y']*original.height()/source['height_mm'],c['w']*original.width()/source['width_mm'],c['h']*original.height()/source['height_mm']).toAlignedRect())
            for s in slots:
                item=QListWidgetItem(f"{'🔒 ' if s.locked else ''}{s.owner}／{KINDS.get(s.kind,s.kind)} 第{s.index+1}欄");item.setData(Qt.UserRole,s.id);item.setToolTip(s.id);self.objects.addItem(item)
            self.canvas.set_content(w,h,image=image,slots=slots,safe_margin_mm=payload.get('safe_margin_mm',0));self.margin.setValue(payload.get('safe_margin_mm',0));self.margin.setEnabled(self.kind=='TEMPLATE' and payload.get('state')=='draft');self.margin_button.setEnabled(self.margin.isEnabled());self.ids=[];self.hidden_ids.clear();self.dim_ids.clear();self.dirty.clear()
            from .object_index import source_structure
            source_id=payload.get('source_id') if self.kind=='TEMPLATE' else self.library.artwork(self.entity_id)['source_id']
            self.structure=source_structure(self.library.source(source_id) if source_id else None,payload)
            self.loading=False;self.rebuild_index();self.select_ids([])
            self.records=self.library.object_edit_history(self.kind,self.entity_id);self.history.setRowCount(len(self.records))
            for i,r in enumerate(self.records):
                for col,value in enumerate((r['phase']+'／'+r['plan']['request']['operation'],', '.join(c['owner']+'/'+c['kind']+'/'+c['id'] for c in r['plan']['changes']),str(r['expected_revision'])+'／'+r['id'])):self.history.setItem(i,col,QTableWidgetItem(value))
            self.history.resizeColumnsToContents();self.status.setText(f'{self.kind}／{self.entity_id} · revision {self.snapshot["revision"]}；原生文字／字距未知，不修改原檔或發布版本。');self.canvas.fit()
        except Exception as error:self.loading=False;self.status.setText('未載入：'+str(error));self.apply_button.setEnabled(False)
    def list_changed(self):
        if not self.loading:self.select_ids(sorted(item.data(Qt.UserRole) for item in self.objects.selectedItems()))
    def rebuild_index(self,*_):
        if self.loading or not hasattr(self,'snapshot'):return
        from .object_index import semantic_index
        self.index_tree.blockSignals(True);self.index_tree.clear();self.tree_nodes=[]
        def add(node,parent):
            item=QTreeWidgetItem(parent,[node['label']]);item.setData(0,Qt.UserRole,node['ids']);self.tree_nodes.append(item)
            if not node['ids']:item.setToolTip(0,'對應 UNKNOWN；選取這列不會猜測或更改 slot')
            for child in node.get('children',[]):add(child,item)
        nodes=semantic_index(self.snapshot['payload']) if self.index_mode.currentIndex()==0 else self.structure.get('nodes',[])+[{'label':'已標記物件（與來源節點對應 UNKNOWN）','ids':[],'children':[{'label':s['owner']+'/'+s['kind']+'/'+s['id'],'ids':[s['id']],'children':[]} for s in self.snapshot['payload']['slots']]}]
        for node in nodes:add(node,self.index_tree)
        self.index_tree.expandAll();self.index_tree.blockSignals(False);self.sync_tree();self.filter_index()
    def sync_tree(self):
        self.index_tree.blockSignals(True)
        for item in self.tree_nodes:
            ids=item.data(0,Qt.UserRole);item.setSelected(bool(ids) and len(ids)==1 and ids[0] in self.ids)
        self.index_tree.blockSignals(False)
    def tree_changed(self):
        if self.loading:return
        ids=sorted({i for item in self.index_tree.selectedItems() for i in item.data(0,Qt.UserRole) or []})
        if ids:self.select_ids(ids)
        else:self.index_count.setText('來源映射 UNKNOWN；原選取保持，不猜測物件')
    def filter_index(self,*_):
        if self.loading or not hasattr(self,'snapshot'):return
        from .object_index import matching_ids
        hits=set(matching_ids(self.snapshot['payload'],self.search.text(),self.index_filter.currentData()))
        self.objects.blockSignals(True)
        for i in range(self.objects.count()):
            item=self.objects.item(i);item.setHidden(item.data(Qt.UserRole) not in hits)
        self.objects.blockSignals(False)
        self.index_tree.blockSignals(True)
        def visible(item):
            children=[visible(item.child(i)) for i in range(item.childCount())];ids=item.data(0,Qt.UserRole) or []
            name_hit=self.index_mode.currentIndex()==1 and self.index_filter.currentData()=='ALL' and bool(self.search.text()) and all(t in item.text(0).casefold() for t in self.search.text().casefold().split())
            show=bool(set(ids)&hits) or any(children) or name_hit or (not ids and not self.search.text() and self.index_filter.currentData()=='ALL')
            item.setHidden(not show);return show
        for i in range(self.index_tree.topLevelItemCount()):visible(self.index_tree.topLevelItem(i))
        self.index_tree.blockSignals(False)
        self.index_count.setText(f'符合 {len(hits)}／{len(self.snapshot["payload"]["slots"])}；选取 {len(self.ids)}，篩選外 {len(set(self.ids)-hits)}；隱藏框 {len(self.hidden_ids)}\n來源 {self.structure["status"]}／slot 映射 {self.structure.get("mapping","UNKNOWN")}；原生Illustrator UNKNOWN')
    def viewport_action(self,action):
        known={s['id'] for s in self.snapshot['payload']['slots']}
        if action=='ALL':self.hidden_ids.clear();self.dim_ids.clear()
        elif not self.ids:self.status.setText('請明確選取；viewport不自動選其他物件');return
        elif action=='HIDE':self.hidden_ids.update(self.ids)
        elif action=='DIM':self.dim_ids.update(self.ids)
        elif action=='ISOLATE':self.hidden_ids=known-set(self.ids)
        self.canvas.resetting=True
        try:
            for item in self.canvas.scene().items():
                if isinstance(item,Box):
                    item.setVisible(item.slot.id not in self.hidden_ids);item.setOpacity(.18 if item.slot.id in self.dim_ids else 1)
                    item.setSelected(item.slot.id in self.ids and item.slot.id not in self.hidden_ids)
        finally:self.canvas.resetting=False
        self.filter_index();self.status.setText('只改檢視框；原稿背景與 DB／正式 Gate 全量範圍不變。隱藏不等於解鎖。')
    def select_ids(self,ids):
        if self.loading:return
        if not self.context_current():self.update_context();return
        known={s['id'] for s in self.snapshot['payload']['slots']}
        if len(ids)!=len(set(ids)) or any(i not in known for i in ids):self.status.setText('物件身份不唯一／上下文不符，未變更選取');return
        if self.dirty:
            if set(ids)==set(self.ids):self.restore_incomplete();return
            from .property_context import discard_pending_selection
            if not discard_pending_selection(self):
                self.loading=True
                try:
                    self.canvas.select_ids(self.ids);self.objects.blockSignals(True)
                    for i in range(self.objects.count()):self.objects.item(i).setSelected(self.objects.item(i).data(Qt.UserRole) in self.ids)
                    self.objects.blockSignals(False);self.sync_tree()
                finally:self.loading=False
                self.restore_incomplete()
                self.status.setText('待套用輸入已保留於原選取；未更動物件。');return
        self.invalidate();self.loading=True;self.ids=list(ids);self.dirty.clear();self.incomplete_inputs.clear();self.cross.setChecked(False);self.canvas.select_ids(ids)
        self.objects.blockSignals(True)
        for i in range(self.objects.count()):self.objects.item(i).setSelected(self.objects.item(i).data(Qt.UserRole) in ids)
        self.objects.blockSignals(False);self.reference.clear();self.reference.addItem('請明確指定基準',None);self.reference.addItem('選取邊界','SELECTION')
        self.sync_tree();self.filter_index()
        if ids:
            common=common_properties(self.snapshot['payload'],ids);rows=[s for s in self.snapshot['payload']['slots'] if s['id'] in ids];text_only=all(s['kind']!='logo' for s in rows)
            for s in rows:self.reference.addItem(s['owner']+'/'+s['kind']+'/'+s['id'][:8],s['id'])
            for key,editor in self.editors.items():
                value=common[key]['value'];editor.setEnabled(not self.canvas.readonly and (text_only or key not in ('size_pt','min_scale','align','color')) and (len(ids)==1 or key not in ('kind','owner','index')))
                if isinstance(editor,QDoubleSpinBox):
                    editor.setRange(min(-2001,value if value is not None else -2001),max(2000,value if value is not None else 2000));editor.setValue(value if value is not None else editor.minimum())
                elif isinstance(editor,QComboBox):editor.setCurrentIndex(editor.findData(value) if value is not None else -1)
                elif isinstance(editor,QLineEdit):editor.setText(value or '')
                else:editor.setTristate(value is None);editor.setCheckState(Qt.PartiallyChecked if value is None else Qt.Checked if value else Qt.Unchecked)
            self.font_choice.setCurrentIndex(0);self.font_choice.setEnabled(text_only and not self.canvas.readonly)
            payload=self.snapshot['payload'];links=payload.get('company_bindings',{})
            from .model import company_ports
            def association(s):
                return '公司關聯 '+str(links.get(s['owner'],'未確認')) if s['owner'].startswith('p') else '共享人物 '+(', '.join(p for p,c in links.items() if s['owner'] in company_ports(c)) or '未確認')
            detail='\n'.join(f"{s['owner']}/{s['kind']}／{s['id']} · {'鎖定' if s.get('locked',False) else '未鎖定'} · {s['font']}/{s.get('font_style') or '原生款式未知'} · {association(s)}" for s in rows)
            size=(payload['width_mm'],payload['height_mm']) if self.kind=='TEMPLATE' else (payload['work_width'],payload['work_height'])
            detail=f"矩形 {size[0]:g}×{size[1]:g} mm／{self.kind} {self.entity_id}／来源作品 {payload.get('source_work_id') or (self.entity_id if self.kind=='ARTWORK' else '未知')}\n"+detail
            mixed=', '.join(k for k,v in common.items() if v['mixed']);self.properties.setPlainText(f'選取{len(ids)}件。混合：{mixed or "無"}\n'+detail+'\n文字內容／原生字距未知。Logo不適用文字patch；跨owner需核對範圍。')
        else:
            for editor in self.editors.values():
                editor.setEnabled(False)
                if isinstance(editor,QDoubleSpinBox):editor.setValue(editor.minimum())
                elif isinstance(editor,QComboBox):editor.setCurrentIndex(-1)
                elif isinstance(editor,QLineEdit):editor.clear()
                else:editor.setCheckState(Qt.Unchecked)
            self.font_choice.setEnabled(False);self.properties.setPlainText('未選取物件；沒有自動加入其他人物／公司。')
        self.loading=False;self.filter_index();self.update_context()

    def update_context(self, *_):
        rows=[s for s in self.snapshot['payload']['slots'] if s['id'] in self.ids] if hasattr(self,'snapshot') else []
        if hasattr(self,'snapshot') and not self.context_current():
            if self.dirty and self.retained_patch is None:self.retained_patch=dict(kind=self.kind,entity_id=self.entity_id,revision=self.snapshot['revision'],ids=self.ids.copy(),patch=self.current_patch(),incomplete=dict(self.incomplete_inputs))
            was_loading=self.loading;self.loading=True
            try:
                self.ids=[];self.canvas.readonly=True;self.canvas.set_mode('pan');self.canvas.select_ids([]);self.objects.blockSignals(True);self.objects.clearSelection();self.objects.blockSignals(False);self.sync_tree()
                for editor in self.editors.values():
                    editor.setEnabled(False)
                    if isinstance(editor,QDoubleSpinBox):editor.setValue(editor.minimum())
                    elif isinstance(editor,QComboBox):editor.setCurrentIndex(-1)
                    elif isinstance(editor,QLineEdit):editor.clear()
                    else:editor.setTristate(True);editor.setCheckState(Qt.PartiallyChecked)
                self.font_choice.setEnabled(False);self.margin.setEnabled(False);self.margin_button.setEnabled(False);self.apply_button.setEnabled(False)
            finally:self.loading=was_loading
            self.filter_index()
            self.context_status.setText('來源版本已失效；屬性已清空，請重新載入並選取。');self.status.setText('來源版本已失效；待套用輸入保留供核對，未套到新物件。');self.retained_button.setVisible(self.retained_patch is not None);return
        text=bool(rows) and all(s['kind']!='logo' for s in rows)
        locked=any(s.get('locked',False) for s in rows)
        label='未選取／過期時無可用值' if not rows else '多選（混合值逐欄判斷）' if len(rows)>1 else '完整Logo；文字工具不適用' if not text else '文字物件；固定字級'
        if locked:label+='；包含鎖定物件，須先明確解鎖'
        self.context_status.setText(label+'／'+self.kind+' '+self.entity_id)
        for key,editor in self.editors.items():editor.setEnabled(bool(rows) and not locked and not self.canvas.readonly and (text or key not in ('size_pt','min_scale','align','color')) and (len(rows)==1 or key not in ('kind','owner','index')))
        self.font_choice.setEnabled(bool(rows) and text and not locked and not self.canvas.readonly)
        for key in ('size_pt','min_scale','align','color'):
            editor=self.editors[key];self.context_form.setRowVisible(editor,text or self.pin_text.isChecked() or self.all_properties.isChecked())
            if not text:editor.setEnabled(False)
    def context_current(self):
        if not hasattr(self,'snapshot') or self.library.closed or self.window.library is not self.library:return False
        try:
            current=self.library.object_snapshot(self.kind,self.entity_id)
            return current['revision']==self.snapshot['revision'] and fingerprint(current['payload'])==fingerprint(self.snapshot['payload'])
        except (ValueError,OSError):return False
    def current_patch(self):
        patch={}
        for key in self.dirty:
            if key=='font_asset':
                if self.font_choice.currentData():patch.update(copy.deepcopy(self.font_choice.currentData()))
                continue
            editor=self.editors[key]
            patch[key]=editor.currentData() if isinstance(editor,QComboBox) else editor.text().strip() if isinstance(editor,QLineEdit) else editor.isChecked() if isinstance(editor,QCheckBox) else int(editor.value()) if key=='index' else editor.value()
        return patch
    def pin_changed(self,checked):
        from .property_context import load_tool_pins,save_tool_pins
        from PySide6.QtCore import QSignalBlocker
        pins=load_tool_pins(self.library);pins.add('text') if checked else pins.discard('text')
        try:save_tool_pins(self.library,pins)
        except Exception:self.status.setText('工具偏好未保存；當次顯示保留，未變更物件。')
        context=getattr(self.window,'right_context',None)
        if context is not None:
            context.pins=pins
            with QSignalBlocker(self.window.property_pin_checks['text']):self.window.property_pin_checks['text'].setChecked(checked)
            context.sync()
        self.update_context()
    def inspect_pending(self):
        if not self.retained_patch:return
        box=QMessageBox(self);box.setWindowTitle('舊版本未套用屬性（唯讀）');box.setText('原版本已改變；這份輸入未套至任何新物件。重新載入或關閉前可明確放棄。');box.setDetailedText(json.dumps(self.retained_patch,ensure_ascii=False,indent=2));box.exec()
    def reject(self):
        if self.dirty or self.retained_patch:
            from .property_context import discard_pending_selection
            if not discard_pending_selection(self,'關閉'):self.restore_incomplete();return
            self.dirty.clear();self.retained_patch=None;self.incomplete_inputs.clear()
        super().reject()
    def closeEvent(self,event):
        if self.dirty or self.retained_patch:
            from .property_context import discard_pending_selection
            if not discard_pending_selection(self,'關閉'):self.restore_incomplete();event.ignore();return
            self.dirty.clear();self.retained_patch=None;self.incomplete_inputs.clear()
        super().closeEvent(event)
    def focus_selection(self):
        items=[i for i in self.canvas.scene().items() if isinstance(i,Box) and i.slot.id in self.ids]
        if items:
            rect=items[0].sceneBoundingRect()
            for i in items[1:]:rect=rect.united(i.sceneBoundingRect())
            self.canvas.fitInView(rect.adjusted(-2,-2,2,2),Qt.KeepAspectRatio)
    def preview_lock(self,locked):self.preview_request({'operation':'LOCK','ids':self.ids,'locked':locked})
    def preview_margin(self):self.preview_request(dict(operation='SAFETY_ZONE',ids=[s['id'] for s in self.snapshot['payload']['slots']],margin_mm=self.margin.value()))
    def preview_patch(self):
        if self.context_current() and (self.incomplete_inputs or any(isinstance(editor,QDoubleSpinBox) and not editor.hasAcceptableInput() for editor in self.editors.values())):self.status.setText('數字輸入尚未完成，未建立提議；請完成或明確放棄。');return
        self.preview_request({'operation':'PATCH','ids':self.ids,'patch':self.current_patch()})
    def preview_geometry(self):
        op,axis=self.direction.currentData();self.preview_request({'operation':op,'axis':axis,'reference':self.reference.currentData(),'ids':self.ids})
    def preview_request(self,request):
        if not self.context_current():self.update_context();self.status.setText('來源版本已變更，先重新載入；未建立舊版本提議。');return
        self.invalidate();request=copy.deepcopy(request);request['cross_owner']=self.cross.isChecked()
        try:
            self.plan=propose(self.snapshot['payload'],self.kind,request);self.request=copy.deepcopy(request);self._preview_generation=self.generation;self.canvas.show_preview(self.plan)
            self.diff.setRowCount(len(self.plan['changes']))
            for i,c in enumerate(self.plan['changes']):
                old=c['before'];new=c['after'];fmt=lambda s:'刪除' if not s else ' / '.join(f'{s["rect"][k]:.4f}' for k in ('x','y','w','h'))
                differences='；'.join(k+': '+str(old.get(k))+' → '+str(new.get(k)) for k in old if new and old.get(k)!=new.get(k) and k not in ('rect','font_asset'))
                if new and old.get('font_asset')!=new.get('font_asset'):differences+='；核准字型pin已變更，款式與家族見上列'
                for col,value in enumerate((c['owner']+'/'+c['kind']+'/'+c['id'],fmt(old),fmt(new),f'{c["dx"]:.4f} / {c["dy"]:.4f}',differences)) :self.diff.setItem(i,col,QTableWidgetItem(value))
            self.diff.resizeColumnsToContents();self.apply_button.setEnabled(True)
            self.summary.setPlainText(f"候選 {request['operation']} · {len(self.plan['changes'])}實際差異／{len(request['ids'])}明確範圍 · reference {request.get('reference','不適用')} · gap {self.plan['gap_mm']} mm\n"+'；'.join(self.plan['warnings']))
            self.status.setText('綠框僅候選，藍框為原位置；尚未寫入。可取消或核對範圍後套用。')
        except Exception as error:self.plan=None;self.request=None;self.status.setText('候選拒絕：'+str(error));self.apply_button.setEnabled(False)
    def after_write(self):
        self.dirty.clear();self.retained_patch=None;self.incomplete_inputs.clear();self.retained_button.hide()
        w=self.window
        if self.kind=='TEMPLATE' and w.template and w.template.id==self.entity_id:w.template=None;w.refresh_templates(self.entity_id)
        elif self.kind=='ARTWORK' and w.work and w.work['id']==self.entity_id:w.load_work(self.library.artwork(self.entity_id))
        w.invalidate();self.reload()
    def main_content_clean(self):
        w=self.window
        if self.kind=='TEMPLATE' and w.template and w.template.id==self.entity_id:
            base=getattr(w,'template_base_payload',None)
            if base is None or Template.from_dict(base)!=w.template:raise ValueError('主編輯有未保存手工內容，未覆蓋')
        elif self.kind=='ARTWORK' and w.work and w.work['id']==self.entity_id:
            slots=[Slot(**{**s,'rect':Rect(**s['rect'])}) for s in w.work['payload']['slots']]
            if slots!=w.slots:raise ValueError('來源主編輯有未保存手工內容，未覆蓋')
        if w.current_slot:
            candidate=w.make_slot(Rect(*(spin.value() for spin in w.coords)),preserve=True);candidate.id=w.current_slot.id
            if candidate!=w.current_slot:raise ValueError('主屬性面板有未套用手工內容，未覆蓋')
    def apply(self):
        if not self.context_current():self.update_context();self.status.setText('來源版本已變更，未套用。');return
        if self.request is None or self.plan is None or self._preview_generation!=self.generation:return
        if QMessageBox.question(self,'核對差異與精確範圍',self.summary.toPlainText()+'\n物件：'+', '.join(self.request['ids'])+'\n確定僅套用本候選？不等於發布／正式輸出PASS。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        if self.request is None or self._preview_generation!=self.generation:return
        self.apply_button.setEnabled(False)
        try:
            self.main_content_clean()
            self.library.apply_object_edit(self.snapshot,copy.deepcopy(self.request),True);self.after_write();self.status.setText('已原子保存本次差異；不合格項目仍須修復，歷史可核對Undo／Redo。')
        except Exception as error:self.status.setText('未提交：'+str(error));self.apply_button.setEnabled(self.plan is not None)
    def history_action(self,action):
        rows=self.history.selectionModel().selectedRows()
        if not rows:return
        record=self.records[rows[0].row()]
        scope=', '.join(c['owner']+'/'+c['kind']+'/'+c['id'] for c in record['plan']['changes'])
        if QMessageBox.question(self,'核對歷史'+action,scope+'\n'+record['plan']['request']['operation']+'；只對未有後續編輯／發布的此批次作用，可能包含明確鎖定／解鎖。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        try:self.main_content_clean();self.library.object_history_action(record['id'],action,True);self.after_write();self.status.setText('本批歷史已'+action+'；全物件驗證仍涵蓋所有slot。')
        except Exception as error:self.status.setText('歷史拒絕：'+str(error))

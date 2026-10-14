"""Two-mode advanced object editor: stable selection, dirty patch, previews and durable history."""
import copy
import json
from PySide6.QtCore import Qt,QPointF,QRectF,Signal
from PySide6.QtGui import QColor,QPen,QImage
from PySide6.QtWidgets import (QDialog,QDialogButtonBox,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QListWidget,QListWidgetItem,QFormLayout,QDoubleSpinBox,QComboBox,QCheckBox,QLineEdit,QSplitter,QWidget,QTableWidget,QTableWidgetItem,QMessageBox,QGraphicsItem,QScrollArea,QPlainTextEdit)
from .gui import Canvas,Box
from .model import Slot,Rect,KINDS,Template
from .object_tools import propose,common_properties,warnings_for
from .font_review import fingerprint


class ObjectCanvas(Canvas):
    selection_ids=Signal(object)
    drag_proposal=Signal(object)
    def __init__(self):
        self.resetting=True;super().__init__();self.allow_multi_drag=True;self.resetting=False;self.base_positions={};self.overlays=[]
    def selection_changed(self):
        if self.resetting:return
        self.selection_ids.emit(sorted(i.slot.id for i in self.scene().selectedItems() if isinstance(i,Box)))
    def set_content(self,*args,**kw):
        self.resetting=True
        try:
            super().set_content(*args,**kw)
            self.base_positions={i.slot.id:(i.pos().x(),i.pos().y()) for i in self.scene().items() if isinstance(i,Box)}
            self.setSceneRect(QRectF(-2010,-2010,6020,6020))
            self.overlays=[];self.mode='edit';self.setDragMode(Canvas.RubberBandDrag)
            for i in self.scene().items():
                if isinstance(i,Box):i.setFlag(QGraphicsItem.ItemIsSelectable,True);i.setFlag(QGraphicsItem.ItemIsMovable,not self.readonly and not i.slot.locked)
        finally:self.resetting=False
    def fit(self):self.fitInView(QRectF(-5,-5,self.width_mm+10,self.height_mm+10),Qt.KeepAspectRatio)
    def select_ids(self,ids):
        self.resetting=True
        try:
            for i in self.scene().items():
                if isinstance(i,Box):i.setSelected(i.slot.id in ids)
        finally:self.resetting=False
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        changed=[]
        for i in self.scene().items():
            if isinstance(i,Box) and i.slot.id in self.base_positions:
                x,y=self.base_positions[i.slot.id];dx,dy=i.pos().x()-x,i.pos().y()-y
                if abs(dx)+abs(dy)>1e-6:changed.append((i.slot.id,dx,dy))
                i.setPos(x,y);i.slot.rect.x,i.slot.rect.y=x,y
        if changed:
            ids=sorted(i.slot.id for i in self.scene().selectedItems() if isinstance(i,Box))
            dx,dy=changed[0][1:]
            self.drag_proposal.emit({'operation':'MOVE','ids':ids,'dx':dx,'dy':dy})
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


class ObjectToolsDialog(QDialog):
    def __init__(self,window,kind,entity_id,parent=None):
        super().__init__(parent or window);self.window=window;self.library=window.library;self.kind=kind;self.entity_id=entity_id
        self.ids=[];self.dirty=set();self.loading=True;self.plan=None;self.request=None;self.generation=0;self._preview_generation=None
        self.setWindowTitle('安全多選／精確對齊 · 候選、鎖定與持久歷史');self.resize(1450,1000)
        layout=QVBoxLayout(self);self.status=QLabel();self.status.setTextFormat(Qt.PlainText);self.status.setWordWrap(True);layout.addWidget(self.status)
        bar=QHBoxLayout()
        for title,fn in (('重新載入',self.reload),('全矩形',lambda:self.canvas.fit()),('定位選取',self.focus_selection),('鎖定選取',lambda:self.preview_lock(True)),('明確解鎖選取',lambda:self.preview_lock(False)),('刪除選取候選',lambda:self.preview_request({'operation':'DELETE','ids':self.ids}))):
            b=QPushButton(title);b.clicked.connect(fn);bar.addWidget(b)
        layout.addLayout(bar)
        body=QSplitter();self.objects=QListWidget();self.objects.setSelectionMode(QListWidget.ExtendedSelection);self.objects.itemSelectionChanged.connect(self.list_changed);body.addWidget(self.objects)
        self.canvas=ObjectCanvas();self.canvas.selection_ids.connect(self.select_ids);self.canvas.drag_proposal.connect(self.preview_request);body.addWidget(self.canvas)
        right=QWidget();form=QFormLayout(right);self.editors={}
        for key,name in (('x','X'),('y','Y'),('w','寬'),('h','高'),('size_pt','固定字級pt'),('min_scale','水平比例下限')):
            spin=QDoubleSpinBox();spin.setRange(-2001,2000);spin.setDecimals(4);spin.setSpecialValueText('混合／未提供');spin.valueChanged.connect(lambda value,k=key:self.changed(k));self.editors[key]=spin;form.addRow(name,spin)
        for key,name,choices in (('kind','類型',list(KINDS.items())),('owner','歸屬',[(f'{p}{n}',f'{p}{n}') for p in ('p','c') for n in range(1,21)]),('align','對齊',[('left','靠左'),('center','置中'),('right','靠右')])):
            combo=QComboBox();combo.setPlaceholderText('混合／各不相同')
            for value,title in choices:combo.addItem(title,value)
            combo.currentIndexChanged.connect(lambda value,k=key:self.changed(k));self.editors[key]=combo;form.addRow(name,combo)
        self.index=QDoubleSpinBox();self.index.setDecimals(0);self.index.setRange(-1,19);self.index.setSpecialValueText('混合');self.index.valueChanged.connect(lambda _:self.changed('index'));self.editors['index']=self.index;form.addRow('映射序號（0起）',self.index)
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
        self.diff=QTableWidget(0,5);self.diff.setHorizontalHeaderLabels(['精確物件／歸屬','原X／Y／W／H','候選X／Y／W／H','ΔX／ΔY mm','屬性差異']);self.diff.setEditTriggers(QTableWidget.NoEditTriggers);layout.addWidget(self.diff,1)
        actions=QHBoxLayout();cancel=QPushButton('取消候選，不寫入');cancel.clicked.connect(self.invalidate);actions.addWidget(cancel)
        self.apply_button=QPushButton('核對範圍並原子套用');self.apply_button.clicked.connect(self.apply);self.apply_button.setEnabled(False);actions.addWidget(self.apply_button);layout.addLayout(actions)
        self.history=QTableWidget(0,3);self.history.setHorizontalHeaderLabels(['歷史階段／操作','物件／歸屬','clock／批次']);self.history.setSelectionBehavior(QTableWidget.SelectRows);self.history.setSelectionMode(QTableWidget.SingleSelection);self.history.setEditTriggers(QTableWidget.NoEditTriggers);layout.addWidget(self.history,1)
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
        self.dirty.add(key);self.invalidate()
    def reload(self):
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
            self.canvas.set_content(w,h,image=image,slots=slots);self.ids=[];self.dirty.clear();self.loading=False;self.select_ids([])
            self.records=self.library.object_edit_history(self.kind,self.entity_id);self.history.setRowCount(len(self.records))
            for i,r in enumerate(self.records):
                for col,value in enumerate((r['phase']+'／'+r['plan']['request']['operation'],', '.join(c['owner']+'/'+c['kind']+'/'+c['id'] for c in r['plan']['changes']),str(r['expected_revision'])+'／'+r['id'])):self.history.setItem(i,col,QTableWidgetItem(value))
            self.history.resizeColumnsToContents();self.status.setText(f'{self.kind}／{self.entity_id} · revision {self.snapshot["revision"]}；原生文字／字距未知，不修改原檔或發布版本。');self.canvas.fit()
        except Exception as error:self.loading=False;self.status.setText('未載入：'+str(error));self.apply_button.setEnabled(False)
    def list_changed(self):
        if not self.loading:self.select_ids(sorted(item.data(Qt.UserRole) for item in self.objects.selectedItems()))
    def select_ids(self,ids):
        if self.loading:return
        known={s['id'] for s in self.snapshot['payload']['slots']}
        if len(ids)!=len(set(ids)) or any(i not in known for i in ids):self.status.setText('物件身份不唯一／上下文不符，未變更選取');return
        self.invalidate();self.loading=True;self.ids=list(ids);self.dirty.clear();self.canvas.select_ids(ids)
        self.objects.blockSignals(True)
        for i in range(self.objects.count()):self.objects.item(i).setSelected(self.objects.item(i).data(Qt.UserRole) in ids)
        self.objects.blockSignals(False);self.reference.clear();self.reference.addItem('請明確指定基準',None);self.reference.addItem('選取邊界','SELECTION')
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
            detail='\n'.join(f"{s['owner']}/{s['kind']}／{s['id']} · {'鎖定' if s.get('locked',False) else '未鎖定'} · {s['font']}/{s.get('font_style') or '原生款式未知'}" for s in rows)
            mixed=', '.join(k for k,v in common.items() if v['mixed']);self.properties.setPlainText(f'選取{len(ids)}件。混合：{mixed or "無"}\n'+detail+'\n文字內容／原生字距未知。Logo不適用文字patch；跨owner需核對範圍。')
        else:
            for editor in self.editors.values():editor.setEnabled(False)
            self.font_choice.setEnabled(False);self.properties.setPlainText('未選取物件；沒有自動加入其他人物／公司。')
        self.loading=False
    def focus_selection(self):
        items=[i for i in self.canvas.scene().items() if isinstance(i,Box) and i.slot.id in self.ids]
        if items:
            rect=items[0].sceneBoundingRect()
            for i in items[1:]:rect=rect.united(i.sceneBoundingRect())
            self.canvas.fitInView(rect.adjusted(-2,-2,2,2),Qt.KeepAspectRatio)
    def preview_lock(self,locked):self.preview_request({'operation':'LOCK','ids':self.ids,'locked':locked})
    def preview_patch(self):
        patch={}
        for key in self.dirty:
            if key=='font_asset':
                if self.font_choice.currentData():patch.update(copy.deepcopy(self.font_choice.currentData()))
                continue
            e=self.editors[key]
            patch[key]=e.currentData() if isinstance(e,QComboBox) else e.text().strip() if isinstance(e,QLineEdit) else e.isChecked() if isinstance(e,QCheckBox) else int(e.value()) if key=='index' else e.value()
        self.preview_request({'operation':'PATCH','ids':self.ids,'patch':patch})
    def preview_geometry(self):
        op,axis=self.direction.currentData();self.preview_request({'operation':op,'axis':axis,'reference':self.reference.currentData(),'ids':self.ids})
    def preview_request(self,request):
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

"""Direct source-canvas marking using the existing object canvas and facts store."""
from copy import deepcopy
from dataclasses import asdict
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QSplitter,QWidget,QLabel,QPushButton,QComboBox,
    QTableWidget,QTableWidgetItem,QPlainTextEdit,QLineEdit,QDoubleSpinBox,QCheckBox,QMessageBox,QInputDialog,QListWidget,QListWidgetItem)
from .annotations import AnnotationSession,resegment
from .object_dialog import ObjectCanvas
from .gui import Box,Canvas
from .model import Slot,Rect,KINDS
from .batch_import import healthy_source
from .training_quality import analyse_work


class AnnotationDialog(QDialog):
    def __init__(self,window,work_id,parent=None):
        super().__init__(parent or window);self.window=window;self.library=window.library;self.session=AnnotationSession(self.library,work_id);self.ids=[];self.loading=False
        self.setWindowTitle('原作品直接標記／校正：只改學習中介資料');self.resize(1350,850)
        layout=QVBoxLayout(self);self.status=QLabel('作品邊界與欄位框不同；拖曳／改類型只存候選，明確確認才成作品事實。');self.status.setWordWrap(True);layout.addWidget(self.status)
        bar=QHBoxLayout()
        for label,fn in [('框選新增標記',lambda:self.canvas.set_mode('slot')),('選取／校正',lambda:self.canvas.set_mode('edit')),('視角平移',lambda:self.canvas.set_mode('pan')),('原稿／疊圖切換',self.toggle_overlay),('改前／改後比較',self.compare),('復原',self.undo),('重做',self.redo)]:self.button(bar,label,fn)
        layout.addLayout(bar);body=QSplitter();self.objects=QListWidget();self.objects.setSelectionMode(QListWidget.ExtendedSelection);self.objects.itemSelectionChanged.connect(self.from_list);body.addWidget(self.objects)
        self.canvas=ObjectCanvas();self.canvas.selection_ids.connect(self.select);self.canvas.drag_proposal.connect(self.move);self.canvas.rectangle.connect(self.add);body.addWidget(self.canvas)
        panel=QWidget();form=QVBoxLayout(panel);self.kind=QComboBox()
        for key,value in KINDS.items():self.kind.addItem(value,key)
        self.owner=QLineEdit('p1');self.owner.setPlaceholderText('人物p1／公司c1，需核對真實歸屬');self.value=QLineEdit();self.value.setMaxLength(512)
        form.addWidget(QLabel('欄位類型 → 人物／公司歸屬 → 來源內容'));form.addWidget(self.kind);form.addWidget(self.owner);form.addWidget(self.value)
        self.coords=[]
        for key in ('x','y','w','h'):
            form.addWidget(QLabel(key+' mm'));spin=QDoubleSpinBox();spin.setRange(-2000,2000);spin.setDecimals(4);self.coords.append(spin);form.addWidget(spin)
        for label,fn in [('套用此框屬性草稿',self.apply_properties),('刪除選定標記草稿',self.delete),('保存草稿（未確認）',self.save),('確認所選作品事實',self.confirm),('改正作品邊界／拆分',self.split),('合併同來源明確作品',self.merge)]:
            b=QPushButton(label);b.clicked.connect(fn);form.addWidget(b)
        self.visual=QCheckBox('已核對目前原作品／完整圖文及物理尺寸');form.addWidget(self.visual)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);form.addWidget(self.details,1);body.addWidget(panel);body.setSizes([220,760,340]);layout.addWidget(body,1);self.overlay=True;self.refresh()

    def button(self,layout,label,fn):
        button=QPushButton(label);button.clicked.connect(fn);layout.addWidget(button);return button

    def guarded(self,fn):
        try:
            if self.window.busy:raise ValueError('背景工作執行中，先保留目前草稿')
            fn()
        except Exception as error:self.status.setText('未套用：'+str(error))

    def refresh(self):
        self.loading=True;payload=self.session.payload;source=self.library.source(self.session.base['source_id']);image=None
        if healthy_source(source):
            original=QImage(source['image']);crop=payload['crop'];image=original.copy(QRectF(crop['x']*original.width()/source['width_mm'],crop['y']*original.height()/source['height_mm'],crop['w']*original.width()/source['width_mm'],crop['h']*original.height()/source['height_mm']).toAlignedRect())
        self.objects.clear();slots=[Slot(**{**s,'rect':Rect(**s['rect'])}) for s in payload['slots']]
        confirmed=set((self.session.facts.get('confirmation') or {}).get('observation_ids',[]));by_slot={o.get('slot_id'):o for o in self.session.observations}
        for slot in slots:
            observation=by_slot.get(slot.id,{});state='已確認' if observation.get('id') in confirmed else '候選／待核對'
            item=QListWidgetItem(slot.owner+'／'+KINDS.get(slot.kind,slot.kind)+'／'+state);item.setData(Qt.UserRole,slot.id);item.setToolTip(slot.id);self.objects.addItem(item)
        self.canvas.set_content(payload['work_width'],payload['work_height'],image,slots,crop=Rect(0,0,payload['work_width'],payload['work_height']));self.canvas.set_mode('edit')
        self.visual.setChecked(bool(payload.get('visual_confirmed')));self.loading=False;self.select([i for i in self.ids if any(s.id==i for s in slots)])

    def showEvent(self,event):super().showEvent(event);self.canvas.fit()

    def from_list(self):
        if not self.loading:self.select([item.data(Qt.UserRole) for item in self.objects.selectedItems()])

    def select(self,ids):
        if self.loading:return
        self.ids=list(ids);self.loading=True;self.canvas.select_ids(ids)
        for i in range(self.objects.count()):self.objects.item(i).setSelected(self.objects.item(i).data(Qt.UserRole) in ids)
        self.loading=False
        if len(ids)==1:
            slot=next(s for s in self.session.payload['slots'] if s['id']==ids[0]);self.kind.setCurrentIndex(self.kind.findData(slot['kind']));self.owner.setText(slot['owner'])
            observation=next((o for o in self.session.observations if o.get('slot_id')==ids[0]),None);self.value.setText(observation['text'] if observation else '')
            for spin,key in zip(self.coords,('x','y','w','h')):spin.setValue(slot['rect'][key])
            self.details.setPlainText(f"作品 {self.session.base['id']}／來源 {self.session.base['source_id']}\n框 {ids[0]}／{slot['owner']}\n原生Illustrator對應未知；AI線索不等於真值。\n內容："+(observation['text'] if observation else '待補來源觀察'))
        else:self.details.setPlainText(f'明確選取{len(ids)}框。多選只允許適用操作，不以首框值覆蓋共同屬性。')

    def move(self,request):
        def action():self.session.change(dict(request,cross_owner=len({s['owner'] for s in self.session.payload['slots'] if s['id'] in request['ids']})<=1));self.refresh()
        self.guarded(action)

    def add(self,rect):
        def action():
            identity=self.session.add(rect,self.kind.currentData(),self.owner.text(),self.value.text() or '待來源核對');self.ids=[identity];self.refresh()
        self.guarded(action)

    def apply_properties(self):
        def action():
            if len(self.ids)!=1:raise ValueError('類型／歸屬只允許逐框核對；多選使用既有安全物件工具')
            patch=dict(zip(('x','y','w','h'),[s.value() for s in self.coords]));patch.update(kind=self.kind.currentData(),owner=self.owner.text())
            self.session.change(dict(operation='PATCH',ids=self.ids,patch=patch))
            for observation in self.session.observations:
                if observation.get('slot_id')==self.ids[0]:observation['text']=self.value.text()
            self.refresh()
        self.guarded(action)

    def delete(self):self.guarded(lambda:(self.session.change(dict(operation='DELETE',ids=self.ids)),self.refresh()))
    def undo(self):self.session.undo();self.refresh()
    def redo(self):self.session.redo();self.refresh()

    def toggle_overlay(self):
        self.overlay=not self.overlay;self.canvas.resetting=True
        for item in self.canvas.scene().items():
            if isinstance(item,Box):item.setVisible(self.overlay)
        self.canvas.resetting=False;self.status.setText('原稿檢視；選取保留、資料驗證仍涵蓋全部框' if not self.overlay else '作品邊界為橘色虛線，資料標記為藍框；來源未修改')

    def compare(self):
        old={s['id']:s for s in self.session.base['payload']['slots']};new={s['id']:s for s in self.session.payload['slots']}
        self.details.setPlainText('\n'.join(identity+'\n原：'+str(old.get(identity))+'\n擬改：'+str(new.get(identity)) for identity in sorted(set(old)|set(new)) if old.get(identity)!=new.get(identity)) or '沒有幾何／語意變更')

    def save_or_raise(self):
        if self.visual.isChecked()!=bool(self.session.payload.get('visual_confirmed')):self.session.checkpoint();self.session.payload['visual_confirmed']=self.visual.isChecked()
        self.session.save();self.refresh();self.status.setText('標記／來源觀察草稿已保存，未核准事實或發布模板。')

    def save(self):self.guarded(self.save_or_raise)

    def confirm(self):
        def action():
            if not self.ids:raise ValueError('先選確切標記')
            self.save_or_raise();work=self.session.base;problems=analyse_work(work,self.library.source(work['source_id']))
            if any(p['severity']=='BLOCK' for p in problems):raise ValueError('作品仍有硬性標記問題：'+'；'.join(p['reason'] for p in problems if p['severity']=='BLOCK'))
            selected=[o for o in self.session.observations if o.get('slot_id') in self.ids]
            high=any(o['classification']=='LOGO' or (o.get('prior_prediction') and next(s for s in work['payload']['slots'] if s['id']==o['slot_id'])['kind'] in ('name','company')) for o in selected)
            if high and len(selected)>1:raise ValueError('來源身分／完整Logo等高風險標記需逐筆核對，先選單一框')
            if not self.visual.isChecked():raise ValueError('先核對原作品、物理尺寸與完整圖文')
            if QMessageBox.question(self,'只確認目前作品所選事實','\n'.join(o['text'] for o in selected)+'\n保留本版本先前已確認項目；不核准通用規則或發布。')!=QMessageBox.Yes:return
            record=self.session.store.facts(work['id']);self.session.store.confirm_facts(work['id'],[o['id'] for o in selected],record['revision'],record['pins'],self.session.store.source_proof(work['id']),'LOCAL_OPERATOR',True)
            self.session.facts=self.session.store.facts(work['id']);self.refresh()
            if hasattr(self.window,'schedule_affected_work'):self.window.schedule_affected_work(work['id'])
        self.guarded(action)

    def split(self):
        def action():
            value,ok=QInputDialog.getMultiLineText(self,'明確作品邊界／拆分','每行原來源毫米 x,y,w,h；所有既有框必須完整且唯一指派',text=','.join(str(self.session.payload['crop'][key]) for key in ('x','y','w','h')))
            if not ok:return
            regions=[Rect(*[float(v.strip()) for v in line.split(',')]) for line in value.splitlines() if line.strip()]
            if QMessageBox.question(self,'確認作品邊界候選','保留舊作品與原稿；新區域／來源觀察均重新待審。確認？')!=QMessageBox.Yes:return
            result=resegment(self.library,[self.session.base],regions,'LOCAL_OPERATOR','人工作品邊界校正',True);self.session=AnnotationSession(self.library,result[0]['id']);self.ids=[];self.refresh()
        self.guarded(action)

    def merge(self):
        def action():
            works=[w for w in self.library.artworks(self.session.base['source_id']) if w['id']!=self.session.base['id'] and w['payload'].get('segmentation_state')!='SUPERSEDED']
            if not works:raise ValueError('同來源沒有另一現行作品')
            labels=[w['name']+'／'+w['id'] for w in works];label,ok=QInputDialog.getItem(self,'選擇明確同一作品的區域','不同人物／公司保留獨立歸屬，不合併身分',labels,0,False)
            if not ok:return
            other=works[labels.index(label)];a=Rect(**self.session.base['payload']['crop']);b=Rect(**other['payload']['crop']);x,y=min(a.x,b.x),min(a.y,b.y);region=Rect(x,y,max(a.x+a.w,b.x+b.w)-x,max(a.y+a.h,b.y+b.h)-y)
            if QMessageBox.question(self,'確認作品合併範圍',label+'\n新區域保留獨立人物與完整Logo，舊作品保留歷史；新事實需重新核對。')!=QMessageBox.Yes:return
            result=resegment(self.library,[self.session.base,other],[region],'LOCAL_OPERATOR','人工同來源區域合併',True);self.session=AnnotationSession(self.library,result[0]['id']);self.ids=[];self.refresh()
        self.guarded(action)

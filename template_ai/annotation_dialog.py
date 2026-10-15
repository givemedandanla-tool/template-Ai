"""Direct source-canvas marking using the existing object canvas and facts store."""
from copy import deepcopy
from dataclasses import asdict
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QSplitter,QWidget,QLabel,QPushButton,QComboBox,
    QTableWidget,QTableWidgetItem,QPlainTextEdit,QLineEdit,QDoubleSpinBox,QCheckBox,QMessageBox,QInputDialog,QListWidget,QListWidgetItem,QTreeWidget,QTreeWidgetItem)
from .annotations import AnnotationSession,resegment
from .object_dialog import ObjectCanvas,canvas_controls
from .gui import Box,Canvas
from .model import Slot,Rect,KINDS
from .batch_import import healthy_source
from .training_quality import analyse_work


class AnnotationDialog(QDialog):
    def __init__(self,window,work_id,parent=None):
        super().__init__(parent or window);self.window=window;self.library=window.library;self.session=AnnotationSession(self.library,work_id);self.ids=[];self.loading=False;self.form_drafts={};self.form_key=None;self.form_baseline=None
        self.setWindowTitle('原作品直接標記／校正：只改學習中介資料');self.resize(1350,850)
        layout=QVBoxLayout(self);self.status=QLabel('作品邊界與欄位框不同；拖曳／改類型只存候選，明確確認才成作品事實。');self.status.setWordWrap(True);layout.addWidget(self.status)
        bar=QHBoxLayout()
        for label,fn in [('框選新增標記',lambda:self.canvas.set_mode('slot')),('選取／校正',lambda:self.canvas.set_mode('edit')),('視角平移',lambda:self.canvas.set_mode('pan')),('原稿／疊圖切換',self.toggle_overlay),('改前／改後比較',self.compare),('復原',self.undo),('重做',self.redo)]:self.button(bar,label,fn)
        layout.addLayout(bar);body=QSplitter();left=QWidget();left_layout=QVBoxLayout(left);self.index_mode=QComboBox();self.index_mode.addItems(['人物／公司語意樹','衍生來源結構（原生圖層未知）']);self.index_mode.currentIndexChanged.connect(self.rebuild_index);left_layout.addWidget(self.index_mode);self.index_tree=QTreeWidget();self.index_tree.setHeaderLabel('同一作品穩定物件／共享關聯');self.index_tree.setSelectionMode(QTreeWidget.ExtendedSelection);self.index_tree.itemSelectionChanged.connect(self.from_tree);left_layout.addWidget(self.index_tree,2);self.tree_nodes=[]
        self.objects=QListWidget();self.objects.setSelectionMode(QListWidget.ExtendedSelection);self.objects.itemSelectionChanged.connect(self.from_list);left_layout.addWidget(self.objects,1);body.addWidget(left)
        self.canvas=ObjectCanvas();self.canvas.selection_ids.connect(self.select);self.canvas.drag_proposal.connect(self.move);self.canvas.rectangle.connect(self.add);body.addWidget(self.canvas)
        self.canvas.preview_proposal.connect(self.preview_move);layout.addWidget(canvas_controls(self.canvas,self.library))
        panel=QWidget();form=QVBoxLayout(panel);self.kind=QComboBox()
        for key,value in KINDS.items():self.kind.addItem(value,key)
        self.owner=QLineEdit('p1');self.owner.setPlaceholderText('人物p1／公司c1，需核對真實歸屬');self.value=QLineEdit();self.value.setMaxLength(512)
        form.addWidget(QLabel('欄位類型 → 人物／公司歸屬 → 來源內容'));form.addWidget(self.kind);form.addWidget(self.owner);form.addWidget(self.value)
        self.coords=[]
        for key in ('x','y','w','h'):
            form.addWidget(QLabel(key+' mm'));spin=QDoubleSpinBox();spin.setRange(-2000,2000);spin.setDecimals(4);self.coords.append(spin);form.addWidget(spin)
        for label,fn in [('將待審文字映射為所選類型',self.bind_observation),('套用此框屬性草稿',self.apply_properties),('刪除選定標記草稿',self.delete),('放棄未套用屬性',self.discard_forms),('所選來源觀察／剔除雜訊',self.noise_context),('保存草稿（未確認）',self.save),('確認所選作品事實',self.confirm),('拒絕所選候選',lambda:self.review_markers('REJECTED')),('疑義隔離所選',lambda:self.review_markers('QUARANTINED')),('恢復所選待確認',lambda:self.review_markers('HUMAN_PENDING_CONFIRMATION')),('改正作品邊界／拆分',self.split),('合併同來源明確作品',self.merge)]:
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
        self.cache_form()
        selection=list(self.ids)+(['observation:'+self.observation_id] if getattr(self,'observation_id',None) else [])
        self.loading=True;payload=self.session.payload;source=self.library.source(self.session.base['source_id']);image=None
        if healthy_source(source):
            original=QImage(source['image']);crop=payload['crop'];image=original.copy(QRectF(crop['x']*original.width()/source['width_mm'],crop['y']*original.height()/source['height_mm'],crop['w']*original.width()/source['width_mm'],crop['h']*original.height()/source['height_mm']).toAlignedRect())
        self.objects.clear();slots=[Slot(**{**s,'rect':Rect(**s['rect'])}) for s in payload['slots']]
        confirmed=set((self.session.facts.get('confirmation') or {}).get('observation_ids',[]));by_slot={o.get('slot_id'):o for o in self.session.observations}
        for slot in slots:
            observation=by_slot.get(slot.id,{});state='已確認' if observation.get('id') in confirmed else observation.get('review',{}).get('state','候選／待核對')
            item=QListWidgetItem(slot.owner+'／'+KINDS.get(slot.kind,slot.kind)+'／'+state);item.setData(Qt.UserRole,slot.id);item.setToolTip(slot.id);self.objects.addItem(item)
        for observation in self.session.observations:
            if observation.get('slot_id') is None:
                item=QListWidgetItem('待審文字／'+observation['text'][:60]);item.setData(Qt.UserRole,'observation:'+observation['id']);self.objects.addItem(item)
        self.canvas.set_content(payload['work_width'],payload['work_height'],image,slots,crop=Rect(0,0,payload['work_width'],payload['work_height']));self.canvas.set_mode('edit')
        self.visual.setChecked(bool(payload.get('visual_confirmed')));self.loading=False;self.rebuild_index();valid={s.id for s in slots}|{'observation:'+o['id'] for o in self.session.observations if o.get('slot_id') is None};self.select([i for i in selection if i in valid])

    def showEvent(self,event):super().showEvent(event);self.canvas.fit()

    def from_list(self):
        if not self.loading:self.select([item.data(Qt.UserRole) for item in self.objects.selectedItems()])

    def rebuild_index(self,*_):
        from .object_index import semantic_index,source_structure
        selected=list(self.ids)+(['observation:'+self.observation_id] if getattr(self,'observation_id',None) else [])
        was_loading=self.loading;self.loading=True;self.index_tree.clear();self.tree_nodes=[]
        nodes=semantic_index(self.session.payload) if self.index_mode.currentIndex()==0 else source_structure(self.library.source(self.session.base['source_id']),self.session.payload)['nodes']
        nodes=list(nodes)+[dict(label='待審來源文字（不猜身分）',ids=[],children=[dict(label=o['text'][:80],ids=['observation:'+o['id']],children=[]) for o in self.session.observations if o.get('slot_id') is None])]
        def add(node,parent=None):
            item=QTreeWidgetItem([node['label']]);ids=set(node.get('ids',[]))
            for child in node.get('children',[]):ids.update(add(child,item))
            item.setData(0,Qt.UserRole,sorted(ids));self.tree_nodes.append(item)
            if parent is None:self.index_tree.addTopLevelItem(item)
            else:parent.addChild(item)
            return ids
        for node in nodes:add(node)
        self.index_tree.expandToDepth(1);self.loading=was_loading
        if not self.loading:self.select(selected)

    def from_tree(self):
        if not self.loading:self.select(sorted({identity for item in self.index_tree.selectedItems() for identity in item.data(0,Qt.UserRole) or []}))

    def select(self,ids):
        if self.loading:return
        self.cache_form()
        valid={s['id'] for s in self.session.payload['slots']}|{'observation:'+o['id'] for o in self.session.observations if o.get('slot_id') is None}
        ids=[identity for identity in ids if identity in valid]
        self.observation_id=next((i.split(':',1)[1] for i in ids if i.startswith('observation:')),None)
        self.ids=[i for i in ids if not i.startswith('observation:')];self.loading=True;self.canvas.select_ids(self.ids)
        for i in range(self.objects.count()):self.objects.item(i).setSelected(self.objects.item(i).data(Qt.UserRole) in ids)
        for item in self.tree_nodes:
            node_ids=item.data(0,Qt.UserRole) or [];item.setSelected(bool(node_ids) and set(node_ids)<=set(ids))
        self.loading=False
        if self.observation_id:
            observation=next(o for o in self.session.observations if o['id']==self.observation_id);self.value.setText(observation['text']);self.details.setPlainText('來源文字尚無可靠欄位映射；請選類型與歸屬再建立框。\n'+self.semantic_details(observation));self.restore_form(ids);return
        if len(ids)==1:
            slot=next(s for s in self.session.payload['slots'] if s['id']==ids[0]);self.kind.setCurrentIndex(self.kind.findData(slot['kind']));self.owner.setText(slot['owner'])
            observation=next((o for o in self.session.observations if o.get('slot_id')==ids[0]),None);self.value.setText(observation['text'] if observation else '')
            for spin,key in zip(self.coords,('x','y','w','h')):spin.setValue(slot['rect'][key])
            self.details.setPlainText(str(observation.get('review',{}))+'\n'+f"作品 {self.session.base['id']}／來源 {self.session.base['source_id']}\n框 {ids[0]}／{slot['owner']}\n標記字型：{slot['font']}／{slot.get('font_style') or '款式未知'}／{slot['size_pt']}pt（標記值，原稿字型仍待核對）\n原生Illustrator對應未知；AI線索不等於真值。\n"+self.semantic_details(observation))
        else:self.details.setPlainText(f'明確選取{len(ids)}框。多選只允許適用操作，不以首框值覆蓋共同屬性。')

        self.restore_form(ids)

    def form_values(self):return dict(kind=self.kind.currentData(),owner=self.owner.text(),text=self.value.text(),coords=[spin.value() for spin in self.coords])

    def cache_form(self):
        if self.form_key is not None and self.form_baseline is not None:
            value=self.form_values()
            if value!=self.form_baseline:self.form_drafts[self.form_key]=value
            else:self.form_drafts.pop(self.form_key,None)

    def restore_form(self,ids):
        self.form_key=tuple(ids) if len(ids)==1 else None;self.form_baseline=self.form_values()
        if self.form_key in self.form_drafts:
            value=self.form_drafts[self.form_key];self.kind.setCurrentIndex(self.kind.findData(value['kind']));self.owner.setText(value['owner']);self.value.setText(value['text'])
            for spin,number in zip(self.coords,value['coords']):spin.setValue(number)

    def discard_forms(self):
        self.form_key=None;self.form_drafts.clear();self.refresh();self.status.setText('已放棄未套用屬性；已套用的標記草稿仍保留。')

    def noise_context(self):
        def action():
            self.require_saved()
            ids=[o['id'] for o in self.session.observations if o.get('slot_id') in self.ids or o['id']==self.observation_id]
            if not ids:raise ValueError('先選明確來源觀察')
            from .training_quality_dialog import TrainingQualityDialog
            dialog=TrainingQualityDialog(self.window);dialog.tabs.setCurrentWidget(dialog.facts_panel);dialog.facts_panel.focus(self.session.base['id'],ids)
            dialog.exec();dialog.deleteLater();self.session=AnnotationSession(self.library,self.session.base['id']);self.refresh()
        self.guarded(action)

    def semantic_details(self,observation):
        if not observation:return '待補來源觀察'
        from .semantic_fields import recognize,TYPE_LABELS
        row=recognize(observation['text'])
        prior=self.session.base['payload'].get('analysis_evidence',{});candidate=prior.get('semantic_candidates',{}).get(observation['id'])
        history=''
        if candidate:history='\n來源分析時的AI候選：'+candidate['semantic_type']+'；模型：'+str(prior.get('semantic_model',{}))+'；依據：'+'；'.join(candidate['signals'])
        return observation['text']+'\n目前內容語意候選：'+TYPE_LABELS[row['semantic_type']]+'（'+row['semantic_type']+'）／平台：'+str(row['platform'])+'\n正規化：'+row['normalized']+'\n判斷依據：'+'；'.join(row['signals'])+'\n'+row['confidence']+'／'+row['version']+history

    def reject(self):
        self.cache_form()
        changed=bool(self.form_drafts) or self.session.payload!=self.session.base['payload'] or self.session.observations!=self.session.facts['observations'] or self.visual.isChecked()!=bool(self.session.payload.get('visual_confirmed'))
        if changed:
            answer=QMessageBox.question(self,'保留標記草稿','目前有未保存的標記校正。',QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel,QMessageBox.Cancel)
            if answer==QMessageBox.Cancel:return
            if answer==QMessageBox.Save:
                try:self.save_or_raise()
                except Exception as error:self.status.setText('未關閉：'+str(error));return
        super().reject()

    def review_markers(self,state):
        def action():
            selected=[o['id'] for o in self.session.observations if o.get('slot_id') in self.ids or o['id']==self.observation_id]
            if not selected:raise ValueError('先選確切標記；不擴大到整作品或其他來源')
            reason,ok=QInputDialog.getText(self,'標記審核草稿 '+state,'理由（保存草稿後持久化；未核准學習）：')
            if ok:self.session.review(selected,state,reason);self.refresh()
        self.guarded(action)

    def bind_observation(self):
        def action():
            if not self.observation_id:raise ValueError('先選左側待審文字')
            self.ids=[self.session.bind_observation(self.observation_id,self.kind.currentData(),self.owner.text())];self.form_drafts.pop(self.form_key,None);self.form_key=None;self.refresh()
        self.guarded(action)

    def move(self,request):
        def action():self.session.change(dict(request,cross_owner=len({s['owner'] for s in self.session.payload['slots'] if s['id'] in request['ids']})<=1));self.refresh()
        self.guarded(action)

    def preview_move(self,request):
        try:
            from .object_tools import propose
            plan=propose(self.session.payload,'ARTWORK',request);self.canvas.show_preview(plan);self.status.setText('僅預覽，未改標記：'+'；'.join(plan['warnings']))
        except Exception as error:self.status.setText('未套用：'+str(error))

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
            self.form_drafts.pop(self.form_key,None);self.form_key=None;self.refresh()
        self.guarded(action)

    def delete(self):self.guarded(lambda:(self.session.change(dict(operation='DELETE',ids=self.ids)),self.refresh()))
    def undo(self):self.session.undo();self.refresh()
    def redo(self):self.session.redo();self.refresh()

    def toggle_overlay(self):
        self.overlay=not self.overlay;self.canvas.resetting=True
        for item in self.canvas.scene().items():
            if isinstance(item,Box):item.setVisible(self.overlay)
        self.canvas.resetting=False;self.status.setText('原稿檢視；選取保留、資料驗證仍涵蓋全部框' if not self.overlay else '作品邊界為橘色虛線，資料標記為藍框；來源未修改')
        if self.overlay:self.canvas.select_ids(self.ids)

    def compare(self):
        def action():
            from .annotation_compare import build_annotation_comparison
            from .comparison_view import CanvasCompareDialog
            self.comparison=CanvasCompareDialog(build_annotation_comparison(self.session),self)
            self.comparison.selection_changed.connect(lambda identity:self.select([identity]))
            self.comparison.open()
            if self.ids:self.comparison.select_slot(self.ids[0])
        self.guarded(action)

    def save_or_raise(self):
        self.cache_form()
        if self.form_drafts:raise ValueError('仍有未套用屬性，先逐框套用或明確放棄；已保留輸入')
        if self.visual.isChecked()!=bool(self.session.payload.get('visual_confirmed')):self.session.checkpoint();self.session.payload['visual_confirmed']=self.visual.isChecked()
        self.session.save();self.refresh();self.status.setText('標記／來源觀察草稿已保存，未核准事實或發布模板。')

    def save(self):self.guarded(self.save_or_raise)

    def confirm(self):
        def action():
            if not self.ids:raise ValueError('先選確切標記')
            if self.observation_id:raise ValueError('選取包含未映射文字，先逐筆核對，不能靜默略過')
            self.save_or_raise();work=self.session.base;problems=analyse_work(work,self.library.source(work['source_id']))
            if any(p['severity']=='BLOCK' for p in problems):raise ValueError('作品仍有硬性標記問題：'+'；'.join(p['reason'] for p in problems if p['severity']=='BLOCK'))
            selected=[o for o in self.session.observations if o.get('slot_id') in self.ids]
            from .semantic_fields import recognize
            slots={s['id']:s for s in work['payload']['slots']};kinds={slots[o['slot_id']]['kind'] for o in selected};owners={slots[o['slot_id']]['owner'] for o in selected}
            high=any(o['classification']=='LOGO' or slots[o['slot_id']]['kind'] in ('name','company') or recognize(o['text'])['semantic_type']=='unknown' or any('矛盾' in s for s in recognize(o['text'])['signals']) for o in selected)
            if high and len(selected)>1:raise ValueError('來源身分／完整Logo等高風險標記需逐筆核對，先選單一框')
            if len(selected)>1 and (len(kinds)!=1 or len(owners)!=1):raise ValueError('低風險批次限同類型、相同明確歸屬與來源；混合條件需逐筆核對')
            if not self.visual.isChecked():raise ValueError('先核對原作品、物理尺寸與完整圖文')
            if QMessageBox.question(self,'只確認目前作品所選事實','\n'.join(o['text'] for o in selected)+'\n保留本版本先前已確認項目；不核准通用規則或發布。')!=QMessageBox.Yes:return
            record=self.session.store.facts(work['id']);self.session.store.confirm_facts(work['id'],[o['id'] for o in selected],record['revision'],record['pins'],self.session.store.source_proof(work['id']),'LOCAL_OPERATOR',True)
            self.session.facts=self.session.store.facts(work['id']);self.refresh()
            if hasattr(self.window,'schedule_affected_work'):self.window.schedule_affected_work(work['id'])
        self.guarded(action)

    def split(self):
        def action():
            self.require_saved()
            from .work_overview_dialog import SourceRegionsDialog
            dialog=SourceRegionsDialog(self.library,self.session.base,self)
            try:
                if dialog.exec()!=QDialog.Accepted:return
                regions=list(dialog.regions)
            finally:dialog.deleteLater()
            if QMessageBox.question(self,'確認作品邊界候選','保留舊作品與原稿；新區域／來源觀察均重新待審。確認？')!=QMessageBox.Yes:return
            result=resegment(self.library,[self.session.base],regions,'LOCAL_OPERATOR','人工作品邊界校正',True);self.session=AnnotationSession(self.library,result[0]['id']);self.ids=[];self.refresh()
        self.guarded(action)

    def merge(self):
        def action():
            self.require_saved()
            works=[w for w in self.library.artworks(self.session.base['source_id']) if w['id']!=self.session.base['id'] and w['payload'].get('segmentation_state')!='SUPERSEDED']
            if not works:raise ValueError('同來源沒有另一現行作品')
            labels=[w['name']+'／'+w['id'] for w in works];label,ok=QInputDialog.getItem(self,'選擇明確同一作品的區域','不同人物／公司保留獨立歸屬，不合併身分',labels,0,False)
            if not ok:return
            other=works[labels.index(label)];a=Rect(**self.session.base['payload']['crop']);b=Rect(**other['payload']['crop']);x,y=min(a.x,b.x),min(a.y,b.y);region=Rect(x,y,max(a.x+a.w,b.x+b.w)-x,max(a.y+a.h,b.y+b.h)-y)
            if QMessageBox.question(self,'確認作品合併範圍',label+'\n新區域保留獨立人物與完整Logo，舊作品保留歷史；新事實需重新核對。')!=QMessageBox.Yes:return
            result=resegment(self.library,[self.session.base,other],[region],'LOCAL_OPERATOR','人工同來源區域合併',True);self.session=AnnotationSession(self.library,result[0]['id']);self.ids=[];self.refresh()
        self.guarded(action)

    def require_saved(self):
        self.cache_form()
        if self.form_drafts:raise ValueError('未套用屬性仍保留，請先套用或放棄')
        if self.session.payload!=self.session.base['payload'] or self.session.observations!=self.session.facts['observations'] or self.visual.isChecked()!=bool(self.session.payload.get('visual_confirmed')):
            raise ValueError('有未保存標記；先保存或明確撤回，不能由作品邊界校正丟棄')

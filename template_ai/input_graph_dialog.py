"""人物 ROOT 卡片與共享資料；只有採用才修改當次輸入。"""
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QSplitter,
    QTreeWidget,QTreeWidgetItem,QScrollArea,QWidget,QGroupBox,QLineEdit,QComboBox,
    QInputDialog,QMessageBox,QDialogButtonBox,QListWidget,QListWidgetItem,QPlainTextEdit,QTabWidget)
from .input_graph import InputGraph, CONTACT_KINDS
from .model import KINDS
from shiboken6 import isValid


class InputGraphDialog(QDialog):
    def __init__(self,window,graph=None):
        super().__init__(window);self.window=window;self.rebuilding=False;self.collapsed=set();self.selected_id=None
        history=None
        if graph is None:
            current=getattr(window,'active_input_graph',None)
            if current:graph=current.data;history=current
            else:
                p,c,l=window.input_data();graph=InputGraph.from_legacy(p,c,l).data
        self.graph=history.clone() if history is not None else InputGraph(graph);self.initial_revision=self.graph.data["revision"]
        from copy import deepcopy
        self.initial_graph=deepcopy(self.graph.data)
        from .logo_store import LogoStore
        self.logo_store=LogoStore(window.library)
        self.setWindowTitle('人物卡片／公司與共享聯絡資料（當次製作）');self.resize(1180,780)
        layout=QVBoxLayout(self)
        source=getattr(window,'reorder_customer_snapshot',None)
        origin=('客戶 '+source['code']+'／主檔 v'+str(source['revision'])+' 的當次複本') if source else '當次輸入'
        self.status=QLabel('資料來源：'+origin+'。可先在這裡修改，按「使用這些資料」才會帶回稿件；客戶原資料保持不變。');self.status.setTextFormat(Qt.PlainText);self.status.setWordWrap(True);layout.addWidget(self.status)
        bar=QHBoxLayout();self.add_button(bar,'＋新增人物',lambda:self.execute('add_person'));self.undo_button=self.add_button(bar,'復原',self.undo);self.redo_button=self.add_button(bar,'重做',self.redo);layout.addLayout(bar)
        split=QSplitter();self.tree=QTreeWidget();self.tree.setHeaderLabels(['人物、公司與聯絡資料']);self.tree.currentItemChanged.connect(self.navigate);split.addWidget(self.tree)
        self.scroll=QScrollArea();self.scroll.setWidgetResizable(True);split.addWidget(self.scroll);split.setStretchFactor(1,3);layout.addWidget(split,1)
        self.summary=QLabel();self.summary.setWordWrap(True);layout.insertWidget(1,self.summary)
        self.problems=QListWidget();self.problems.setMaximumWidth(330);self.problems.itemClicked.connect(self.locate_warning);split.addWidget(self.problems)
        self.pending_input={};self.field_warnings={};self.field_locations={};self.warning_timer=QTimer(self);self.warning_timer.setSingleShot(True);self.warning_timer.timeout.connect(self.refresh_warnings)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);self.adopt_button=buttons.button(QDialogButtonBox.Ok);self.adopt_button.setText('使用這些資料');buttons.button(QDialogButtonBox.Cancel).setText('取消這次修改');buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.technical_group=QGroupBox('顯示詳細資料（進階核對）');self.technical_group.setCheckable(True);self.technical_group.setChecked(False);self.technical_group.setAccessibleName('進階資料對應與變更影響')
        group_layout=QVBoxLayout(self.technical_group);self.technical_body=QWidget();technical_layout=QVBoxLayout(self.technical_body);technical_layout.setContentsMargins(0,0,0,0)
        self.technical_tabs=QTabWidget();self.technical_tabs.setMaximumHeight(155);technical_layout.addWidget(self.technical_tabs)
        self.identity_details=QPlainTextEdit();self.identity_details.setReadOnly(True);self.identity_details.setAccessibleName('穩定身分、模板位置與欄位歸屬的技術詳情');self.technical_tabs.addTab(self.identity_details,'資料對應')
        logo_details_scroll=QScrollArea();logo_details_scroll.setWidgetResizable(True)
        self.logo_state_details=QLabel();self.logo_state_details.setWordWrap(True);self.logo_state_details.setTextFormat(Qt.PlainText);self.logo_state_details.setTextInteractionFlags(Qt.TextSelectableByMouse|Qt.TextSelectableByKeyboard);self.logo_state_details.setAccessibleName('各公司圖片的完整狀態代碼')
        logo_details_scroll.setWidget(self.logo_state_details);self.technical_tabs.addTab(logo_details_scroll,'圖片狀態')
        self.source_impacts=QPlainTextEdit();self.source_impacts.setReadOnly(True);self.source_impacts.setMaximumHeight(130);self.source_impacts.setPlaceholderText('目前沒有來源差異；採用任何來源操作版本後，舊候選仍須重新核對。');self.technical_tabs.addTab(self.source_impacts,'共用資料變更影響')
        group_layout.addWidget(self.technical_body);self.technical_body.setVisible(False);self.technical_group.toggled.connect(self.technical_body.setVisible);layout.insertWidget(2,self.technical_group)
        self.field_editors={};self.cards={};self.rebuild()

    def add_button(self,bar,text,action):
        b=QPushButton(text);b.clicked.connect(action);bar.addWidget(b);return b

    def execute(self,action,**params):
        # Qt can emit editingFinished while destroying the owner window.
        # Do not rebuild a draft or inspect consumers after that lifetime.
        if not isValid(self) or not isValid(self.window):return False
        if self.rebuilding:return False
        if any(len(value)>2048 for value in self.pending_input.values()):
            self.status.setText('有一欄資料過長，原文仍保留在輸入框。請先縮短或另存原文，再使用這些資料。');self.refresh_warnings();return False
        try:
            plan=self.graph.make_plan(action,**params)
            if plan['requires_confirmation']:
                impact='\n'.join(plan['labels']) or '僅新增資料'
                detail='這次修改可能同時影響共用這份資料的人物或公司。請先核對下列對象；選「否」會保留目前資料。\n\n'+f"操作：{action}\n實際受影響實體：\n{impact}\n引用ID："+', '.join(plan['affected'])+'\n資料來源：當次輸入；不改客戶主檔／原稿／Logo資產。'
                detail+='\n欄位變化：'
                for delta in plan['differences']:
                    old,new=delta['before'],delta['after'];field=new or old
                    detail+='\n'+KINDS[field['kind']]+'／'+field['owner_id']+'：'+('未有此欄位' if old is None else old['value'])+' → '+('刪除此欄位' if new is None else new['value'])
                detail+='\n實體／Logo引用變化：'+str(plan['entity_differences'])+'\n關聯變化：'+str(plan['link_changes'])+'\n操作後（人物／公司／欄位／關聯）：'+str(plan['result_counts'])
                if action=='edit_field':
                    old=self.graph.field(params['field_id']);detail+='\n舊值：'+old['value']+'\n新值：'+params['value']
                if action=='copy_person':detail+='\n私人欄位：獨立複本；公司：'+('連結既有共享實體' if params['company_mode']=='SHARED' else '公司與聯絡欄位建立獨立複本；Logo引用既有核准資產')
                if QMessageBox.question(self,'核對共享影響／移除結果',detail)!=QMessageBox.Yes:
                    self.rebuild();return False
            self.graph.apply(plan,approved=True)
            self.status.setText('已在這個視窗修改資料。按「使用這些資料」後，請更新稿件再確認。')
            self.rebuild();return True
        except (ValueError,KeyError,StopIteration,TypeError) as error:
            self.status.setText('未套用：'+str(error));return False

    def undo(self):
        if any(len(value)>2048 for value in self.pending_input.values()):
            self.status.setText('過長欄位原文仍保留，請先縮短或另存，再復原其他資料。');return
        if not self.graph.undo_stack:return
        if self.confirm_source_history(self.graph.undo_stack[-1],'復原'):self.graph.undo();self.rebuild()

    def redo(self):
        if any(len(value)>2048 for value in self.pending_input.values()):
            self.status.setText('過長欄位原文仍保留，請先縮短或另存，再重做其他資料。');return
        if not self.graph.redo_stack:return
        if self.confirm_source_history(self.graph.redo_stack[-1],'重做'):self.graph.redo();self.rebuild()

    def confirm_source_history(self,target,action):
        from .source_change_impact import consumers,source_change_impact,describe
        try:rows=source_change_impact(consumers(self.window),self.graph.data,target)
        except ValueError as error:self.status.setText('未'+action+'：'+str(error));return False
        if not rows:return True
        dialog=QDialog(self);dialog.setWindowTitle(action+'共用來源／實際引用範圍');box=QVBoxLayout(dialog);label=QLabel(action+'這次來源變更將影響下列'+str(len(rows))+'份引用作品。只先修改目前草稿，採用後才同步當次來源；各作品人工位置保留，仍須各尺寸完整重驗。');label.setWordWrap(True);box.addWidget(label);details=QPlainTextEdit(describe(rows));details.setReadOnly(True);box.addWidget(details);buttons=QDialogButtonBox(QDialogButtonBox.Yes|QDialogButtonBox.No);buttons.button(QDialogButtonBox.No).setDefault(True);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);box.addWidget(buttons);dialog.resize(950,620)
        try:return dialog.exec()==QDialog.Accepted
        finally:dialog.deleteLater()

    def navigate(self,item,previous=None):
        if not item:return
        eid=item.data(0,Qt.UserRole);self.selected_id=eid
        card=self.cards.get(eid)
        if card:self.scroll.ensureWidgetVisible(card)
        editor=self.field_editors.get(eid)
        if editor:self.scroll.ensureWidgetVisible(editor);editor.setFocus()

    def focus_field(self,field_id,entity_id=None):
        editor=self.field_locations.get((field_id,entity_id)) or self.field_editors.get(field_id)
        if editor is None:self.status.setText('欄位版本已改，無法推測位置');return False
        self.scroll.ensureWidgetVisible(editor);editor.setFocus();editor.selectAll();self.selected_id=field_id;return True

    def choose(self,title,entries):
        if not entries:self.status.setText('沒有適用對象；未變更資料');return None
        labels=[str(index+1)+'．'+name for index,(_,name) in enumerate(entries)]
        label,ok=QInputDialog.getItem(self,title,'請選擇要連結的對象。同名資料也可能是不同筆，請核對人物與公司。',labels,0,False)
        return entries[labels.index(label)][0] if ok and label in labels else None

    def add_company(self,pid):
        name,ok=QInputDialog.getText(self,'新增獨立公司','公司名稱（可稍後補齊）')
        if ok:self.execute('add_company',person_id=pid,name=name)

    def link_company(self,pid):
        cid=self.choose('連結既有公司',[(c['id'],self.graph.label(c['id'])) for c in self.graph.data['companies'] if [pid,c['id']] not in self.graph.data['links']])
        if cid:self.execute('link_company',person_id=pid,company_id=cid)

    def link_contact(self,eid):
        choices=[(f['id'],KINDS[f['kind']]+' · '+self.graph.label(f['owner_id'])+'（'+f['value']+'）') for f in self.graph.data['fields'] if f['kind'] in CONTACT_KINDS and eid not in f['users']]
        fid=self.choose('連結同一份聯絡資料',choices)
        if fid:self.execute('link_field',field_id=fid,entity_id=eid)

    def copy_person(self,pid):
        mode,ok=QInputDialog.getItem(self,'複製人物：私人欄位一律獨立','公司與公司聯絡資料如何處理？',['連結既有共享公司','建立獨立公司複本'],0,False)
        if ok:self.execute('copy_person',person_id=pid,company_mode='SHARED' if mode=='連結既有共享公司' else 'INDEPENDENT')

    def field_row(self,layout,f,eid):
        row=QHBoxLayout();label=QLabel('公司名稱' if f['kind']=='name' and eid in {c['id'] for c in self.graph.data['companies']} else KINDS[f['kind']]);label.setMinimumWidth(50);row.addWidget(label)
        editor=QLineEdit(f['value']);editor.setMaxLength(2147483647);editor.setObjectName('input-field-'+f['id']);row.addWidget(editor,1)
        editor.setToolTip('這份資料屬於：'+self.graph.label(f['owner_id'])+'。共用資料修改時會先提示影響；詳細對應可在上方展開查看。')
        def commit():
            if not self.rebuilding and editor.text()!=self.graph.field(f['id'])['value']:
                if len(editor.text())>2048:
                    self.pending_input[f['id']]=editor.text();self.refresh_warnings();return
                self.execute('edit_field',field_id=f['id'],value=editor.text())
        editor.editingFinished.connect(commit);self.field_editors.setdefault(f['id'],editor);self.field_locations[(f['id'],eid)]=editor
        editor.textEdited.connect(lambda value,fid=f['id']:(self.pending_input.__setitem__(fid,value),self.warning_timer.start(180)))
        impact=self.graph.field_impact(f['id'])
        shared=len(impact)>1
        marker=QLabel(('共享：'+'／'.join(self.graph.label(x) for x in impact)) if shared else '獨立');marker.setTextFormat(Qt.PlainText);row.addWidget(marker)
        if f['owner_id']!=eid:
            self.add_button(row,'不再共用這筆資料',lambda:self.execute('unlink_field',field_id=f['id'],entity_id=eid))
            self.add_button(row,'另外保存一份',lambda:self.execute('independent_field',field_id=f['id'],entity_id=eid))
        if f['kind'] in CONTACT_KINDS:self.add_button(row,'複製成新資料',lambda:self.execute('copy_field',field_id=f['id'],owner_id=eid))
        if f['owner_id']==eid and f['kind']!='name':self.add_button(row,'刪除這筆資料',lambda:self.execute('delete_field',field_id=f['id']))
        layout.addLayout(row)
        warning=QLabel();warning.setWordWrap(True);warning.setStyleSheet('color:#9a3412');layout.addWidget(warning);self.field_warnings.setdefault(f['id'],[]).append(warning)

    def entity_fields(self,layout,eid):
        for f in self.graph.data['fields']:
            if eid in f['users']:self.field_row(layout,f,eid)
        row=QHBoxLayout();kind=QComboBox()
        allowed=(('title',)+CONTACT_KINDS) if eid in {p['id'] for p in self.graph.data['people']} and not any(f['kind']=='title' and f['owner_id']==eid for f in self.graph.data['fields']) else CONTACT_KINDS
        for k in allowed:kind.addItem('＋新增'+KINDS[k],k)
        row.addWidget(kind);self.add_button(row,'新增所選欄位',lambda:self.execute('add_field',owner_id=eid,kind=kind.currentData()))
        self.add_button(row,'連結既有共享聯絡資料',lambda:self.link_contact(eid));layout.addLayout(row)

    def company_card(self,parent,cid,pid=None):
        refs=[p for p,c in self.graph.data['links'] if c==cid]
        box=QGroupBox('公司：'+self.graph.label(cid)+'\n共用這家公司的人物：'+('／'.join(self.graph.label(x) for x in refs) or '尚無人物使用（仍保留公司與圖片）'))
        parent.addWidget(box);v=QVBoxLayout(box);self.entity_fields(v,cid);self.cards.setdefault(cid,box)
        row=QHBoxLayout();row.addWidget(QLabel('這個尺寸使用的公司圖片'));combo=QComboBox();combo.addItem('尚未選擇圖片','')
        c=self.graph.entity(cid);assets=self.window.library.logos()
        for number,a in enumerate(assets):
            binding=self.logo_store.db.execute('SELECT company_id FROM logo_entity_bindings WHERE entity_id=?',(cid,)).fetchone()
            managed_allowed=not a.get('managed_logo') or (binding and a.get('company_id')==binding[0])
            if a.get('approved') and managed_allowed and a['company']==self.graph.label(cid) and abs(a['width_mm']-self.window.out_w.value())<1e-5 and abs(a['height_mm']-self.window.out_h.value())<1e-5:combo.addItem(a['company']+' · 圖片 '+str(number+1),a['id'])
        found=combo.findData(c['logo_id'])
        if found<0 and c['logo_id']:combo.addItem('既有引用失聯／非目前尺寸（須重新核對）',c['logo_id']);found=combo.count()-1
        combo.setCurrentIndex(max(0,found));combo.currentIndexChanged.connect(lambda:self.execute('edit_logo',company_id=cid,logo_id=combo.currentData()))
        row.addWidget(combo,1);v.addLayout(row);row=QHBoxLayout()
        match=self.logo_store.match(cid,self.graph.label(cid),self.window.out_w.value(),self.window.out_h.value(),selected_id=c['logo_id'] or None)
        self.logo_states[cid]=dict(state=match['state'],reason=match['reason'])
        logo_messages={'IDENTITY_REVIEW_REQUIRED':'請先核對這張圖片確實屬於這家公司。','SELECTION_INVALID':'原選圖片目前無法使用，請重新查看與選擇。','SELECTED_PENDING_OUTPUT_CHECK':'已選擇圖片，產生稿件後還要檢查輸出。','SINGLE_PREVIEW':'找到一個可預覽版本，仍要確認使用及檢查輸出。','MULTIPLE_REVIEW_REQUIRED':'有多個可用版本，請比較後選擇。','MISSING':'這個尺寸還沒有合格圖片；可以先填資料，輸出前需補齊。'}
        status=QLabel(f"卡片尺寸 {self.window.out_w.value():g}×{self.window.out_h.value():g} mm："+logo_messages.get(match['state'],'圖片狀況仍需核對。'));status.setTextFormat(Qt.PlainText);status.setWordWrap(True);v.addWidget(status)
        self.add_button(row,'選擇 Logo',lambda:self.choose_logo(cid));self.add_button(row,'匯入新 Logo',lambda:self.open_logo_library(cid,True));self.add_button(row,'查看審核狀態',lambda:self.open_logo_library(cid,False));v.addLayout(row);row=QHBoxLayout()
        if pid:
            self.add_button(row,'解除此人物公司關聯',lambda:self.execute('unlink_company',person_id=pid,company_id=cid))
            self.add_button(row,'此人物改用獨立公司複本',lambda:self.execute('independent_company',person_id=pid,company_id=cid))
        self.add_button(row,'刪除公司實體（引用中會阻擋）',lambda:self.execute('delete_company',company_id=cid));v.addLayout(row)
        return box

    def choose_logo(self,cid):
        from .logo_choice_dialog import LogoChoiceDialog
        dialog=LogoChoiceDialog(self.window,self.graph,cid,self)
        if dialog.exec()==QDialog.Accepted and dialog.selected_asset:
            self.execute('edit_logo',company_id=cid,logo_id=dialog.selected_asset['id'])

    def open_logo_library(self,cid,import_new):
        from .logo_library_dialog import LogoLibraryDialog
        dialog=LogoLibraryDialog(self.window)
        dialog.query.setText(self.graph.label(cid));dialog.views.setCurrentIndex(2 if import_new else 1)
        binding=self.logo_store.db.execute('SELECT company_id FROM logo_entity_bindings WHERE entity_id=?',(cid,)).fetchone()
        if binding:dialog.company.setCurrentIndex(max(0,dialog.company.findData(binding[0])))
        if import_new:dialog.manual_import()
        dialog.exec();self.rebuild()

    def refresh_warnings(self):
        import sqlite3
        try:self.window.library.db.execute('SELECT 1')
        except sqlite3.ProgrammingError:self.warning_timer.stop();self.summary.setText('本機資料庫已關閉，輸入檢查已停止；未宣稱通過');return
        try:
            from .input_diagnostics import diagnose
            preview=InputGraph(self.graph.data)
            overlong=[]
            for field in preview.data['fields']:
                if field['id'] in self.pending_input:
                    value=self.pending_input[field['id']]
                    if len(value)>2048:overlong.append(field)
                    else:field['value']=value
            model_id=None;learning_summary=None
            if getattr(self.window,'session_id',None) and hasattr(self.window,'sessions'):
                model_id=self.window.sessions.current(self.window.session_id)['model_id']
            from .production_report import input_advice
            advice=input_advice(self.window.library,preview,self.window.out_w.value(),self.window.out_h.value(),model_id)
            learning_summary=advice['summary'] if advice['status']!='NO_ACTIVE_MODEL' else None
            people,companies,_=preview.compile(self.window.library.logos());report=diagnose(people,companies,[] if learning_summary else self.window.library.templates(True),self.window.out_w.value(),self.window.out_h.value());self.warning_report=report
            if learning_summary:report['learning_advice']=advice
            for field in overlong:
                report['issues'].append(dict(owner=self.graph.label(field['owner_id']),entity_id=field['owner_id'],field_id=field['id'],code='INPUT_STORAGE_LIMIT',severity='WARNING',reason='這欄超過目前可保存的2048字元；原文完整保留，尚未採用。請縮短或另存原文。這不是版面學習所得的字數上限。'))
            self.adopt_button.setEnabled(not overlong)
            self.summary.setText(('有資料需要查看（預估風險，仍待版面確認）' if report['issues'] else '目前未發現輸入問題，仍需產生稿件檢查')+f"；{len(people)}位人物、{len(companies)}家公司、{len(report['issues'])}個提醒。")
            if learning_summary:self.summary.setText(('有資料需要查看；' if report['issues'] else '')+learning_summary)
            self.problems.clear()
            for issue in report['issues']:
                try:owner_name=self.graph.label(issue['entity_id']) if issue.get('entity_id') else issue['owner']
                except (KeyError,ValueError):owner_name=issue['owner']
                item=QListWidgetItem(owner_name+'／'+KINDS.get(issue.get('field_kind'),'共用資料')+'：'+issue['reason']);item.setData(Qt.UserRole,issue);self.problems.addItem(item)
            for fid,labels in self.field_warnings.items():
                text='\n'.join(issue['reason'] for issue in report['issues'] if issue.get('field_id')==fid)
                for label in labels:label.setText(text);label.setVisible(bool(text))
        except (ValueError,TypeError) as error:self.summary.setText('尚未完成輸入檢查：'+str(error))

    def accept(self):
        for field_id,editor in list(self.field_editors.items()):
            if len(editor.text())>2048:
                self.pending_input[field_id]=editor.text();self.refresh_warnings();return
        changes=[(fid,editor.text()) for fid,editor in self.field_editors.items() if editor.text()!=self.graph.field(fid)['value']]
        for fid,value in changes:
            if not self.execute('edit_field',field_id=fid,value=value):return
        super().accept()

    def locate_warning(self,item):
        issue=item.data(Qt.UserRole);editor=self.field_locations.get((issue.get('field_id'),issue.get('entity_id'))) or self.field_editors.get(issue.get('field_id'))
        if editor:self.selected_id=issue.get('field_id');self.scroll.ensureWidgetVisible(editor);editor.setFocus()

    def rebuild(self):
        self.rebuilding=True;self.tree.blockSignals(True)
        try:
            self.warning_timer.stop();self.pending_input={};self.field_warnings={};self.field_locations={};self.tree.clear();self.field_editors={};self.cards={};self.logo_states={}
            old=self.scroll.takeWidget()
            if old:
                for editor in old.findChildren(QLineEdit):editor.blockSignals(True)
                old.deleteLater()
            content=QWidget();v=QVBoxLayout(content)
            for n,p in enumerate(self.graph.data['people']):
                pid=p['id'];box=QGroupBox(f'人物卡片 {n+1}：'+self.graph.label(pid));box.setCheckable(True);box.setChecked(pid not in self.collapsed);body=QWidget();body_layout=QVBoxLayout(body);box_layout=QVBoxLayout(box);box_layout.addWidget(body);body.setVisible(pid not in self.collapsed)
                def collapse(checked,pid=pid,body=body):
                    body.setVisible(checked)
                    if checked:self.collapsed.discard(pid)
                    else:self.collapsed.add(pid)
                box.toggled.connect(collapse);v.addWidget(box);self.cards[pid]=box
                node=QTreeWidgetItem([f'人物 {n+1}：'+self.graph.label(pid)]);node.setData(0,Qt.UserRole,pid);self.tree.addTopLevelItem(node)
                self.entity_fields(body_layout,pid)
                row=QHBoxLayout();self.add_button(row,'＋新增公司',lambda checked=False,pid=pid:self.add_company(pid));self.add_button(row,'連結既有公司',lambda checked=False,pid=pid:self.link_company(pid));self.add_button(row,'複製人物資訊',lambda checked=False,pid=pid:self.copy_person(pid));self.add_button(row,'移除此人物',lambda checked=False,pid=pid:self.execute('delete_person',person_id=pid));body_layout.addLayout(row)
                for f in self.graph.data['fields']:
                    if pid in f['users']:
                        item=QTreeWidgetItem([KINDS[f['kind']]+' · '+('共用自 '+self.graph.label(f['owner_id']) if f['owner_id']!=pid else '個人資料')]);item.setData(0,Qt.UserRole,f['id']);node.addChild(item)
                for person,cid in self.graph.data['links']:
                    if person==pid:
                        self.company_card(body_layout,cid,pid);item=QTreeWidgetItem(['公司：'+self.graph.label(cid)]);item.setData(0,Qt.UserRole,cid);node.addChild(item)
            for c in self.graph.data['companies']:
                if not any(cid==c['id'] for _,cid in self.graph.data['links']):self.company_card(v,c['id'])
            v.addStretch(1);self.scroll.setWidget(content);self.tree.expandAll();self.undo_button.setEnabled(bool(self.graph.undo_stack));self.redo_button.setEnabled(bool(self.graph.redo_stack))
            self.refresh_warnings()
            details=['資料版次：'+str(self.graph.data['revision']),'模板 p1/c1 是位置代號；卡片 ROOT 與欄位 ID 保留穩定身分。']
            for index,person in enumerate(self.graph.data['people']):details.append('p'+str(index+1)+' → ROOT '+person['id']+'；'+self.graph.label(person['id']))
            for index,company in enumerate(self.graph.data['companies']):
                details.append('c'+str(index+1)+' → 公司 ID '+company['id']+'；Logo ID '+str(company.get('logo_id') or '未選取'))
                state=self.logo_states.get(company['id'],{});details.append('Logo 狀態 '+state.get('state','UNKNOWN')+'；'+state.get('reason','尚未核對'))
            for field in self.graph.data['fields']:details.append('欄位 ID '+field['id']+'；種類 '+field['kind']+'；所有者 '+field['owner_id']+'；使用者 '+', '.join(field['users']))
            self.identity_details.setPlainText('\n'.join(details))
            self.logo_state_details.setText('\n\n'.join(self.graph.label(company['id'])+'\n'+str(self.logo_states.get(company['id'],{}).get('state','UNKNOWN'))+'\n'+str(self.logo_states.get(company['id'],{}).get('reason','尚未核對')) for company in self.graph.data['companies']))
            from .source_change_impact import consumers,source_change_impact,describe
            try:self.source_impacts.setPlainText(describe(source_change_impact(consumers(self.window),self.initial_graph,self.graph.data)))
            except ValueError as error:self.source_impacts.setPlainText('來源影響待核對：'+str(error))
        finally:self.rebuilding=False;self.tree.blockSignals(False)

    def hideEvent(self,event):
        self.warning_timer.stop();super().hideEvent(event)

"""One customer entry backed by the existing Library connection."""
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLineEdit,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QPlainTextEdit,QMessageBox,QFileDialog,QInputDialog,QHeaderView,QComboBox
from .customers import CustomerStore

class CustomerDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.store=CustomerStore(window.library);self.snapshot=None;self.results=[]
        self.setWindowTitle('本機客戶／版型關聯與逐欄比對');self.resize(1000,720);layout=QVBoxLayout(self)
        self.status=QLabel('僅匿名研究資料；查詢不合併、不回寫；完整個資權限尚未完成。');self.status.setWordWrap(True);layout.addWidget(self.status)
        bar=QHBoxLayout();self.query=QLineEdit();self.query.setPlaceholderText('客戶編號／姓名／聯絡資訊（空查詢不載全庫）');bar.addWidget(self.query);self.query_kind=QComboBox()
        for label,value in [('全部欄位','ANY'),('客戶編號','CODE'),('人物／顯示名稱','NAME'),('電話（手機／私人）','PHONE'),('LINE','LINE'),('IG','IG'),('Email','EMAIL'),('公司','COMPANY')]:self.query_kind.addItem(label,value)
        bar.addWidget(self.query_kind);self.add_button(bar,'搜尋',self.search);self.add_button(bar,'將目前人物資料人工建檔',self.create);layout.addLayout(bar)
        self.customers=QTableWidget(0,3);self.customers.setMaximumHeight(135);self.customers.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.customers.setHorizontalHeaderLabels(['客戶編號','名稱','內部ID／版型數']);self.customers.setEditTriggers(QTableWidget.NoEditTriggers);self.customers.setSelectionBehavior(QTableWidget.SelectRows);self.customers.itemSelectionChanged.connect(self.select);layout.addWidget(self.customers)
        self.fields=QTableWidget(0,7);self.fields.setHorizontalHeaderLabels(['回寫（預設不選）','人物／公司／類型','快照原值','本次值（可編輯／清空）','stable欄位ID','目前主檔值','共享影響']);self.fields.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.fields.setColumnHidden(4,True);layout.addWidget(self.fields,2)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details)
        bar=QHBoxLayout();self.add_button(bar,'核對身份／瀏覽尺寸版型',self.browse_styles);self.add_button(bar,'快速文字選exact版型',self.prefill);self.add_button(bar,'比較選中欄位差異',self.preview);self.add_button(bar,'確認選中差異回寫',self.write);self.add_button(bar,'比較兩個客戶（不合併）',self.compare);layout.addLayout(bar)
        bar=QHBoxLayout();self.add_button(bar,'關聯另一確切尺寸／版型',self.link_style);self.add_button(bar,'查看並恢復已選欄位的歷史值',self.restore_history);self.add_button(bar,'完整圖差異／新增刪除共享同步',self.sync_graph);self.add_button(bar,'來源客戶候選／批次審核',self.source_candidates);layout.addLayout(bar)
        bar=QHBoxLayout();self.add_button(bar,'加密資料庫部分備份',self.backup);self.add_button(bar,'隔離還原到新目錄',self.restore);self.add_button(bar,'關閉',self.accept);layout.addLayout(bar)
        bar=QHBoxLayout();self.add_button(bar,'核對並撤銷來源／版型關聯',self.revoke_association);layout.addLayout(bar)
        self.identity_plan=None
        bar=QHBoxLayout();self.add_button(bar,'合併前完整影響預覽',self.preview_merge);self.add_button(bar,'合併歷史／拆分預覽',self.preview_split);self.add_button(bar,'確認目前身份方案',self.commit_identity);self.add_button(bar,'保留獨立／取消方案',self.cancel_identity);layout.addLayout(bar)
        bar=QHBoxLayout();self.add_button(bar,'記錄兩客戶保留獨立',lambda:self.review_identity('KEEP_SEPARATE'));self.add_button(bar,'記錄身份待審',lambda:self.review_identity('PENDING_REVIEW'));layout.addLayout(bar)

    def review_identity(self,state):
        def action():
            selected=sorted({i.row() for i in self.customers.selectedItems()})
            if len(selected)!=2:raise ValueError('Ctrl選取兩個獨立客戶')
            actor,ok=QInputDialog.getText(self,'身份處置記錄','核對者')
            if not ok:return
            reason,ok=QInputDialog.getText(self,'身份處置記錄','待審／保留獨立理由')
            if not ok:return
            result=self.identity_service().record_review(*(self.results[i]['id'] for i in selected),state,actor,reason)
            self.identity_plan=None;self.details.setPlainText(json.dumps(result,ensure_ascii=False));self.status.setText('身份處置已記錄；沒有合併、刪除或修改人物／來源')
        self.guarded(action)

    def identity_service(self):
        from .customer_identity import CustomerIdentity
        return CustomerIdentity(self.store)

    def cancel_identity(self):
        self.identity_plan=None;self.status.setText('已取消身份方案；本機主檔與來源關聯未變更')

    def preview_merge(self):
        def action():
            selected=sorted({i.row() for i in self.customers.selectedItems()})
            if len(selected)!=2:raise ValueError('Ctrl選取兩個獨立客戶；相同聯絡資料不代表同一身份')
            customers=[self.results[i] for i in selected]
            labels=[f"{c['code']} · {c['name']} · {c['id']}" for c in customers]
            chosen,ok=QInputDialog.getItem(self,'保留的主客戶ID','逐項核實人物／公司與來源，不合併不同人物實體',labels,0,False)
            if not ok:return
            primary=labels.index(chosen);a,b=customers[primary],customers[1-primary]
            code,ok=QInputDialog.getItem(self,'主要顯示編號','舊編號保留可搜尋別名',[a['code'],b['code']],0,False)
            if not ok:return
            self.identity_plan=self.identity_service().plan_merge(a['id'],b['id'],code)
            self.details.setPlainText(json.dumps(self.identity_plan,ensure_ascii=False,indent=2))
            self.status.setText('只讀合併預覽：核對全部人物／公司、欄位、來源、每尺寸版型與別名後，另按確認')
        self.guarded(action)

    def preview_split(self):
        def action():
            if not self.snapshot:raise ValueError('請先選目前主客戶')
            rows=[r for r in self.identity_service().history(self.snapshot['id']) if r['state']=='MERGED']
            if not rows:raise ValueError('沒有可拆分的合併記錄')
            labels=[r['id'] for r in rows]
            chosen,ok=QInputDialog.getItem(self,'合併歷史','檢查原A/B與合併後新修改；不以歷史值覆蓋新合法值',labels,0,False)
            if not ok:return
            self.identity_plan=self.identity_service().plan_split(chosen)
            self.details.setPlainText(json.dumps(self.identity_plan,ensure_ascii=False,indent=2))
            self.status.setText('只讀拆分預覽：保留目前可明確歸屬的新值；跨客戶共享或新歸屬不明時阻擋')
        self.guarded(action)

    def commit_identity(self):
        def action():
            if not self.identity_plan:raise ValueError('先取得完整合併／拆分影響預覽')
            actor,ok=QInputDialog.getText(self,'身份核准','核准者')
            if not ok:return
            reason,ok=QInputDialog.getText(self,'身份證據','核對理由；同名、同電話、同Logo、同bytes均不能單獨證明身份')
            if not ok:return
            if QMessageBox.question(self,'確認明列身份方案','已核對方案中的全部身份、歸屬、來源及版型？\n只執行這份方案；任何版本競爭會阻擋，不改原稿、發布版或既有輸出。')!=QMessageBox.Yes:return
            service=self.identity_service()
            result=(service.merge if self.identity_plan['operation']=='MERGE' else service.split)(self.identity_plan,True,actor,reason)
            self.identity_plan=None;self.details.setPlainText(json.dumps(result,ensure_ascii=False,indent=2));self.status.setText('身份方案已完成並通過關聯檢查；重新搜尋可核對主客戶及歷史別名')
        self.guarded(action)

    def revoke_association(self):
        def action():
            if not self.snapshot:raise ValueError('先選取客戶')
            from .customer_candidates import CustomerCandidates
            service=CustomerCandidates(self.store);rows=service.associations(self.snapshot['id'])
            if not rows:raise ValueError('所選客戶無來源建檔關聯')
            labels=[r['source_id']+'／作品'+r['artwork_id']+'／版型'+r['template_id'] for r in rows]
            label,ok=QInputDialog.getItem(self,'撤銷確切來源關聯','人物／聯絡資料保留，來源原稿不變',labels,0,False)
            if not ok:return
            choice,ok=QInputDialog.getItem(self,'撤銷範圍','確切版型關聯若仍有其他來源引用則阻擋',['只撤銷此來源關聯','同時移除此客戶的該版型關聯'],0,False)
            if not ok:return
            note,ok=QInputDialog.getText(self,'撤銷原因','保存必要最小稽核，不輸入多餘個資')
            if not ok:return
            if QMessageBox.question(self,'確認撤銷',self.snapshot['code']+'\n'+label+'\n'+choice+'\n'+note)!=QMessageBox.Yes:return
            self.snapshot=service.revoke_association(self.snapshot,rows[labels.index(label)]['id'],'LOCAL_OPERATOR',note,True,choice.startswith('同時'))
            if getattr(self.window,'reorder_customer_snapshot',None) and self.window.reorder_customer_snapshot['id']==self.snapshot['id']:
                self.window.reorder_customer_snapshot=self.snapshot;self.window.invalidate()
            self.query.setText(self.snapshot['code']);self.search();self.status.setText('確切關聯已撤銷並留最小稽核；當次新稿未修改，重新開啟重訂需核對現行關聯。')
        self.guarded(action)
    def add_button(self,bar,text,fn):
        b=QPushButton(text);b.clicked.connect(fn);bar.addWidget(b);return b
    def guarded(self,fn):
        try:return fn()
        except Exception as e:self.status.setText('未完成：'+str(e))
    def search(self):
        def action():
            self.snapshot=None;self.fields.setRowCount(0);self.details.clear();self.customers.clearSelection()
            self.results=self.store.search(self.query.text(),field=self.query_kind.currentData());self.customers.setRowCount(min(100,len(self.results)))
            for i,c in enumerate(self.results[:100]):
                for j,v in enumerate((c['code'],c['name'],c['id']+'／'+str(len(c['styles'])))):self.customers.setItem(i,j,QTableWidgetItem(v))
            self.status.setText(f'顯示{min(100,len(self.results))}筆；'+('仍有更多，請縮小條件' if len(self.results)>100 else '相同聯絡方式仍保留獨立身份；電話只去可說明格式，不猜國碼或修改原值'))
        self.guarded(action)
    def select(self):
        row=self.customers.currentRow();self.snapshot=self.store.get(self.results[row]['id']) if 0<=row<len(self.results) else None;self.fields.setRowCount(0)
        baseline=getattr(self.window,'reorder_customer_snapshot',None)
        if self.snapshot and baseline and baseline['id']==self.snapshot['id']:self.snapshot=baseline
        work_graph=getattr(self.window,'active_input_graph',None)
        work_fields={f['id']:f for f in work_graph.data['fields']} if work_graph and baseline and self.snapshot and baseline['id']==self.snapshot['id'] else {}
        if not self.snapshot:return
        current=self.store.get(self.snapshot['id']);current_fields={f['id']:f for f in current['fields']}
        from .input_graph import InputGraph
        entity_graph=InputGraph(self.snapshot['graph']) if self.snapshot.get('graph') else None
        self.fields.setRowCount(len(self.snapshot['fields']))
        for i,f in enumerate(self.snapshot['fields']):
            check=QTableWidgetItem();check.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable);check.setCheckState(Qt.Unchecked);self.fields.setItem(i,0,check)
            owner=entity_graph.field(f['id'])['owner_id'] if entity_graph else None
            owner_label=entity_graph.label(owner) if entity_graph else f['owner']
            impact=entity_graph.field_impact(f['id']) if entity_graph else []
            for col,value in ((1,owner_label+'／'+f['kind']),(2,f['value']),(3,work_fields.get(f['id'],{}).get('value',f['value'])),(4,f['id']),(5,current_fields.get(f['id'],{}).get('value','欄位已移除')),(6,'／'.join(entity_graph.label(x) for x in impact) if len(impact)>1 else '獨立')):
                item=QTableWidgetItem(value);item.setToolTip('欄位ID：'+f['id']+'\n所有者ID：'+str(owner)+'\n'+value)
                if col!=3:item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable)
                self.fields.setItem(i,col,item)
        self.details.setPlainText(json.dumps(self.snapshot['styles'],ensure_ascii=False,indent=2))
    def create(self):
        def action():
            code,ok=QInputDialog.getText(self,'客戶編號','字串編號（保留前導0）')
            if not ok:return
            name,ok=QInputDialog.getText(self,'名稱','客戶顯示名稱')
            if not ok:return
            templates=self.window.library.templates();labels=[f'{t.id} · {t.name} v{t.version} · {t.width_mm}×{t.height_mm}mm · {t.state}' for t in templates]
            chosen,ok=QInputDialog.getItem(self,'確切版型','人工核對此客戶的尺寸與版本',labels,0,False)
            if not ok:return
            people,companies,logos=self.window.input_data()
            from .input_graph import InputGraph
            graph=getattr(self.window,'active_input_graph',None) or InputGraph.from_legacy(people,companies,logos)
            fields=[dict(owner=f'p{i+1}',kind=k,value=v) for i,p in enumerate(people) for k,vs in p.items() if k in ('name','title','phone','email','line','ig','address') for v in vs if v]
            if QMessageBox.question(self,'建檔確認',f'客戶{code}，{len(fields)}欄，版型{chosen}；只存本機，非購買紀錄。確認？')!=QMessageBox.Yes:return
            c=self.store.create_graph(code,name,graph.data,templates[labels.index(chosen)].id,True);self.query.setText(c['code']);self.search();self.status.setText('人工客戶與確切尺寸版型關聯已保存')
        self.guarded(action)
    def values(self):
        if not self.snapshot:raise ValueError('先選取客戶')
        return {f['id']:self.fields.item(i,3).text() for i,f in enumerate(self.snapshot['fields'])}
    def preview(self):
        def action():self.details.setPlainText(json.dumps(self.store.differences(self.snapshot,self.values()),ensure_ascii=False,indent=2))
        self.guarded(action)
    def write(self):
        def action():
            values=self.values();selected=[f['id'] for i,f in enumerate(self.snapshot['fields']) if self.fields.item(i,0).checkState()==Qt.Checked];plan=self.store.differences(self.snapshot,values);actual=[x for x in plan['rows'] if x['id'] in selected]
            self.details.setPlainText(json.dumps(plan,ensure_ascii=False,indent=2))
            if not actual:raise ValueError('沒有勾選變更；沒有回寫')
            if QMessageBox.question(self,'僅回寫勾選欄位',json.dumps(actual,ensure_ascii=False,indent=2))!=QMessageBox.Yes:return
            updated=self.store.writeback(self.snapshot,values,selected,True)
            if getattr(self.window,'reorder_customer_snapshot',None) and self.window.reorder_customer_snapshot['id']==updated['id']:self.window.reorder_customer_snapshot=updated
            self.select();self.status.setText('選中欄位已原子回寫；當次候選仍須重驗')
        self.guarded(action)
    def prefill(self):
        def action():
            if not self.snapshot:raise ValueError('先選取客戶')
            links=self.snapshot['styles'];labels=[f"{s['id']} · {s['width_mm']}×{s['height_mm']}mm · {s['template_id']}" for s in links];choice,ok=QInputDialog.getItem(self,'確認身份與版型',self.snapshot['code']+'；僅預填本次，須重新驗證',labels,0,False)
            if not ok:return
            if QMessageBox.question(self,'預填影響','這會替換本次人物輸入。確認身份及上述確切版型？')!=QMessageBox.Yes:return
            draft=self.store.reorder(self.snapshot['id'],links[labels.index(choice)]['id'],True);w=self.window
            source_template=next(t for t in w.library.templates() if t.id==draft['template_id'])
            if source_template.source_id:raise ValueError('有來源圖的版型請使用尺寸版型目錄核對來源，快速文字入口不略過來源檢查')
            if not draft.get('graph'):
                # Ambiguous historical records remain review-only; never flatten away ownership.
                raise ValueError('舊客戶歸屬遷移待人工核對；資料保留，尚未預填')
            w.out_w.setValue(draft['width_mm']);w.out_h.setValue(draft['height_mm']);w.reorder_template_id=draft['template_id'];w.adopt_input_graph(draft['graph'],draft['snapshot']);w.invalidate();self.status.setText('已引用exact版本預填當次，無主檔修改；正式輸出仍待重新排版')
        self.guarded(action)
    def compare(self):
        def action():
            selected=sorted({i.row() for i in self.customers.selectedItems()})
            if len(selected)!=2:raise ValueError('Ctrl選取兩個客戶列')
            result=self.store.compare(*(self.results[i]['id'] for i in selected));self.details.setPlainText(json.dumps(result,ensure_ascii=False,indent=2));self.status.setText('只讀線索比對；身份UNKNOWN、不合併')
        self.guarded(action)
    def backup(self):
        def action():
            from .secure_backup import backup
            path,_=QFileDialog.getSaveFileName(self,'加密資料庫部分備份','','加密備份 (*.tabi)')
            if not path:return
            password,ok=QInputDialog.getText(self,'備份密碼','至少12字；遺失無法還原；資產不隨包',QLineEdit.Password)
            if ok:self.details.setPlainText(json.dumps(backup(self.window.library,path,password),ensure_ascii=False,indent=2));self.status.setText('加密完整性通過；部分備份，外部資產未保存，未宣稱可離線製作')
        self.guarded(action)
    def restore(self):
        def action():
            from .secure_backup import restore
            path,_=QFileDialog.getOpenFileName(self,'加密備份','','加密備份 (*.tabi)')
            if not path:return
            target,ok=QInputDialog.getText(self,'隔離目的地','不存在的新目錄完整路徑；不切換／覆寫目前Library')
            if not ok:return
            password,ok=QInputDialog.getText(self,'還原密碼','錯密碼不還原',QLineEdit.Password)
            if ok:self.details.setPlainText(json.dumps(restore(path,target,password),ensure_ascii=False,indent=2));self.status.setText('隔離資料庫完整性通過；外部資產待重新連結、製作未驗證')
        self.guarded(action)

    def link_style(self):
        def action():
            if not self.snapshot:raise ValueError('先選取客戶')
            templates=self.window.library.templates();labels=[f'{t.name} · {t.width_mm}×{t.height_mm} mm · v{t.version} · {t.id} · {t.state}' for t in templates]
            label,ok=QInputDialog.getItem(self,'關聯另一確切版型','不代表購買或本次Gate通過',labels,0,False)
            if not ok:return
            if QMessageBox.question(self,'新增版型關聯',self.snapshot['code']+' → '+label)!=QMessageBox.Yes:return
            updated=self.store.link_style(self.snapshot,templates[labels.index(label)].id,True)
            if getattr(self.window,'reorder_customer_snapshot',None) and self.window.reorder_customer_snapshot['id']==updated['id']:self.window.reorder_customer_snapshot=updated
            self.select();self.status.setText('確切尺寸／版型關聯已保存，本次製作與模板均未更動')
        self.guarded(action)

    def restore_history(self):
        def action():
            if not self.snapshot:raise ValueError('先選取客戶')
            history=self.store.history(self.snapshot['id'])
            if not history:raise ValueError('尚無欄位變更歷史')
            labels=[f"v{r['revision']} · {r['id']}" for r in history];label,ok=QInputDialog.getItem(self,'恢復歷史值是新的受控修改','只處理本頁勾選的欄位；不啟用舊電話搜尋別名',labels,0,False)
            if not ok:return
            change=history[labels.index(label)];values={f['id']:f['old'] for f in change['payload']['fields']};selected=[f['id'] for i,f in enumerate(self.snapshot['fields']) if self.fields.item(i,0).checkState()==Qt.Checked]
            plan=self.store.differences(self.snapshot,values);self.details.setPlainText(json.dumps(plan,ensure_ascii=False,indent=2))
            if not selected:raise ValueError('請勾選要恢復的欄位，沒有自動全選')
            if QMessageBox.question(self,'確認歷史值與目前版本',json.dumps(plan,ensure_ascii=False,indent=2))!=QMessageBox.Yes:return
            updated=self.store.restore_change(self.snapshot,change['id'],selected,True)
            if getattr(self.window,'reorder_customer_snapshot',None) and self.window.reorder_customer_snapshot['id']==updated['id']:self.window.reorder_customer_snapshot=updated
            self.select();self.status.setText('已以新版本恢復選中欄位；當次製作未被自動覆寫')
        self.guarded(action)

    def browse_styles(self):
        def action():
            if not self.snapshot:raise ValueError('先選取並核對客戶')
            current=self.store.get(self.snapshot['id'])
            if QMessageBox.question(self,'核對客戶身份',current['code']+'／'+current['name']+'／ID '+current['id']+'\n相同姓名／電話不是同一身份證明；確認後只開此客戶已確認關聯版型？')!=QMessageBox.Yes:return
            from .customer_catalog import CustomerStyleDialog
            dialog=CustomerStyleDialog(self.window,current,self)
            try:dialog.exec()
            finally:dialog.catalog.close_previews();dialog.deleteLater()
        self.guarded(action)

    def sync_graph(self):
        def action():
            if not self.snapshot:raise ValueError('先選取並確認客戶身份')
            from .customer_sync_dialog import CustomerSyncDialog
            dialog=CustomerSyncDialog(self.window,self.store,self.snapshot,self)
            dialog.exec()
            self.select()
        self.guarded(action)

    def source_candidates(self):
        def action():
            from .customer_candidates_dialog import CustomerCandidatesDialog
            dialog=CustomerCandidatesDialog(self.window,self)
            dialog.exec()
            self.search()
        self.guarded(action)

"""同一 Library 的尺寸 Logo 庫、候選審核與新尺寸預測獨立入口。"""
from copy import deepcopy
import json
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,
    QPushButton,QTreeWidget,QTreeWidgetItem,QTableWidget,QTableWidgetItem,QCheckBox,
    QPlainTextEdit,QComboBox,QTabBar,QDoubleSpinBox,QFileDialog,QInputDialog,QMessageBox,
    QDialogButtonBox)

from .customers import digest
from .logo_store import LogoStore
from .logo_assets import errors


class LogoLibraryDialog(QDialog):
    def __init__(self,window,exceptions_only=False):
        super().__init__(window)
        self.window=window;self.store=LogoStore(window.library);self.running=False;self.changed=False
        self.offset=0;self._reloading=False
        self.exceptions_only=exceptions_only
        self.setWindowTitle('尺寸獨立 Logo 庫／候選審核／新尺寸預測');self.resize(1220,850)
        layout=QVBoxLayout(self);self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);layout.addWidget(self.status)
        self.reference=QCheckBox('進入新尺寸預測專區（跨庫僅作候選，必須另核准目標尺寸）')
        self.reference.toggled.connect(self.reload);layout.addWidget(self.reference)
        bar=QHBoxLayout();self.company=QComboBox();bar.addWidget(self.company)
        self.button(bar,'新增已核對公司身分（不合併同名）',self.create_company)
        self.target_w,self.target_h=QDoubleSpinBox(),QDoubleSpinBox()
        for spin,value in ((self.target_w,window.out_w.value()),(self.target_h,window.out_h.value())):
            spin.setRange(.01,2000);spin.setDecimals(4);spin.setSuffix(' mm');spin.setValue(value);bar.addWidget(spin)
        self.predict_button=self.button(bar,'由已授權來源提出新尺寸候選',self.predict);layout.addLayout(bar)
        self.query=QLineEdit();self.query.setPlaceholderText('在目前尺寸搜尋公司、來源、確切資產／版本與狀態');self.query.textChanged.connect(self.selected);layout.addWidget(self.query)
        self.views=QTabBar()
        for title in ('已核准 Logo／版本歷史','AI 待審核候選','人工匯入'):self.views.addTab(title)
        self.views.currentChanged.connect(self.selected);layout.addWidget(self.views)
        self.tree=QTreeWidget();self.tree.setHeaderLabels(['卡片實體尺寸 mm／確切版本']);self.tree.setMaximumHeight(155);self.tree.itemSelectionChanged.connect(self.selected);layout.addWidget(self.tree)
        self.table=QTableWidget(0,8);self.table.setHorizontalHeaderLabels(['公司','卡片尺寸 mm','確切資產／候選 ID','核准範圍／狀態','版本／來源類型','來源／品質','目標尺寸 mm','公司身分 ID'])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.currentCellChanged.connect(self.show_details);layout.addWidget(self.table,2)
        bar=QHBoxLayout();self.import_button=self.button(bar,'人工匯入（先進待審核）',self.manual_import)
        self.discover_button=self.button(bar,'從目前來源作品提出複合群組候選',self.discover)
        self.button(bar,'附加本機 OCR 文字線索',self.ocr)
        self.button(bar,'查看／校正／逐項核准候選',self.review);self.button(bar,'拒絕／標為待修復',self.reject_candidate)
        self.button(bar,'放大比較完整來源與變體',self.compare);layout.addLayout(bar)
        bar=QHBoxLayout();self.button(bar,'合併所選來源候選',self.merge);self.button(bar,'另建兩個完整候選區域',self.split)
        self.button(bar,'建立同尺寸新版本候選',self.new_version);self.button(bar,'撤銷確切已核准版本',self.revoke)
        self.button(bar,'以既有草稿工具調整框位',self.edit_frame);self.button(bar,'前100候選',lambda:self.page(-100));self.button(bar,'後100候選',lambda:self.page(100));layout.addLayout(bar)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);self.details.setMaximumHeight(170);layout.addWidget(self.details)
        self.reload()

    def button(self,bar,label,action):
        button=QPushButton(label);button.clicked.connect(action);bar.addWidget(button);return button

    def guarded(self,action):
        try:
            if self.running or self.window.busy:raise ValueError('背景工作未完成，保留目前作用範圍')
            action()
        except (ValueError,KeyError,OSError,sqlite3.DatabaseError) as error:self.status.setText('未完成：'+str(error))

    def selected_size(self):
        node=self.tree.currentItem();return node.data(0,Qt.UserRole) if node else [self.window.out_w.value(),self.window.out_h.value()]

    def reload(self,*_):
        if self.running:return
        old_size=self.selected_size() if hasattr(self,'tree') and self.tree.currentItem() else [self.window.out_w.value(),self.window.out_h.value()]
        company=self.company.currentData();self.company.blockSignals(True);self.company.clear();self.company.addItem('尚未指定公司身分',None)
        for item in self.store.companies():self.company.addItem(item['name']+'／'+item['id'],item['id'])
        self.company.setCurrentIndex(max(0,self.company.findData(company)));self.company.blockSignals(False)
        self.assets=self.window.library.logos()
        sizes={(a['width_mm'],a['height_mm']) for a in self.assets}
        sizes.update((t.width_mm,t.height_mm) for t in self.window.library.templates())
        sizes.update((r[0],r[1]) for r in self.store.db.execute("SELECT DISTINCT json_extract(payload,'$.width_mm'),json_extract(payload,'$.height_mm') FROM logo_proposals LIMIT 200"))
        sizes.add(tuple(old_size));self.tree.blockSignals(True);self.tree.clear();selected=None
        for size in sorted(sizes):
            item=QTreeWidgetItem([f'{size[0]:g}×{size[1]:g} mm']);item.setData(0,Qt.UserRole,list(size));self.tree.addTopLevelItem(item)
            if list(size)==old_size:selected=item
            for asset in self.assets:
                if (asset['width_mm'],asset['height_mm'])==size:
                    child=QTreeWidgetItem([asset['company']+'／'+asset['id']]);child.setData(0,Qt.UserRole,list(size));child.setData(0,Qt.UserRole+1,asset['id']);item.addChild(child)
        if selected:self.tree.setCurrentItem(selected)
        self.tree.blockSignals(False)
        self.selected()

    def selected(self,*_):
        if self.running:return
        size=self.selected_size();reference=self.reference.isChecked();query=self.query.text().casefold();view=self.views.currentIndex()
        self.predict_button.setEnabled(reference);self.target_w.setEnabled(reference);self.target_h.setEnabled(reference)
        self.import_button.setEnabled(not reference);self.discover_button.setEnabled(not reference)
        if reference:
            rows=[dict(deepcopy(a),_kind='ASSET') for a in self.assets if a.get('approved')]
        elif view==0:
            rows=[dict(deepcopy(a),_kind='ASSET') for a in self.assets if size==[a['width_mm'],a['height_mm']]]
        else:
            rows=[]
            for proposal in self.store.proposals(*size,self.offset):
                if self.exceptions_only or (view==2)==(proposal['origin']=='MANUAL'):
                    company=next((c for c in self.store.companies() if c['id']==proposal.get('company_id')),None)
                    rows.append(dict(proposal,_kind='PROPOSAL',company=company['name'] if company else '身分待核對'))
        if self.exceptions_only:
            rows=[r for r in rows if r['_kind']=='PROPOSAL' and r['state'] in ('PENDING','NEEDS_REPAIR') and
                  (r['state']=='NEEDS_REPAIR' or not r.get('company_id') or r.get('evidence',{}).get('uncertainty') or r.get('evidence',{}).get('conflicts'))]
        self.rows=[r for r in rows if query in (r.get('company','')+' '+r['id']+' '+str(r.get('origin',''))+' '+str(r.get('state',r.get('status','')))+' '+str(r.get('evidence',{}))).casefold()]
        self.table.blockSignals(True);self.table.setRowCount(len(self.rows))
        for i,row in enumerate(self.rows):
            state=row.get('state',row.get('status','APPROVED' if row.get('approved') else 'UNKNOWN'))
            health=errors(row) if row['_kind']=='ASSET' else errors(row['asset'],False)
            scope='來源尺寸已核准／目標未核准' if reference else state+'／僅此尺寸'
            source=('；'.join(health) or '來源 hash 已核對') if row.get('managed_logo') or row['_kind']=='PROPOSAL' else '舊資產，來源／完整性需核對'
            values=(row['company'],f"{row['width_mm']:g}×{row['height_mm']:g}",row['id'],scope,
                    str(row.get('version','候選'))+'／'+row.get('origin','LEGACY'),source,
                    f'{self.target_w.value():g}×{self.target_h.value():g}' if reference else '不跨尺寸',row.get('company_id') or 'UNKNOWN')
            for col,value in enumerate(values):
                item=QTableWidgetItem(str(value));item.setToolTip(str(value));self.table.setItem(i,col,item)
        node=self.tree.currentItem();exact=node.data(0,Qt.UserRole+1) if node else None
        index=next((i for i,r in enumerate(self.rows) if r['id']==exact),0 if self.rows else -1)
        self.table.setCurrentCell(index,0);self.table.blockSignals(False);self.show_details()
        self.status.setText(('新尺寸預測專區：跨庫內容只作參考，目標未核准；退出後恢復尺寸隔離。' if reference else f'目前卡片尺寸庫 {size} mm；已核准／待審／人工匯入共用同一資產庫。')+' 瀏覽不核准、不自動替換當次 Logo。')
        if self.exceptions_only:self.status.setText('Logo例外中心：只顯示本尺寸身分／來源不確定、衝突或待修復候選；其他待審仍在一般審核佇列。')

    def current(self):
        index=self.table.currentRow()
        if not 0<=index<len(self.rows):raise ValueError('先選取確切 Logo 或候選')
        return self.rows[index]

    def focus_proposal(self,identity):
        row=self.store.proposal(identity);size=[row['width_mm'],row['height_mm']]
        self.reference.setChecked(False);self.query.clear();self.reload()
        for i in range(self.tree.topLevelItemCount()):
            node=self.tree.topLevelItem(i)
            if node.data(0,Qt.UserRole)==size:self.tree.setCurrentItem(node);break
        count=self.store.db.execute("SELECT count(*) FROM logo_proposals WHERE rowid<(SELECT rowid FROM logo_proposals WHERE id=?) AND abs(json_extract(payload,'$.width_mm')-?)<0.00001 AND abs(json_extract(payload,'$.height_mm')-?)<0.00001",(identity,*size)).fetchone()[0]
        self.offset=(count//100)*100
        self.views.setCurrentIndex(2 if row['origin']=='MANUAL' else 1);self.selected()
        index=next((i for i,r in enumerate(self.rows) if r['id']==identity),-1)
        if index>=0:self.table.setCurrentCell(index,0)
        return index>=0

    def show_details(self,*_):
        if not hasattr(self,'details'):return
        try:self.details.setPlainText(json.dumps(self.current(),ensure_ascii=False,indent=2))
        except ValueError:self.details.clear()

    def page(self,delta):self.offset=max(0,self.offset+delta);self.selected()

    def create_company(self):
        def action():
            name,ok=QInputDialog.getText(self,'核對公司身分','已確認公司名稱（同名公司不自動合併）')
            if not ok:return
            note,ok=QInputDialog.getText(self,'身分依據','來源／身分核對依據，不抄寫私人聯絡資料')
            if not ok:return
            if QMessageBox.question(self,'新增獨立公司身分',name+'\n'+note+'\n不合併任何同名公司，確認？')!=QMessageBox.Yes:return
            company=self.store.create_company(name,note,True);self.reload();self.company.setCurrentIndex(self.company.findData(company['id']))
        self.guarded(action)

    def background(self,label,operation):
        root=self.window.library.root;self.running=True;self.status.setText(label+'；背景核對中，尚未宣稱完成。')
        def worker():
            from .storage import Library
            library=None
            try:
                library=Library(root)
                return {'result':operation(LogoStore(library))}
            except Exception as error:return {'error':str(error)}
            finally:
                if library:library.close()
        def finished(result):
            self.running=False;self.reload()
            self.status.setText('未完成：'+result['error'] if 'error' in result else label+'已建立／重用候選，仍需逐項核准。')
        try:self.window.run_job(label,worker,finished)
        except Exception:self.running=False;raise

    def manual_import(self,base=None):
        def action():
            if self.reference.isChecked():raise ValueError('新尺寸參考專區只建立明確預測候選；返回一般尺寸才人工匯入')
            path,_=QFileDialog.getOpenFileName(self,'完整 Logo 圖文來源','','Logo (*.svg *.pdf *.ai *.png *.jpg *.jpeg)')
            if not path:return
            width,height=self.selected_size();company=self.company.currentData()
            def operation(store):
                from .importer import import_file
                result=import_file(path,store.library.assets)
                payload=dict(image=result['image'],svg=result.get('svg',''),source_width_mm=result['width_mm'],source_height_mm=result['height_mm'],source_hash=result['hash'],crop=None)
                return store.propose(payload,width,height,'MANUAL',company,family_base=base)['id']
            self.background('人工匯入完整 Logo',operation)
        self.guarded(action)

    def discover(self):
        def action():
            if self.reference.isChecked():raise ValueError('此處只作新尺寸預測，請回一般庫由來源提出候選')
            source,work=self.window.source,self.window.work
            if not source or not work:raise ValueError('先在原訓練工作台選定來源作品')
            sid,wid=source['id'],work['id']
            def operation(store):
                from .logo_discovery import discover
                return [r['id'] for r in discover(store,sid,wid)]
            self.background('從向量群組提出完整 Logo 候選',operation)
        self.guarded(action)

    def predict(self):
        def action():
            if not self.reference.isChecked():raise ValueError('跨尺寸參考只限明確進入新尺寸預測專區')
            company=self.company.currentData();width,height=self.target_w.value(),self.target_h.value()
            if not company:raise ValueError('先選定已核對的公司身分')
            self.background('提出新卡片尺寸 Logo 候選',lambda store:[r['id'] for r in store.predict_new_size(company,width,height)])
        self.guarded(action)

    def ocr(self):
        def action():
            row=self.current()
            if row['_kind']!='PROPOSAL':raise ValueError('OCR只補充待審候選線索，不改正式Logo文字')
            identity,revision=row['id'],row['revision']
            def operation(store):
                from .logo_ocr import annotate
                return annotate(store,identity,revision)['id']
            self.background('附加本機 OCR 線索（不是公司身分確認）',operation)
        self.guarded(action)

    def review(self):
        def action():
            row=self.current()
            if row['_kind']!='PROPOSAL':raise ValueError('此為已保存版本；請選待審候選，或明確建立新版本候選')
            if self.reference.isChecked():raise ValueError('先返回目標尺寸庫選取候選，不能在跨庫參考畫面直接核准來源版本')
            from .logo_review_dialog import LogoReviewDialog
            dialog=LogoReviewDialog(self.store,self.store.proposal(row['id']),self)
            if dialog.exec()==QDialog.Accepted:
                self.changed=True;self.window.refresh_logos()
            self.reload()
        self.guarded(action)

    def reject_candidate(self):
        def action():
            row=self.current()
            if row['_kind']!='PROPOSAL':raise ValueError('正式版本需用明確撤銷，不當成拒絕候選')
            reason,ok=QInputDialog.getText(self,'拒絕或待修正','來源、邊界、身分或品質原因')
            if not ok:return
            mode,ok=QInputDialog.getItem(self,'處置候選','不刪原始來源',['拒絕','待修復'],0,False)
            if not ok:return
            self.store.reject(row['id'],row['revision'],reason,True,repair=mode=='待修復');self.reload()
        self.guarded(action)

    def compare(self):
        def action():
            selected=sorted({item.row() for item in self.table.selectedItems()})
            if not 1<=len(selected)<=2:raise ValueError('選取一或兩筆確切版本／候選作唯讀比較')
            rows=[self.rows[i] for i in selected];assets=[r['asset'] if r['_kind']=='PROPOSAL' else r for r in rows]
            from .logo_compare import LogoCompareWidget
            dialog=QDialog(self);dialog.setWindowTitle('完整圖文／來源與版本對照（不選用、不核准）');dialog.resize(1280,650);layout=QVBoxLayout(dialog);widget=LogoCompareWidget();layout.addWidget(widget)
            widget.show_assets(assets[-1],assets[0],30,15)
            buttons=QDialogButtonBox(QDialogButtonBox.Close);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons);dialog.exec()
        self.guarded(action)

    def region_selection(self):
        indices=sorted({item.row() for item in self.table.selectedItems()})
        if not indices:raise ValueError('先選取來源候選；不處理已核准資產')
        rows=[self.rows[i] for i in indices]
        if any(r['_kind']!='PROPOSAL' for r in rows):raise ValueError('合併／拆分只建立來源候選，不更改正式 Logo')
        return rows

    def merge(self):
        def action():
            rows=self.region_selection()
            if len(rows)<2:raise ValueError('選取至少兩個同作品待審來源候選')
            note,ok=QInputDialog.getText(self,'合併成完整圖文候選','完整圖文及公司歸屬的校正依據')
            if not ok:return
            self.store.regions([dict(id=r['id'],revision=r['revision']) for r in rows],None,note);self.reload()
        self.guarded(action)

    def split(self):
        def action():
            row=self.current()
            if row['_kind']!='PROPOSAL' or row['origin']!='SOURCE':raise ValueError('先選一筆同作品來源候選')
            dialog=QDialog(self);dialog.setWindowTitle('建立兩個需重新核對的完整圖文區域');layout=QVBoxLayout(dialog)
            layout.addWidget(QLabel('這不是切割已核准商標；兩個區域各自重新確認完整性、公司與品質。'))
            frames=[];crop=row['asset']['crop']
            for number in range(2):
                bar=QHBoxLayout();spins=[];bar.addWidget(QLabel('區域'+str(number+1)))
                for name in ('x','y','w','h'):
                    bar.addWidget(QLabel(name+' mm'));spin=QDoubleSpinBox();spin.setRange(0,2000);spin.setDecimals(5);spin.setValue(crop[name]);bar.addWidget(spin);spins.append(spin)
                frames.append(spins);layout.addLayout(bar)
            note=QLineEdit();note.setPlaceholderText('校正理由與原稿證據');layout.addWidget(note);buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
            if dialog.exec()!=QDialog.Accepted:return
            regions=[dict(zip(('x','y','w','h'),[s.value() for s in spins])) for spins in frames]
            self.store.regions([dict(id=row['id'],revision=row['revision'])],regions,note.text());self.reload()
        self.guarded(action)

    def new_version(self):
        def action():
            row=self.current()
            if row['_kind']!='ASSET' or not row.get('managed_logo'):raise ValueError('先選已核對公司身分的受管理版本；舊資產先重新匯入核對')
            self.company.setCurrentIndex(self.company.findData(row['company_id']));self.manual_import(base=row['id'])
        self.guarded(action)

    def revoke(self):
        def action():
            row=self.current()
            if row['_kind']!='ASSET':raise ValueError('先選確切正式版本')
            # UI 用的 _kind 不屬於資產內容，不放入 CAS 雜湊。
            asset=self.store.asset(row['id'])
            references=[dict(customer_id=r[0],company_entity_id=r[1]) for r in self.store.db.execute('SELECT customer_id,id FROM customer_entities WHERE logo_id=?',(asset['id'],))] if self.store.db.execute("SELECT 1 FROM sqlite_master WHERE name='customer_entities'").fetchone() else []
            current=getattr(self.window,'active_input_graph',None);work_refs=[c['id'] for c in current.data['companies'] if c['logo_id']==asset['id']] if current else []
            reason,ok=QInputDialog.getText(self,'撤銷版本原因','不刪原圖；原選用候選會失效，必須重新核對')
            if not ok:return
            if QMessageBox.question(self,'確認確切版本與實際引用影響',asset['id']+'\n當次公司：'+str(work_refs)+'\n主檔引用：'+str(references)+'\n不自動替換其他版本，確認撤銷？')!=QMessageBox.Yes:return
            self.store.revoke(asset['id'],digest(asset),reason,True);self.changed=True;self.window.refresh_logos();self.reload()
        self.guarded(action)

    def edit_frame(self):
        def action():
            template=self.window.template
            if not template or self.window.tabs.currentIndex()!=1 or self.window.template_stack.currentIndex()!=1:
                raise ValueError('先在模板庫明確開啟要調整的模板，不從瀏覽 Logo 猜測目標')
            if self.reference.isChecked() or self.selected_size()!=[template.width_mm,template.height_mm]:
                raise ValueError('框位編輯只限目前模板的同一實體尺寸，先返回一般尺寸庫')
            from .training_navigation import require_clean_navigation
            require_clean_navigation(self.window)
            if template.state=='published':
                if QMessageBox.question(self,'建立同模板新版本草稿','保持正式版不變；另建草稿，再由既有物件工具預覽與確認毫米差異？')!=QMessageBox.Yes:return
                self.window.new_version()
            if not self.window.template or self.window.template.state!='draft':
                raise ValueError('尚未成功建立草稿，沒有變更正式框位')
            self.window.object_tools()
        self.guarded(action)

    def closeEvent(self,event):
        if self.running:self.status.setText('背景候選正在安全保存，完成後可關閉。');event.ignore()
        else:super().closeEvent(event)

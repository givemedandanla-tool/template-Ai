"""One customer entry backed by the existing Library connection."""
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLineEdit,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QPlainTextEdit,QMessageBox,QFileDialog,QInputDialog
from .customers import CustomerStore

class CustomerDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.store=CustomerStore(window.library);self.snapshot=None;self.results=[]
        self.setWindowTitle('本機客戶／版型關聯與逐欄比對');self.resize(1000,720);layout=QVBoxLayout(self)
        self.status=QLabel('僅匿名研究資料；查詢不合併、不回寫；完整個資權限尚未完成。');self.status.setWordWrap(True);layout.addWidget(self.status)
        bar=QHBoxLayout();self.query=QLineEdit();self.query.setPlaceholderText('客戶編號／姓名／聯絡資訊（空查詢不載全庫）');bar.addWidget(self.query);self.add_button(bar,'搜尋',self.search);self.add_button(bar,'將目前人物資料人工建檔',self.create);layout.addLayout(bar)
        self.customers=QTableWidget(0,3);self.customers.setHorizontalHeaderLabels(['客戶編號','名稱','內部ID／版型數']);self.customers.setEditTriggers(QTableWidget.NoEditTriggers);self.customers.setSelectionBehavior(QTableWidget.SelectRows);self.customers.itemSelectionChanged.connect(self.select);layout.addWidget(self.customers)
        self.fields=QTableWidget(0,5);self.fields.setHorizontalHeaderLabels(['回寫（預設不選）','人物／類型','主檔原值','本次值（可編輯／清空）','stable欄位ID']);layout.addWidget(self.fields)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details)
        bar=QHBoxLayout();self.add_button(bar,'確認身份／選版型預填當次',self.prefill);self.add_button(bar,'比較選中欄位差異',self.preview);self.add_button(bar,'確認選中差異回寫',self.write);self.add_button(bar,'比較兩個客戶（不合併）',self.compare);layout.addLayout(bar)
        bar=QHBoxLayout();self.add_button(bar,'加密資料庫部分備份',self.backup);self.add_button(bar,'隔離還原到新目錄',self.restore);self.add_button(bar,'關閉',self.accept);layout.addLayout(bar)
    def add_button(self,bar,text,fn):
        b=QPushButton(text);b.clicked.connect(fn);bar.addWidget(b);return b
    def guarded(self,fn):
        try:return fn()
        except Exception as e:self.status.setText('未完成：'+str(e))
    def search(self):
        def action():
            self.results=self.store.search(self.query.text());self.customers.setRowCount(min(100,len(self.results)))
            for i,c in enumerate(self.results[:100]):
                for j,v in enumerate((c['code'],c['name'],c['id']+'／'+str(len(c['styles'])))):self.customers.setItem(i,j,QTableWidgetItem(v))
            self.status.setText(f'顯示{min(100,len(self.results))}筆；'+('仍有更多，請縮小條件' if len(self.results)>100 else '相同聯絡方式仍保留獨立身份'))
        self.guarded(action)
    def select(self):
        row=self.customers.currentRow();self.snapshot=self.store.get(self.results[row]['id']) if 0<=row<len(self.results) else None;self.fields.setRowCount(0)
        if not self.snapshot:return
        self.fields.setRowCount(len(self.snapshot['fields']))
        for i,f in enumerate(self.snapshot['fields']):
            check=QTableWidgetItem();check.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable);check.setCheckState(Qt.Unchecked);self.fields.setItem(i,0,check)
            for col,value in ((1,f['owner']+'／'+f['kind']),(2,f['value']),(3,f['value']),(4,f['id'])):
                item=QTableWidgetItem(value)
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
            if any(p.get('company') for p in people):raise ValueError('公司關聯建檔尚未實作，先勿保存此資料，避免遺失公司語意')
            fields=[dict(owner=f'p{i+1}',kind=k,value=v) for i,p in enumerate(people) for k,vs in p.items() if k in ('name','title','phone','email','line','ig','address') for v in vs if v]
            if QMessageBox.question(self,'建檔確認',f'客戶{code}，{len(fields)}欄，版型{chosen}；只存本機，非購買紀錄。確認？')!=QMessageBox.Yes:return
            c=self.store.create(code,name,fields,templates[labels.index(chosen)].id,True);self.query.setText(c['code']);self.search();self.status.setText('人工客戶與確切尺寸版型關聯已保存')
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
            self.store.writeback(self.snapshot,values,selected,True);self.select();self.status.setText('選中欄位已原子回寫；當次候選仍須重驗')
        self.guarded(action)
    def prefill(self):
        def action():
            if not self.snapshot:raise ValueError('先選取客戶')
            links=self.snapshot['styles'];labels=[f"{s['id']} · {s['width_mm']}×{s['height_mm']}mm · {s['template_id']}" for s in links];choice,ok=QInputDialog.getItem(self,'確認身份與版型',self.snapshot['code']+'；僅預填本次，須重新驗證',labels,0,False)
            if not ok:return
            if QMessageBox.question(self,'預填影響','這會替換本次人物輸入。確認身份及上述確切版型？')!=QMessageBox.Yes:return
            draft=self.store.reorder(self.snapshot['id'],links[labels.index(choice)]['id'],True);w=self.window;w.people.setRowCount(len(draft['people']))
            for i,p in enumerate(draft['people']):
                for j,k in enumerate(('name','title','phone','email','line','ig','address')):w.people.setItem(i,j,QTableWidgetItem('；'.join(p.get(k,[]))))
                w.people.setItem(i,7,QTableWidgetItem(''))
            w.companies.setRowCount(1);w.companies.setItem(0,0,QTableWidgetItem(''));w.out_w.setValue(draft['width_mm']);w.out_h.setValue(draft['height_mm']);w.reorder_template_id=draft['template_id'];w.refresh_logos();w.invalidate();self.status.setText('已引用exact版本預填當次，無主檔修改；正式輸出仍待重新排版')
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

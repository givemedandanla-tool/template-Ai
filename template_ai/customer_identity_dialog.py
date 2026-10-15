"""Shared human-readable identity comparison, not a second customer editor."""
from PySide6.QtCore import Qt,Signal
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QTreeWidget,QTreeWidgetItem,QPushButton,QCheckBox,QMessageBox


class IdentityPreviewDialog(QDialog):
    reviewed=Signal(str)

    def __init__(self,window,store,plan,parent=None):
        super().__init__(parent or window);self.window=window;self.store=store;self.plan=plan
        self.setWindowTitle('身份合併／拆分逐項核對');self.resize(1180,780)
        layout=QVBoxLayout(self)
        split=plan['operation']=='SPLIT';comparison=plan['operation']=='COMPARE'
        self.states=plan['original']['before'] if split else plan['before']
        caption=('只讀雙欄比對：身份UNKNOWN，沒有自動合併或修改。' if comparison else '拆分：保留目前可明確歸屬的新值。歧義需先修正，不會用歷史值覆蓋。' if split else
                 f"合併：保留主客戶 {plan['primary_code']}。人物／公司保持獨立，舊碼保留別名。")
        label=QLabel(caption+'\n相同姓名、電話、公司、Logo或原稿位元均只是線索，不能單獨證明同一身份。');label.setWordWrap(True);layout.addWidget(label)
        self.table=QTreeWidget();self.table.setHeaderLabels(['核對項目','客戶 A（原資料）','客戶 B（原資料）','差異／目前值與影響']);layout.addWidget(self.table,1)
        a,b=[s['customer'] for s in self.states]
        self.add('客戶編號',a['code'],b['code'],'舊碼均保留；可搜尋到核准的主客戶')
        self.add('主檔名稱',a['name'],b['name'],'保留主客戶名稱，不拼接成另一個人')
        identity=self.add('內部身份',a['id'],b['id'],'穩定ID保留；次客戶停用轉向，不重用ID')
        identity.setToolTip(0,'內部身份用於確認歸屬與追溯，並不代表已核實現實身份')
        self.add('既有歷史別名','、'.join(a.get('identity_aliases',[])) or '無','、'.join(b.get('identity_aliases',[])) or '無','主編號／別名衝突會阻擋')
        names={}
        for customer in (a,b):
            names.update({f['owner_id']:f['value'] for f in customer['graph']['fields'] if f['kind']=='name'})
        current={f['id']:f['value'] for g in plan.get('graphs',[]) for f in g['fields']}
        for key,label in (('people','人物（各自獨立）'),('companies','公司（各自獨立）')):
            self.add(label,'\n'.join(names[e['id']]+' · '+e['id'][:8] for e in a['graph'][key]),
                     '\n'.join(names[e['id']]+' · '+e['id'][:8] for e in b['graph'][key]),'不依名稱、共享公司或Logo自動合併實體')
        fields=self.add('人物／公司欄位','','','每一值依穩定所有者核對；不按姓名串接人物')
        for kind in sorted({f['kind'] for c in (a,b) for f in c['graph']['fields']}):
            groups=[[f for f in c['graph']['fields'] if f['kind']==kind] for c in (a,b)]
            display=lambda rows:'\n'.join(f"{names[f['owner_id']]} [{f['owner_id'][:8]}]：{f['value']}"+
                ('（共享給'+','.join(names[u] for u in f['users'] if u!=f['owner_id'])+'）' if len(f['users'])>1 else '') for f in rows)
            values=[{f['value'] for f in rows} for rows in groups]
            verdict='文字相同，僅為線索' if values[0] and values[0]==values[1] else '僅B有資料' if not values[0] else '僅A有資料' if not values[1] else '資料不同／衝突，逐項核對'
            changes=[f"{names[f['owner_id']]}：{f['value']} → {current[f['id']]}（保留新值）" for rows in groups for f in rows if f['id'] in current and current[f['id']]!=f['value']]
            if split:changes += [f"{names[f['owner_id']]}：原欄位已刪除，方案保留目前刪除狀態" for rows in groups for f in rows if f['id'] not in current]
            self.add(kind,display(groups[0]),display(groups[1]),'\n'.join([verdict]+changes),fields)
        if split:
            old_ids={f['id'] for customer in (a,b) for f in customer['graph']['fields']}
            new=[[f for f in g['fields'] if f['id'] not in old_ids] for g in plan['graphs']]
            self.add('合併後新增欄位',display(new[0]),display(new[1]),'按已核准的穩定所有者保留新增值；不恢復已刪除舊值',fields)
        links=lambda g:'\n'.join(names[p]+' → '+names[c] for p,c in g['links']) or '無'
        self.add('人物－公司關係',links(a['graph']),links(b['graph']),
                 ('拆分後A：'+links(plan['graphs'][0])+'\n拆分後B：'+links(plan['graphs'][1])) if split else '保留全部已確認關係，不因相同公司名稱合併')
        styles=self.add('尺寸／確切版型版本','','','每原版型保留原人物範圍，仍須重新排版驗證')
        for side,state in enumerate(self.states):
            for style in state['customer']['styles']:
                value=f"{style['width_mm']:g} × {style['height_mm']:g} mm\n版型 {style['template_id']}\n關聯 {style['id']}"
                self.add('A版型' if side==0 else 'B版型',value if side==0 else '',value if side else '',style['template_hash'],styles)
        sources=self.add('原稿／來源作品','','','未列來源表示證據不足；不能當已核實來源')
        pins=plan.get('asset_pins',{})
        for side,state in enumerate(self.states):
            for association in state['associations']:
                pin=pins.get(association['source_id'],{})
                value=f"{pin.get('path','目前位置未核實')}\n來源 {association['source_id']}\n作品 {association['artwork_id']}"
                node=self.add('A原稿區域' if side==0 else 'B原稿區域',value if side==0 else '',value if side else '',association['source_hash'],sources)
                node.setData(0,Qt.UserRole,association['artwork_id'])
        self.table.expandToDepth(0)
        for column,width in enumerate((190,300,300,340)):self.table.setColumnWidth(column,width)
        bar=QHBoxLayout()
        for text,fn in [('查看A客戶卡片',lambda:self.customer_card(0)),('查看B客戶卡片',lambda:self.customer_card(1)),('定位所選來源作品',self.locate_source)]:
            button=QPushButton(text);button.clicked.connect(fn);bar.addWidget(button)
        layout.addLayout(bar)
        self.ack=QCheckBox('已逐項核對雙方身份、人物／公司、來源、每尺寸版型及本方案影響；此核對不授權發布模板或輸出');layout.addWidget(self.ack)
        bar=QHBoxLayout();self.confirm=QPushButton('完成核對，返回後另行確認方案');self.confirm.setEnabled(False);self.ack.toggled.connect(self.confirm.setEnabled);self.confirm.clicked.connect(self.acknowledge);bar.addWidget(self.confirm)
        close=QPushButton('返回，尚未核准');close.clicked.connect(self.reject);bar.addWidget(close);layout.addLayout(bar)
        if comparison:self.ack.hide();self.confirm.hide()

    def add(self,label,a,b,status,parent=None):
        node=QTreeWidgetItem([label,str(a),str(b),str(status)])
        for column in range(4):node.setToolTip(column,node.text(column))
        if parent:parent.addChild(node)
        else:self.table.addTopLevelItem(node)
        return node

    def acknowledge(self):
        if self.ack.isChecked():self.reviewed.emit(self.plan['sha256']);self.accept()

    def customer_card(self,side):
        from .customer_catalog import CustomerStyleDialog
        current=self.store.get(self.states[side]['customer']['id'])
        self.card=CustomerStyleDialog(self.window,current,self);self.card.open()

    def locate_source(self):
        node=self.table.currentItem();identity=node.data(0,Qt.UserRole) if node else None
        if not identity:QMessageBox.information(self,'來源定位','先選一個A／B原稿區域');return
        try:
            from .annotation_dialog import AnnotationDialog
            self.annotation=AnnotationDialog(self.window,identity,self);self.annotation.open()
        except (ValueError,OSError) as error:QMessageBox.warning(self,'來源未開啟',str(error))

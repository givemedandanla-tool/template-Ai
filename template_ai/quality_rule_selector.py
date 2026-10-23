"""Bounded exact approved rule selection reused by the existing version setup."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLineEdit,QPushButton,QLabel,QTableWidget,QTableWidgetItem,QCheckBox

STATES=('ACTIVE','ISOLATED_APPROVED_REPAIR_CANDIDATE')


class ExactRuleSelector(QWidget):
    error=Signal(str)

    def __init__(self,store,parent=None):
        super().__init__(parent);self.store=store;self.offset=0;self.selected_versions={};self.rows=[]
        layout=QVBoxLayout(self);bar=QHBoxLayout();self.query=QLineEdit();self.query.setPlaceholderText('全庫搜尋已核准規則完整字串／版本；每頁50筆');bar.addWidget(self.query,1)
        for label,delta in (('搜尋',0),('前50',-50),('後50',50)):
            button=QPushButton(label);button.clicked.connect(lambda checked=False,d=delta:self.guarded_refresh(d));bar.addWidget(button)
        layout.addLayout(bar);self.table=QTableWidget(0,3);self.table.setHorizontalHeaderLabels(['明確選取','完整字串／exact版本','核准狀態']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setMaximumHeight(155);layout.addWidget(self.table)
        self.status=QLabel('未預設任何隔離規則；凍結版本不等於正式採用。');self.status.setWordWrap(True);layout.addWidget(self.status)

    def guarded_refresh(self,delta=0):
        try:self.refresh(delta)
        except (ValueError,OSError) as error:self.status.setText(str(error));self.error.emit(str(error))

    def refresh(self,delta=0):
        self.offset=max(0,self.offset+delta) if delta else 0
        where="kind='RULE' AND json_extract(payload,'$.state') IN ('ACTIVE','ISOLATED_APPROVED_REPAIR_CANDIDATE')";args=[]
        for token in self.query.text().casefold().split():where+=" AND instr(training_casefold(id||' '||json_extract(payload,'$.literal')||' '||json_extract(payload,'$.state')),?)>0";args.append(token)
        total=self.store.db.execute('SELECT count(*) FROM training_records WHERE '+where,args).fetchone()[0]
        self.rows=[dict(id=row[0],revision=row[1],literal=row[2],state=row[3]) for row in self.store.db.execute("SELECT id,revision,json_extract(payload,'$.literal'),json_extract(payload,'$.state') FROM training_records WHERE "+where+' ORDER BY id LIMIT 50 OFFSET ?',(*args,self.offset))]
        self.table.setRowCount(len(self.rows))
        for index,row in enumerate(self.rows):
            previous=self.selected_versions.get(row['id'])
            if previous is not None and previous!=row['revision']:self.selected_versions.pop(row['id'],None)
            box=QCheckBox();box.setChecked(self.selected_versions.get(row['id'])==row['revision']);box.toggled.connect(lambda selected,r=row:self.choose(r,selected));self.table.setCellWidget(index,0,box)
            self.table.setItem(index,1,QTableWidgetItem(row['literal']+' · '+row['id'][:12]+' / '+str(row['revision'])))
            self.table.setItem(index,2,QTableWidgetItem('已核准既有規則' if row['state']=='ACTIVE' else '已核准隔離修復候選'))
        self.status.setText(f"第{self.offset+1}起最多50筆／共{total}；明列{len(self.selected_versions)}個版本。支持／反例失效仍由後端拒絕。")

    def choose(self,row,selected):
        if selected:self.selected_versions[row['id']]=row['revision']
        else:self.selected_versions.pop(row['id'],None)

    def selection(self):
        if not self.selected_versions or len(self.selected_versions)>200:raise ValueError('明列1～200個已核准規則；空清單請明確選擇不使用規則')
        result=[]
        for identity,revision in sorted(self.selected_versions.items()):
            row=self.store.db.execute("SELECT revision,json_extract(payload,'$.state') FROM training_records WHERE kind='RULE' AND id=?",(identity,)).fetchone()
            if not row or row[0]!=revision or row[1] not in STATES:raise ValueError('選定規則版次／核准狀態已改變，需重新核對')
            result.append(dict(id=identity,revision=revision))
        return result

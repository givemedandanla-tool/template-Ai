"""One review center for current rule versions, evidence, exact known impact and human decisions."""
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, QPlainTextEdit, QPushButton, QCheckBox, QMessageBox
from .training_store import TrainingStore


class RuleReviewPanel(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent); self.window=window; self.store=TrainingStore(window.library); self.rows=[]; self.offset=0; self.loading=False
        outer=QVBoxLayout(self);bar=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('全規則完整文字／ID搜尋（字詞AND）');self.search.textChanged.connect(self.search_changed);bar.addWidget(self.search,1);self.state=QComboBox();self.state.addItems(['ALL','PENDING','DEFERRED','ACTIVE','REJECTED','DISABLED']);self.state.currentIndexChanged.connect(self.search_changed);bar.addWidget(self.state);self.reload_button=QPushButton('重新核對規則');self.reload_button.clicked.connect(self.reload);bar.addWidget(self.reload_button);outer.addLayout(bar)
        self.status=QLabel('LOW同前提可批次；HIGH逐條詳審；BLOCK不可批准。影響只指候選，不改發布模板。');self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);outer.addWidget(self.status)
        self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(['風險','狀態／版次','完整字串','type／scope組','候選排除／保留','規則ID']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.ExtendedSelection);self.table.itemSelectionChanged.connect(self.selected);outer.addWidget(self.table,2)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);outer.addWidget(self.details,2)
        bar=QHBoxLayout();self.previous_button=QPushButton('上一頁規則');self.next_button=QPushButton('下一頁規則');self.previous_button.clicked.connect(lambda:self.page(-200));self.next_button.clicked.connect(lambda:self.page(200));bar.addWidget(self.previous_button);bar.addWidget(self.next_button);self.count=QLabel();bar.addWidget(self.count,1);outer.addLayout(bar)
        bar=QHBoxLayout();self.actor=QLineEdit();self.actor.setMaxLength(120);self.actor.setPlaceholderText('審核者（本機）');bar.addWidget(self.actor);self.reason=QLineEdit();self.reason.setMaxLength(512);self.reason.setPlaceholderText('本次審核原因');bar.addWidget(self.reason);self.detail_reviewed=QCheckBox('已逐條詳審HIGH來源、正反例與精確影響');bar.addWidget(self.detail_reviewed);outer.addLayout(bar)
        bar=QHBoxLayout();self.approve_button=QPushButton('明確批准選中規則');self.reject_button=QPushButton('拒絕');self.defer_button=QPushButton('暫緩')
        for button,action in ((self.approve_button,'APPROVE'),(self.reject_button,'REJECT'),(self.defer_button,'DEFER')):button.clicked.connect(lambda _,a=action:self.decide(a));bar.addWidget(button)
        outer.addLayout(bar);self.reload()

    def search_changed(self,*_):self.offset=0;self.reload()
    def page(self,delta):self.offset=max(0,self.offset+delta);self.reload()
    def selected_ids(self):return [self.rows[r.row()]['id'] for r in self.table.selectionModel().selectedRows() if r.row()<len(self.rows)]
    def reload(self,*_):
        if self.loading:return
        old=self.selected_ids();self.loading=True
        try:
            where=['kind=?'];args=['RULE']
            for token in self.search.text().casefold().split():where.append("training_casefold(payload||id) LIKE ? ESCAPE '\\'");args.append('%'+token.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%')
            if self.state.currentText()!='ALL':where.append("json_extract(payload,'$.state')=?");args.append(self.state.currentText())
            condition=' AND '.join(where);total=self.store.db.execute('SELECT count(*) FROM training_records WHERE '+condition,args).fetchone()[0]
            ids=[r[0] for r in self.store.db.execute('SELECT id FROM training_records WHERE '+condition+' ORDER BY id LIMIT 200 OFFSET ?',args+[self.offset])]
            self.rows=[self.store.inspect_rule(rid) for rid in ids];self.rows.sort(key=lambda r:({'BLOCK':0,'HIGH':1,'LOW':2}[r['risk']],r['scope_group'],r['id']));self.table.setRowCount(len(self.rows))
            for i,row in enumerate(self.rows):
                excluded=sum(r['decision_if_active']=='EXCLUDED_RULE' for r in row['matches']);values=(row['risk'],row['state']+' / r'+str(row['revision']),row['rule']['literal'],row['rule']['scope']['object_type']+' / '+row['scope_group'][:12],f"{excluded}／{len(row['matches'])-excluded}",row['id'])
                for j,value in enumerate(values):item=QTableWidgetItem(value);item.setToolTip(value);self.table.setItem(i,j,item)
                if row['id'] in old:self.table.selectRow(i)
            self.count.setText(f'本頁{len(self.rows)}／搜尋總數{total}／全規則{self.store.count("RULE")}；風險與scope固定排序僅本頁');self.previous_button.setEnabled(self.offset>0);self.next_button.setEnabled(self.offset+len(ids)<total)
        except Exception as error:self.rows=[];self.table.setRowCount(0);self.status.setText('規則核對失敗：'+str(error))
        finally:self.loading=False;self.selected()

    def selected(self):
        if self.loading:return
        ids=self.selected_ids();rows=[r for r in self.rows if r['id'] in ids];self.details.setPlainText(json.dumps(rows,ensure_ascii=False,indent=2))
        for button in (self.approve_button,self.reject_button,self.defer_button):button.setEnabled(bool(ids) and not self.window.busy)

    def decide(self,action):
        for button in (self.approve_button,self.reject_button,self.defer_button):button.setEnabled(False)
        try:
            from .training_store import text
            actor=text(self.actor.text(),'審核者',120);reason=text(self.reason.text(),'審核原因');plan=self.store.rule_review_plan(self.selected_ids());self.details.setPlainText(json.dumps(plan,ensure_ascii=False,indent=2))
            summary=f"{action}／{', '.join(plan['ids'])}\n範圍SHA {plan['digest']}\n"+'\n'.join(f"{r['id']} r{r['revision']} {r['risk']}：{len(r['matches'])}候選、作品{', '.join(r['affected_work_ids'])}" for r in plan['rows'])+'\n只啟用訓練候選規則，不改原稿／正式模板。'
            if QMessageBox.question(self,'確認規則審核',summary,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:self.status.setText('已取消，規則未變更');return
            result=self.store.review_rules(plan,action,actor,reason,approved=True,detail_reviewed=self.detail_reviewed.isChecked());self.status.setText('已保存：'+', '.join(r['id']+' '+r['state'] for r in result));self.reload()
        except Exception as error:self.status.setText('未審核：'+str(error))
        finally:self.selected()

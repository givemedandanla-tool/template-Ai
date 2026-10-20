"""Confirmed correction evidence stays pending until generalized and validated."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gui import MainWindow
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QComboBox,QPushButton,QTableWidget,QTableWidgetItem,QPlainTextEdit,QInputDialog,QMessageBox
from .training_store import TrainingStore,text


class RuleHintsPanel(QWidget):
    def __init__(self,window,parent=None):
        super().__init__(parent);self.host_window: MainWindow=window;self.store=TrainingStore(window.library);self.offset=0;self.rows=[]
        layout=QVBoxLayout(self);bar=QHBoxLayout();self.query=QLineEdit();self.query.setPlaceholderText('本頁修正案例／來源／原因搜尋');self.query.textChanged.connect(self.reload);bar.addWidget(self.query);self.order=QComboBox();self.order.addItems(['RISK','SOURCE','STATE']);self.order.currentIndexChanged.connect(self.reload);bar.addWidget(self.order);layout.addLayout(bar)
        self.status=QLabel('修正立即作用於確切作品；候選線索不等於已驗證通用規則。人物／公司歸屬不從單例擴散。');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['風險／狀態','來源作品','已知影響','線索ID']);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.SingleSelection);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.itemSelectionChanged.connect(self.selected);layout.addWidget(self.table,1)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details,2);bar=QHBoxLayout()
        for label,fn in [('上一頁',lambda:self.page(-200)),('下一頁',lambda:self.page(200)),('刷新',self.reload),('定位來源作品',self.locate),('暫緩',lambda:self.decide('DEFERRED')),('拒絕',lambda:self.decide('REJECTED'))]:button=QPushButton(label);button.clicked.connect(fn);bar.addWidget(button)
        layout.addLayout(bar);self.reload()

    def page(self,delta):self.offset=max(0,self.offset+delta);self.reload()
    def reload(self,*_):
        self.rows=[r for r in self.store.records('RULE_HINT',self.offset,200) if all(word in json.dumps(r,ensure_ascii=False).casefold() for word in self.query.text().casefold().split())]
        self.rows.sort(key=lambda r:(r.get({'SOURCE':'work_id','STATE':'state'}.get(self.order.currentText(),'risk'),''),r['id']));self.table.setRowCount(len(self.rows))
        for i,row in enumerate(self.rows):
            count=self.host_window.library.db.execute("SELECT count(*) FROM templates WHERE json_extract(payload,'$.source_work_id')=?",(row['work_id'],)).fetchone()[0]
            for j,value in enumerate((row['risk']+'／'+row['state'],row['work_id'],f'實際1作品＋{count}引用模板；跨作品適用未知',row['id'])):self.table.setItem(i,j,QTableWidgetItem(value))
        self.status.setText(f'本頁讀取最多200線索，篩選後{len(self.rows)}；高風險逐條，支持案例1件，反例／通用前提／泛化測試未取得則明示缺漏。')

    def current(self):
        index=self.table.currentRow()
        if not 0<=index<len(self.rows):raise ValueError('先選確切修正線索')
        return self.rows[index]

    def selected(self):
        try:
            row=self.current();self.details.setPlainText(json.dumps(row,ensure_ascii=False,indent=2)+'\n適用：此來源／作品／欄位的已確認修正。\n支持案例：1件；反例：尚未取得。\n跨作品語意／歸屬適用：未知；泛化測試：未執行，不能啟用或批次核准。\n通用雜訊規則需另在既有來源觀察／規則審核中心提供正反例與範圍；語意模型需另行授權及留出驗證。')
        except ValueError:self.details.clear()

    def locate(self):
        try:
            from .training_navigation import locate_work
            row=self.current();after=row['after'];locate_work(self.host_window,row['work_id'],[after['slot_id']] if after.get('slot_id') else [])
        except Exception as error:self.status.setText(str(error))

    def decide(self,state):
        try:
            row=self.current();reason,ok=QInputDialog.getText(self,'逐條修正線索審核','保存原因；不撤銷此作品事實，不修改其他作品')
            if not ok:return
            text(reason,'審核原因')
            if QMessageBox.question(self,'確認'+state,row['id']+'\n'+reason)!=QMessageBox.Yes:return
            with self.store.transaction():
                current=self.store.get('RULE_HINT',row['id'])
                if current['revision']!=row['revision']:raise ValueError('線索已更新，重新核對')
                current.update(state=state,review_actor='LOCAL_OPERATOR',review_reason=reason);self.store._write('RULE_HINT',row['id'],current,row['revision'],'correction_hint_'+state.lower())
            self.reload()
        except Exception as error:self.status.setText('未審核：'+str(error))

"""人物 ROOT 公司卡片的尺寸限定匹配與確切版本選擇。"""
from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,
    QPushButton,QTableWidget,QTableWidgetItem,QMessageBox)

from .input_graph import fingerprint
from .logo_compare import LogoCompareWidget
from .logo_store import LogoStore


class LogoChoiceDialog(QDialog):
    def __init__(self,window,graph,company_id,parent=None,width=None,height=None):
        super().__init__(parent or window)
        self.window,self.graph,self.entity_id=window,graph,company_id
        self.graph_signature=fingerprint(graph.data)
        self.uses_window_size=width is None and height is None
        self.width,self.height=(window.out_w.value(),window.out_h.value()) if self.uses_window_size else (width,height)
        self.store=LogoStore(window.library);self.selected_asset=None
        self.setWindowTitle('此公司／此卡片尺寸的完整 Logo 選擇');self.resize(1190,760)
        layout=QVBoxLayout(self);self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);layout.addWidget(self.status)
        bar=QHBoxLayout();self.company=QComboBox();self.company.addItem('先核對確切資產公司身分',None)
        for company in self.store.companies():
            if company['name']==graph.label(company_id):self.company.addItem(company['name']+'／'+company['id'],company['id'])
        binding=self.store.db.execute('SELECT company_id FROM logo_entity_bindings WHERE entity_id=?',(company_id,)).fetchone()
        if binding:self.company.setCurrentIndex(max(0,self.company.findData(binding[0])))
        bar.addWidget(self.company);button=QPushButton('確認當次公司與資產身分對應');button.clicked.connect(self.bind);bar.addWidget(button)
        button=QPushButton('查看審核狀態／匯入新 Logo');button.clicked.connect(self.library);bar.addWidget(button);layout.addLayout(bar)
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['確切版本','公司身分','卡片尺寸 mm','來源／版本','核准狀態']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.currentCellChanged.connect(self.preview);layout.addWidget(self.table)
        self.compare=LogoCompareWidget();layout.addWidget(self.compare,2)
        bar=QHBoxLayout();self.choose_button=QPushButton('採用明確選定版本到公司卡片');self.choose_button.clicked.connect(self.choose);bar.addWidget(self.choose_button);cancel=QPushButton('返回，不變更原引用');cancel.clicked.connect(self.reject);bar.addWidget(cancel);layout.addLayout(bar)
        self.refresh()

    def refresh(self):
        current=self.graph.entity(self.entity_id)['logo_id']
        self.match=self.store.match(self.entity_id,self.graph.label(self.entity_id),self.width,self.height,selected_id=current or None)
        self.rows=self.match['candidates'];self.table.blockSignals(True);self.table.setRowCount(len(self.rows))
        for i,asset in enumerate(self.rows):
            for col,value in enumerate((asset['id'],asset['company']+'／'+asset['company_id'],
                f'{asset["width_mm"]:g}×{asset["height_mm"]:g}',f'v{asset["version"]}／'+asset['origin'],'已核准；當次輸出未驗證')):
                self.table.setItem(i,col,QTableWidgetItem(value))
        selected=self.match.get('selected');index=next((i for i,a in enumerate(self.rows) if selected and a['id']==selected['id']),-1)
        self.table.setCurrentCell(index,0);self.table.blockSignals(False)
        self.status.setText(f'當次公司 {self.graph.label(self.entity_id)}／{self.entity_id}；卡片 {self.width:g}×{self.height:g} mm；'+self.match['state']+'：'+self.match['reason'])
        self.choose_button.setEnabled(bool(self.rows));self.preview()

    def bind(self):
        try:
            identity=self.company.currentData()
            if not identity:raise ValueError('名稱只是線索，請明確選定已核對的公司身分')
            affected=[self.graph.label(eid)+'／'+eid for eid in self.graph.references(self.entity_id)]
            if QMessageBox.question(self,'核對實際公司與共享影響',self.company.currentText()+'\n當次實體：'+self.entity_id+'\n影響：'+str(affected)+'\n只建立資產身分對應，不改其他公司／版型，確認？')!=QMessageBox.Yes:return
            self.store.bind(self.entity_id,identity,self.graph.label(self.entity_id),True);self.refresh()
        except ValueError as error:self.status.setText('未確認：'+str(error))

    def preview(self,*_):
        if not hasattr(self,'compare'):return
        index=self.table.currentRow()
        if 0<=index<len(self.rows):self.compare.show_assets(self.rows[index],width=30,height=15)
        else:
            # 清除先前選取圖像，不讓空選取仍看見另一個公司的商標。
            self.compare.show_assets({},width=30,height=15)

    def choose(self):
        try:
            index=self.table.currentRow()
            if not 0<=index<len(self.rows):raise ValueError('請選一個同尺寸的確切版本；多版本不預選')
            asset=deepcopy(self.rows[index])
            if fingerprint(self.graph.data)!=self.graph_signature or (self.uses_window_size and [self.window.out_w.value(),self.window.out_h.value()]!=[self.width,self.height]):raise ValueError('當次公司或尺寸已變更，重新核對')
            if QMessageBox.question(self,'確切版本與尺寸引用',asset['company']+'／'+asset['id']+f'／v{asset["version"]}\n'+f'{self.width:g}×{self.height:g} mm；仍須重新排版與輸出驗證。確認？')!=QMessageBox.Yes:return
            fresh=self.store.match(self.entity_id,self.graph.label(self.entity_id),self.width,self.height,selected_id=asset['id'])
            if not fresh['selected'] or fresh['selected']!=asset:raise ValueError('來源／版本／身分已變更，不套用過期選擇')
            self.selected_asset=asset;self.accept()
        except (ValueError,KeyError,OSError) as error:self.status.setText('未選用：'+str(error))

    def library(self):
        from .logo_library_dialog import LogoLibraryDialog
        dialog=LogoLibraryDialog(self.window)
        for i in range(dialog.tree.topLevelItemCount()):
            node=dialog.tree.topLevelItem(i)
            if node.data(0,Qt.UserRole)==[self.width,self.height]:dialog.tree.setCurrentItem(node);break
        dialog.company.setCurrentIndex(max(0,dialog.company.findData(self.company.currentData())))
        dialog.query.setText(self.graph.label(self.entity_id))
        dialog.exec()
        selected=self.company.currentData();self.company.clear();self.company.addItem('先核對確切資產公司身分',None)
        for company in self.store.companies():
            if company['name']==self.graph.label(self.entity_id):self.company.addItem(company['name']+'／'+company['id'],company['id'])
        self.company.setCurrentIndex(max(0,self.company.findData(selected)));self.refresh()

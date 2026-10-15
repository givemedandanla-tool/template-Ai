"""Physical-size view over the existing logo table; references never become approvals."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QTreeWidget,QTreeWidgetItem,QTableWidget,QTableWidgetItem,QCheckBox,QPlainTextEdit
import json

class LogoLibraryDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.setWindowTitle('尺寸獨立 Logo 庫／新尺寸唯讀參考');self.resize(950,650);l=QVBoxLayout(self);self.status=QLabel();self.status.setWordWrap(True);l.addWidget(self.status)
        self.reference=QCheckBox('進入新尺寸跨庫參考專區（唯讀、不核准、不跨庫套用）');self.reference.toggled.connect(self.reload);l.addWidget(self.reference)
        self.query=QLineEdit();self.query.setPlaceholderText('在所選尺寸依公司或exact資產ID搜尋');self.query.textChanged.connect(self.selected);l.addWidget(self.query)
        self.tree=QTreeWidget();self.tree.setHeaderLabels(['尺寸 mm／公司／exact資產']);self.tree.itemSelectionChanged.connect(self.selected);l.addWidget(self.tree)
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['公司','來源尺寸mm','資產ID','核准範圍','目標尺寸mm']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);l.addWidget(self.table)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);l.addWidget(self.details);self.reload()
    def reload(self):
        self.assets=self.window.library.logos();self.tree.blockSignals(True);self.tree.clear();sizes=sorted({(a['width_mm'],a['height_mm']) for a in self.assets})
        for size in sizes:
            item=QTreeWidgetItem([f'{size[0]:g}×{size[1]:g} mm']);item.setData(0,Qt.UserRole,list(size));self.tree.addTopLevelItem(item)
            for a in self.assets:
                if (a['width_mm'],a['height_mm'])==size:
                    child=QTreeWidgetItem([a['company']+'／'+a['id']]);child.setData(0,Qt.UserRole,list(size));child.setData(0,Qt.UserRole+1,a['id']);item.addChild(child)
        self.tree.blockSignals(False)
        if self.tree.topLevelItemCount():self.tree.setCurrentItem(self.tree.topLevelItem(0))
        self.selected()
    def selected(self):
        node=self.tree.currentItem();size=node.data(0,Qt.UserRole) if node else None;target=[self.window.out_w.value(),self.window.out_h.value()];q=self.query.text().casefold();reference=self.reference.isChecked()
        self.rows=[a for a in self.assets if (reference or size==[a['width_mm'],a['height_mm']]) and q in (a['company']+' '+a['id']).casefold()];self.table.setRowCount(len(self.rows))
        for i,a in enumerate(self.rows):
            for j,value in enumerate((a['company'],f"{a['width_mm']:g}×{a['height_mm']:g}",a['id'],'來源尺寸已核准／目標未核准' if reference else '僅此尺寸已核准',f'{target[0]:g}×{target[1]:g}' if reference else '不跨尺寸')):self.table.setItem(i,j,QTableWidgetItem(value))
        self.status.setText(('新尺寸唯讀參考專區；目標'+str(target)+'mm；所有跨庫參考均未在目標核准，無加入正式庫按鈕。' if reference else '目前尺寸庫 '+str(size)+' mm；其他尺寸資產不在此清單。')+' AI預測與目標品質審核尚未實作。')
        exact=node.data(0,Qt.UserRole+1) if node else None;asset=next((a for a in self.assets if a['id']==exact),None);self.details.setPlainText(json.dumps(asset,ensure_ascii=False,indent=2) if asset else '選取資產查看既有來源；公司實體ID／原生完整性未知即未核實。')

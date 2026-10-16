"""Descriptive, bounded current distribution with exact drilldown, never an AI quality score."""
import json
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTreeWidget,QTreeWidgetItem,QPlainTextEdit
from .training_store import TrainingStore
from .training_navigation import locate_work


class CoveragePanel(QWidget):
    def __init__(self,window,parent=None):
        super().__init__(parent);self.window=window;self.store=TrainingStore(window.library);self.offset=0;self.report=None;layout=QVBoxLayout(self);bar=QHBoxLayout();self.previous_button=QPushButton('上頁掃描');self.next_button=QPushButton('下頁掃描');self.reload_button=QPushButton('重算目前範圍');self.previous_button.clicked.connect(lambda:self.page(-200));self.next_button.clicked.connect(lambda:self.page(200));self.reload_button.clicked.connect(self.reload)
        for b in (self.previous_button,self.next_button,self.reload_button):bar.addWidget(b)
        layout.addLayout(bar);self.status=QLabel('僅描述來源／作品／可信樣本／資料集分布。不用樣本數判品質，不推薦補樣；原生效果／客戶身份UNKNOWN。');self.status.setWordWrap(True);layout.addWidget(self.status);self.count=QLabel();self.count.setWordWrap(True);layout.addWidget(self.count);self.tree=QTreeWidget();self.tree.setHeaderLabels(['分組／精確內容','本頁作品數／ID']);self.tree.itemSelectionChanged.connect(self.selected);layout.addWidget(self.tree,2);self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details,2);self.locate_button=QPushButton('定位選中exact作品');self.locate_button.clicked.connect(self.locate);layout.addWidget(self.locate_button);self._loaded=False
    def showEvent(self,event):
        super().showEvent(event)
        if not self._loaded:self.reload()
    def page(self,delta):self.offset=max(0,self.offset+delta);self.reload()
    def reload(self,*_):
        self._loaded=True
        from PySide6.QtCore import Qt
        try:
            self.report=self.store.coverage_report(self.offset);self.tree.clear()
            for axis,values in self.report['facets'].items():
                parent=QTreeWidgetItem([axis,'分母：本頁已掃作品']);self.tree.addTopLevelItem(parent)
                for value,ids in values.items():
                    group=QTreeWidgetItem([value,str(len(ids))]);parent.addChild(group)
                    for wid in ids:
                        row=next(r for r in self.report['artworks'] if r['work_id']==wid);item=QTreeWidgetItem([wid,row['facts_state']]);item.setData(0,Qt.UserRole,wid);group.addChild(item)
            totals=self.report['totals'];scope=self.report['scan'];self.count.setText(f"總來源{totals['sources']}／作品{totals['artworks']}／無作品來源{totals['sources_without_artworks']}／保存樣本{totals['stored_samples']}／資料集{totals['datasets']}；本頁起點{self.offset}，掃來源{scope['sources']}、作品{scope['artworks']}、樣本{scope['samples']}、資料集{scope['datasets']}；目前樣本{self.report['sample_states']}。各分類重疊，資料集角色以entry出現次數計。");self.details.setPlainText(json.dumps(self.report,ensure_ascii=False,indent=2));self.status.setText('；'.join(self.report['notices']) or '空庫目前沒有分布；不代表品質或正式無解');self.previous_button.setEnabled(self.offset>0);self.next_button.setEnabled(any(self.offset+200<totals[k] for k in ('sources','artworks','stored_samples','datasets')))
        except Exception as error:self.report=None;self.tree.clear();self.status.setText('覆蓋統計未完成：'+str(error));self.details.clear()
        self.selected()
    def selected(self):
        from PySide6.QtCore import Qt
        item=self.tree.currentItem();wid=item.data(0,Qt.UserRole) if item else None;self.locate_button.setEnabled(bool(wid) and not self.window.busy)
        if wid and self.report:self.details.setPlainText(json.dumps(next(r for r in self.report['artworks'] if r['work_id']==wid),ensure_ascii=False,indent=2))
    def locate(self):
        from PySide6.QtCore import Qt
        try:
            item=self.tree.currentItem();wid=item.data(0,Qt.UserRole) if item else None
            if not wid or not self.report:raise ValueError('展開分組，選取exact作品，不任意選第一件')
            row=next(r for r in self.report['artworks'] if r['work_id']==wid)
            if self.store.library.artwork(wid)['revision']!=row['work_revision']:raise ValueError('工作版次已變更，重新計數')
            locate_work(self.window,wid);self.status.setText('已定位exact作品；統計未改source／labels／samples／dataset')
        except Exception as error:self.status.setText('未定位：'+str(error))

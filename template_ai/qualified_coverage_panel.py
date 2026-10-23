"""Primary C-scope coverage view; inventory is a separately labelled legacy view."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gui import MainWindow
from PySide6.QtCore import Qt,QDateTime
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QComboBox,QTreeWidget,QTreeWidgetItem,QPlainTextEdit,QHeaderView
from shiboken6 import isValid
from .training_store import TrainingStore

VIEWS=(('目前已核准可訓練','APPROVED_TRAINABLE'),('候選待審','CANDIDATE_PENDING'),('已排除／污染隔離','EXCLUDED'),('調參驗證','VALIDATION'),('獨立品質保留集','QUALITY_HOLDOUT'),('精確訓練資料集版本','EXACT_DATASET'))
AXES=dict(size='實體尺寸',people='人數',companies='公司數',logo='Logo類型',native_text='原生文字證據',special_effect='特殊文字效果',ocr='OCR補救',multi_work='單檔多作品')
VALUES=dict(DERIVATIVE_PATH_NATIVE_TEXT_UNKNOWN='衍生向量路徑；原生文字／外框來源未知',DERIVATIVE_TEXT_NATIVE_UNVERIFIED='衍生檔文字；原生可編輯性未核實',DERIVATIVE_EFFECT_ATTRIBUTES_NATIVE_TYPE_UNKNOWN='衍生檔效果屬性；原生效果類型未知',LOCAL_OCR_EXECUTION_RECORDED_NATIVE_UNKNOWN='有本機OCR執行紀錄；原生類型未知',UNKNOWN='未知／未核實',VECTOR_ONLY='已核對純圖形',TEXT_AND_VECTOR='已核對完整複合圖文',TEXT_ONLY='已核對文字型Logo',NO_LOGO='已核對無Logo',MULTIPLE_VERIFIED_TYPES='多種已核對類型',SOURCE_HAS_MULTIPLE_REGISTERED_WORKS_COMPLETENESS_UNKNOWN='來源登錄多件作品；原稿完整性未知',SOURCE_HAS_ONE_REGISTERED_WORK_COMPLETENESS_UNKNOWN='來源登錄一件作品；原稿完整性未知')


class QualifiedCoveragePanel(QWidget):
    def __init__(self,window,parent=None):
        super().__init__(parent);self.host_window: MainWindow=window;self.store=TrainingStore.bind(window.library);self.report=None;self.loading=False;self.loaded=False;self.offset=0;self.dataset_offset=0;self.history_offset=0;self.historical=False;self.generation=0
        layout=QVBoxLayout(self);bar=QHBoxLayout();self.collection=QComboBox()
        for label,value in VIEWS:self.collection.addItem(label,value)
        bar.addWidget(self.collection);self.dataset=QComboBox();self.dataset.addItem('先選明確資料集版本',None);self.dataset.setEnabled(False);bar.addWidget(self.dataset,1);self.button(bar,'資料集前50',lambda:self.datasets(-50));self.button(bar,'資料集後50',lambda:self.datasets(50));layout.addLayout(bar)
        bar=QHBoxLayout();self.previous_button=self.button(bar,'前50筆',lambda:self.reload(max(0,self.offset-50)));self.next_button=self.button(bar,'後50筆',lambda:self.reload(self.offset+50));self.reload_button=self.button(bar,'依目前資格重算',lambda:self.reload(0));layout.addLayout(bar)
        self.status=QLabel('只描述明確資料集合的當時計數；不以數量判定品質，不提供補樣建議。');self.status.setTextFormat(Qt.PlainText);self.status.setWordWrap(True);layout.addWidget(self.status);self.count=QLabel();self.count.setTextFormat(Qt.PlainText);self.count.setWordWrap(True);layout.addWidget(self.count)
        self.tree=QTreeWidget();self.tree.setHeaderLabels(['可核對分類／具名來源','本頁作品數／去重標記權重']);self.tree.header().setSectionResizeMode(0,QHeaderView.Stretch);self.tree.header().setSectionResizeMode(1,QHeaderView.ResizeToContents);layout.addWidget(self.tree,2);self.details=QPlainTextEdit();self.details.setReadOnly(True);self.details.setMaximumHeight(130);layout.addWidget(self.details)
        bar=QHBoxLayout();self.locate_button=self.button(bar,'返回選中來源與標記核對',self.locate);self.samples_button=self.button(bar,'開啟既有可信樣本審核',self.samples);layout.addLayout(bar)
        bar=QHBoxLayout();self.history=QComboBox();self.history.addItem('歷史快照僅當時計數',None);bar.addWidget(self.history,1);self.button(bar,'歷史前50',lambda:self.histories(-50));self.button(bar,'歷史後50',lambda:self.histories(50));self.button(bar,'檢視選中歷史快照',self.load_history);layout.addLayout(bar)
        self.collection.currentIndexChanged.connect(lambda:self.guard(self.changed));self.dataset.currentIndexChanged.connect(lambda:self.guard(lambda:self.reload(0)));self.tree.itemSelectionChanged.connect(self.selected)

    def button(self,bar,label,action):
        button=QPushButton(label);button.clicked.connect(lambda:self.guard(action));bar.addWidget(button);return button
    def guard(self,action):
        try:action()
        except (ValueError,KeyError,OSError,TypeError) as error:self.status.setText('未執行：'+str(error))
    def host(self):
        parent=self.parentWidget()
        while parent is not None and not hasattr(parent,'quality_panel'):parent=parent.parentWidget()
        if parent is None:raise ValueError('請由既有訓練中心開啟覆蓋統計')
        return parent
    def showEvent(self,event):
        super().showEvent(event)
        if not self.loaded:self.guard(lambda:self.reload(0))
    def request(self,command,payload,callback):
        host=self.host()
        if host.quality_panel.loading:raise ValueError('既有背景核對尚未完成，請稍後重算')
        if self.host_window.busy:raise ValueError('目前已有背景操作，請完成或取消後重算')
        if self.store.library.closed or self.host_window.library is not self.store.library:raise ValueError('專案環境已變更，請重新開啟覆蓋統計')
        self.loading=True;generation=self.generation;self.status.setText('正在本機核對本頁來源與用途，尚未宣稱完成。')
        def done(value):
            if not isValid(self):return
            self.loading=False
            if generation!=self.generation:self.report=None;self.tree.clear();self.status.setText('選擇已變更，舊統計不套用；請重算目前範圍。');return
            callback(value)
        def failed(error):
            if not isValid(self):return
            self.loading=False;self.status.setText('統計未完成，未沿用舊數值：'+str(error));self.report=None;self.tree.clear();self.count.clear();self.details.clear();self.locate_button.setEnabled(False)
        host.quality_panel.request('SAMPLE_'+command,payload,done,on_error=failed)

    def changed(self):
        self.generation+=1;self.report=None;self.tree.clear();self.count.clear()
        self.dataset_offset=0;self.dataset.blockSignals(True);self.dataset.clear();self.dataset.addItem('先選明確資料集版本',None);self.dataset.blockSignals(False)
        specific=self.collection.currentData() in ('EXACT_DATASET','QUALITY_HOLDOUT');self.dataset.setEnabled(specific)
        if self.collection.currentData()=='EXACT_DATASET':self.datasets(0)
        else:self.reload(0)
    def datasets(self,delta=0):
        if self.collection.currentData() not in ('EXACT_DATASET','QUALITY_HOLDOUT'):raise ValueError('此檢視未限定單一資料集；需先切換精確資料集或保留集')
        kind='QUALITY_SET' if self.collection.currentData()=='QUALITY_HOLDOUT' else 'DATASET';self.dataset_offset=max(0,self.dataset_offset+delta)
        def loaded(value):
            self.dataset.blockSignals(True);self.dataset.clear();self.dataset.addItem('全部已登錄保留集' if kind=='QUALITY_SET' else '先選明確資料集版本',None)
            for row in value['rows']:self.dataset.addItem(row['label']+'／版本'+str(row['revision'])+'／'+row['id'][:8],row['id'])
            self.dataset.blockSignals(False);self.status.setText('資料集目錄每頁50筆；不自動替使用者選取版本。')
        self.request('COVERAGE_DATASETS',dict(kind=kind,offset=self.dataset_offset),loaded)
    def reload(self,offset=0):
        if self.collection.currentData()=='EXACT_DATASET' and not self.dataset.currentData():self.status.setText('先明確選取精確資料集版本；沒有任選第一版。');return
        self.generation+=1;self.report=None;self.tree.clear();self.count.clear();self.offset=offset;self.historical=False
        def loaded(value):self.loaded=True;self.report=value;self.display()
        self.request('COVERAGE',dict(collection=self.collection.currentData(),dataset_id=self.dataset.currentData(),offset=offset),loaded)
    def display(self):
        value=self.report;self.tree.clear();rows={row.get('work_id'):row for row in value['rows'] if row.get('work_id')};counts=value['counts'];collection=dict((data,label) for label,data in VIEWS).get(value['collection'],value['collection']);prefix='歷史快照（當時集合：'+collection+'），只供對帳；需要重算才有目前資格。' if self.historical else '本次資料集合：'+collection
        self.count.setText(prefix+'\n掃描'+str(counts['scanned_record_occurrences'])+'／登錄範圍'+str(value['roster_total'])+'；符合'+str(counts['matching_record_occurrences'])+('、當時核實' if self.historical else '、本次核實')+str(counts['currently_verified_occurrences'])+'。\n'+('當時有效來源檔' if self.historical else '本頁有效來源檔')+str(counts['distinct_source_files'])+'／作品'+str(counts['distinct_artworks'])+'／精確內容'+str(counts['exact_content_groups'])+'／去重標記權重'+str(counts['deduplicated_approved_label_weights'])+'／已登錄相關群組'+str(counts['declared_related_groups'])+'；獨立性未由件數決定。')
        if value['collection']=='QUALITY_HOLDOUT':self.count.setText(self.count.text()+'\n其中已使用／曝光成員：'+str(counts.get('exposed_or_consumed_holdout_members',0))+'筆；不授予新的獨立驗收資格。')
        for axis,values in value['facets'].items():
            parent=QTreeWidgetItem([AXES.get(axis,axis),'分類重疊，分母僅本掃描集合']);self.tree.addTopLevelItem(parent)
            for category,work_ids in values.items():
                group=QTreeWidgetItem([VALUES.get(category,category),str(len(work_ids))+'／'+str(value['facet_label_weights'].get(axis,{}).get(category,0))]);parent.addChild(group)
                for wid in work_ids:
                    row=rows[wid];item=QTreeWidgetItem([row.get('work_name','歷史作品／'+wid[:12])+'／'+row.get('source_name','來源參照'),row['state']+'／'+row['role']]);item.setData(0,Qt.UserRole,wid);group.addChild(item)
        self.status.setText('；'.join(value['notices']));self.details.setPlainText('統計時間：'+QDateTime.fromSecsSinceEpoch(int(value['created'])).toString(Qt.ISODate)+'\n全頁分類可重疊；未知不算已核實類型。\n不以件數判定品質，不生成補樣、訓練或素材搜尋任務。');self.previous_button.setEnabled(self.offset>0 and not self.historical);self.next_button.setEnabled(self.offset+50<value['roster_total'] and not self.historical);self.selected()
    def selected(self):
        item=self.tree.currentItem();wid=item.data(0,Qt.UserRole) if item else None;enabled=bool(wid) and bool(self.report) and not self.loading and not self.historical and not self.host_window.busy;self.locate_button.setEnabled(enabled)
        if wid and self.report:
            row=next(row for row in self.report['rows'] if row.get('work_id')==wid);self.details.setPlainText((row.get('work_name') or '歷史作品')+'\n來源：'+str(row.get('source_name','歷史參照'))+'\n標記／記錄版本：'+str(row['record_revision'])+'；作品版本：'+str(row['work_revision'])+'\n角色：'+row['role']+'；目前狀態：'+row['state']+'\n'+'；'.join(row.get('reasons',[]))+('\n保留集狀態：'+{'EXPOSED_NOT_FRESH':'答案已揭露，不能當新獨立來源','CONSUMED_EXISTING_PROTOCOL_ONLY':'已有固定試驗使用紀錄，只可用於原試驗','REGISTERED_GOLD_FRESHNESS_NOT_GRANTED':'僅已登錄，本頁未授予新獨立驗收資格'}.get(row.get('holdout_state'),'未知') if row.get('holdout_state') else ''))
    def locate(self):
        if self.historical or not self.report:raise ValueError('歷史快照不冒充目前資格，請重算後返回來源')
        if self.store.epoch!=self.report['source_epoch_after_snapshot']:raise ValueError('統計後資料版本已變更，請先重算')
        item=self.tree.currentItem();wid=item.data(0,Qt.UserRole) if item else None
        if not wid:raise ValueError('先展開分類並選取具名作品')
        row=next(row for row in self.report['rows'] if row.get('work_id')==wid);host=self.host()
        if host.facts_panel.has_pending_observation():raise ValueError('來源事實有未套用人工內容；保留原編輯，未切換')
        from .qualified_coverage import QualifiedCoverage
        if QualifiedCoverage(self.host_window.library).stamp(wid)!=row['scope_stamp']:raise ValueError('來源／作品版本已變更，舊統計需重算')
        from .training_navigation import locate_work
        locate_work(self.host_window,wid);host.facts_panel.focus(wid,[]);host.tabs.setCurrentWidget(host.facts_panel);self.status.setText('已返回同一來源畫布與標記；未更動訓練、客戶或模板。')
    def samples(self):
        host=self.host();host.tabs.setCurrentWidget(host.samples_panel);host.samples_panel.open_pool()
    def histories(self,delta=0):
        self.history_offset=max(0,self.history_offset+delta)
        def loaded(value):
            self.history.clear();self.history.addItem('先選歷史快照，不能當目前資格',None)
            for row in value['rows']:self.history.addItem(dict((value,label) for label,value in VIEWS).get(row['collection'],row['collection'])+'／'+QDateTime.fromSecsSinceEpoch(int(row['created'])).toString(Qt.ISODate)+'／'+row['id'][:8],row['id'])
        self.request('COVERAGE_SNAPSHOTS',dict(offset=self.history_offset),loaded)
    def load_history(self):
        if not self.history.currentData():raise ValueError('先明確選取歷史快照')
        def loaded(value):self.report=value['snapshot'];self.historical=True;self.display()
        self.request('COVERAGE_HISTORICAL',dict(identity=self.history.currentData()),loaded)

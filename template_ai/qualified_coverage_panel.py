"""Primary C-scope coverage view; inventory is a separately labelled legacy view."""
from PySide6.QtCore import Qt,QDateTime
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QComboBox,QTreeWidget,QTreeWidgetItem,QPlainTextEdit
from .training_store import TrainingStore

VIEWS=(('目前已核准可訓練','APPROVED_TRAINABLE'),('候選待審','CANDIDATE_PENDING'),('已排除／污染隔離','EXCLUDED'),('調參驗證','VALIDATION'),('獨立品質保留集','QUALITY_HOLDOUT'),('精確訓練資料集版本','EXACT_DATASET'))
AXES=dict(size='實體尺寸',people='人數',companies='公司數',logo='Logo類型',native_text='原生文字證據',special_effect='特殊文字效果',ocr='OCR補救',multi_work='單檔多作品')
VALUES=dict(UNKNOWN='未知／未核實',VECTOR_ONLY='已核對純圖形',TEXT_AND_VECTOR='已核對完整複合圖文',TEXT_ONLY='已核對文字型Logo',NO_LOGO='已核對無Logo',MULTIPLE_VERIFIED_TYPES='多種已核對類型',SOURCE_HAS_MULTIPLE_REGISTERED_WORKS_COMPLETENESS_UNKNOWN='來源登錄多件作品；原稿完整性未知',SOURCE_HAS_ONE_REGISTERED_WORK_COMPLETENESS_UNKNOWN='來源登錄一件作品；原稿完整性未知')


class QualifiedCoveragePanel(QWidget):
    def __init__(self,window,parent=None):
        super().__init__(parent);self.window=window;self.store=TrainingStore.bind(window.library);self.report=None;self.loading=False;self.loaded=False;self.offset=0;self.dataset_offset=0;self.history_offset=0;self.historical=False
        layout=QVBoxLayout(self);bar=QHBoxLayout();self.collection=QComboBox()
        for label,value in VIEWS:self.collection.addItem(label,value)
        bar.addWidget(self.collection);self.dataset=QComboBox();self.dataset.addItem('先選明確資料集版本',None);bar.addWidget(self.dataset,1);self.button(bar,'資料集前50',lambda:self.datasets(-50));self.button(bar,'資料集後50',lambda:self.datasets(50));layout.addLayout(bar)
        bar=QHBoxLayout();self.previous_button=self.button(bar,'前50筆',lambda:self.reload(max(0,self.offset-50)));self.next_button=self.button(bar,'後50筆',lambda:self.reload(self.offset+50));self.reload_button=self.button(bar,'依目前資格重算',lambda:self.reload(0));layout.addLayout(bar)
        self.status=QLabel('只描述明確資料集合的當時計數；不以數量判定品質，不提供補樣建議。');self.status.setTextFormat(Qt.PlainText);self.status.setWordWrap(True);layout.addWidget(self.status);self.count=QLabel();self.count.setTextFormat(Qt.PlainText);self.count.setWordWrap(True);layout.addWidget(self.count)
        self.tree=QTreeWidget();self.tree.setHeaderLabels(['可核對分類／具名來源','本頁作品數／去重標記權重']);layout.addWidget(self.tree,2);self.details=QPlainTextEdit();self.details.setReadOnly(True);self.details.setMaximumHeight(130);layout.addWidget(self.details)
        bar=QHBoxLayout();self.locate_button=self.button(bar,'返回選中來源與標記核對',self.locate);self.samples_button=self.button(bar,'開啟既有可信樣本審核',self.samples);layout.addLayout(bar)
        bar=QHBoxLayout();self.history=QComboBox();self.history.addItem('歷史快照僅當時計數',None);bar.addWidget(self.history,1);self.button(bar,'歷史前50',lambda:self.histories(-50));self.button(bar,'歷史後50',lambda:self.histories(50));self.button(bar,'檢視選中歷史快照',self.load_history);layout.addLayout(bar)
        self.collection.currentIndexChanged.connect(self.changed);self.dataset.currentIndexChanged.connect(lambda:self.reload(0));self.tree.itemSelectionChanged.connect(self.selected)

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
        self.loading=True;self.status.setText('正在本機核對本頁來源與用途，尚未宣稱完成。')
        def done(value):self.loading=False;callback(value)
        def failed(error):self.loading=False;self.status.setText('統計未完成，未沿用舊數值：'+str(error));self.report=None;self.tree.clear();self.locate_button.setEnabled(False)
        host.quality_panel.request('SAMPLE_'+command,payload,done,on_error=failed)

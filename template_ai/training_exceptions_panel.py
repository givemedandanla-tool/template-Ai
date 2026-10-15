from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QComboBox,QPushButton,QTableWidget,QTableWidgetItem,QPlainTextEdit,QMessageBox,QInputDialog)
from .automatic_training import AutomaticTraining
from .training_exceptions import exception_rows,exclude_work


class TrainingExceptionsPanel(QWidget):
    def __init__(self,window,parent=None):
        super().__init__(parent);self.window=window;self.service=AutomaticTraining(window.library);self.offset=0;self.rows=[]
        layout=QVBoxLayout(self);self.status=QLabel('作品局部隔離；排序不核准資料，其他獨立作品可繼續。');self.status.setWordWrap(True);layout.addWidget(self.status)
        bar=QHBoxLayout();self.query=QLineEdit();self.query.setPlaceholderText('來源／作品／類型／原因');bar.addWidget(self.query)
        self.order=QComboBox()
        for label,key in [('智慧建議：嚴重度與實際影響','SMART'),('依來源','SOURCE'),('依類型','TYPE')]:self.order.addItem(label,key)
        bar.addWidget(self.order);self.severity=QComboBox();self.severity.addItems(['ALL','BLOCK','REVIEW']);bar.addWidget(self.severity)
        button=QPushButton('重新核對');button.clicked.connect(self.reload);bar.addWidget(button);layout.addLayout(bar)
        self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['嚴重程度','作品／來源','問題','實際影響','排序依據']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.ExtendedSelection);layout.addWidget(self.table,2)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details)
        bar=QHBoxLayout()
        for label,fn in [('定位作品／欄位',self.locate),('校正所選作品',self.edit),('只重分析所選作品',self.retry),('明確排除此作品',self.exclude),('上一頁',lambda:self.page(-100)),('下一頁',lambda:self.page(100))]:
            b=QPushButton(label);b.clicked.connect(fn);bar.addWidget(b)
        layout.addLayout(bar);self.query.textChanged.connect(self.reload);self.order.currentIndexChanged.connect(self.reload);self.severity.currentIndexChanged.connect(self.reload);self.table.itemSelectionChanged.connect(self.selected);self.reload()

    def selected_rows(self):return [self.rows[i.row()] for i in self.table.selectionModel().selectedRows() if i.row()<len(self.rows)]

    def reload(self,*_):
        try:
            self.rows=exception_rows(self.window.library,self.query.text(),self.order.currentData(),self.severity.currentText(),self.offset);self.table.setRowCount(len(self.rows))
            for i,row in enumerate(self.rows):
                for col,value in enumerate((row['severity'],row['work_name']+'／'+row['source_id'],row['code']+'：'+row['reason'],str(row['impact_count']),row['ranking_reason'])):
                    cell=QTableWidgetItem(value);cell.setToolTip(value);self.table.setItem(i,col,cell)
            self.status.setText(f'本頁實際{len(self.rows)}項問題；只讀檢查100作品單元，未把未讀頁當例外清零。')
        except Exception as error:self.status.setText('例外索引未完成：'+str(error))

    def page(self,delta):self.offset=max(0,self.offset+delta);self.reload()

    def selected(self):self.details.setPlainText('\n\n'.join(r['work_name']+'：'+r['reason']+'\n'+r['ranking_reason'] for r in self.selected_rows()))

    def current(self):
        rows=self.selected_rows()
        if not rows:raise ValueError('先明確選取作品問題')
        row=rows[0]
        if self.window.library.artwork(row['work_id'])['revision']!=row['work_revision']:raise ValueError('作品已更新，先重新核對')
        return row

    def locate(self):
        try:
            row=self.current();from .training_navigation import locate_work
            locate_work(self.window,row['work_id'],row['slot_ids']);self.status.setText('已定位同一作品／框位，未核准或解除隔離。')
        except Exception as error:self.status.setText(str(error))

    def edit(self):
        try:
            row=self.current();from .annotation_dialog import AnnotationDialog
            dialog=AnnotationDialog(self.window,row['work_id'],self);dialog.exec();dialog.deleteLater();self.reload()
        except Exception as error:self.status.setText('尚未校正：'+str(error))

    def retry(self):
        try:
            ids=sorted({row['work_id'] for row in self.selected_rows()});plan=self.service.retry_plan(ids)
            if QMessageBox.question(self,'精確作品增量重分析','只處理以下作品，其餘不重跑：\n'+'\n'.join(ids))!=QMessageBox.Yes:return
            job=self.service.create_retry(plan,'LOCAL_OPERATOR',True)
            from .automatic_training_dialog import AutomaticTrainingDialog
            dialog=AutomaticTrainingDialog(self.window);dialog.show();dialog.start_job(job)
        except Exception as error:self.status.setText('未重分析：'+str(error))

    def exclude(self):
        try:
            row=self.current();reason,ok=QInputDialog.getText(self,'排除確切作品','不刪除來源、不當作成功或訓練真值，請輸入原因')
            if ok and QMessageBox.question(self,'確認排除',row['work_name']+'\n'+reason)==QMessageBox.Yes:exclude_work(self.service,row['unit_id'],row['unit_revision'],reason,True);self.reload()
        except Exception as error:self.status.setText('未排除：'+str(error))

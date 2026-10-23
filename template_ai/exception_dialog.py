"""Explicit exception review; a ranked suggestion never approves a sample or rule."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gui import MainWindow
import copy
import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QLineEdit,QComboBox,QTableWidget,QTableWidgetItem,QPlainTextEdit,QDialogButtonBox,QMessageBox,QInputDialog)
from .worker_callbacks import JobCallbacks
from .import_exceptions import exception_rows,prepare_retry,apply_action
from .batch_dialog import BatchImportDialog,navigation_clean
from .font_review import fingerprint


class ImportExceptionDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.host_window: MainWindow=window;self.store=window.import_store;self.busy=False;self.runner=None;self.plan=None;self.rows=[];self.generation=0;self.loading=True
        self.setWindowTitle('來源匯入例外中心／安全單件處理');self.resize(1240,850);layout=QVBoxLayout(self)
        self.status=QLabel('真實失敗／中斷待辦；排序建議不解除隔離／不核准訓練或規則。');self.status.setTextFormat(Qt.PlainText);self.status.setWordWrap(True);layout.addWidget(self.status)
        bar=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('搜尋來源／類型／原因／stable ID');self.search.textChanged.connect(self.reload);bar.addWidget(self.search,1)
        self.order=QComboBox()
        for title,value in [('智慧建議（嚴重度→exact影響→stable ID）','SMART'),('依來源','SOURCE'),('依類型','TYPE')]:self.order.addItem(title,value)
        self.order.currentIndexChanged.connect(self.reload);bar.addWidget(self.order)
        self.filter=QComboBox()
        for title,value in [('待處理／隔離','OPEN'),('已明確排除','EXCLUDED'),('全部例外','ALL')]:self.filter.addItem(title,value)
        self.filter.currentIndexChanged.connect(self.reload);bar.addWidget(self.filter)
        self.reload_button=QPushButton('重新載入');self.reload_button.clicked.connect(self.reload);bar.addWidget(self.reload_button);layout.addLayout(bar)
        self.count=QLabel();layout.addWidget(self.count)
        self.repair_button=QPushButton('以實際匯入例外預覽根因／人工恢復');self.repair_button.clicked.connect(self.open_repair);layout.addWidget(self.repair_button)
        self.logo_exceptions=QPushButton('核對不確定／衝突 Logo（按尺寸）');self.logo_exceptions.clicked.connect(self.open_logo_exceptions);layout.addWidget(self.logo_exceptions)
        self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(['狀態／嚴重度','來源／頁次','類型／attempt','exact依賴影響','排序原因','批次／項ID']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.ExtendedSelection);self.table.itemSelectionChanged.connect(self.selected);layout.addWidget(self.table,2)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details,1)
        row=QHBoxLayout();self.preview_button=QPushButton('重新預檢選中失敗／中斷項');self.preview_button.clicked.connect(self.preview_retry);row.addWidget(self.preview_button)
        self.apply_button=QPushButton('核對hash差異並只重試所選項');self.apply_button.clicked.connect(self.apply_retry);row.addWidget(self.apply_button)
        self.exclude_button=QPushButton('確認原因並排除所選項');self.exclude_button.clicked.connect(lambda:self.change_status('EXCLUDE'));row.addWidget(self.exclude_button)
        self.restore_button=QPushButton('明確恢復已排除項');self.restore_button.clicked.connect(lambda:self.change_status('RESTORE'));row.addWidget(self.restore_button);layout.addLayout(row)
        row=QHBoxLayout();self.source=QComboBox();row.addWidget(self.source,1);self.locate_button=QPushButton('定位明確所選登錄來源');self.locate_button.clicked.connect(self.locate);row.addWidget(self.locate_button);layout.addLayout(row)
        close=QDialogButtonBox(QDialogButtonBox.Close);close.rejected.connect(self.reject);layout.addWidget(close);self.loading=False;self.reload()
    def open_repair(self):
        try:
            if self.busy or self.host_window.busy:raise ValueError('匯入仍在執行，請先等待或安全停止')
            rows=self.selection()
            if len(rows)!=1:raise ValueError('一次選一個實際失敗／中斷項；不猜測未登錄作品')
            row=rows[0]
            from .training_quality_dialog import open_repair_center
            open_repair_center(self.host_window,dict(origin='IMPORT_EXCEPTION',batch_id=row['batch_id'],item_id=row['item']['id'],expected_revision=row['revision'],description='核對實際來源匯入例外及人工恢復，不自動訓練'))
        except (ValueError,KeyError) as error:self.status.setText(str(error))

    def open_logo_exceptions(self):
        if self.busy or self.host_window.busy:return
        from .logo_library_dialog import LogoLibraryDialog
        dialog=LogoLibraryDialog(self.host_window,exceptions_only=True);dialog.views.setCurrentIndex(1);dialog.exec()

    def controls(self):
        idle=not self.busy and not self.host_window.busy and not (self.runner and self.runner.isVisible())
        for w in (self.table,self.search,self.order,self.filter,self.reload_button,self.source):w.setEnabled(idle)
        selected=self.selection();self.preview_button.setEnabled(idle and bool(selected));self.apply_button.setEnabled(idle and bool(self.plan));self.exclude_button.setEnabled(idle and bool(selected));self.restore_button.setEnabled(idle and bool(selected));self.locate_button.setEnabled(idle and self.source.count()>0)
    def selection(self):return [self.rows[i.row()] for i in self.table.selectionModel().selectedRows() if i.row()<len(self.rows)]
    def invalidate(self):self.plan=None;self.generation+=1;self.apply_button.setEnabled(False)
    def reload(self,*_):
        if self.loading or self.busy or (self.runner and self.runner.isVisible()):return
        keys={r['key'] for r in self.selection()};self.invalidate();self.loading=True
        try:
            self.rows=exception_rows(self.host_window.library,self.store,self.search.text(),self.order.currentData(),self.filter.currentData());self.table.setRowCount(len(self.rows))
            for i,r in enumerate(self.rows):
                item=r['item'];values=[item['status']+'／'+str(r['severity']),Path(item['path']).name+'／p'+str(item['page']),r['type']+'／'+str(item['attempts']),r['ranking_reason'].split('；')[1],r['ranking_reason'],r['key']]
                for c,value in enumerate(values):
                    cell=QTableWidgetItem(value);cell.setData(Qt.UserRole,r['key']);cell.setToolTip(item['path'] if c==1 else value);self.table.setItem(i,c,cell)
            self.table.setColumnWidth(0,135);self.table.setColumnWidth(1,205);self.table.setColumnWidth(2,130);self.table.setColumnWidth(3,205);self.table.setColumnWidth(4,280)
            self.table.clearSelection()
            for i,r in enumerate(self.rows):
                if r['key'] in keys:
                    from PySide6.QtCore import QItemSelectionModel
                    self.table.selectionModel().select(self.table.model().index(i,0),QItemSelectionModel.Select|QItemSelectionModel.Rows)
            self.count.setText(str(len(self.rows))+'個實際符合例外；來源保留。客戶依賴UNKNOWN；未宣稱例外已清零或模型已訓練。')
        except Exception as error:self.rows=[];self.table.setRowCount(0);self.status.setText('例外索引受阻：'+str(error))
        finally:self.loading=False;self.selected()
    def selected(self):
        if self.loading:return
        self.invalidate();rows=self.selection();self.details.setPlainText(json.dumps(rows,ensure_ascii=False,indent=2));self.source.clear()
        for sid in sorted({sid for row in rows for sid in row['source_ids']}):self.source.addItem(Path(self.host_window.library.source(sid)['current_path']).name+'／'+sid,sid)
        self.controls()
    def scoped(self):
        rows=self.selection()
        if not rows or len({r['batch_id'] for r in rows})!=1:raise ValueError('請明確選取同一批次；跨批次不暗中拆分／套用')
        b=self.store.get(rows[0]['batch_id'])
        if b['revision']!=rows[0]['revision']:raise ValueError('批次已異動，請重新載入')
        return rows,b
    def preview_retry(self):
        if self.busy or self.host_window.busy:return
        try:rows,b=self.scoped()
        except Exception as error:self.status.setText(str(error));return
        rows=copy.deepcopy(rows);sources=self.host_window.library.list_sources();self.invalidate();generation=self.generation;self.busy=True;self.controls();self.status.setText('背景重新核對所選來源；不開始匯入。')
        def work():
            try:return {'plan':prepare_retry(rows,sources)}
            except Exception as error:return {'error':str(error) or type(error).__name__}
        def done(result):
            self.busy=False
            try:
                if 'error' in result:raise ValueError(result['error'])
                if generation!=self.generation or self.store.get(b['id'])['revision']!=b['revision']:raise ValueError('背景核驗期間範圍／版次異動，預覽失效')
                self.plan=result['plan'];report=copy.deepcopy(self.plan)
                for r in report['items'].values():r['proof']=r['proof'].__dict__
                self.details.setPlainText(json.dumps(report,ensure_ascii=False,indent=2));self.status.setText('已核對舊／新hash差異；仍未解除隔離，須明確確認才只重試所選項。')
            except Exception as error:self.plan=None;self.status.setText('未完成：'+str(error))
            finally:self.controls()
        try:self.host_window.run_job('例外來源重試預檢',work,JobCallbacks(done,lambda error:done({'error':str(error)})))
        except Exception as error:self.busy=False;self.plan=None;self.status.setText(str(error));self.controls()
    def apply_retry(self):
        if not self.plan or self.busy or self.host_window.busy:return
        plan=self.plan;before=fingerprint({'batch':plan['batch_id'],'revision':plan['revision'],'ids':plan['ids'],'items':{i:{**x,'proof':x['proof'].__dict__} for i,x in plan['items'].items()}})
        message='只重試 '+str(len(plan['ids']))+' 項；SUCCESS／其他READY項保持。\n'+'\n'.join(i+' · '+('內容異動' if x['changed'] else '同hash')+'\n'+str(x['old_hash'])+' → '+x['new_hash'] for i,x in list(plan['items'].items())[:5])+'\n變更內容會另登錄來源，不覆寫原來源／作品／模板。'
        if QMessageBox.question(self,'核對精確重試與hash差異',message,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        try:
            current=fingerprint({'batch':plan['batch_id'],'revision':plan['revision'],'ids':plan['ids'],'items':{i:{**x,'proof':x['proof'].__dict__} for i,x in plan['items'].items()}})
            if self.plan is not plan or before!=current or self.host_window.busy:raise ValueError('確認期間候選／背景狀態異動，請重驗')
            batch=apply_action(self.store,plan['batch_id'],plan['revision'],plan['ids'],'RETRY',plan=plan,confirmed=True);self.invalidate();self.runner=BatchImportDialog(self.host_window);self.runner.setParent(self,Qt.Dialog);self.runner.setWindowModality(Qt.WindowModal);self.runner.batch=batch;self.runner.render(batch['items']);self.runner.refresh_history();self.runner.setWindowTitle('明確選中例外的單件重試');self.runner.show();self.runner.start_run(plan['ids']);self.runner.finished.connect(self.runner_closed);self.controls()
        except Exception as error:self.status.setText('重試未套用：'+str(error));self.controls()
    def runner_closed(self,*_):
        old=self.runner;self.runner=None
        if old:old.deleteLater()
        self.reload()
    def change_status(self,action):
        if self.busy or self.host_window.busy:return
        try:rows,b=self.scoped()
        except Exception as error:self.status.setText(str(error));return
        reason=''
        if action=='EXCLUDE':
            reason,ok=QInputDialog.getText(self,'明確排除原因','不删除來源／不等於成功或可信樣本，請輸入原因：')
            if not ok:return
        ids=sorted(r['item']['id'] for r in rows);selection_before=[r['key'] for r in rows];generation=self.generation
        if QMessageBox.question(self,'核對例外狀態範圍',action+'／'+str(len(ids))+'項\n'+'\n'.join(ids[:8])+'\n排除／恢復不批准規則或訓練。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        try:
            if generation!=self.generation or [r['key'] for r in self.selection()]!=selection_before or self.host_window.busy:raise ValueError('確認期間範圍異動')
            apply_action(self.store,b['id'],b['revision'],ids,action,reason=reason,confirmed=True);self.reload();self.status.setText('已保存 '+action+' 與歷史；原始來源、其他項、作品／規則未變。')
        except Exception as error:self.status.setText('未套用：'+str(error));self.controls()
    def locate(self):
        if self.busy or self.host_window.busy or not self.source.currentData():return
        if not navigation_clean(self.host_window):self.status.setText('主工作台尚未套用手工屬性，先明確保存／取消再定位');return
        sid=self.source.currentData();self.host_window.refresh_sources(sid);self.host_window.tabs.setCurrentIndex(0);self.status.setText('已定位精確登錄來源；視覺／資料正確性未自動批准。')
    def reject(self):
        if self.busy:return
        if self.runner and self.runner.isVisible():self.runner.reject();return
        super().reject()
    def closeEvent(self,event):
        if self.busy or (self.runner and self.runner.isVisible()):event.ignore();self.reject()
        else:super().closeEvent(event)

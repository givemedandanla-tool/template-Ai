"""Per-file review, real worker progress and exact safe retry selection."""
from copy import deepcopy
import threading
from pathlib import Path
from PySide6.QtCore import Qt,QObject,Signal,QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QTableWidget,QTableWidgetItem,QLineEdit,QComboBox,QPushButton,QPlainTextEdit,QMessageBox
from .worker_callbacks import JobCallbacks
from .output_batch import OutputBatch
from .multi_size import MultiSizeWorkflow

class Progress(QObject):updated=Signal(object)

class OutputBatchDialog(QDialog):
    def __init__(self,parent,plan):
        super().__init__(parent);self.owner=parent;self.window=parent.window;self.engine=OutputBatch(parent.service,plan);self.running=False;self.cancel=threading.Event();self.controls=[];self.setWindowTitle('逐檔FINAL／PREVIEW清單、更名與安全重試');self.resize(1350,780);self.progress=Progress(self);self.progress.updated.connect(self.update_row,Qt.QueuedConnection)
        layout=QVBoxLayout(self);self.status=QLabel('確認前不寫檔。新增預設不覆寫；覆寫將保留原檔並重新核對版本，競爭衝突時停止。');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.table=QTableWidget(len(self.engine.items),7);self.table.setHorizontalHeaderLabels(['尺寸／類型／格式','預計檔名（可更名）','衝突動作','實際狀態','已嘗試','目的地／原因','暫存／原檔恢復位置']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.ExtendedSelection);layout.addWidget(self.table,2)
        for i,row in enumerate(self.engine.items):
            name=QLineEdit(Path(row['path']).name);action=QComboBox();action.addItem('更名／新增（不覆寫）','CREATE');action.addItem('略過','SKIP');action.addItem('明確覆寫（保留原檔）','OVERWRITE');self.controls.append((name,action));self.table.setCellWidget(i,1,name);self.table.setCellWidget(i,2,action);self.table.setItem(i,0,QTableWidgetItem(row['key']+' mm／'+row['mode']+'／'+Path(row['path']).suffix));self.update_row(row)
        self.table.horizontalHeader().setStretchLastSection(True);self.table.resizeColumnsToContents();bar=QHBoxLayout();self.start=self.button(bar,'核對完整清單並輸出',lambda:self.run(False));self.retry=self.button(bar,'只重試選取的可恢復失敗',lambda:self.run(True));self.retry.setEnabled(False);self.button(bar,'安全取消',self.cancel.set);self.button(bar,'開啟選取檔案資料夾',self.open_folder);self.button(bar,'確認清理選取暫存（保留正式／原檔）',self.cleanup);layout.addLayout(bar)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);self.details.setPlainText('未輸出尺寸與原因：\n'+str(plan['omitted'])+'\n本次部分輸出：'+str(plan['partial']));layout.addWidget(self.details,1)
    def button(self,bar,label,fn):
        button=QPushButton(label);button.clicked.connect(fn);bar.addWidget(button);return button
    def ids(self):return [str(index.row()) for index in self.table.selectionModel().selectedRows()]
    def update_row(self,row):
        i=int(row['id']);self.table.setItem(i,3,QTableWidgetItem(row['status']));self.table.setItem(i,4,QTableWidgetItem(str(row['attempts'])));self.table.setItem(i,5,QTableWidgetItem(row['path']+'\n'+row.get('reason','')));self.table.setItem(i,6,QTableWidgetItem('暫存：'+str(row.get('stage_path') or '無')+'\n原檔恢復：'+str(row.get('recovery_path') or '無')))
    def run(self,retry):
        try:
            if self.running or self.window.busy:return
            if not self.owner.is_current():raise ValueError('輸入已變更，先回多尺寸重算')
            if self.engine.scope is None:self.engine.configure({row['id']:dict(name=name.text(),action=action.currentData()) for row,(name,action) in zip(self.engine.items,self.controls)})
            selected=self.ids() if retry else [row['id'] for row in self.engine.items if row['status']=='PLANNED']
            if retry and not selected:raise ValueError('先選確切FAILED且可恢復的項目；成功／略過／品質阻擋不重做')
            lines=[r['action']+'／'+r['mode']+'／'+r['path']+'／既存版本 '+str(r.get('expected_target')) for r in self.engine.items if r['id'] in selected or (not retry and r['status']=='SKIPPED')]
            if QMessageBox.question(self,'明確確認逐檔動作／部分輸出','\n'.join(lines)+'\n部分輸出：'+str(self.engine.plan['partial'])+'；其餘尺寸未完成。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:
                if not retry:self.engine.scope=None
                return
            if not self.owner.is_current():raise ValueError('確認期間輸入已變更')
            if not selected:
                self.status.setText('全部明確略過；沒有產生檔案。')
                for row in self.engine.items:self.update_row(row)
                return
            self.running=True;self.cancel.clear();self.start.setEnabled(False);self.retry.setEnabled(False)
            for name,action in self.controls:name.setEnabled(False);action.setEnabled(False)
            root=self.window.library.root;plan=deepcopy(self.engine.plan);items=deepcopy(self.engine.items);scope=self.engine.scope;entries=deepcopy(self.owner.service.entries);inputs=deepcopy(self.owner.inputs);graph=deepcopy(self.owner.graph.data);generation=self.owner.generation;stale=self.owner.stale;stop=self.owner.stop
            def worker():
                from .storage import Library
                library=None
                try:
                    library=Library(root);workflow=MultiSizeWorkflow(library,inputs,graph,generation);workflow.entries=entries;engine=OutputBatch(workflow,plan);engine.items=items;engine.scope=scope
                    return dict(items=engine.execute(selected,True,plan['partial'],current_check=lambda:not stale.is_set() and not stop.is_set(),cancel=self.cancel,progress=self.progress.updated.emit,retry=retry))
                except Exception as error:return dict(error=str(error))
                finally:
                    if library:library.close()
            def finished(result):
                self.running=False;self.retry.setEnabled(True);self.start.setEnabled(any(row['status']=='PLANNED' for row in result.get('items',self.engine.items)))
                if result.get('error'):self.status.setText('未完成：'+result['error']);return
                self.engine.items=result['items']
                for row in self.engine.items:self.update_row(row)
                counts={state:sum(r['status']==state for r in self.engine.items) for state in ('SUCCESS','FAILED','BLOCKED','SKIPPED','PLANNED')};self.status.setText('逐檔實際結果 '+str(counts)+'；已成功檔案受保護，未完成者不可算成功。');self.owner.last_output=self.engine.items
            self.window.run_job('逐檔安全輸出／精確重試',worker,JobCallbacks(finished,lambda error:finished({'error':str(error)}),self.cancel))
        except Exception as error:self.running=False;self.start.setEnabled(any(row['status']=='PLANNED' for row in self.engine.items));self.retry.setEnabled(any(row['status']=='FAILED' and row['retryable'] for row in self.engine.items));self.status.setText('未開始：'+str(error))
    def open_folder(self):
        ids=self.ids()
        if ids:
            row=self.engine.items[int(ids[0])];QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(row['path']).parent)))
    def cleanup(self):
        if self.running:return
        try:
            ids=self.ids();selected=[row for row in self.engine.items if row['id'] in ids and row.get('stage_path')]
            if not selected:raise ValueError('先選本程式已記錄的暫存；正式檔與原檔恢復副本不會清理')
            if QMessageBox.question(self,'只清理確切未改變的暫存','\n'.join(row['stage_path'] for row in selected),QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            for row in selected:self.update_row(self.engine.cleanup_stage(row['id'],True))
        except Exception as error:self.status.setText('未清理：'+str(error))
    def reject(self):
        if self.running:self.cancel.set();self.status.setText('安全取消中，等待目前檔案步驟完成。');return
        super().reject()
    def closeEvent(self,event):
        if self.running:self.cancel.set();event.ignore()
        else:super().closeEvent(event)

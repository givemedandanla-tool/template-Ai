"""Explicit cross-target properties inside the existing multi-size result workflow."""
import copy,json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QListWidget,
    QListWidgetItem,QCheckBox,QPushButton,QTableWidget,QTableWidgetItem,QPlainTextEdit,QMessageBox)
from .candidate_sync import cross_property_plan,prepare_cross_batch,calculate_cross_batch,install_cross_batch
from .multi_size_edit import SizeEditAdapter
from shiboken6 import isValid


class CrossPropertyDialog(QDialog):
    def __init__(self,owner):
        super().__init__(owner);self.owner=owner;self.service=owner.service;self.source_entry=owner.entry();self.source_id=self.source_entry['selected'];self.plan=None;self.running=False;self.setWindowTitle('明確跨候選／尺寸套用屬性（不複製座標）');layout=QVBoxLayout(self)
        source=self.source();layout.addWidget(QLabel('來源：'+source.template.name+f' v{source.template.version}／{source.template.width_mm:g}×{source.template.height_mm:g} mm'))
        self.status=QLabel('先選來源物件、明確屬性與目標，再逐項預覽。無唯一欄位映射或未通過整張Gate的目標保留舊版本。');self.status.setWordWrap(True);layout.addWidget(self.status);self.objects=QListWidget();self.objects.setSelectionMode(QListWidget.ExtendedSelection)
        for slot in self.source().template.slots:
            item=QListWidgetItem(slot.owner+'／'+slot.kind+'／'+slot.id);item.setData(Qt.UserRole,slot.id);self.objects.addItem(item)
        if self.objects.count():self.objects.item(0).setSelected(True)
        layout.addWidget(self.objects);bar=QHBoxLayout();self.attributes={}
        for key,title in (('align','文字對齊'),('color','文字顏色'),('locked','明確鎖定狀態')):
            box=QCheckBox(title);box.setChecked(key=='align');self.attributes[key]=box;bar.addWidget(box)
        layout.addLayout(bar);self.targets=[];self.table=QTableWidget(0,3);self.table.setHorizontalHeaderLabels(['明確目標','尺寸／模板版本','預覽／套用狀態']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);layout.addWidget(self.table,1)
        for entry in owner.service.entries:
            for index,candidate in enumerate(entry['candidates']):
                if candidate is self.source():continue
                key=json.dumps([entry['key'],candidate.template.id],separators=(',',':'));self.targets.append((key,entry,index));row=self.table.rowCount();self.table.setRowCount(row+1);item=QTableWidgetItem();item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Unchecked);self.table.setItem(row,0,item);self.table.setItem(row,1,QTableWidgetItem(f'{candidate.template.width_mm:g}×{candidate.template.height_mm:g} mm／'+candidate.template.name+f' v{candidate.template.version}'));self.table.setItem(row,2,QTableWidgetItem('尚未預覽'))
        self.table.horizontalHeader().setStretchLastSection(True);bar=QHBoxLayout();self.preview_button=QPushButton('預覽實際目標差異');self.preview_button.clicked.connect(self.preview);bar.addWidget(self.preview_button);self.apply_button=QPushButton('確認後逐目標重驗套用');self.apply_button.clicked.connect(self.apply);bar.addWidget(self.apply_button);self.cancel_button=QPushButton('取消此跨候選套用');self.cancel_button.clicked.connect(self.cancel);bar.addWidget(self.cancel_button);layout.addLayout(bar);self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details,1);self.resize(1120,800)
    def source(self):
        if self.owner.service is not self.service:raise ValueError('來源集合已更新，重新開啟比較')
        return next(c for c in self.source_entry['candidates'] if c.template.id==self.source_id)
    def controls(self):
        return dict(ids=[item.data(Qt.UserRole) for item in self.objects.selectedItems()],attributes=[key for key,box in self.attributes.items() if box.isChecked()],keys=[key for row,(key,entry,index) in enumerate(self.targets) if self.table.item(row,0).checkState()==Qt.Checked])
    def selected_targets(self,controls):return [(key,entry['candidates'][index]) for key,entry,index in self.targets if key in controls['keys']]
    def release_adapters(self):
        for adapter,index in getattr(self,'adapters',{}).values():
            if isValid(adapter):adapter.deleteLater()
        self.adapters={}
    def preview(self):
        try:
            if self.running or not self.owner.is_current():raise ValueError('來源尚未完成同步／背景工作尚未結束')
            controls=self.controls();self.plan=cross_property_plan(self.source(),self.selected_targets(controls),controls['ids'],controls['attributes']);self.preview_controls=copy.deepcopy(controls);lines=['未套用；每個實體尺寸獨立通過完整Gate後才可採用。']
            states=dict(READY_FOR_EXPLICIT_CONFIRMATION='差異待確認',INCOMPATIBLE='無法安全套用',UNCHANGED='屬性一致，未變動')
            for target in self.plan['targets']:
                row=next(i for i,(key,entry,index) in enumerate(self.targets) if key==target['key']);self.table.item(row,2).setText(states[target['state']]);lines.append(self.table.item(row,1).text()+'：'+states[target['state']]+'／'+target['reason']+'／現況：'+target['current_risk_label'])
                for change in target['changes']:lines.append('  '+change['object_id']+'／'+change['property']+'：'+str(change['before'])+' → '+str(change['after']))
            self.details.setPlainText('\n'.join(lines));self.status.setText('已列實際目標與屬性差異；姓名／公司／Logo位置不會因屬性套用被挪動。')
        except (ValueError,KeyError,IndexError,StopIteration) as error:self.plan=None;self.status.setText('未預覽：'+str(error))
    def apply(self):
        try:
            if self.running or self.owner.running or self.owner.window.busy:raise ValueError('原單一背景工作仍在進行')
            if self.plan is None or self.controls()!=self.preview_controls:raise ValueError('目標／物件／屬性已改，先重新預覽')
            if not self.owner.is_current():raise ValueError('來源已改，先同步重驗')
            if QMessageBox.question(self,'逐目標實際作用範圍',self.details.toPlainText()+'\n失敗／不相容目標保留舊版本，通過的目標分別記錄可復原變動。')!=QMessageBox.Yes:return
            self.adapters={key:(SizeEditAdapter(self.owner,entry,index),index) for key,entry,index in self.targets if key in self.preview_controls['keys']};batch=prepare_cross_batch(self.plan,self.source(),self.adapters,approved=True);self.owner.stop.clear();self.running=True
            def work(library):return calculate_cross_batch(batch,library,self.owner.stop)
            def failed(message):self.running=False;self.release_adapters();self.status.setText('未套用：'+str(message)+'；各目標保留原版本')
            def done(results):
                self.running=False
                try:installed=install_cross_batch(batch,results,self.source(),self.adapters)
                except (ValueError,KeyError,IndexError,StopIteration) as error:installed=[dict(key=row['key'],state='STALE_IGNORED',reason=str(error) or '來源集合已更新') for row in results]
                labels=dict(APPLIED_VERIFIED='已重驗套用／可單筆復原',VALIDATION_FAILED='驗證失敗，保留原版本',INCOMPATIBLE='不相容，未套用',UNCHANGED='屬性一致，未變動',STALE_IGNORED='版本已改，忽略舊結果',CANCELLED='已取消，未套用',FAILED='失敗，未套用');lines=[]
                for result in installed:
                    row=next(i for i,(key,entry,index) in enumerate(self.targets) if key==result['key']);state=labels.get(result['state'],result['state']);self.table.item(row,2).setText(state);lines.append(self.table.item(row,1).text()+'：'+state+'／'+result['reason'])
                self.details.setPlainText('\n'.join(lines));self.status.setText('逐目標結果已列出；成功與失敗各自保留，沒有跨尺寸借用PASS。');self.results=installed;self.plan=None;self.release_adapters()
            self.owner.background('明確跨候選屬性逐目標重驗',work,done,resource_kind='GEOMETRY',cancel=self.owner.stop,on_error=failed,require_current=True)
        except (ValueError,KeyError,IndexError,StopIteration) as error:self.running=False;self.release_adapters();self.status.setText('未開始套用：'+str(error))
    def cancel(self):
        if self.running:self.owner.stop.set();self.status.setText('取消中；未採用的計算副本不會套用')
        else:self.plan=None;self.status.setText('已取消這次差異，所有目標保留原狀')
    def closeEvent(self,event):
        if self.running:self.cancel();event.ignore()
        else:super().closeEvent(event)

"""Explicitly bounded custom proposal, saved through existing draft versioning."""
from copy import deepcopy
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QDoubleSpinBox,QLineEdit,QCheckBox,QPushButton,QPlainTextEdit,QMessageBox
from .custom_layout import CustomLayout
from .customers import digest
from .render import render_image

class CustomLayoutDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.plan=None;self.created=None;self.running=False;self.setWindowTitle('無合格現成模板時：授權範圍內特製草稿');self.resize(1000,760);layout=QVBoxLayout(self);self.status=QLabel('固定字級、歸屬及完整Logo；只調目前模板的允許幾何。求解可行不代表已發布。');self.status.setWordWrap(True);layout.addWidget(self.status);self.base=QComboBox()
        people,_,_=window.input_data()
        for t in window.library.templates(True):
            if (t.width_mm,t.height_mm,t.capacity)==(window.out_w.value(),window.out_h.value(),len(people)):self.base.addItem(t.name+f' v{t.version}／{t.width_mm:g}×{t.height_mm:g}mm',t.id)
        layout.addWidget(self.base);bar=QHBoxLayout();self.limits={}
        for key,label,maximum,value in [('move_mm','允許位移mm',50,0),('expand_mm','允許擴框mm',50,0),('gap_mm','最小間距mm（非印刷標準）',5,0)]:
            spin=QDoubleSpinBox();spin.setRange(0,maximum);spin.setDecimals(3);spin.setValue(value);self.limits[key]=spin;bar.addWidget(QLabel(label));bar.addWidget(spin)
        layout.addLayout(bar);self.reason=QLineEdit();self.reason.setMaxLength(512);self.reason.setPlaceholderText('核准本次特製範圍的理由；不建立跨模板通用規則');layout.addWidget(self.reason);self.approve=QCheckBox('已核對上述範圍、來源與差異；只授權建立新版本草稿');layout.addWidget(self.approve);self.image=QLabel();self.image.setAlignment(Qt.AlignCenter);layout.addWidget(self.image,2);self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details,1);bar=QHBoxLayout();self.preview_button=self.button(bar,'求解及預覽差異（未套用）',self.preview);self.save_button=self.button(bar,'明確建立特製版本草稿',self.save);self.button(bar,'定位已建立草稿核對／發布',self.locate);layout.addLayout(bar)
    def button(self,bar,label,fn):
        button=QPushButton(label);button.clicked.connect(fn);bar.addWidget(button);return button
    def policy(self):return {key:spin.value() for key,spin in self.limits.items()}
    def preview(self):
        try:
            if self.running or self.window.busy:return
            if not self.base.currentData():raise ValueError('沒有同尺寸／人物容量的已核准基準；先建立及核准設計規則，不猜造版面')
            people,companies,logos=self.window.input_data();root=self.window.library.root;generation=self.window.generation;policy=self.policy();identity=self.base.currentData();self.running=True;self.plan=None;self.preview_button.setEnabled(False);self.save_button.setEnabled(False)
            def worker():
                from .storage import Library
                library=None
                try:
                    library=Library(root);return dict(plan=CustomLayout(library).plan(identity,people,companies,logos,policy,generation))
                except Exception as error:return dict(error=str(error))
                finally:
                    if library:library.close()
            def finished(result):
                self.running=False;self.preview_button.setEnabled(True);self.save_button.setEnabled(True)
                if result.get('error'):self.status.setText('未求得候選：'+result['error']);return
                self.plan=result['plan'];self.status.setText(self.plan['status']+'：'+'；'.join(self.plan['issues']));self.details.setPlainText('明定範圍 '+str(policy)+'\n實測 '+str(self.plan['measurements'])+'\n逐框差異 '+str(self.plan['changes']))
                image=render_image(self.plan['preview_candidate'],100,True);self.image.setPixmap(QPixmap.fromImage(image).scaled(760,320,Qt.KeepAspectRatio,Qt.SmoothTransformation))
            self.window.run_job('Cassowary明定範圍特製候選',worker,finished)
        except Exception as error:self.running=False;self.preview_button.setEnabled(True);self.save_button.setEnabled(True);self.status.setText('未求解：'+str(error))
    def save(self):
        try:
            if self.running or self.window.busy:return
            if not self.plan or self.plan['policy']!=self.policy() or self.plan['base_plan']['source']['id']!=self.base.currentData() or self.plan['generation']!=self.window.generation:raise ValueError('先對目前輸入及範圍預覽；不可套用過期候選')
            if not self.approve.isChecked():raise ValueError('請先核對並明確授權本次草稿範圍')
            if QMessageBox.question(self,'建立同一模板的新版本草稿',str(self.plan['changes'])+'\n只保存新草稿，不改原始AI、不覆寫正式版、不啟用全域規則。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            people,companies,logos=self.window.input_data();self.created=CustomLayout(self.window.library).create_draft(self.plan,people,companies,logos,'LOCAL_OPERATOR',self.reason.text(),True);self.status.setText('已建立特製草稿 '+self.created.id+'；尚未發布，正式輸出仍被阻擋。')
        except Exception as error:self.status.setText('未保存：'+str(error))
    def locate(self):
        if not self.created:return
        self.window.tabs.setCurrentIndex(1);self.window.template_stack.setCurrentIndex(1);self.window.refresh_templates(self.created.id);self.accept()
    def reject(self):
        if self.running:self.status.setText('求解中；等待目前有界步驟完成後關閉。');return
        super().reject()

"""Explicit per-slot design policy, staged in the current version draft."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gui import MainWindow
from copy import deepcopy
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QImage,QPainter,QPixmap
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QFormLayout,QDoubleSpinBox,QLineEdit,QCheckBox,QPushButton,QMessageBox
from .model import Slot,Rect,Template
from .text_policy import tracking_geometry
from .layout import text_geometry
from .render import draw_text
from .object_tools import propose

class TextPolicyDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.host_window: MainWindow=window;self.slot=deepcopy(window.current_slot);self.template_id=window.template.id;self.before=window.template.to_dict();self.setWindowTitle('固定字級／字距與語意分散規則（目前草稿）');self.resize(720,500)
        outer=QVBoxLayout(self);self.status=QLabel();self.status.setWordWrap(True);outer.addWidget(self.status);form=QFormLayout();self.values=[]
        for label,key in [('設計字距 mm','tracking_mm'),('允許下限 mm','tracking_min_mm'),('允許上限 mm','tracking_max_mm')]:
            spin=QDoubleSpinBox();spin.setRange(0,2);spin.setDecimals(4);spin.setValue(getattr(self.slot,key));self.values.append(spin);form.addRow(label,spin)
        self.distribute=QCheckBox('明確核准目前職稱／地址欄位的分散規則');self.distribute.setChecked(self.slot.align=='distributed');form.addRow(self.distribute);self.reason=QLineEdit((self.slot.distribution_approval or {}).get('reason',''));self.reason.setMaxLength(512);form.addRow('規則理由（分散必填）',self.reason);self.sample=QLineEdit('Sample title');self.sample.setMaxLength(512);form.addRow('量測示例（非原稿真值）',self.sample);outer.addLayout(form)
        self.image=QLabel();outer.addWidget(self.image);bar=QPushButton('度量並預覽（不套用）');bar.clicked.connect(self.preview);outer.addWidget(bar);self.apply_button=QPushButton('明確套用目前欄位草稿');self.apply_button.clicked.connect(self.apply);outer.addWidget(self.apply_button);self.preview()
    def candidate(self):
        slot=deepcopy(self.slot);slot.tracking_mm,slot.tracking_min_mm,slot.tracking_max_mm=[spin.value() for spin in self.values]
        slot.align='distributed' if self.distribute.isChecked() else ('left' if slot.align=='distributed' else slot.align)
        slot.distribution_approval=dict(approved=True,actor='LOCAL_OPERATOR',reason=self.reason.text()) if self.distribute.isChecked() else None;return slot
    def preview(self):
        try:
            slot=self.candidate();w,h,errors,tracking,strategy=tracking_geometry(slot,self.sample.text(),text_geometry)
            if errors:raise ValueError('；'.join(errors))
            scale=min(1,slot.rect.w/w) if w else 1
            valid=scale>=slot.min_scale and h<=slot.rect.h
            image=QImage(640,180,QImage.Format_ARGB32);image.fill(Qt.white);p=QPainter(image)
            try:
                factor=min(600/max(slot.rect.w,1),150/max(slot.rect.h,1));p.translate(10,10);p.scale(factor,factor);draw_text(p,QRectF(0,0,slot.rect.w,slot.rect.h),self.sample.text(),slot.font,slot.size_pt,scale,slot.align,slot.color,slot.font_style,slot.font_asset,tracking)
            finally:p.end()
            self.image.setPixmap(QPixmap.fromImage(image));self.status.setText(f'{slot.owner}/{slot.kind}／{slot.id}；固定 {slot.size_pt:g} pt；實測寬{w:.4f}mm／框{slot.rect.w:g}mm，選用字距{tracking:.4f}mm，水平比例{scale:.2%}；{strategy}；'+('示例可排入，非完整印前PASS' if valid else '示例無解：不能正式輸出；可修改草稿政策'))
        except (ValueError,TypeError) as error:self.image.clear();self.status.setText('未通過：'+str(error))
    def _check_current_draft(self):
        from .font_review import fingerprint
        current=self.host_window.template
        if (self.host_window.tabs.currentIndex()!=1 or current is None
                or current.id!=self.template_id
                or fingerprint(current.to_dict())!=fingerprint(self.before)):
            raise ValueError('目前草稿已變更，請重開規則編輯')

    def apply(self):
        try:
            self._check_current_draft()
            slot=self.candidate();patch={key:deepcopy(getattr(slot,key)) for key in ('tracking_mm','tracking_min_mm','tracking_max_mm','align','distribution_approval')};plan=propose(self.before,'TEMPLATE',dict(operation='PATCH',ids=[slot.id],patch=patch))
            if QMessageBox.question(self,'只修改目前模板版本草稿',f'{slot.id}／固定{slot.size_pt:g}pt\n{patch}\n不啟用跨模板規則、不發布，保存後仍需完整驗證。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            self._check_current_draft()
            if not self.host_window.editable() or self.host_window.checkpoint() is False:return
            self.host_window.template=Template.from_dict(plan['after']);self.host_window.refresh_editor();self.host_window.editor_selection([slot.id]);self.accept()
        except (ValueError,TypeError) as error:self.status.setText('未套用：'+str(error))

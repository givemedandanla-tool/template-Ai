"""Logo 邊界、來源與品質逐項核對；關閉或只看預覽不會核准。"""
from copy import deepcopy
import json
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QDoubleSpinBox, QPlainTextEdit, QMessageBox, QLineEdit)

from .logo_compare import LogoCompareWidget
from .customers import digest


class LogoReviewDialog(QDialog):
    def __init__(self, store, proposal, parent=None):
        super().__init__(parent)
        self.store, self.proposal = store, deepcopy(proposal)
        self.approved_asset = None
        self.setWindowTitle('完整 Logo／來源與目標尺寸：逐項審核')
        self.resize(1280, 900)
        layout = QVBoxLayout(self)
        self.status = QLabel('邊界更改需先保存校正，再重新核對；未核准的 Logo 不會進正式庫。')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        bar = QHBoxLayout()
        bar.addWidget(QLabel('明確公司身分'))
        self.company = QComboBox()
        for company in store.companies():
            self.company.addItem(company['name'] + '／' + company['id'], company['id'])
        index = self.company.findData(proposal.get('company_id'))
        self.company.setCurrentIndex(max(0, index))
        bar.addWidget(self.company)
        layout.addLayout(bar)
        bar = QHBoxLayout()
        crop = proposal['asset'].get('crop') or dict(x=0, y=0, w=proposal['asset']['source_width_mm'],
                                                     h=proposal['asset']['source_height_mm'])
        self.coords = []
        for name in ('x', 'y', 'w', 'h'):
            bar.addWidget(QLabel(name + ' mm'))
            spin = QDoubleSpinBox()
            spin.setRange(0, 2000)
            spin.setDecimals(5)
            spin.setValue(crop[name])
            self.coords.append(spin)
            bar.addWidget(spin)
        self.save_crop = QPushButton('保存邊界合併／拆分校正')
        self.save_crop.clicked.connect(self.correct)
        bar.addWidget(self.save_crop)
        drag=QPushButton('在完整原來源拖曳框選邊界')
        drag.clicked.connect(self.drag_crop);bar.addWidget(drag)
        layout.addLayout(bar)
        bar = QHBoxLayout()
        self.frame_width, self.frame_height = QDoubleSpinBox(), QDoubleSpinBox()
        for spin, value in ((self.frame_width, 30), (self.frame_height, 15)):
            spin.setRange(.01, 2000)
            spin.setDecimals(4)
            spin.setValue(value)
            bar.addWidget(spin)
        button = QPushButton('預覽比較框位（不改模板）')
        button.clicked.connect(self.preview)
        bar.addWidget(button)
        button=QPushButton('建立目標框位PDF／PNG／JPG品質比較檔')
        button.clicked.connect(self.proof);bar.addWidget(button)
        layout.addLayout(bar)
        self.compare = LogoCompareWidget()
        layout.addWidget(self.compare, 3)
        self.details = QPlainTextEdit(json.dumps(proposal, ensure_ascii=False, indent=2))
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(110)
        layout.addWidget(self.details)
        self.note = QLineEdit()
        self.note.setPlaceholderText('來源、品質／目標尺寸與邊界校正依據（不得空白）')
        layout.addWidget(self.note)
        self.flags = {}
        for key, label in [('identity_confirmed', '已核對確切公司身分，沒有按同名字串合併'),
            ('whole_mark_confirmed', '框位包含完整文字與圖形，未拆字／切損／變形'),
            ('usage_authorized', '已確認此來源可合法用於本機工作'),
            ('digital_quality_confirmed', '已在目標卡片尺寸與適用輸出情境核對數位品質')]:
            check = QCheckBox(label)
            self.flags[key] = check
            layout.addWidget(check)
        bar = QHBoxLayout()
        self.approve_button = QPushButton('確認並加入此尺寸正式 Logo 庫')
        self.approve_button.clicked.connect(self.approve)
        bar.addWidget(self.approve_button)
        cancel = QPushButton('返回，不核准')
        cancel.clicked.connect(self.reject)
        bar.addWidget(cancel)
        layout.addLayout(bar)
        for spin in self.coords + [self.frame_width, self.frame_height]:
            spin.valueChanged.connect(self.invalidate_review)
        self.company.currentIndexChanged.connect(self.invalidate_review)
        self.preview()

    def crop(self):
        return {name: spin.value() for name, spin in zip(('x', 'y', 'w', 'h'), self.coords)}

    def crop_canvas(self):
        from .gui import Canvas
        from .logo_compare import preview_png
        from PySide6.QtGui import QImage
        from .model import Rect
        asset=self.proposal['asset'];image=QImage()
        if not image.loadFromData(preview_png(asset,1,1,True),'PNG'):raise ValueError('完整來源圖不可讀')
        canvas=Canvas();canvas.set_content(asset['source_width_mm'],asset['source_height_mm'],image,crop=Rect(**self.crop()))
        canvas.set_mode('crop');return canvas

    def adopt_crop(self,rect):
        asset=self.proposal['asset']
        if not rect.valid() or rect.x<0 or rect.y<0 or rect.x+rect.w>asset['source_width_mm']+1e-5 or rect.y+rect.h>asset['source_height_mm']+1e-5:
            raise ValueError('框選需完整位於原來源；來源作品邊界另於保存時核對')
        for spin,value in zip(self.coords,(rect.x,rect.y,rect.w,rect.h)):spin.setValue(value)
        self.invalidate_review();self.preview()

    def drag_crop(self):
        try:
            dialog=QDialog(self);dialog.setWindowTitle('原來源完整圖文：拖曳新邊界，仍需保存校正');dialog.resize(1000,650)
            layout=QVBoxLayout(dialog);canvas=self.crop_canvas();layout.addWidget(canvas)
            def chosen(rect):
                try:self.adopt_crop(rect);dialog.accept()
                except ValueError as error:self.status.setText(str(error))
            canvas.rectangle.connect(chosen);dialog.show();canvas.fit();dialog.exec()
        except (ValueError,OSError) as error:self.status.setText('無法框選：'+str(error))

    def preview(self):
        asset = deepcopy(self.proposal['asset'])
        asset['crop'] = self.crop()
        self.compare.show_assets(asset, width=self.frame_width.value(), height=self.frame_height.value())
        self.preview_signature = digest([self.crop(), self.frame_width.value(),
                                        self.frame_height.value(), self.company.currentData()])

    def invalidate_review(self, *_):
        self.preview_signature = None
        self.output_proof=None
        for check in self.flags.values():
            check.setChecked(False)
        self.status.setText('條件已變更，請重新預覽並核對每一項；尚未核准。')

    def proof(self):
        try:
            from .logo_output_proof import create_proof
            asset=deepcopy(self.proposal['asset']);asset['crop']=self.crop()
            self.output_proof=create_proof(asset,self.frame_width.value(),self.frame_height.value(),self.store.library.assets/'logo-proofs')
            self.proof_signature=digest([self.crop(),self.frame_width.value(),self.frame_height.value(),self.company.currentData()])
            self.details.setPlainText(json.dumps(self.output_proof,ensure_ascii=False,indent=2))
            self.status.setText('三種數位比較檔已實際產生、讀回與核對尺寸；可在上述本機路徑開啟。仍需人工核對細節，尚未核准或證明實體印刷。')
            return True
        except (ValueError,OSError) as error:self.output_proof=None;self.status.setText('數位比較未通過：'+str(error));return False

    def correct(self):
        try:
            if QMessageBox.question(self, '僅校正候選，不改來源',
                    '保存此完整邊界與公司歸屬？所有品質勾選會清除，需重新核對。') != QMessageBox.Yes:
                return
            self.proposal = self.store.revise(self.proposal['id'], self.proposal['revision'], self.crop(),
                self.company.currentData(), self.proposal['evidence'].get('object_ids'), self.note.text())
            for check in self.flags.values():
                check.setChecked(False)
            self.details.setPlainText(json.dumps(self.proposal, ensure_ascii=False, indent=2))
            self.preview()
            self.status.setText('候選校正已保存，原稿／其他 Logo／版型均未變。重新核對後才可核准。')
        except (ValueError, KeyError, OSError, sqlite3.DatabaseError) as error:
            self.status.setText('未校正：' + str(error))

    def approve(self):
        try:
            signature = digest([self.crop(), self.frame_width.value(), self.frame_height.value(), self.company.currentData()])
            if not self.compare.available or self.preview_signature != signature:
                raise ValueError('先重新預覽目前公司／框位與可讀來源，不能核准過期畫面')
            original_crop = self.proposal['asset'].get('crop') or dict(x=0, y=0,
                w=self.proposal['asset']['source_width_mm'], h=self.proposal['asset']['source_height_mm'])
            if any(abs(self.crop()[key] - original_crop[key]) > 1e-5 for key in original_crop):
                raise ValueError('邊界尚未保存校正；不能用不同預覽核准舊邊界')
            review = {key: check.isChecked() for key, check in self.flags.items()}
            review.update(actor='LOCAL_OPERATOR', note=self.note.text(),
                          compared_frame_mm=[self.frame_width.value(), self.frame_height.value()])
            if not all(check.isChecked() for check in self.flags.values()):
                raise ValueError('請完成每一項來源／身分／完整性／品質核對')
            if getattr(self,'output_proof',None) is None or self.proof_signature!=signature:
                if not self.proof():raise ValueError('實際數位比較檔產生／讀回未通過')
            review['output_proof']=deepcopy(self.output_proof)
            if QMessageBox.question(self, '此尺寸與版本核准',
                    '公司：' + self.company.currentText() + '\n卡片尺寸：' +
                    str([self.proposal['width_mm'], self.proposal['height_mm']]) +
                    '\n只核准此候選與此尺寸；不自動替換既有版型或當次 Logo。') != QMessageBox.Yes:
                return
            self.approved_asset = self.store.approve(self.proposal['id'], self.proposal['revision'],
                self.company.currentData(), review, approved=True)
            self.accept()
        except (ValueError, KeyError, OSError, sqlite3.DatabaseError) as error:
            self.status.setText('未核准：' + str(error))

"""Local, human visual font review; preview sizing never establishes source pt."""
from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path
import struct

from PySide6.QtCore import QPointF, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFontDatabase, QImage, QImageReader, QPainterPath, QPixmap, QRawFont
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
)


class _Preview(QLabel):
    def __init__(self, empty_text, parent=None):
        super().__init__(empty_text, parent)
        self.image = QImage()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(260, 150)
        self.setStyleSheet('background:white;border:1px solid #dce3ec;border-radius:6px;color:#526174;padding:8px;')

    def set_image(self, image):
        self.image = image
        self._fit()

    def _fit(self):
        if not self.image.isNull():
            size = self.contentsRect().size()
            self.setPixmap(QPixmap.fromImage(self.image).scaled(size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit()


class FontReviewDialog(QDialog):
    """Show original crop and explicitly chosen local font side by side.

    The family catalogue is enumerated only after this dialog is opened. A
    system-family choice retains UNKNOWN file identity. Selecting a real font
    file additionally records its verified SHA and collection face, not the
    original artwork's native font identity or point size.
    """

    def __init__(self, page, work, field, parent=None):
        super().__init__(parent)
        self.setObjectName('fontReviewDialog')
        self.setWindowTitle('比對本機字型外觀')
        self.resize(940, 690)
        self.page, self.work, self.field = deepcopy(page or {}), deepcopy(work or {}), deepcopy(field or {})
        self.text = str(field.get('text', ''))
        self._annotation = None
        self._rendered_record = None
        self._system_families = []
        self._file_candidates = []
        self.families_loaded = False
        self.kept_unknown = False
        self.source_crop = self._crop_original()
        root = QVBoxLayout(self)
        intro = QLabel('對照原稿與候選字型，選擇外觀符合的一項。候選僅供人工比較，不代表系統已辨識成功。')
        intro.setWordWrap(True)
        root.addWidget(intro)
        previews = QHBoxLayout()
        original_box, candidate_box = QVBoxLayout(), QVBoxLayout()
        original_box.addWidget(QLabel('原稿中的文字'))
        self.original_preview = _Preview('原稿裁切尚未取得')
        self.original_preview.setObjectName('originalFontCrop')
        self.original_preview.set_image(self.source_crop)
        original_box.addWidget(self.original_preview)
        candidate_box.addWidget(QLabel('目前候選字型'))
        self.candidate_preview = _Preview('選擇下方候選以比較')
        self.candidate_preview.setObjectName('candidateFontPreview')
        candidate_box.addWidget(self.candidate_preview)
        previews.addLayout(original_box)
        previews.addLayout(candidate_box)
        root.addLayout(previews, 2)
        note = QLabel('兩側僅為方便觀看而等比例放大；這裡不設定原稿字級、字寬，也不改動原稿。')
        note.setWordWrap(True)
        root.addWidget(note)
        self.filter_edit = QLineEdit()
        self.filter_edit.setObjectName('fontFamilyFilter')
        self.filter_edit.setPlaceholderText('輸入字型名稱，縮小候選範圍')
        root.addWidget(self.filter_edit)
        row = QHBoxLayout()
        self.family_list = QListWidget()
        self.family_list.setObjectName('fontFamilyCandidates')
        row.addWidget(self.family_list, 3)
        options = QVBoxLayout()
        options.addWidget(QLabel('字型款式'))
        self.style_combo = QComboBox()
        self.style_combo.setObjectName('fontStyleCandidates')
        options.addWidget(self.style_combo)
        self.file_button = QPushButton('從本機字型檔選擇…')
        self.file_button.clicked.connect(self.choose_font_file)
        options.addWidget(self.file_button)
        self.count_label = QLabel('正在讀取本機字型名稱…')
        self.count_label.setWordWrap(True)
        options.addWidget(self.count_label)
        options.addStretch()
        row.addLayout(options, 2)
        root.addLayout(row, 2)
        self.status_label = QLabel('請選擇候選；無法判斷時可以保留未知。')
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName('fontReviewStatus')
        root.addWidget(self.status_label)
        buttons = QHBoxLayout()
        self.unknown_button = QPushButton('仍無法確定')
        self.unknown_button.clicked.connect(self.keep_unknown)
        buttons.addWidget(self.unknown_button)
        buttons.addStretch()
        self.cancel_button = QPushButton('取消')
        self.cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.cancel_button)
        self.use_button = QPushButton('記錄這個候選')
        self.use_button.setObjectName('confirmFontCandidate')
        self.use_button.setEnabled(False)
        self.use_button.clicked.connect(self.accept_choice)
        buttons.addWidget(self.use_button)
        root.addLayout(buttons)
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(80)
        self._render_timer.timeout.connect(self.render_candidate)
        self.filter_edit.textChanged.connect(self._filter_families)
        self.family_list.currentItemChanged.connect(self._family_changed)
        self.style_combo.currentIndexChanged.connect(self._schedule_render)
        QTimer.singleShot(0, self.load_families)

    def _crop_original(self):
        try:
            from ..offline_runtime import assert_local_path
            path = self.page.get('image') or self.work.get('image')
            if not path:
                return QImage()
            assert_local_path(path)
            reader = QImageReader(str(path))
            size = reader.size()
            if size.width() <= 0 or size.height() <= 0 or size.width()*size.height() > 12_000_000:
                return QImage()
            width, height = float(self.page['width_mm']), float(self.page['height_mm'])
            crop, frame = self.work['crop'], self.field['rect']
            values = [width,height,*[float(frame[k]) for k in ('x','y','w','h')],float(crop['x']),float(crop['y'])]
            if not all(math.isfinite(v) for v in values) or min(width,height,frame['w'],frame['h']) <= 0:
                return QImage()
            left=(float(crop['x'])+float(frame['x']))/width*size.width()
            top=(float(crop['y'])+float(frame['y']))/height*size.height()
            right=left+float(frame['w'])/width*size.width()
            bottom=top+float(frame['h'])/height*size.height()
            bounds=QRect(math.floor(left),math.floor(top),math.ceil(right)-math.floor(left),math.ceil(bottom)-math.floor(top)).intersected(QRect(0,0,size.width(),size.height()))
            if bounds.isEmpty():
                return QImage()
            image=reader.read()
            return image.copy(bounds) if not image.isNull() else QImage()
        except (KeyError,TypeError,ValueError,OSError):
            return QImage()

    def load_families(self):
        if self.families_loaded:
            return
        self._system_families = sorted(QFontDatabase.families(), key=str.casefold)
        self.families_loaded = True
        self._filter_families()

    def _filter_families(self, *_):
        query=self.filter_edit.text().strip().casefold()
        records=[*self._file_candidates,*[dict(family=f,source='SYSTEM') for f in self._system_families]]
        records=[r for r in records if query in r['family'].casefold()]
        self.family_list.blockSignals(True)
        self.family_list.clear()
        for record in records[:200]:
            caption=record['family']+(' · 已選字型檔' if record['source']=='FILE' else '')
            item=QListWidgetItem(caption)
            item.setData(Qt.ItemDataRole.UserRole,record)
            self.family_list.addItem(item)
        self.family_list.blockSignals(False)
        suffix='；輸入名稱可查看其他候選' if len(records)>200 else ''
        self.count_label.setText(f'目前顯示 {min(len(records),200)} / {len(records)} 個候選{suffix}')
        self._rendered_record=None
        self.use_button.setEnabled(False)
        self.style_combo.clear()
        if self.family_list.count():
            self.family_list.setCurrentRow(0)

    def _family_changed(self, current, previous=None):
        self.style_combo.blockSignals(True)
        self.style_combo.clear()
        if current is not None:
            record=current.data(Qt.ItemDataRole.UserRole)
            if record['source']=='FILE':
                for face in record['faces']:
                    self.style_combo.addItem(face.get('style') or '一般',face)
            else:
                for style in QFontDatabase.styles(record['family']):
                    self.style_combo.addItem(style,dict(style=style))
        self.style_combo.blockSignals(False)
        self._schedule_render()

    def _schedule_render(self, *_):
        self._rendered_record=None
        self.use_button.setEnabled(False)
        self._render_timer.start()

    def _render_raw(self, raw):
        from ..visual_font_match import shaped_outline, render_outline
        if not self.text.strip() or len(self.text)>2048:
            raise ValueError('這段文字尚未取得或過長，請先核對文字／分開標記，再比較字型。')
        path=QPainterPath()
        for index,line in enumerate(self.text.splitlines()):
            if line.strip():
                path.addPath(shaped_outline(line,raw).translated(QPointF(0,index*144)))
        bounds=path.boundingRect()
        if path.isEmpty() or min(bounds.width(),bounds.height()) <= 0:
            raise ValueError('候選無可顯示的文字輪廓。')
        scale=min(740/bounds.width(),160/bounds.height())
        return render_outline(path,max(1,round(bounds.width()*scale)),max(1,round(bounds.height()*scale)))

    @staticmethod
    def _matches_family(raw, family):
        aliases={raw.familyName().casefold()}
        expected=family.split(' [',1)[0].casefold()
        if expected in aliases:
            return True
        try:
            from fontTools.ttLib import TTFont,newTable
            data=bytes(raw.fontTable('name'))
            if len(data)<6:
                return False
            table=newTable('name')
            font=TTFont()
            try:
                table.decompile(data,font)
                aliases.update(row.toUnicode().casefold() for row in table.names if row.nameID in (1,16))
            finally:
                font.close()
        except (ValueError,KeyError,UnicodeError,AssertionError,IndexError,struct.error):
            pass
        # Qt may append the foundry to distinguish identically named families.
        return expected in aliases

    def render_candidate(self):
        self._render_timer.stop()
        self._rendered_record=None
        self.use_button.setEnabled(False)
        current=self.family_list.currentItem()
        style=self.style_combo.currentData()
        if current is None or not isinstance(style,dict):
            self.status_label.setText('沒有符合的字型，請調整名稱或保留未知。')
            return False
        if self.source_crop.isNull():
            self.status_label.setText('尚未取得原稿裁切，無法完成視覺核對；請返回檢查作品範圍。')
            return False
        record=current.data(Qt.ItemDataRole.UserRole)
        try:
            from ..font_catalog import face_fingerprint
            if record['source']=='FILE':
                from ..visual_font_match import exact_face
                selected=dict(path=record['path'],sha256=record['sha256'],face_index=style['index'])
                with exact_face(selected) as raw:
                    image=self._render_raw(raw)
                    annotation=dict(family=raw.familyName(),style=raw.styleName(),file_path=record['path'],
                                    file_sha256=record['sha256'],face_index=style['index'],rendered_face_fingerprint=face_fingerprint(raw),font_file_identity='VERIFIED_LOCAL_FILE_FACE')
                identity='已取得所選字型檔與字面；這仍是人工候選，不代表原稿原生身份已確認。'
            else:
                font=QFontDatabase.font(record['family'],style['style'],96)
                font.setPixelSize(96)
                raw=QRawFont.fromFont(font)
                if not raw.isValid() or not self._matches_family(raw,record['family']):
                    raise ValueError('系統無法使用這個名稱的實際字型，請選其他候選或明確選擇字型檔。')
                image=self._render_raw(raw)
                annotation=dict(family=record['family'],style=raw.styleName(),file_path=None,file_sha256=None,
                                face_index=None,rendered_face_fingerprint=face_fingerprint(raw),font_file_identity='UNKNOWN')
                identity='僅記錄人工選擇的名稱與款式；尚未取得實際字型檔身份。'
            annotation.update(method='HUMAN_VISUAL_REVIEW',source='HUMAN_VISUAL_REVIEW',
                              status='ANNOTATED' if record['source']=='FILE' else 'ANNOTATED_FAMILY_ONLY',
                              pt_confirmed=False,horizontal_scale_confirmed=False,
                              native_source_font_identity_confirmed=False,preview_scaling='PROPORTIONAL_DISPLAY_ONLY_NOT_SOURCE_PT')
            self.candidate_preview.set_image(image)
            self._rendered_record=annotation
            self.use_button.setEnabled(True)
            self.status_label.setText(identity)
            return True
        except (ValueError,RuntimeError,OSError,KeyError) as error:
            message=str(error)
            if 'FONT_MISSING_GLYPHS' in message:
                message='這個候選缺少部分文字字形，未使用其他字型偷偷補上；請選其他候選或保留未知。'
            self.status_label.setText(message)
            self.candidate_preview.clear()
            self.candidate_preview.setText('這個候選無法完整顯示比較文字')
            return False

    def choose_font_file(self):
        path,_=QFileDialog.getOpenFileName(self,'選擇本機字型檔','','字型檔 (*.ttf *.otf *.ttc *.otc)')
        if path:
            self.load_font_file(path)

    def load_font_file(self,path):
        try:
            from ..offline_runtime import assert_local_path
            from ..font_evidence import inspect_font
            assert_local_path(path)
            report=inspect_font(path)
            grouped={}
            for face in report['faces']:
                if face.get('family'):
                    grouped.setdefault(face['family'],[]).append(face)
            if not grouped:
                raise ValueError('字型檔沒有可核對的名稱與字面。')
            self._file_candidates=[dict(family=family,source='FILE',path=str(Path(path).resolve()),sha256=report['hash'],faces=faces) for family,faces in grouped.items()]
            self.filter_edit.clear()
            self._filter_families()
            self.family_list.setCurrentRow(0)
            return self.render_candidate()
        except (ValueError,OSError,RuntimeError) as error:
            self.status_label.setText(str(error))
            self.use_button.setEnabled(False)
            self._rendered_record=None
            return False

    def accept_choice(self):
        if not self.render_candidate() or self._rendered_record is None:
            return
        self._annotation=deepcopy(self._rendered_record)
        self.accept()

    def keep_unknown(self):
        self.kept_unknown=True
        self._annotation=None
        self.reject()

    def annotation(self):
        return deepcopy(self._annotation) if self.result()==QDialog.DialogCode.Accepted else None

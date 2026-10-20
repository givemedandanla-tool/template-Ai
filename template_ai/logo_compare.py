"""重用既有同步對照畫布，比較原始來源、現用版本與候選完整 Logo。"""
from copy import deepcopy
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from .comparison_view import ComparisonCanvas
from .logo_assets import geometry
from .model import Rect
from .render import draw_logo


def preview_png(asset, width, height, full_source=False):
    if asset.get('svg') and Path(asset['svg']).stat().st_size > 5_000_000:
        raise ValueError('向量複雜度超出此對照預算；請在原來源工具核對，未產生假預覽')
    asset = deepcopy(asset)
    if full_source:
        asset['crop'] = None
        width, height = asset['source_width_mm'], asset['source_height_mm']
    scale = min(640/width, 480/height)
    image = QImage(max(1, round(width*scale)), max(1, round(height*scale)), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(image.width()/width, image.height()/height)
    try:
        draw_logo(painter, QRectF(0, 0, width, height), asset)
    finally:
        painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    if not image.save(buffer, 'PNG'):
        raise ValueError('Logo 對照圖編碼失敗')
    return bytes(data)


class LogoCompareWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.root_layout = QVBoxLayout(self)
        self.info = QLabel('尚未選取可核對來源；不顯示猜測縮圖。')
        self.info.setWordWrap(True)
        self.info.setTextFormat(Qt.PlainText)
        self.root_layout.addWidget(self.info)
        buttons = QHBoxLayout()
        for label, action in [('符合框位', self.fit), ('放大', lambda: self.zoom(1.25)),
                              ('縮小', lambda: self.zoom(.8))]:
            button = QPushButton(label)
            button.clicked.connect(action)
            buttons.addWidget(button)
        self.root_layout.addLayout(buttons)
        self.body = QWidget()
        self.root_layout.addWidget(self.body, 1)
        self.views = []
        self.available = False
        self.center, self.zoom_value = QPointF(), 1
        self.setMinimumHeight(240)

    def show_assets(self, candidate, original=None, width=30, height=15):
        old = self.body
        self.body = QWidget()
        self.root_layout.replaceWidget(old, self.body)
        old.deleteLater()
        self.views = []
        self.available = False
        try:
            fit = geometry(candidate, Rect(0, 0, width, height))
            crop = candidate.get('crop') or dict(x=0, y=0, w=candidate['source_width_mm'], h=candidate['source_height_mm'])
            padding, scale = fit['padding_mm'], fit['scale']
            mapping = dict(page_size=[candidate['source_width_mm'], candidate['source_height_mm']],
                crop=dict(x=crop['x']-padding['left']/scale, y=crop['y']-padding['top']/scale,
                          w=width/scale, h=height/scale))
            data = dict(template_size=[width, height], slots=[],
                source=dict(mapping=mapping), source_png=preview_png(candidate, width, height, True),
                original_png=preview_png(original or candidate, width, height),
                candidate_png=preview_png(candidate, width, height))
            columns = QHBoxLayout(self.body)
            for label, mode in [('完整來源（含裁切框以外內容）', 'source'),
                                ('現用版本／候選原貌', 'original'), ('候選等比放入', 'candidate')]:
                panel = QVBoxLayout()
                panel.addWidget(QLabel(label))
                view = ComparisonCanvas(data, mode, self)
                view.navigated.connect(self.synchronize)
                self.views.append(view)
                panel.addWidget(view)
                columns.addLayout(panel)
            self.width_mm, self.height_mm = width, height
            self.info.setText(f"比較框位 {width:g}×{height:g} mm；完整等比縮放 {fit['scale']:.4g}；"
                f"實際占用 {fit['actual']['w']:.4g}×{fit['actual']['h']:.4g} mm；留白 {fit['padding_mm']}。"
                '圖像、文字、透明背景一併保留；此畫面不代表實體印刷驗收。')
            self.fit()
            self.available = True
        except (ValueError, KeyError, OSError) as error:
            self.info.setText('來源預覽不可用／未知：' + str(error))

    def synchronize(self, center, zoom):
        self.center, self.zoom_value = QPointF(center), max(.02, min(500, zoom))
        for view in self.views:
            view.set_view(self.center, self.zoom_value)

    def fit(self):
        if self.views:
            scale = min(min(v.viewport().width()/self.width_mm, v.viewport().height()/self.height_mm)
                        for v in self.views)*.9
            self.synchronize(QPointF(self.width_mm/2, self.height_mm/2), scale)

    def zoom(self, factor):
        self.synchronize(self.center, self.zoom_value*factor)

    def showEvent(self,event):
        super().showEvent(event)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0,self.fit)

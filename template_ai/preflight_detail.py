"""Read-only detail views reuse original drawing and millimetre viewport controls."""
import json
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPicture,QPainter
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QSplitter,QWidget,QGraphicsItem,QPlainTextEdit


def source_picture(item):
    if not item.logo:return None
    from .render import draw_logo
    picture=QPicture();painter=QPainter(picture)
    try:draw_logo(painter,QRectF(0,0,item.slot.rect.w,item.slot.rect.h),item.logo)
    finally:painter.end()
    return picture


class SourcePictureItem(QGraphicsItem):
    def __init__(self,picture,width,height):super().__init__();self.picture=picture;self.frame=QRectF(0,0,width,height)
    def boundingRect(self):return self.frame
    def paint(self,painter,option,widget=None):painter.drawPicture(0,0,self.picture)


class PreflightDetailDialog(QDialog):
    def __init__(self,window,item,proof,source,actual,detail,picture=None):
        super().__init__(window);self.setWindowTitle('物件來源／實際數位輸出細節');self.resize(1200,780);layout=QVBoxLayout(self)
        self.status=QLabel('比較快照：'+item.slot.owner+'／'+item.slot.kind+'／'+item.slot.id+'；'+proof['scope']['format']+'，'+str(proof['scope']['dpi'])+' DPI。畫面放大不等於實體印刷認證。');self.status.setWordWrap(True);layout.addWidget(self.status)
        from .gui import Canvas
        from .viewport_controls import navigation_controls
        split=QSplitter();layout.addWidget(split,1);self.views=[]
        titles=['完整Logo來源（白底、保留原繪圖幾何）' if picture else '目前來源渲染／原尺寸物件區域','實際已編碼並讀回（含成品背景合成）']
        for index,(title,image) in enumerate(zip(titles,(source,actual))):
            page=QWidget();box=QVBoxLayout(page);box.addWidget(QLabel(title));canvas=Canvas();canvas.readonly=True;self.views.append(canvas)
            if index==0 and picture:
                canvas.set_content(item.slot.rect.w,item.slot.rect.h);canvas.scene().addItem(SourcePictureItem(picture,item.slot.rect.w,item.slot.rect.h))
            else:canvas.set_content(image.width()*25.4/proof['scope']['dpi'],image.height()*25.4/proof['scope']['dpi'],image)
            canvas.set_mode('pan');box.addWidget(canvas,1);box.addWidget(navigation_controls(canvas,window.library));split.addWidget(page)
        self.measurements=QPlainTextEdit();self.measurements.setReadOnly(True);self.measurements.setMaximumHeight(135);self.measurements.setPlainText(json.dumps(detail,ensure_ascii=False,indent=2));layout.addWidget(self.measurements)
        if item.slot.kind=='logo' and not item.logo:self.status.setText(self.status.text()+' 來源缺失：此框為診斷占位，並非真實Logo。')
    def showEvent(self,event):
        super().showEvent(event)
        for view in self.views:view.fit()
    def mark_stale(self):self.status.setText('資料／尺寸／格式已改變；這是歷史比較快照，不可沿用作目前輸出核准。')

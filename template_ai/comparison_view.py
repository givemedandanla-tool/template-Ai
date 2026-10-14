"""Three synchronized read-only scenes in one template-mm coordinate domain."""
from PySide6.QtCore import QPointF,QRectF,Qt,Signal
from PySide6.QtGui import QColor,QPen,QPixmap,QTransform
from PySide6.QtWidgets import (QDialog,QDialogButtonBox,QGraphicsScene,QGraphicsView,QHBoxLayout,QLabel,QListWidget,QPushButton,QVBoxLayout,QWidget)
from .canvas_compare import template_point,source_point
from .model import KINDS


class ComparisonCanvas(QGraphicsView):
    navigated=Signal(object,float)
    picked=Signal(str)
    def __init__(self,data,mode,parent=None):
        super().__init__(parent);self.data=data;self.frames={};self._drag=None;self._moved=False
        self.setScene(QGraphicsScene(self));self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QGraphicsView.NoAnchor);self.setResizeAnchor(QGraphicsView.NoAnchor)
        self.setMinimumSize(220,260);self.setBackgroundBrush(QColor('#e2e8f0'));w,h=data['template_size']
        pixmap=QPixmap();raw=data[mode+'_png']
        if raw:
            if not pixmap.loadFromData(raw,'PNG'):raise ValueError('對照圖像解碼失敗')
            item=self.scene().addPixmap(pixmap)
            if mode=='source':
                m=data['source']['mapping'];pw,ph=m['page_size'];c=m['crop'];sx=pw*w/c['w']/pixmap.width();sy=ph*h/c['h']/pixmap.height()
                item.setTransform(QTransform.fromScale(sx,sy));item.setPos(-c['x']*w/c['w'],-c['y']*h/c['h'])
            else:item.setTransform(QTransform.fromScale(w/pixmap.width(),h/pixmap.height()))
            item.setAcceptedMouseButtons(Qt.NoButton)
        pen=QPen(QColor('#475569'));pen.setCosmetic(True)
        self.scene().addRect(QRectF(0,0,w,h),pen)
        for s in data['slots']:
            r=s['rect'];p=QPen(QColor('#64748b'));p.setCosmetic(True);p.setStyle(Qt.DashLine)
            item=self.scene().addRect(QRectF(r['x'],r['y'],r['w'],r['h']),p)
            item.setAcceptedMouseButtons(Qt.NoButton);item.setZValue(2);self.frames[s['id']]=item
        # Equal scene bounds avoid independent scrollbar clipping when panning linked views.
        self.setSceneRect(QRectF(-20000,-20000,40000,40000));self.shared_center=QPointF(w/2,h/2);self.shared_zoom=1

    def set_view(self,center,zoom):
        self.shared_center=QPointF(center);self.shared_zoom=zoom
        self.setTransform(QTransform.fromScale(zoom,zoom));self.centerOn(center)

    def highlight(self,slot_id):
        for key,item in self.frames.items():
            pen=QPen(QColor('#dc2626' if key==slot_id else '#64748b'));pen.setCosmetic(True);pen.setWidth(3 if key==slot_id else 1)
            if key!=slot_id:pen.setStyle(Qt.DashLine)
            item.setPen(pen)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        # NoAnchor otherwise keeps the old top-left and silently changes the center.
        if hasattr(self,'shared_center'):
            self.set_view(self.shared_center,self.shared_zoom)

    def wheelEvent(self,event):
        factor=1.25 if event.angleDelta().y()>0 else .8
        self.navigated.emit(self.shared_center,max(.02,min(500,self.shared_zoom*factor)));event.accept()

    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton:self._drag=event.position();self._moved=False;self.setCursor(Qt.ClosedHandCursor);event.accept()
        else:super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self._drag is not None:
            delta=event.position()-self._drag;self._drag=event.position()
            if abs(delta.x())+abs(delta.y())>1:self._moved=True
            self.navigated.emit(self.shared_center-QPointF(delta.x()/self.shared_zoom,delta.y()/self.shared_zoom),self.shared_zoom);event.accept()
        else:super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if self._drag is not None:
            if not self._moved:
                pos=self.mapToScene(event.position().toPoint());hits=[key for key,item in self.frames.items() if item.rect().contains(pos)]
                if len(hits)==1:self.picked.emit(hits[0])
            self._drag=None;self.unsetCursor();event.accept()
        else:super().mouseReleaseEvent(event)


class CanvasCompareDialog(QDialog):
    def __init__(self,data,parent=None):
        super().__init__(parent);self.data=data;self.selected_id=None;self.setWindowTitle('原稿／原模板／替代草稿 · 同步唯讀對照');self.resize(1400,790)
        layout=QVBoxLayout(self)
        label=QLabel(data['source']['reason']+'\n'+data['original_reason']+'。'+data['scope']);label.setTextFormat(Qt.PlainText);label.setWordWrap(True);layout.addWidget(label)
        bar=QHBoxLayout()
        for title,fn in (('符合矩形',self.fit_template),('符合原稿全頁',self.fit_source),('定位所選欄',self.focus_selected),('放大',lambda:self.zoom(1.25)),('縮小',lambda:self.zoom(.8))):
            b=QPushButton(title);b.clicked.connect(fn);bar.addWidget(b)
            if title=='符合原稿全頁':b.setEnabled(data['source']['mapping'] is not None)
        layout.addLayout(bar);body=QHBoxLayout();self.views=[]
        for mode,title in (('source','原稿衍生參考'),('before','原模板已知文字'),('after','替代草稿：僅所選欄改字型')):
            box=QWidget();column=QVBoxLayout(box);column.addWidget(QLabel(title));view=ComparisonCanvas(data,mode,self);self.views.append(view);column.addWidget(view);body.addWidget(box,1)
            view.navigated.connect(self.synchronize);view.picked.connect(self.select_slot)
        self.objects=QListWidget();self.objects.setMaximumWidth(250)
        for s in data['slots']:
            self.objects.addItem(f"{s['owner']}／{KINDS.get(s['kind'],s['kind'])} 第{s['index']+1}欄")
            self.objects.item(self.objects.count()-1).setData(Qt.UserRole,s['id'])
        self.objects.currentItemChanged.connect(lambda item,old:self.select_slot(item.data(Qt.UserRole)) if item else None);body.addWidget(self.objects);layout.addLayout(body,1)
        self.position=QLabel();self.position.setTextFormat(Qt.PlainText);self.position.setWordWrap(True);layout.addWidget(self.position)
        self.buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText('已查看對照，回到逐欄核准');self.buttons.button(QDialogButtonBox.Cancel).setText('返回，不核准')
        self.buttons.accepted.connect(self.accept);self.buttons.rejected.connect(self.reject);layout.addWidget(self.buttons)
        self.center=QPointF();self.zoom_value=1;self.select_slot(data['slot_id']);self.fit_template()

    def synchronize(self,center,zoom):
        self.center=QPointF(center);self.zoom_value=max(.02,min(500,zoom))
        for view in self.views:view.set_view(self.center,self.zoom_value)

    def fit_rect(self,rect):
        factor=min(min(v.viewport().width()/max(.001,rect.width()),v.viewport().height()/max(.001,rect.height())) for v in self.views)*.9
        self.synchronize(rect.center(),factor)

    def fit_template(self):
        w,h=self.data['template_size'];self.fit_rect(QRectF(0,0,w,h))

    def fit_source(self):
        m=self.data['source']['mapping']
        if not m:return
        x,y=template_point(m,0,0);xx,yy=template_point(m,*m['page_size']);self.fit_rect(QRectF(x,y,xx-x,yy-y))

    def zoom(self,factor):self.synchronize(self.center,self.zoom_value*factor)

    def select_slot(self,slot_id):
        hits=[s for s in self.data['slots'] if s['id']==slot_id]
        if len(hits)!=1:return False
        self.selected_id=slot_id;s=hits[0];r=s['rect']
        for v in self.views:v.highlight(slot_id)
        index=next(i for i in range(self.objects.count()) if self.objects.item(i).data(Qt.UserRole)==slot_id)
        self.objects.blockSignals(True);self.objects.setCurrentRow(index);self.objects.blockSignals(False)
        text=f"模板 {self.data['template_id']}／框 {slot_id}：({r['x']:g},{r['y']:g}) {r['w']:g}×{r['h']:g} mm"
        m=self.data['source']['mapping']
        if m:
            x,y=source_point(m,r['x'],r['y']);text+=f"；原頁第{m['page']}頁 ({x:g},{y:g}) {m['unit']}／歷史r{m['revision']}"
        else:text+='；來源位置未知'
        # Label is created after views / object list during construction.
        if hasattr(self,'position'):self.position.setText(text)
        self._position_text=text
        if hasattr(self,'center'):
            self.synchronize(QPointF(r['x']+r['w']/2,r['y']+r['h']/2),self.zoom_value)
        return True

    def focus_selected(self):
        s=next((s for s in self.data['slots'] if s['id']==self.selected_id),None)
        if s:
            r=s['rect'];self.fit_rect(QRectF(r['x']-2,r['y']-2,r['w']+4,r['h']+4))

    def showEvent(self,event):
        super().showEvent(event);self.position.setText(getattr(self,'_position_text',''));self.fit_template()

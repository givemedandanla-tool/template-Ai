"""View-only millimetre navigation; nominal DPI is explicitly uncalibrated."""
import math
from PySide6.QtCore import Qt,QRectF
from PySide6.QtWidgets import QWidget,QHBoxLayout,QPushButton,QLabel,QDoubleSpinBox,QSlider


def navigation_controls(canvas):
    widget=QWidget();bar=QHBoxLayout(widget);bar.setContentsMargins(0,0,0,0)
    def add(label,fn):
        b=QPushButton(label);b.clicked.connect(fn);bar.addWidget(b)
    def focus():
        items=canvas.scene().selectedItems()
        if items:
            rect=QRectF()
            for item in items:rect=rect.united(item.sceneBoundingRect())
            canvas.fitInView(rect.adjusted(-2,-2,2,2),Qt.KeepAspectRatio);canvas.view_changed.emit()
    add('全稿',canvas.fit);add('定位選取',focus);add('−',lambda:canvas.set_zoom(canvas.transform().m11()/1.25));add('＋',lambda:canvas.set_zoom(canvas.transform().m11()*1.25))
    nominal=canvas.logicalDpiX()/25.4
    add('名義實際尺寸（未校準）',lambda:canvas.set_zoom(nominal))
    spin=QDoubleSpinBox();spin.setRange(.1,20000);spin.setDecimals(2);spin.setSuffix('%');bar.addWidget(spin)
    slider=QSlider(Qt.Horizontal);slider.setRange(0,1000);slider.setMaximumWidth(150);bar.addWidget(slider)
    def refresh():
        scale=max(.2,min(500,canvas.transform().m11()))
        spin.blockSignals(True);spin.setValue(canvas.transform().m11()/nominal*100);spin.blockSignals(False)
        slider.blockSignals(True);slider.setValue(round(math.log(scale/.2)/math.log(2500)*1000));slider.blockSignals(False)
    spin.valueChanged.connect(lambda value:canvas.set_zoom(value/100*nominal))
    slider.valueChanged.connect(lambda value:canvas.set_zoom(.2*math.exp(value/1000*math.log(2500))))
    canvas.view_changed.connect(refresh);canvas.zoom_percent=spin;canvas.zoom_slider=slider;refresh()
    bar.addWidget(QLabel('僅改視角；滾輪縮放，平移模式拖曳。百分比非物理校準。'));return widget

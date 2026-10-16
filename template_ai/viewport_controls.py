"""View-only millimetre navigation; nominal DPI is explicitly uncalibrated."""
import math
from PySide6.QtCore import Qt,QRectF,QObject,QEvent
from PySide6.QtWidgets import QWidget,QHBoxLayout,QPushButton,QLabel,QDoubleSpinBox,QSlider,QApplication,QGraphicsItem,QDialog,QVBoxLayout,QDialogButtonBox,QAbstractSpinBox,QComboBox


class FocusWheelGuard(QObject):
    def eventFilter(self,widget,event):
        if event.type()==QEvent.Wheel:
            focus=QApplication.focusWidget()
            if not widget.hasFocus() and (focus is None or not widget.isAncestorOf(focus)):
                event.ignore();return True
        return super().eventFilter(widget,event)


def guard_control_wheel(widget):
    if isinstance(widget,(QAbstractSpinBox,QComboBox)) and not hasattr(widget,'_focus_wheel_guard'):
        widget._focus_wheel_guard=FocusWheelGuard(widget);widget.installEventFilter(widget._focus_wheel_guard)


def canvas_has_input_focus(canvas):
    """Qt retains authority over text/IME/popups; never dispatch from stale selection."""
    focus=QApplication.focusWidget();modal=QApplication.activeModalWidget()
    if focus not in (canvas,canvas.viewport()) or getattr(canvas,'_ime_preedit',False):return False
    if QApplication.activePopupWidget() is not None or (modal is not None and modal is not canvas.window()):return False
    item=canvas.scene().focusItem()
    return item is None or not bool(item.flags() & QGraphicsItem.ItemAcceptsInputMethod)


def allow_canvas_content(canvas,operation):
    guard=getattr(canvas,'content_guard',None)
    reason=guard(operation) if guard else ('此畫布唯讀，請使用既有編輯流程。' if canvas.readonly else '')
    if reason:canvas.command_status.emit(str(reason));return False
    return True


def dispatch_canvas_command(canvas,command):
    if not canvas.has_content_commands:canvas.command_status.emit('此畫布的內容操作請使用目前視窗既有的明確按鈕；未派送其他工作歷史。');return
    if getattr(canvas,'_command_inflight',False):canvas.command_status.emit('目前指令尚未結束；未重複提交。');return
    if not allow_canvas_content(canvas,command):return
    canvas._command_inflight=True
    try:canvas.command_requested.emit(command)
    finally:canvas._command_inflight=False


def show_canvas_help(canvas):
    dialog=QDialog(canvas.window());dialog.setWindowTitle('畫布快捷鍵與目前模式');layout=QVBoxLayout(dialog)
    ids=sorted(getattr(canvas,'selection_intent',set()))
    note=QLabel(f'目前工具：{canvas.mode}；作品 {canvas.width_mm:g}×{canvas.height_mm:g} mm\n明確選取：'+('、'.join(ids[:8]) or '無')+'\n\n先看輸入焦點，再看工具與目前物件。文字／數字／下拉選單及中文組字不派送畫布修改。\n方向鍵：可編輯框位按目前毫米步距微調；Shift×10。長按不重複提交。\nSpace：暫時平移；放開或離開焦點恢復原工具。\n滾輪／Ctrl＋、－、0：聚焦畫布後只改視角。全稿／定位／倍率亦可點選工具列。\nEsc：結束尚未提交的手勢，不放棄已保存工作或待套用欄位。\n\n鍵位與步距是可用性候選；尚未完成 Windows 輸入法／裝置相容資格驗證。');note.setWordWrap(True);note.setTextFormat(Qt.PlainText);layout.addWidget(note)
    if hasattr(canvas,'request_nudge'):
        row=QHBoxLayout();layout.addLayout(row)
        for label,dx,dy in [('向左',-1,0),('向上',0,-1),('向下',0,1),('向右',1,0)]:
            button=QPushButton(label+'（目前毫米步距）');row.addWidget(button)
            button.clicked.connect(lambda checked=False,x=dx,y=dy:(dialog.accept(),canvas.request_nudge(x,y)))
    keys=QLabel('目前畫布按鍵（可在共用畫布設定變更）：\n'+'\n'.join(name+'：'+(key or '未配置') for name,key in canvas.command_bindings.items())+'\n復原／重做沿用目前工作的既有歷史；刪除先開差異預覽，須明確核對後才套用。');keys.setWordWrap(True);keys.setTextFormat(Qt.PlainText);layout.addWidget(keys)
    if not canvas.has_content_commands:keys.setText(keys.text()+'\n此畫布的內容操作使用目前視窗既有明確按鈕；不派送其他工作歷史。')
    if not canvas.readonly and canvas.has_content_commands:
        row=QHBoxLayout();layout.addLayout(row)
        for command,label in [('UNDO','核對目前工作復原'),('REDO','核對目前工作重做'),('DELETE','預覽所選物件刪除')]:
            button=QPushButton(label);row.addWidget(button);button.clicked.connect(lambda checked=False,name=command:(dialog.accept(),dispatch_canvas_command(canvas,name)))
    buttons=QDialogButtonBox(QDialogButtonBox.Close);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons);dialog.resize(640,440);dialog.exec();dialog.deleteLater()


def navigation_controls(canvas,library=None):
    if library is not None:
        from .editor_settings import load_commands
        canvas.command_bindings=load_commands(library)
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
    add('快捷鍵／模式',lambda:show_canvas_help(canvas))
    spin=QDoubleSpinBox();spin.setRange(.1,20000);spin.setDecimals(2);spin.setSuffix('%');bar.addWidget(spin)
    guard_control_wheel(spin)
    slider=QSlider(Qt.Horizontal);slider.setRange(0,1000);slider.setMaximumWidth(150);bar.addWidget(slider)
    def refresh():
        scale=max(.2,min(500,canvas.transform().m11()))
        spin.blockSignals(True);spin.setValue(canvas.transform().m11()/nominal*100);spin.blockSignals(False)
        slider.blockSignals(True);slider.setValue(round(math.log(scale/.2)/math.log(2500)*1000));slider.blockSignals(False)
    spin.valueChanged.connect(lambda value:canvas.set_zoom(value/100*nominal))
    slider.valueChanged.connect(lambda value:canvas.set_zoom(.2*math.exp(value/1000*math.log(2500))))
    canvas.view_changed.connect(refresh);canvas.zoom_percent=spin;canvas.zoom_slider=slider;refresh()
    hint=QLabel('聚焦畫布後滾輪縮放，平移模式拖曳；百分比非物理校準。');hint.setWordWrap(True);hint.setTextFormat(Qt.PlainText);canvas.command_status.connect(hint.setText);bar.addWidget(hint);return widget

"""繁體中文三模式桌面工作台；所有背景工作都不直接改動目前畫布。"""
from __future__ import annotations
import math

import copy
import json
from pathlib import Path
import sys
import sqlite3

from PySide6.QtCore import QObject, QPointF, QRectF, QRunnable, Qt, QThreadPool, Signal, QTimer, QSignalBlocker
from PySide6.QtGui import QAction, QColor, QFont, QFontDatabase, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QDialog, QDialogButtonBox, QFontComboBox, QFormLayout, QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView,
    QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMessageBox, QPushButton, QSpinBox, QSplitter, QTabWidget, QTableWidget, QTreeWidget, QTreeWidgetItem, QPlainTextEdit,
    QTableWidgetItem, QVBoxLayout, QWidget, QStackedWidget, QScrollArea,QLayout)

from . import __version__
from .importer import import_file, inkscape_path
from .layout import Candidate, match
from .model import KINDS, Rect, Slot, Template, learn_from_labels, new_id, template_errors
from .render import export, render_image, render_background
from .background import make_background
from .storage import Library
from .fonts import FontManager


class Signals(QObject):
    done = Signal(object)
    error = Signal(str)


class Job(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = Signals()

    def run(self):
        try:
            self.signals.done.emit(self.function())
        except Exception as e:
            self.signals.error.emit(str(e))


class Box(QGraphicsRectItem):
    def __init__(self, slot: Slot, callback):
        super().__init__(0, 0, slot.rect.w, slot.rect.h)
        self.slot, self.callback = slot, callback
        self.setPos(slot.rect.x, slot.rect.y)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(2)
        pen = QPen(QColor("#2563eb"), 1)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QColor(37, 99, 235, 24))
        self.caption = KINDS.get(slot.kind, "欄位") + " · " + slot.owner

    def itemChange(self,change,value):
        if change==QGraphicsItem.ItemPositionChange and self.scene():
            views=self.scene().views()
            selected=[i for i in self.scene().selectedItems() if isinstance(i,Box)]
            locked_ids={i.slot.id for i in self.scene().items() if isinstance(i,Box) and i.slot.locked}
            intended_locked=any(locked_ids & getattr(v,'selection_intent',set()) for v in views)
            if self.slot.locked or intended_locked or any(i.slot.locked for i in selected) or any(v.readonly for v in views) or (len(selected)>1 and any(not getattr(v,'allow_multi_drag',False) for v in views)):
                return self.pos()
        return super().itemChange(change,value)

    def paint(self, p, option, widget=None):
        super().paint(p, option, widget)
        p.save()
        font = QFont()
        font.setPixelSize(2)
        p.setFont(font)
        p.setPen(QColor("#1d4ed8"))
        p.drawText(QRectF(0, -3, max(25, self.rect().width()), 3), self.caption)
        p.restore()

    def mousePressEvent(self, event):
        self.callback("before_move", self.slot)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if abs(self.pos().x() - self.slot.rect.x) > 1e-6 or abs(self.pos().y() - self.slot.rect.y) > 1e-6:
            self.slot.rect.x, self.slot.rect.y = self.pos().x(), self.pos().y()
            self.callback("moved", self.slot)


class Canvas(QGraphicsView):
    view_changed = Signal()
    rectangle = Signal(object)
    selected = Signal(object)
    moved = Signal(str, object)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor("#e8edf5"))
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.mode = "pan"
        self.start = None
        self.rubber = None
        self.width_mm, self.height_mm = 90.0, 54.0
        self.readonly = False
        self.scene().selectionChanged.connect(self.selection_changed)

    def set_content(self, width, height, image=None, slots=None, crop=None):
        self.start = None
        self.scene().clear()
        self.rubber = None
        self.width_mm, self.height_mm = width, height
        paper = self.scene().addRect(QRectF(0, 0, width, height), QPen(QColor("#cbd5e1")), QColor("white"))
        paper.setZValue(-2)
        if image is not None and not image.isNull():
            pix = self.scene().addPixmap(QPixmap.fromImage(image))
            from PySide6.QtGui import QTransform
            pix.setTransform(QTransform.fromScale(width / image.width(), height / image.height()))
            pix.setZValue(-1)
        if crop:
            pen = QPen(QColor("#d97706"), 2, Qt.DashLine)
            pen.setCosmetic(True)
            self.scene().addRect(QRectF(crop.x, crop.y, crop.w, crop.h), pen).setZValue(1)
        for slot in slots or []:
            self.scene().addItem(Box(slot, lambda action, obj: self.moved.emit(action, obj)))
        self.setSceneRect(QRectF(-5, -5, width + 10, height + 10))

    def fit(self):
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)
        self.view_changed.emit()

    def set_zoom(self,value):
        if not math.isfinite(value):return
        value=max(.2,min(500,value));self.scale(value/max(.00001,self.transform().m11()),value/max(.00001,self.transform().m22()));self.view_changed.emit()

    def set_mode(self, mode):
        if self.readonly and mode in ("edit", "slot"):
            mode = "pan"
        self.mode = mode
        self.setDragMode(QGraphicsView.ScrollHandDrag if mode == "pan" else QGraphicsView.NoDrag)
        self.setCursor(Qt.CrossCursor if mode in ("crop", "slot") else Qt.ArrowCursor)
        for item in self.scene().items():
            if isinstance(item, Box):
                item.setFlag(QGraphicsItem.ItemIsMovable, mode == "edit" and not item.slot.locked)
                item.setFlag(QGraphicsItem.ItemIsSelectable, mode == "edit")

    def selection_changed(self):
        boxes = [i for i in self.scene().selectedItems() if isinstance(i, Box)]
        self.selected.emit(boxes[0].slot if len(boxes) == 1 else None)

    def select_id(self, slot_id):
        self.scene().clearSelection()
        for item in self.scene().items():
            if isinstance(item, Box) and item.slot.id == slot_id:
                item.setSelected(True)
                self.ensureVisible(item)

    def keyPressEvent(self,event):
        if event.modifiers() & Qt.ControlModifier and event.key() in (Qt.Key_Plus,Qt.Key_Equal,Qt.Key_Minus,Qt.Key_0):
            value=self.logicalDpiX()/25.4 if event.key()==Qt.Key_0 else self.transform().m11()*(.8 if event.key()==Qt.Key_Minus else 1.25)
            self.set_zoom(value);event.accept();return
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        scale = self.transform().m11() * factor
        if 0.2 <= scale <= 500:
            self.scale(factor, factor)
            self.view_changed.emit()
        event.accept()

    def mousePressEvent(self, event):
        if self.mode in ("crop", "slot") and event.button() == Qt.LeftButton:
            self.start = self.mapToScene(event.position().toPoint())
            pen = QPen(QColor("#f59e0b"), 2)
            pen.setCosmetic(True)
            self.rubber = self.scene().addRect(QRectF(self.start, self.start), pen)
            self.rubber.setZValue(10)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.start is not None and self.rubber:
            self.rubber.setRect(QRectF(self.start, self.mapToScene(event.position().toPoint())).normalized())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.start is not None:
            rect = self.rubber.rect()
            self.scene().removeItem(self.rubber)
            self.start, self.rubber = None, None
            if rect.width() >= 0.5 and rect.height() >= 0.5:
                self.rectangle.emit(Rect(rect.x(), rect.y(), rect.width(), rect.height()))
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class MainWindow(QMainWindow):
    inputs_invalidated = Signal(int)
    def __init__(self, data_root):
        super().__init__()
        self.library = Library(data_root)
        from .training_store import TrainingStore
        TrainingStore(self.library)  # Complete schema before any read-only selection callback.
        from .diagnostic_snapshot import LocatorStore
        try:LocatorStore(self.library)
        except (OSError,ValueError):pass
        from .batch_import import BatchStore
        self.import_store=BatchStore(self.library)
        self.font_manager = FontManager(self.library,lazy=True)
        self.source_offset=0;self.template_offset=0
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.source = None
        self.crop = None
        self.work = None
        self.works = []
        self.slots = []
        self.template = None
        self.template_revision=None
        self.template_base_hash=None
        self.template_base_payload=None
        self.current_slot = None
        self.candidates = []
        self.active_input_graph = None
        self.reorder_customer_snapshot = None
        self.generation = 0
        self.undo_stack, self.redo_stack = [], []
        self._mode_memory={};self._active_mode=0
        self.busy = False
        self._background_jobs = {}
        self._waiting_launches={}
        from .runtime_supervisor import RuntimeSupervisor
        self.runtime=RuntimeSupervisor(self)
        from .runtime_dispatch import RuntimeDispatch
        self.execution_queue=RuntimeDispatch(self)
        self.loading_form = False
        self.setWindowTitle(f"Template AI {__version__} · 矩形排版研究版")
        self.resize(1340, 850)
        self.setMinimumSize(960, 640)
        self.build_ui()
        self.refresh_sources()
        self.refresh_templates()
        self.refresh_logos()
        from .workbench_navigation import WorkbenchNavigation
        self.navigation=WorkbenchNavigation(self,self.work_context,self.return_work_button)
        self.statusBar().showMessage("本機研究版 · 請使用匿名／合成資料 · 實體印刷分析尚未執行")
        if self.font_manager.issues:
            self.statusBar().showMessage("字型資產需處理：" + "；".join(self.font_manager.issues))
        from .backup_center import BackupScheduler
        self.backup_scheduler=BackupScheduler(self)
        from .source_watch import SourceWatchService
        self.source_watch=SourceWatchService(self)
        QTimer.singleShot(500,self,self.recover_import_startup)
        if (self.library.root/'RESTORE_REPORT.json').is_file():
            self.setWindowTitle(self.windowTitle()+' · 還原副本（需重新驗證）')
            self.statusBar().showMessage('目前為隔離還原副本；原環境保留，來源／字型／學習與正式輸出需重新驗證')

    def recover_import_startup(self):
        if self.library.closed:return
        try:self.import_store.recover(limit=20)
        except Exception as error:self.statusBar().showMessage('匯入斷點尚未核實；已停止恢復，請從診斷處理：'+str(error))

    def sync_property_mode(self,*args):
        browsing=self.tabs.currentIndex()==1 and self.template_stack.currentIndex()==0
        self.property_fields.setVisible(self.tabs.currentIndex()!=2);self.selected_info.setVisible(self.tabs.currentIndex()!=2);self.output_properties.setVisible(self.tabs.currentIndex()==2)
        self.property_panel.setEnabled(not browsing)
        self.property_panel.setToolTip("模板瀏覽為唯讀；先明確開啟模板編輯區" if browsing else "")

    def closeEvent(self,event):
        if hasattr(self,'template_catalog'):self.template_catalog.close_previews()
        super().closeEvent(event)

    def button(self, text, action, layout):
        button = QPushButton(text)
        button.clicked.connect(action)
        layout.addWidget(button)
        return button

    def build_ui(self):
        root = QWidget()
        outer = QVBoxLayout(root)
        title = QLabel("Template AI   矩形區域自動排版與模板學習")
        title.setObjectName("title")
        header=QHBoxLayout();header.addWidget(title,1);outer.addLayout(header)
        context_row=QHBoxLayout();self.work_context=QLabel();self.work_context.setWordWrap(True)
        self.work_context.setAccessibleName('當次工作位置與保存狀態');context_row.addWidget(self.work_context,1)
        self.return_work_button=QPushButton('返回原工作');context_row.addWidget(self.return_work_button);outer.addLayout(context_row)
        title.setToolTip("匯入原稿 → 視覺核對與標記 → 學習並發布模板 → 輸入人物資料 → 驗證與數位輸出")
        splitter = QSplitter();self.workspace_splitter=splitter
        rail=QWidget();rail.setMaximumWidth(185);rail_layout=QVBoxLayout(rail)
        for label,index in [('訓練與原稿',0),('模板／Logo',1),('排版與輸出',2)]:
            button=QPushButton(label);button.clicked.connect(lambda _,i=index:self.navigate_mode(i));rail_layout.addWidget(button)
        self.function_stack=QStackedWidget()
        groups=[ [('一鍵來源分析',self.automatic_training),('來源／作品總覽',self.work_overview),('品質／規則／學習',self.training_center)],
                 [('模板瀏覽',self.return_catalog),('新版本草稿',self.new_version),('物件／精確對齊',self.object_tools),('版本差異／回退',self.template_versions),('尺寸Logo庫',self.logo_center)],
                 [('人物／公司輸入',self.edit_input_graph),('產生排版候選',self.generate),('預覽數位輸出',lambda:self.export_current(True)),('正式數位輸出',lambda:self.export_current(False))] ]
        for group in groups:
            panel=QWidget();panel_layout=QVBoxLayout(panel)
            for label,fn in group:self.button(label,fn,panel_layout)
            panel_layout.addStretch();self.function_stack.addWidget(panel)
        rail_layout.addWidget(self.function_stack,1)
        for label,fn in [('共用字型管理',self.font_center),('共用畫布設定',self.editor_settings),('目前問題診斷',self.shared_diagnostic),('低負載／背景暫停',self.runtime_center)]:self.button(label,fn,rail_layout)
        rail_layout.addStretch();self.function_rail=rail;splitter.addWidget(rail)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.build_training(), "① 訓練與原稿標記")
        self.tabs.addTab(self.build_templates(), "② 模板與 Logo")
        self.tabs.addTab(self.build_output(), "③ 排版與輸出")
        self.tabs.currentChanged.connect(self.mode_changed)
        splitter.addWidget(self.tabs)
        self.property_panel=self.build_properties()
        splitter.addWidget(self.property_panel)
        self.tabs.currentChanged.connect(self.sync_property_mode)
        self.template_stack.currentChanged.connect(self.sync_property_mode)
        self.sync_property_mode()
        for label,panel in [('功能導覽',rail),('屬性面板',self.property_panel)]:
            action=QPushButton(label+' 顯示／收合');action.clicked.connect(lambda _,p=panel:p.setVisible(not p.isVisible()));header.addWidget(action)
        splitter.setSizes([160,1000,300])
        outer.addWidget(splitter, 1)
        self.setCentralWidget(root)
        self.setStyleSheet("""
        QWidget {font-size: 13px; color: #17243b;} QMainWindow {background: #f7f9fc;}
        QLabel#title {font-size: 23px; font-weight: 700; color: #163b72; padding: 8px 0;}
        QPushButton {padding: 7px 11px; border: 1px solid #cbd5e1; border-radius: 5px; background: white;}
        QPushButton:hover {background: #eaf1ff; border-color: #2563eb;}
        QPushButton:disabled {color: #94a3b8; background: #eef2f7;}
        QGroupBox {font-weight: 600; border: 1px solid #d7dfeb; border-radius: 6px; margin-top: 12px; padding-top: 12px;}
        QGroupBox::title {subcontrol-origin: margin; left: 10px; padding: 0 4px;}
        QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {min-height: 25px;}
        QTabBar::tab {padding: 11px 15px;} QTabBar::tab:selected {color: #1d4ed8; font-weight: 700;}
        """)
        self.menuBar().addAction("復原目前標記／草稿", self.undo)
        self.menuBar().addAction("重做目前標記／草稿", self.redo)
        self.menuBar().addAction("匯入合法本機字型", self.import_font)
        self.menuBar().addAction("修復既有本機字型", self.repair_font)
        self.menuBar().addAction("共用字型管理中心", self.font_center)
        self.menuBar().addAction('本機完整關聯備份／還原',self.backup_center)
        self.menuBar().addAction("共用畫布設定",self.editor_settings)
        self.menuBar().addAction("字型替代審核歷史", self.font_review_history)
        self.menuBar().addAction("本機客戶／版型與備份", self.customer_center)
        self.menuBar().addAction("尺寸獨立 Logo 庫", self.logo_center)
        self.menuBar().addAction("多作品安全批次對齊", self.batch_object_center)
        self.menuBar().addAction("輸入問題定位（既有診斷）", lambda: self.open_diagnostic('input'))
        self.menuBar().addAction("輸入問題報告", lambda: self.diagnostic_report("input"))
        self.menuBar().addAction("當前候選問題報告", lambda: self.diagnostic_report("candidate"))
        self.menuBar().addAction("當前模板問題報告", lambda: self.diagnostic_report("template"))
        self.menuBar().addAction("開啟歷史診斷報告", self.open_report_file)
        self.menuBar().addAction("清除本機報告定位索引", self.clear_report_locators)
        self.menuBar().addAction("來源根目錄安全重掃", self.source_scan_center)
        self.menuBar().addAction("操作說明", self.help)

    def diagnostic_report(self, kind, work_id=None):
        from .diagnostic_dialog import DiagnosticReportDialog
        dialog=DiagnosticReportDialog(self,kind,work_id)
        try:dialog.exec()
        finally:dialog.deleteLater()

    def editor_settings(self):
        from .editor_settings import EditorSettingsDialog
        dialog=EditorSettingsDialog(self);dialog.exec();dialog.deleteLater()

    def shared_diagnostic(self):
        try:
            index=self.tabs.currentIndex();self.diagnostic_report('training' if index==0 else 'template' if index==1 else 'input',self.work['id'] if index==0 and self.work else None)
        except Exception as error:self.error(str(error))

    def open_report_file(self):
        from .diagnostic_dialog import open_saved_report
        try:open_saved_report(self)
        except Exception as error:self.error(str(error))

    def clear_report_locators(self):
        from .diagnostic_snapshot import LocatorStore
        try:
            LocatorStore(self.library).clear()
            self.inform('本機報告定位索引已清除；已保存的安全報告檔仍保留。')
        except Exception as error:self.error(str(error))

    def source_scan_center(self):
        from .source_scan_dialog import SourceScanDialog
        dialog=SourceScanDialog(self)
        self.navigation.begin('來源修正')
        try:dialog.exec()
        finally:dialog.deleteLater();self.navigation.finish()

    def open_diagnostic(self, kind):
        from .diagnostic_routes import open_diagnostic
        try:return open_diagnostic(self,kind)
        except Exception as error:self.error(str(error))

    def batch_object_center(self):
        from .batch_objects import BatchObjectDialog
        dialog=BatchObjectDialog(self)
        try:dialog.exec()
        finally:dialog.deleteLater()

    def logo_center(self,*,return_origin=None):
        if self.busy:
            self.inform('背景工作進行中，請保留目前作用範圍')
            return
        from .logo_library_dialog import LogoLibraryDialog
        dialog = LogoLibraryDialog(self)
        if return_origin is not None:dialog.focus_size(*return_origin.entry()['size_mm'])
        self.navigation.begin('尺寸 Logo 管理',origin=return_origin)
        try: dialog.exec()
        finally: dialog.deleteLater();self.navigation.finish()

    def customer_center(self):
        from .customer_dialog import CustomerDialog
        dialog = CustomerDialog(self)
        try: dialog.exec()
        finally: dialog.deleteLater()

    def build_training(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        toolbar = QHBoxLayout()
        self.import_button = self.button("匯入 AI／PDF／SVG／圖片", self.import_source, toolbar)
        self.page = QSpinBox()
        self.page.setRange(1, 999)
        self.page.setPrefix("頁碼 ")
        toolbar.addWidget(self.page)
        self.button("框選作品", lambda: self.train_canvas.set_mode("crop"), toolbar)
        self.button("新增欄位框", lambda: self.train_canvas.set_mode("slot"), toolbar)
        self.button("選取／移動", lambda: self.train_canvas.set_mode("edit"), toolbar)
        self.button("平移", lambda: self.train_canvas.set_mode("pan"), toolbar)
        self.button("全稿", lambda: self.train_canvas.fit(), toolbar)
        layout.addLayout(toolbar)
        self.source_combo = QComboBox()
        self.source_combo.currentIndexChanged.connect(self.choose_source)
        layout.addWidget(self.source_combo)
        source_pages=QHBoxLayout();self.source_previous=self.button('上頁來源',lambda:self.source_page(-48),source_pages);self.source_next=self.button('下頁來源',lambda:self.source_page(48),source_pages);self.source_count=QLabel();source_pages.addWidget(self.source_count);layout.addLayout(source_pages)
        links_row = QHBoxLayout()
        self.button("檢查原稿連結", self.check_source_link, links_row)
        self.button("重新連結同內容原稿", self.relink_source, links_row)
        self.button("批次來源定位／復原", self.batch_source_links, links_row)
        self.button("批次匯入／取消與續跑", self.batch_import, links_row)
        self.button("來源匯入例外中心", self.import_exceptions, links_row)
        links_row.addStretch()
        layout.addLayout(links_row)
        workflow_row=QHBoxLayout()
        self.button("預檢後一鍵自動訓練",self.automatic_training,workflow_row)
        self.button("本機字串語意模型",self.semantic_learning,workflow_row)
        self.button("來源／作品總覽與校正",self.work_overview,workflow_row)
        workflow_row.addStretch();layout.addLayout(workflow_row)
        works_row = QHBoxLayout()
        works_row.addWidget(QLabel("目前作品"))
        self.work_combo = QComboBox()
        self.work_combo.currentIndexChanged.connect(self.choose_work)
        works_row.addWidget(self.work_combo, 1)
        self.button("重新命名作品", self.rename_work, works_row)
        self.button("標記歷史／恢復", self.restore_work, works_row)
        self.button("標記品質／規則與可信樣本", self.training_center, works_row)
        self.source_repair_button=self.button("目前原稿局部修復",self.source_repair,works_row)
        layout.addLayout(works_row)
        self.source_info = QLabel("選取一份來源；一個檔案可以逐作品框選、保存標記並學習不同模板。")
        self.source_info.setWordWrap(True)
        layout.addWidget(self.source_info)
        split = QSplitter()
        self.train_canvas = Canvas()
        self.train_canvas.rectangle.connect(self.add_rectangle)
        self.train_canvas.selected.connect(self.select_slot)
        self.train_canvas.moved.connect(self.box_moved)
        split.addWidget(self.train_canvas)
        from .viewport_controls import navigation_controls
        layout.addWidget(navigation_controls(self.train_canvas))
        self.slot_list = QListWidget()
        self.slot_list.currentRowChanged.connect(self.list_selection)
        split.addWidget(self.slot_list)
        split.setSizes([750, 160])
        layout.addWidget(split, 1)
        row = QHBoxLayout()
        self.visual = QCheckBox("已與可信原稿對照，確認此作品視覺一致")
        self.visual.toggled.connect(self.labels_changed)
        row.addWidget(self.visual)
        self.button("載入參考圖比對", self.compare_reference, row)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.button("保存標記／恢復點", self.save_labels, row)
        self.button("依標記學習模板", self.learn_template, row)
        self.button("將選取框核准為 Logo", self.capture_logo, row)
        self.button("刪除選取標記", self.delete_slot, row)
        self.button("安全多選／精確對齊", self.object_tools, row)
        layout.addLayout(row)
        return widget

    def build_templates(self):
        from .catalog_widget import CatalogWidget
        self.template_stack=QStackedWidget()
        editor=self.build_template_editor()
        self.template_catalog=CatalogWidget(self)
        self.template_stack.addWidget(self.template_catalog);self.template_stack.addWidget(editor)
        return self.template_stack

    def open_catalog_editor(self,template_id):
        from .training_navigation import require_clean_navigation
        require_clean_navigation(self)
        index=next((i for i,t in enumerate(self.templates) if t.id==template_id),None)
        if index is None:
            self.refresh_templates(select=template_id)
            index=next((i for i,t in enumerate(self.templates) if t.id==template_id),None)
        if index is None:raise ValueError('模板已失聯，未開啟其他版本')
        self.template_list.setCurrentRow(index)
        if not self.template or self.template.id!=template_id:self.choose_template(index)
        self.template_stack.setCurrentIndex(1);self.tabs.setCurrentIndex(1)
        self.statusBar().showMessage('明確進入模板編輯區；已發布版本唯讀，另建新版草稿才可修改')

    def return_catalog(self):
        from .training_navigation import require_clean_navigation
        try:
            require_clean_navigation(self);self.current_slot=None;self.property_button.setEnabled(False);self.template_catalog.reload();self.template_stack.setCurrentIndex(0)
        except ValueError as error:self.error(str(error))

    def build_template_editor(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        row = QHBoxLayout()
        self.button("返回唯讀模板瀏覽", self.return_catalog, row)
        self.button("新增空白矩形模板", self.new_template, row)
        self.button("加入合成示範模板", self.add_demo, row)
        self.button("建立新版本草稿", self.new_version, row)
        self.button("版本差異／回退草稿", self.template_versions, row)
        self.button("保存草稿", self.save_draft, row)
        self.button("驗證並發布", self.publish_template, row)
        layout.addLayout(row)
        split = QSplitter()
        self.template_list = QListWidget()
        self.template_list.currentRowChanged.connect(self.choose_template)
        left=QWidget();left_layout=QVBoxLayout(left);left_layout.addWidget(self.template_list)
        template_pages=QHBoxLayout();self.template_previous=self.button('上頁模板',lambda:self.template_page(-48),template_pages);self.template_next=self.button('下頁模板',lambda:self.template_page(48),template_pages);self.template_count=QLabel();template_pages.addWidget(self.template_count);left_layout.addLayout(template_pages)
        self.editor_tree=QTreeWidget();self.editor_tree.setHeaderLabel('人物／公司／欄位（共享引用）');self.editor_tree.setSelectionMode(QTreeWidget.ExtendedSelection);self.editor_tree.itemSelectionChanged.connect(self.editor_tree_selection);left_layout.addWidget(self.editor_tree);split.addWidget(left)
        from .object_dialog import ObjectCanvas,canvas_controls
        self.edit_canvas = ObjectCanvas();self.edit_canvas.allow_multi_drag=False
        self.edit_canvas.selection_ids.connect(self.editor_selection)
        self.edit_canvas.drag_proposal.connect(self.editor_canvas_apply)
        self.edit_canvas.preview_proposal.connect(self.editor_canvas_preview)
        self.edit_canvas.rectangle.connect(self.add_rectangle)
        split.addWidget(self.edit_canvas)
        from .viewport_controls import navigation_controls
        layout.addWidget(canvas_controls(self.edit_canvas,self.library))
        split.setSizes([230, 720])
        layout.addWidget(split, 1)
        row = QHBoxLayout()
        self.button("新增模板欄位", lambda: self.edit_canvas.set_mode("slot"), row)
        self.button("選取／移動", lambda: self.edit_canvas.set_mode("edit"), row)
        self.button("全稿", lambda: self.edit_canvas.fit(), row)
        self.button("刪除欄位", self.delete_slot, row)
        self.button("安全多選／精確對齊", self.object_tools, row)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.background_button = self.button("匯入乾淨固定背景", self.import_background, row)
        self.clear_background_button = self.button("移除固定背景", self.clear_background, row)
        row.addStretch(1)
        layout.addLayout(row)
        self.template_info = QLabel("已發布版本唯讀，修改時建立新版本草稿；學習方式為人工標記幾何規則。")
        self.template_info.setWordWrap(True)
        layout.addWidget(self.template_info)
        row = QHBoxLayout()
        self.button("匯入並核准完整 Logo", self.import_logo, row)
        self.logo_list = QComboBox()
        row.addWidget(self.logo_list, 1)
        layout.addLayout(row)
        return widget

    def build_output(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        size_row = QHBoxLayout()
        self.out_w, self.out_h = QDoubleSpinBox(), QDoubleSpinBox()
        for spin, value in [(self.out_w, 90), (self.out_h, 54)]:
            spin.setRange(1, 2000)
            spin.setDecimals(3)
            spin.setValue(value)
            spin.setSuffix(" mm")
            spin.valueChanged.connect(self.invalidate)
        size_row.addWidget(QLabel("矩形寬／高"))
        size_row.addWidget(self.out_w)
        size_row.addWidget(self.out_h)
        self.button("開始自動排版", self.generate, size_row)
        self.layout_session_button=self.button("排版進度／恢復", self.layout_session, size_row)
        self.layout_session_button.setToolTip("當次真實進度、暫停／取消及恢復上一次未完成的排版")
        from .layout_recovery import LayoutRecovery
        try:
            if LayoutRecovery(self.library.root).pending():self.layout_session_button.setText("恢復排版")
        except (OSError,ValueError):self.layout_session_button.setText("核實恢復暫存")
        self.button('多尺寸驗證／部分輸出',self.multi_size,size_row)
        self.button("解除重訂版型限定", self.clear_reorder_filter, size_row)
        self.button("當次候選局部修改", self.candidate_editor, size_row)
        layout.addLayout(size_row)
        self.graph_status = QLabel("當次輸入：可開人物卡片建立共享公司與多筆聯絡資料；下方為相容簡易表格。")
        self.graph_status.setWordWrap(True)
        layout.addWidget(self.graph_status)
        graph_bar = QHBoxLayout()
        self.graph_button = self.button("人物ROOT卡片／共享公司與聯絡資料", self.edit_input_graph, graph_bar)
        self.button("清除當次輸入並回到簡易表格", self.clear_input_graph, graph_bar)
        layout.addLayout(graph_bar)
        self.legacy_input_panel=QGroupBox('相容表格輸入／輸入問題（展開或收合）');self.legacy_input_panel.setCheckable(True)
        table_container=QWidget();table_layout=QVBoxLayout(table_container);table_scroll=QScrollArea();table_scroll.setWidgetResizable(True);table_scroll.setWidget(table_container);table_scroll.setMaximumHeight(260);self.legacy_table_scroll=table_scroll
        group_layout=QVBoxLayout(self.legacy_input_panel);group_layout.addWidget(table_scroll);self.legacy_input_panel.toggled.connect(table_scroll.setVisible);self.legacy_input_panel.setChecked(False);layout.addWidget(self.legacy_input_panel)
        self.people = QTableWidget(1, 8)
        self.people.setHorizontalHeaderLabels(["姓名", "職稱", "電話", "Email", "LINE", "IG", "地址", "公司序號"])
        self.people.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.people.setMaximumHeight(115)
        self.people.itemChanged.connect(self.invalidate)
        table_layout.addWidget(QLabel("人物資料：多筆同類聯絡資訊以「；」分隔，公司序號對應下方公司 1、2…"))
        table_layout.addWidget(self.people)
        row = QHBoxLayout()
        self.button("輸入問題報告", lambda: self.diagnostic_report("input"), row)
        self.button("新增人物", lambda: self.add_row(self.people), row)
        self.button("移除選取人物", lambda: self.remove_row(self.people), row)
        self.button("填入匿名示範資料", self.demo_input, row)
        table_layout.addLayout(row)
        self.companies = QTableWidget(1, 2)
        self.companies.setHorizontalHeaderLabels(["公司名稱", "已核准 Logo（依目前尺寸選取）"])
        self.companies.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.companies.setMaximumHeight(75)
        self.companies.itemChanged.connect(self.invalidate)
        table_layout.addWidget(self.companies)
        from .input_warning_delegate import InputWarningDelegate
        self.people.setItemDelegate(InputWarningDelegate(self.people));self.companies.setItemDelegate(InputWarningDelegate(self.companies))
        self.input_state = QLabel('輸入待驗證；欄位提示不代表印前通過')
        layout.insertWidget(1,self.input_state)
        self.input_problems = QListWidget()
        self.input_problems.setMaximumHeight(100)
        self.input_problems.itemClicked.connect(self.locate_input_problem)
        table_layout.addWidget(self.input_problems)
        self.input_timer = QTimer(self)
        self.input_timer.setSingleShot(True)
        self.input_timer.timeout.connect(self.refresh_input_problems)
        row = QHBoxLayout()
        self.button("新增公司", self.add_company, row)
        self.button("移除選取公司", lambda: self.remove_row(self.companies), row)
        self.button("更新同尺寸 Logo 選項", self.refresh_logos, row)
        table_layout.addLayout(row)
        split = QSplitter()
        self.button('無合格現成模板：授權特製草稿',self.custom_layout,layout)
        self.candidate_list = QListWidget()
        self.candidate_list.currentRowChanged.connect(self.choose_candidate)
        self.candidate_list.hide()
        candidate_panel=QWidget();candidate_layout=QVBoxLayout(candidate_panel);self.qualified_candidates=QListWidget();self.review_candidates=QListWidget();self.blocked_candidates=QListWidget()
        for title,view in [('安全候選（輸出前重核）',self.qualified_candidates),('待確認／來源不明草稿（禁止正式輸出）',self.review_candidates),('硬性阻擋候選（禁止正式輸出）',self.blocked_candidates)]:
            candidate_layout.addWidget(QLabel(title));candidate_layout.addWidget(view)
            view.currentItemChanged.connect(lambda item,previous:self.candidate_list.setCurrentRow(item.data(Qt.UserRole)) if item else None)
        self.button("保留當次待確認草稿",self.keep_review_draft,candidate_layout)
        self.button("修正後重新檢查當前候選",self.recheck_candidate,candidate_layout)
        self.button('重新計算受影響候選',self.recheck_affected_candidates,candidate_layout)
        self.dependency_notice=QLabel('選取候選可檢視變更依賴與受影響框位');self.dependency_notice.setWordWrap(True);self.dependency_notice.setMinimumHeight(96);candidate_layout.addWidget(self.dependency_notice)
        candidate_layout.removeWidget(self.dependency_notice);candidate_layout.insertWidget(0,self.dependency_notice)
        self.result_recommendation=QLabel('尚無已驗證候選');self.result_recommendation.setWordWrap(True);candidate_layout.insertWidget(0,self.result_recommendation)
        self.recommended_button=QPushButton('查看目前合格推薦');self.recommended_button.clicked.connect(self.select_recommended_candidate);candidate_layout.insertWidget(1,self.recommended_button)
        self.button('展開候選比較／驗證差異',self.compare_candidate_results,candidate_layout)
        self.result_problem_items=QListWidget();self.result_problem_items.setMaximumHeight(140);self.result_problem_items.itemClicked.connect(self.locate_result_problem);candidate_layout.addWidget(self.result_problem_items)
        self.button('由此問題開啟既有修正入口',self.fix_result_problem,candidate_layout)
        self.candidate_scroll=QScrollArea();self.candidate_scroll.setWidgetResizable(True);self.candidate_scroll.setWidget(candidate_panel);self.candidate_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.candidate_scroll.setMinimumWidth(270);split.addWidget(self.candidate_scroll)
        self.output_canvas = Canvas()
        self.output_canvas.setMinimumHeight(240)
        split.addWidget(self.output_canvas)
        from .viewport_controls import navigation_controls
        layout.addWidget(navigation_controls(self.output_canvas))
        split.setSizes([220, 740])
        layout.addWidget(split, 1)
        self.issues = QLabel("輸入資料後開始排版。缺少同尺寸真實 Logo 或超出固定字級字寬限制時，正式輸出會被阻擋。")
        self.issues.setWordWrap(True)
        layout.addWidget(self.issues)
        self.button("候選問題報告", lambda: self.diagnostic_report("candidate"), layout)
        row = QHBoxLayout()
        self.dpi = QSpinBox()
        self.dpi.setRange(72, 600)
        self.dpi.setValue(300)
        self.dpi.setSuffix(" DPI（數位設定）")
        row.addWidget(self.dpi)
        self.export_button = self.button("輸出正式 PDF／PNG／JPG", lambda: self.export_current(False), row)
        self.preview_button = self.button("輸出非正式 PREVIEW", lambda: self.export_current(True), row)
        self.export_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        layout.addLayout(row)
        # Let existing controls scroll at small resolutions instead of clipping
        # the central canvas below its declared physical-view minimum.
        layout.setSizeConstraint(QLayout.SetMinimumSize)
        self.output_page_scroll=QScrollArea();self.output_page_scroll.setWidgetResizable(True)
        self.output_page_scroll.setWidget(widget)
        return self.output_page_scroll

    def candidate_editor(self):
        from .candidate_edit import CandidateEditDialog
        dialog=CandidateEditDialog(self)
        try:dialog.exec()
        finally:dialog.deleteLater()

    def multi_size(self):
        from .multi_size_dialog import MultiSizeDialog
        dialog=MultiSizeDialog(self)
        try:dialog.exec()
        finally:dialog.deleteLater()

    def clear_reorder_filter(self):
        self.reorder_template_id=None
        self.invalidate()

    def layout_session(self):
        from .layout_session import LayoutSessionDialog
        dialog=getattr(self,'foreground_layout_session',None)
        if dialog is None:dialog=LayoutSessionDialog(self);self.foreground_layout_session=dialog
        dialog.show();dialog.raise_()

    def build_properties(self):
        widget = QWidget()
        widget.setMinimumWidth(260)
        layout = QVBoxLayout(widget)
        group = QGroupBox("目前欄位 · 毫米屬性");self.property_fields=group
        form = QFormLayout(group)
        self.kind = QComboBox()
        for key, name in KINDS.items():
            self.kind.addItem(name, key)
        self.owner = QComboBox()
        for prefix, label in [("p", "人物"), ("c", "公司")]:
            for number in range(1, 21):
                self.owner.addItem(f"{label} {number}", f"{prefix}{number}")
        self.index = QSpinBox()
        self.index.setRange(1, 20)
        self.coords = []
        for name in ["X", "Y", "寬", "高"]:
            spin = QDoubleSpinBox()
            spin.setRange(-2000, 2000)
            spin.setDecimals(3)
            spin.setSuffix(" mm")
            form.addRow(name, spin)
            self.coords.append(spin)
        self.font = QFontComboBox()
        from .demo import default_font
        self.font.setCurrentFont(QFont(default_font()))
        self.pt = QDoubleSpinBox()
        self.pt.setRange(1, 200)
        self.pt.setValue(10)
        self.pt.setSuffix(" pt（固定）")
        self.text_color = QLineEdit("#111827")
        self.text_color.setMaxLength(7)
        self.text_color.setPlaceholderText("#RRGGBB")
        self.scale = QDoubleSpinBox()
        self.scale.setRange(5, 100)
        self.scale.setValue(85)
        self.scale.setSuffix(" %")
        self.align = QComboBox()
        for name, value in [("靠左", "left"), ("置中", "center"), ("靠右", "right")]:
            self.align.addItem(name, value)
        self.required = QCheckBox("必要欄位")
        self.required.setChecked(True)
        form.addRow("類型", self.kind)
        form.addRow("歸屬", self.owner)
        form.addRow("同類資料第幾筆", self.index)
        form.addRow("字型", self.font)
        form.addRow("定案字級", self.pt)
        form.addRow("文字色彩", self.text_color)
        form.addRow("本模板字寬下限", self.scale)
        self.align.addItem("分散（需獨立核准欄位規則）","distributed")
        form.addRow("對齊", self.align)
        policy_button=QPushButton("字距／語意分散規則");policy_button.clicked.connect(self.text_policy_editor);form.addRow(policy_button)
        form.addRow(self.required)
        self.property_button = QPushButton("套用至選取欄位")
        self.property_button.clicked.connect(self.apply_properties)
        form.addRow(self.property_button)
        layout.addWidget(group)
        self.selected_info = QLabel("先在畫布選取一個欄位。\n字級定案後不因字數自動改變。\n字寬下限是模板設計值，尚未實體印刷驗證。")
        self.selected_info.setWordWrap(True)
        layout.addWidget(self.selected_info)
        self.output_properties=QPlainTextEdit();self.output_properties.setReadOnly(True);self.output_properties.setPlainText('尚無目前候選；請完成輸入並試排。');layout.addWidget(self.output_properties,1)
        layout.addWidget(QLabel('標記／規則須明確核准；本機資料不會自動上傳。'))
        return widget

    def inform(self, text):
        QMessageBox.information(self, "Template AI", text)

    def error(self, text):
        self.statusBar().showMessage("操作未完成：" + text[:150])
        QMessageBox.warning(self, "需要處理", text)

    def runtime_center(self):
        from .runtime_panel import RuntimePanel
        panel=RuntimePanel(self);panel.setAttribute(Qt.WA_DeleteOnClose);panel.show();return panel

    def cancel_waiting_jobs(self):
        for cancel in self._waiting_launches.values():cancel.set()
        self.statusBar().showMessage('已請求取消尚未啟動的工作；當前已執行的原子步驟請在工作面板安全取消')

    def run_job(self, message, function, callback,*,on_error=None,resource_kind='ANALYSIS',cancel=None):
        """Legacy immediate launch failures raise; deferred failures use the explicit error callback."""
        if self.busy:
            self.inform("目前仍有背景匯入工作，請等待完成")
            return
        self.busy = True
        self.import_button.setEnabled(False)
        self.statusBar().showMessage(message + " · 背景執行中，完成前不宣稱成功")
        job = Job(function)
        token = new_id()
        if cancel is None:
            import threading
            cancel=getattr(callback,'cancel_event',None) or threading.Event()
        self._waiting_launches[token]=cancel
        self._background_jobs[token] = job
        job.signals.setParent(self)
        def release():
            self._waiting_launches.pop(token,None)
            self._background_jobs.pop(token, None)
            job.signals.deleteLater()
        def finished(value):
            self.busy = False
            self.import_button.setEnabled(True)
            self.statusBar().showMessage(message+' · 背景步驟已結束；請核對目前工作結果')
            try:
                callback(value)
            except Exception as e:
                self.error(str(e))
            finally:
                release()
        def failed(text):
            self.busy = False
            self.import_button.setEnabled(True)
            self.statusBar().showMessage(message+' · 工作未完成；尚未宣稱保存成功')
            try:
                (on_error or getattr(callback,'error',None) or self.error)(text)
            finally:
                release()
        job.signals.done.connect(finished, Qt.QueuedConnection)
        job.signals.error.connect(failed, Qt.QueuedConnection)
        context=self.library
        def launch(deferred=False):
            if context.closed or self.library is not context:
                self.busy=False;release();return
            if cancel.is_set():failed('已取消尚未啟動的工作；沒有新增成果');return
            decision=self.runtime.admit(resource_kind,foreground=True)
            if not decision.allowed:
                self.statusBar().showMessage(message+' · 等待資源；尚未執行／保存：'+','.join(decision.reasons))
                QTimer.singleShot(500,self,lambda:launch(True));return
            self._waiting_launches.pop(token,None)
            try:self.pool.start(job)
            except Exception as error:
                if not deferred and on_error is None:
                    self.busy=False;self.import_button.setEnabled(True);release();raise
                failed(str(error))
        launch()

    def import_source(self):
        path, _ = QFileDialog.getOpenFileName(self, "選擇只讀原稿", "", "設計來源 (*.ai *.pdf *.svg *.eps *.png *.jpg *.jpeg)")
        if not path:
            return
        page = self.page.value()
        self.run_job("匯入與建立來源預覽", lambda: import_file(path, self.library.assets, page),
                     lambda result: self.source_imported(path, result))

    def source_imported(self, path, result):
        source = self.library.add_source(Path(path), result)
        self.refresh_sources(source["id"])
        self.statusBar().showMessage("來源已保存；" + ("重用同內容解析，保留本次來源登錄" if result.get("reused") else "視覺一致性仍待原稿核對"))

    def automatic_training(self):
        if self.busy:return
        from .automatic_training_dialog import AutomaticTrainingDialog
        dialog=AutomaticTrainingDialog(self);dialog.exec();dialog.deleteLater()

    def semantic_learning(self):
        if self.busy:return
        from .semantic_learning_dialog import SemanticLearningDialog
        dialog=SemanticLearningDialog(self);dialog.exec();dialog.deleteLater()

    def work_overview(self):
        if self.busy:return
        from .work_overview_dialog import WorkOverviewDialog
        dialog=WorkOverviewDialog(self);dialog.exec();dialog.deleteLater()

    def schedule_affected_work(self,work_id):
        from .automatic_training import AutomaticTraining
        from .automatic_training_dialog import AutomaticTrainingDialog
        service=AutomaticTraining(self.library);plan=service.retry_plan([work_id]);job=service.create_retry(plan,'CONFIRMED_WORK_INCREMENTAL',True)
        dialog=AutomaticTrainingDialog(self);dialog.setAttribute(Qt.WA_DeleteOnClose);dialog.show();dialog.start_job(job)
        self.statusBar().showMessage('已排入確切作品增量重分析：'+work_id+'；主編輯草稿保留，引用模板依原版次重新核驗。')

    def batch_import(self):
        if self.busy:return
        from .batch_dialog import BatchImportDialog
        dialog=BatchImportDialog(self)
        try:dialog.exec()
        finally:dialog.deleteLater()

    def import_exceptions(self):
        if self.busy:return
        from .exception_dialog import ImportExceptionDialog
        dialog=ImportExceptionDialog(self)
        try:dialog.exec()
        finally:dialog.deleteLater()

    def check_source_link(self):
        if not self.source or self.busy:
            return
        from .source_links import source_status
        source = dict(self.source)
        self.run_job("唯讀檢查原稿內容", lambda: source_status(source),
                     lambda result: self.inform(result["message"] + "\n目前位置：" + result["path"]))

    def batch_source_links(self):
        if self.busy:
            return
        from .source_dialog import SourceRelinkDialog
        SourceRelinkDialog(self).exec()

    def font_center(self):
        if self.busy: return
        from .font_dialog import FontCenterDialog
        dialog = FontCenterDialog(self)
        self.navigation.begin('字型管理')
        try:dialog.refresh();dialog.exec()
        finally:dialog.deleteLater();self.navigation.finish()

    def backup_center(self):
        from .backup_center import BackupManagerDialog
        if getattr(self,'backup_dialog',None) is None:self.backup_dialog=BackupManagerDialog(self)
        self.backup_dialog.refresh_history();self.backup_dialog.show();self.backup_dialog.raise_()

    def font_review_history(self):
        if self.busy:return
        from .font_review_dialog import FontReviewDialog
        FontReviewDialog(self).exec()

    def relink_source(self):
        if not self.source or self.busy:
            return
        source = dict(self.source)
        path, _ = QFileDialog.getOpenFileName(self, "選取同內容原稿（不替換內容）", "", "設計來源 (*.ai *.pdf *.svg *.eps *.png *.jpg *.jpeg);;所有檔案 (*)")
        if not path:
            return
        from .source_links import verify_source
        root=self.library.root
        def work():
            from .source_context import snapshot_contexts
            current=snapshot_contexts(root,[source['id']])[0]
            return current,verify_source(path,current['hash'])
        def finished(payload):
            from .source_dialog import SourceRelinkDialog
            from .source_discovery import availability
            current,proof=payload
            prior=getattr(self,'_source_relink_preview',None)
            if prior:prior.close()
            dialog=SourceRelinkDialog(self);self._source_relink_preview=dialog
            dialog.show_report(dict(status='COMPLETE',root='',roots=[],entries=1,bytes_budgeted=proof.stat[2],hashed_files=1,errors=[],manual_candidate=True,
                                    rows=[dict(source=current,availability=availability(current),candidates=[proof],same_name_different=[])]))
            dialog.show()
            self.statusBar().showMessage('同位元候選已核對；請在來源管理預覽關聯、勾選來源與位置後明確確認')
        self.run_job("核對原稿內容與完整關聯，尚不改位置",work,finished)

    def refresh_sources(self, select=None, preserve_editor=False):
        retained=self.source['id'] if preserve_editor and self.source else None
        from .startup_catalog import editor_page
        selected=retained or select or (self.library.active_source_id() if self.source is None else None)
        page=editor_page(self.library,'sources',self.source_offset,selected);self.source_offset=page['offset'];self.sources=page['items']
        self.source_count.setText(f"本頁{len(self.sources)}／全部{page['total']}；起點{self.source_offset+1 if page['total'] else 0}")
        self.source_previous.setEnabled(self.source_offset>0);self.source_next.setEnabled(self.source_offset+48<page['total'])
        self.source_count.setToolTip('\n'.join(page['issues']))
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        for s in self.sources:
            self.source_combo.addItem(f"{Path(s['current_path']).name} · 第 {s['page']} 頁 · {s['engine']}", s["id"])
            self.source_combo.setItemData(self.source_combo.count() - 1,
                f"原始登錄：{s['original_path']}\n目前位置：{s['current_path']}\n位置版次：r{s['link_revision']}", Qt.ToolTipRole)
        select = retained or select or self.library.active_source_id()
        if select:
            self.source_combo.setCurrentIndex(next((i for i, s in enumerate(self.sources) if s["id"] == select), 0))
        self.source_combo.blockSignals(False)
        if self.sources and not retained:
            self.choose_source(self.source_combo.currentIndex())

    def source_page(self,delta):
        from .training_navigation import require_clean_navigation
        try:require_clean_navigation(self);self.source_offset=max(0,self.source_offset+delta);self.refresh_sources()
        except Exception as error:self.error(str(error))

    def choose_source(self, index):
        if not 0 <= index < len(self.sources):
            return
        try:
            if self.source:
                self.save_labels(silent=True)
            source = self.sources[index]
            width, height = min(2000, source["width_mm"]), min(2000, source["height_mm"])
            from dataclasses import asdict
            work = self.library.initialize_artwork(source["id"], {"crop": asdict(Rect(0, 0, width, height)),
                "work_width": width, "work_height": height, "slots": [], "visual_confirmed": False})
            self.source = source
            self.load_work(work)
            self.library.select_source(source["id"])
        except Exception as e:
            self.error(str(e))
            self.source_combo.blockSignals(True)
            if self.source:
                self.source_combo.setCurrentIndex(self.source_combo.findData(self.source["id"]))
            self.source_combo.blockSignals(False)

    def refresh_works(self):
        self.works = self.library.artworks(self.source["id"]) if self.source else []
        self.work_combo.blockSignals(True)
        self.work_combo.clear()
        for work in self.works:
            self.work_combo.addItem(f"{work['name']} · r{work['revision']}", work["id"])
        if self.work:
            self.work_combo.setCurrentIndex(self.work_combo.findData(self.work["id"]))
        self.work_combo.blockSignals(False)

    def load_work(self, work):
        self.work = work
        saved = work["payload"]
        self.crop = Rect(**saved["crop"])
        self.slots = [Slot(**{**s, "rect": Rect(**s["rect"])}) for s in saved["slots"]]
        self.font_manager.ensure_slots(self.slots)
        self.work_width, self.work_height = saved["work_width"], saved["work_height"]
        self.visual.blockSignals(True)
        self.visual.setChecked(bool(saved.get("visual_confirmed")))
        self.visual.blockSignals(False)
        self.current_slot = None
        self.property_button.setEnabled(False)
        self.undo_stack, self.redo_stack = [], []
        self.refresh_works()
        self.refresh_training()
        self.train_canvas.fit()

    def choose_work(self, index):
        if not self.source or not 0 <= index < len(self.works):
            return
        work_id = self.works[index]["id"]
        try:
            self.save_labels(silent=True)
            self.load_work(self.library.select_artwork(self.source["id"], work_id))
        except Exception as e:
            self.refresh_works()
            self.error(str(e))

    def rename_work(self):
        if not self.work:
            return
        name, ok = QInputDialog.getText(self, "作品名稱", "作品名稱（最多 120 字）", text=self.work["name"])
        if ok:
            try:
                self.library.rename_artwork(self.work["id"], name)
                self.work["name"] = name.strip()
                self.refresh_works()
            except Exception as e:
                self.error(str(e))

    def restore_work(self):
        if not self.work:
            return
        from datetime import datetime
        try:
            self.save_labels(silent=True)
            history = self.library.artwork_history(self.work["id"])
            choices = [f"r{item['revision']} · {datetime.fromtimestamp(item['created']).strftime('%Y-%m-%d %H:%M:%S')}" for item in history]
            choice, ok = QInputDialog.getItem(self, "恢復標記歷史", "選擇版次；會保存為新版本，不刪除後續歷史", choices, 0, False)
            if not ok:
                return
            revision = history[choices.index(choice)]["revision"]
            if QMessageBox.question(self, "恢復作品標記", f"恢復至 r{revision} 的框位、毫米及視覺確認狀態？\n已發布模板不會跟著改動。") != QMessageBox.Yes:
                return
            self.load_work(self.library.restore_artwork(self.work["id"], revision, self.work["revision"]))
            self.statusBar().showMessage("歷史標記已恢復並保存，後續版本仍保留")
        except Exception as e:
            self.error(str(e))

    def refresh_training(self):
        if not self.source:
            return
        # 標記座標屬作品；顯示時轉回全稿毫米位置。
        visible = copy.deepcopy(self.slots)
        for s in visible:
            s.rect.x = self.crop.x + s.rect.x * self.crop.w / self.work_width
            s.rect.y = self.crop.y + s.rect.y * self.crop.h / self.work_height
            s.rect.w *= self.crop.w / self.work_width
            s.rect.h *= self.crop.h / self.work_height
        self.train_canvas.set_content(self.source["width_mm"], self.source["height_mm"], QImage(self.source["image"]), visible, self.crop)
        self.train_canvas.set_mode(self.train_canvas.mode)
        self.slot_list.blockSignals(True)
        self.slot_list.clear()
        for s in self.slots:
            self.slot_list.addItem(f"{KINDS[s.kind]} · {s.owner} · 第 {s.index+1} 筆")
        self.slot_list.blockSignals(False)
        self.source_info.setText(f"作品 {self.work_width:.3f} × {self.work_height:.3f} mm · {len(self.slots)} 個欄位 · {self.source['engine']}\n橘框是作品邊界，藍框是資料／Logo 標記；這些操作不改動原稿。")

    def add_rectangle(self, rect):
        if self.tabs.currentIndex() == 0:
            if not self.source:
                return
            if not rect.inside(self.source["width_mm"], self.source["height_mm"]):
                self.error("框位必須位於來源矩形內")
                return
            if self.train_canvas.mode == "crop":
                w, ok = QInputDialog.getDouble(self, "標定作品", "作品實體寬度（mm）", rect.w, 0.1, 2000, 3)
                if not ok:
                    return
                h, ok = QInputDialog.getDouble(self, "標定作品", "作品實體高度（mm）", rect.h, 0.1, 2000, 3)
                if not ok:
                    return
                try:
                    self.save_labels(silent=True)
                    from dataclasses import asdict
                    work = self.library.create_artwork(self.source["id"], f"作品 {len(self.works)+1}",
                        {"crop": asdict(rect), "work_width": w, "work_height": h, "slots": [], "visual_confirmed": False})
                    self.load_work(work)
                except Exception as e:
                    self.error(str(e))
                    return
            else:
                if not (rect.x >= self.crop.x and rect.y >= self.crop.y and rect.x + rect.w <= self.crop.x + self.crop.w and rect.y + rect.h <= self.crop.y + self.crop.h):
                    self.error("資料框必須在目前橘色作品框內")
                    return
                if self.checkpoint() is False:return
                mapped = Rect((rect.x - self.crop.x) * self.work_width / self.crop.w, (rect.y - self.crop.y) * self.work_height / self.crop.h,
                              rect.w * self.work_width / self.crop.w, rect.h * self.work_height / self.crop.h)
                self.slots.append(self.make_slot(mapped))
                self.save_labels(silent=True)
            self.refresh_training()
        elif self.tabs.currentIndex() == 1 and self.editable():
            if self.checkpoint() is False:return
            self.template.slots.append(self.make_slot(rect))
            self.refresh_editor()

    def make_slot(self, rect,preserve=False):
        family=self.font.currentFont().family();asset=self.font_manager.asset_for_family(family)
        style=""
        displayed=getattr(self,'_selected_font_display',None)
        if self.current_slot and displayed and displayed['slot_id']==self.current_slot.id and family==displayed['display']:
            # Qt combo可能將bare family顯示成foundry別名；保留實際已核准pin，不以別名重建身份。
            family=self.current_slot.font;asset=copy.deepcopy(self.current_slot.font_asset);style=self.current_slot.font_style
        elif asset:
            from .font_catalog import raw_asset
            try:style=raw_asset(asset).styleName()
            except ValueError:pass  # 保留pin與既有Gate，不能暗借系統字型。
        return Slot(self.kind.currentData(), self.owner.currentData(), rect, self.index.value()-1,
                    family, self.pt.value(), self.scale.value()/100,
                    self.align.currentData(), self.required.isChecked(), color=self.text_color.text().strip(),
                    font_asset=asset,font_style=style,locked=self.current_slot.locked if preserve and self.current_slot else False,
                    **({key:copy.deepcopy(getattr(self.current_slot,key)) for key in ('tracking_mm','tracking_min_mm','tracking_max_mm','distribution_approval')} if preserve and self.current_slot else {}))

    def current_slots(self):
        return self.slots if self.tabs.currentIndex() == 0 else self.template.slots if self.template else []

    def editable(self):
        if self.tabs.currentIndex() == 0:
            return self.source is not None
        if self.tabs.currentIndex() == 1 and self.template and self.template.state == "draft":
            return True
        self.inform("已發布模板唯讀，請先建立新版本草稿")
        return False

    def select_slot(self, slot):
        self.current_slot = next((s for s in self.current_slots() if slot and s.id == slot.id), None)
        s = self.current_slot
        self.property_button.setEnabled(s is not None and not s.locked and self.tabs.currentIndex() != 2 and (self.tabs.currentIndex()==0 or (self.template and self.template.state=='draft')))
        if not s:
            return
        self.kind.setCurrentIndex(self.kind.findData(s.kind))
        self.owner.setCurrentIndex(self.owner.findData(s.owner))
        self.index.setValue(s.index+1)
        for spin, value in zip(self.coords, [s.rect.x, s.rect.y, s.rect.w, s.rect.h]):
            spin.setValue(value)
        selected_font=QFontDatabase.font(s.font,s.font_style,10) if s.font_style else QFont(s.font)
        self.font.setCurrentFont(selected_font)
        self._selected_font_display={'slot_id':s.id,'display':self.font.currentFont().family()}
        self.pt.setValue(s.size_pt)
        self.text_color.setText(s.color)
        self.scale.setValue(s.min_scale*100)
        self.align.setCurrentIndex(self.align.findData(s.align))
        self.required.setChecked(s.required)
        self.selected_info.setText(f"{KINDS[s.kind]} · {s.owner} · {'已鎖定；須明確解鎖' if s.locked else '未鎖定'}\n款式：{s.font_style or '預設／待核驗'}；改幾何／色彩不重設已選款式。\n已選取框位以作品毫米表示。\n原始字型／可編輯性未知時，不將本模板設計值冒稱原稿屬性。")
        if self.tabs.currentIndex()==0 and self.work:
            from .training_store import TrainingStore
            from .semantic_fields import TYPE_LABELS
            facts=TrainingStore.bind(self.library).facts(self.work['id']);observation=next((o for o in facts['observations'] if o.get('slot_id')==s.id),None)
            if observation:
                semantic=observation.get('semantic') or {};self.selected_info.setText(self.selected_info.text()+'\n來源文字：'+observation['text'][:512]+'\n語意候選：'+TYPE_LABELS.get(semantic.get('semantic_type'),'待確認')+'／'+str(semantic.get('confidence','UNKNOWN'))+'\n依據：'+'；'.join(semantic.get('signals',[]))+'\n作品事實保存狀態：'+facts['state']+'；確認範圍以逐項核對紀錄為準。')
        elif self.tabs.currentIndex()==1 and self.template:
            errors=template_errors(self.template);self.selected_info.setText(self.selected_info.text()+'\n設計安全邊距：'+str(self.template.safe_margin_mm)+'mm\n'+('驗證待修復：'+'；'.join(errors[:8]) if errors else '幾何／語意檢查通過；仍依實際資料驗證字形及輸出。'))

    def list_selection(self, row):
        if 0 <= row < len(self.slots):
            self.train_canvas.select_id(self.slots[row].id)

    def checkpoint(self):
        if not self.editor_fresh():return False
        self.undo_stack.append(copy.deepcopy(self.current_slots()))
        self.undo_stack = self.undo_stack[-50:]
        self.redo_stack.clear()
        return True

    def editor_fresh(self):
        from .font_review import fingerprint
        try:
            if self.tabs.currentIndex()==0 and self.work:
                current=self.library.object_snapshot('ARTWORK',self.work['id'])
                if current['revision']!=self.work['revision'] or fingerprint(current['payload'])!=fingerprint(self.work['payload']):raise ValueError('來源標記已變更／過期，保留手工內容；請重新核對')
            elif self.tabs.currentIndex()==1 and self.template:
                current=self.library.object_snapshot('TEMPLATE',self.template.id)
                if current['revision']!=self.template_revision or fingerprint(current['payload'])!=self.template_base_hash:raise ValueError('模板已變更／ABA／過期，保留手工內容；請重新核對')
            return True
        except ValueError as error:self.error(str(error));return False

    def save_current_template(self):
        if not self.template:return
        if not self.editor_fresh():raise ValueError('模板上下文已變更，未覆寫；手工內容保留')
        self.library.save_template(self.template,expected_revision=self.template_revision)
        current=self.library.object_snapshot('TEMPLATE',self.template.id)
        from .font_review import fingerprint
        self.template_revision=current['revision'];self.template_base_hash=fingerprint(current['payload'])
        self.template_base_payload=copy.deepcopy(current['payload'])

    def undo(self):
        if not self.editable() or not self.undo_stack or not self.editor_fresh():
            return
        self.redo_stack.append(copy.deepcopy(self.current_slots()))
        self.replace_slots(self.undo_stack.pop())

    def redo(self):
        if not self.editable() or not self.redo_stack or not self.editor_fresh():
            return
        self.undo_stack.append(copy.deepcopy(self.current_slots()))
        self.replace_slots(self.redo_stack.pop())

    def replace_slots(self, slots):
        from dataclasses import asdict
        from .object_tools import protect_locked
        try:protect_locked({'slots':[asdict(s) for s in self.current_slots()]},{'slots':[asdict(s) for s in slots]})
        except ValueError as error:self.error(str(error));return
        if self.tabs.currentIndex() == 0:
            self.slots = slots
            self.refresh_training()
            self.save_labels(silent=True)
        else:
            self.template.slots = slots
            self.refresh_editor()

    def box_moved(self, action, displayed_slot):
        if displayed_slot.locked:return
        if action == "before_move":
            if self.tabs.currentIndex() == 1 and not self.editable():
                return
            self.checkpoint()
            return
        actual = next((s for s in self.current_slots() if s.id == displayed_slot.id), None)
        if actual:
            if self.tabs.currentIndex() == 0:
                actual.rect.x = (displayed_slot.rect.x - self.crop.x) * self.work_width / self.crop.w
                actual.rect.y = (displayed_slot.rect.y - self.crop.y) * self.work_height / self.crop.h
                self.save_labels(silent=True)
            self.select_slot(actual)

    def apply_properties(self):
        if not self.current_slot or not self.editable():
            return
        if self.current_slot.locked:self.error('物件已鎖定；請在安全多選工具明確解鎖');return
        import re
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", self.text_color.text().strip()):
            self.error("文字色彩請輸入 #RRGGBB，例如 #173d75")
            return
        if self.checkpoint() is False:return
        s = self.make_slot(Rect(*(spin.value() for spin in self.coords)),preserve=True)
        if not s.rect.valid():self.undo_stack.pop();self.error('框位寬高需大於零且有限');return
        if self.current_slot.kind=='logo' and (s.kind!='logo' or abs(s.rect.w/s.rect.h-self.current_slot.rect.w/self.current_slot.rect.h)>1e-6):
            self.undo_stack.pop();self.error('完整Logo不能改成一般文字或不等比變形');return
        s.id = self.current_slot.id
        self.current_slot.__dict__.update(s.__dict__)
        if self.tabs.currentIndex() == 0:
            self.refresh_training()
            self.save_labels(silent=True)
        else:
            self.refresh_editor()

    def delete_slot(self):
        if not self.current_slot or not self.editable():
            return
        if self.current_slot.locked:self.error('物件已鎖定；不能刪除');return
        if self.checkpoint() is False:return
        self.current_slots().remove(self.current_slot)
        self.current_slot = None
        if self.tabs.currentIndex() == 0:
            self.refresh_training()
            self.save_labels(silent=True)
        else:
            self.refresh_editor()

    def source_repair(self):
        try:
            if not self.work:raise ValueError('先選取實際來源作品')
            from .training_navigation import require_clean_navigation
            from .training_quality_dialog import open_repair_center
            require_clean_navigation(self)
            open_repair_center(self,dict(origin='SOURCE_FACTS',origin_id=self.work['id'],work_id=self.work['id'],description='從原畫布核對此作品的來源、人工真值與局部問題'))
        except (ValueError,KeyError) as error:self.statusBar().showMessage(str(error))

    def training_center(self):
        from .training_quality_dialog import TrainingQualityDialog
        dialog = TrainingQualityDialog(self)
        try: dialog.exec()
        finally: dialog.deleteLater()

    def object_tools(self):
        from .object_dialog import ObjectToolsDialog
        from .font_review import fingerprint
        try:
            tab=self.tabs.currentIndex()
            if tab==0 and self.work:kind,entity_id='ARTWORK',self.work['id']
            elif tab==1 and self.template:kind,entity_id='TEMPLATE',self.template.id
            else:self.inform('請先選取來源作品或保存的模板草稿');return
            snapshot=self.library.object_snapshot(kind,entity_id)
            if kind=='TEMPLATE':
                if fingerprint(Template.from_dict(snapshot['payload']).to_dict())!=fingerprint(self.template.to_dict()):raise ValueError('主工作台有未保存編輯；請先保存或明確放棄')
            else:
                from dataclasses import asdict
                stored=[asdict(Slot(**{**s,'rect':Rect(**s['rect'])})) for s in snapshot['payload']['slots']]
                if [Slot(**{**s,'rect':Rect(**s['rect'])}) for s in stored]!=self.slots:raise ValueError('來源標記有未保存內容，請先保存')
            if self.current_slot:
                draft=self.make_slot(Rect(*(s.value() for s in self.coords)),preserve=True);draft.id=self.current_slot.id
                if draft!=self.current_slot:raise ValueError('屬性面板有未套用內容；請先套用或明確重選放棄')
            dialog=ObjectToolsDialog(self,kind,entity_id)
            try:dialog.exec()
            finally:dialog.deleteLater()
        except Exception as error:self.error(str(error))

    def labels_changed(self):
        if self.source:
            try:
                self.save_labels(silent=True)
            except Exception as e:
                self.error(str(e))

    def save_labels(self, silent=False):
        if not self.source or not self.work:
            return
        from dataclasses import asdict
        try:
            self.work = self.library.save_artwork(self.work["id"], {"crop": asdict(self.crop), "work_width": self.work_width,
                "work_height": self.work_height, "slots": [asdict(s) for s in self.slots], "visual_confirmed": self.visual.isChecked()}, self.work["revision"])
        except Exception as e:
            if silent:
                raise
            self.error(str(e))
            return
        self.refresh_works()
        if not silent:
            self.statusBar().showMessage("標記與作品尺寸已保存，重開程式可恢復；原檔未修改")

    def compare_reference(self):
        if not self.source:
            return
        path, _ = QFileDialog.getOpenFileName(self, "選擇可信原稿參考圖片", "", "參考圖 (*.png *.jpg *.jpeg)")
        if not path:
            return
        from .validation import compare_images
        source_image = self.source["image"]
        def finished(result):
            self.inform(f"參考圖與匯入圖：{result['status']}\n平均像素差：{result.get('mean_difference', '未知')}\n比對結果只供診斷；請放大人工核對後勾選視覺確認。不同尺寸參考圖不自動縮放冒稱一致。")
        self.run_job("原稿視覺差異量測", lambda: compare_images(QImage(source_image), QImage(path)), finished)

    def learn_template(self):
        if not self.source:
            return
        if not self.visual.isChecked():
            self.error("請先與可信原稿對照，確認此作品視覺一致")
            return
        name, ok = QInputDialog.getText(self, "學習模板", "此作品模板名稱")
        if not ok or not name.strip():
            return
        try:
            bindings = self.ask_bindings(self.slots)
            if bindings is None:
                return
            self.save_labels(silent=True)
            t = learn_from_labels(name, self.work_width, self.work_height, self.slots, self.source["id"], self.crop, bindings,
                                  source_work_id=self.work["id"], source_work_revision=self.work["revision"])
            self.library.save_template(t)
            self.save_labels(silent=True)
            self.refresh_templates(t.id)
            self.tabs.setCurrentIndex(1)
            self.statusBar().showMessage("已從確認標記建立幾何規則模板草稿；發布仍需人工確認")
        except Exception as e:
            self.error(str(e))

    def new_template(self):
        name, ok = QInputDialog.getText(self, "空白模板", "模板名稱")
        if not ok or not name.strip():
            return
        w, ok = QInputDialog.getDouble(self, "矩形寬", "寬度 mm", 90, 1, 2000, 3)
        if not ok:
            return
        h, ok = QInputDialog.getDouble(self, "矩形高", "高度 mm", 54, 1, 2000, 3)
        if not ok:
            return
        t = Template(name.strip(), w, h, [])
        self.library.save_template(t)
        self.refresh_templates(t.id)

    def add_demo(self):
        from .demo import demo_template
        t = demo_template()
        self.library.save_template(t)
        self.refresh_templates(t.id)
        self.statusBar().showMessage("合成示範模板已加入草稿；請驗證並發布後排版")

    def refresh_templates(self, select=None, preserve_editor=False):
        from .startup_catalog import editor_page
        page=editor_page(self.library,'templates',self.template_offset,self.template.id if preserve_editor and self.template else select);self.template_offset=page['offset'];self.templates=page['items']
        self.template_count.setText(f"本頁{len(self.templates)}／全部{page['total']}");self.template_count.setToolTip('\n'.join(page['issues']))
        self.template_previous.setEnabled(self.template_offset>0);self.template_next.setEnabled(self.template_offset+48<page['total'])
        if hasattr(self,"template_catalog"):self.template_catalog.reload()
        self.template_list.blockSignals(True)
        self.template_list.clear()
        for t in self.templates:
            self.template_list.addItem(f"{t.name} · v{t.version}\n{t.width_mm:g}×{t.height_mm:g} mm · {t.capacity} 人 · {'已發布' if t.state == 'published' else '草稿'}")
        if preserve_editor:
            current_id=self.template.id if self.template else None
            index=next((i for i,t in enumerate(self.templates) if t.id==current_id),-1)
            self.template_list.setCurrentRow(index);self.template_list.blockSignals(False);return
        self.template_list.blockSignals(False)
        if self.templates:
            index = next((i for i, t in enumerate(self.templates) if t.id == select), 0)
            self.template_list.setCurrentRow(index)

    def template_page(self,delta):
        from .training_navigation import require_clean_navigation
        try:require_clean_navigation(self);self.template_offset=max(0,self.template_offset+delta);self.refresh_templates()
        except Exception as error:self.error(str(error))

    def choose_template(self, row):
        if not 0 <= row < len(self.templates):
            return
        if self.template and self.template.state == "draft":
            try:self.save_current_template()
            except Exception as error:self.error(str(error));return
        from .font_review import fingerprint
        snapshot=self.library.object_snapshot('TEMPLATE',self.templates[row].id)
        self.template = Template.from_dict(snapshot['payload'])
        self.template_revision=snapshot['revision'];self.template_base_hash=fingerprint(snapshot['payload'])
        self.template_base_payload=copy.deepcopy(snapshot['payload'])
        self.undo_stack, self.redo_stack = [], []
        self.current_slot = None
        self.refresh_editor()
        self.edit_canvas.fit()

    def refresh_editor(self):
        if not self.template:
            return
        t = self.template
        self.font_manager.ensure_slots(t.slots)
        selected=set(getattr(self.edit_canvas,'selection_intent',set()))
        self.edit_canvas.readonly = t.state == "published"
        self.background_button.setEnabled(t.state == "draft" and not self.busy)
        self.clear_background_button.setEnabled(t.state == "draft" and t.background is not None and not self.busy)
        errors = template_errors(t)
        background_image = None
        if t.background:
            try:
                background_image = render_background(t)
            except ValueError as e:
                errors.append(str(e))
        self.edit_canvas.set_content(t.width_mm, t.height_mm, image=background_image, slots=copy.deepcopy(t.slots),safe_margin_mm=t.safe_margin_mm)
        self.edit_canvas.set_mode("edit" if t.state == "draft" else "pan")
        self.rebuild_editor_tree();self.editor_selection(sorted(selected))
        self.template_info.setText(f"{t.name} v{t.version} · {'唯讀已發布' if t.state == 'published' else '可編輯草稿'}\n" + ("；".join(errors[:5]) if errors else "幾何與語意檢查未發現問題；正式輸出仍需實際資料量測") + "\n" + "；".join(t.reasons))

    def text_policy_editor(self):
        if self.tabs.currentIndex()!=1 or not self.template or not self.current_slot or self.current_slot.kind=='logo' or not self.editable():self.inform('請選取模板草稿的一般文字框');return
        from .text_policy_dialog import TextPolicyDialog
        dialog=TextPolicyDialog(self);dialog.exec();dialog.deleteLater()

    def rebuild_editor_tree(self):
        from .object_index import semantic_index
        self.editor_tree.blockSignals(True);self.editor_tree.clear();self.editor_tree_nodes=[]
        def add(parent,node):
            item=QTreeWidgetItem([node['label']]);item.setData(0,Qt.UserRole,node['ids']);self.editor_tree_nodes.append(item)
            parent.addChild(item) if parent else self.editor_tree.addTopLevelItem(item)
            for child in node['children']:add(item,child)
        for node in semantic_index(self.template.to_dict()):add(None,node)
        self.editor_tree.expandAll();self.editor_tree.blockSignals(False)

    def editor_tree_selection(self):
        ids=sorted({identity for item in self.editor_tree.selectedItems() for identity in item.data(0,Qt.UserRole) or []});self.editor_selection(ids)

    def editor_selection(self,ids):
        if not self.template:return
        valid={slot.id for slot in self.template.slots};ids=[identity for identity in ids if identity in valid]
        self.edit_canvas.select_ids(ids);self.editor_tree.blockSignals(True)
        for item in getattr(self,'editor_tree_nodes',[]):
            members=item.data(0,Qt.UserRole) or [];item.setSelected(bool(members) and set(members)<=set(ids))
        self.editor_tree.blockSignals(False)
        if self.tabs.currentIndex()==1:
            self.select_slot(next((slot for slot in self.template.slots if len(ids)==1 and slot.id==ids[0]),None))
            if len(ids)>1:self.selected_info.setText(f'選取{len(ids)}物件；共同屬性／群組操作請用安全多選工具。未擴大範圍。')

    def editor_canvas_preview(self,request):
        try:
            from .object_tools import propose
            plan=propose(self.template.to_dict(),'TEMPLATE',request);self.edit_canvas.show_preview(plan);self.template_info.setText('幾何候選，未套用：'+'；'.join(plan['warnings']))
        except (ValueError,TypeError,KeyError) as error:self.template_info.setText('候選未通過：'+str(error))

    def editor_canvas_apply(self,request):
        try:
            if self.tabs.currentIndex()!=1 or not self.editable():return
            from .object_tools import propose
            plan=propose(self.template.to_dict(),'TEMPLATE',request)
            if self.checkpoint() is False:return
            self.template=Template.from_dict(plan['after']);self.refresh_editor();self.editor_selection(request['ids'])
            self.template_info.setText('已套用目前未發布草稿；'+'；'.join(plan['warnings']) if plan['warnings'] else '已套用目前未發布草稿；幾何與語意檢查未發現問題，輸出仍需實際資料驗證。')
        except (ValueError,TypeError,KeyError) as error:self.template_info.setText('未套用：'+str(error));self.refresh_editor()

    def import_background(self):
        if not self.template or not self.editable() or self.busy:
            return
        path, _ = QFileDialog.getOpenFileName(self, "選擇已清除可變資料的同尺寸背景", "", "背景 (*.svg *.pdf *.ai *.png *.jpg *.jpeg)")
        if not path:
            return
        template_id, version = self.template.id, self.template.version
        width, height = self.template.width_mm, self.template.height_mm
        def finished(result):
            # 背景轉換期間仍可切換模式；完成時不把資產套進別的模板。
            if not self.template or self.template.id != template_id or self.template.version != version or self.template.state != "draft":
                self.inform("模板上下文已切換，本次背景尚未套用；請回到原草稿重新匯入")
                return
            asset = make_background(result, width, height)
            dialog = QDialog(self)
            dialog.setWindowTitle("核對固定背景")
            layout = QVBoxLayout(dialog)
            note = QLabel(f"請核對 {width:g}×{height:g} mm 背景。\n背景應只包含固定裝飾；姓名、電話等可變資料與待替換 Logo 必須先在設計工具清除。\n左側是匯入參考，右側是軟體實際呈現；請核對圖案、色彩與原稿一致。")
            note.setWordWrap(True)
            layout.addWidget(note)
            images = QHBoxLayout()
            for caption in ("匯入參考", "實際背景呈現"):
                column = QVBoxLayout()
                column.addWidget(QLabel(caption))
                image = QLabel()
                column.addWidget(image)
                images.addLayout(column)
                if caption == "匯入參考":
                    image.setPixmap(QPixmap(asset["image"]).scaled(420, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                else:
                    actual_image = image
            layout.addLayout(images)
            mode = QComboBox()
            if asset["svg"]:
                mode.addItem("保留向量（需核對實際呈現）", "vector")
            mode.addItem("使用匯入圖像（以圖片保留視覺）", "raster")
            layout.addWidget(mode)
            buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
            buttons.button(QDialogButtonBox.Ok).setText("已核對，核准乾淨背景")
            buttons.button(QDialogButtonBox.Cancel).setDefault(True)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            def refresh_actual():
                asset["render_mode"] = mode.currentData()
                review = copy.deepcopy(self.template)
                review.background = {**asset, "approved": True}
                try:
                    actual = render_background(review)
                    actual_image.setPixmap(QPixmap.fromImage(actual).scaled(420, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    buttons.button(QDialogButtonBox.Ok).setEnabled(True)
                except ValueError as e:
                    actual_image.clear()
                    actual_image.setText("無法呈現：" + str(e))
                    buttons.button(QDialogButtonBox.Ok).setEnabled(False)
            mode.currentIndexChanged.connect(refresh_actual)
            refresh_actual()
            if dialog.exec() != QDialog.Accepted:
                return
            asset["approved"] = True
            self.template.background = asset
            self.save_current_template()
            self.refresh_templates(self.template.id)
            self.invalidate()
            self.statusBar().showMessage("已保存核准固定背景；預覽與數位輸出使用同一背景")
        self.run_job("轉換固定背景", lambda: import_file(path, self.library.assets), finished)

    def clear_background(self):
        if not self.template or not self.editable() or self.busy:
            return
        if self.template.background is None:
            return
        if QMessageBox.question(self, "移除固定背景", "將此草稿改為空白背景？原始背景檔與已發布歷史版本會保留。") != QMessageBox.Yes:
            return
        self.template.background = None
        self.save_current_template()
        self.refresh_templates(self.template.id)
        self.invalidate()

    def new_version(self):
        if not self.template:
            return
        if not self.editor_fresh():return
        from .template_versions import TemplateVersions
        try:
            current=self.library.object_snapshot('TEMPLATE',self.template.id)
            if Template.from_dict(current['payload'])!=self.template:raise ValueError('請先保存目前草稿，保留未保存的版本內容')
            service=TemplateVersions(self.library);t=service.clone(service.plan(self.template.id),'LOCAL_OPERATOR','明確建立同一模板新版本草稿',True);self.refresh_templates(t.id)
        except Exception as error:self.error(str(error))

    def template_versions(self):
        if not self.template or self.busy:return
        from .template_versions_dialog import TemplateVersionsDialog
        dialog=TemplateVersionsDialog(self);dialog.exec();dialog.deleteLater()

    def save_draft(self):
        if not self.template or not self.editable():
            return
        try:
            self.save_current_template()
            self.refresh_templates(self.template.id)
            self.invalidate()
            self.statusBar().showMessage("模板草稿已持久保存")
        except Exception as e:
            self.error(str(e))

    def publish_template(self):
        if not self.template or self.template.state != "draft":
            return
        if not self.editor_fresh():return
        bindings = self.ask_bindings(self.template.slots)
        if bindings is None:
            return
        self.template.company_bindings = bindings
        errors = template_errors(self.template)
        if errors:
            self.error("\n".join(errors))
            return
        if QMessageBox.question(self, "發布模板", "確認發布目前幾何與語意規則？\n發布後本版本唯讀；數位輸出仍依實際人物資料、字型及同尺寸 Logo 再驗證。") != QMessageBox.Yes:
            return
        self.library.publish(self.template)
        self.refresh_templates(self.template.id)
        self.invalidate()

    def ask_bindings(self, slots):
        companies = sorted({s.owner for s in slots if s.owner.startswith("c")})
        people = sorted({s.owner for s in slots if s.kind == "name"})
        bindings = {}
        for person in people if companies else []:
            text, ok = QInputDialog.getText(self, "確認人物公司歸屬", f"{person} 的公司埠（逗號分隔，可多家公司；空白表示無公司）："+", ".join(companies))
            if not ok:return None
            chosen=[v.strip() for v in text.replace('，',',').split(',') if v.strip()]
            if len(set(chosen))!=len(chosen) or any(c not in companies for c in chosen):
                self.error("請輸入清單中的公司埠，不猜測歸屬");return None
            bindings[person]=chosen[0] if len(chosen)==1 else chosen
        return bindings

    def capture_logo(self):
        if not self.source or not self.current_slot or self.current_slot.kind != "logo":
            self.error("請在原稿選取一個完整 Logo 標記框")
            return
        if not self.visual.isChecked():
            self.error("請先確認作品與可信原稿視覺一致")
            return
        try:
            from .training_navigation import require_clean_navigation
            from .logo_store import LogoStore
            require_clean_navigation(self)
            s = self.current_slot.rect
            crop = {"x": self.crop.x + s.x * self.crop.w / self.work_width, "y": self.crop.y + s.y * self.crop.h / self.work_height,
                    "w": s.w * self.crop.w / self.work_width, "h": s.h * self.crop.h / self.work_height}
            candidate=LogoStore(self.library).propose_source(self.source['id'],self.work['id'],crop,
                object_ids=[self.current_slot.id],evidence={'method':'USER_MARKED_ENTIRE_LOGO_FRAME'})
            self.open_logo_proposal(candidate['id'])
        except Exception as error:
            self.error(str(error))

    def open_logo_proposal(self,identity):
        from .logo_library_dialog import LogoLibraryDialog
        dialog=LogoLibraryDialog(self)
        dialog.focus_proposal(identity)
        try:dialog.exec()
        finally:dialog.deleteLater()

    def import_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "完整 Logo 圖文來源", "", "Logo (*.svg *.pdf *.ai *.png *.jpg *.jpeg)")
        if not path:
            return
        w, h = self.out_w.value(), self.out_h.value()
        def finished(result):
            from .logo_store import LogoStore
            candidate=LogoStore(self.library).propose({"image": result["image"], "svg": result["svg"], "source_width_mm": result["width_mm"],
                "source_height_mm": result["height_mm"], "crop": None, "source_hash": result["hash"]},w,h,'MANUAL')
            self.open_logo_proposal(candidate['id'])
        self.run_job("匯入完整 Logo", lambda: import_file(path, self.library.assets), finished)

    def refresh_logos(self):
        self.logo_assets = self.library.logos()
        self.logo_list.clear()
        for asset in self.logo_assets:
            self.logo_list.addItem(f"{asset['company']} · {asset['width_mm']:g}×{asset['height_mm']:g} mm · "+('已核准' if asset.get('approved') else '已撤銷／不可用'))
        for row in range(self.companies.rowCount()):
            old = self.companies.cellWidget(row, 1)
            selected = old.currentData() if old else None
            combo = QComboBox()
            combo.addItem("尚未選取真實 Logo", None)
            for asset in self.logo_assets:
                if asset.get('approved') and abs(asset["width_mm"]-self.out_w.value()) < 1e-5 and abs(asset["height_mm"]-self.out_h.value()) < 1e-5:
                    combo.addItem(asset["company"] + " · 已核准 " + asset["id"][:6], asset["id"])
            index = combo.findData(selected)
            if index >= 0:
                combo.setCurrentIndex(index)
            combo.currentIndexChanged.connect(self.invalidate)
            self.companies.setCellWidget(row, 1, combo)
        self.invalidate()

    def add_row(self, table):
        if self.active_input_graph is not None:
            self.edit_input_graph();return
        if table.rowCount() >= 20:
            self.error("本版最多 20 筆人物或公司")
            return
        table.insertRow(table.rowCount())
        self.invalidate()

    def add_company(self):
        self.add_row(self.companies)
        self.refresh_logos()

    def remove_row(self, table):
        if self.active_input_graph is not None:
            self.edit_input_graph();return
        if table.currentRow() >= 0 and table.rowCount() > 1:
            if QMessageBox.question(self, "移除資料", "移除後序號可能變動，請重新核對人物公司關聯。繼續？") == QMessageBox.Yes:
                table.removeRow(table.currentRow())
                self.invalidate()

    def edit_input_graph(self,*,focus_field_id=None,focus_entity_id=None,return_origin=None):
        if self.busy:
            self.error("背景工作中，待完成後編輯當次輸入");return
        from .input_graph_dialog import InputGraphDialog
        self.navigation.begin('人物與公司資料',origin=return_origin)
        try:
            dialog=InputGraphDialog(self)
            if focus_field_id:QTimer.singleShot(0,dialog,lambda:dialog.focus_field(focus_field_id,focus_entity_id))
            if dialog.exec()==QDialog.Accepted:self.adopt_input_graph(dialog.graph.data,history=dialog.graph)
        except (ValueError,TypeError) as error:self.error(str(error))
        finally:self.navigation.finish()

    def adopt_input_graph(self, data, snapshot=None, history=None):
        from .input_graph import InputGraph
        graph=history.clone() if history is not None else InputGraph(data)
        if graph.data!=data:raise ValueError("歷史與目前卡片版本不符")
        people,companies,logos=graph.compile(self.library.logos())
        self.active_input_graph=graph
        if snapshot is not None:self.reorder_customer_snapshot=copy.deepcopy(snapshot)
        for table in (self.people,self.companies):table.blockSignals(True)
        try:
            self.people.setRowCount(len(people))
            for i,p in enumerate(people):
                for j,k in enumerate(("name","title","phone","email","line","ig","address")):
                    self.people.setItem(i,j,QTableWidgetItem("；".join(p.get(k,[]))))
                self.people.setItem(i,7,QTableWidgetItem(",".join(c[1:] for c in p["companies"])))
            self.companies.setRowCount(len(companies))
            for i,c in enumerate(companies):self.companies.setItem(i,0,QTableWidgetItem(c["name"]))
            self.people.setEditTriggers(QTableWidget.NoEditTriggers);self.companies.setEditTriggers(QTableWidget.NoEditTriggers)
            self.refresh_logos()
            for i,c in enumerate(graph.data["companies"]):
                combo=self.companies.cellWidget(i,1);idx=combo.findData(c["logo_id"])
                combo.setCurrentIndex(max(0,idx));combo.setEnabled(False)
        finally:
            for table in (self.people,self.companies):table.blockSignals(False)
        self.graph_status.setText(f"人物卡片模式：{len(people)}人物／{len(companies)}公司／{len(graph.data['fields'])}穩定欄位；下表唯讀摘要，所有編輯請開人物卡片。資料僅當次，客戶主檔未回寫。")
        self.invalidate()

    def clear_input_graph(self):
        if QMessageBox.question(self,"清除當次輸入","清除目前人物／公司／聯絡資料與重訂來源，保留客戶主檔及模板。確認？")!=QMessageBox.Yes:return
        self.active_input_graph=None;self.reorder_customer_snapshot=None
        self.reorder_template_id=None
        self.people.clearContents();self.people.setRowCount(1);self.companies.clearContents();self.companies.setRowCount(1)
        for table in (self.people,self.companies):table.setEditTriggers(QTableWidget.DoubleClicked|QTableWidget.EditKeyPressed|QTableWidget.AnyKeyPressed)
        self.legacy_input_panel.setChecked(True)
        self.graph_status.setText("簡易表格模式；可隨時轉入人物ROOT卡片。")
        self.refresh_logos();self.invalidate()

    def input_data(self):
        if self.active_input_graph is not None:return self.active_input_graph.compile(self.library.logos())
        def cell(table, row, col):
            item = table.item(row, col)
            return item.text().strip() if item else ""
        people = []
        for row in range(self.people.rowCount()):
            data = {}
            for col, key in enumerate(["name", "title", "phone", "email", "line", "ig", "address"]):
                data[key] = [v.strip() for v in cell(self.people, row, col).replace(";", "；").split("；") if v.strip()]
            company = cell(self.people, row, 7)
            data["company"] = "c"+str(int(company)) if company else ""
            people.append(data)
        companies = [{"name": cell(self.companies, row, 0)} for row in range(self.companies.rowCount())]
        assets = {asset["id"]: asset for asset in self.library.logos()}
        logos = {}
        for row in range(self.companies.rowCount()):
            combo = self.companies.cellWidget(row, 1)
            if combo and combo.currentData() in assets:
                logos[f"c{row+1}"] = assets[combo.currentData()]
        return people, companies, logos

    def invalidate(self, *_):
        self.generation += 1
        if hasattr(self, 'input_timer'): self.input_timer.start(180)
        self.export_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        if self.candidates:
            self.issues.setText("資料／尺寸／模板或 Logo 已變更；目前候選過期，請重新排版。")
        if hasattr(self,'output_properties'):self.output_properties.setPlainText('當次資料／尺寸／模板已變更；候選過期，請重新試排。')
        if hasattr(self,'qualified_candidates'):
            self.qualified_candidates.setEnabled(False);self.review_candidates.setEnabled(False);self.blocked_candidates.setEnabled(False)
        if hasattr(self,'dependency_notice'):self.dependency_notice.setText('資料已變更；人工框位保留，停止連續輸入後顯示受影響原因。尚未重驗，不得正式輸出。')
        self.inputs_invalidated.emit(self.generation)

    def refresh_input_problems(self):
        try:self.library.db.execute("SELECT 1")
        except sqlite3.ProgrammingError:self.input_timer.stop();return
        from .input_diagnostics import diagnose
        try:
            people, companies, _ = self.input_data()
            report = diagnose(people, companies, self.library.templates(True), self.out_w.value(), self.out_h.value())
        except (ValueError, TypeError) as error:
            report = {'issues': [{'table':'people','row':i,'col':7,'owner':f'p{i+1}','reason':'公司序號需為有效整數：'+str(error)} for i in range(self.people.rowCount()) if self.people.item(i,7) and not self.people.item(i,7).text().strip().isdigit() and self.people.item(i,7).text().strip()]}
        self.input_problems.clear()
        from PySide6.QtWidgets import QListWidgetItem
        for issue in report['issues']:
            item = QListWidgetItem(issue['owner']+' · '+issue['reason']); item.setData(Qt.UserRole, issue); self.input_problems.addItem(item)
        for table in (self.people,self.companies):
            blocker = QSignalBlocker(table)
            for row in range(table.rowCount()):
                for col in range(table.columnCount()):
                    item=table.item(row,col)
                    if item:
                        from .input_warning_delegate import WARNING_ROLE
                        warning='\n'.join(i['reason'] for i in report['issues'] if i['table']==('people' if table is self.people else 'companies') and i['row']==row and i['col']==col)
                        item.setToolTip(warning);item.setData(WARNING_ROLE,warning)
                table.setRowHeight(row,48 if any(i['row']==row and i['table']==('people' if table is self.people else 'companies') for i in report['issues']) else 28)
            del blocker
        self.input_state.setText(f"{len(report['issues'])}項輸入提示／待版面驗證；非全域無解，正式輸出依當前候選Gate")
        self.refresh_dependency_notice()
        self.refresh_candidate_views(self.candidate_list.currentRow())

    def locate_input_problem(self, item):
        if self.active_input_graph is not None:
            self.edit_input_graph();return
        self.legacy_input_panel.setChecked(True)
        issue=item.data(Qt.UserRole);table=getattr(self,issue['table']);table.setCurrentCell(issue['row'],issue['col']);table.setFocus()

    def custom_layout(self):
        if self.busy:return
        from .custom_layout_dialog import CustomLayoutDialog
        dialog=CustomLayoutDialog(self);dialog.exec();dialog.deleteLater()

    def generate(self):
        if self.busy:self.statusBar().showMessage('已有背景工作；此次排版未開始');return
        from .layout_session import LayoutSessionDialog
        dialog=getattr(self,'foreground_layout_session',None)
        if dialog is None:
            dialog=LayoutSessionDialog(self);self.foreground_layout_session=dialog
        dialog.show();dialog.raise_();dialog.start(auto_apply=True)
        self.issues.setText('當次排版在單一背景worker執行；先顯示已核實的部分候選，未遍歷者不代表無解。')

    def refresh_candidate_views(self,row=None):
        if not hasattr(self,'qualified_candidates'):return
        from PySide6.QtWidgets import QListWidgetItem
        from .candidate_results import recommendation
        recommendation_state=recommendation(self);assessments=recommendation_state['assessments']
        signature=(self.generation,tuple((c.template.id,c.template.version,risk['digest'],c.generation,repr(c.score)) for c,risk in zip(self.candidates,assessments)))
        views=(self.qualified_candidates,self.review_candidates,self.blocked_candidates)
        for view in views:view.blockSignals(True)
        if signature!=getattr(self,'_candidate_view_signature',None):
            for view in views:view.clear()
            for index,c in enumerate(self.candidates):
                risk=assessments[index]
                view=self.review_candidates if c.generation!=self.generation else self.qualified_candidates if risk['formal_allowed'] else self.blocked_candidates if risk['state']=='HARD_BLOCKED' else self.review_candidates
                item=QListWidgetItem(c.template.name+f' v{c.template.version}／{c.template.width_mm:g}×{c.template.height_mm:g}mm／{c.template.capacity}人\n'+('排序依據：'+str(c.score)+'；'+'；'.join(c.reasons) if risk['formal_allowed'] else risk['label']+'；'+'；'.join(x['reason'] for x in risk['conditions'] if x['status']!='PASS')+'；'+'；'.join(c.issues[:3])));item.setData(Qt.UserRole,index);view.addItem(item)
                if c.generation!=self.generation:item.setText('待重驗：輸入世代已變，人工框位保留\n'+item.text())
            self._candidate_view_signature=signature
        self.result_recommendation.setText(recommendation_state['label']+'\n'+recommendation_state['scope_label']);self.recommended_button.setEnabled(recommendation_state['index'] is not None)
        for view in views:
            view.clearSelection();view.setCurrentRow(-1)
            for index in range(view.count()):
                if view.item(index).data(Qt.UserRole)==row:view.setCurrentRow(index)
            view.setEnabled(bool(self.candidates));view.blockSignals(False)

    def choose_candidate(self, row):
        self.refresh_candidate_views(row)
        if not 0 <= row < len(self.candidates):
            return
        c = self.candidates[row]
        if hasattr(self,'navigation'):self.navigation.update()
        try:
            from .candidate_risk import bind_source
            bind_source(c,self.library,conditions=[x for x in c.risk_context.get('conditions',[]) if x['id'] not in ('SOURCE_AND_QUALITY_TRUST','EXACT_PUBLISHED_SOURCE_VERSION','ORIGINAL_SOURCE_BYTES')],require_registered=True)
            from .candidate_results import current_assessment
            risk=current_assessment(self,row);eligible=risk['formal_allowed'];self.refresh_candidate_views(row)
            image = render_image(c, 150, not eligible)
            from .render import preview_height
            self.output_canvas.set_content(c.template.width_mm, preview_height(c) if not eligible else c.template.height_mm, image)
            self.output_canvas.set_mode("pan")
            self.output_canvas.fit()
            current = c.generation == self.generation
            self.refresh_dependency_notice()
            self.refresh_result_problems(row)
            self.export_button.setEnabled(eligible and current)
            self.preview_button.setEnabled(current)
            self.output_properties.setPlainText(f"目前候選：{c.template.name} v{c.template.version}\nID {c.template.id}\n尺寸 {c.template.width_mm:g}×{c.template.height_mm:g}mm／{c.template.capacity}人\n"+('已驗證合格（有效版本）' if eligible and current else risk['label'] if current else '候選過期：禁止正式輸出')+'\n排序為規則適配，非審美保證\n'+'；'.join(c.reasons)+'\n問題：\n'+'\n'.join(c.issues[:20]))
            self.output_properties.appendPlainText('\n逐項Gate：\n'+'\n'.join(x['status']+' · '+x['reason'] for x in risk['conditions'])+'\n輸入快照 '+str(risk['input_digest'])[:16]+'\n引擎／規則 '+str(risk['engine_digest'])[:16]+'\n資產依賴 '+str(risk['dependency_stamp'])[:16]+'\n使用依據：已核准模板與明確規則；未將排序分數當模型信心')
            self.input_state.setText(('目前所選候選已驗證合格；輸出前仍需重核有效版本。' if eligible else risk['label']+'。可修正輸入、公司與Logo配對、字型／來源或另選模板，再重新檢查；不推論所有設計都無解。') if current else '輸入／候選已變更，待重新驗證。')
            self.issues.setText(risk['label']+'\n'+'；'.join(x['reason'] for x in risk['conditions'] if x['status']!='PASS')+'\n'+("數位排版檢查通過；尚未做實體印刷分析。" if eligible else "正式輸出阻擋：\n" + "\n".join(c.issues[:8])) + "\n" + "；".join(c.reasons))
        except Exception as e:
            self.export_button.setEnabled(False)
            self.preview_button.setEnabled(False)
            self.error(str(e))

    def keep_review_draft(self):
        row=self.candidate_list.currentRow()
        if not 0<=row<len(self.candidates):return
        reason,ok=QInputDialog.getText(self,'當次待確認草稿','輸入此次需人工核對的原因；只保留記憶體，不發布、不寫入客戶或訓練集')
        if not ok:return
        try:
            from .candidate_risk import transient_draft
            self.candidates[row]=transient_draft(self.candidates[row],reason);self.choose_candidate(row)
        except ValueError as error:self.error(str(error))

    def compare_candidate_results(self):
        from .candidate_results import ResultComparisonDialog
        dialog=ResultComparisonDialog(self)
        try:dialog.exec()
        finally:dialog.deleteLater()

    def refresh_result_problems(self,index):
        from PySide6.QtWidgets import QListWidgetItem
        from .candidate_results import problem_rows
        self.result_problem_items.clear()
        for row in problem_rows(self,index):
            owner=('人物' if row['owner'].startswith('p') else '公司')+row['owner'][1:] if row['owner'] else '整張／來源'
            item=QListWidgetItem(owner+'／'+KINDS.get(row['kind'],'相關條件')+'：'+row['reason']);item.setData(Qt.UserRole,row);item.setToolTip(row['code']+'\n'+'、'.join(row['slot_ids']));self.result_problem_items.addItem(item)

    def locate_result_problem(self,item):
        from .candidate_results import locate_problem
        if item is None:return
        try:return locate_problem(self,item.data(Qt.UserRole))
        except (ValueError,OSError,TypeError,KeyError,IndexError) as error:self.statusBar().showMessage('問題待重新核對：'+str(error))

    def fix_result_problem(self):
        from .candidate_results import fix_problem
        item=self.result_problem_items.currentItem()
        if item is None:self.statusBar().showMessage('先選取一項具名問題');return
        try:fix_problem(self,item.data(Qt.UserRole))
        except (ValueError,OSError,TypeError,KeyError,IndexError) as error:self.statusBar().showMessage('未開啟修正：'+str(error))

    def select_recommended_candidate(self):
        from .candidate_results import recommendation
        result=recommendation(self)
        if result['index'] is not None:self.candidate_list.setCurrentRow(result['index'])
        else:self.statusBar().showMessage(result['label'])

    def refresh_dependency_notice(self):
        if not hasattr(self,'dependency_notice') or not self.candidates:return
        index=self.candidate_list.currentRow()
        if not 0<=index<len(self.candidates):return
        from .candidate_changes import candidate_impact
        try:
            impact=candidate_impact(self,index);self.dependency_notice.setText(impact['label']+'：'+impact['reason']+'\n涉及物件：'+('、'.join(impact['affected_slot_ids']) or '無局部框位變動；整張不變條件仍須核對'))
        except (ValueError,OSError,TypeError,KeyError) as error:self.dependency_notice.setText('依賴待核對；保守重驗整張作品：'+str(error))

    def recheck_affected_candidates(self):
        from .candidate_edit import plan_recheck
        from .candidate_edit_dispatch import dispatcher
        from .candidate_changes import candidate_impact
        if len(self.candidates)>200:self.inform('超過當次200候選重驗預算，請縮小目前集合');return
        manager=dispatcher(self);count=0
        for index,candidate in enumerate(self.candidates):
            # Conservative admission: unchanged current candidates reuse measurements;
            # stale generations are explicit user-triggered jobs, never per keystroke.
            if candidate.generation==self.generation and not candidate_impact(self,index)['needs_recheck']:continue
            manager.submit(plan_recheck(self,index));count+=1
        self.statusBar().showMessage('已排程'+str(count)+'個候選完整重驗；共用單worker，人工框位保留')

    def recheck_candidate(self):
        row=self.candidate_list.currentRow()
        if not 0<=row<len(self.candidates):return
        try:
            from .candidate_edit import plan_recheck
            from .candidate_edit_dispatch import dispatcher
            dispatcher(self).submit(plan_recheck(self,row))
        except (ValueError,OSError) as error:self.error(str(error))

    def export_current(self, preview):
        row = self.candidate_list.currentRow()
        if not 0 <= row < len(self.candidates):
            return
        c = self.candidates[row]
        from .candidate_risk import bind_source
        bind_source(c,self.library,require_registered=True)
        from .candidate_results import current_assessment,selection_pin
        current_risk=current_assessment(self,row)
        if not preview and not current_risk['formal_allowed']:self.error(current_risk['label']);self.export_button.setEnabled(False);return
        output_pin=selection_pin(self,row)
        name = f"{c.template.width_mm:g}x{c.template.height_mm:g}_{'PREVIEW' if preview else 'FINAL'}.png"
        path, _ = QFileDialog.getSaveFileName(self, "保存數位檔案（預設不覆寫）", name, "PNG (*.png);;PDF (*.pdf);;JPG (*.jpg)")
        if not path:
            return
        try:
            from .candidate_risk import bind_source
            bind_source(c,self.library,conditions=[x for x in c.risk_context.get('conditions',[]) if x['id'] not in ('SOURCE_AND_QUALITY_TRUST','EXACT_PUBLISHED_SOURCE_VERSION','ORIGINAL_SOURCE_BYTES')],require_registered=True)
            if not preview and (self.candidate_list.currentRow()!=row or selection_pin(self,row)!=output_pin or not current_assessment(self,row)['formal_allowed']):raise ValueError('目前資料／尺寸／來源或人工版本已改，正式輸出前須重新核對')
            export(c, path, self.dpi.value(), preview, self.generation)
            self.statusBar().showMessage("檔案已實際寫入：" + path)
        except Exception as e:
            self.error(str(e))

    def demo_input(self):
        if self.active_input_graph is not None:
            if QMessageBox.question(self,"替換當次輸入","示範資料將替換目前卡片，客戶主檔保留。繼續？")!=QMessageBox.Yes:return
            from .input_graph import InputGraph
            self.adopt_input_graph(InputGraph.from_legacy([{"name":["林小明"],"title":["設計顧問"],"phone":["0900-123-456"],"email":["hello@example.test"]}],[]).data);return
        self.people.setRowCount(1)
        for i, value in enumerate(["林小明", "設計顧問", "0900-123-456", "hello@example.test", "", "", "", ""]):
            self.people.setItem(0, i, QTableWidgetItem(value))
        self.invalidate()

    def import_font(self):
        path, _ = QFileDialog.getOpenFileName(self, "選取已獲授權的本機字型（不安裝 Windows）", "", "字型 (*.ttf *.otf *.ttc)")
        if not path:
            return
        if QMessageBox.question(self, "字型使用", "確認有權將此字型複本保存於本機並使用？\n只載入本程式，重開時自動載入，不修改 Windows 字型系統；嵌入與印刷授權仍需核對。") != QMessageBox.Yes:
            return
        try:
            from .font_evidence import inspect_font
            proof=inspect_font(path); face_index=0
            if len(proof['faces'])>1:
                labels=[f"{f['index']} · {f['family']} / {f['style']} / {f['version']}" for f in proof['faces']]
                selected,ok=QInputDialog.getItem(self,'TTC字面選擇','選取本次匯入字面；其他字面不會被借用',labels,0,False)
                if not ok:return
                face_index=labels.index(selected)
            asset = self.font_manager.import_font(path, approved=True,face_index=face_index)
            self.font.setCurrentFont(QFont(asset["families"][0]))
            self.inform("已保存並載入本程式：" + "、".join(asset["families"]) + "\n重開時會核對內容後自動載入；字型不會隨原始碼包上傳。")
            self.invalidate()
        except Exception as e:
            self.error(str(e))

    def navigate_mode(self,index):
        self.tabs.setCurrentIndex(index)
        if index==2 and self.candidates:
            def reveal():
                canvas=self.output_canvas;scroll=self.output_page_scroll;canvas.setFocus()
                # QGraphicsView's input-method focus rectangle is not the whole
                # canvas. Reveal its actual widget rectangle in page coordinates.
                centre=canvas.mapTo(scroll.widget(),canvas.rect().center())
                xmargin=max(0,min(canvas.width()//2,scroll.viewport().width()//2-12))
                ymargin=max(0,min(canvas.height()//2,scroll.viewport().height()//2-12))
                scroll.ensureVisible(centre.x(),centre.y(),xmargin,ymargin)
            QTimer.singleShot(0,self,reveal)

    def mode_changed(self,index=None):
        index=self.tabs.currentIndex() if index is None else index
        if hasattr(self,'navigation') and not self.navigation.restoring:self.navigation.remember(self._active_mode)
        form=dict(kind=self.kind.currentData(),owner=self.owner.currentData(),index=self.index.value(),coords=[s.value() for s in self.coords],font=self.font.currentFont(),pt=self.pt.value(),color=self.text_color.text(),scale=self.scale.value(),align=self.align.currentData(),required=self.required.isChecked(),font_display=copy.deepcopy(getattr(self,'_selected_font_display',None)))
        self._mode_memory[self._active_mode]=(self.current_slot.id if self.current_slot else None,self.undo_stack,self.redo_stack,form)
        self._active_mode=index
        self.function_stack.setCurrentIndex(index)
        selected,self.undo_stack,self.redo_stack,form=self._mode_memory.get(index,(None,[],[],None))
        self.select_slot(next((s for s in self.current_slots() if s.id==selected),None))
        if form and self.current_slot:
            for combo,key in ((self.kind,'kind'),(self.owner,'owner'),(self.align,'align')):combo.setCurrentIndex(combo.findData(form[key]))
            self.index.setValue(form['index'])
            for spin,value in zip(self.coords,form['coords']):spin.setValue(value)
            self.font.setCurrentFont(form['font']);self.pt.setValue(form['pt']);self.text_color.setText(form['color']);self.scale.setValue(form['scale']);self.required.setChecked(form['required']);self._selected_font_display=form['font_display']

    def repair_font(self):
        if self.busy:
            return
        assets = self.library.fonts()
        if not assets:
            self.inform("目前沒有已核准字型資產，請先匯入合法本機字型")
            return
        choices = [" / ".join(a["families"]) + " · " + a["original_name"] + " · " + a["hash"][:12] for a in assets]
        selected, ok = QInputDialog.getItem(self, "修復字型資產", "選取要恢復的既有字型版本", choices, 0, False)
        if not ok:
            return
        asset = assets[choices.index(selected)]
        path, _ = QFileDialog.getOpenFileName(self, "選取同內容且已獲授權的字型複本", "", "字型 (*.ttf *.otf *.ttc)")
        if not path:
            return
        if QMessageBox.question(self, "字型修復", "確認有權保存與使用此字型？\n僅恢復相同內容的本機複本，保留已發布模板與字型版本；損壞複本會保留於本機隔離區。") != QMessageBox.Yes:
            return
        try:
            self.font_manager.repair_font(asset["hash"], path, approved=True)
            self.invalidate()
            self.inform("字型複本已恢復；請重新排版並核對結果。重開會載入原核准版本。")
        except Exception as error:
            self.error(str(error))

    def help(self):
        self.inform("第一版快速操作：\n1. 模板區加入示範模板，驗證並發布。\n2. 輸出區填入匿名示範，開始排版並輸出。\n3. 訓練區匯入來源，框選作品、標定毫米，新增欄位並設定歸屬。\n4. 核對原稿後確認視覺一致，保存標記、學習模板。\n5. 缺少 Logo 或內容排不下只可 PREVIEW，不會暗縮字級。\n\n本版只提供標記幾何規則學習；完整自動辨識、客戶重訂、深度模型、完整權限與印刷分析尚未完成。")

    def closeEvent(self, event):
        if self.library.closed:
            event.accept();return
        if self.busy:
            self.inform("背景工作尚未安全結束，請等待完成或先在目前工作面板安全取消")
            event.ignore()
            return
        if not self.navigation.confirm_close():
            event.ignore();return
        try:
            if self.template and self.template.state == "draft":
                self.save_current_template()
            if self.source:
                self.save_labels(silent=True)
        except Exception as e:
            self.navigation.save_error='正式資料保存失敗；尚未安全關閉。';self.navigation.update()
            self.error("保存失敗，尚未安全關閉：" + str(e))
            event.ignore()
            return
        self.input_timer.stop()
        self.backup_scheduler.shutdown()
        self.source_watch.shutdown()
        self.font_manager.close()
        self.library.close()
        event.accept()

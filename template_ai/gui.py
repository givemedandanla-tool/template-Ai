"""繁體中文三模式桌面工作台；所有背景工作都不直接改動目前畫布。"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QPointF, QRectF, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QAction, QColor, QFont, QFontDatabase, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QDialog, QDialogButtonBox, QFontComboBox, QFormLayout, QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView,
    QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMessageBox, QPushButton, QSpinBox, QSplitter, QTabWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)

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
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable)
        self.setZValue(2)
        pen = QPen(QColor("#2563eb"), 1)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QColor(37, 99, 235, 24))
        self.caption = KINDS.get(slot.kind, "欄位") + " · " + slot.owner

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
    rectangle = Signal(object)
    selected = Signal(object)
    moved = Signal(str, object)

    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor("#e8edf5"))
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
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

    def set_mode(self, mode):
        if self.readonly and mode in ("edit", "slot"):
            mode = "pan"
        self.mode = mode
        self.setDragMode(QGraphicsView.ScrollHandDrag if mode == "pan" else QGraphicsView.NoDrag)
        self.setCursor(Qt.CrossCursor if mode in ("crop", "slot") else Qt.ArrowCursor)
        for item in self.scene().items():
            if isinstance(item, Box):
                item.setFlag(QGraphicsItem.ItemIsMovable, mode == "edit")
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

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        scale = self.transform().m11() * factor
        if 0.2 <= scale <= 500:
            self.scale(factor, factor)
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
    def __init__(self, data_root):
        super().__init__()
        self.library = Library(data_root)
        self.font_manager = FontManager(self.library)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.source = None
        self.crop = None
        self.work = None
        self.works = []
        self.slots = []
        self.template = None
        self.current_slot = None
        self.candidates = []
        self.generation = 0
        self.undo_stack, self.redo_stack = [], []
        self.busy = False
        self.loading_form = False
        self.setWindowTitle(f"Template AI {__version__} · 矩形排版研究版")
        self.resize(1340, 850)
        self.setMinimumSize(960, 640)
        self.build_ui()
        self.refresh_sources()
        self.refresh_templates()
        self.refresh_logos()
        self.statusBar().showMessage("本機研究版 · 請使用匿名／合成資料 · 實體印刷分析尚未執行")
        if self.font_manager.issues:
            self.statusBar().showMessage("字型資產需處理：" + "；".join(self.font_manager.issues))

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
        outer.addWidget(title)
        outer.addWidget(QLabel("匯入原稿 → 視覺核對與標記 → 學習並發布模板 → 輸入人物資料 → 驗證與數位輸出"))
        splitter = QSplitter()
        self.tabs = QTabWidget()
        self.tabs.addTab(self.build_training(), "① 訓練與原稿標記")
        self.tabs.addTab(self.build_templates(), "② 模板與 Logo")
        self.tabs.addTab(self.build_output(), "③ 排版與輸出")
        self.tabs.currentChanged.connect(self.mode_changed)
        splitter.addWidget(self.tabs)
        splitter.addWidget(self.build_properties())
        splitter.setSizes([1000, 300])
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
        self.menuBar().addAction("操作說明", self.help)

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
        links_row = QHBoxLayout()
        self.button("檢查原稿連結", self.check_source_link, links_row)
        self.button("重新連結同內容原稿", self.relink_source, links_row)
        self.button("批次來源定位／復原", self.batch_source_links, links_row)
        links_row.addStretch()
        layout.addLayout(links_row)
        works_row = QHBoxLayout()
        works_row.addWidget(QLabel("目前作品"))
        self.work_combo = QComboBox()
        self.work_combo.currentIndexChanged.connect(self.choose_work)
        works_row.addWidget(self.work_combo, 1)
        self.button("重新命名作品", self.rename_work, works_row)
        self.button("標記歷史／恢復", self.restore_work, works_row)
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
        layout.addLayout(row)
        return widget

    def build_templates(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        row = QHBoxLayout()
        self.button("新增空白矩形模板", self.new_template, row)
        self.button("加入合成示範模板", self.add_demo, row)
        self.button("建立新版本草稿", self.new_version, row)
        self.button("保存草稿", self.save_draft, row)
        self.button("驗證並發布", self.publish_template, row)
        layout.addLayout(row)
        split = QSplitter()
        self.template_list = QListWidget()
        self.template_list.currentRowChanged.connect(self.choose_template)
        split.addWidget(self.template_list)
        self.edit_canvas = Canvas()
        self.edit_canvas.selected.connect(self.select_slot)
        self.edit_canvas.rectangle.connect(self.add_rectangle)
        self.edit_canvas.moved.connect(self.box_moved)
        split.addWidget(self.edit_canvas)
        split.setSizes([230, 720])
        layout.addWidget(split, 1)
        row = QHBoxLayout()
        self.button("新增模板欄位", lambda: self.edit_canvas.set_mode("slot"), row)
        self.button("選取／移動", lambda: self.edit_canvas.set_mode("edit"), row)
        self.button("全稿", lambda: self.edit_canvas.fit(), row)
        self.button("刪除欄位", self.delete_slot, row)
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
        layout.addLayout(size_row)
        self.people = QTableWidget(1, 8)
        self.people.setHorizontalHeaderLabels(["姓名", "職稱", "電話", "Email", "LINE", "IG", "地址", "公司序號"])
        self.people.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.people.setMaximumHeight(115)
        self.people.itemChanged.connect(self.invalidate)
        layout.addWidget(QLabel("人物資料：多筆同類聯絡資訊以「；」分隔，公司序號對應下方公司 1、2…"))
        layout.addWidget(self.people)
        row = QHBoxLayout()
        self.button("新增人物", lambda: self.add_row(self.people), row)
        self.button("移除選取人物", lambda: self.remove_row(self.people), row)
        self.button("填入匿名示範資料", self.demo_input, row)
        layout.addLayout(row)
        self.companies = QTableWidget(1, 2)
        self.companies.setHorizontalHeaderLabels(["公司名稱", "已核准 Logo（依目前尺寸選取）"])
        self.companies.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.companies.setMaximumHeight(75)
        self.companies.itemChanged.connect(self.invalidate)
        layout.addWidget(self.companies)
        row = QHBoxLayout()
        self.button("新增公司", self.add_company, row)
        self.button("移除選取公司", lambda: self.remove_row(self.companies), row)
        self.button("更新同尺寸 Logo 選項", self.refresh_logos, row)
        layout.addLayout(row)
        split = QSplitter()
        self.candidate_list = QListWidget()
        self.candidate_list.currentRowChanged.connect(self.choose_candidate)
        split.addWidget(self.candidate_list)
        self.output_canvas = Canvas()
        split.addWidget(self.output_canvas)
        split.setSizes([220, 740])
        layout.addWidget(split, 1)
        self.issues = QLabel("輸入資料後開始排版。缺少同尺寸真實 Logo 或超出固定字級字寬限制時，正式輸出會被阻擋。")
        self.issues.setWordWrap(True)
        layout.addWidget(self.issues)
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
        return widget

    def build_properties(self):
        widget = QWidget()
        widget.setMinimumWidth(260)
        layout = QVBoxLayout(widget)
        group = QGroupBox("目前欄位 · 毫米屬性")
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
        form.addRow("對齊", self.align)
        form.addRow(self.required)
        self.property_button = QPushButton("套用至選取欄位")
        self.property_button.clicked.connect(self.apply_properties)
        form.addRow(self.property_button)
        layout.addWidget(group)
        self.selected_info = QLabel("先在畫布選取一個欄位。\n字級定案後不因字數自動改變。\n字寬下限是模板設計值，尚未實體印刷驗證。")
        self.selected_info.setWordWrap(True)
        layout.addWidget(self.selected_info)
        layout.addStretch()
        layout.addWidget(QLabel("第一版：標記幾何規則學習\n自動語意辨識與深度模型仍待後續研究\n本機資料不會自動上傳"))
        return widget

    def inform(self, text):
        QMessageBox.information(self, "Template AI", text)

    def error(self, text):
        self.statusBar().showMessage("操作未完成：" + text[:150])
        QMessageBox.warning(self, "需要處理", text)

    def run_job(self, message, function, callback):
        if self.busy:
            self.inform("目前仍有背景匯入工作，請等待完成")
            return
        self.busy = True
        self.import_button.setEnabled(False)
        self.statusBar().showMessage(message + " · 背景執行中，完成前不宣稱成功")
        job = Job(function)
        def finished(value):
            self.busy = False
            self.import_button.setEnabled(True)
            try:
                callback(value)
            except Exception as e:
                self.error(str(e))
        def failed(text):
            self.busy = False
            self.import_button.setEnabled(True)
            self.error(text)
        job.signals.done.connect(finished)
        job.signals.error.connect(failed)
        self.pool.start(job)

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

    def relink_source(self):
        if not self.source or self.busy:
            return
        source = dict(self.source)
        path, _ = QFileDialog.getOpenFileName(self, "選取同內容原稿（不替換內容）", "", "設計來源 (*.ai *.pdf *.svg *.eps *.png *.jpg *.jpeg);;所有檔案 (*)")
        if not path:
            return
        from .source_links import verify_source
        def finished(proof):
            self.library.relink_source(source["id"], proof, source.get("link_revision", 0))
            selected = self.source["id"] if self.source else source["id"]
            self.refresh_sources(selected)
            self.statusBar().showMessage("原稿已重新連結；內容一致，原登錄、作品與模板版次保留")
        self.run_job("核對原稿內容後重連", lambda: verify_source(path, source["hash"]), finished)

    def refresh_sources(self, select=None):
        self.sources = self.library.list_sources()
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        for s in self.sources:
            self.source_combo.addItem(f"{Path(s['current_path']).name} · 第 {s['page']} 頁 · {s['engine']}", s["id"])
            self.source_combo.setItemData(self.source_combo.count() - 1,
                f"原始登錄：{s['original_path']}\n目前位置：{s['current_path']}\n位置版次：r{s['link_revision']}", Qt.ToolTipRole)
        select = select or self.library.active_source_id()
        if select:
            self.source_combo.setCurrentIndex(next((i for i, s in enumerate(self.sources) if s["id"] == select), 0))
        self.source_combo.blockSignals(False)
        if self.sources:
            self.choose_source(self.source_combo.currentIndex())

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
                self.checkpoint()
                mapped = Rect((rect.x - self.crop.x) * self.work_width / self.crop.w, (rect.y - self.crop.y) * self.work_height / self.crop.h,
                              rect.w * self.work_width / self.crop.w, rect.h * self.work_height / self.crop.h)
                self.slots.append(self.make_slot(mapped))
                self.save_labels(silent=True)
            self.refresh_training()
        elif self.tabs.currentIndex() == 1 and self.editable():
            self.checkpoint()
            self.template.slots.append(self.make_slot(rect))
            self.refresh_editor()

    def make_slot(self, rect):
        return Slot(self.kind.currentData(), self.owner.currentData(), rect, self.index.value()-1,
                    self.font.currentFont().family(), self.pt.value(), self.scale.value()/100,
                    self.align.currentData(), self.required.isChecked(), color=self.text_color.text().strip(),
                    font_asset=self.font_manager.asset_for_family(self.font.currentFont().family()))

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
        self.property_button.setEnabled(s is not None and self.tabs.currentIndex() != 2)
        if not s:
            return
        self.kind.setCurrentIndex(self.kind.findData(s.kind))
        self.owner.setCurrentIndex(self.owner.findData(s.owner))
        self.index.setValue(s.index+1)
        for spin, value in zip(self.coords, [s.rect.x, s.rect.y, s.rect.w, s.rect.h]):
            spin.setValue(value)
        self.font.setCurrentFont(QFont(s.font))
        self.pt.setValue(s.size_pt)
        self.text_color.setText(s.color)
        self.scale.setValue(s.min_scale*100)
        self.align.setCurrentIndex(self.align.findData(s.align))
        self.required.setChecked(s.required)
        self.selected_info.setText(f"{KINDS[s.kind]} · {s.owner}\n已選取框位以作品毫米表示。\n原始字型／可編輯性未知時，不將本模板設計值冒稱原稿屬性。")

    def list_selection(self, row):
        if 0 <= row < len(self.slots):
            self.train_canvas.select_id(self.slots[row].id)

    def checkpoint(self):
        self.undo_stack.append(copy.deepcopy(self.current_slots()))
        self.undo_stack = self.undo_stack[-50:]
        self.redo_stack.clear()

    def undo(self):
        if not self.editable() or not self.undo_stack:
            return
        self.redo_stack.append(copy.deepcopy(self.current_slots()))
        self.replace_slots(self.undo_stack.pop())

    def redo(self):
        if not self.editable() or not self.redo_stack:
            return
        self.undo_stack.append(copy.deepcopy(self.current_slots()))
        self.replace_slots(self.redo_stack.pop())

    def replace_slots(self, slots):
        if self.tabs.currentIndex() == 0:
            self.slots = slots
            self.refresh_training()
            self.save_labels(silent=True)
        else:
            self.template.slots = slots
            self.refresh_editor()

    def box_moved(self, action, displayed_slot):
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
        import re
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", self.text_color.text().strip()):
            self.error("文字色彩請輸入 #RRGGBB，例如 #173d75")
            return
        self.checkpoint()
        s = self.make_slot(Rect(*(spin.value() for spin in self.coords)))
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
        self.checkpoint()
        self.current_slots().remove(self.current_slot)
        self.current_slot = None
        if self.tabs.currentIndex() == 0:
            self.refresh_training()
            self.save_labels(silent=True)
        else:
            self.refresh_editor()

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

    def refresh_templates(self, select=None):
        self.templates = self.library.templates()
        self.template_list.blockSignals(True)
        self.template_list.clear()
        for t in self.templates:
            self.template_list.addItem(f"{t.name} · v{t.version}\n{t.width_mm:g}×{t.height_mm:g} mm · {t.capacity} 人 · {'已發布' if t.state == 'published' else '草稿'}")
        self.template_list.blockSignals(False)
        if self.templates:
            index = next((i for i, t in enumerate(self.templates) if t.id == select), 0)
            self.template_list.setCurrentRow(index)

    def choose_template(self, row):
        if not 0 <= row < len(self.templates):
            return
        if self.template and self.template.state == "draft":
            self.library.save_template(self.template)
        self.template = copy.deepcopy(self.templates[row])
        self.undo_stack, self.redo_stack = [], []
        self.current_slot = None
        self.refresh_editor()
        self.edit_canvas.fit()

    def refresh_editor(self):
        if not self.template:
            return
        t = self.template
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
        self.edit_canvas.set_content(t.width_mm, t.height_mm, image=background_image, slots=t.slots)
        self.edit_canvas.set_mode("edit" if t.state == "draft" else "pan")
        self.template_info.setText(f"{t.name} v{t.version} · {'唯讀已發布' if t.state == 'published' else '可編輯草稿'}\n" + ("；".join(errors[:5]) if errors else "幾何與語意檢查未發現問題；正式輸出仍需實際資料量測") + "\n" + "；".join(t.reasons))

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
            self.library.save_template(self.template)
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
        self.library.save_template(self.template)
        self.refresh_templates(self.template.id)
        self.invalidate()

    def new_version(self):
        if not self.template:
            return
        t = copy.deepcopy(self.template)
        t.id, t.state = new_id(), "draft"
        t.version = self.library.next_version(t.family_id)
        self.library.save_template(t)
        self.refresh_templates(t.id)

    def save_draft(self):
        if not self.template or not self.editable():
            return
        try:
            self.library.save_template(self.template)
            self.refresh_templates(self.template.id)
            self.invalidate()
            self.statusBar().showMessage("模板草稿已持久保存")
        except Exception as e:
            self.error(str(e))

    def publish_template(self):
        if not self.template or self.template.state != "draft":
            return
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
        companies = sorted({s.owner for s in slots if s.kind in ("company", "logo")})
        people = sorted({s.owner for s in slots if s.kind == "name"})
        bindings = {}
        for person in people if companies else []:
            company, ok = QInputDialog.getItem(self, "確認人物公司歸屬", f"{person} 關聯哪一家公司？本版每人物支援一家公司。", companies, 0, False)
            if not ok:
                return None
            bindings[person] = company
        return bindings

    def capture_logo(self):
        if not self.source or not self.current_slot or self.current_slot.kind != "logo":
            self.error("請在原稿選取一個完整 Logo 標記框")
            return
        if not self.visual.isChecked():
            self.error("請先確認作品與可信原稿視覺一致")
            return
        company, ok = QInputDialog.getText(self, "公司歸屬", "此完整 Logo 所屬公司的已確認名稱")
        if not ok or not company.strip():
            return
        if QMessageBox.question(self, "Logo 核准", "確認框位包含完整圖文、來源可用且歸屬正確？\n僅核准目前作品尺寸，不跨尺寸借用。") != QMessageBox.Yes:
            return
        s = self.current_slot.rect
        crop = {"x": self.crop.x + s.x * self.crop.w / self.work_width, "y": self.crop.y + s.y * self.crop.h / self.work_height,
                "w": s.w * self.crop.w / self.work_width, "h": s.h * self.crop.h / self.work_height}
        self.library.add_logo(company, self.work_width, self.work_height, {"image": self.source["image"], "svg": self.source["svg"],
            "source_width_mm": self.source["width_mm"], "source_height_mm": self.source["height_mm"], "crop": crop, "source_id": self.source["id"]})
        self.refresh_logos()

    def import_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "完整 Logo 圖文來源", "", "Logo (*.svg *.pdf *.ai *.png *.jpg *.jpeg)")
        if not path:
            return
        company, ok = QInputDialog.getText(self, "公司歸屬", "已確認公司名稱")
        if not ok or not company.strip():
            return
        w, h = self.out_w.value(), self.out_h.value()
        def finished(result):
            if QMessageBox.question(self, "核准 Logo", f"請先核對原檔完整圖文及公司歸屬。\n核准公司「{company}」、矩形尺寸 {w:g}×{h:g} mm 的 Logo？") != QMessageBox.Yes:
                return
            self.library.add_logo(company, w, h, {"image": result["image"], "svg": result["svg"], "source_width_mm": result["width_mm"],
                "source_height_mm": result["height_mm"], "crop": None, "source_hash": result["hash"]})
            self.refresh_logos()
        self.run_job("匯入完整 Logo", lambda: import_file(path, self.library.assets), finished)

    def refresh_logos(self):
        self.logo_assets = self.library.logos()
        self.logo_list.clear()
        for asset in self.logo_assets:
            self.logo_list.addItem(f"{asset['company']} · {asset['width_mm']:g}×{asset['height_mm']:g} mm · 已核准")
        for row in range(self.companies.rowCount()):
            old = self.companies.cellWidget(row, 1)
            selected = old.currentData() if old else None
            combo = QComboBox()
            combo.addItem("尚未選取真實 Logo", None)
            for asset in self.logo_assets:
                if abs(asset["width_mm"]-self.out_w.value()) < 1e-5 and abs(asset["height_mm"]-self.out_h.value()) < 1e-5:
                    combo.addItem(asset["company"] + " · 已核准 " + asset["id"][:6], asset["id"])
            index = combo.findData(selected)
            if index >= 0:
                combo.setCurrentIndex(index)
            combo.currentIndexChanged.connect(self.invalidate)
            self.companies.setCellWidget(row, 1, combo)
        self.invalidate()

    def add_row(self, table):
        if table.rowCount() >= 20:
            self.error("本版最多 20 筆人物或公司")
            return
        table.insertRow(table.rowCount())
        self.invalidate()

    def add_company(self):
        self.add_row(self.companies)
        self.refresh_logos()

    def remove_row(self, table):
        if table.currentRow() >= 0 and table.rowCount() > 1:
            if QMessageBox.question(self, "移除資料", "移除後序號可能變動，請重新核對人物公司關聯。繼續？") == QMessageBox.Yes:
                table.removeRow(table.currentRow())
                self.invalidate()

    def input_data(self):
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
        self.export_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        if self.candidates:
            self.issues.setText("資料／尺寸／模板或 Logo 已變更；目前候選過期，請重新排版。")

    def generate(self):
        try:
            people, companies, logos = self.input_data()
            self.candidates = match(self.library.templates(True), self.out_w.value(), self.out_h.value(), people, companies, logos, self.generation)
            self.candidate_list.clear()
            for c in self.candidates:
                self.candidate_list.addItem(f"{'可正式數位輸出' if c.valid else '阻擋／診斷候選'}\n{c.template.name} · v{c.template.version}")
            if not self.candidates:
                self.issues.setText("目前沒有同矩形尺寸、同人物容量的已發布模板；請先建立或發布合適模板。本版尚未實作無模板的特製排版。")
                self.export_button.setEnabled(False)
                self.preview_button.setEnabled(False)
                self.output_canvas.scene().clear()
            else:
                self.candidate_list.setCurrentRow(0)
                self.statusBar().showMessage(f"已實際檢查 {len(self.candidates)} 個同尺寸同容量模板；排名為規則適配，不宣稱審美最優")
        except Exception as e:
            self.error(str(e))

    def choose_candidate(self, row):
        if not 0 <= row < len(self.candidates):
            return
        c = self.candidates[row]
        try:
            image = render_image(c, 150, not c.valid)
            self.output_canvas.set_content(c.template.width_mm, c.template.height_mm+(14 if not c.valid else 0), image)
            self.output_canvas.set_mode("pan")
            self.output_canvas.fit()
            current = c.generation == self.generation
            self.export_button.setEnabled(c.valid and current)
            self.preview_button.setEnabled(current)
            self.issues.setText(("數位排版檢查通過；尚未做實體印刷分析。" if c.valid else "正式輸出阻擋：\n" + "\n".join(c.issues[:8])) + "\n" + "；".join(c.reasons))
        except Exception as e:
            self.export_button.setEnabled(False)
            self.preview_button.setEnabled(False)
            self.error(str(e))

    def export_current(self, preview):
        row = self.candidate_list.currentRow()
        if not 0 <= row < len(self.candidates):
            return
        c = self.candidates[row]
        name = f"{c.template.width_mm:g}x{c.template.height_mm:g}_{'PREVIEW' if preview else 'FINAL'}.png"
        path, _ = QFileDialog.getSaveFileName(self, "保存數位檔案（預設不覆寫）", name, "PNG (*.png);;PDF (*.pdf);;JPG (*.jpg)")
        if not path:
            return
        try:
            export(c, path, self.dpi.value(), preview, self.generation)
            self.statusBar().showMessage("檔案已實際寫入：" + path)
        except Exception as e:
            self.error(str(e))

    def demo_input(self):
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
            asset = self.font_manager.import_font(path, approved=True)
            self.font.setCurrentFont(QFont(asset["families"][0]))
            self.inform("已保存並載入本程式：" + "、".join(asset["families"]) + "\n重開時會核對內容後自動載入；字型不會隨原始碼包上傳。")
            self.invalidate()
        except Exception as e:
            self.error(str(e))

    def mode_changed(self):
        self.current_slot = None
        self.property_button.setEnabled(False)
        self.undo_stack, self.redo_stack = [], []

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
        if self.busy:
            self.inform("來源正在安全匯入，請完成後再關閉")
            event.ignore()
            return
        try:
            if self.template and self.template.state == "draft":
                self.library.save_template(self.template)
            if self.source:
                self.save_labels(silent=True)
        except Exception as e:
            self.error("保存失敗，尚未安全關閉：" + str(e))
            event.ignore()
            return
        self.font_manager.close()
        self.library.close()
        event.accept()

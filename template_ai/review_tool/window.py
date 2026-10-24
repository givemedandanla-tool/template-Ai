"""Original-centred desktop review: visible facts first, linked measurements on demand."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QSplitter, QStackedWidget, QStyle, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from . import __version__
from .canvas import ReviewCanvas
from .jobs import AnalysisJobs
from .session import SessionStore


KINDS = {
    'unknown': '尚未確定', 'name': '姓名', 'title': '職稱', 'company': '公司名稱',
    'mobile': '手機', 'landline': '市內電話', 'phone': '電話（種類待查）',
    'fax': '傳真', 'email': '電子郵件', 'social_id': '社群帳號', 'address': '地址',
    'website': '網址', 'logo': '圖片／Logo', 'label': '資料標籤', 'noise': '旁註', 'other': '其他',
}
STATES = {'UNCHECKED': '尚未核對', 'REVIEWED': '已核對', 'UNKNOWN': '暫時無法確定'}
SOURCE_STATES = {'ADDED': '尚未判讀', 'READY': '尚未判讀', 'WAITING': '等待處理', 'QUEUED': '等待處理', 'RUNNING': '正在判讀',
                 'ANALYSING': '正在判讀', 'PROCESSING': '正在判讀', 'MISSING': '來源檔案找不到',
                 'ANALYSED': '已判讀，待核對', 'ANALYZED': '已判讀，待核對',
                 'COMPLETE': '已判讀，待核對', 'PARTIAL': '部分結果，需補查',
                 'FAILED': '需要處理問題', 'PAUSED': '已暫停'}


class ReviewWindow(QMainWindow):
    analysisFinished = Signal()
    fieldChanged = Signal(str)

    def __init__(self, data_dir, parent=None):
        super().__init__(parent)
        self.root = Path(data_dir)
        self.store = SessionStore(self.root)
        self.jobs = AnalysisJobs(self.root / 'cache', self)
        self.current_source_id = None
        self.current_work_id = None
        self.current_field_id = None
        self._view_page_id = None
        self._loading = False
        self._editor_dirty = False
        self._allow_close = False
        self._discarding = False
        self._annotation_kind = 'unknown'
        self._work_bounds_mode = False
        self._step = 0
        self.setWindowTitle(f'作品判讀與核對 · Template AI Review {__version__}')
        self.setMinimumSize(980, 660)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1440, max(980, int(screen.width() * .92))),
                    min(920, max(660, int(screen.height() * .9))))
        self._build()
        self.jobs.progress.connect(self._analysis_progress)
        self.jobs.result.connect(self._analysis_result)
        self.jobs.failure.connect(self._analysis_failure)
        self.jobs.finished.connect(self._analysis_finished)
        self._refresh_tree()
        saved = self.store.data.get('selection', {})
        if saved.get('work_id'):
            try:
                self.select_work(saved['work_id'])
                if saved.get('field_id'):
                    self.select_field(saved['field_id'])
                self.notify('已恢復上次工作。背景判讀保持暫停，可從下一處待核對接續。')
            except (KeyError, ValueError, TypeError):
                self.notify('上次的選取位置已變更，請從左側選擇作品。')
        notice = getattr(self.store, 'recovery_notice', None)
        if notice:
            self.notify(str(notice))
        self._update_save_state()

    def _button(self, text, icon=None, callback=None, primary=False):
        button = QPushButton(text)
        button.setAccessibleName(text)
        names = {'加入檔案':'folder-plus','開始判讀':'scan-text','暫停':'pause','更多':'ellipsis',
                 '選取':'mouse-pointer-2','新增標記':'square-plus','調整範圍':'scan','復原':'undo-2',
                 '查看全部判讀資料':'list-tree','套用這項修正':'check','標記彼此關係':'link-2',
                 '移除這個標記':'trash','比對本機字型':'type','下一處待核對':'arrow-right',
                 '保存進度':'save','完成這份核對':'check','放大':'zoom-in','縮小':'zoom-out',
                 '看整份作品':'maximize','放大檢查':'zoom-in','定位到原稿':'locate'}
        names.update({'移除選取關係': 'trash', '返回核對': 'undo-2', '新增人物或公司': 'square-plus'})
        svg = Path(__file__).parent / 'icons' / (names.get(text, '') + '.svg')
        if text in names and svg.is_file():
            button.setIcon(QIcon(str(svg)))
        elif icon:
            button.setIcon(self.style().standardIcon(icon))
        if primary:
            button.setObjectName('primary')
        if callback:
            button.clicked.connect(callback)
        return button

    def _build(self):
        self.setStyleSheet('''
        QMainWindow,QWidget{font-family:"Microsoft JhengHei UI","Noto Sans CJK TC";color:#172033;font-size:14px;}
        QMainWindow{background:#f4f6f9;} QLabel#brand{font-size:23px;font-weight:600;}
        QMenu{background:#ffffff;color:#172033;border:1px solid #d9e0ea;padding:4px 0;}
        QMenu::item{background:transparent;color:#172033;padding:8px 16px;}
        QMenu::item:selected:enabled{background:#e8f0ff;color:#153c91;}
        QMenu::item:disabled{color:#65728a;}
        QMenu::separator{height:1px;background:#dfe5ed;margin:5px 8px;}
        QPushButton{background:white;border:1px solid #d9e0ea;border-radius:6px;padding:8px 12px;min-height:20px;}
        QPushButton:hover{background:#edf4ff;border-color:#91b4f7;} QPushButton:disabled{color:#929baa;background:#edf0f5;}
        QPushButton#primary{background:#2563eb;color:white;border:1px solid #2563eb;font-weight:600;}
        QPushButton#primary:hover{background:#1d4ed8;} QLineEdit,QPlainTextEdit,QComboBox,QListWidget{background:white;border:1px solid #d9e0ea;border-radius:5px;padding:6px;}
        QTreeWidget{background:white;border:0;outline:none;} QTreeWidget::item{padding:9px 4px;border-bottom:1px solid #f0f3f8;}
        QTreeWidget::item:selected{background:#e8f0ff;color:#153c91;} QHeaderView::section{background:#f6f8fb;border:0;padding:7px;}
        QSplitter::handle{background:#e2e7ef;width:1px;} QScrollArea{border:0;background:white;}
        QFrame#panel{background:white;border:1px solid #e1e6ef;border-radius:7px;}
        QLabel#notice{background:#eef4ff;color:#20477d;padding:9px;border-radius:5px;}
        ''')
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(10)
        header = QHBoxLayout()
        brand = QLabel('作品判讀與核對')
        brand.setObjectName('brand')
        header.addWidget(brand)
        header.addWidget(QLabel(f'Template AI · {__version__}'))
        header.addStretch()
        self.add_button = self._button('加入檔案', QStyle.StandardPixmap.SP_DirOpenIcon, self.choose_files)
        self.start_button = self._button('開始判讀', QStyle.StandardPixmap.SP_MediaPlay, self.start_analysis)
        self.pause_button = self._button('暫停', QStyle.StandardPixmap.SP_MediaPause, self._pause_resume)
        self.pause_button.hide()
        self.more_button = self._button('更多', QStyle.StandardPixmap.SP_FileDialogDetailedView)
        menu = QMenu(self)
        for text, callback in [('重試失敗檔案', self.retry_failed), ('重新判讀目前檔案', self.reanalyse_current),
                               ('加入重新判讀新找到的作品', self.adopt_new_works),
                               ('調整作品範圍', self.adjust_work_bounds), ('停止本次判讀', self.stop_analysis),
                               ('匯出完整觀察資料（僅本機）', self.export_observations),
                               ('匯出問題報告', self.export_report), ('查看保存位置', self.open_data_dir)]:
            action = menu.addAction(text)
            action.triggered.connect(callback)
        self.more_button.setMenu(menu)
        for button in (self.add_button, self.start_button, self.pause_button, self.more_button):
            header.addWidget(button)
        outer.addLayout(header)
        guide = QHBoxLayout()
        self.steps = []
        for label in ['① 加入檔案', '② 判讀檔案', '③ 核對與修正', '④ 保存與完成']:
            step = QLabel(label)
            step.setAlignment(Qt.AlignmentFlag.AlignCenter)
            guide.addWidget(step, 1)
            self.steps.append(step)
        outer.addLayout(guide)
        self.notice = QLabel('加入 AI、PDF 或 SVG 作品，查看判讀結果，再核對內容與歸屬。')
        self.notice.setObjectName('notice')
        self.notice.setTextFormat(Qt.TextFormat.PlainText)
        self.notice.setWordWrap(True)
        outer.addWidget(self.notice)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['檔案與作品'])
        self.tree.setColumnCount(1)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tree.setMinimumWidth(190)
        self.tree.setColumnWidth(0, 180)
        self.tree.itemSelectionChanged.connect(self._tree_selected)
        splitter.addWidget(self.tree)
        workspace = QWidget()
        wl = QVBoxLayout(workspace)
        wl.setContentsMargins(8, 0, 8, 0)
        tools = QHBoxLayout()
        self.select_button = self._button('選取', QStyle.StandardPixmap.SP_ArrowUp, lambda: self.canvas.set_mode('select'))
        self.add_mark_button = self._button('新增標記', QStyle.StandardPixmap.SP_FileDialogNewFolder)
        mark_menu = QMenu(self)
        for label, kind in [('作品範圍', '__work__'), ('文字欄位', 'unknown'), ('圖片／Logo', 'logo'), ('旁註', 'noise')]:
            action = mark_menu.addAction(label)
            action.triggered.connect(lambda checked=False, k=kind: self.begin_add(k))
        self.add_mark_button.setMenu(mark_menu)
        self.resize_button = self._button('調整範圍', QStyle.StandardPixmap.SP_TitleBarMaxButton, lambda: self.canvas.set_mode('resize'))
        self.undo_button = self._button('復原', QStyle.StandardPixmap.SP_ArrowBack, self.undo)
        for button in (self.select_button, self.add_mark_button, self.resize_button, self.undo_button):
            tools.addWidget(button)
        tools.addStretch()
        wl.addLayout(tools)
        self.canvas = ReviewCanvas()
        self.canvas.scene().addText('從上方「加入檔案」開始。\n原稿與判讀結果會顯示在這裡。')
        self.canvas.fieldSelected.connect(self._canvas_selected)
        self.canvas.annotationAdded.connect(self._on_annotation_added)
        self.canvas.annotationResized.connect(self._on_annotation_resized)
        self.canvas.statusMessage.connect(self.notify)
        if hasattr(self.canvas, 'fieldsSelected'):
            self.canvas.fieldsSelected.connect(lambda ids: self.relation_button.setVisible(len(ids) > 1))
        wl.addWidget(self.canvas, 1)
        viewtools = QHBoxLayout()
        overlay = QCheckBox('判讀標記')
        overlay.setChecked(True)
        overlay.toggled.connect(self.canvas.set_overlays_visible)
        viewtools.addWidget(overlay)
        viewtools.addStretch()
        for text, callback in [('縮小', lambda: self.canvas.zoom(.8)), ('放大', lambda: self.canvas.zoom(1.25)),
                               ('看整份作品', self.canvas.fit_work)]:
            viewtools.addWidget(self._button(text, callback=callback))
        wl.addLayout(viewtools)
        splitter.addWidget(workspace)
        right = QFrame()
        self.right_panel = right
        right.setObjectName('panel')
        right.setMinimumWidth(310)
        rl = QVBoxLayout(right)
        self.detail_title = QLabel('選取原稿上的標記')
        self.detail_title.setTextFormat(Qt.TextFormat.PlainText)
        self.detail_title.setStyleSheet('font-size:18px;font-weight:600;')
        rl.addWidget(self.detail_title)
        self.overview_button = self._button('查看全部判讀資料', QStyle.StandardPixmap.SP_FileDialogInfoView, self.show_overview)
        rl.addWidget(self.overview_button)
        self.detail_stack = QStackedWidget()
        placeholder = QLabel('點選原稿上的內容，就能核對文字、種類與歸屬。\n\n精確數據收在總覽，不必逐項填寫。')
        placeholder.setWordWrap(True)
        placeholder.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.detail_stack.addWidget(placeholder)
        form_page = QWidget()
        form = QFormLayout(form_page)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setMaximumHeight(90)
        form.addRow('判讀文字', self.text_edit)
        self.prediction_label = QLabel()
        self.prediction_label.setTextFormat(Qt.TextFormat.PlainText)
        self.prediction_label.setWordWrap(True)
        self.prediction_label.setStyleSheet('color:#65728a;')
        form.addRow('原判讀', self.prediction_label)
        self.kind_combo = QComboBox()
        for key, label in KINDS.items():
            self.kind_combo.addItem(label, key)
        form.addRow('資料種類', self.kind_combo)
        self.owner_combo = QComboBox()
        form.addRow('屬於誰', self.owner_combo)
        self.add_owner_button = self._button('新增人物或公司', QStyle.StandardPixmap.SP_FileDialogNewFolder, self.add_owner)
        form.addRow(self.add_owner_button)
        self.shared_list = QListWidget()
        self.shared_list.setMaximumHeight(95)
        form.addRow('共享給誰（可不選）', self.shared_list)
        self.review_combo = QComboBox()
        for key, label in STATES.items():
            self.review_combo.addItem(label, key)
        self.apply_field_button = self._button('套用這項修正', QStyle.StandardPixmap.SP_DialogApplyButton, self.commit_field)
        self.relation_button = self._button('標記彼此關係', QStyle.StandardPixmap.SP_FileLinkIcon, self.add_relation)
        self.relation_button.hide()
        form.addRow(self.relation_button)
        form.addRow(self._button('移除這個標記', QStyle.StandardPixmap.SP_TrashIcon, self.remove_annotation))
        self.font_button = self._button('比對本機字型', QStyle.StandardPixmap.SP_FileDialogContentsView, self.compare_font)
        form.addRow(self.font_button)
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setWidget(form_page)
        self.detail_stack.addWidget(scroller)
        overview_page = QWidget()
        ol = QVBoxLayout(overview_page)
        ol.setContentsMargins(0, 0, 0, 0)
        self.overview_search = QLineEdit()
        self.overview_search.setPlaceholderText('搜尋目前項目的數據或關係')
        self.overview_search.textChanged.connect(self._filter_overview)
        ol.addWidget(self.overview_search)
        self.overview_tree = QTreeWidget()
        self.overview_tree.setHeaderLabels(['判讀資料', '數值／狀態'])
        self.overview_tree.setColumnWidth(0, 150)
        self.overview_tree.itemClicked.connect(self._overview_selected)
        ol.addWidget(self.overview_tree, 1)
        for text, callback in [('定位到原稿', self.locate_current), ('放大檢查', self.zoom_current), ('返回核對', self.show_review)]:
            ol.addWidget(self._button(text, callback=callback))
        self.remove_relation_button = self._button('移除選取關係', QStyle.StandardPixmap.SP_TrashIcon, self.remove_selected_relation)
        self.remove_relation_button.hide()
        self._selected_relation_id = None
        ol.addWidget(self.remove_relation_button)
        self.detail_stack.addWidget(overview_page)
        rl.addWidget(self.detail_stack, 1)
        self.field_actions = QWidget()
        actions = QVBoxLayout(self.field_actions)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.addWidget(QLabel('核對狀態'))
        actions.addWidget(self.review_combo)
        actions.addWidget(self.apply_field_button)
        rl.addWidget(self.field_actions)
        self.field_actions.hide()
        self.detail_stack.currentChanged.connect(lambda index: self.field_actions.setVisible(index == 1))
        self.next_button = self._button('下一處待核對', QStyle.StandardPixmap.SP_ArrowForward, self.next_pending)
        rl.addWidget(self.next_button)
        splitter.addWidget(right)
        splitter.setSizes([240, 750, 350])
        outer.addWidget(splitter, 1)
        footer = QHBoxLayout()
        self.save_state = QLabel('尚未加入檔案')
        self.save_state.setWordWrap(True)
        footer.addWidget(self.save_state, 1)
        self.save_button = self._button('保存進度', QStyle.StandardPixmap.SP_DialogSaveButton, self.save_progress, True)
        self.complete_button = self._button('完成這份核對', QStyle.StandardPixmap.SP_DialogApplyButton, self.complete_current_work)
        footer.addWidget(self.save_button)
        footer.addWidget(self.complete_button)
        outer.addLayout(footer)
        for signal in (self.text_edit.textChanged, self.kind_combo.currentIndexChanged,
                       self.owner_combo.currentIndexChanged, self.review_combo.currentIndexChanged,
                       self.shared_list.itemChanged):
            signal.connect(self._editor_changed)
        self._set_step(0)

    def _set_step(self, index):
        self._step = index
        for i, step in enumerate(self.steps):
            step.setStyleSheet('padding:9px;border-bottom:3px solid '+('#2563eb;color:#1d4ed8;font-weight:600;' if i == index else '#dfe5ed;color:#6d7890;'))
        for button, active in ((self.add_button, index == 0), (self.start_button, index == 1),
                               (self.save_button, index in (2, 3))):
            button.setObjectName('primary' if active else '')
            button.style().unpolish(button)
            button.style().polish(button)

    def notify(self, message):
        self.notice.setText(str(message))

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, '加入作品檔案', '', '作品檔案 (*.ai *.pdf *.svg);;所有檔案 (*)')
        if paths:
            self.add_files(paths)

    def add_files(self, paths):
        self.commit_field()
        try:
            added = self.store.add_files(paths)
        except (OSError, ValueError):
            self.notify('無法加入這批檔案。請選擇仍在本機的 AI、PDF 或 SVG 檔案，再試一次；這批尚未加入。')
            return []
        self._refresh_tree()
        self._set_step(1)
        self.notify(f'已加入 {len(added)} 個檔案，尚未判讀。點擊「開始判讀」後取得預覽與作品候選。')
        self._update_save_state()
        return added

    def start_analysis(self, sources=None):
        if isinstance(sources, bool):
            sources = None
        if self.jobs.is_running():
            self.notify('目前已有判讀工作。可以暫停或等候完成。')
            return
        self.commit_field()
        if sources is None:
            sources = [s for s in self.store.sources() if
                       (not s.get('analysis') and s.get('status') != 'FAILED')
                       or s.get('status') in ('PAUSED', 'PARTIAL')]
        if not sources:
            self.notify('沒有尚未判讀的檔案；需要更新時，從「更多」選擇重新判讀。')
            return
        self._set_step(1)
        self.start_button.setEnabled(False)
        self.pause_button.show()
        self.pause_button.setText('暫停')
        self.jobs.start(sources)

    def _analysis_progress(self, source_id, event):
        stage = str(event.get('stage', ''))
        if source_id and stage not in ('paused', 'pausing', 'resumed', 'stopped'):
            self.store.stage_status(source_id, 'ANALYSING', str(event.get('message', '正在判讀')))
        if stage == 'paused':
            self.pause_button.setText('繼續判讀')
            self.pause_button.setIcon(QIcon(str(Path(__file__).parent / 'icons/arrow-right.svg')))
        elif stage == 'resumed':
            self.pause_button.setText('暫停')
            self.pause_button.setIcon(QIcon(str(Path(__file__).parent / 'icons/pause.svg')))
        message = event.get('message') or '正在判讀，請稍候。'
        if source_id:
            message = self.store.get_source(source_id).get('name', '目前檔案') + '：' + message
        if self.current_work_id and stage not in ('paused', 'pausing', 'stopped'):
            message = '背景判讀：' + message + '　你可以繼續核對目前作品。'
        self.notify(message)
        self._refresh_tree()

    def _analysis_result(self, source_id, result):
        if self._discarding:
            return
        self.commit_field()
        self.store.apply_analysis(source_id, result)
        try:
            self.store.save()
        except OSError:
            self.notify('結果已取得，但保存失敗。請保留此視窗並重試保存。')
        self._refresh_tree()
        works = self.store.works(source_id)
        if not self.current_work_id and works and self.current_source_id in (None, source_id):
            self.select_work(works[0]['id'])
        self._update_save_state()

    def _analysis_failure(self, source_id, message):
        self.store.stage_status(source_id, 'FAILED', str(message))
        self.notify(str(message) + ' 已完成結果保留，可從「更多」重試失敗檔案或匯出問題報告。')
        self._refresh_tree()
        self._update_save_state()

    def _analysis_finished(self):
        self.start_button.setEnabled(True)
        self.pause_button.hide()
        if not self._discarding:
            for source in self.store.sources():
                if source.get('status') in ('ANALYSING', 'PROCESSING'):
                    self.store.stage_status(source['id'], 'PAUSED', '工作已停止；完成部分保留，可稍後接續。')
            try:
                self.store.save()
            except OSError:
                self.notify('判讀已停止，但保存尚未成功。請重試保存。')
        self._refresh_tree()
        self._update_save_state()
        self.analysisFinished.emit()

    def _pause_resume(self):
        if getattr(self.jobs, 'paused', False):
            self.jobs.resume()
        else:
            self.jobs.pause()

    def stop_analysis(self):
        self.jobs.stop()

    def retry_failed(self):
        self.start_analysis([s for s in self.store.sources() if s.get('status') == 'FAILED'])

    def reanalyse_current(self):
        if self.current_source_id:
            self.notify('新的判讀會另存版本；已有人工修正不會被覆蓋。')
            self.start_analysis([self.store.get_source(self.current_source_id)])

    def adopt_new_works(self):
        self.commit_field()
        if not self.current_source_id:
            self.notify('請先選取來源檔案。')
            return
        source = self.store.get_source(self.current_source_id)
        version_id = source.get('pending_analysis_version')
        if not version_id:
            self.notify('目前沒有等待採用的新判讀作品。')
            return
        try:
            added = self.store.adopt_new_unseen_works(self.current_source_id, version_id)
        except (ValueError, KeyError) as error:
            self.notify(str(error))
            return
        self._refresh_tree()
        self._update_save_state()
        self.notify(f'已加入 {len(added["work_ids"])} 份新找到的作品，原有人工修正維持不變。')

    def _refresh_tree(self):
        self.tree.blockSignals(True)
        self.tree.clear()
        for source in self.store.sources():
            status = SOURCE_STATES.get(source.get('status', 'ADDED'), '待核對')
            name = source.get('name') or Path(source.get('path', '')).name
            parent = QTreeWidgetItem([name + '\n' + status])
            parent.setData(0, Qt.ItemDataRole.UserRole, ('source', source['id']))
            parent.setToolTip(0, source.get('name', '來源檔案'))
            self.tree.addTopLevelItem(parent)
            for work in self.store.works(source['id']):
                fields = work.get('fields', [])
                pending = sum(f.get('review_state') != 'REVIEWED' for f in fields)
                state = '仍有待查項目' if pending else ('已核對' if fields else '尚未標記欄位')
                child = QTreeWidgetItem([(work.get('name') or '作品') + '\n' + state])
                child.setData(0, Qt.ItemDataRole.UserRole, ('work', work['id']))
                parent.addChild(child)
                if work['id'] == self.current_work_id:
                    self.tree.setCurrentItem(child)
            parent.setExpanded(True)
        self.tree.blockSignals(False)
        pending = [s for s in self.store.sources() if
                   (not s.get('analysis') and s.get('status') != 'FAILED') or s.get('status') in ('PAUSED', 'PARTIAL')]
        self.start_button.setEnabled(not self.jobs.is_running() and bool(pending))
        self.start_button.setText(f'開始判讀（{len(pending)}）' if pending else '開始判讀')
        self.start_button.setAccessibleName(f'開始判讀 {len(pending)} 個檔案')
        self.complete_button.setEnabled(bool(self.current_work_id))

    def _tree_selected(self):
        item = self.tree.currentItem()
        if not item:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data:
            self.select_work(data[1]) if data[0] == 'work' else self.select_source(data[1])

    def _page(self, source, work=None):
        pages = source.get('analysis', {}).get('pages', [])
        if work:
            for page in pages:
                if page.get('id') == work.get('page_id') or page.get('page') == work.get('page'):
                    return page
        if not work and self._view_page_id:
            for page in pages:
                if page.get('id') == self._view_page_id:
                    return page
        return pages[0] if pages else None

    def select_source(self, source_id):
        self.commit_field()
        self.current_source_id, self.current_work_id, self.current_field_id = source_id, None, None
        source = self.store.get_source(source_id)
        page = self._page(source)
        if page:
            self._view_page_id = page.get('id')
        self.detail_stack.setCurrentIndex(0)
        self.detail_title.setText('先查看作品範圍')
        if page:
            self.canvas.set_source(page['image'], page['width_mm'], page['height_mm'], calibrated=bool(page.get('calibrated', False)))
            self.canvas.set_work({'crop': {'x': 0, 'y': 0, 'w': page['width_mm'], 'h': page['height_mm']}})
            self.canvas.set_fields([{'id': 'work:' + w['id'], 'rect': w['crop'], 'label': w.get('name', '作品')}
                                    for w in self.store.works(source_id) if w.get('page') == page.get('page')])
        else:
            self.notify('這個檔案尚未判讀；點擊「開始判讀」取得預覽與作品範圍。')
        self._update_save_state()

    def select_work(self, work_id):
        self.commit_field()
        work = self.store.get_work(work_id)
        self.current_work_id, self.current_source_id, self.current_field_id = work_id, work['source_id'], None
        self._work_bounds_mode = False
        source = self.store.get_source(self.current_source_id)
        page = self._page(source, work)
        if page:
            self._view_page_id = page.get('id')
            self.canvas.set_source(page['image'], page['width_mm'], page['height_mm'], calibrated=bool(page.get('calibrated', False)))
            self.canvas.set_work(work)
            self._draw_fields()
        self.detail_title.setText(work.get('name', '作品'))
        self.detail_stack.setCurrentIndex(0)
        self.store.select(self.current_source_id, work_id, None)
        self._set_step(2)
        self.notify('先確認作品範圍，再點選標記核對文字與歸屬。無法確定的內容可以保留待查。')
        self._update_save_state()

    def _draw_fields(self):
        if not self.current_work_id:
            return
        fields = [dict(f, label=KINDS.get(str(f.get('kind', '')).lower(), '待核對內容'))
                  for f in self.store.get_work(self.current_work_id).get('fields', [])]
        self.canvas.blockSignals(True)
        self.canvas.set_fields(fields)
        if self.current_field_id:
            self.canvas.select_field(self.current_field_id)
        self.canvas.blockSignals(False)

    def _canvas_selected(self, field_id):
        if field_id.startswith('work:'):
            if not self._work_bounds_mode:
                self.select_work(field_id[5:])
        else:
            self.select_field(field_id)

    def select_field(self, field_id):
        self.commit_field()
        if not self.current_work_id:
            return
        field = self.store.get_field(self.current_work_id, field_id)
        self.current_field_id = field_id
        self.store.select(self.current_source_id, self.current_work_id, field_id)
        self._loading = True
        self.text_edit.setPlainText(field.get('text', ''))
        self.kind_combo.setCurrentIndex(max(0, self.kind_combo.findData(str(field.get('kind', 'unknown')).lower())))
        prediction = field.get('prediction', {})
        self.prediction_label.setText(KINDS.get(str(prediction.get('kind', 'unknown')).lower(), '尚未確定'))
        self.owner_combo.clear()
        self.owner_combo.addItem('尚未指定', None)
        self.shared_list.clear()
        for owner in self.store.data.get('owners', []):
            oid = owner['id']
            self.owner_combo.addItem(owner.get('label') or owner.get('name') or '人物／公司', oid)
            row = QListWidgetItem(owner.get('label') or owner.get('name') or '人物／公司')
            row.setData(Qt.ItemDataRole.UserRole, oid)
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(Qt.CheckState.Checked if oid in field.get('shared_with', []) else Qt.CheckState.Unchecked)
            self.shared_list.addItem(row)
        self.owner_combo.setCurrentIndex(max(0, self.owner_combo.findData(field.get('owner'))))
        self.review_combo.setCurrentIndex(max(0, self.review_combo.findData(field.get('review_state', 'UNCHECKED'))))
        self._loading = False
        self._editor_dirty = False
        self.detail_title.setText('選取的欄位')
        if self.detail_stack.currentIndex() == 2:
            self._populate_overview()
        else:
            self.detail_stack.setCurrentIndex(1)
        self.canvas.select_field(field_id)
        self._set_step(2)
        self._update_save_state()

    def _editor_changed(self, *args):
        if not self._loading and self.current_field_id:
            self._editor_dirty = True
            self._set_step(2)
            self._update_save_state()

    def commit_field(self):
        if not self._editor_dirty or not self.current_work_id or not self.current_field_id:
            return
        shared = [self.shared_list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.shared_list.count())
                  if self.shared_list.item(i).checkState() == Qt.CheckState.Checked]
        owner = self.owner_combo.currentData()
        self.store.update_field(self.current_work_id, self.current_field_id,
            {'text': self.text_edit.toPlainText(), 'kind': self.kind_combo.currentData(), 'owner': owner,
             'shared_with': [x for x in shared if x != owner], 'review_state': self.review_combo.currentData()})
        self._editor_dirty = False
        self._draw_fields()
        self._refresh_tree()
        self._update_save_state()
        self.fieldChanged.emit(self.current_field_id)

    def add_owner(self):
        label, ok = QInputDialog.getText(self, '新增人物或公司', '請輸入顯示名稱：')
        if not ok or not label.strip():
            return
        kind, ok = QInputDialog.getItem(self, '資料歸屬', '這是人物還是公司？', ['人物', '公司'], 0, False)
        if not ok:
            return
        self.commit_field()
        owner = self.store.add_owner(label.strip(), 'PERSON' if kind == '人物' else 'COMPANY')
        oid = owner['id'] if isinstance(owner, dict) else owner
        if self.current_field_id:
            self.select_field(self.current_field_id)
            self.owner_combo.setCurrentIndex(self.owner_combo.findData(oid))

    def begin_add(self, kind):
        self.commit_field()
        if not self.current_source_id:
            self.notify('請先判讀並選取一份可預覽的來源。')
            return
        self._annotation_kind = kind
        if kind == '__work__':
            self.select_source(self.current_source_id)
        elif not self.current_work_id:
            self.notify('請先選取作品，再新增其中的欄位。')
            return
        self.canvas.set_mode('add')
        self.notify('在原稿上拖曳框選範圍；原稿本身不會被改動。')

    def _on_annotation_added(self, rect):
        if self._annotation_kind == '__work__':
            source = self.store.get_source(self.current_source_id)
            page = self._page(source)
            if page:
                work = self.store.add_work(source['id'], page['id'], rect)
                self._refresh_tree()
                self.select_work(work['id'])
        elif self.current_work_id:
            field = self.store.add_annotation(self.current_work_id, self._annotation_kind, rect)
            self._draw_fields()
            self.select_field(field['id'])
        self.canvas.set_mode('select')
        self._update_save_state()

    def _on_annotation_resized(self, field_id, rect):
        if field_id.startswith('work:'):
            work_id = field_id[5:]
            self.store.resize_work(work_id, rect)
            self.select_work(work_id)
        elif self.current_work_id:
            self.store.resize_annotation(self.current_work_id, field_id, rect)
            self._draw_fields()
        self._update_save_state()

    def adjust_work_bounds(self):
        if not self.current_source_id:
            return
        work_id = self.current_work_id
        self.select_source(self.current_source_id)
        self._work_bounds_mode = True
        self.canvas.set_mode('resize')
        if work_id:
            self.canvas.select_field('work:' + work_id)
        self.notify('拖動作品範圍的邊界。只修正判讀範圍，不移動原稿。')

    def remove_annotation(self):
        self.commit_field()
        if self.current_field_id and self.current_work_id:
            self.store.remove_annotation(self.current_work_id, self.current_field_id)
            self.current_field_id = None
            self._editor_dirty = False
            self.detail_stack.setCurrentIndex(0)
            self._draw_fields()
            self._refresh_tree()
            self._update_save_state()

    def undo(self):
        self.commit_field()
        previous_field_id = self.current_field_id
        if self.store.undo():
            wid = self.current_work_id
            self.current_field_id = None
            try:
                if wid:
                    self.select_work(wid)
                    if previous_field_id and any(f['id'] == previous_field_id for f in self.store.get_work(wid).get('fields', [])):
                        self.select_field(previous_field_id)
            except (KeyError, ValueError):
                self.current_work_id = None
            self._refresh_tree()
            self._update_save_state()

    def add_relation(self):
        if not self.current_work_id:
            return
        ids = self.canvas.selected_fields()
        if len(ids) < 2:
            self.notify('按住 Ctrl 或 Shift 點選多個標記，再標記彼此關係。')
            return
        labels = {'同一組': 'group', '左邊切齊': 'aligned_to', '右邊切齊': 'aligned_to',
                  '上下順序': 'precedes', '標籤對應資料': 'label_of', '圖示對應資料': 'icon_for'}
        label, ok = QInputDialog.getItem(self, '標記彼此關係', '請選擇原稿上看見的關係：', list(labels), 0, False)
        if ok:
            props = {'alignment': 'left' if label == '左邊切齊' else 'right'} if '切齊' in label else {}
            relation = self.store.add_relation(self.current_work_id, ids, labels[label], **props)
            self.canvas.show_measurement(relation, self.store.get_field(self.current_work_id, ids[0]))
            self._update_save_state()

    def next_pending(self):
        self.commit_field()
        items = [(w, f) for w in self.store.works() for f in w.get('fields', [])]
        if not items:
            self.notify('目前沒有欄位標記。可以在原稿上新增標記，不代表原稿沒有文字。')
            return
        current = next((i for i, (_, f) in enumerate(items) if f['id'] == self.current_field_id), -1)
        ordered = items[current + 1:] + items[:current + 1]
        for work, field in ordered:
            if field.get('review_state') != 'REVIEWED':
                if work['id'] != self.current_work_id:
                    self.select_work(work['id'])
                self.select_field(field['id'])
                self.canvas.locate_field(field['id'])
                return
        self.notify('目前所有欄位都已標記核對。可完成這份作品，或打開總覽檢查。')

    def show_overview(self):
        self.commit_field()
        self.detail_stack.setCurrentIndex(2)
        self.detail_title.setText('判讀總覽')
        self._populate_overview()

    def show_review(self):
        self.canvas.clear_measurement()
        self.detail_title.setText('選取的欄位' if self.current_field_id else '選取原稿上的標記')
        self.detail_stack.setCurrentIndex(1 if self.current_field_id else 0)

    def _populate_overview(self):
        self.overview_tree.clear()
        self._selected_relation_id = None
        self.remove_relation_button.hide()
        if not self.current_work_id:
            QTreeWidgetItem(self.overview_tree, ['先選取作品或欄位', '點選中央原稿上的標記'])
            return
        work = self.store.get_work(self.current_work_id)
        work_info = QTreeWidgetItem(self.overview_tree, ['作品結構與量測', '目前作品，按需展開'])
        self._add_data(work_info, {k: v for k, v in work.items() if k not in ('fields', 'relations', 'geometry_relations')})
        field = self.store.get_field(self.current_work_id, self.current_field_id) if self.current_field_id else None
        if field:
            record = QTreeWidgetItem(self.overview_tree, ['欄位完整記錄', '目前選取項目'])
            self._add_data(record, {k: v for k, v in field.items() if k not in ('measurements', 'evidence', 'prediction', 'revisions')})
            page = self._page(self.store.get_source(self.current_source_id), work) or {}
            calibrated = (page.get('calibrated') is True
                          and work.get('measurements', {}).get('width_mm', {}).get('status') != 'UNKNOWN'
                          and field.get('measurements', {}).get('frame', {}).get('coordinate') != 'UNVERIFIED_PREVIEW_MM')
            section = QTreeWidgetItem(self.overview_tree, ['尺寸與位置', '判讀標記，非可用容器' if calibrated else '實體比例未確認，以下只供預覽定位'])
            rect = field.get('rect', {})
            for key, name, metric in [('x', '左邊位置', 'rect'), ('y', '上邊位置', 'rect'), ('w', '欄位寬度', 'width'), ('h', '欄位高度', 'height')]:
                value = f'{rect[key]:.3f}' + (' mm' if calibrated else '（預覽座標，非已驗毫米）') if isinstance(rect.get(key), (int, float)) else '尚未取得'
                item = QTreeWidgetItem(section, [name, value])
                item.setData(0, Qt.ItemDataRole.UserRole, ('metric', metric))
            section.setExpanded(True)
            for label, key in [('文字樣式與量測', 'measurements'), ('取得依據', 'evidence'), ('原判讀', 'prediction'), ('人工修訂', 'revisions'), ('人工字型核對', 'human_font_annotation')]:
                parent = QTreeWidgetItem(self.overview_tree, [label, ''])
                self._add_data(parent, field.get(key, {}))
        else:
            QTreeWidgetItem(self.overview_tree, ['目前作品', work.get('name', '作品')])
        relations = QTreeWidgetItem(self.overview_tree, ['欄位關係', '點選以在原稿查看'])
        for relation in work.get('relations', []):
            item = QTreeWidgetItem(relations, [str(relation.get('kind', '關係')), '人工標記或來源觀察'])
            item.setData(0, Qt.ItemDataRole.UserRole, ('relation', relation))
        for relation in work.get('geometry_relations', []):
            item = QTreeWidgetItem(relations, ['相鄰位置量測（非切齊規則）', '點選顯示對應欄位'])
            item.setData(0, Qt.ItemDataRole.UserRole, ('relation', relation))
            self._add_data(item, relation.get('measurements', {}))
        if field and field.get('owner'):
            owner = field['owner']
            related_ids = [f['id'] for f in work.get('fields', []) if f.get('owner') == owner or owner in f.get('shared_with', [])]
            item = QTreeWidgetItem(relations, ['共同歸屬／共享', '依穩定人物／公司關聯'])
            item.setData(0, Qt.ItemDataRole.UserRole, ('relation', {'kind': 'owned_by', 'field_ids': related_ids}))
        for label in ['字型身份', '原始字級', '基線', '分散方式', '容器可用範圍']:
            QTreeWidgetItem(self.overview_tree, [label, '依來源證據；未取得時保持未知'])
        source = self.store.get_source(self.current_source_id)
        source_info = QTreeWidgetItem(self.overview_tree, ['來源／工具／缺失', '僅本機資料，按需展開'])
        analysis = source.get('analysis', {})
        self._add_data(source_info, {'來源': analysis.get('source', {}), '目前頁面': self._page(source, work),
                                    '工具能力': analysis.get('capabilities', {}), '缺失與例外': source.get('issues', []),
                                    '待採用新判讀版本': source.get('pending_analysis_version')})
        versions = len(source.get('analysis_versions', []))
        if versions:
            QTreeWidgetItem(self.overview_tree, ['另存判讀版本', f'{versions} 份；人工修正保留'])
        self._filter_overview(self.overview_search.text())

    def _add_data(self, parent, value, depth=0):
        if depth > 5:
            QTreeWidgetItem(parent, ['更多內容', '保存在完整本地觀察包'])
            return
        rows = value.items() if isinstance(value, dict) else enumerate(value) if isinstance(value, list) else [('內容', value)]
        for count, (key, item) in enumerate(rows):
            if count >= 150:
                QTreeWidgetItem(parent, ['其餘內容', '請匯出完整本地觀察包；此處顯示前150項'])
                break
            if isinstance(item, (dict, list)):
                child = QTreeWidgetItem(parent, [str(key), ''])
                if str(key) in ('ink_bounds', 'container_bounds', 'baseline', 'distribution', 'alignment'):
                    child.setData(0, Qt.ItemDataRole.UserRole, ('metric', str(key)))
                self._add_data(child, item, depth + 1)
            else:
                text = '未知' if item is None else str(item)
                QTreeWidgetItem(parent, [str(key), text[:1000] + ('…（完整內容在觀察包）' if len(text) > 1000 else '')])

    def _filter_overview(self, text):
        text = text.casefold()
        def visit(item):
            own = text in (item.text(0) + ' ' + item.text(1)).casefold()
            found = [visit(item.child(i)) for i in range(item.childCount())]
            match = own or any(found)
            item.setHidden(not match)
            if text and match:
                item.setExpanded(True)
            return match
        for i in range(self.overview_tree.topLevelItemCount()):
            visit(self.overview_tree.topLevelItem(i))

    def _overview_selected(self, item, column):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or not self.current_work_id:
            return
        work = self.store.get_work(self.current_work_id)
        field = self.store.get_field(self.current_work_id, self.current_field_id) if self.current_field_id else None
        if data[0] == 'metric' and field:
            self.canvas.show_measurement(data[1], field)
        elif data[0] == 'relation':
            relation = data[1]
            self._selected_relation_id = relation.get('id') if any(r.get('id') == relation.get('id') for r in work.get('relations', [])) else None
            self.remove_relation_button.setVisible(bool(self._selected_relation_id))
            ids = relation.get('field_ids', [])
            first = next((f for f in work.get('fields', []) if f['id'] in ids), field)
            if first:
                self.canvas.show_measurement(relation, first)

    def remove_selected_relation(self):
        if self.current_work_id and self._selected_relation_id:
            self.store.remove_relation(self.current_work_id, self._selected_relation_id)
            self.canvas.clear_measurement()
            self._populate_overview()
            self._update_save_state()

    def locate_current(self):
        if self.current_field_id:
            self.canvas.locate_field(self.current_field_id)

    def zoom_current(self):
        self.locate_current()
        self.canvas.zoom(1.8)

    def compare_font(self):
        if not self.current_work_id or not self.current_field_id:
            return
        from .font_dialog import FontReviewDialog
        self.commit_field()
        work = self.store.get_work(self.current_work_id)
        field = self.store.get_field(self.current_work_id, self.current_field_id)
        page = self._page(self.store.get_source(self.current_source_id), work)
        dialog = FontReviewDialog(page, work, field, self)
        if dialog.exec():
            annotation = dialog.annotation()
            if annotation:
                self.store.annotate_font(self.current_work_id, self.current_field_id, annotation)
                self._update_save_state()
                self.notify('已另存人工字型核對。原稿字級與字寬仍依各自證據，不會由候選預覽補成真值。')

    def save_progress(self):
        self.commit_field()
        self.save_state.setText('正在保存，請稍候…')
        try:
            result = self.store.save()
        except (OSError, ValueError) as error:
            self.notify('尚未保存成功。請確認本機資料夾可寫入，保留此視窗後重試。')
            self._update_save_state()
            return False
        self._set_step(3)
        self._update_save_state()
        self.notify('已保存於本機。保存不等於核對完成，私人資料不會上傳。')
        return result

    def _update_save_state(self):
        dirty = self._editor_dirty or self.store.dirty
        saved = self.store.saved_utc
        self.save_state.setText('尚有修改未保存' if dirty else ('已保存於本機' + (f' · {saved}' if saved else '')))
        if not self.store.sources() and not saved:
            self.save_state.setText('尚未加入檔案 · 作品與資料只在本機處理')
        self.save_button.setVisible(bool(self.store.sources()))
        self.complete_button.setVisible(bool(self.store.works()))
        self.right_panel.setVisible(bool(self.current_work_id))
        self.complete_button.setEnabled(bool(self.current_work_id))
        self.overview_button.setEnabled(bool(self.current_work_id))

    def complete_current_work(self):
        self.commit_field()
        if not self.current_work_id:
            return
        result = self.store.complete_work(self.current_work_id)
        if result['status'] == 'INCOMPLETE':
            self.notify(f'仍有 {result["unchecked"]} 項尚未核對。可以逐項查看或保存進度後離開，不會自動勾選。')
            self.next_pending()
            return result
        if not self.save_progress():
            return result
        self._refresh_tree()
        self.notify('這份作品已核對，仍有待查項目。可繼續下一份。' if result['status'] == 'REVIEWED_WITH_UNKNOWNS' else '這份作品已核對。這不代表模型訓練或模板產出完成。')
        return result

    def export_report(self, path=None):
        if isinstance(path, bool):
            path = None
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, '匯出安全問題報告', 'TemplateAIReview-report.json', 'JSON (*.json)')
        if not path:
            return
        report = self.store.safe_report()
        try:
            Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        except OSError:
            self.notify('問題報告尚未保存。請改選可寫入的本機資料夾，原工作保持不變。')
            return None
        self.notify('已匯出安全問題報告。原稿、文字、字型與私人路徑未包含；請自行檢查後手動分享。')
        return report

    def export_observations(self):
        self.commit_field()
        path, _ = QFileDialog.getSaveFileName(self, '完整觀察資料只保存在本機，包含私人內容', 'review-observations.local.json', 'JSON (*.json)')
        if path:
            try:
                self.store.export_observation_package(path)
                self.notify('完整觀察資料已保存於本機，包含私人內容，請勿當作安全問題報告分享。')
            except (OSError, ValueError):
                self.notify('觀察資料尚未匯出。請選擇可寫入的本機位置，原工作仍保留。')

    def open_data_dir(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.root.resolve())))

    def closeEvent(self, event):
        if self._allow_close:
            event.accept()
            return
        self.commit_field()
        if self.store.dirty or self.jobs.is_running():
            box = QMessageBox(self)
            box.setWindowTitle('離開前保存工作')
            box.setText('保存後離開會保留已完成結果；正在處理的檔案可能需要重試。')
            save = box.addButton('保存後離開', QMessageBox.ButtonRole.AcceptRole)
            back = box.addButton('返回繼續工作', QMessageBox.ButtonRole.RejectRole)
            discard = box.addButton('放棄未保存修改', QMessageBox.ButtonRole.DestructiveRole)
            box.setDefaultButton(save)
            box.exec()
            if box.clickedButton() == back:
                event.ignore()
                return
            self._discarding = box.clickedButton() == discard
            self.jobs.stop()
            if box.clickedButton() == save and not self.save_progress():
                event.ignore()
                return
            if box.clickedButton() not in (save, discard):
                event.ignore()
                return
        self._allow_close = True
        event.accept()

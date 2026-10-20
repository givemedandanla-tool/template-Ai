"""Task-oriented desktop shell; existing widgets and DesignSessions own the data."""
from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea,
    QSplitter, QStackedWidget, QVBoxLayout, QWidget, QGroupBox, QSizePolicy, QLayout,
    QComboBox,
)
from PySide6.QtCore import QSignalBlocker


STYLE = """QMainWindow, QDialog { background: #f5f7fb; }
QWidget { color: #17243b; font-size: 13px; }
QLabel { background: transparent; }
QLabel#workspaceTitle { font-size: 23px; font-weight: 700; }
QLabel#workspaceHint, QLabel#offlineBadge { color: #46566e; }
QWidget#workspaceRail { background: #ffffff; border-right: 1px solid #dce3ed; }
QPushButton { background: #ffffff; padding: 8px 12px; border: 1px solid #c4cedd; border-radius: 7px; min-height: 20px; }
QPushButton:hover { background: #edf3ff; border-color: #2864c7; }
QPushButton:focus { border: 2px solid #205ac0; }
QPushButton:checked { background: #e8f0ff; border-color: #3368bd; color: #154a9b; font-weight: 600; }
QPushButton#workspacePrimary { background: #2359ae; color: #ffffff; border-color: #2359ae; font-weight: 600; }
QPushButton#workspacePrimary:hover { background: #19498f; }
QPushButton:disabled { color: #69788b; background: #edf0f5; border-color: #d3dbe6; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit { background: #ffffff; border: 1px solid #bac6d7; border-radius: 5px; padding: 5px; selection-background-color: #2359ae; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QPlainTextEdit:focus { border: 2px solid #2359ae; }
QGroupBox { background: #ffffff; border: 1px solid #d7dfeb; border-radius: 8px; margin-top: 12px; padding: 14px 8px 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
QTabWidget::pane { border: 0; }
QTabBar::tab { padding: 9px 12px; background: #edf1f7; }
QTabBar::tab:selected { background: #ffffff; color: #164d99; }
QListWidget, QTableWidget, QTreeWidget, QGraphicsView { background: #ffffff; border: 1px solid #d7dfeb; border-radius: 6px; }
QHeaderView::section { background: #edf1f7; padding: 5px; border: 0; }
QStatusBar { background: #ffffff; color: #46566e; }
QSplitter::handle { background: #e4eaf3; }
"""


def label(text, name=""):
    result = QLabel(text)
    result.setWordWrap(True)
    result.setTextFormat(Qt.PlainText)
    if name:
        result.setObjectName(name)
    return result


def button(text, action, name=""):
    result = QPushButton(text)
    result.setAccessibleName(text)
    if name:
        result.setObjectName(name)
    result.clicked.connect(action)
    return result


def disclosure(title, widget):
    group = QGroupBox(title)
    group.setCheckable(True)
    layout = QVBoxLayout(group)
    layout.addWidget(widget)
    group.toggled.connect(widget.setVisible)
    group.setChecked(False)
    return group


class DesktopWorkspace(QObject):
    """Navigation and view composition only; never writes layout/model records."""

    TITLES = ("匯入與學習", "模板與圖片", "製作稿件")
    HINTS = (
        "匯入作品，核對文字與來源，再學習可共用的版面規則。",
        "尋找、整理與編輯模板；需要時再開啟專業工具。",
        "填寫資料 → 產生完整稿件 → 調整位置 → 確認與儲存。",
    )

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.editor = None
        self._editor_generation = None
        self._last_state = None
        self._editor_pin = None
        self._tools_dialog = None
        self.legacy_root = window.takeCentralWidget()
        self.legacy_root.setParent(window)
        self.legacy_root.hide()
        self.legacy_rail = window.function_rail
        self._build_shell()
        self._build_production()
        self._build_learning()
        self._group_menus()
        window.setStyleSheet(STYLE)
        window.tabs.currentChanged.connect(self.mode_changed)
        window.inputs_invalidated.connect(self.invalidate_view)
        self.timer = QTimer(self)
        self.timer.setInterval(300)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.mode_changed(window.tabs.currentIndex())

    def _build_shell(self):
        w = self.window
        root = QWidget()
        root.setObjectName("desktopWorkspace")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 10, 14, 8)
        heading = QHBoxLayout()
        title_area = QVBoxLayout()
        self.title = label("", "workspaceTitle")
        self.hint = label("", "workspaceHint")
        title_area.addWidget(self.title)
        title_area.addWidget(self.hint)
        heading.addLayout(title_area, 1)
        heading.addWidget(label("本機作業 · 手動匯出報告", "offlineBadge"))
        self.professional = button("顯示編輯工具", self.toggle_properties)
        heading.addWidget(self.professional)
        outer.addLayout(heading)
        context = QHBoxLayout()
        context.addWidget(w.work_context, 1)
        context.addWidget(w.return_work_button)
        outer.addLayout(context)
        rail = QWidget()
        rail.setObjectName("workspaceRail")
        rail.setMinimumWidth(160)
        rail.setMaximumWidth(200)
        nav = QVBoxLayout(rail)
        nav.setContentsMargins(8, 14, 8, 14)
        nav.addWidget(label("Template AI"))
        self.nav_buttons = {}
        # Retain the established accessible action name for existing automation.
        for index, text in ((2, "排版與輸出"), (0, "匯入與學習"), (1, "模板與圖片")):
            control = button(text, lambda checked=False, i=index: w.navigate_mode(i), f"workspaceNav{index}")
            control.setCheckable(True)
            self.nav_buttons[index] = control
            nav.addWidget(control)
        nav.addSpacing(14)
        self.guidance_button = button("工作引導", self.open_guidance, "workspaceGuidance")
        self.support_button = button("問題與報告", self.open_support, "workspaceSupport")
        nav.addWidget(self.guidance_button)
        nav.addWidget(self.support_button)
        nav.addWidget(button("更多工具", self.open_tools, "workspaceTools"))
        nav.addStretch()
        nav.addWidget(button("備份與還原", w.backup_center))
        nav.addWidget(button("電腦負載與暫停", w.runtime_center))
        old = w.workspace_splitter.replaceWidget(0, rail)
        old.hide()
        old.setParent(self.legacy_root)
        w.function_rail = rail
        w.tabs.tabBar().hide()
        w.workspace_splitter.setSizes([170, 1000, 280])
        outer.addWidget(w.workspace_splitter, 1)
        self.footer_host = QVBoxLayout()
        self.footer_host.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self.footer_host)
        w.setCentralWidget(root)
        self.root = root

    def _build_production(self):
        w = self.window
        self.old_output = w.output_page_scroll.takeWidget()
        self.old_output.setParent(self.legacy_root)
        self.old_output.hide()
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(2, 2, 2, 2)
        dimensions = QHBoxLayout()
        dimensions.addWidget(label("成品尺寸"))
        w.out_w.setAccessibleName("成品寬度，毫米")
        w.out_h.setAccessibleName("成品高度，毫米")
        dimensions.addWidget(w.out_w)
        dimensions.addWidget(label("×"))
        dimensions.addWidget(w.out_h)
        dimensions.addStretch()
        dimensions.addWidget(button("接續已保存稿件", self.resume_saved))
        dimensions.addWidget(button("更多製作工具", self.open_output_tools))
        layout.addLayout(dimensions)
        self.state = label("填好資料後，就能產生稿件。", "workspaceState")
        self.state.setAccessibleName("目前製作狀態與下一步")
        layout.addWidget(self.state)
        split = QSplitter()
        data = QWidget()
        data.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        data_layout = QVBoxLayout(data)
        data_layout.setSizeConstraint(QLayout.SetNoConstraint)
        data_layout.setContentsMargins(4, 4, 8, 4)
        data_layout.addWidget(label("1  填寫資料"))
        w.graph_button.setText("填寫人物與公司資料")
        w.graph_button.setAccessibleName("填寫人物與公司資料")
        data_layout.addWidget(w.graph_button)
        data_layout.addWidget(w.graph_status)
        data_layout.addWidget(w.input_state)
        w.graph_status.setWordWrap(True)
        w.input_state.setWordWrap(True)
        for control in (w.graph_status, w.input_state):
            control.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        data_layout.addWidget(button("找舊客戶／重訂", w.customer_center))
        data_layout.addWidget(button("管理公司圖片", w.logo_center))
        w.legacy_input_panel.setTitle("使用表格輸入（熟手工具）")
        data_layout.addWidget(w.legacy_input_panel)
        self.other_fixed = disclosure("查看其他固定版面", w.candidate_scroll)
        w.candidate_scroll.setMinimumWidth(0)
        self.other_fixed.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        w.legacy_input_panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        data_layout.addWidget(self.other_fixed)
        data_layout.addWidget(button("查看這份稿件的問題", self.open_current_report))
        data_layout.addStretch()
        self.data_layout = data_layout
        for control in data.findChildren(QPushButton):
            control.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        data_scroll = QScrollArea()
        data_scroll.setWidgetResizable(True)
        data_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        data_scroll.setMinimumWidth(210)
        data_scroll.setWidget(data)
        split.addWidget(data_scroll)
        preview = QWidget()
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(4, 4, 4, 4)
        preview_layout.addWidget(label("2  檢查與調整"))
        self.preview_stack = QStackedWidget()
        self.preview_stack.addWidget(w.output_canvas)
        preview_layout.addWidget(self.preview_stack, 1)
        self.preview_hint = label("完整稿件會顯示在這裡。填好資料後，按下方的「產生稿件」。")
        preview_layout.addWidget(self.preview_hint)
        self.learned_controls = QWidget()
        self.learned_controls_layout = QVBoxLayout(self.learned_controls)
        self.learned_controls_layout.setContentsMargins(0, 0, 0, 0)
        self.learned_controls.hide()
        preview_layout.addWidget(self.learned_controls)
        self.issue_summary = w.issues
        preview_layout.addWidget(self.issue_summary)
        split.addWidget(preview)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([250, 750])
        layout.addWidget(split, 1)
        self.production_footer = QWidget()
        footer = QHBoxLayout(self.production_footer)
        footer.setContentsMargins(0, 2, 0, 0)
        self.primary = button("產生稿件", self.primary_action, "workspacePrimary")
        self.primary.setMinimumWidth(150)
        footer.addWidget(self.primary)
        footer.addWidget(button("修改位置", self.adjust_positions))
        self.update_button = button("重新排版", self.generate)
        footer.addWidget(self.update_button)
        footer.addStretch()
        # Keep the existing export commands and their gate/version checks.
        w.preview_button.setText("另存預覽稿")
        w.export_button.setText("正式輸出")
        footer.addWidget(w.preview_button)
        footer.addWidget(w.export_button)
        self.footer_host.addWidget(self.production_footer)
        w.output_page_scroll.setWidget(page)
        self.production_page = page

    def _group_menus(self):
        bar = self.window.menuBar()
        actions = list(bar.actions())
        for action in actions:
            # clear() deletes menu-owned actions; preserve every old command.
            action.setParent(self.window)
            bar.removeAction(action)
        groups = {name: bar.addMenu(name) for name in ("編輯", "作品與模板", "資料與備份", "檢查與報告", "設定")}
        for action in actions:
            text = action.text()
            if any(word in text for word in ("報告", "診斷", "檢查")):
                target = "檢查與報告"
            elif any(word in text for word in ("備份", "客戶", "還原")):
                target = "資料與備份"
            elif any(word in text for word in ("復原", "重做", "對齊")):
                target = "編輯"
            elif any(word in text for word in ("設定", "字型", "負載")):
                target = "設定"
            else:
                target = "作品與模板"
            groups[target].addAction(action)
        help_menu = bar.addMenu("使用說明")
        help_menu.addAction("工作引導", self.open_guidance)
        help_menu.addAction("離線問題與報告", self.open_support)
        self.menu_groups = groups

    def _build_learning(self):
        w = self.window
        index = w.tabs.currentIndex()
        blocker = QSignalBlocker(w.tabs)
        self.old_training = w.tabs.widget(0)
        self.old_training.setParent(self.legacy_root)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(label("先匯入作品，再核對分析結果；資料充足時才學習與啟用規則。"))
        row = QHBoxLayout()
        w.import_button.setText("匯入作品")
        row.addWidget(w.import_button)
        row.addWidget(button("自動分析作品", w.automatic_training))
        row.addWidget(button("核對與學習引導", self.open_guidance))
        row.addStretch()
        row.addWidget(button("更多原稿工具", lambda: self._open_widget(self.old_training, "原稿標記與來源工具")))
        layout.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(label("來源檔案"))
        w.source_combo.setAccessibleName("選擇來源檔案")
        row.addWidget(w.source_combo, 1)
        row.addWidget(w.source_previous)
        row.addWidget(w.source_next)
        layout.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(label("這份檔案中的作品"))
        w.work_combo.setAccessibleName("選擇檔案中的作品")
        row.addWidget(w.work_combo, 1)
        row.addWidget(w.page)
        layout.addLayout(row)
        layout.addWidget(w.source_info)
        split = QSplitter()
        split.addWidget(w.train_canvas)
        split.addWidget(w.slot_list)
        split.setStretchFactor(0, 1)
        split.setSizes([800, 170])
        layout.addWidget(split, 1)
        view = QHBoxLayout()
        view.addWidget(button("完整顯示", w.train_canvas.fit))
        view.addWidget(button("放大", lambda: w.train_canvas.set_zoom(w.train_canvas.transform().m11() * 1.25)))
        view.addWidget(button("縮小", lambda: w.train_canvas.set_zoom(w.train_canvas.transform().m11() / 1.25)))
        view.addStretch()
        view.addWidget(button("顯示／收合欄位清單", lambda: w.slot_list.setVisible(not w.slot_list.isVisible())))
        layout.addLayout(view)
        layout.addWidget(w.visual)
        footer = QHBoxLayout()
        footer.addWidget(button("比對參考圖", w.compare_reference))
        footer.addWidget(button("保存核對進度", w.save_labels))
        footer.addStretch()
        layout.addLayout(footer)
        # setParent removed the old tab; preserve the established 0/1/2 contract.
        w.tabs.insertTab(0, page, "匯入與學習")
        w.tabs.setCurrentIndex(index)
        del blocker
        w.slot_list.hide()
        self.learning_page = page

    def mode_changed(self, index):
        self.title.setText(self.TITLES[index])
        self.hint.setText(self.HINTS[index])
        for current, control in self.nav_buttons.items():
            control.setChecked(current == index)
        self.window.property_panel.setVisible(False)
        self.production_footer.setVisible(index == 2)
        self.professional.setText("顯示編輯工具")
        self.refresh()

    def toggle_properties(self):
        panel = self.window.property_panel
        panel.setVisible(not panel.isVisible())
        self.professional.setText("收合編輯工具" if panel.isVisible() else "顯示編輯工具")

    def open_tools(self):
        self._open_widget(self.legacy_rail, "更多工作工具")

    def open_output_tools(self):
        self._open_widget(self.old_output, "更多製作工具")

    def _open_widget(self, widget, title):
        dialog = QDialog(self.window)
        dialog.setWindowTitle(title)
        dialog.resize(820, 650)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label("這些工具沿用目前的資料與規則。需要時再使用，不會自動改動稿件。"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        widget.show()
        layout.addWidget(scroll)
        layout.addWidget(button("返回工作", dialog.accept))
        try:
            dialog.exec()
        finally:
            scroll.takeWidget()
            widget.setParent(self.legacy_root)
            widget.hide()
            dialog.deleteLater()

    def open_guidance(self):
        from .guided_operations import GuidedOperationsDialog
        dialog = GuidedOperationsDialog(self.window)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    def open_support(self):
        from .offline_support_dialog import install_offline_support
        install_offline_support(self.window).open_dialog()

    def open_current_report(self):
        if self.editor is not None and self._editor_is_current():
            self.editor.details_group.setChecked(True)
            self._open_widget(self.editor.result_details, "這份稿件的詳細原因")
        else:
            self.window.diagnostic_report("candidate")

    def ensure_editor(self):
        from .production_bridge import attach
        editor = self._make_editor()
        if editor.solve_worker is not None and editor.solve_worker.isRunning():
            raise ValueError("目前正在排版，請先停止這次排版，再變更稿件。")
        attach(editor)
        self._editor_pin = self._session_pin()
        self._editor_generation = self.window.generation
        self.preview_stack.setCurrentWidget(editor.canvas)
        self.learned_controls.show()
        self.refresh()
        return editor

    def _make_editor(self):
        from .design_learning_dialog import DesignLearningDialog
        if self.editor is None:
            self.editor = DesignLearningDialog(self.window)
            self.editor.hide()
            self.preview_stack.addWidget(self.editor.canvas)
            self._compose_editor_controls()
        return self.editor

    def _compose_editor_controls(self):
        editor = self.editor
        row = QHBoxLayout()
        row.addWidget(editor.undo_button)
        row.addWidget(editor.redo_button)
        row.addStretch()
        self.learned_controls_layout.addLayout(row)
        alternatives = QWidget()
        inner = QVBoxLayout(alternatives)
        for text, control in (("要移動的資料", editor.subject), ("相對位置", editor.relation), ("參考資料", editor.reference)):
            inner.addWidget(label(text))
            control.setAccessibleName(text)
            inner.addWidget(control)
        inner.addWidget(button("調整兩欄相對位置", lambda: editor.attempt(lambda: editor.set_relation(editor.subject.currentData(), editor.relation.currentData(), editor.reference.currentData(), background=True))))
        self.position_choices = disclosure("用選單調整位置", alternatives)
        self.learned_controls_layout.addWidget(self.position_choices)
        self.learned_controls_layout.addWidget(editor.capacity_summary)
        more = QWidget()
        more_layout = QVBoxLayout(more)
        more_layout.addWidget(label("其他版面"))
        more_layout.addWidget(editor.candidate_choices)
        more_layout.addWidget(button("查看選取版面", lambda: editor.attempt(editor.choose_candidate)))
        editor.switch_button.setText("採用這次更換的版面")
        more_layout.addWidget(editor.switch_button)
        more_layout.addWidget(label("正式稿須通過來源、字型與模型資格檢查；預覽確認不會取代這些檢查。"))
        more_layout.addWidget(editor.formal_button)
        more_layout.addWidget(editor.formal_export_button)
        more_layout.addWidget(label("沿用已保存的相同檔案"))
        more_layout.addWidget(editor.artifacts)
        more_layout.addWidget(button("開啟已保存檔案", lambda: editor.attempt(editor.replay)))
        self.learned_more = disclosure("更多稿件選項", more)
        self.data_layout.insertWidget(self.data_layout.count() - 1, self.learned_more)

    def _editor_is_current(self):
        w = self.window
        basic = bool(self.editor is not None and self.editor.session_id
                    and self.editor.session_id == getattr(w, "production_session_id", None)
                    and getattr(w, "production_generation", None) == w.generation
                    and getattr(w, "production_view", None) == "LEARNED")
        if not basic:
            return False
        from .production_bridge import current_graph
        from .training_store import digest
        try:
            row = self.editor.sessions.current(self.editor.session_id)
            return bool(row and digest(current_graph(w).data) == digest(row["input_graph"])
                        and (w.out_w.value(), w.out_h.value()) == (row["width_mm"], row["height_mm"]))
        except (ValueError, OSError, TypeError):
            return False

    def _session_pin(self):
        if self.editor is None or not self.editor.session_id:
            return None
        row = self.editor.sessions.current(self.editor.session_id)
        return (row["id"], row["revision"]) if row else None

    def _switch_pending(self):
        if not self._editor_is_current():
            return False
        try:
            row, result, candidate = self.editor.sessions.checked_result(self.editor.session_id)
            review = row.get("family_switch_review", {})
            return bool(result.get("family_switch_requires_review") and
                        (review.get("result_id") != result["id"] or review.get("content_digest") != result["content_digest"]))
        except ValueError:
            return False

    def invalidate_view(self, *args):
        self._last_state = None
        # The existing bridge invalidates its confirmed version. Never display
        # an embedded old candidate as if it represented the new input.
        if self.editor is not None:
            self.preview_stack.setCurrentWidget(self.window.output_canvas)
            self.learned_controls.hide()
        self.refresh()

    def generate(self):
        from .production_bridge import routes_to_learning
        try:
            if routes_to_learning(self.window):
                editor = self.ensure_editor()
                editor.attempt(editor.solve_async)
            else:
                self.preview_stack.setCurrentWidget(self.window.output_canvas)
                self.learned_controls.hide()
                self.window.generate()
        except (ValueError, TypeError, OSError) as error:
            self.show_error(error)
        self.refresh()

    def primary_action(self):
        self.refresh()
        editor = self.editor
        if editor is not None and editor.solve_worker is not None and editor.solve_worker.isRunning():
            editor.cancel_solve()
        elif self._switch_pending():
            editor.attempt(editor.review_switch)
            editor.refresh_draft()
        elif self._editor_is_current() and editor.export_button.isEnabled():
            editor.attempt(editor.export_preview)
        elif self._editor_is_current() and editor.confirm_button.isEnabled():
            editor.attempt(editor.confirm_preview)
        elif self.window.preview_button.isEnabled() and not self._editor_is_current():
            self.window.export_current(True)
        else:
            self.generate()
        self.refresh()

    def adjust_positions(self):
        from .production_bridge import routes_to_learning
        try:
            if routes_to_learning(self.window):
                editor = self.ensure_editor()
                if not editor.confirm_button.isEnabled():
                    self.state.setText("請先產生稿件，再拖動資料或使用位置選單。")
                else:
                    editor.canvas.setFocus()
                    self.preview_hint.setText("拖動聯絡資料改變相對位置；也可展開下方的位置選單。")
            else:
                self.window.open_production()
        except (ValueError, TypeError, OSError) as error:
            self.show_error(error)

    def resume_saved(self):
        if self.window.busy:
            self.state.setText("目前正在處理，請先停止或等待完成，再接續其他稿件。")
            return
        editor = self._make_editor()
        editor.refresh()
        dialog = QDialog(self.window)
        dialog.setWindowTitle("接續已保存稿件")
        dialog.resize(520, 230)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label("選擇先前保存的稿件。接續後會帶回那份資料、尺寸與排版決定。"))
        choices = QComboBox()
        choices.setObjectName("resumeDraftChoice")
        choices.setAccessibleName("選擇已保存稿件")
        for index in range(editor.session_choices.count()):
            choices.addItem(editor.session_choices.itemText(index), editor.session_choices.itemData(index))
        layout.addWidget(choices)
        status = label("" if choices.count() else "目前沒有已保存稿件，請先填資料並產生稿件。")
        layout.addWidget(status)
        accept = button("接續這份稿件", dialog.accept, "resumeDraftAccept")
        accept.setEnabled(choices.count() > 0)
        layout.addWidget(accept)
        layout.addWidget(button("返回工作", dialog.reject))
        try:
            if dialog.exec() == QDialog.Accepted:
                identity = choices.currentData()
                editor.session_choices.setCurrentIndex(editor.session_choices.findData(identity))
                editor.bound_to_main = True
                editor.attempt(editor.resume_session)
                self._editor_pin = self._session_pin()
                self.refresh()
        finally:
            dialog.deleteLater()

    def show_error(self, error):
        from .production_report import explain_error
        report = explain_error(error)
        self.state.setText(report["summary"] + " " + report["next_step"])
        support = getattr(self.window, "offline_support", None)
        if support:
            support.record("LAYOUT", "ACTION_FAILED", error=error)

    def refresh(self):
        w = self.window
        if w.library.closed:
            self.timer.stop()
            return
        w.candidate_scroll.setVisible(self.other_fixed.isChecked() and not self._editor_is_current())
        editor = self.editor
        current = self._editor_is_current()
        if current and not (editor.solve_worker and editor.solve_worker.isRunning()):
            pin = self._session_pin()
            if self._editor_pin != pin:
                editor.refresh_draft()
                self._editor_pin = self._session_pin()
        if not current:
            self.preview_stack.setCurrentWidget(w.output_canvas)
            self.learned_controls.hide()
            self.preview_hint.setText("檢查完整稿件；更正內容後請重新排版，位置調整請按下方「修改位置」。")
        if hasattr(self, 'learned_more'):
            self.learned_more.setVisible(current)
        if editor is not None and editor.solve_worker is not None and editor.solve_worker.isRunning():
            key = ("running", editor.solve_status.text())
            text, action = editor.solve_status.text(), "停止這次排版"
        elif self._editor_is_current():
            key = ("learned", editor.solve_status.text(), editor.confirm_button.isEnabled(), editor.export_button.isEnabled())
            text = editor.solve_status.text()
            action = "儲存預覽稿" if editor.export_button.isEnabled() else "確認這份預覽稿" if editor.confirm_button.isEnabled() else "產生稿件"
            if self._switch_pending():
                action = "採用這個新版本面"
                text = "這次需要更換版面，請先檢查預覽，再決定是否採用。"
            self.preview_stack.setCurrentWidget(editor.canvas)
            self.learned_controls.show()
            self.preview_hint.setText("這是學習規則產生的預覽稿。可拖動聯絡資料；正式輸出另須通過檢查。")
        elif w.busy:
            key = ("busy",)
            text, action = "正在產生稿件；資料已保留，可從排版進度停止或接續。", "正在處理"
        else:
            key = ("fixed", w.generation, w.preview_button.isEnabled())
            text = "可以檢查這份稿件；需要時修改資料或調整位置。" if w.preview_button.isEnabled() else "填好資料後產生稿件；修改內容後請重新排版。"
            action = "另存這份預覽稿" if w.preview_button.isEnabled() else "產生稿件"
        if self._last_state != key:
            self._last_state = key
            self.state.setText(text)
            self.primary.setText(action)
            self.primary.setAccessibleName(action)
        running = bool(editor and editor.solve_worker and editor.solve_worker.isRunning())
        self.primary.setEnabled(running or not w.busy)
        self.update_button.setEnabled(not w.busy and not (editor and editor.solve_worker and editor.solve_worker.isRunning()))
        self.update_button.setVisible(bool(w.preview_button.isEnabled() or current))

    def can_close(self):
        if self.editor is not None:
            for name in ("worker", "solve_worker"):
                worker = getattr(self.editor, name, None)
                if worker is not None and worker.isRunning():
                    worker.cancel.set()
                    self.state.setText("正在停止目前工作；資料已保留，完成後可關閉。")
                    return False
        return True


def install_desktop_workspace(window):
    workspace = DesktopWorkspace(window)
    window.desktop_workspace = workspace
    return workspace

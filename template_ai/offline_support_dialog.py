"""Beginner-facing local support, with optional technical detail and manual export."""
from __future__ import annotations

from pathlib import Path
import time

from PySide6.QtCore import QObject, QTimer, Signal, Qt
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog, QHBoxLayout,
                              QLabel, QPlainTextEdit, QPushButton, QTextBrowser,
                              QVBoxLayout, QWidget)

from .diagnostic_bundle import encoded
from .offline_runtime import assert_local_path
from .offline_support import (MAX_BYTES, MISSING, OfflineJournal, build_support_bundle, missing_from_hint,
                              read_support_bundle, report_html, save_support_bundle)


STAGE_LABELS = [('APPLICATION', '軟體啟動與操作'), ('IMPORT', '匯入作品'),
                ('LEARNING', '學習作品規則'), ('TEMPLATES', '整理與編輯模板'),
                ('INPUT', '填寫或修改資料'), ('LAYOUT', '排版與位置調整'), ('OUTPUT', '確認與輸出')]


class OfflineSupportPanel(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.setObjectName('offlineSupportPanel')
        self.controller = controller
        self.raw = None
        self.data = None
        self.historical = False
        layout = QVBoxLayout(self)
        title = QLabel('遇到問題，保存報告再交給 Codex')
        title.setObjectName('workspaceTitle')
        title.setWordWrap(True)
        layout.addWidget(title)
        explanation = QLabel('使用期間不會上傳資料。報告只保留操作階段、錯誤類型、版本和量測；不包含客戶原文、原稿、字型檔或資料庫。你決定何時把匯出的 ZIP 附到 Codex 對話。')
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        row = QHBoxLayout()
        self.stage = QComboBox()
        self.stage.setAccessibleName('遇到問題的工作階段')
        for key, label in STAGE_LABELS:
            self.stage.addItem(label, key)
        row.addWidget(QLabel('當時在做什麼'))
        row.addWidget(self.stage, 1)
        self.missing = QComboBox()
        self.missing.setAccessibleName('畫面提示缺少的資訊')
        for key, label in MISSING.items():
            self.missing.addItem('不確定缺少什麼' if key in ('NONE',) else label, key)
        row.addWidget(self.missing, 1)
        self.mark_button = QPushButton('記下這個問題')
        self.mark_button.clicked.connect(self.mark_problem)
        row.addWidget(self.mark_button)
        layout.addLayout(row)
        self.overview = QTextBrowser()
        self.overview.setOpenLinks(False)
        self.overview.setOpenExternalLinks(False)
        self.overview.setAccessibleName('白話問題報告與技術內容')
        layout.addWidget(self.overview, 1)
        self.details_button = QPushButton('顯示技術資料')
        self.details_button.setCheckable(True)
        self.details_button.toggled.connect(self.show_details)
        layout.addWidget(self.details_button)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setAccessibleName('報告完整 JSON')
        self.details.setMaximumHeight(210)
        self.details.hide()
        layout.addWidget(self.details)
        self.status = QLabel('紀錄只保存在這台電腦。')
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        self.status.setAccessibleName('問題報告保存狀態')
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        self.refresh_button = QPushButton('更新目前報告')
        self.refresh_button.clicked.connect(self.refresh)
        actions.addWidget(self.refresh_button)
        self.open_button = QPushButton('開啟以前的報告')
        self.open_button.clicked.connect(self.open_saved)
        actions.addWidget(self.open_button)
        actions.addStretch()
        self.export_button = QPushButton('匯出問題報告')
        self.export_button.setObjectName('primaryAction')
        self.export_button.clicked.connect(self.export)
        actions.addWidget(self.export_button)
        layout.addLayout(actions)
        self.refresh()

    def show_details(self, visible):
        self.details.setVisible(visible)
        self.details_button.setText('收起技術資料' if visible else '顯示技術資料')

    def display(self):
        self.overview.setHtml(report_html(self.data).decode())
        self.details.setPlainText(encoded(self.data).decode())
        self.export_button.setEnabled(self.raw is not None)

    def refresh(self):
        self.controller.flush()
        self.historical = False
        self.data = self.controller.journal.report()
        self.raw = build_support_bundle(self.data)
        self.display()
        self.status.setText('這是目前可手動匯出的實際內容。' + ('' if self.data['journal_persisted'] else ' 本機紀錄尚未寫入磁碟；請立即匯出，避免關閉後失去紀錄。'))

    def mark_problem(self):
        self.controller.flush()
        self.controller.record(self.stage.currentData(), 'USER_REPORTED_PROBLEM',
                               missing=self.missing.currentData())
        self.refresh()
        self.status.setText('已記下階段與缺少資訊；沒有記錄私人內容。匯出後，可在 Codex 另外描述你想完成的工作。')

    def export(self):
        if self.raw is None:
            return
        name = 'TEMPLATE_AI_SUPPORT_' + self.data['created_utc'][:10] + '_' + self.data['report_id'][:8] + '.zip'
        path, _ = QFileDialog.getSaveFileName(self, '保存問題報告到本機', name, '問題報告 (*.zip)')
        if not path:
            self.status.setText('已取消匯出，紀錄仍保留在本機。')
            return
        try:
            save_support_bundle(path, self.raw)
            self.controller.record('SUPPORT', 'REPORT_EXPORTED')
            self.status.setText('已完整保存 ZIP。請自行把這個檔案附到 Codex 對話；軟體沒有傳送任何資料。')
        except Exception as error:
            self.controller.record('SUPPORT', 'REPORT_SAVE_FAILED', error=error)
            self.status.setText('報告尚未保存。請選可寫入的本機資料夾與新的 ZIP 檔名，再試一次；目前報告仍在。')

    def open_saved(self):
        path, _ = QFileDialog.getOpenFileName(self, '開啟本機問題報告', '', '問題報告 (*.zip)')
        if not path:
            self.status.setText('已取消開啟，原有報告仍保留。')
            return
        try:
            assert_local_path(path)
            source = Path(path)
            if not source.is_file() or source.stat().st_size > MAX_BYTES + 65536:
                raise ValueError('報告大小不合法')
            raw = source.read_bytes()
            data = read_support_bundle(raw)
            # Untrusted supplied HTML is never rendered; regenerate from the
            # validated data, just like the existing diagnostic report reader.
            self.data, self.raw, self.historical = data, raw, True
            self.display()
            self.status.setText('已開啟歷史報告。這不是目前稿件的檢查，也不會改動工作內容。')
        except Exception as error:
            self.controller.record('SUPPORT', 'ACTION_FAILED', error=error)
            self.status.setText('無法驗證這份報告；原有報告仍保留。請重新選擇由軟體完整匯出的 ZIP。')


class OfflineSupportController(QObject):
    problem = Signal()

    def __init__(self, window, journal=None):
        super().__init__(window)
        self.window = window
        self.journal = journal or OfflineJournal(window.library.root)
        self.stage = 'APPLICATION'
        self.pending = set()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(350)
        self.timer.timeout.connect(self.flush)
        self.last_activity = time.monotonic()
        self.problem.connect(self.show_problem)
        if hasattr(window, 'tabs'):
            window.tabs.currentChanged.connect(self.on_stage_changed)
        if hasattr(window, 'inputs_invalidated'):
            window.inputs_invalidated.connect(lambda *_: self.schedule('INPUT', 'INPUT_CHANGED'))
        window.statusBar().messageChanged.connect(lambda *_: self.schedule(self.stage, 'GUI_STATUS_CHANGED'))
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.close)

    def record(self, stage, code, **parameters):
        return self.journal.record(stage, code, **parameters)

    def record_problem(self, message=None, error=None):
        return self.record(self.stage, 'ACTION_FAILED', error=error, missing=missing_from_hint(message))

    def on_stage_changed(self, index):
        self.stage = {0: 'IMPORT', 1: 'TEMPLATES', 2: 'LAYOUT'}.get(index, 'APPLICATION')
        self.schedule(self.stage, 'STAGE_OPENED')

    def schedule(self, stage, code):
        self.pending.add((stage, code))
        self.timer.start()

    def flush(self):
        self.timer.stop()
        for stage, code in sorted(self.pending):
            self.journal.record(stage, code)
        self.pending.clear()

    def show_problem(self):
        self.window.statusBar().showMessage('軟體遇到問題，資料請保留；請到「問題回報」匯出報告，交給 Codex 協助。')

    def create_panel(self, parent=None):
        return OfflineSupportPanel(self, parent)

    def open_dialog(self):
        self.record('SUPPORT', 'REPORT_OPENED')
        dialog = QDialog(self.window)
        dialog.setWindowTitle('問題回報 · 只保存在本機')
        dialog.resize(990, 720)
        layout = QVBoxLayout(dialog)
        layout.addWidget(self.create_panel(dialog))
        close = QPushButton('返回工作')
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        try:
            return dialog.exec()
        finally:
            dialog.deleteLater()

    def close(self):
        if getattr(self, '_closed', False):
            return
        self._closed = True
        self.flush()
        self.record('APPLICATION', 'APP_CLOSED')


def install_offline_support(window, journal=None):
    controller = getattr(window, 'offline_support', None)
    if controller is None:
        if journal is None:
            journal = getattr(QApplication.instance(), '_template_ai_support_journal', None)
        controller = OfflineSupportController(window, journal)
        window.offline_support = controller
    return controller

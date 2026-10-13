"""單根來源搜尋、明列勾選及可核對批次復原；背景不存取 SQLite。"""
import threading
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from .source_discovery import discover_sources
from .source_links import verify_source


class SourceRelinkDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.library = window.library
        self.root = ""
        self.report = None
        self.busy = False
        self.cancel_event = threading.Event()
        self.setWindowTitle("来源批次定位與重連")
        self.resize(1120, 620)
        layout = QVBoxLayout(self)
        self.path_label = QLabel("選取已授權本機搜尋範圍；不預設搜尋整部電腦")
        self.path_label.setTextFormat(Qt.PlainText)
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)
        controls = QHBoxLayout()
        self.choose_button = QPushButton("選擇搜尋資料夾")
        self.choose_button.clicked.connect(self.choose_root)
        controls.addWidget(self.choose_button)
        self.search_button = QPushButton("搜尋同內容候選")
        self.search_button.clicked.connect(self.search)
        controls.addWidget(self.search_button)
        self.cancel_button = QPushButton("取消搜尋")
        self.cancel_button.clicked.connect(self.cancel_event.set)
        self.cancel_button.setEnabled(False)
        controls.addWidget(self.cancel_button)
        layout.addLayout(controls)
        self.status = QLabel("搜尋及內容相同不代表客戶／來源身份已核准。請逐列檢視並勾選。")
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["確認身份", "原登錄／來源識別", "目前位置／狀態", "新位置候選", "影響範圍", "内容核對"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table, 1)
        self.apply_button = QPushButton("確認勾選集合並重新連結")
        self.apply_button.clicked.connect(self.apply_selection)
        self.apply_button.setEnabled(False)
        layout.addWidget(self.apply_button)
        history = QHBoxLayout()
        self.history_combo = QComboBox()
        history.addWidget(self.history_combo, 1)
        self.undo_button = QPushButton("核對原位置並復原此批次")
        self.undo_button.clicked.connect(self.undo_batch)
        history.addWidget(self.undo_button)
        layout.addLayout(history)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.button(QDialogButtonBox.Close).setText("關閉")
        close.rejected.connect(self.reject)
        layout.addWidget(close)
        self.refresh_history()

    def refresh_history(self):
        self.history_combo.clear()
        for record in self.library.relink_batches():
            self.history_combo.addItem(f"{record['kind']} · {len(record['items'])} 筆 · {record['id']}", record["id"])

    def choose_root(self):
        if self.busy or self.window.busy:
            return
        root = QFileDialog.getExistingDirectory(self, "選取已授權的單一本機搜尋根目錄")
        if root:
            self.root = root
            self.path_label.setText(root)
            self.report = None
            self.table.setRowCount(0)
            self.apply_button.setEnabled(False)

    def start(self, message, function, callback, cancellable=False):
        if self.busy or self.window.busy:
            return
        self.busy = True
        for button in (self.choose_button, self.search_button, self.apply_button, self.undo_button): button.setEnabled(False)
        self.table.setEnabled(False)
        self.cancel_event.clear()
        self.cancel_button.setEnabled(cancellable)
        self.status.setText(message)
        def work():
            try: return {"value": function()}
            except Exception as error: return {"error": str(error)}
        def done(payload):
            self.busy = False
            self.choose_button.setEnabled(True)
            self.search_button.setEnabled(True)
            self.undo_button.setEnabled(True)
            self.table.setEnabled(True)
            self.cancel_button.setEnabled(False)
            if "error" in payload:
                self.status.setText("未更新任何來源：" + payload["error"])
                return
            try:
                callback(payload["value"])
            except Exception as error:
                self.status.setText("未完成更新：" + str(error))
        self.window.run_job(message, work, done)

    def search(self):
        if not self.root:
            self.status.setText("請先選取一個搜尋根目錄")
            return
        sources = self.library.list_sources()
        for source in sources:
            source["impacts"] = self.library.source_impacts(source["id"])
        self.report = None
        self.start("唯讀搜尋；不依檔名接受不同內容", lambda: discover_sources(sources, self.root, self.cancel_event), self.show_report, True)

    def show_report(self, report):
        self.report = report
        self.table.setRowCount(len(report["rows"]))
        for i, row in enumerate(report["rows"]):
            source = row["source"]
            check = QCheckBox()
            check.setChecked(False)
            check.setEnabled(bool(row["candidates"]) and report["status"] != "CANCELLED")
            self.table.setCellWidget(i, 0, check)
            self.table.setItem(i, 1, QTableWidgetItem(source["original_path"] + "\n" + source["id"]))
            self.table.setItem(i, 2, QTableWidgetItem(source["current_path"] + "\n" + row["availability"]))
            combo = QComboBox()
            combo.addItem("請明確選取候選位置", None)
            for proof in row["candidates"]:
                combo.addItem(proof.path, proof)
                combo.setItemData(combo.count() - 1, proof.path, Qt.ToolTipRole)
            self.table.setCellWidget(i, 3, combo)
            self.table.setItem(i, 4, QTableWidgetItem(source.get("impacts", {}).get("summary", "關聯未知")))
            note = f"{source['hash']}\n{source.get('byte_size', '未知')} bytes；同內容副本 {len(row['candidates'])}；同名異內容 {len(row['same_name_different'])}"
            if row.get("candidate_limit"): note += "；候選超額，請縮小範圍"
            self.table.setItem(i, 5, QTableWidgetItem(note))
            for column in (1, 2, 4, 5):
                item = self.table.item(i, column)
                item.setToolTip(item.text())
        self.table.resizeColumnsToContents()
        for i in (1, 2, 3, 5): self.table.setColumnWidth(i, 230)
        self.table.resizeRowsToContents()
        names = {"COMPLETE":"指定範圍搜尋完成", "PARTIAL":"僅完成部分搜尋，不能稱全部找齊", "CANCELLED":"已取消搜尋，未更新來源"}
        errors = "；".join(e["reason"] for e in report["errors"][:3])
        self.status.setText(f"{names[report['status']]}；已查看 {report['entries']} 項、核對 {report['hashed_files']} 檔；略過／錯誤 {len(report['errors'])}。" + errors)
        self.apply_button.setEnabled(report["status"] != "CANCELLED" and any(r["candidates"] for r in report["rows"]))

    def apply_selection(self):
        if self.busy or not self.report or self.report["status"] == "CANCELLED": return
        selected = []
        for i, row in enumerate(self.report["rows"]):
            if not self.table.cellWidget(i, 0).isChecked(): continue
            proof = self.table.cellWidget(i, 3).currentData()
            if proof is None:
                self.status.setText("勾選的來源尚未選取候選；未更新任何來源")
                return
            selected.append((row["source"], proof.path))
        if not selected:
            self.status.setText("沒有明列勾選來源，未更新任何來源"); return
        if QMessageBox.question(self, "確認重連集合", f"已逐筆核實這 {len(selected)} 條來源的身份與影響範圍？\n內容相同不能代替客戶映射確認。只更新位置，保留原登錄、作品與模板。") != QMessageBox.Yes:
            return
        def verify():
            return [{"source_id": s["id"], "expected_revision": s["link_revision"], "proof": verify_source(path, s["hash"])} for s, path in selected]
        self.start("再次核對勾選集合內容", verify, lambda requests: self.commit(requests))

    def commit(self, requests, undo_of=None):
        record = self.library.relink_sources(requests, approved=True, undo_of=undo_of)
        self.report = None
        self.apply_button.setEnabled(False)
        self.table.setRowCount(0)
        self.refresh_history()
        current = self.window.source["id"] if self.window.source else None
        self.status.setText(f"已{'復原' if undo_of else '更新'} {len(record['items'])} 筆位置；全批交易保存，原登錄與作品／模板保留")
        try:
            self.window.refresh_sources(current)
        except Exception as error:
            self.status.setText(f"已保存 {len(record['items'])} 筆位置，但畫面需重新載入：{error}")

    def undo_batch(self):
        if self.busy or self.window.busy: return
        batch_id = self.history_combo.currentData()
        if not batch_id: return
        record = self.library.relink_batch(batch_id)
        paths = "\n".join(i["previous_path"] for i in record["items"][:5])
        if QMessageBox.question(self, "確認復原批次", f"核對並復原 {len(record['items'])} 筆原位置？\n{paths}\n失聯、內容異動或後續版次變更時，全批拒絕。復原形成新位置版次。") != QMessageBox.Yes: return
        def verify():
            return [{"source_id": i["source_id"], "expected_revision": i["after_revision"], "proof": verify_source(i["previous_path"], i["hash"])} for i in record["items"]]
        self.start("核對原批次來源位置與內容", verify, lambda requests: self.commit(requests, batch_id))

    def reject(self):
        if self.busy:
            self.cancel_event.set()
            self.status.setText("工作正在安全結束，請等候後再關閉")
            return
        super().reject()

    def closeEvent(self, event):
        if self.busy:
            self.cancel_event.set()
            event.ignore()
        else: event.accept()

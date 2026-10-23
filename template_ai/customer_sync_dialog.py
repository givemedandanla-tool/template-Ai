"""主檔圖差異工作台：當次採用值與主檔同步選擇分開。"""
from copy import deepcopy
import json
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QPlainTextEdit, QMessageBox, QInputDialog)

from . import customer_sync


class CustomerSyncDialog(QDialog):
    def __init__(self, window, store, snapshot, parent=None):
        super().__init__(parent or window)
        self.host_window, self.store, self.snapshot = window, store, deepcopy(snapshot)
        source = getattr(window, 'reorder_customer_snapshot', None)
        graph = getattr(window, 'active_input_graph', None)
        self.working = deepcopy(graph.data if graph and source and source['id'] == snapshot['id']
                                else snapshot['graph'])
        if self.working is None:
            raise ValueError('舊資料歸屬待確認，不能進行圖同步')
        self.setWindowTitle('當次資料／永久主檔：完整圖差異與選擇同步')
        self.resize(1120, 720)
        layout = QVBoxLayout(self)
        self.status = QLabel('預設全部僅本次使用；勾選並確認才同步主檔。資產與版型不由此修改。')
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        layout.addWidget(self.status)
        bar = QHBoxLayout()
        for label, action in [('編輯比較草稿（不改主檔）', self.edit_work),
                              ('重新比對三方值', self.refresh),
                              ('確認選中項目同步', self.commit),
                              ('預覽歷史恢復', self.history), ('清理修訂紀錄', self.clear_history)]:
            button = QPushButton(label)
            button.clicked.connect(action)
            bar.addWidget(button)
        layout.addLayout(bar)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(['同步（預設不選）', '穩定 ID／類型', '操作',
            '快照原值', '目前主檔值', '當次採用值／擬同步值', '受影響實體'])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table, 2)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        layout.addWidget(self.details, 1)
        self.restore_of = None
        self.refresh()

    def refresh(self):
        try:
            selected = set(self.selected()) if hasattr(self, 'plan') else set()
            self.plan = customer_sync.differences(self.store, self.snapshot, self.working)
            self.table.setRowCount(len(self.plan['rows']))
            for i, row in enumerate(self.plan['rows']):
                check = QTableWidgetItem()
                check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                check.setCheckState(Qt.Checked if row['id'] in selected else Qt.Unchecked)
                self.table.setItem(i, 0, check)
                values = [row['id'], row['operation'], row['before'], row['current'],
                          row['after'], row['affected']]
                for col, value in enumerate(values, 1):
                    item = QTableWidgetItem(value if isinstance(value, str) else
                                            json.dumps(value, ensure_ascii=False))
                    item.setToolTip(item.text())
                    self.table.setItem(i, col, item)
            self.status.setText(f"客戶 {self.snapshot['code']}／{self.snapshot['id']}；快照 v{self.snapshot['revision']}，"
                f"目前 v{self.plan['current_revision']}；" +
                ('版本過期，先核對三方差異，禁止舊值覆寫。' if self.plan['stale'] else
                 '未勾選保留主檔原值；取消或關閉不修改當次輸入。'))
            self.details.setPlainText(json.dumps(self.plan, ensure_ascii=False, indent=2))
        except (ValueError, KeyError) as error:
            self.status.setText('未套用：' + str(error))

    def selected(self):
        return [r['id'] for i, r in enumerate(self.plan['rows'])
                if self.table.item(i, 0) and self.table.item(i, 0).checkState() == Qt.Checked]

    def edit_work(self):
        from .input_graph_dialog import InputGraphDialog
        dialog = InputGraphDialog(self.host_window, self.working)
        dialog.setWindowTitle('比較用草稿：新增／刪除／共享關係；未同步主檔')
        if dialog.exec() == QDialog.Accepted:
            self.working = deepcopy(dialog.graph.data)
            self.restore_of = None
            self.refresh()

    def commit(self):
        try:
            selected = self.selected()
            chosen = [row for row in self.plan['rows'] if row['id'] in selected]
            if not chosen:
                raise ValueError('沒有選中差異，主檔保持不變')
            # 再算一次完整結果，顯示未勾選資料保留原值的真實結果。
            proposed = customer_sync._apply(self.snapshot['graph'], chosen, set(selected))
            summary = dict(customer_id=self.snapshot['id'], customer_code=self.snapshot['code'],
                           snapshot_revision=self.snapshot['revision'], selected=chosen,
                           master_after=proposed, work_input_unchanged=True)
            message = json.dumps(summary, ensure_ascii=False, indent=2)
            if QMessageBox.question(self, '確認實際增／修／刪及共享影響', message) != QMessageBox.Yes:
                return
            updated = customer_sync.writeback(self.store, self.snapshot, self.working,
                selected, approved=True, source_ref='reorder:' + str(getattr(self.host_window,
                'reorder_template_id', '') or ''), restore_of=self.restore_of)
            if getattr(self.host_window, 'reorder_customer_snapshot', None) and \
                    self.host_window.reorder_customer_snapshot['id'] == updated['id']:
                self.host_window.reorder_customer_snapshot = updated
            self.snapshot = updated
            self.restore_of = None
            self.refresh()
            self.status.setText('勾選項目已原子保存為主檔新版本；當次輸入、版型與原稿未變。')
        except (ValueError, KeyError, OSError, sqlite3.DatabaseError) as error:
            self.refresh()
            self.status.setText('整個集合未套用：' + str(error))

    def _choose_history(self, title):
        history = [r for r in self.store.history(self.snapshot['id'])
                   if r['payload'].get('graph_changes')]
        if not history:
            raise ValueError('尚無完整圖同步修訂')
        labels = [f"v{r['revision']}／{r['id']}" for r in history]
        value, ok = QInputDialog.getItem(self, title, '只列此客戶修訂；不建立舊電話搜尋別名', labels, 0, False)
        return history[labels.index(value)] if ok else None

    def history(self):
        try:
            record = self._choose_history('選擇要預覽的歷史恢復')
            if record is None:
                return
            self.working, _ = customer_sync.restore_plan(self.store, self.snapshot, record['id'])
            self.restore_of = record['id']
            self.refresh()
            self.status.setText('歷史反向差異已列出；仍須逐項勾選、確認，形成新版本。')
        except ValueError as error:
            self.status.setText(str(error))

    def clear_history(self):
        try:
            record = self._choose_history('清理不再需要的圖同步歷史')
            if record and QMessageBox.question(self, '清理修訂紀錄',
                    '僅清除此修訂；目前主檔與當次輸入不變，之後無法由此紀錄恢復。') == QMessageBox.Yes:
                customer_sync.delete_history(self.store, self.snapshot, record['id'], approved=True)
                self.status.setText('指定歷史已清理；目前主檔未變。')
        except ValueError as error:
            self.status.setText(str(error))

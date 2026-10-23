"""來源客戶候選的分頁核對入口；自動提出與人工入庫分開。"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gui import MainWindow
from copy import deepcopy
import json
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QPlainTextEdit, QMessageBox, QInputDialog,
    QListWidget, QListWidgetItem, QDialogButtonBox, QAbstractItemView)

from .worker_callbacks import JobCallbacks
from .customer_candidates import CustomerCandidates
from .customers import CustomerStore


class CustomerCandidatesDialog(QDialog):
    def __init__(self, window, parent=None):
        super().__init__(parent or window)
        self.host_window: MainWindow = window
        self.candidates = CustomerCandidates(CustomerStore(window.library))
        self.offset = self.source_offset = 0
        self.running = False
        self.setWindowTitle('來源客戶候選／衝突審核與安全批次入庫')
        self.resize(1150, 760)
        layout = QVBoxLayout(self)
        self.status = QLabel('候選不代表已確認身分；檔名／同內容／同電話都不自動合併。')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        bar = QHBoxLayout()
        self.source = QComboBox()
        bar.addWidget(self.source)
        self.rules = QComboBox()
        for label, pattern in [('完整檔名去副檔名', r'(?P<code>.+)'),
            ('完整數字編號', r'(?P<code>[0-9]+)'), ('第一個底線前的編號', r'(?P<code>[^_]+)_.+'),
            ('英數及連字號編號', r'(?P<code>[A-Za-z0-9-]+)')]:
            self.rules.addItem(label, pattern)
        bar.addWidget(self.rules)
        self.button(bar, '由此來源提出候選', self.propose)
        self.button(bar, '前100來源', lambda: self.page_sources(-100))
        self.button(bar, '後100來源', lambda: self.page_sources(100))
        layout.addLayout(bar)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['入庫（預設不選）', '編號候選', '狀態', '尺寸 mm／版本',
                                             '來源檔／作品', '需核對／衝突'])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.currentCellChanged.connect(self.details_changed)
        layout.addWidget(self.table, 2)
        bar = QHBoxLayout()
        self.button(bar, '查看原始作品', self.locate)
        self.button(bar, '逐筆核對／校正／處置', self.review)
        self.button(bar, '確認勾選的已審候選入庫', self.commit)
        self.button(bar, '前100候選', lambda: self.page(-100))
        self.button(bar, '後100候選', lambda: self.page(100))
        self.button(bar, '重新載入', self.reload)
        layout.addLayout(bar)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        layout.addWidget(self.details, 1)
        self.reload_sources()
        self.reload()

    def button(self, bar, label, action):
        button = QPushButton(label)
        button.clicked.connect(action)
        bar.addWidget(button)
        return button

    def guarded(self, action):
        try:
            if self.running or self.host_window.busy:
                raise ValueError('背景工作進行中，請保留目前範圍')
            action()
        except (ValueError, KeyError, OSError, sqlite3.DatabaseError) as error:
            self.status.setText('未完成：' + str(error))

    def reload_sources(self):
        selected = self.source.currentData()
        self.source.clear()
        for sid, raw in self.host_window.library.db.execute(
                'SELECT id,payload FROM sources ORDER BY rowid LIMIT 100 OFFSET ?', (self.source_offset,)):
            from pathlib import Path
            source = json.loads(raw)
            self.source.addItem(Path(source['original_path']).name + '／' + sid, sid)
        self.source.setCurrentIndex(max(0, self.source.findData(selected)))

    def page_sources(self, delta):
        if not self.running:
            self.source_offset = max(0, self.source_offset + delta)
            self.reload_sources()

    def page(self, delta):
        if not self.running:
            self.offset = max(0, self.offset + delta)
            self.reload()

    def reload(self):
        if self.running:
            return
        self.rows = self.candidates.list(self.offset)
        self.table.setRowCount(len(self.rows))
        for i, row in enumerate(self.rows):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            check.setCheckState(Qt.Unchecked)
            self.table.setItem(i, 0, check)
            for col, value in enumerate((row['code_candidate'], row['state'],
                str(row['size_mm']) + '／' + row['pins']['template_id'],
                row['filename'] + '／' + row['pins']['artwork_id'], '；'.join(row['issues'])), 1):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.table.setItem(i, col, item)
        self.details_changed()

    def current(self):
        row = self.table.currentRow()
        if not 0 <= row < len(self.rows):
            raise ValueError('先選取一筆候選核對')
        return self.rows[row]

    def details_changed(self, *_):
        if hasattr(self, 'details'):
            try:
                self.details.setPlainText(json.dumps(self.current(), ensure_ascii=False, indent=2))
            except ValueError:
                self.details.clear()

    def propose(self):
        def action():
            sid, pattern, root = self.source.currentData(), self.rules.currentData(), self.host_window.library.root
            if not sid:
                raise ValueError('尚無已匯入來源')
            self.running = True
            self.status.setText('背景核對來源與已標記事實，尚未建立主檔。')
            def worker():
                from .storage import Library
                library = None
                try:
                    library = Library(root)
                    rows = CustomerCandidates(CustomerStore(library)).propose(sid, pattern)
                    return {'ids': [r['id'] for r in rows]}
                except Exception as error:
                    return {'error': str(error)}
                finally:
                    if library:
                        library.close()
            def finished(result):
                self.running = False
                self.reload()
                self.status.setText('未完成：' + result['error'] if 'error' in result else
                    f"本來源提出／重用 {len(result['ids'])} 筆候選；0筆時請先核對作品並學習確切版型。尚未入庫。")
            try:
                self.host_window.run_job('建立來源客戶候選', worker, JobCallbacks(finished,lambda error:finished({'error':str(error)})))
            except Exception:
                self.running = False
                raise
        self.guarded(action)

    def locate(self):
        def action():
            candidate = self.current()
            self.candidates._fresh(candidate)
            from .training_navigation import locate_work
            locate_work(self.host_window, candidate['pins']['artwork_id'])
            self.status.setText('已定位原始作品；未修改來源或核准候選。')
        self.guarded(action)

    def choose_existing(self, code):
        rows = self.candidates.store.search(code, field='CODE')
        if not rows:
            raise ValueError('找不到指定客戶編號，不能按姓名／電話猜身分')
        labels = [r['code'] + '／' + r['name'] + '／' + r['id'] for r in rows]
        chosen, ok = QInputDialog.getItem(self, '明確核對既有客戶', '只關聯版型，不覆寫人物資料', labels, 0, False)
        if not ok:
            return None, None
        customer = rows[labels.index(chosen)]
        graph = customer.get('graph')
        if not graph:
            raise ValueError('既有客戶所有權尚未核對')
        from .input_graph import InputGraph
        g = InputGraph(graph)
        dialog = QDialog(self)
        dialog.setWindowTitle('選取此來源關聯的人物範圍')
        layout = QVBoxLayout(dialog)
        listing = QListWidget()
        listing.setSelectionMode(QAbstractItemView.MultiSelection)
        for person in graph['people']:
            item = QListWidgetItem(g.label(person['id']) + '／' + person['id'])
            item.setData(Qt.UserRole, person['id'])
            listing.addItem(item)
        layout.addWidget(listing)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        return (customer, [item.data(Qt.UserRole) for item in listing.selectedItems()]) \
            if dialog.exec() == QDialog.Accepted else (None, None)

    def review(self):
        def action():
            candidate = self.current()
            labels = ['新增為獨立客戶（不合併）', '只關聯到明確選定的既有客戶', '拒絕', '暫緩']
            label, ok = QInputDialog.getItem(self, '逐筆處置來源候選',
                '同編號／同電話／同內容須核對來源與差異', labels, 0, False)
            if not ok:
                return
            decision = ['NEW_SEPARATE', 'LINK_EXISTING', 'REJECT', 'DEFER'][labels.index(label)]
            graph = deepcopy(candidate['graph'])
            code, target, scope = candidate['code_candidate'], None, None
            if decision in ('NEW_SEPARATE', 'LINK_EXISTING'):
                from .input_graph_dialog import InputGraphDialog
                editor = InputGraphDialog(self.host_window, graph)
                editor.setWindowTitle('核對來源人物／公司／聯絡候選（不改訓練事實或主檔）')
                if editor.exec() != QDialog.Accepted:
                    return
                graph = editor.graph.data
                code, ok = QInputDialog.getText(self, '確認客戶編號',
                    '保留前導0；完整檔名只是候選，請核對原始作品', text=code)
                if not ok:
                    return
                if decision == 'LINK_EXISTING':
                    target, scope = self.choose_existing(code)
                    if target is None:
                        return
            note, ok = QInputDialog.getMultiLineText(self, '記錄核對與衝突處置理由',
                '請記錄來源、身分及關聯核對結果；不要重複抄寫私人聯絡資料')
            if not ok:
                return
            conflicts=self.candidates.conflicts(graph,code,candidate['pins']['source_id']) if decision in ('NEW_SEPARATE','LINK_EXISTING') else candidate.get('conflicts',[])
            self.details.setPlainText(json.dumps(conflicts,ensure_ascii=False,indent=2))
            if QMessageBox.question(self, '保存審核，尚未入庫',
                    label + '／客戶編號 ' + code + '\n來源：' + candidate['filename'] +
                    '\n尺寸／版型：' + str(candidate['size_mm']) + '／' + candidate['pins']['template_id'] +
                    '\n已核對以下問題？\n' + '\n'.join(candidate['issues'])+'\n逐筆來源／身分差異：\n'+json.dumps(conflicts,ensure_ascii=False,indent=2)) != QMessageBox.Yes:
                return
            self.candidates.review(candidate['id'], candidate['revision'], graph, code, decision,
                'LOCAL_OPERATOR', note, target, scope, approved=True)
            self.reload()
            self.status.setText('審核已保存；沒有自動入庫或覆寫客戶資料。')
        self.guarded(action)

    def commit(self):
        def action():
            selected = [r for i, r in enumerate(self.rows)
                        if self.table.item(i, 0).checkState() == Qt.Checked]
            if not selected:
                raise ValueError('未勾選候選，沒有入庫')
            summary = [{'id': r['id'], 'code': (r.get('review') or {}).get('code'),
                        'review': r.get('review'), 'source': r['filename'], 'pins': r['pins']} for r in selected]
            if QMessageBox.question(self, '確認確切候選與關聯，整批原子入庫',
                    json.dumps(summary, ensure_ascii=False, indent=2)) != QMessageBox.Yes:
                return
            output = self.candidates.commit([{'id': r['id'], 'revision': r['revision']} for r in selected], True)
            self.reload()
            self.status.setText(f'{len(output)} 筆已原子入庫；版型／Logo及當次輸出仍須獨立驗證。')
        self.guarded(action)

    def closeEvent(self, event):
        if self.running:
            self.status.setText('背景工作正在完成安全保存，完成後可關閉。')
            event.ignore()
        else:
            super().closeEvent(event)

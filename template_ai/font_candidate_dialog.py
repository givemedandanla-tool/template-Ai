"""字型候選唯讀工作流；沒有套用、正式輸出或安裝動作。"""
import copy

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QTableWidget,
    QTableWidgetItem, QVBoxLayout)

from .worker_callbacks import JobCallbacks
from .font_catalog import build_inventory, host_candidates
from .font_candidates import SCOPE, find_candidates, render_candidate


class FontCandidateDialog(QDialog):
    def __init__(self, center):
        super().__init__(center)
        self.window = center.window
        self.reference = copy.deepcopy(center.selected())
        self.reference_style = center.style.currentText()
        self.busy = False; self.generation = 0; self.report = None; self.preview_data = None
        self.setWindowTitle("字型替代候選 · 唯讀比較與預覽"); self.resize(1160, 780)
        layout = QVBoxLayout(self)
        info = QLabel(SCOPE); info.setTextFormat(Qt.PlainText); info.setWordWrap(True); layout.addWidget(info)
        inputs = QHBoxLayout()
        self.text = QLineEdit(center.text.text()); self.text.setMaxLength(4096)
        self.text.setPlaceholderText("要量測及預覽的完整單行文字"); inputs.addWidget(self.text, 1)
        self.size = QDoubleSpinBox(); self.size.setRange(1,200); self.size.setValue(center.size.value()); self.size.setSuffix(" pt"); inputs.addWidget(self.size)
        self.width = QDoubleSpinBox(); self.width.setRange(.001,2000); self.width.setDecimals(3); self.width.setValue(center.width.value()); self.width.setSuffix(" mm"); inputs.addWidget(self.width)
        self.minimum = QDoubleSpinBox(); self.minimum.setRange(5,100); self.minimum.setValue(center.minimum.value()); self.minimum.setSuffix(" % 最小水平比例"); inputs.addWidget(self.minimum)
        self.search_button = QPushButton("查詢候選"); self.search_button.clicked.connect(self.search); inputs.addWidget(self.search_button)
        layout.addLayout(inputs)
        self.compare = QCheckBox("比較中心所選字面的自然字寬（非原稿身份）")
        self.compare.setEnabled(self.reference is not None); self.compare.setChecked(False)
        self.compare.setToolTip(" / ".join(self.reference["families"]) if self.reference else "中心尚未選取比較字面；原稿字寬未知")
        layout.addWidget(self.compare)
        self.status = QLabel("請查詢候選；不預設選取或套用字型。")
        self.status.setTextFormat(Qt.PlainText); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.summary = QLabel("每輪最多量測64字面、64 MiB資產大小，最多展示10個候選；排序依來源身份、已知比較字寬差異、水平壓縮及穩定身份。")
        self.summary.setTextFormat(Qt.PlainText); self.summary.setWordWrap(True); layout.addWidget(self.summary)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["排名／實際字面", "來源／身份", "覆蓋率", "自然字寬", "水平比例", "比較字寬差異", "排名理由／限制"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers); self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection); self.table.itemSelectionChanged.connect(self.selection_changed)
        layout.addWidget(self.table, 2)
        self.exclusions = QTableWidget(0, 2); self.exclusions.setHorizontalHeaderLabels(["排除字面／來源", "不列入候選的原因"])
        self.exclusions.setEditTriggers(QTableWidget.NoEditTriggers); layout.addWidget(self.exclusions, 1)
        self.preview_button = QPushButton("重新核驗所選候選並唯讀預覽")
        self.preview_button.setEnabled(False); self.preview_button.clicked.connect(self.preview); layout.addWidget(self.preview_button)
        self.review_button=QPushButton("核准本機候選的模板影響／草稿替代審核")
        self.review_button.setEnabled(False);self.review_button.clicked.connect(self.open_review);layout.addWidget(self.review_button)
        self.preview_label = QLabel("未建立預覽；預览不代表原稿外觀一致或正式成品合格。")
        self.preview_label.setTextFormat(Qt.PlainText); self.preview_label.setAlignment(Qt.AlignCenter)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(self.preview_label); scroll.setMinimumHeight(130); layout.addWidget(scroll, 1)
        self.details = QLabel(SCOPE); self.details.setTextFormat(Qt.PlainText); self.details.setWordWrap(True); layout.addWidget(self.details)
        close = QDialogButtonBox(QDialogButtonBox.Close); close.button(QDialogButtonBox.Close).setText("關閉"); close.rejected.connect(self.reject); layout.addWidget(close)
        for widget in (self.text,self.size,self.width,self.minimum,self.compare):
            signal = widget.textChanged if widget is self.text else widget.toggled if widget is self.compare else widget.valueChanged
            signal.connect(self.invalidate)

    def inputs(self):
        return {"text":self.text.text(), "size_pt":self.size.value(), "width_mm":self.width.value(), "min_scale":self.minimum.value()/100}

    def invalidate(self, *_):
        self.generation += 1; self.report = None
        self.summary.setText("輸入已變更，舊搜尋統計不適用；每輪最多量測64字面、展示10個候選。")
        self.table.setRowCount(0); self.exclusions.setRowCount(0); self.selection_changed()
        self.status.setText("輸入或比較條件已變更；請重新查詢，舊候選不適用。")

    def selected(self):
        rows = self.table.selectionModel().selectedRows()
        return self.report["candidates"][rows[0].row()] if self.report and rows else None

    def selection_changed(self):
        self.preview_data = None; self.preview_label.clear()
        self.preview_label.setText("明確選取一個候選後，重新核驗並預覽；不套用模板。")
        self.preview_button.setEnabled(self.selected() is not None and not self.busy)
        self.review_button.setEnabled(bool(self.selected() and self.selected()['row']['kind']=='ASSET') and not self.busy)
        self.details.setText(SCOPE)

    def start(self, message, work, done):
        if self.busy or self.window.busy: return
        generation = self.generation
        self.busy = True; self.status.setText(message)
        self.search_button.setEnabled(False); self.preview_button.setEnabled(False); self.table.setEnabled(False)
        self.review_button.setEnabled(False)
        def guarded():
            try: return {"value":work()}
            except Exception as error: return {"error":str(error)}
        def finished(payload):
            try:
                if generation != self.generation:
                    self.status.setText("工作期間輸入已改變，結果過期；請重新查詢。")
                elif "error" in payload:
                    self.status.setText("未完成："+payload["error"]+"；可重新查詢。")
                    self.preview_data = None; self.preview_label.clear(); self.preview_label.setText("核驗失敗，未顯示候選預覽。")
                else: done(payload["value"])
            finally:
                self.busy = False; self.search_button.setEnabled(True); self.table.setEnabled(True)
                self.preview_button.setEnabled(self.selected() is not None)
                self.review_button.setEnabled(bool(self.selected() and self.selected()['row']['kind']=='ASSET'))
        try: self.window.run_job(message, guarded, JobCallbacks(finished,lambda error:finished({'error':str(error)})))
        except Exception:
            self.busy = False; self.search_button.setEnabled(True); self.table.setEnabled(True)
            self.preview_button.setEnabled(self.selected() is not None)
            raise

    def search(self):
        if self.busy or self.window.busy: return
        inputs = self.inputs(); reference = copy.deepcopy(self.reference) if self.compare.isChecked() else None
        assets = self.window.library.fonts(); templates = self.window.library.templates(); hosts,partial = host_candidates()
        self.invalidate()
        def work():
            inventory = build_inventory(assets,templates,hosts,partial,max_bytes=64*1024*1024)
            return find_candidates(inventory,**inputs,reference=reference,reference_style=self.reference_style)
        self.start("背景核對必要字形、來源及固定字級尺寸，篩選並排名", work, self.show_report)

    def show_report(self, report):
        self.report = report
        total = len(report["candidates"])
        self.summary.setText(f"{'部分搜尋' if report['status']=='PARTIAL' else '無實際文字' if report['status']=='NO_TEXT' else '本輪搜尋完成'}；量測 {report['checked_faces']} 字面，展示 {total} 候選，排除 {len(report['excluded'])}，未量測 {report['omitted_faces']}，其餘合格 {report['hidden_eligible']}。排序：來源身份 → 已知比較字寬差異 → 水平壓縮 → 穩定身份。\n"+report["reference_issue"])
        self.status.setText("請明確選取候選後重新核驗並唯讀預覽；不預設選取或套用。")
        self.table.blockSignals(True); self.table.setRowCount(total)
        for i,candidate in enumerate(report["candidates"]):
            a = candidate["analysis"]; delta = candidate["width_delta_ratio"]
            values = [f"{candidate['rank']} · {a['family']} / {a['style']}",candidate["row"]["source"],f"{a['coverage']*100:.2f}%",
                      f"{a['width_mm']:.4f} mm",f"{a['scale']*100:.3f}%", "未知" if delta is None else f"{delta*100:+.3f}%",
                      "；".join(candidate["reasons"])]
            for j,value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value+"\n"+candidate["row"]["identity"]+"\n"+candidate["id"] if j==1 else value)
                self.table.setItem(i,j,item)
        self.table.clearSelection(); self.table.blockSignals(False)
        for j,w in enumerate((225,150,85,115,100,115,330)): self.table.setColumnWidth(j,w)
        self.exclusions.setRowCount(len(report["excluded"]))
        for i,candidate in enumerate(report["excluded"]):
            for j,value in enumerate((" / ".join(candidate["row"]["families"])+" / "+candidate["requested_style"]+" · "+candidate["row"]["source"], "；".join(candidate["reasons"]))):
                item=QTableWidgetItem(value); item.setToolTip(value); self.exclusions.setItem(i,j,item)
        self.exclusions.setColumnWidth(0,340); self.exclusions.setColumnWidth(1,700)
        self.table.resizeRowsToContents(); self.exclusions.resizeRowsToContents(); self.selection_changed()

    def preview(self):
        candidate = self.selected()
        if not candidate or self.busy or self.window.busy: return
        inputs = dict(self.report["input"])
        self.preview_data=None; self.preview_label.clear(); self.preview_label.setText("重新核驗中；不沿用舊畫面。")
        self.start("重新核對所選字面與完整文字，建立唯讀预覽", lambda:render_candidate(candidate, inputs), self.show_preview)

    def show_preview(self, result):
        pixmap=QPixmap()
        if not pixmap.loadFromData(result["png"],"PNG"): raise ValueError("預覽PNG無法顯示")
        self.preview_data=result; self.preview_label.setPixmap(pixmap)
        a=result["analysis"]
        self.details.setText(f"{a['family']} / {a['style']}；固定 {a['size_pt']:g} pt，自然字寬 {a['width_mm']:.4f} mm，水平比例 {a['scale']*100:.3f}%。觀看倍率 {result['pixels_per_mm']:.3f} px/mm；整框縮放只影響觀看。\n"+SCOPE)
        self.status.setText("所選候選重新核驗與唯讀預覽完成；模板及字型設定未變更。")

    def reject(self):
        if self.busy: self.status.setText("背景核驗中，請等候完成再關閉。"); return
        super().reject()

    def open_review(self):
        candidate=self.selected()
        if self.busy or not candidate or candidate['row']['kind']!='ASSET':return
        from .font_review_dialog import FontReviewDialog
        FontReviewDialog(self.window,candidate['row'],self.text.text(),self).exec()

    def closeEvent(self,event):
        if self.busy: event.ignore()
        else: event.accept()

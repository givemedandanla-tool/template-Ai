"""共用字型中心；查詢與診斷不替換模板，Qt字型物件不跨執行緒。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox,QDialog,QDialogButtonBox,QDoubleSpinBox,QHBoxLayout,QLabel,QLineEdit,
    QPushButton,QTableWidget,QTableWidgetItem,QVBoxLayout)
from .worker_callbacks import JobCallbacks
from .font_catalog import STATUS_NAMES,analyze_font,build_inventory,filter_inventory,host_candidates


class FontCenterDialog(QDialog):
    def __init__(self,window):
        super().__init__(window)
        self.window=window
        self.busy=False
        self.analysis_generation=0
        self.inventory=None
        self.visible_rows=[]
        self.setWindowTitle("共用字型管理與文字診斷")
        self.resize(1180,760)
        layout=QVBoxLayout(self)
        top=QHBoxLayout()
        self.query=QLineEdit(); self.query.setPlaceholderText("家族、款式、來源、狀態或模板名稱")
        self.query.textChanged.connect(self.filter_rows); top.addWidget(self.query,1)
        self.kind=QComboBox()
        for title,data in (("全部來源",None),("程式核准複本","ASSET"),("Qt可用候選","QT"),("模板待處理引用","REFERENCE")): self.kind.addItem(title,data)
        self.kind.currentIndexChanged.connect(self.filter_rows); top.addWidget(self.kind)
        self.health=QComboBox(); self.health.addItem("全部狀態",None)
        for key,name in STATUS_NAMES.items(): self.health.addItem(name,key)
        self.health.currentIndexChanged.connect(self.filter_rows); top.addWidget(self.health)
        self.refresh_button=QPushButton("重新核對字型資產"); self.refresh_button.clicked.connect(self.refresh); top.addWidget(self.refresh_button)
        layout.addLayout(top)
        self.status=QLabel("資產內容需核對；Qt可用不等於原稿身份已證實。查詢不變更模板。")
        self.status.setTextFormat(Qt.PlainText); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.table=QTableWidget(0,6)
        self.table.setHorizontalHeaderLabels(["家族","款式／字面","來源","狀態","模板／欄位影響","內容身份／使用限制"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers); self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection); self.table.itemSelectionChanged.connect(self.selection_changed)
        layout.addWidget(self.table,1)
        self.details=QLabel("選取一列檢視完整引用與限制")
        self.details.setTextFormat(Qt.PlainText); self.details.setWordWrap(True); self.details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.details)
        inputs=QHBoxLayout()
        self.text=QLineEdit("Alex Example 0900-123-456"); self.text.setMaxLength(4096); inputs.addWidget(self.text,1)
        self.size=QDoubleSpinBox(); self.size.setRange(1,200); self.size.setValue(10); self.size.setSuffix(" pt"); inputs.addWidget(self.size)
        self.width=QDoubleSpinBox(); self.width.setRange(.001,2000); self.width.setDecimals(3); self.width.setValue(80); self.width.setSuffix(" mm"); inputs.addWidget(self.width)
        self.minimum=QDoubleSpinBox(); self.minimum.setRange(5,100); self.minimum.setValue(85); self.minimum.setSuffix(" % 最小字寬"); inputs.addWidget(self.minimum)
        self.style=QComboBox(); inputs.addWidget(self.style)
        self.analyze_button=QPushButton("診斷所選字面"); self.analyze_button.clicked.connect(self.analyze); self.analyze_button.setEnabled(False); inputs.addWidget(self.analyze_button)
        layout.addLayout(inputs)
        self.result=QLabel("診斷僅判斷所選單行字形／字寬；不改字級、不截字、不核准完整輸出或授權。")
        self.result.setTextFormat(Qt.PlainText); self.result.setWordWrap(True); self.result.setTextInteractionFlags(Qt.TextSelectableByMouse); layout.addWidget(self.result)
        for widget in (self.text,self.size,self.width,self.minimum):
            (widget.textChanged if widget is self.text else widget.valueChanged).connect(self.clear_result)
        self.style.currentIndexChanged.connect(self.clear_result)
        actions=QHBoxLayout()
        self.candidates_button=QPushButton("替代候選排名與唯讀預覽"); self.candidates_button.clicked.connect(self.open_candidates); actions.addWidget(self.candidates_button)
        self.import_button=QPushButton("匯入合法本機字型"); self.import_button.clicked.connect(self.import_font); actions.addWidget(self.import_button)
        self.rights_button=QPushButton('核對所選字面輸出授權'); self.rights_button.clicked.connect(self.attest_rights); actions.addWidget(self.rights_button)
        self.repair_button=QPushButton("修復既有核准複本"); self.repair_button.clicked.connect(self.repair_font); actions.addWidget(self.repair_button)
        close=QDialogButtonBox(QDialogButtonBox.Close); close.button(QDialogButtonBox.Close).setText("關閉"); close.rejected.connect(self.reject); actions.addWidget(close)
        layout.addLayout(actions)

    def clear_result(self,*_):
        self.analysis_generation+=1
        self.result.setText("診斷輸入或字面已改變；請重新診斷。字型／模板與輸出未變更。")

    def start(self,message,work,done):
        if self.busy or self.window.busy: return
        self.busy=True; self.status.setText(message)
        for button in (self.refresh_button,self.analyze_button,self.import_button,self.repair_button,self.candidates_button): button.setEnabled(False)
        self.table.setEnabled(False)
        for control in (self.query,self.kind,self.health): control.setEnabled(False)
        def guarded():
            try: return {"value":work()}
            except Exception as error: return {"error":str(error)}
        def finished(payload):
            self.busy=False; self.table.setEnabled(True)
            for control in (self.query,self.kind,self.health): control.setEnabled(True)
            for button in (self.refresh_button,self.import_button,self.repair_button,self.candidates_button): button.setEnabled(True)
            if "error" in payload: self.status.setText("尚未完成核對："+payload["error"])
            else: done(payload["value"])
            self.analyze_button.setEnabled(self.selected() is not None)
        self.window.run_job(message,guarded,JobCallbacks(finished,lambda error:finished({'error':str(error)})))

    def refresh(self):
        if self.busy or self.window.busy: return
        assets=self.window.library.fonts(); templates=self.window.library.templates()
        hosts,partial=host_candidates()
        self.inventory=None; self.table.setRowCount(0); self.clear_result()
        self.start("背景只讀核對字型身份與模板引用",lambda:build_inventory(assets,templates,hosts,partial),self.show_inventory)

    def show_inventory(self,inventory):
        self.inventory=inventory
        self.status.setText(("本輪核對完成" if inventory["status"]=="COMPLETE" else "部分核對，不能當全部資產可用")+
                            f"；{len(inventory['rows'])} 個條目。Qt候選來源未核實，原稿字型未知仍保留未知。")
        self.filter_rows()

    def filter_rows(self,*_):
        if self.busy or not self.inventory: return
        self.visible_rows=filter_inventory(self.inventory["rows"],self.query.text(),self.kind.currentData(),self.health.currentData())
        self.table.blockSignals(True); self.table.setRowCount(len(self.visible_rows))
        for i,row in enumerate(self.visible_rows):
            templates={r["template_id"] for r in row["references"]}
            identity=row["identity"]
            if row.get("asset"): identity += "\n"+row["asset"].get("hash","未知")+"\n"+row["asset"].get("path","未知")
            values=[" / ".join(row["families"])," / ".join(row["styles"]) or "未核驗",row["source"],STATUS_NAMES[row["status"]],
                    f"{len(templates)} 模板／{len(row['references'])} 欄位",identity]
            for column,value in enumerate(values):
                item=QTableWidgetItem(value); item.setToolTip(value); self.table.setItem(i,column,item)
        self.table.resizeColumnsToContents()
        for col,width in ((0,180),(1,130),(2,150),(3,160),(4,145),(5,300)): self.table.setColumnWidth(col,width)
        self.table.resizeRowsToContents(); self.table.clearSelection(); self.table.blockSignals(False)
        self.selection_changed()

    def selected(self):
        rows=self.table.selectionModel().selectedRows()
        return self.visible_rows[rows[0].row()] if rows and rows[0].row()<len(self.visible_rows) else None

    def selection_changed(self):
        row=self.selected(); self.style.blockSignals(True); self.style.clear()
        if row:
            self.style.addItems(row["styles"])
            refs=[f"{r['template_name']} v{r['version']}（{r['state']}）／{r['owner']}／{r['kind']} · {r['slot_id']}"+
                  (" · 引用家族不符" if r.get("binding_valid") is False else "") for r in row["references"]]
            self.details.setText("；".join(row["notes"])+"\n"+"\n".join(refs[:12])+(f"\n另有{len(refs)-12}條引用；本輪僅展示前12條" if len(refs)>12 else ""))
        else: self.details.setText("尚未選取條目；不預設核准或替換字型")
        self.style.blockSignals(False); self.analyze_button.setEnabled(bool(row) and not self.busy); self.clear_result()

    def analyze(self):
        row=self.selected()
        if not row or self.busy: return
        text,size,width,minimum,style=self.text.text(),self.size.value(),self.width.value(),self.minimum.value()/100,self.style.currentText()
        generation=self.analysis_generation
        def publish(result):
            if generation!=self.analysis_generation:
                self.result.setText("診斷期間輸入已變更，結果過期；請重新診斷。")
                self.status.setText("未將舊診斷套用到新輸入")
            else: self.show_analysis(result)
        self.start("背景核對實際字形與固定字級單行寬度",lambda:analyze_font(row,text,size,width,minimum,style or None),publish)

    def show_analysis(self,result):
        coverage="未判定" if result["coverage"] is None else f"{result['coverage']*100:.2f}%"
        measured="未核驗" if result["width_mm"] is None else f"{result['width_mm']:.4f} mm"
        scale="未核驗" if result["scale"] is None else f"{result['scale']*100:.3f}%"
        verdict={"FEASIBLE_WIDTH":"此單行字形與寬度範圍可行","BLOCKED":"字形／字面／寬度驗證未通過","NO_TEXT":"無實際文字"}[result["status"]]
        self.result.setText(f"{verdict} · 固定 {result['size_pt']:g} pt\n實際字面：{result.get('family','未證實')}／{result.get('style','未證實')}\n覆蓋率 {coverage}；實測寬度 {measured}；需要水平比例 {scale}\n"+
                            "；".join(result["issues"]+result["missing"][:20])+"\n"+result["scope"])
        self.status.setText("所選條目診斷完成；未改模板、來源或輸出核准")

    def import_font(self):
        if not self.busy and not self.window.busy: self.window.import_font(); self.refresh()

    def attest_rights(self):
        from PySide6.QtWidgets import QInputDialog,QMessageBox
        row=self.selected()
        if self.busy or not row or not row.get('asset'):return
        actor,ok=QInputDialog.getText(self,'字型輸出授權','核准者（不等於授權提供者）')
        if not ok:return
        basis,ok=QInputDialog.getText(self,'字型輸出授權','有權印製／轉出的授權依據；不接受以外觀或可載入當授權')
        if not ok:return
        pdf=QMessageBox.question(self,'PDF嵌入用途','授權是否也明確允許PDF嵌入？\nOpenType技術限制仍會獨立檢查；選否仍可核對點陣輸出。')==QMessageBox.Yes
        if QMessageBox.question(self,'確認授權範圍','只更新所選字面記錄；既有模板不會被自動改寫，需另建草稿重新套用並驗證。是否確認？')!=QMessageBox.Yes:return
        try:self.window.font_manager.record_output_rights(row['asset'],actor,basis,pdf);self.refresh()
        except (ValueError,OSError) as error:self.result.setText(str(error))

    def open_candidates(self):
        if self.busy or self.window.busy: return
        from .font_candidate_dialog import FontCandidateDialog
        dialog=FontCandidateDialog(self)
        dialog.exec()

    def repair_font(self):
        if not self.busy and not self.window.busy: self.window.repair_font(); self.refresh()

    def reject(self):
        if self.busy: self.status.setText("工作正在安全核對；請等候完成再關閉"); return
        super().reject()

    def closeEvent(self,event):
        if self.busy: event.ignore()
        else: event.accept()

"""共用字型中心；查詢與診斷不替換模板，Qt字型物件不跨執行緒。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox,QDialog,QDialogButtonBox,QDoubleSpinBox,QHBoxLayout,QLabel,QLineEdit,
    QPushButton,QTableWidget,QTableWidgetItem,QVBoxLayout)
from .worker_callbacks import JobCallbacks
from .font_catalog import STATUS_NAMES,analyze_font,build_inventory,filter_inventory,host_candidates,recorded_use_rights,measured_glyph_state


class FontCenterDialog(QDialog):
    def __init__(self,window,source_context=None):
        super().__init__(window)
        self.window=window
        self.busy=False
        self.analysis_generation=0
        self.inventory=None
        self.visible_rows=[]
        self.measurements={};self.source_reference=None;self.identity_report=None
        self.windows_receipt=None
        self.setWindowTitle("共用字型管理與文字診斷")
        self.resize(1180,760)
        layout=QVBoxLayout(self)
        self.source_context=source_context
        self.context_label=QLabel('');self.context_label.setTextFormat(Qt.PlainText);self.context_label.setWordWrap(True)
        self.context_label.setVisible(bool(source_context));layout.addWidget(self.context_label)
        top=QHBoxLayout()
        self.query=QLineEdit(); self.query.setPlaceholderText("家族、款式、來源、狀態或模板名稱")
        self.query.textChanged.connect(self.filter_rows); top.addWidget(self.query,1)
        self.kind=QComboBox()
        for title,data in (("全部來源",None),("程式核准複本","ASSET"),("Qt可用候選","QT"),("模板待處理引用","REFERENCE")): self.kind.addItem(title,data)
        self.kind.addItem('Windows已登錄來源（Qt字面另驗）','WINDOWS_SOURCE')
        self.kind.currentIndexChanged.connect(self.filter_rows); top.addWidget(self.kind)
        self.health=QComboBox(); self.health.addItem("全部狀態",None)
        for key,name in STATUS_NAMES.items(): self.health.addItem(name,key)
        self.health.currentIndexChanged.connect(self.filter_rows); top.addWidget(self.health)
        self.refresh_button=QPushButton("重新核對字型資產"); self.refresh_button.clicked.connect(self.refresh); top.addWidget(self.refresh_button)
        layout.addLayout(top)
        filters=QHBoxLayout();self.rights=QComboBox();self.glyph=QComboBox()
        for label,value in [('全部授權記錄',None),('授權未核實','UNKNOWN'),('資產已阻擋','BLOCKED'),('已記錄PDF用途（輸出重驗）','PDF_RECORDED'),('僅記錄點陣用途','RASTER_RECORDED')]:self.rights.addItem(label,value)
        for label,value in [('本輪全部字形狀態',None),('尚未檢查','NOT_CHECKED'),('已測缺字','MISSING'),('已測字形覆蓋（版面另驗）','COVERED')]:self.glyph.addItem(label,value)
        for control in (self.rights,self.glyph):control.currentIndexChanged.connect(self.filter_rows);filters.addWidget(control)
        layout.addLayout(filters)
        source=QHBoxLayout();self.source_button=QPushButton('指定來源字型參考檔（只讀）');self.source_button.clicked.connect(self.choose_source_font);source.addWidget(self.source_button);self.identity_button=QPushButton('核對來源與選取字面的身分');self.identity_button.clicked.connect(self.verify_source_identity);self.identity_button.setEnabled(False);source.addWidget(self.identity_button);layout.addLayout(source)
        self.source_label=QLabel('原稿字型未識別；名稱／外觀相似只作候選。');self.source_label.setTextFormat(Qt.PlainText);self.source_label.setWordWrap(True);layout.addWidget(self.source_label)
        self.identity_label=QLabel('來源身分尚未核對；未變更來源或模板。');self.identity_label.setTextFormat(Qt.PlainText);self.identity_label.setWordWrap(True);layout.addWidget(self.identity_label)
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
            (widget.textChanged if widget is self.text else widget.valueChanged).connect(self.diagnostic_inputs_changed)
        self.style.currentIndexChanged.connect(self.diagnostic_style_changed)
        actions=QHBoxLayout()
        self.candidates_button=QPushButton("替代候選排名與唯讀預覽"); self.candidates_button.clicked.connect(self.open_candidates); actions.addWidget(self.candidates_button)
        self.import_button=QPushButton("匯入合法本機字型"); self.import_button.clicked.connect(self.import_font); actions.addWidget(self.import_button)
        self.rights_button=QPushButton('核對所選字面輸出授權'); self.rights_button.clicked.connect(self.attest_rights); actions.addWidget(self.rights_button)
        self.repair_button=QPushButton("修復既有核准複本"); self.repair_button.clicked.connect(self.repair_font); actions.addWidget(self.repair_button)
        self.windows_button=QPushButton('安裝至Windows（另行確認）');self.windows_button.clicked.connect(self.open_windows_workflow);actions.addWidget(self.windows_button);self.update_windows_action()
        close=QDialogButtonBox(QDialogButtonBox.Close); close.button(QDialogButtonBox.Close).setText("關閉"); close.rejected.connect(self.reject); actions.addWidget(close)
        layout.addLayout(actions)
        if source_context:
            text=source_context.get('text','')
            if not isinstance(text,str) or len(text)>4096:raise ValueError('來源文字超出診斷預算；未截斷或套用')
            self.context_label.setText('來源定位：'+str(source_context.get('location',''))+'\n僅供本次唯讀診斷；衍生字型名稱是候選線索，原稿字型／字級／可編輯性未證實。')
            self.text.setText(text)
            hint=source_context.get('family_hint','')
            if isinstance(hint,str) and len(hint)<=500:
                # This is a search hint only, never a CSS resolution or identity proof.
                self.query.setText(hint.split(',')[0].strip().strip("\"'"))


    def clear_result(self,*_):
        self.analysis_generation+=1
        self.identity_report=None;self.identity_label.setText('來源身分尚未核對；未變更來源或模板。')
        self.result.setText("診斷輸入或字面已改變；請重新診斷。字型／模板與輸出未變更。")

    def diagnostic_inputs_changed(self,*_):
        self.measurements.clear();self.clear_result();self.filter_rows()

    def diagnostic_style_changed(self,*_):
        row=self.selected()
        if row:self.measurements.pop(row['id'],None)
        self.clear_result()

    def show_cached_analysis(self):
        row=self.selected();value=self.measurements.get(row['id']) if row else None
        if value and value.get('style')==self.style.currentText():self.show_analysis(value)

    def update_windows_action(self):
        import sys
        row=self.selected();enabled=sys.platform=='win32' and not self.busy and bool(row and row.get('asset'))
        self.windows_button.setEnabled(enabled);self.windows_button.setToolTip('僅交接Windows原生檢視器，安裝／範圍仍須獨立確認；目前平台不可用時不啟動。')

    def open_windows_workflow(self):
        import sys
        row=self.selected()
        if self.busy or self.window.busy:return
        if sys.platform!='win32' or not row or not row.get('asset'):self.status.setText('需Windows與已核對的程式內字型來源；未啟動或安裝。');return
        from .windows_font_dialog import WindowsFontWorkflowDialog
        dialog=WindowsFontWorkflowDialog(self);dialog.exec();dialog.deleteLater()

    def start(self,message,work,done):
        if self.busy or self.window.busy: return
        self.busy=True; self.status.setText(message)
        for button in (self.refresh_button,self.analyze_button,self.import_button,self.repair_button,self.candidates_button,self.source_button,self.identity_button,self.windows_button): button.setEnabled(False)
        self.table.setEnabled(False)
        for control in (self.query,self.kind,self.health,self.rights,self.glyph): control.setEnabled(False)
        def guarded():
            try: return {"value":work()}
            except Exception as error: return {"error":str(error)}
        def finished(payload):
            self.busy=False; self.table.setEnabled(True)
            for control in (self.query,self.kind,self.health,self.rights,self.glyph): control.setEnabled(True)
            for button in (self.refresh_button,self.import_button,self.repair_button,self.candidates_button,self.source_button): button.setEnabled(True)
            if "error" in payload: self.status.setText("尚未完成核對："+payload["error"])
            else: done(payload["value"])
            self.analyze_button.setEnabled(self.selected() is not None)
            self.identity_button.setEnabled(bool(self.selected() and self.source_reference))
            self.update_windows_action()
        self.window.run_job(message,guarded,JobCallbacks(finished,lambda error:finished({'error':str(error)})))

    def refresh(self):
        if self.busy or self.window.busy: return
        assets=self.window.library.fonts(); templates=self.window.library.templates()
        hosts,partial=host_candidates()
        self.inventory=None;self.measurements.clear(); self.table.setRowCount(0); self.clear_result()
        def inventory():
            from .windows_font_sources import windows_font_sources
            return build_inventory(assets,templates,hosts,partial,windows_sources=windows_font_sources())
        self.start("背景只讀核對字型身份與模板引用",inventory,self.show_inventory)

    def show_inventory(self,inventory):
        self.inventory=inventory
        source_status={'COMPLETE':'本輪登錄檔案已核對','PARTIAL':'僅完成部分來源','STALE':'來源變更需重盤','UNAVAILABLE':'目前環境不可用','NOT_CHECKED':'尚未核對'}.get(inventory.get('windows_source_status','NOT_CHECKED'),'尚未核對')
        self.status.setText(("本輪核對完成" if inventory["status"]=="COMPLETE" else "部分核對，不能當全部資產可用")+
                            f"；{len(inventory['rows'])} 個條目。Qt候選來源未核實，原稿字型未知仍保留未知。Windows登錄來源："+source_status+'；登錄不等於目前實際選字或使用授權。'+'；'.join(inventory.get('notes',[])[:3]))
        self.filter_rows()

    def filter_rows(self,*_):
        if self.busy or not self.inventory: return
        selected=self.selected();old_id=selected['id'] if selected else None;old_style=self.style.currentText()
        self.visible_rows=filter_inventory(self.inventory["rows"],self.query.text(),self.kind.currentData(),self.health.currentData(),rights=self.rights.currentData(),glyph=self.glyph.currentData(),measurements=self.measurements)
        self.table.blockSignals(True); self.table.setRowCount(len(self.visible_rows))
        for i,row in enumerate(self.visible_rows):
            templates={r["template_id"] for r in row["references"]}
            identity=row["identity"]
            identity+='\n授權記錄：'+{'UNKNOWN':'未核實','BLOCKED':'資產阻擋','PDF_RECORDED':'已記錄PDF用途，輸出仍須重驗','RASTER_RECORDED':'僅記錄點陣用途'}[recorded_use_rights(row)]+'；本輪字形：'+{'NOT_CHECKED':'未檢查','MISSING':'已測缺字','COVERED':'已測覆蓋（僅該款式與文字）'}[measured_glyph_state(row,self.measurements)]
            if row.get("asset"): identity += "\n"+row["asset"].get("hash","未知")+"\n"+row["asset"].get("path","未知")
            values=[" / ".join(row["families"])," / ".join(row["styles"]) or "未核驗",row["source"],STATUS_NAMES[row["status"]],
                    f"{len(templates)} 模板／{len(row['references'])} 欄位",identity]
            for column,value in enumerate(values):
                item=QTableWidgetItem(value); item.setToolTip(value); self.table.setItem(i,column,item)
        self.table.resizeColumnsToContents()
        for col,width in ((0,180),(1,130),(2,150),(3,160),(4,145),(5,300)): self.table.setColumnWidth(col,width)
        self.table.resizeRowsToContents(); self.table.clearSelection()
        index=next((i for i,row in enumerate(self.visible_rows) if row['id']==old_id),None)
        if index is not None:self.table.selectRow(index)
        self.table.blockSignals(False)
        self.selection_changed()
        if index is not None and old_style in self.visible_rows[index]['styles']:
            self.style.blockSignals(True);self.style.setCurrentText(old_style);self.style.blockSignals(False)
        self.show_cached_analysis()

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
        self.show_cached_analysis()
        self.identity_button.setEnabled(bool(row and self.source_reference and not self.busy))
        self.update_windows_action()

    def analyze(self):
        row=self.selected()
        if not row or self.busy: return
        text,size,width,minimum,style=self.text.text(),self.size.value(),self.width.value(),self.minimum.value()/100,self.style.currentText()
        generation=self.analysis_generation
        def publish(result):
            if generation!=self.analysis_generation:
                self.filter_rows()
                self.result.setText("診斷期間輸入已變更，結果過期；請重新診斷。")
                self.status.setText("未將舊診斷套用到新輸入")
            else:
                if len(self.measurements)>=64:self.measurements.pop(next(iter(self.measurements)))
                self.measurements[row['id']]=result;self.filter_rows();self.show_analysis(result)
        self.start("背景核對實際字形與固定字級單行寬度",lambda:analyze_font(row,text,size,width,minimum,style or None),publish)

    def choose_source_font(self):
        if self.busy or self.window.busy:return
        from PySide6.QtWidgets import QFileDialog,QInputDialog
        from .font_evidence import inspect_font
        path,_=QFileDialog.getOpenFileName(self,'只讀指定有權提供的來源字型參考','','字型 (*.ttf *.otf *.ttc)')
        if not path:return
        def loaded(proof):
            face=proof['faces'][0]
            if len(proof['faces'])>1:
                choices=[str(f['index'])+'／'+str(f['family'])+'／'+str(f['style']) for f in proof['faces']];choice,ok=QInputDialog.getItem(self,'指定確切來源字面','集合檔不能只靠檔案身分；選取實際來源字面',choices,0,False)
                if not ok:return
                face=proof['faces'][choices.index(choice)]
            self.source_reference=dict(font_path=path,font_sha256=proof['hash'],face_index=face['index'],family=face['family'],postscript_name=face['postscript_name'],unique_name=face['unique_name']);self.clear_result();self.source_label.setText('本機參考：'+path+'／'+str(face['family'])+'／'+str(face['style'])+'；使用者指定參考不等於原稿關聯已證實。')
        self.start('只讀解析來源字型參考／字面，不匯入或安裝',lambda:inspect_font(path),loaded)

    def verify_source_identity(self):
        row=self.selected()
        if self.busy or self.window.busy or not row or not self.source_reference:return
        from .source_text_evidence import identity_match
        reference=dict(self.source_reference);asset=row.get('asset') or {};face=asset.get('font_evidence',{});candidate={**asset,'family':face.get('family') or next(iter(row['families']),''),'postscript_name':face.get('postscript_name'),'unique_name':face.get('unique_name')};generation=self.analysis_generation
        registered_only=False
        if not asset and row.get('windows_sources'):
            from PySide6.QtWidgets import QInputDialog
            sources=row['windows_sources'];origin=sources[0]
            if len(sources)>1:
                choices=[v['path']+'／'+v['style']+'／字面'+str(v['face_index'])+'／'+','.join(v['registry_scopes']) for v in sources];choice,ok=QInputDialog.getItem(self,'核對確切Windows登錄來源','只核對此檔案／字面；不推定程式目前採用它',choices,0,False)
                if not ok:return
                origin=sources[choices.index(choice)]
            current=self.selected()
            if not current or current['id']!=row['id'] or generation!=self.analysis_generation:self.identity_label.setText('來源選取已改變，請重新核對。');return
            candidate=dict(path=origin['path'],hash=origin['hash'],family=row['families'][0],font_evidence=dict(index=origin['face_index']));registered_only=True
        def loaded(report):
            if generation!=self.analysis_generation:self.identity_label.setText('核對期間資料已變更，未採用舊身分結果。');return
            self.identity_report=report;self.identity_label.setText({'PROVEN_SAME_EXTRACTED_FACE':'已核對來源集合之同一字面複本；原稿關聯及原生可編輯性仍待證據。','PROVEN_SAME_BYTES':'已核對同一檔案與字面；原稿字型關聯及原生可編輯性仍待證據。','POSSIBLE_ALIAS':'僅名稱可能別名，未證實原稿字型。','UNIDENTIFIED':'字型身分未識別；來源不足或已變更，未核准替換。'}[report['state']]+report.get('reason',''))
            if registered_only:
                report.update(comparison_scope='REGISTERED_WINDOWS_SOURCE_ONLY',actual_qt_face_verified=False)
                if report['state'] in ('PROVEN_SAME_BYTES','PROVEN_SAME_EXTRACTED_FACE'):self.identity_label.setText('已核對所選Windows登錄檔案／字面與參考相同；程式目前實際採用字面、原稿關聯及用途授權仍待核對。')
                else:self.identity_label.setText(self.identity_label.text()+' 此結果僅指所選Windows登錄檔案，程式目前實際採用字面仍待核對。')
        self.start('核對目前來源／選取檔案與確切字面',lambda:identity_match(reference,candidate),loaded)

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
        pdf=QMessageBox.question(self,'PDF嵌入用途','授權是否也明確允許PDF嵌入？\nOpenType技術限制仍會獨立檢查；選否仍可核對點陣輸出。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes
        if QMessageBox.question(self,'確認授權範圍','只更新所選字面記錄；既有模板不會被自動改寫，需另建草稿重新套用並驗證。是否確認？',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
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

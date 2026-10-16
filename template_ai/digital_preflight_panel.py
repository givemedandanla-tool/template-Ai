"""An on-demand inspection section in the original right property panel."""
import copy,json,shutil,tempfile,threading
from pathlib import Path
from PySide6.QtCore import Qt,QRectF,QTimer
from PySide6.QtGui import QColor,QPen
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QPushButton,QCheckBox,QTableWidget,QTableWidgetItem,QPlainTextEdit,QLineEdit,QLayout
from shiboken6 import isValid
from .training_store import digest
from .worker_callbacks import JobCallbacks
from .digital_preflight import inspect_candidate
from .digital_output_proof import build_proof,region_images
from .candidate_results import selection_pin

LABELS={'PASS':'通過','BLOCKED':'阻擋','WARNING':'警告','NOT_CHECKED':'未檢查'}
NAMES={'PHYSICAL_SIZE':'實體尺寸／取樣','TRIM_BOUNDS':'成品裁切邊界','SAFE_ZONE':'安全區','TEXT_COMPLETE':'文字完整','FIXED_FONT':'固定字級／字型','HORIZONTAL_SCALE':'水平比例','OWNERSHIP':'人物／公司歸屬','OVERLAP':'物件重疊','CURRENT_WHOLE_CARD_GATE':'目前完整Gate','LOGO_SOURCE':'Logo來源／有效像素','ENCODED_FORMAT':'實際格式讀回','PDF_FONT_EMBEDDING':'PDF字型內嵌','ENCODED_BODY_COMPARISON':'卡片本體實測差異'}


class DigitalPreflightPanel(QWidget):
    def __init__(self,window):
        super().__init__(window.property_panel.widget());self.window=window;self.library=window.library;self.running=False;self.proof=None;self.proof_pin=None;self.review_receipt=None;self.cancel_event=threading.Event();self.serial=0;self.guides=[];self.detail=None;self.temporary=tempfile.TemporaryDirectory(prefix='template-ai-preflight-PREVIEW-')
        box=QVBoxLayout(self);box.setSizeConstraint(QLayout.SetMinimumSize);self.setMinimumWidth(400);self.status=QLabel('數位印前檢查尚未執行；比較檔不是正式輸出。');self.status.setWordWrap(True);box.addWidget(self.status)
        row=QHBoxLayout();row.addWidget(QLabel('目標格式'));self.format=QComboBox();self.format.addItems(['PNG','PDF','JPG']);row.addWidget(self.format);box.addLayout(row);self.settings=QLabel();self.settings.setWordWrap(True);box.addWidget(self.settings)
        self.overlay={}
        for key,label,checked in [('trim','成品裁切線',True),('safe','目前模板安全區',True),('page','印刷頁範圍（未另加出血）',False)]:
            check=QCheckBox(label);check.setChecked(checked);check.toggled.connect(self.draw_guides);self.overlay[key]=check;box.addWidget(check)
        self.table=QTableWidget(0,3);self.table.setHorizontalHeaderLabels(['檢查','結果','實測原因']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.SingleSelection);self.table.setMaximumHeight(250);self.table.setMinimumHeight(180);self.table.setColumnWidth(0,125);self.table.setColumnWidth(1,60);self.table.horizontalHeader().setStretchLastSection(True);self.table.itemSelectionChanged.connect(self.selected);box.addWidget(self.table)
        self.inspect_button=QPushButton('產生本格式實際比較檔');self.inspect_button.clicked.connect(self.inspect);box.addWidget(self.inspect_button);self.cancel_button=QPushButton('取消目前核對');self.cancel_button.clicked.connect(self.cancel);self.cancel_button.setEnabled(False);box.addWidget(self.cancel_button)
        self.objects=QComboBox();box.addWidget(self.objects);self.detail_button=QPushButton('選取物件／Logo局部放大比對');self.detail_button.clicked.connect(self.open_detail);box.addWidget(self.detail_button);self.locate_button=QPushButton('定位所選問題／既有修正入口');self.locate_button.clicked.connect(self.locate);box.addWidget(self.locate_button)
        self.review_widget=QWidget();review_box=QVBoxLayout(self.review_widget);self.review_actor=QLineEdit();self.review_actor.setPlaceholderText('本次格式核對者（具名）');self.review_evidence=QLineEdit();self.review_evidence.setPlaceholderText('實際來源／文字／Logo細節核對依據');self.review_consent=QCheckBox('我已對照此格式原尺寸快照的全部物件與Logo');self.review_button=QPushButton('套用本次格式核對');self.review_button.clicked.connect(self.confirm_review)
        for widget in (self.review_actor,self.review_evidence,self.review_consent,self.review_button):review_box.addWidget(widget)
        box.addWidget(self.review_widget);self.review_actor.textChanged.connect(self.reviewer_changed);self.review_evidence.textChanged.connect(self.reviewer_changed);self.review_consent.toggled.connect(self.clear_review)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);self.details.setMaximumHeight(150);box.addWidget(self.details)
        window.property_panel.widget().layout().insertWidget(0,self);window.inputs_invalidated.connect(self.invalidate);window.candidate_list.currentRowChanged.connect(self.invalidate);window.dpi.valueChanged.connect(self.invalidate);self.format.currentIndexChanged.connect(self.invalidate);window.tabs.currentChanged.connect(self.mode_changed);self.invalidate()
    def candidate(self):
        index=self.window.candidate_list.currentRow()
        if self.library.closed or self.window.library is not self.library or not 0<=index<len(self.window.candidates):raise ValueError('先選取目前專案的排版候選')
        return index,self.window.candidates[index]
    def pin(self):
        index,c=self.candidate();return digest(dict(selection=selection_pin(self.window,index),format=self.format.currentText(),dpi=self.window.dpi.value()))
    def matches(self,serial,pin):
        try:return serial==self.serial and pin==self.pin()
        except (ValueError,OSError):return False
    def candidate_rendered(self):
        try:changed=getattr(self,'render_pin',None)!=self.pin()
        except (ValueError,OSError):changed=True
        if changed:self.invalidate()
        else:self.draw_guides()
    def mode_changed(self,*args):self.mode_changed_visibility();self.draw_guides()
    def invalidate(self,*args):
        self.serial+=1;self.proof=None;self.proof_pin=None;self.review_receipt=None;self.review_consent.setChecked(False);self.table.setRowCount(0);self.details.clear();self.objects.blockSignals(True);self.objects.clear()
        try:
            index,c=self.candidate();self.settings.setText(f'{c.template.width_mm:g}×{c.template.height_mm:g} mm；{self.window.dpi.value()} DPI。頁範圍依目前尺寸，不假定印刷出血。')
            for p in c.items:self.objects.addItem(p.slot.owner+'／'+p.slot.kind+'／'+p.slot.id,p.slot.id)
            first=next((i for i,p in enumerate(c.items) if p.logo),0);self.objects.setCurrentIndex(first)
        except ValueError:self.settings.setText('尚無目前候選。')
        finally:self.objects.blockSignals(False)
        self.status.setText('目前未檢查；資料／尺寸／格式改變後不沿用舊結果。');self.detail_button.setEnabled(False)
        if self.detail and isValid(self.detail):self.detail.mark_stale()
        try:self.render_pin=self.pin()
        except (ValueError,OSError):self.render_pin=None
        self.draw_guides();self.mode_changed_visibility();self.review_widget.setVisible(self.format.currentText()!='PNG');self.update_export_state()
    def mode_changed_visibility(self):
        active=self.window.tabs.currentIndex()==2
        self.setVisible(active);self.window.property_panel.setMinimumWidth(440 if active else 220)
    def remove_guides(self):
        for item in self.guides:
            try:
                if item.scene():item.scene().removeItem(item)
            except RuntimeError:pass
        self.guides=[]
    def draw_guides(self,*args):
        self.remove_guides()
        if self.window.tabs.currentIndex()!=2:return
        try:_,c=self.candidate()
        except ValueError:return
        t=c.template;safe=t.safe_margin_mm
        for key,color,style,rect in [('trim','#b45309',Qt.DashLine,QRectF(0,0,t.width_mm,t.height_mm)),('page','#1d4ed8',Qt.DotLine,QRectF(0,0,t.width_mm,t.height_mm)),('safe','#15803d',Qt.DashDotLine,QRectF(safe,safe,t.width_mm-2*safe,t.height_mm-2*safe))]:
            if not self.overlay[key].isChecked() or rect.width()<0 or rect.height()<0:continue
            pen=QPen(QColor(color),1,style);pen.setCosmetic(True);item=self.window.output_canvas.scene().addRect(rect,pen);item.setZValue(20);item.setAcceptedMouseButtons(Qt.NoButton);item.setData(0,'PREFLIGHT_OVERLAY');self.guides.append(item)
    def set_running(self,value):
        self.running=value;self.inspect_button.setEnabled(not value);self.cancel_button.setEnabled(value);self.detail_button.setEnabled(not value and self.proof is not None);self.review_button.setEnabled(not value and self.proof is not None)
    def inspect(self):
        try:
            if self.running or self.window.busy:raise ValueError('原共享背景工作尚未結束，完成後再核對')
            _,candidate=self.candidate();candidate=copy.deepcopy(candidate);pin=self.pin();serial=self.serial;format=self.format.currentText();dpi=self.window.dpi.value();root=Path(self.temporary.name);self.cancel_event=threading.Event();cancel=self.cancel_event;self.proof=None;self.proof_pin=None;self.review_receipt=None;self.review_consent.setChecked(False);self.table.setRowCount(0);self.details.clear();self.set_running(True);self.status.setText('原背景工作正在實際編碼、讀回與比對；尚未宣稱成功。')
            def work():
                value=build_proof(candidate,format,dpi,root)
                if cancel.is_set():shutil.rmtree(Path(value['file']['path']).parent);raise ValueError('已取消，未採用比較結果')
                return value
            def done(value):
                if not isValid(self):return
                self.set_running(False)
                if not self.matches(serial,pin):self.status.setText('核對期間資料／尺寸／格式已改變，舊比較未採用。');return
                self.proof=value;self.proof_pin=pin;self.show_rows(value['rows']);self.detail_button.setEnabled(True);self.status.setText('本格式比較檔已實際保存並讀回；請核對局部細節。尚非正式輸出／印刷核准。');self.review_button.setEnabled(True);self.update_export_state()
            def failed(error):
                if isValid(self):self.set_running(False);self.status.setText('數位核對未確認：'+str(error))
            self.window.run_job('數位預檢／實際格式讀回',work,JobCallbacks(done,failed,cancel))
        except (ValueError,OSError) as error:self.status.setText(str(error));self.set_running(False)
    def clear_review(self,*args):self.review_receipt=None;self.update_export_state()
    def reviewer_changed(self,*args):self.review_consent.setChecked(False);self.clear_review()
    def update_export_state(self):
        try:
            index,c=self.candidate()
            from .candidate_results import current_assessment
            eligible=bool(self.proof and self.proof_pin==self.pin() and current_assessment(self.window,index)['formal_allowed'] and not any(r['status'] in ('BLOCKED','NOT_CHECKED') for r in self.proof['rows']))
            self.window.export_button.setEnabled(eligible and (self.format.currentText()=='PNG' or self.review_receipt is not None))
        except (ValueError,OSError):self.window.export_button.setEnabled(False)
    def review_form_pin(self):return digest(dict(context=self.pin(),actor=self.review_actor.text(),evidence=self.review_evidence.text(),consent=self.review_consent.isChecked()))
    def confirm_review(self):
        try:
            if self.running or self.window.busy or not self.proof or self.proof_pin!=self.pin() or not self.review_consent.isChecked():raise ValueError('需目前原尺寸格式快照、具名證據與明確核對')
            _,candidate=self.candidate();candidate=copy.deepcopy(candidate);proof=copy.deepcopy(self.proof);pin=self.review_form_pin();serial=self.serial;actor=self.review_actor.text();evidence=self.review_evidence.text();self.cancel_event=threading.Event();cancel=self.cancel_event;self.set_running(True)
            def work():
                from .digital_review import confirm
                receipt=confirm(candidate,proof,actor,evidence,True)
                if cancel.is_set():raise ValueError('已取消格式核對，未採用憑證')
                return receipt
            def done(receipt):
                self.set_running(False)
                if not self.matches(serial,self.proof_pin) or pin!=self.review_form_pin():self.status.setText('核對期間資料／具名／證據已變，舊憑證未採用。');return
                self.review_receipt=receipt;self.update_export_state();self.status.setText('已記住當次格式／尺寸核對；正式輸出仍須比對目前資料、實際像素與PDF結構。')
            def failed(error):self.set_running(False);self.status.setText('格式核對未確認：'+str(error));self.update_export_state()
            self.window.run_job('目前格式快照具名核對',work,JobCallbacks(done,failed,cancel))
        except (ValueError,OSError) as error:self.status.setText(str(error));self.set_running(False)
    def show_rows(self,rows):
        self.table.setSortingEnabled(False);self.table.setRowCount(len(rows))
        for i,r in enumerate(rows):
            for j,text in enumerate((NAMES.get(r['code'],r['code']),LABELS[r['status']],r['reason'])):
                item=QTableWidgetItem(text);item.setData(Qt.UserRole,copy.deepcopy(r));item.setToolTip(text);self.table.setItem(i,j,item)
    def selected(self):
        selected=self.table.selectionModel().selectedRows()
        if selected:self.details.setPlainText(json.dumps(self.table.item(selected[0].row(),0).data(Qt.UserRole),ensure_ascii=False,indent=2))
    def cancel(self):self.cancel_event.set();self.status.setText('已要求取消；等待原工作結束，未宣稱比較完成。')
    def close_session(self):
        self.cancel_event.set();self.proof=None;self.proof_pin=None;self.review_receipt=None
        if self.detail and isValid(self.detail):self.detail.close()
        self.temporary.cleanup()
    def locate(self):
        try:
            if not self.proof or self.proof_pin!=self.pin():raise ValueError('需目前有效比較與明確選中問題')
            selected=self.table.selectionModel().selectedRows()
            if not selected:raise ValueError('先明確選取檢查項目')
            row=self.table.item(selected[0].row(),0).data(Qt.UserRole);index,_=self.candidate()
            if not row['slot_ids']:self.window.diagnostic_report('candidate');return
            from .candidate_results import locate_problem
            locate_problem(self.window,dict(candidate_index=index,pin=selection_pin(self.window,index),slot_ids=row['slot_ids'],code=row['code'],route='candidate',owner='',kind='unknown',reason=row['reason']),open_input=False)
        except (ValueError,OSError) as error:self.status.setText(str(error))
    def open_detail(self):
        try:
            if self.running or self.window.busy or not self.proof or self.proof_pin!=self.pin():raise ValueError('先取得目前尺寸／格式的實際比較檔')
            _,candidate=self.candidate();candidate=copy.deepcopy(candidate);identity=self.objects.currentData();item=next(p for p in candidate.items if p.slot.id==identity);proof=copy.deepcopy(self.proof);pin=self.pin();serial=self.serial;self.cancel_event=threading.Event();cancel=self.cancel_event;self.set_running(True)
            def work():
                from .preflight_detail import source_picture
                a,b,detail=region_images(candidate,proof,identity);picture=source_picture(item)
                if cancel.is_set():raise ValueError('已取消局部比較，未開啟結果')
                return a,b,detail,picture
            def done(value):
                self.set_running(False)
                if not self.matches(serial,pin):self.status.setText('內容已改變，未開啟舊局部比較。');return
                from .preflight_detail import PreflightDetailDialog
                if self.detail and isValid(self.detail):self.detail.close();self.detail.deleteLater()
                a,b,detail,picture=value;self.detail=PreflightDetailDialog(self.window,item,proof,a,b,detail,picture);self.detail.show()
            def failed(error):self.set_running(False);self.status.setText('局部比較未確認：'+str(error))
            self.window.run_job('物件／Logo來源與實際輸出比較',work,JobCallbacks(done,failed,self.cancel_event))
        except (ValueError,OSError,StopIteration) as error:self.status.setText(str(error));self.set_running(False)


def open_preflight(window):
    window.tabs.setCurrentIndex(2)
    panel=getattr(window,'digital_preflight_panel',None)
    if panel is None:panel=DigitalPreflightPanel(window);window.digital_preflight_panel=panel
    window.property_panel.setVisible(True);panel.show();panel.draw_guides()
    QTimer.singleShot(0,panel,lambda:window.property_panel.verticalScrollBar().setValue(0))
    return panel

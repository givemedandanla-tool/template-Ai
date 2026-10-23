"""Read-only per-target format review using the same proof/detail/review engines."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gui import MainWindow
import copy,json,threading
from pathlib import Path
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QLineEdit,QCheckBox,QPushButton,QPlainTextEdit
from .training_store import digest
from .digital_preflight import scope
from .digital_output_proof import build_proof,region_images
from .digital_review import confirm
from .worker_callbacks import JobCallbacks


class BatchFormatReviewDialog(QDialog):
    def __init__(self,batch,row):
        super().__init__(batch);self.batch=batch;self.workflow=batch.owner.service;self.host_window: MainWindow=batch.host_window;self.row=copy.deepcopy(row);self.format=Path(row['path']).suffix[1:].upper();self.dpi=batch.dpi.value();self.proof=None;self.running=False;self.cancel=threading.Event();self.detail=None;self.setWindowTitle('此筆尺寸／格式實際快照核對');self.resize(850,690)
        box=QVBoxLayout(self);self.status=QLabel(f'僅此筆 {row["id"]}／{row["key"]}／{self.format}／{self.dpi} DPI；不核准其他尺寸、格式或資料。');self.status.setWordWrap(True);box.addWidget(self.status)
        self.inspect_button=QPushButton('產生此筆原尺寸實際格式快照');self.inspect_button.clicked.connect(self.inspect);box.addWidget(self.inspect_button);self.objects=QComboBox();box.addWidget(self.objects);self.detail_button=QPushButton('選取物件／Logo來源與實際輸出比對');self.detail_button.clicked.connect(self.open_detail);self.detail_button.setEnabled(False);box.addWidget(self.detail_button)
        self.actor=QLineEdit();self.actor.setPlaceholderText('具名格式核對者');self.evidence=QLineEdit();self.evidence.setPlaceholderText('此筆來源／文字／完整Logo及輸出細節核對依據');self.consent=QCheckBox('我已核對此筆原尺寸、格式、DPI的實際快照');box.addWidget(self.actor);box.addWidget(self.evidence);box.addWidget(self.consent)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);box.addWidget(self.details,1);buttons=QHBoxLayout();self.confirm_button=QPushButton('套用此筆格式核對');self.confirm_button.clicked.connect(self.confirm);buttons.addWidget(self.confirm_button);cancel=QPushButton('取消／關閉');cancel.clicked.connect(self.reject);buttons.addWidget(cancel);box.addLayout(buttons)
        self.candidate=self.current_candidate();self.expected=self.token()
        for p in self.candidate.items:self.objects.addItem(p.slot.owner+'／'+p.slot.kind+'／'+p.slot.id,p.slot.id)
        self.objects.setCurrentIndex(next((i for i,p in enumerate(self.candidate.items) if p.logo),0))
    def current_candidate(self):
        if not self.batch.owner.is_current() or self.batch.dpi.value()!=self.dpi:raise ValueError('來源／輸入／輸出DPI已改變，需重新核對本筆')
        row=next((r for r in self.batch.engine.items if r['id']==self.row['id']),None)
        if not row or row['key']!=self.row['key'] or row['template_id']!=self.row['template_id'] or row['mode']!='FINAL' or Path(row['path']).suffix[1:].upper()!=self.format:raise ValueError('目前逐檔目標已變更')
        entry=next(e for e in self.workflow.entries if e['key']==row['key']);candidate=self.workflow.revalidate(entry)
        if candidate.template.id!=row['template_id']:raise ValueError('目前選定候選已改變')
        return copy.deepcopy(candidate)
    def token(self):return digest(dict(row_id=self.row['id'],scope=scope(self.current_candidate(),self.format,self.dpi)))
    def current(self):
        try:return self.expected==self.token()
        except (ValueError,OSError,StopIteration):return False
    def set_running(self,value):self.running=value;self.inspect_button.setEnabled(not value);self.confirm_button.setEnabled(not value);self.detail_button.setEnabled(not value and self.proof is not None)
    def dispatch(self,label,work,done):
        if self.running or self.host_window.busy:self.status.setText('原共享背景工作尚未結束');return
        self.cancel=threading.Event();cancel=self.cancel;self.set_running(True)
        def run():
            result=work()
            if cancel.is_set():raise ValueError('已取消，本筆核對未採用')
            return result
        def finished(value):
            self.set_running(False)
            if not self.current():self.status.setText('目標／來源／格式已改變，舊結果未採用。');return
            done(value)
        def failed(error):self.set_running(False);self.status.setText('本筆未確認：'+str(error))
        self.host_window.run_job(label,run,JobCallbacks(finished,failed,cancel))
    def inspect(self):
        try:
            if not self.current():raise ValueError('目前目標已變，請重新由該筆開啟')
            candidate=copy.deepcopy(self.current_candidate());root=self.workflow.format_proof_directory();self.proof=None;self.consent.setChecked(False)
            def loaded(value):self.proof=value;self.details.setPlainText(json.dumps(value['rows'],ensure_ascii=False,indent=2));self.detail_button.setEnabled(True);self.status.setText('此筆實際格式已編碼讀回，仍需逐項對照後明確核對；尚未正式輸出。')
            self.dispatch('逐筆格式實際快照',lambda:build_proof(candidate,self.format,self.dpi,root),loaded)
        except (ValueError,OSError) as error:self.status.setText(str(error))
    def open_detail(self):
        try:
            if not self.proof or not self.current():raise ValueError('先取得目前此筆的實際格式快照')
            candidate=copy.deepcopy(self.current_candidate());proof=copy.deepcopy(self.proof);identity=self.objects.currentData();item=next(p for p in candidate.items if p.slot.id==identity)
            def work():
                from .preflight_detail import source_picture
                a,b,detail=region_images(candidate,proof,identity);return a,b,detail,source_picture(item)
            def opened(value):
                from .preflight_detail import PreflightDetailDialog
                if self.detail:self.detail.close();self.detail.deleteLater()
                a,b,detail,picture=value;self.detail=PreflightDetailDialog(self.host_window,item,proof,a,b,detail,picture,parent=self);self.detail.show()
            self.dispatch('逐筆物件來源／實際格式比較',work,opened)
        except (ValueError,OSError,StopIteration) as error:self.status.setText(str(error))
    def form_pin(self):return digest(dict(actor=self.actor.text(),evidence=self.evidence.text(),consent=self.consent.isChecked(),target=self.token()))
    def confirm(self):
        try:
            if not self.proof or not self.current() or not self.consent.isChecked():raise ValueError('需目前實際格式快照、具名證據與明確核對')
            candidate=self.current_candidate();proof=copy.deepcopy(self.proof);actor=self.actor.text();evidence=self.evidence.text();form=self.form_pin()
            def saved(receipt):
                if form!=self.form_pin():self.status.setText('具名／證據／確認已變，舊核對未採用。');return
                self.workflow.set_format_review(self.row['key'],self.format,self.dpi,receipt);self.batch.status.setText('僅此筆 '+self.row['id']+'／'+self.row['key']+'／'+self.format+'／'+str(self.dpi)+' DPI 已核對；檔案尚未輸出。')
                if self.detail:self.detail.close()
                self.accept()
            self.dispatch('逐筆格式目前範圍核對',lambda:confirm(candidate,proof,actor,evidence,True),saved)
        except (ValueError,OSError) as error:self.status.setText(str(error))
    def reject(self):
        if self.running:self.cancel.set();self.status.setText('等待原工作取消完成；未自動核對本筆。');return
        if self.detail:self.detail.close()
        super().reject()
    def closeEvent(self,event):
        if self.running:self.cancel.set();event.ignore();return
        super().closeEvent(event)

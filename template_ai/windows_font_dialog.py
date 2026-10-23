"""Explicit default-No handoff to the original Windows installation interface."""
import copy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QLineEdit,QCheckBox,QPushButton,QDialogButtonBox,QMessageBox

class WindowsFontWorkflowDialog(QDialog):
    def __init__(self,center):
        super().__init__(center);self.center=center;self.asset=copy.deepcopy(center.selected()['asset']);self.library=center.host_window.library;self.row_id=center.selected()['id'];self.running=False;self.receipt=None;self.setWindowTitle('安裝至Windows：交接原生字型介面');self.resize(780,520);box=QVBoxLayout(self)
        self.source=QLabel('選取來源：'+self.asset['path']+'\n內容身分：'+self.asset['hash']);self.source.setWordWrap(True);box.addWidget(self.source)
        self.source.setTextFormat(Qt.PlainText)
        note=QLabel('這是與程式內匯入分開的動作。此處只開啟Windows原生字型檢視器；安裝仍須在Windows確認來源、授權、目前使用者／全系統範圍及可能管理員權限。\n復原：在Windows設定的字型頁面核對實際安裝字型後移除；移除可能影響其他文件／使用者。未取得Windows結果前不標示安裝成功。');note.setWordWrap(True);box.addWidget(note)
        self.actor=QLineEdit();self.actor.setPlaceholderText('具名啟動者');self.basis=QLineEdit();self.basis.setPlaceholderText('有權提供及安裝此字型的來源／授權依據');box.addWidget(self.actor);box.addWidget(self.basis)
        self.consent=QCheckBox('我同意開啟此來源的Windows原生流程；安裝範圍與最終授權另在Windows確認');box.addWidget(self.consent);self.status=QLabel('尚未啟動；未安裝、未更動系統字型。');self.status.setWordWrap(True);box.addWidget(self.status)
        self.status.setTextFormat(Qt.PlainText)
        self.open_button=QPushButton('確認後開啟Windows原生字型檢視器');self.open_button.clicked.connect(self.begin);box.addWidget(self.open_button);buttons=QDialogButtonBox(QDialogButtonBox.Close);buttons.rejected.connect(self.reject);box.addWidget(buttons)
    def begin(self):
        if self.running or self.center.busy or self.center.host_window.busy:return
        row=self.center.selected()
        if not row or row['id']!=self.row_id or self.center.host_window.library is not self.library:self.status.setText('來源選取／專案已變更，請重新開啟');return
        if not self.consent.isChecked() or not self.actor.text().strip() or not self.basis.text().strip():self.status.setText('需具名、來源授權依據及獨立明確同意');return
        if QMessageBox.question(self,'只啟動此來源的Windows流程','來源：'+self.asset['path']+'\n只開啟原生檢視器，不代表已安裝。實際安裝範圍、權限與來源授權仍須在Windows確認。是否啟動？',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        from .windows_font_workflow import open_windows_font_workflow
        actor,basis=self.actor.text(),self.basis.text();self.running=True
        for control in (self.actor,self.basis,self.consent,self.open_button):control.setEnabled(False)
        self.status.setText('核對目前字型並啟動原生流程中；尚無安裝結果。')
        def loaded(receipt):self.receipt=receipt;self.center.windows_receipt=receipt;self.status.setText(receipt['reason'])
        def work():return open_windows_font_workflow(self.asset,actor,basis,True)
        # Existing centre worker owns completion; restore the dialog on both outcomes.
        def completed(value):
            if 'error' not in value:loaded(value['receipt'])
            else:self.status.setText('未啟動：'+value['error'])
            self.running=False
            for control in (self.actor,self.basis,self.consent,self.open_button):control.setEnabled(True)
        def guarded():
            try:return dict(receipt=work())
            except (ValueError,OSError) as error:return dict(error=str(error))
        self.center.start('獨立Windows字型流程／目前來源重新核對',guarded,completed)
    def reject(self):
        if self.running:self.status.setText('等待目前來源核對與啟動結果；尚未宣稱安裝成功。');return
        super().reject()
    def closeEvent(self,event):
        if self.running:event.ignore();return
        super().closeEvent(event)

"""Manual findings on the original major-review page, using its explicit consent."""
from PySide6.QtWidgets import QHBoxLayout,QLabel,QComboBox,QPlainTextEdit
from .customers import digest


class MajorFindingPageMixin:
    def init_finding_controls(self,layout):
        self.finding_plan=None;self.finding_pin=None;self.finding_action=None
        bar=QHBoxLayout();self.finding=QComboBox()
        for label,value in [('確認無誤（新事實）','CHECKED_OK'),('修正後重新核准（新事實）','REAPPROVED'),('確認錯誤待修','ERROR_NEEDS_FIX'),('待人工核對','NEEDS_MANUAL'),('阻擋','BLOCKED'),('無法判定','UNKNOWN'),('核准範圍排除、保持隔離','EXCLUDED_HOLD')]:self.finding.addItem(label,value)
        bar.addWidget(self.finding);self.button(bar,'預覽本件人工結論',self.preview_finding);self.button(bar,'預覽重新開啟此件',self.preview_reopen);layout.addLayout(bar)
        layout.addWidget(QLabel('本件原稿／新事實／修正或排除的可核對證據（必填）'));self.finding_evidence=QPlainTextEdit();self.finding_evidence.setMaximumHeight(70);layout.addWidget(self.finding_evidence)
        self.finding.currentIndexChanged.connect(self.invalidate);self.finding_evidence.textChanged.connect(self.invalidate)
    def finding_unit(self):
        rows=self.selected_units()
        if len(rows)!=1 or rows[0]['kind']!='QUALITY_WORK_QUARANTINE':raise ValueError('請明確選取一件本案作品；模板與模型隔離另行核准')
        return rows[0]
    def finding_context_pin(self):
        row=self.finding_unit();return digest(dict(case_id=self.case_id(),unit_id=row['id'],finding=self.finding.currentData(),evidence=self.finding_evidence.toPlainText(),actor=self.dialog.actor.text(),reason=self.dialog.reason.text()))
    def preview_finding(self):
        d=self.dialog;row=self.finding_unit();pin=self.finding_context_pin();self.invalidate();self.pending_action='FINDING';self.finding_action='FINDING'
        def loaded(value):
            if self.finding_context_pin()!=pin:d.status.setText('本件結論預覽期間選取／證據已變更，未採用');return
            self.finding_plan=value;self.finding_pin=pin;d.details.setPlainText('作品 '+value['work_id']+'／審核版次 '+str(value['unit_revision'])+'\n本次人工結論：'+value['finding']+'\n目前來源事實版次 '+str(value['facts_revision'])+'\n'+('只解除此件作品隔離；模板版次與模型品質不自動解除。' if value['release_work'] else '保存本件結論，仍暫停可信使用；範圍排除不等於此件安全。')+'\n證據：'+value['evidence']);d.status.setText('本件原／新結論預覽完成；需下方具名與明確確認後才保存。')
        d.request('MAJOR_FINDING_PLAN',dict(case_id=self.case_id(),unit_id=row['id'],finding=self.finding.currentData(),evidence=self.finding_evidence.toPlainText()),loaded)
    def preview_reopen(self):
        d=self.dialog;row=self.finding_unit();pin=self.finding_context_pin();self.invalidate();self.pending_action='FINDING';self.finding_action='REOPEN'
        def loaded(value):
            if self.finding_context_pin()!=pin:d.status.setText('重新開啟預覽期間本件已變更，未採用');return
            self.finding_plan=value;self.finding_pin=pin;d.details.setPlainText('重新開啟作品 '+value['work_id']+'／審核版次 '+str(value['unit_revision'])+'\n將恢復REVIEW_REQUIRED，保留舊解除／排除歷史。\n目前事實版次 '+str(value['facts_revision'])+'；解除需再保存與確認更新的完整事實，不沿用舊核准。');d.status.setText('重新開啟範圍預覽完成；明確確認後才重新隔離。')
        d.request('MAJOR_REOPEN_PLAN',dict(case_id=self.case_id(),unit_id=row['id']),loaded)
    def confirm_finding(self):
        d=self.dialog
        if not self.finding_plan or self.finding_pin!=self.finding_context_pin() or not d.consent.isChecked() or not d.actor.text().strip() or not d.reason.text().strip():raise ValueError('需目前本件結論預覽、具名、原因與明確確認')
        command='MAJOR_REOPEN_UNIT' if self.finding_action=='REOPEN' else 'MAJOR_CONFIRM_FINDING';value=self.finding_plan
        def saved(row):
            self.finding_plan=None;self.finding_pin=None;d.consent.setChecked(False);self.load_case(0)
        d.request(command,dict(value=value,actor=d.actor.text(),reason=d.reason.text(),approved=True),saved)

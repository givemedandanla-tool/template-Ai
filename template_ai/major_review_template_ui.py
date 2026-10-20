"""Exact template review, source correction drafts and scoped completion in the same page."""
import json
from PySide6.QtWidgets import QHBoxLayout,QVBoxLayout,QLabel,QLineEdit,QCheckBox,QGridLayout
from .customers import digest
from .major_template_review import CHECKS


class MajorTemplatePageMixin:
    def init_template_controls(self,layout):
        self.template_plan=None;self.template_plan_pin=None;self.template_action=None
        bar=QHBoxLayout();self.template_target=QLineEdit();self.template_target.setPlaceholderText('確切模板版本ID；選原版或已保存修正草稿');bar.addWidget(self.template_target);self.button(bar,'使用目前模板列的版本ID',self.use_template_unit);layout.addLayout(bar)
        self.template_checks={};grid=QGridLayout();labels=['原稿欄位映射','人物／公司歸屬','完整Logo','本尺寸合法資產','固定字級與下限','安全區與幾何','語意無損']
        for i,(key,label) in enumerate(zip(CHECKS,labels)):box=QCheckBox(label);self.template_checks[key]=box;grid.addWidget(box,i//4,i%4);box.toggled.connect(self.invalidate)
        layout.addLayout(grid);self.template_evidence=QLineEdit();self.template_evidence.setPlaceholderText('本確切版本／尺寸的原稿與整卡核對證據');layout.addWidget(self.template_evidence)
        self.source_bindings=QLineEdit();self.source_bindings.setPlaceholderText('選填模板物件ID→原稿物件ID的JSON；留空只提出唯一對應供核對');layout.addWidget(self.source_bindings)
        bar=QHBoxLayout();self.button(bar,'預覽此版本目前輸入的完整重驗',self.preview_template);self.draft_name=QLineEdit();self.draft_name.setPlaceholderText('以目前人工原稿建立修正草稿名稱');bar.addWidget(self.draft_name);self.draft_bindings=QLineEdit();self.draft_bindings.setPlaceholderText('人物→公司port JSON，例如 {}');self.draft_bindings.setText('{}');bar.addWidget(self.draft_bindings);self.button(bar,'預覽以新原稿真值建立草稿',self.preview_repair);layout.addLayout(bar)
        notice=QLabel('模板重驗使用目前排版輸入／Logo映射，依此版本真實尺寸計算；來源、字型、語意或資產仍有阻擋就不解除。修正草稿從目前已核實原稿重建，舊訓練參考保留在版本歷史，仍須另行核准。');notice.setWordWrap(True);layout.addWidget(notice)
        bar=QHBoxLayout();self.button(bar,'預覽結束指定重審範圍',self.preview_closure);layout.addLayout(bar)
        for field in [self.template_target,self.template_evidence,self.source_bindings,self.draft_name,self.draft_bindings]:field.textChanged.connect(self.invalidate)
    def template_unit(self):
        rows=self.selected_units()
        if len(rows)!=1 or rows[0]['kind']!='QUALITY_TEMPLATE_QUARANTINE':raise ValueError('請明確選取一件本案模板版本；來源作品先走本件事實重審')
        return rows[0]
    def use_template_unit(self):
        row=self.template_unit();self.template_target.setText(row.get('approved_template_id') or row['template_id'])
    def template_context_pin(self,action):
        d=self.dialog;value=dict(action=action,case_id=self.case_id(),actor=d.actor.text(),reason=d.reason.text())
        if action!='CLOSE':value.update(unit_id=self.template_unit()['id'],target=self.template_target.text(),evidence=self.template_evidence.text(),checks={k:b.isChecked() for k,b in self.template_checks.items()},slot_bindings=self.source_bindings.text(),draft_name=self.draft_name.text(),company_bindings=self.draft_bindings.text(),generation=d.host_window.generation,inputs=d.host_window.input_data())
        return digest(value)
    def preview_template(self):
        d=self.dialog;unit=self.template_unit();pin=self.template_context_pin('TEMPLATE');self.invalidate();self.pending_action='TEMPLATE';self.template_action='TEMPLATE';people,companies,logos=d.host_window.input_data();bindings=json.loads(self.source_bindings.text()) if self.source_bindings.text().strip() else None
        def loaded(value):
            if self.template_context_pin('TEMPLATE')!=pin:d.status.setText('模板重驗期間版本／映射／輸入已變更，舊結果未採用');return
            self.template_plan=value;self.template_plan_pin=pin;lines=['此確切版本完整重驗：'+('可明確核對解除本版本' if value['can_release'] else '仍阻擋'),'模板 '+value['template_id']+'／v'+str(value['template_version']),'原稿／模板一對一映射：']+[a+' → '+b for a,b in value['slot_bindings'].items()]
            lines+=['仍須各自印前／輸出授權，模型品質未解除。']+value['blockers'];lines.extend(c['id']+'：'+c['status']+'／'+c.get('reason','') for c in value['conditions']);d.details.setPlainText('\n'.join(lines));d.status.setText('已保存此版本的完整預檢；核對差異與阻擋後明確確認。')
        d.request('MAJOR_TEMPLATE_PLAN',dict(case_id=self.case_id(),unit_id=unit['id'],template_id=self.template_target.text().strip(),people=people,companies=companies,logos=logos,manual_checks={k:b.isChecked() for k,b in self.template_checks.items()},evidence=self.template_evidence.text(),slot_bindings=bindings),loaded)
    def preview_repair(self):
        d=self.dialog;unit=self.template_unit();pin=self.template_context_pin('REPAIR');self.invalidate();self.pending_action='TEMPLATE';self.template_action='REPAIR';bindings=json.loads(self.draft_bindings.text())
        def loaded(value):
            if self.template_context_pin('REPAIR')!=pin:d.status.setText('原稿修正預覽期間內容已變更，未採用');return
            self.template_plan=value;self.template_plan_pin=pin;t=value['template'];d.details.setPlainText('明確從目前完整人工事實／原稿標記建立修正草稿。\n來源作品 '+value['source_work_pins']['work_id']+'／r'+str(value['source_work_pins']['work_revision'])+'\n新草稿 '+t['id']+'／v'+str(t['version'])+'／'+str(t['width_mm'])+'×'+str(t['height_mm'])+' mm\n舊學習參考保留於版本歷史，不沿用舊模型幾何；尚未發布或解除此模板隔離。');d.status.setText('目前原稿修正草稿預覽完成，明確確認後才保存新版本。')
        d.request('MAJOR_REPAIR_DRAFT_PLAN',dict(case_id=self.case_id(),unit_id=unit['id'],name=self.draft_name.text(),company_bindings=bindings),loaded)
    def preview_closure(self):
        d=self.dialog;pin=self.template_context_pin('CLOSE');self.invalidate();self.pending_action='TEMPLATE';self.template_action='CLOSE'
        def loaded(value):
            if self.template_context_pin('CLOSE')!=pin:d.status.setText('結案預覽期間案件／核對者已改，未採用');return
            self.template_plan=value;self.template_plan_pin=pin;d.details.setPlainText(f'只結束已封存的指定案件範圍：{value["total"]}項、目前核准{value["reapproved"]}、核准排除但仍不可信{value["excluded_still_untrusted"]}。\n'+('可明確結案。' if value['can_close'] else '仍有阻擋，不能結案。')+'\n未知依賴與新增未掃描項不算全庫安全，模型未去污染／未取得獨立品質或正式輸出核准。\n新增已知未掃描作品：'+','.join(value['new_known_unscanned_work_ids'])+'\n'+'\n'.join(str(row) for row in value['blockers']));d.status.setText('指定範圍結案預覽已讀回；不是全庫安全或模型品質核准。')
        d.request('MAJOR_CLOSURE_PLAN',dict(case_id=self.case_id()),loaded)
    def confirm_template_action(self):
        d=self.dialog;action=self.template_action
        if not self.template_plan or self.template_plan_pin!=self.template_context_pin(action) or not d.consent.isChecked() or not d.actor.text().strip() or not d.reason.text().strip():raise ValueError('需目前明確版本／範圍預覽、具名、原因與確認')
        value=self.template_plan
        if action=='TEMPLATE' and not value['can_release'] or action=='CLOSE' and not value['can_close']:raise ValueError('此版本／範圍仍受阻擋，不可核准')
        command={'TEMPLATE':'MAJOR_CONFIRM_TEMPLATE','REPAIR':'MAJOR_CREATE_REPAIR_DRAFT','CLOSE':'MAJOR_CLOSE_SCOPE'}[action]
        def saved(result):
            self.template_plan=None;self.template_plan_pin=None;d.consent.setChecked(False)
            if action=='REPAIR':self.template_target.setText(result['template']['id']);d.status.setText('已保存並讀回目前原稿修正草稿與舊參考歷史；仍需本版本完整重驗。')
            else:self.load_case(0)
        d.request(command,dict(value=value,actor=d.actor.text(),reason=d.reason.text(),approved=True),saved)

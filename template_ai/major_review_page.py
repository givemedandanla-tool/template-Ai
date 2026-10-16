"""A source-evidence page in the existing repair workbench and worker transport."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QPlainTextEdit,QLineEdit,QPushButton,QTableWidget,QTableWidgetItem
from .customers import digest
from .major_review_job_ui import MajorJobPageMixin
from .major_review_finding_ui import MajorFindingPageMixin

STATES={'UNSCANNED':'未掃描','UNKNOWN':'無法判定','REAPPROVED':'修正後重新核准','CHECKED_OK':'確認無誤','ERROR_NEEDS_FIX':'確認錯誤待修','NEEDS_MANUAL':'待人工','BLOCKED':'阻擋','PROCESSING':'正在分析','INTERRUPTED':'中斷待明確接續','CANCELLED':'已取消／尚未完成','EXCLUDED_VERIFIED':'核准排除／仍暫停信任','STALE_REVIEW':'重審憑證已過期'}


class MajorReviewPage(MajorFindingPageMixin,MajorJobPageMixin,QWidget):
    def __init__(self,dialog):
        super().__init__(dialog);self.dialog=dialog;self.plan=None;self.plan_pin=None;self.offset=0;self.case_offset=0;self.rows=[];self.case=None
        layout=QVBoxLayout(self);notice=QLabel('發現重大共通錯誤 → 以目前選定的既有問題發起重審。先核對來源、正反例與影響範圍；開始隔離不等於完成重審，未知依賴不算全庫安全。');notice.setWordWrap(True);layout.addWidget(notice)
        bar=QHBoxLayout();bar.addWidget(QLabel('問題類別'));self.category=QComboBox();self.category.addItems(['人物／欄位歸屬','公司完整Logo','作品切分／漏件','雜訊規則','客戶／版型版本','實體尺寸','來源／解析器','模型／語意','其他具名問題']);bar.addWidget(self.category);self.severity=QComboBox();self.severity.addItem('重大','CRITICAL');self.severity.addItem('高風險','HIGH');bar.addWidget(self.severity);layout.addLayout(bar)
        self.correct=QPlainTextEdit();self.wrong=QPlainTextEdit()
        for title,field in [('可核對的正確例子',self.correct),('可核對的錯誤例子',self.wrong)]:layout.addWidget(QLabel(title));field.setMaximumHeight(70);layout.addWidget(field);field.textChanged.connect(self.invalidate)
        bar=QHBoxLayout();self.button(bar,'預覽影響／版本與隔離策略',self.preview);self.button(bar,'查看原待修問題／來源證據',lambda:dialog.tabs.setCurrentIndex(0));layout.addLayout(bar)
        self.coverage=QLabel('尚未檢索；選取一個既有原稿／例外問題，再預覽。');self.coverage.setWordWrap(True);layout.addWidget(self.coverage)
        bar=QHBoxLayout();self.query=QLineEdit();self.query.setPlaceholderText('來源證據案件／類別／ID');bar.addWidget(self.query);self.cases=QComboBox();bar.addWidget(self.cases,1);self.button(bar,'查詢持久案件',lambda:self.list_cases(0));self.button(bar,'前50案',lambda:self.list_cases(-50));self.button(bar,'後50案',lambda:self.list_cases(50));layout.addLayout(bar)
        bar=QHBoxLayout();self.unit_query=QLineEdit();self.unit_query.setPlaceholderText('此案來源／作品／模板版本／狀態／原因');bar.addWidget(self.unit_query);self.button(bar,'讀回案件／原批次仍保留',lambda:self.load_case(0));self.button(bar,'前50項',lambda:self.load_case(-50));self.button(bar,'後50項',lambda:self.load_case(50));layout.addLayout(bar)
        self.counts=QLabel('尚未讀回持久案件；未宣稱已完成。');self.counts.setWordWrap(True);layout.addWidget(self.counts);self.table=QTableWidget(0,5);self.table.setHorizontalHeaderLabels(['實體種類／確切ID','來源／版次','原核准／目前狀態','重審狀態','原因']);self.table.setSelectionBehavior(QTableWidget.SelectRows);layout.addWidget(self.table)
        bar=QHBoxLayout();self.button(bar,'定位原作品／既有來源事實編輯器',self.locate);layout.addLayout(bar)
        for field in [self.category,self.severity]:field.currentIndexChanged.connect(self.invalidate)
        dialog.actor.textChanged.connect(self.invalidate);dialog.reason.textChanged.connect(self.invalidate)
        self.cases.currentIndexChanged.connect(lambda *_:setattr(self,'offset',0))
        self.init_job_controls(layout)
        self.init_finding_controls(layout)
    def button(self,bar,title,action):
        button=QPushButton(title);button.clicked.connect(lambda:self.dialog.guard(action));bar.addWidget(button);return button
    def invalidate(self,*_):
        self.plan=None;self.plan_pin=None
        self.job_plan=None;self.job_pin=None
        self.finding_plan=None;self.finding_pin=None
        if hasattr(self.dialog,'consent'):self.dialog.consent.setChecked(False)
    def form(self):return dict(issue_id=self.dialog.issue_id(),category=self.category.currentText(),correct_example=self.correct.toPlainText(),wrong_example=self.wrong.toPlainText(),severity=self.severity.currentData())
    def pin(self):return digest(dict(form=self.form(),actor=self.dialog.actor.text(),reason=self.dialog.reason.text()))
    def preview(self):
        d=self.dialog;form=self.form();pin=self.pin();self.invalidate();self.coverage.setText('檢索既有依賴與歷史中；尚未完成預檢或啟動隔離。')
        self.pending_action='CASE'
        def loaded(plan):
            if self.pin()!=pin:d.status.setText('預檢期間問題／證據／核對者已變更；舊影響清單未採用');return
            self.plan=plan;self.plan_pin=pin;c=plan['coverage'];self.coverage.setText(f'已檢索本機登錄 {c["registered_sources"]} 個來源、{c["registered_works"]} 件作品；目前可追溯受影響 {c["affected_sources"]} 個來源、{c["affected_works"]} 件作品、{c["affected_templates"]} 個模板版本。未記錄與歷史失聯依賴仍未知。')
            lines=['確認將對明確關聯作品／模板暫停信任；原稿、已發布版本及舊結案紀錄保留。','使用者證據：'+plan['category']+'／'+plan['severity'],'正確：'+plan['correct_example'],'錯誤：'+plan['wrong_example']]
            for row in plan['rows']:lines.append('作品 '+row['work_id']+'／來源 '+row['source_id']+'／標記版次 '+str(row['pins']['work_revision'])+'／原事實版次 '+str(row['facts_revision'])+'／'+row['precheck'])
            for row in plan['templates']:lines.append('模板 '+row['template_id']+'／版本 '+str(row['version']))
            for row in plan.get('component_fingerprints',[]):lines.append('暫停信任實際組件 '+row['kind']+'／指紋 '+row['key']+'；改名稱／新管線ID不解除，仍需獨立品質驗證')
            for identity in plan.get('pipeline_ids',[]):lines.append('暫停依賴管線 '+identity+'；未宣稱模型已去污染')
            d.details.setPlainText('\n'.join(lines));d.status.setText('影響預覽完成，尚未啟動。核對未知範圍及下方明確確認，再按「確認並保存所選預覽」。')
        d.request('MAJOR_PLAN',form,loaded)
    def confirm(self):
        if self.pending_action=='FINDING':return self.confirm_finding()
        if self.pending_action=='JOB':return self.confirm_job()
        d=self.dialog
        if not self.plan or self.pin()!=self.plan_pin or not d.consent.isChecked() or not d.actor.text().strip() or not d.reason.text().strip():raise ValueError('需目前預覽、來源正反例、具名核對者、原因與明確確認')
        plan=self.plan;pin=self.plan_pin
        def saved(case):
            self.plan=None;self.plan_pin=None;d.consent.setChecked(False);self.case=case;self.cases.addItem(case['plan']['category']+'／'+case['id'],case['id']);self.cases.setCurrentIndex(self.cases.count()-1);d.status.setText('已持久讀回重大重審與隔離；尚未重審完成，模型未宣稱已去污染。');self.load_case(0)
        d.request('MAJOR_CONFIRM',dict(plan=plan,actor=d.actor.text(),reason=d.reason.text(),approved=True),saved)
    def list_cases(self,delta):
        self.case_offset=max(0,self.case_offset+delta)
        def loaded(value):
            self.cases.clear()
            for row in value['rows']:self.cases.addItem(row['category']+'／'+row['state']+'／'+row['id'],row['id'])
            self.counts.setText(f'來源證據案件：本頁 {len(value["rows"])}／總 {value["total"]}；逐案讀回後才顯示有效狀態。')
        self.dialog.request('MAJOR_CASES',dict(offset=self.case_offset,query=self.query.text()),loaded)
    def load_case(self,delta):
        case_id=self.cases.currentData()
        if not case_id:raise ValueError('先查詢並明確選取持久案件')
        self.offset=max(0,self.offset+delta);query=self.unit_query.text()
        def loaded(value):
            self.case=value['case'];self.rows=value['rows'];summary=value['summary'];counts=summary['states'];self.counts.setText('本案工作／模板任務 '+str(summary['total'])+'，已檢查 '+str(summary['checked'])+'；'+'、'.join(STATES.get(k,k)+' '+str(v) for k,v in counts.items())+f'。符合搜尋 {value["total"]}／本頁 {len(self.rows)}；未知依賴不算全庫安全。')
            c=value['coverage'];self.coverage.setText(f'此案快照：登錄來源 {c["registered_sources"]}／作品 {c["registered_works"]}；受影響來源 {c["affected_sources"]}／作品 {c["affected_works"]}／模板版本 {c["affected_templates"]}。這是已記錄依賴；未知範圍未宣稱安全。')
            self.table.setRowCount(len(self.rows))
            for i,row in enumerate(self.rows):
                work=row['kind']=='QUALITY_WORK_QUARANTINE';values=[('作品 ' if work else '模板 ')+(row.get('work_id') or row.get('template_id')),(row.get('source_id','')+'／'+str(row.get('pins',{}).get('work_revision',row.get('version','')))),str(row.get('facts_revision',''))+'／'+row['state'],STATES.get(row['effective_state'],row['effective_state']),row.get('reason','')]
                for j,text in enumerate(values):item=QTableWidgetItem(text);item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable);item.setData(Qt.UserRole,dict(id=row['id'],kind=row['kind'],revision=row['revision']));item.setToolTip(text);self.table.setItem(i,j,item)
            for i,width in enumerate([265,220,170,130,230]):self.table.setColumnWidth(i,width)
            self.table.horizontalHeader().setStretchLastSection(True)
            self.dialog.status.setText('已讀回本案實際逐項狀態；完整結案與模型品質仍需各自驗證。')
        self.dialog.request('MAJOR_STATUS',dict(case_id=case_id,offset=self.offset,query=query),loaded)
    def locate(self):
        index=self.table.currentRow()
        if not 0<=index<len(self.rows):raise ValueError('請明確選取本頁作品')
        ref=self.table.item(index,0).data(Qt.UserRole);row=next(r for r in self.rows if r['kind']==ref['kind'] and r['id']==ref['id'] and r['revision']==ref['revision'])
        if row['kind']!='QUALITY_WORK_QUARANTINE':raise ValueError('模板版本保留待審；請先由其來源作品核對，再使用既有模板版本工具')
        panel=self.dialog.panel;panel.table.clearSelection();panel.recheck_item=row;panel.source_facts();self.dialog.status.setText('已定位原作品與既有來源事實；保存新人工事實後回來讀回案件，未自動解除隔離。')

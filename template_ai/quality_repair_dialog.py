"""Seven native repair pages over the existing QualityPanel request/worker path."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QTabWidget,QWidget,QScrollArea,QLabel,QLineEdit,QPlainTextEdit,QComboBox,QCheckBox,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView)
from shiboken6 import isValid
from .quality_repairs import ROOT_LAYERS
from .quality_repair_gates import STAGES

TITLES=('待修問題','根因與影響','候選修復計畫','增量處理進度','前後品質差異','可核准／阻擋原因','回退／恢復')
ROOT_NAMES=('來源不完整','作品切分','原生文字效果','本機OCR','欄位／人物歸屬','雜訊規則','完整複合Logo','尺寸專用Logo資產','客戶／版型版本','模型退步','人工真值有爭議')


class QualityRepairDialog(QDialog):
    def __init__(self,panel):
        super().__init__(panel);self.panel=panel;self.window=panel.window;self.library=panel.library;self.store=panel.store
        self.setWindowTitle('局部修復、品質驗證與安全回退');self.resize(1180,880)
        self.issue=None;self.pending=None;self.issue_offset=0;self.work_offset=0;self.job_offset=0;self.roles={};self.catalogs=[]
        outer=QVBoxLayout(self);self.status=QLabel('先核對原稿與人工真值；原問題修好、歷史重審及獨立品質驗收分開判定。');self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);outer.addWidget(self.status)
        bar=QHBoxLayout();self.actor=QLineEdit();self.actor.setPlaceholderText('具名核對者');self.reason=QLineEdit();self.reason.setPlaceholderText('本次核對、適用邊界與負面案例依據');bar.addWidget(self.actor);bar.addWidget(self.reason,1);outer.addLayout(bar);self.actor.textChanged.connect(self.invalidate);self.reason.textChanged.connect(self.invalidate)
        self.tabs=QTabWidget();outer.addWidget(self.tabs,1);self.forms=[]
        for title in TITLES:
            scroll=QScrollArea();scroll.setWidgetResizable(True);page=QWidget();form=QFormLayout(page);scroll.setWidget(page);self.tabs.addTab(scroll,title);self.forms.append(form)
        self.issue_form();self.root_form();self.candidate_form();self.progress_form();self.comparison_form();self.approval_form();self.recovery_form()
        self.details=QPlainTextEdit();self.details.setReadOnly(True);self.details.setMaximumHeight(175);outer.addWidget(self.details)
        for combo in self.findChildren(QComboBox):combo.currentIndexChanged.connect(self.invalidate)
        self.consent=QCheckBox('我已核對此預覽的實際來源、exact版本、影響與阻擋；明確確認本次操作');outer.addWidget(self.consent)
        bar=QHBoxLayout();self.confirm_button=QPushButton('確認並保存所選預覽');self.confirm_button.clicked.connect(lambda:self.guard(self.confirm));bar.addWidget(self.confirm_button)
        close=QPushButton('關閉');close.clicked.connect(self.reject);bar.addWidget(close);outer.addLayout(bar)
        boundary=QLabel('修復只變更分析推薦與版本憑證；原稿、人工事實、客戶主檔與已發布版型仍走各自核准流程。未證明原生Illustrator、實機效能或生產品質。');boundary.setWordWrap(True);outer.addWidget(boundary)

    def reject(self):
        if self.panel.loading:
            self.status.setText('背景核對尚未讀回；請先取消該核對或等待完成，再關閉。');return
        super().reject()

    def invalidate(self,*_):
        previous=self.pending;self.pending=None
        if hasattr(self,'consent'):self.consent.setChecked(False)
        if previous is not None and hasattr(self,'status'):self.status.setText('輸入或版本選擇已改變，舊預覽已失效；請重新核對後再保存。')

    def guard(self,action):
        try:action()
        except (ValueError,KeyError,OSError,TypeError) as error:self.status.setText(str(error))

    def request(self,command,payload,callback):
        self.status.setText('正在本機核對持久版本；完成讀回前不宣稱成功。')
        def done(value):
            if not isValid(self):return
            callback(value)
        def failed(error):
            if not isValid(self):return
            self.pending=None;self.consent.setChecked(False);self.status.setText('操作未確認，請重新核對；未自動重試：'+str(error))
        self.panel.request(command,payload,done,on_error=failed)

    def button(self,form,label,action):
        button=QPushButton(label);button.clicked.connect(lambda:self.guard(action));form.addRow(button);return button

    def line(self,form,label):
        field=QLineEdit();field.textChanged.connect(self.invalidate);form.addRow(label,field);return field

    def picker(self,form,label,kind):
        row=QHBoxLayout();query=QLineEdit();query.setPlaceholderText('全庫搜尋名稱／版本；每頁50筆');combo=QComboBox();combo.addItem('請明確選擇',None);row.addWidget(query);row.addWidget(combo,1)
        page={'offset':0}
        def load(delta=0):
            offset=max(0,page['offset']+delta) if delta else 0
            def loaded(result):
                previous=combo.currentData();combo.clear();combo.addItem('請明確選擇',None);page['offset']=result['offset']
                for record in result['rows']:
                    if kind=='AUTO_JOB' and record['label']!='SEMANTIC_REPAIR_CANDIDATE':continue
                    combo.addItem((record['label'] or record['state'] or kind)+' · '+record['id'][:12],record['id'])
                index=combo.findData(previous);combo.setCurrentIndex(max(0,index));self.status.setText(f"已載入 {result['offset']+1} 起最多50筆，共 {result['total']} 筆；未自動選定版本。")
            self.request('LIST',dict(kind=kind,offset=offset,query=query.text()),loaded)
        for text,delta in (('搜尋',0),('前50',-50),('後50',50)):
            button=QPushButton(text);button.clicked.connect(lambda checked=False,d=delta:self.guard(lambda:load(d)));row.addWidget(button)
        combo.currentIndexChanged.connect(self.invalidate);form.addRow(label,row);self.catalogs.append(combo);return combo

    def identity(self,combo):
        value=combo.currentData()
        if not value:raise ValueError('先明確選擇具名的實際版本／憑證')
        return value

    def issue_id(self):
        if not self.issue:raise ValueError('先在待修問題選取實際問題')
        return self.issue['id']

    def review_id(self):
        identity=self.identity(self.review);row=self.store.get('QUALITY_REPAIR_ROOT_REVIEW',identity)
        if not row or row['plan']['issue_id']!=self.issue_id():raise ValueError('根因核對需與目前選取的問題相同')
        return identity

    def candidate_id(self):
        identity=self.identity(self.candidate);row=self.store.get('QUALITY_REPAIR_PIPELINE_CANDIDATE',identity)
        if not row or row['plan']['issue_id']!=self.issue_id():raise ValueError('候選需與目前選取的問題相同')
        return identity

    def select_record(self,combo,identity,label):
        index=combo.findData(identity)
        if index<0:combo.addItem(label+' · '+identity[:12],identity);index=combo.count()-1
        combo.setCurrentIndex(index)

    def summary(self,value):
        lines=[]
        for key,label in (('hypothesis','根因候選'),('evidence','核對依據'),('operation','本次動作'),('stage','本次階段')):
            if key in value:lines.append(label+'：'+str(value[key]))
        if 'work_roles' in value:
            lines.append('明列訓練／驗證來源：'+str(len(value['work_roles'])))
            for wid,role in list(value['work_roles'].items())[:20]:lines.append(self.library.artwork(wid)['name']+'：'+role)
        if 'batch_eligible' in value:
            for row in value['rows'][:20]:lines.append('規則 '+row['rule']['literal']+'：'+row['risk']+'；支持／反例 '+str(len(row['rule']['positive_examples']))+'/'+str(len(row['rule']['counterexamples'])))
        if value.get('pipeline_id'):
            pipeline=self.store.get('QUALITY_PIPELINE',value['pipeline_id'])
            lines.append('實際管線：'+(pipeline['name'] if pipeline else '已失聯')+' · '+value['pipeline_id'][:12])
        for key,label in (('state','狀態'),('conclusion','判定'),('passed','本階段通過'),('can_prepare_candidate','可準備候選'),('candidate_decision_eligible','可核准品質'),('independence_claim','獨立性主張'),('quality_pass','品質通過'),('production_active','已正式採用')):
            if key in value:lines.append(label+'：'+str(value[key]))
        for key,label in (('blockers','阻擋'),('errors','錯誤'),('current_errors','目前證據失效')):
            lines.extend(label+'：'+str(item) for item in value.get(key,[])[:30])
        for key,label in (('fixed_cases','原有已消除錯誤'),('new_cases','新增錯誤'),('unresolved_cases','仍存在錯誤'),('class_regressions','類別退步'),('pending_historical_rechecks','歷史待重審')):
            if key in value:lines.append(label+'：'+str(len(value[key])))
        for side,result in value.get('results',{}).items():
            if not isinstance(result,dict) or 'statistics' not in result:continue
            lines.append(('基準' if side=='BASELINE' else '候選')+'：'+str(result.get('quality_gate')))
            for domain,detail in result['statistics']['domains'].items():
                for kind,row in detail['classes'].items():
                    count=row.get('descriptive_counts');lines.append(domain+' / '+kind+'：'+row['state']+('；TP/FP/FN '+str([count[k] for k in ('tp','fp','fn')]) if count else '；mm／正例 '+str(row['gold_objects'])))
        dependency=value.get('dependencies') or value.get('source_impact')
        if dependency:
            lines.append('已知影響作品：'+str(len(dependency.get('affected_work_ids',dependency.get('rows',[])))))
            lines.append('未登錄／未掃描的歷史依賴仍屬未知，不能當作安全或已完成。')
        return '\n'.join(lines) or '已讀回明列來源與版本。請確認操作範圍；這不代表訓練、品質或正式採用已通過。'

    def preview(self,command,payload,kind,extra=None):
        def loaded(value):
            self.pending=(kind,value,extra or {});self.consent.setChecked(False);self.details.setPlainText(self.summary(value));self.status.setText('預覽已完成；核對來源、版本、阻擋與適用範圍後再明確保存。')
        self.request(command,payload,loaded)

    def confirm(self):
        if not self.pending or not self.consent.isChecked() or not self.actor.text().strip() or not self.reason.text().strip():raise ValueError('需有預覽、具名核對者、原因與未預設的明確確認')
        kind,plan,extra=self.pending;payload=dict(kind=kind,plan=plan,actor=self.actor.text(),reason=self.reason.text(),approved=True,**extra)
        command='CONFIRM' if kind in ('PROTOCOL','REPORT') else 'REPAIR_CONFIRM'
        def saved(row):
            self.pending=None;self.consent.setChecked(False);self.status.setText('已保存並讀回本次憑證；其他階段與正式採用仍需各自通過。')
            if kind=='ISSUE':self.issue=row;self.select_record(self.issues,row['id'],row['reason'])
            if kind=='ROOT':self.select_record(self.review,row['id'],row['plan']['hypothesis'])
            if kind=='TRAIN':self.select_record(self.job,row['id'],'局部訓練待啟動')
            if kind=='CANDIDATE':self.select_record(self.candidate,row['id'],row['reason'])
            if kind=='PROTOCOL':self.select_record(self.protocol,row['id'],row['scope']['name'])
            if kind=='REPORT':self.select_record(self.report,row['id'],'已保存固定兩側比較')
            if kind=='GATE':self.select_record(self.previous_gate,row['id'],row['plan']['stage']);self.select_record(self.final_gate,row['id'],row['plan']['stage'])
            if kind=='IMPACT':self.select_record(self.impact_review,row['id'],row['reason'])
            if kind=='DECISION':self.select_record(self.decision,row['id'],row['reason'])
            if kind=='RELEASE':self.details.setPlainText('已原子保存正式版本與部署憑證；新來源使用核准的凍結管線，佇列沿用各工作原本核對版本。')
        self.request(command,payload,saved)

    def issue_form(self):
        form=self.forms[0];self.issues=self.picker(form,'待修問題','QUALITY_REPAIR_ISSUE');self.button(form,'讀取選中問題',self.load_issue)
        self.source_work=self.line(form,'來源作品（入口或目前畫布定位，無需輸入識別碼）');self.source_work.setReadOnly(True);self.source_name=QLabel();self.source_name.setTextFormat(Qt.PlainText);self.source_name.setWordWrap(True);form.addRow('具名來源',self.source_name);self.source_work.textChanged.connect(self.source_identity_changed);self.description=self.line(form,'原稿問題、重現現象與負面案例')
        self.button(form,'帶入目前畫布作品',lambda:self.source_work.setText(self.window.work['id'] if self.window.work else ''))
        self.button(form,'預覽原稿問題登錄',lambda:self.source_issue('SOURCE_FACTS',self.source_work.text()))
        self.button(form,'開啟原稿事實核對（保留未儲存編輯）',self.source_facts)

    def load_issue(self):
        def loaded(row):self.issue=row;self.source_work.setText(row['evidence'].get('work_id') or '');self.details.setPlainText(row['reason']+'\n'+row['evidence'].get('description',''));self.status.setText('已選取實際問題；請另外選同一問題的根因核對與候選。')
        self.request('REPAIR_GET',dict(kind='QUALITY_REPAIR_ISSUE',id=self.identity(self.issues)),loaded)

    def source_identity_changed(self,identity):
        if not identity:
            self.source_name.setText((self.issue or {}).get('evidence',{}).get('source_path') or '尚未選定具名作品');return
        try:
            work=self.library.artwork(identity);source=self.library.source(work['source_id']);self.source_name.setText(work['name']+' ／ '+Path(source['original_path']).name)
        except (ValueError,KeyError):self.source_name.setText('來源作品失聯，請重新核對')

    def source_issue(self,origin,origin_id):
        self.preview('REPAIR_SOURCE_PLAN',dict(work_id=self.source_work.text(),origin=origin,origin_id=origin_id,description=self.description.text()),'ISSUE')

    def root_form(self):
        form=self.forms[1];self.layer=QComboBox()
        for code,name in zip(ROOT_LAYERS,ROOT_NAMES):self.layer.addItem(name,code)
        self.layer.insertItem(0,'請明確選擇根因候選',None);self.layer.setCurrentIndex(0);form.addRow('根因候選（不是已證實根因）',self.layer)
        self.hypothesis=self.line(form,'發生條件與根因假設');self.evidence=self.line(form,'人工原稿、正確答案與負面案例依據')
        self.original_reviewed=QCheckBox('我已核對實際原稿');self.truth_reviewed=QCheckBox('我已核對人工正確答案');form.addRow(self.original_reviewed);form.addRow(self.truth_reviewed);self.original_reviewed.toggled.connect(self.invalidate);self.truth_reviewed.toggled.connect(self.invalidate);self.layer.currentIndexChanged.connect(self.invalidate)
        self.button(form,'預覽根因及阻擋',lambda:self.preview('REPAIR_ROOT_PLAN',dict(identity=self.issue_id(),layer=self.layer.currentData(),hypothesis=self.hypothesis.text(),evidence=self.evidence.text(),original_reviewed=self.original_reviewed.isChecked(),truth_reviewed=self.truth_reviewed.isChecked()),'ROOT'))
        self.review=self.picker(form,'同一問題的根因核對憑證','QUALITY_REPAIR_ROOT_REVIEW')
        self.component=QComboBox();self.component.addItems(['SOURCE','PARSER','MODEL','RULE']);form.addRow('影響依據',self.component);self.rule=self.picker(form,'實際規則（僅規則影響）','RULE')
        self.button(form,'讀取已知／潛在／未知影響',self.load_impact)
        self.impact_nodes=[];self.impact_offset=0;self.impact_table=QTableWidget(0,3);self.impact_table.setHorizontalHeaderLabels(['影響類型','具名來源／作品／版本','直接／潛在／未知']);self.impact_table.setEditTriggers(QTableWidget.NoEditTriggers);self.impact_table.setMinimumHeight(150);self.impact_table.setMaximumHeight(180);self.impact_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);form.addRow(self.impact_table)
        self.button(form,'前50項影響',lambda:self.impact_page(-50));self.button(form,'後50項影響',lambda:self.impact_page(50))
        self.truth_set=self.picker(form,'重新人工核對後的同來源新版真值集','QUALITY_SET')
        self.button(form,'預覽新版人工真值接續（不解除HOLDOUT曝露）',lambda:self.preview('REPAIR_TRUTH_PLAN',dict(issue_id=self.issue_id(),dataset_id=self.identity(self.truth_set),reason=self.reason.text()),'TRUTH'))

    def load_impact(self):
        def loaded(row):
            dependency=row['dependencies'];self.impact_nodes=dependency.get('nodes') or [dict(key='WORK:'+r['work_id'],dependency_match=r['dependency_match']) for r in dependency.get('rows',[])]
            self.impact_offset=0;self.impact_page(0);self.details.setPlainText(self.summary(row));self.status.setText('已知影響分頁顯示；未登錄與未掃描的歷史仍未知。')
        self.request('REPAIR_ISSUE_IMPACT',dict(identity=self.issue_id(),component=self.component.currentText(),rule_id=self.rule.currentData()),loaded)

    def impact_page(self,delta):
        self.impact_offset=max(0,self.impact_offset+delta);rows=self.impact_nodes[self.impact_offset:self.impact_offset+50];self.impact_table.setRowCount(len(rows))
        labels=dict(SOURCE='來源',WORK='作品',MODEL='模型版本',RULE='規則版本',SAMPLE='樣本',DATASET='資料集',TEMPLATE='版型版本',STYLE='版型家族',CUSTOMER='客戶')
        for index,row in enumerate(rows):
            kind,identity=row['key'].split(':',1);identity=identity.split(':',1)[0];name=identity[:12]
            query={'WORK':('SELECT name FROM artworks WHERE id=?',identity),'SOURCE':('SELECT original_path FROM sources WHERE id=?',identity),'TEMPLATE':("SELECT json_extract(payload,'$.name') FROM templates WHERE id=?",identity),'CUSTOMER':('SELECT name FROM customers WHERE id=?',identity)}.get(kind)
            if query:
                value=self.library.db.execute(query[0],(query[1],)).fetchone()
                if value:name=Path(value[0]).name if kind=='SOURCE' else value[0]
            for column,text in enumerate((labels.get(kind,kind),name,row['dependency_match'])):self.impact_table.setItem(index,column,QTableWidgetItem(str(text)))

    def candidate_form(self):
        form=self.forms[2];self.work_query=self.line(form,'全庫搜尋訓練來源／角色');self.work_table=QTableWidget(0,3);self.work_table.setHorizontalHeaderLabels(['來源／作品','人工事實與角色','本次明列用途']);self.work_table.setMinimumHeight(180);self.work_table.setMaximumHeight(225);self.work_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);form.addRow(self.work_table)
        self.button(form,'搜尋來源（前50筆）',lambda:self.work_page(0));self.button(form,'前50筆來源',lambda:self.work_page(-50));self.button(form,'後50筆來源',lambda:self.work_page(50))
        self.button(form,'預覽局部語意訓練計畫',lambda:self.preview('REPAIR_SEMANTIC_PLAN',dict(work_roles=dict(self.roles)),'TRAIN',dict(review_id=self.review_id())))
        self.detail_rule=QCheckBox('我已逐條詳閱HIGH風險規則的原稿、支持與反例');form.addRow(self.detail_rule);self.detail_rule.toggled.connect(self.invalidate)
        self.button(form,'預覽所選既有規則的獨立候選核對',lambda:self.preview('REPAIR_RULE_PLAN',dict(rule_ids=[self.identity(self.rule)]),'RULE',dict(review_id=self.review_id(),detail_reviewed=self.detail_rule.isChecked())))
        self.button(form,'使用既有版本設定選擇模型／已核准隔離規則',self.version_setup)
        self.pipeline=self.picker(form,'實際凍結候選管線（在既有品質設定保存）','QUALITY_PIPELINE')
        self.button(form,'預覽登錄exact修復候選',lambda:self.preview('REPAIR_CANDIDATE_PLAN',dict(review_id=self.review_id(),pipeline_id=self.identity(self.pipeline)),'CANDIDATE'))
        self.candidate=self.picker(form,'同問題的exact修復候選','QUALITY_REPAIR_PIPELINE_CANDIDATE')

    def version_setup(self):
        from .quality_setup import QualitySetupDialog
        dialog=QualitySetupDialog(self)
        for index in range(dialog.tabs.count()):dialog.tabs.setTabVisible(index,index==3)
        dialog.tabs.setCurrentIndex(3)
        try:dialog.exec()
        finally:dialog.deleteLater()

    def previewed(self,kind,value):
        if kind is not None:raise ValueError('此入口只保存實際可執行版本；人工真值及品質仍走既有獨立流程')
        if not value.get('manifest') or not value.get('id'):raise ValueError('沒有可讀回的實際管線版本')
        self.select_record(self.pipeline,value['id'],value['name']);self.details.setPlainText('已保存並選取實際可執行版本：'+value['name']+' · '+value['id'][:12]+'\n下一步核對同問題根因與候選登錄；這不是品質或正式採用通過。');self.status.setText('已保存凍結版本；規則仍保持隔離，需完成順序品質與明確採用。')

    def work_page(self,delta):
        offset=max(0,self.work_offset+delta) if delta else 0
        def loaded(page):
            self.work_offset=page['offset'];self.work_table.setRowCount(len(page['rows']))
            for index,row in enumerate(page['rows']):
                self.work_table.setItem(index,0,QTableWidgetItem(row['name']+' · '+Path(row['source_path']).name));self.work_table.setItem(index,1,QTableWidgetItem(('人工已確認' if row['facts_state']=='CONFIRMED' else '人工事實待核對')+' / '+{'HOLDOUT':'保留集（禁訓練）','TRAIN':'訓練來源','VALIDATION':'驗證對照'}.get(row['locked_role'],'尚未分派')))
                combo=QComboBox();combo.addItem('未選擇',None)
                for role in ('TRAIN','VALIDATION'):combo.addItem('本次訓練' if role=='TRAIN' else '本次驗證',role);combo.model().item(combo.count()-1).setEnabled(role in row['allowed_roles'])
                selected=self.roles.get(row['id'])
                if selected not in row['allowed_roles']:self.roles.pop(row['id'],None);selected=None
                combo.setCurrentIndex(max(0,combo.findData(selected)));combo.setToolTip('\n'.join(row['blockers']));combo.currentIndexChanged.connect(lambda _,c=combo,wid=row['id']:self.set_role(wid,c.currentData()));self.work_table.setCellWidget(index,2,combo)
            self.status.setText(f"來源第{page['offset']+1}起最多50筆／共{page['total']}；已明列{len(self.roles)}件。保留集／家族衝突與未確認資料停用。")
        self.request('REPAIR_WORKS',dict(offset=offset,query=self.work_query.text()),loaded)

    def set_role(self,identity,role):
        if role:self.roles[identity]=role
        else:self.roles.pop(identity,None)
        self.pending=None;self.consent.setChecked(False)

    def progress_form(self):
        form=self.forms[3];self.job=self.picker(form,'實際局部訓練工作','AUTO_JOB');self.progress=QPlainTextEdit();self.progress.setReadOnly(True);form.addRow(self.progress)
        self.button(form,'重新讀取進度',lambda:self.job_page(0));self.button(form,'前50來源進度',lambda:self.job_page(-50));self.button(form,'後50來源進度',lambda:self.job_page(50))
        self.button(form,'明確送入共用背景佇列',self.enqueue_train);self.button(form,'開啟共用暫停／取消／恢復控制',self.runtime_controls)

    def job_page(self,delta):
        offset=max(0,self.job_offset+delta) if delta else 0
        def loaded(row):
            self.job_offset=row['offset'];phases=dict(READY='等待明確啟動',RUNNING='處理中',COMPLETED='已完成',CANCELLED='已取消',PAUSED_RESOURCES='因資源暫停',INTERRUPTED='中斷後待明確接續')
            model_state='候選已產生，尚未品質驗收' if row['model_id'] else '尚未產生候選模型；來源核對與訓練分開顯示'
            actions=dict(SOURCE_VERIFIED_NOT_YET_TRAINED='來源已核對（模型另列）',MODEL_CREATED_NOT_ACTIVATED='候選模型已建立，未正式採用')
            lines=['工作：'+phases.get(row['phase'],'狀態待核對')+'（'+str(row['phase'])+'）','模型：'+model_state]
            for item in row['items']:lines.append(item['work_name']+'：'+('成功' if item['state']=='SUCCESS' else '待核對／處理中')+' / '+str(item.get('error') or actions.get(item.get('action'),'等待來源核對')))
            self.progress.setPlainText('\n'.join(lines));self.status.setText('來源核對完成與模型候選產生分開顯示；不是品質通過。')
        if self.library.closed or self.window.library is not self.library:raise ValueError('環境已改變，未套用舊進度')
        from .quality_repair_commands import job_status
        loaded(job_status(self.library,self.identity(self.job),offset))

    def enqueue_train(self):
        if not self.consent.isChecked() or not self.actor.text().strip():raise ValueError('需具名並明確勾選啟動／續跑選定範圍')
        job=self.store.get('AUTO_JOB',self.identity(self.job))
        if not job or job.get('operation')!='SEMANTIC_REPAIR_CANDIDATE':raise ValueError('只送入選中的局部修復訓練工作')
        root=self.store.get('QUALITY_REPAIR_ROOT_REVIEW',job['root_review_id'])
        if not root or root['plan']['issue_id']!=self.issue_id():raise ValueError('訓練工作必須屬於同一個目前選取問題，不能借用其他問題的工作')
        self.window.execution_queue.submit('AUTO_JOB',job,self.actor.text());self.consent.setChecked(False);self.status.setText('已送入既有公平佇列；進度與暫停／取消沿用背景控制。')

    def runtime_controls(self):
        from .runtime_panel import RuntimePanel
        dialog=RuntimePanel(self.window)
        try:dialog.exec()
        finally:dialog.deleteLater()

    def comparison_form(self):
        form=self.forms[4];self.stage=QComboBox()
        for code,name in zip(STAGES,('一：原問題重現與修復','二：未受影響關鍵對照','三：新的獨立保留集驗收')):self.stage.addItem(name,code)
        self.stage.currentIndexChanged.connect(self.invalidate);form.addRow('不可跳過的驗證順序',self.stage);self.dataset=self.picker(form,'明列本階段來源及人工真值集','QUALITY_SET');self.policy=self.picker(form,'明確品質政策','QUALITY_POLICY');self.previous_gate=self.picker(form,'直接前一階段PASS（第一階段不選）','QUALITY_REPAIR_GATE')
        self.button(form,'預覽固定雙側階段試驗',lambda:self.preview('REPAIR_STAGE_PLAN',dict(candidate_id=self.candidate_id(),stage=self.stage.currentData(),dataset_id=self.identity(self.dataset),policy_id=self.identity(self.policy),reason=self.reason.text(),previous_gate_id=self.previous_gate.currentData()),'PROTOCOL'))
        self.protocol=self.picker(form,'本階段固定試驗','QUALITY_PROTOCOL');self.button(form,'將固定雙側送入共用評估佇列',self.enqueue_pair)
        self.button(form,'讀取前後品質差異並預覽保存',lambda:self.preview('COMPARE',dict(protocol_id=self.identity(self.protocol)),'REPORT'))
        self.report=self.picker(form,'已保存固定差異報告','QUALITY_PAIR_REPORT');self.button(form,'預覽本階段PASS／FAIL與阻擋憑證',lambda:self.preview('REPAIR_GATE_PLAN',dict(report_id=self.identity(self.report)),'GATE'))
        self.button(form,'預覽明確品質接受（仍不正式啟用）',lambda:self.preview('REPAIR_DECISION_PLAN',dict(report_id=self.identity(self.report)),'DECISION'))
        self.button(form,'在原品質中心檢視逐案對照（揭露規則仍適用）',self.open_quality)

    def enqueue_pair(self):
        protocol=self.store.get('QUALITY_PROTOCOL',self.identity(self.protocol));binding=protocol['scope'].get('repair_stage') or {}
        if binding.get('candidate_id')!=self.candidate_id():raise ValueError('只送入同一問題、同一候選預先核對的階段試驗')
        self.select_record(self.panel.protocols,self.identity(self.protocol),'修復固定階段');self.panel.actor.setText(self.actor.text());self.panel.enqueue_pair()

    def open_quality(self):
        self.select_record(self.panel.protocols,self.identity(self.protocol),'修復固定階段');self.reject()

    def approval_form(self):
        form=self.forms[5];self.final_gate=self.picker(form,'完整三階段的最後PASS憑證','QUALITY_REPAIR_GATE');self.decision=self.picker(form,'同一新獨立驗收的明確品質接受','QUALITY_VERSION_DECISION')
        self.button(form,'預覽必要歷史影響／待重審／未知範圍',lambda:self.preview('REPAIR_IMPACT_PLAN',dict(candidate_id=self.candidate_id()),'IMPACT'));self.impact_review=self.picker(form,'已明確核對的歷史影響','QUALITY_REPAIR_IMPACT_REVIEW')
        self.operation=QComboBox();self.operation.addItem('採用已通過完整修復流程的候選','DEPLOY');self.operation.addItem('首次建立可信基準（已有修復問題時停用）','INITIAL_BASELINE');form.addRow('正式推薦版本動作',self.operation)
        self.button(form,'預覽正式採用及所有阻擋',self.release_plan);self.button(form,'讀回目前正式版本／失效原因',self.release_status)

    def release_plan(self):
        def status(row):self.preview('REPAIR_RELEASE_PLAN',dict(decision_id=self.identity(self.decision),expected_revision=row['active_revision'],operation=self.operation.currentData(),gate_id=self.final_gate.currentData(),impact_review_id=self.impact_review.currentData()),'RELEASE')
        self.request('REPAIR_STATUS',{},status)

    def release_status(self):
        def loaded(row):self.last_release_status=row;self.details.setPlainText('正式版本：'+str((row['pin'] or {}).get('pipeline_id') or '未建立或需重新核對')+'\n'+'\n'.join(row['errors'])+'\n不自動信任任何舊版；發布與原稿核准仍獨立。');self.status.setText('已讀回目前正式指標與可信證據。')
        self.request('REPAIR_STATUS',{},loaded)

    def recovery_form(self):
        form=self.forms[6];self.old_event=self.picker(form,'實際已部署的歷史版本','QUALITY_PIPELINE_DEPLOYMENT');self.button(form,'預覽可信舊版本與回退阻擋',self.rollback_plan);self.button(form,'讀取目前恢復／阻擋狀態',self.release_status)
        form.addRow(QLabel('舊版本也必須仍有有效品質、來源、規則及歷史重審憑證；已撤回或有重大錯誤時維持阻擋。備份恢復後需明確重新核對，不自動啟動。'))

    def rollback_plan(self):
        self.request('REPAIR_STATUS',{},lambda row:self.preview('REPAIR_ROLLBACK_PLAN',dict(target_event_id=self.identity(self.old_event),expected_revision=row['active_revision']),'RELEASE'))

    def source_facts(self):
        wid=self.source_work.text() or (self.issue or {}).get('evidence',{}).get('work_id')
        if not wid:raise ValueError('先選具名來源作品')
        parent=self.panel.parentWidget()
        while parent is not None and not hasattr(parent,'facts_panel'):parent=parent.parentWidget()
        if parent is not None and parent.facts_panel.loaded and parent.facts_panel.loaded['id']!=wid and parent.facts_panel.has_pending_observation():raise ValueError('來源事實仍有未套用人工內容，保留原編輯，不切換')
        from .training_navigation import require_clean_navigation,locate_work
        require_clean_navigation(self.window);locate_work(self.window,wid)
        if parent is not None:
            if not parent.facts_panel.loaded or parent.facts_panel.loaded['id']!=wid:parent.facts_panel.focus(wid,[])
            parent.tabs.setCurrentWidget(parent.facts_panel)
        self.reject()

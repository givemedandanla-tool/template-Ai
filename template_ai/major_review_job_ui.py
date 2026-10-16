"""Selected source reanalysis UI on the original repair page and FIFO dispatcher."""
from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import QHBoxLayout,QLabel,QComboBox,QTableWidget
from .customers import digest
from .model import KINDS


class MajorJobPageMixin:
    def init_job_controls(self,layout):
        self.job_plan=None;self.job_pin=None;self.pending_action='CASE';self.analysis_job=None
        self.table.setSelectionMode(QTableWidget.ExtendedSelection);self.table.itemSelectionChanged.connect(self.invalidate)
        bar=QHBoxLayout();self.button(bar,'預覽所選作品的增量重分析',self.preview_job);self.button(bar,'原／新判定與分析原因',self.show_analysis);layout.addLayout(bar)
        bar=QHBoxLayout();self.analysis_jobs=QComboBox();bar.addWidget(self.analysis_jobs,1);self.button(bar,'讀回本案分析工作（最多50）',self.list_jobs);self.button(bar,'明確接續已選分析',self.resume_job);self.button(bar,'停止已選分析／尚未開始項',self.cancel_job);layout.addLayout(bar)
        self.job_notice=QLabel('分析沿用原持久共享佇列；尚未排程，不自動訓練、核准或解除隔離。');self.job_notice.setWordWrap(True);layout.addWidget(self.job_notice)
        self.cases.currentIndexChanged.connect(self.invalidate);self.analysis_jobs.currentIndexChanged.connect(self.invalidate)
        self.cases.currentIndexChanged.connect(self.job_case_changed)
        self.dialog.window.execution_queue.progress.connect(self.job_progress)
        self.dialog.window.execution_queue.changed.connect(self.job_queue_changed)
    def case_id(self):
        identity=self.cases.currentData()
        if not self.case or self.case['id']!=identity:raise ValueError('請先明確選取並讀回此持久案件')
        return identity
    def job_case_changed(self,*_):
        self.analysis_job=None;self.analysis_jobs.clear()
    def selected_units(self):
        rows=[]
        for selected in self.table.selectionModel().selectedRows():
            ref=self.table.item(selected.row(),0).data(Qt.UserRole);rows.append(next(row for row in self.rows if row['id']==ref['id'] and row['kind']==ref['kind'] and row['revision']==ref['revision']))
        return rows
    def selected_work_ids(self):
        rows=self.selected_units()
        if not rows or any(row['kind']!='QUALITY_WORK_QUARANTINE' for row in rows):raise ValueError('請明確選取1至200件本案作品；模板版本另走人工核對')
        return sorted(row['work_id'] for row in rows)
    def job_context_pin(self):return digest(dict(case_id=self.case_id(),work_ids=self.selected_work_ids(),actor=self.dialog.actor.text(),reason=self.dialog.reason.text()))
    def preview_job(self):
        d=self.dialog;case_id=self.case_id();work_ids=self.selected_work_ids();pin=self.job_context_pin();self.invalidate();self.pending_action='JOB'
        def loaded(value):
            if self.job_context_pin()!=pin:d.status.setText('增量預覽期間選取／核對者已變更，舊工作範圍未採用');return
            self.job_plan=value;self.job_pin=pin;lines=['確認後將保存所選增量工作並送入原公平佇列，實際重分析。','只保存原引擎未核實建議與舊判定對照；不訓練模型、不改原稿或事實、不解除隔離。',f'確切作品 {len(value["work_ids"])}／來源 {len(value["items"])}；其餘案件項目未計完成。']
            for item in value['items']:lines.append('來源 '+item['source_id']+'／SHA-256 '+item['source_hash']+'／作品 '+','.join(item['work_scope']))
            d.details.setPlainText('\n'.join(lines));d.status.setText('增量範圍預覽完成；勾選下方明確確認並保存，才加入原共享佇列。')
        d.request('MAJOR_JOB_PLAN',dict(case_id=case_id,work_ids=work_ids),loaded)
    def confirm_job(self):
        d=self.dialog
        if not self.job_plan or self.job_pin!=self.job_context_pin() or not d.consent.isChecked() or not d.actor.text().strip() or not d.reason.text().strip():raise ValueError('需目前所選增量預覽、具名核對者、原因與明確確認')
        value=self.job_plan
        def saved(job):
            self.job_plan=None;self.job_pin=None;d.consent.setChecked(False);self.analysis_job=job;self.analysis_jobs.addItem('來源重分析／'+job['phase']+'／'+job['id'],job['id']);self.analysis_jobs.setCurrentIndex(self.analysis_jobs.count()-1)
            try:d.window.execution_queue.submit('AUTO_JOB',job,job['actor']);self.job_notice.setText('已保存工作 '+job['id']+' 並送入原公平佇列；等待實際執行，不代表重審通過。')
            except ValueError as error:self.job_notice.setText('已保存工作 '+job['id']+'，尚未成功加入佇列：'+str(error))
        d.request('MAJOR_CREATE_JOB',dict(value=value,actor=d.actor.text(),reason=d.reason.text(),approved=True),saved)
    def job_progress(self,request_id,job):
        if not self.analysis_job or job['id']!=self.analysis_job['id'] or job.get('scope',{}).get('case_id')!=self.cases.currentData():return
        self.analysis_job=job;items=job['items'];saved=sum(item['state']=='SUCCESS' for item in items);failed=sum(item['state']=='FAILED' for item in items)
        self.job_notice.setText(f'原共享工作實際進度：來源已保存 {saved}/{len(items)}、失敗 {failed}；目前 {job["phase"]}。分析完成仍需人工核對／受控解除隔離。')
    def job_queue_changed(self):
        if not self.isVisible() or not self.analysis_job:return
        def refresh():
            d=self.dialog
            if d.window.busy or d.panel.loading or not self.analysis_job or self.analysis_job['scope']['case_id']!=self.cases.currentData():return
            def loaded(value):
                job=value['job'];self.analysis_job=job;saved=sum(item['state']=='SUCCESS' for item in job['items']);self.job_notice.setText(f'已讀回原共享工作：{value["effective_phase"]}，來源已保存 {saved}/{len(job["items"])}；重審仍待人工核對。')
            d.request('MAJOR_JOB',dict(case_id=self.cases.currentData(),job_id=self.analysis_job['id']),loaded)
        QTimer.singleShot(0,refresh)
    def list_jobs(self):
        case_id=self.case_id()
        def loaded(value):
            self.analysis_jobs.clear()
            for row in value['rows']:self.analysis_jobs.addItem('來源重分析／'+row['phase']+'／'+row['id'],row['id'])
            self.job_notice.setText(f'已讀回本案保存的分析工作 {len(value["rows"])}/{value["total"]}；重新啟動不自動接續。')
        self.dialog.request('MAJOR_JOBS',dict(case_id=case_id,offset=0),loaded)
    def resume_job(self):
        d=self.dialog;case_id=self.case_id();identity=self.analysis_jobs.currentData()
        if not identity or not d.consent.isChecked() or not d.actor.text().strip():raise ValueError('先讀回已選工作，具名並明確確認接續；不自動沿用上次程式階段')
        actor=d.actor.text()
        def loaded(value):
            job=value['job']
            if value['effective_phase']=='COMPLETED':self.job_notice.setText('此分析已完成落盤，請讀回原／新對照；重審尚須人工核對。');return
            self.analysis_job=job;d.window.execution_queue.submit('AUTO_JOB',job,actor,retry_failed=True);d.consent.setChecked(False);self.job_notice.setText('已明確提交原共享佇列接續；仍重新核對原工作範圍、來源與目前人工版本。')
        d.request('MAJOR_JOB',dict(case_id=case_id,job_id=identity),loaded)
    def cancel_job(self):
        case_id=self.case_id();identity=self.analysis_jobs.currentData();window=self.dialog.window
        if not identity:raise ValueError('先選取此案分析工作')
        job=window.execution_queue.queue.store.get('AUTO_JOB',identity)
        if not job or job.get('operation')!='MAJOR_SOURCE_RECHECK' or job.get('scope',{}).get('case_id')!=case_id:raise ValueError('工作不屬於目前案件；未停止其他案件分析')
        row=window.library.db.execute("SELECT id FROM runtime_requests WHERE json_extract(payload,'$.job_id')=? AND json_extract(payload,'$.state') IN ('WAITING','PAUSED_RESOURCES','RUNNING','INTERRUPTED') ORDER BY seq LIMIT 1",(identity,)).fetchone()
        if not row:raise ValueError('此工作目前沒有可停止的待辦；已保存分析結果仍保留')
        window.execution_queue.cancel(row[0]);self.job_notice.setText('已要求原佇列停止；已保存分析不撤銷，未完成項仍需重審。')
    def show_analysis(self):
        rows=self.selected_units()
        if len(rows)!=1 or rows[0]['kind']!='QUALITY_WORK_QUARANTINE':raise ValueError('請明確選取一件有已保存分析的作品')
        row=rows[0]
        def loaded(value):
            result=value['analysis'];lines=['此為已保存的原／新判定對照；'+('目前作品來源版次仍一致。' if value['current'] else '目前來源／作品已改變，以下為歷史對照，不能當目前核准。'),'原判定：']
            old=next(item for item in result['original_facts'] if item['work_id']==row['work_id']);lines.append('事實版次 '+str(old['facts_revision']))
            if old['missing_prior_facts']:lines.append('缺原人工事實紀錄，維持未知，不補造舊核准。')
            else:
                for observation in old['facts'].get('observations',[])[:200]:lines.append(str(observation.get('owner',''))+'／'+str(observation.get('kind',''))+'／'+str(observation.get('text',''))[:256])
            lines.extend(['新分析：原來源引擎的未驗證建議；未使用語意模型、未核准原生Illustrator映射。','仍需由原稿與人工事實逐件核對；未自動套用。'])
            for suggestion in result['suggestions'][:100]:
                lines.append(str(suggestion.get('name','作品候選'))+'／'+str(suggestion.get('work_width'))+'×'+str(suggestion.get('work_height'))+' mm')
                for slot in suggestion.get('slots',[])[:200]:lines.append(KINDS.get(slot['kind'],slot['kind'])+'／'+slot['owner']+'／'+str(slot['rect']))
                lines.extend(str(reason) for reason in suggestion.get('evidence',{}).get('issues',[]))
            self.dialog.details.setPlainText('\n'.join(lines));self.dialog.status.setText('已讀回本件實際保存的原／新判定；尚未人工核准或解除隔離。')
        self.dialog.request('MAJOR_ANALYSIS',dict(case_id=self.case_id(),unit_id=row['id']),loaded)

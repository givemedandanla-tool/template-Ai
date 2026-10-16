"""Lazy native quality workflow, bounded workers, and explicitly exposed diagnosis."""
import threading
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QImageReader,QPen,QColor
from PySide6.QtWidgets import (QWidget,QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QComboBox,QPlainTextEdit,QTableWidget,QTableWidgetItem,QMessageBox,QSplitter)
from .training_store import TrainingStore
from .quality_command import run_command
from .quality_setup import QualitySetupDialog,LABELS
from .worker_callbacks import JobCallbacks
from .model import KINDS


class QualityPanel(QWidget):
    def __init__(self,window,parent=None):
        super().__init__(parent);self.window=window;self.library=window.library;self.root=self.library.root;self.store=TrainingStore.bind(self.library);self.loading=False;self.active=False;self.offset=0;self.protocol_offset=0;self.rows=[];self.pending=None;self.jobs={};self.last_plan=None;self.cancel_event=threading.Event()
        layout=QVBoxLayout(self);self.status=QLabel('獨立品質驗收：訓練成功與來源結案均不是品質通過。開啟本頁後才載入目錄。');self.status.setWordWrap(True);layout.addWidget(self.status)
        bar=QHBoxLayout();self.actor=QLineEdit();self.actor.setPlaceholderText('具名核對者（必填）');self.reason=QLineEdit();self.reason.setPlaceholderText('本次確認／重大錯誤重審依據');bar.addWidget(self.actor);bar.addWidget(self.reason,1);layout.addLayout(bar)
        bar=QHBoxLayout();self.query=QLineEdit();self.query.setPlaceholderText('全庫搜尋固定試驗名稱／版本');self.protocols=QComboBox();bar.addWidget(self.query);bar.addWidget(self.protocols,1)
        self.button(bar,'搜尋／刷新',lambda:self.list_protocols(0));self.button(bar,'前50個',lambda:self.list_protocols(-50));self.button(bar,'後50個',lambda:self.list_protocols(50));layout.addLayout(bar)
        bar=QHBoxLayout();self.button(bar,'設定真值／政策／版本／固定試驗',self.setup);self.button(bar,'確認保存預覽',self.confirm_preview);self.button(bar,'固定雙側加入公平佇列',self.enqueue_pair);self.button(bar,'刷新工作／品質指標',self.load_status);self.button(bar,'取消本次核對',lambda:self.cancel_event.set());layout.addLayout(bar)
        bar=QHBoxLayout();self.side=QComboBox();self.side.addItem('基準版本','BASELINE');self.side.addItem('候選版本','CANDIDATE');bar.addWidget(self.side);self.button(bar,'取消選中側工作',self.cancel_side);self.button(bar,'精確A/B比較預覽',self.compare);self.button(bar,'核准已保存品質比較憑證',self.decide);layout.addLayout(bar)
        self.report_id=QLineEdit();self.report_id.setPlaceholderText('品質比較憑證ID（保存後填入；不足／合成自驗不會核准正式品質）');layout.addWidget(self.report_id)
        bar=QHBoxLayout();self.button(bar,'查看所有來源樣本（含零錯誤）',lambda:self.source_units(0));layout.addLayout(bar);self.source_mode=False
        bar=QHBoxLayout();self.decision_id=QLineEdit();self.decision_id.setPlaceholderText('已接受的品質決策憑證ID（撤回保留歷史）');bar.addWidget(self.decision_id,1);self.button(bar,'撤回此品質接受／不自動回退',self.withdraw);layout.addLayout(bar)
        self.stats=QTableWidget(0,8);self.stats.setHorizontalHeaderLabels(['領域／類別','TP／FP／FN','Precision／Recall','Gold物件','正例獨立群組','失敗群組','群組失敗率區間','判定']);self.stats.setEditTriggers(QTableWidget.NoEditTriggers);layout.addWidget(self.stats,1)
        bar=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('全清單搜尋原因／來源／版本／人物／作品');self.severity=QComboBox();self.severity.addItems(['ALL','CRITICAL','ERROR','UNKNOWN']);self.domain=QComboBox();self.domain.addItem('所有領域','ALL')
        for key,label in LABELS.items():self.domain.addItem(label,key)
        self.field=QComboBox();self.field.addItems(['ALL',*KINDS,'ANNOTATION'])
        for widget in (self.search,self.severity,self.domain,self.field):bar.addWidget(widget)
        self.button(bar,'揭露答案以逐案診斷',self.expose);self.button(bar,'搜尋診斷',lambda:self.cases(0));layout.addLayout(bar)
        bar=QHBoxLayout();self.facets={}
        for key,label in (('size','尺寸如90x54'),('people','人數容量'),('logo','Logo類型'),('customer','客戶ID'),('group','獨立群組ID'),('role','資料角色'),('multi_work','多作品YES／NO')):
            field=QLineEdit();field.setPlaceholderText(label);bar.addWidget(field);self.facets[key]=field
        layout.addLayout(bar)
        self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['嚴重度／領域','來源／作品','分類／原因','位置／歸屬']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.SingleSelection);self.table.cellDoubleClicked.connect(lambda *_:self.guarded(self.detail));layout.addWidget(self.table,1)
        bar=QHBoxLayout();self.button(bar,'前50筆',lambda:self.cases(-50));self.button(bar,'後50筆',lambda:self.cases(50));self.button(bar,'原稿：人工真值 vs 實際AI框',self.detail);self.component=QComboBox();self.component.addItems(['PARSER','MODEL','RULE']);bar.addWidget(self.component);self.rule=QLineEdit();self.rule.setPlaceholderText('規則版本ID（僅規則重審）');bar.addWidget(self.rule);self.button(bar,'預覽UI-052跨歷史批次重審',self.recheck);layout.addLayout(bar)
        bar=QHBoxLayout();self.repair_button=self.button(bar,'局部修復／正式版本／安全回退',self.open_repair);self.case_repair_button=self.button(bar,'選中品質案例／影響作品修復',self.repair_selected);self.recheck_repair_button=self.button(bar,'選中持久重審項修復',self.repair_recheck);layout.addLayout(bar)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);self.details.setMaximumHeight(155);layout.addWidget(self.details)
        bar=QHBoxLayout();self.quarantine_query=QLineEdit();self.quarantine_query.setPlaceholderText('全庫搜尋待重審作品／案例');self.quarantines=QComboBox();bar.addWidget(self.quarantine_query);bar.addWidget(self.quarantines,1);self.button(bar,'搜尋重審項（最多50）',self.list_quarantines);self.button(bar,'預覽逐件解除隔離',self.preview_resolution);self.button(bar,'開啟選中來源事實核對',self.source_facts);layout.addLayout(bar)
        self.review_evidence=QLineEdit();self.review_evidence.setPlaceholderText('逐件新事實與原稿對照證據（解除隔離必填；不解除模型品質隔離）');layout.addWidget(self.review_evidence);self.recheck_item=None;self.impact_rows=[];self.impact_offset=0;self.impact_mode=False

    def button(self,bar,label,fn):
        button=QPushButton(label);button.clicked.connect(lambda:self.guarded(fn));bar.addWidget(button);return button

    def guarded(self,fn):
        try:fn()
        except Exception as error:self.status.setText('未執行：'+str(error))

    def activate(self):
        if not self.active:self.active=True;self.list_protocols(0)

    def request(self,command,payload,callback,on_error=None):
        if self.loading:return self.status.setText('核對仍在執行；可取消並刷新持久結果')
        if self.library.closed or self.window.library is not self.library:return self.status.setText('專案環境已變更，未執行')
        if self.window.busy:return self.status.setText('目前已有背景操作，完成後再送出本次明確核對')
        self.loading=True;self.cancel_event=threading.Event();cancel=self.cancel_event;self.status.setText('本機背景核對中；完成讀回前不宣稱保存成功')
        def failed(error):
            from shiboken6 import isValid
            if isValid(self):self.loading=False;self.pending=None;self.status.setText('結果未確認，請刷新持久資料；未自動重試：'+str(error))
            if on_error is not None:on_error(error)
        def done(value):
            from shiboken6 import isValid
            if not isValid(self):return
            self.loading=False
            if self.library.closed or self.window.library is not self.library:return self.status.setText('環境已變更；未套用舊結果')
            try:callback(value)
            except Exception as error:failed(error)
        try:self.window.run_job('本機品質核對',lambda:run_command(self.root,command,payload,cancel=cancel),JobCallbacks(done,failed,cancel))
        except Exception as error:failed(error)

    def open_repair(self,entry=None):
        from .quality_repair_dialog import QualityRepairDialog
        dialog=QualityRepairDialog(self);self._repair_dialog=dialog
        if entry:
            dialog.source_work.setText(entry.get('work_id') or '')
            dialog.description.setText(entry.get('description') or '從既有來源／例外／品質憑證核對局部問題')
            if entry.get('origin')=='ACTUAL_QUALITY_CASE':dialog.guard(lambda:dialog.preview('REPAIR_QUALITY_PLAN',dict(protocol_id=entry['protocol_id'],side=entry['side'],row=entry['row'],work_id=entry.get('work_id')),'ISSUE'))
            elif entry.get('origin')=='IMPORT_EXCEPTION':dialog.guard(lambda:dialog.preview('REPAIR_IMPORT_PLAN',dict(batch_id=entry['batch_id'],item_id=entry['item_id'],expected_revision=entry['expected_revision'],description=dialog.description.text()),'ISSUE'))
            else:dialog.guard(lambda:dialog.source_issue(entry['origin'],entry['origin_id']))
        try:dialog.exec()
        finally:self._repair_dialog=None;dialog.deleteLater()

    def repair_selected(self):
        selected=self.table.selectionModel().selectedRows()
        if not selected:
            if self.recheck_item:return self.repair_recheck()
            raise ValueError('先選取實際案例或待重審作品；零錯誤來源總覽不是失敗')
        index=selected[0].row()
        if self.impact_mode:
            row=self.impact_rows[self.impact_offset+index]
            return self.open_repair(dict(origin='SOURCE_FACTS',origin_id=row['work_id'],work_id=row['work_id'],description='從既有影響預覽核對原稿，不將潛在影響當已證實失敗'))
        row=self.rows[index]
        self.open_repair(dict(origin='ACTUAL_QUALITY_CASE',protocol_id=self.selected(),side=self.side.currentData(),row=row,work_id=row['case'].get('work_id')))

    def repair_recheck(self):
        identity=self.quarantines.currentData() or (self.recheck_item or {}).get('id')
        row=self.store.get('QUALITY_WORK_QUARANTINE',identity) if identity else None
        if not row:raise ValueError('先選取持久化的待重審作品項目')
        self.open_repair(dict(origin='CROSS_BATCH_RECHECK',origin_id=row['case_id'],work_id=row['work_id']))

    def setup(self):
        dialog=QualitySetupDialog(self)
        try:dialog.exec()
        finally:dialog.deleteLater()

    def list_protocols(self,delta):
        offset=max(0,self.protocol_offset+delta) if delta else 0
        def loaded(result):
            previous=self.protocols.currentData();self.protocols.clear();self.protocol_offset=result['offset']
            for row in result['rows']:self.protocols.addItem(row['label']+' · '+row['id'][:12],row['id'])
            index=self.protocols.findData(previous)
            if index>=0:self.protocols.setCurrentIndex(index)
            self.status.setText(f"固定試驗共{result['total']}；本頁{len(result['rows'])}。來源影像尚未載入。")
        self.request('LIST',dict(kind='QUALITY_PROTOCOL',offset=offset,query=self.query.text()),loaded)

    def selected(self):
        value=self.protocols.currentData()
        if not value:raise ValueError('先建立並選取預先固定的獨立試驗')
        return value

    def previewed(self,kind,value):
        self.pending=(kind,value) if kind else None;self.last_plan=value
        lines=[]
        if kind=='GOLD':lines=[f"作品 {value['work_id']}／來源頁 {value['source_page']}／人工觀察 {len(value['objects'])}",f"本機權利：{value['rights']['basis']}／{value['rights']['reference']}"]+[LABELS[k]+'：'+('人工核實' if v=='MANUALLY_VERIFIED' else '資料不足') for k,v in value['domain_truth'].items()]
        elif kind=='SET':
            manifest=value['manifest'];lines=[f"邏輯檔{manifest['file_count']}／實體位置{manifest['physical_path_count']}／來源頁{manifest['source_page_count']}／Gold作品{manifest['gold_work_count']}／獨立群組{manifest['independent_group_count']}",f"全來源真值完整：{manifest['whole_source_gold_complete']}；獨立性準備完成：{manifest['independence_scope_ready']}"]+value['errors']
        elif kind=='POLICY':lines=[value['name'],value['basis'],value['reference'],f"用途 {value['scope']}／信賴水準 {value['confidence']}／IoU {value['matching_iou']}"]+[LABELS[k]+'：'+str(v) for k,v in value['thresholds'].items()]
        elif kind=='PROTOCOL':
            scope=value['scope'];lines=[scope['name'],f"Gold作品{scope['gold_work_count']}／物件{scope['gold_object_count']}／來源檔{scope['source_file_count']}／獨立群組{scope['independent_groups']}",f"固定集 {scope['dataset_id']}／政策 {scope['policy_id']}"]+[side+'：'+row['id']+'／'+row['manifest_digest'] for side,row in scope['pipelines'].items()]
        elif kind=='REPORT':lines=[value['conclusion'],f"公平比較：{value['fair_comparison']}；可作正式品質決策：{value['candidate_decision_eligible']}",f"觀察到修復案例{len(value['fixed_cases'])}／新案例{len(value['new_cases'])}／尚存{len(value['unresolved_cases'])}",f"新重大錯誤：{value['new_critical_errors']}；類別退步：{value['class_regressions']}",f"固定分母：{value['denominators']}",'修復數量不等於統計顯著進步；逐案答案需另行明確揭露。']
        elif kind=='RECHECK':lines=[f"共通重大錯誤：{value['critical_errors']}",f"歷史影響候選{len(value['rows'])}／失聯{len(value['missing_historical_work_ids'])}",f"缺少舊依賴版本的候選{sum(r['legacy_dependency_versions_unknown'] for r in value['rows'])}；不是已證實錯誤，須逐件重審。",'確認後隔離受影響作品／樣本，包含歷史已結案。保留原稿、客戶、已發布模板與舊收據；不宣稱模型已去污染。']
        elif kind=='RESOLVE':
            row=value['row'];self.recheck_item=row;lines=[f"作品{row['work_id']}／隔離r{row['revision']}／案例{row['case_id']}",f"隔離時事實r{row['facts_revision']}；目前r{value['current_facts_revision']}／{value['current_facts_state']}",'需比隔離時更新且已人工確認的來源事實；只解除此件，模型品質隔離與舊接受不會自動恢復。']
        else:lines=['已保存本機版本／憑證：'+str(value.get('id','')),'此操作不代表模型已通過品質或模板／規則已發布。']
        self.details.setPlainText('\n'.join(lines));self.status.setText('預覽已取得；核對範圍後明確保存' if kind else '本機版本已保存，品質尚待固定獨立試驗')
        if kind=='RECHECK':self.impact_rows=value['rows'];self.impact_offset=0;self.show_impact()

    def confirm_preview(self):
        if not self.pending:raise ValueError('先取得本次預覽')
        kind,plan=self.pending
        if QMessageBox.question(self,'確認本次具名範圍','已核對以上來源、合法用途、版本及影響？此操作保存本次預覽。')!=QMessageBox.Yes:return
        if kind=='RECHECK':command='CONFIRM_RECHECK';payload=dict(plan=plan,actor=self.actor.text(),reason=self.reason.text(),approved=True)
        elif kind=='RESOLVE':command='RESOLVE_RECHECK';payload=dict(quarantine_id=plan['row']['id'],revision=plan['row']['revision'],actor=self.actor.text(),reason=self.reason.text(),evidence=self.review_evidence.text(),approved=True)
        else:command='CONFIRM';payload=dict(kind=kind,plan=plan,actor=self.actor.text(),approved=True)
        def saved(value):
            self.pending=None;self.previewed(None,value)
            if kind=='REPORT':self.report_id.setText(value['id'])
        self.request(command,payload,saved)

    def enqueue_pair(self):
        protocol=self.selected()
        role=self.store.get('QUALITY_PROTOCOL',protocol)['scope'].get('evaluation_role','HOLDOUT')
        message='HOLDOUT完成後不得藉重跑本集調參。' if role=='HOLDOUT' else role+'只做描述診斷，不是獨立品質驗收，也不執行訓練。'
        if QMessageBox.question(self,'固定雙側驗收','將基準與候選加入既有公平佇列？使用固定來源與版本。'+message)!=QMessageBox.Yes:return
        def submit(value):
            jobs=value.get('jobs',value)
            for side in ('BASELINE','CANDIDATE'):
                job=jobs[side]
                if job['phase'] not in ('COMPLETED','COMPLETED_WITH_EXCEPTIONS'):
                    self.window.execution_queue.submit('EVAL_JOB',job,self.actor.text())
            self.jobs=jobs;self.status.setText('已送入持久公平佇列；工作完成不等於品質通過。暫停／續跑沿用主程式背景資源控制。')
        def status(value):
            if value['jobs']:submit(value)
            else:self.request('CREATE_PAIR',dict(protocol_id=protocol,actor=self.actor.text(),approved=True),submit)
        self.request('PAIR_STATUS',dict(protocol_id=protocol),status)

    def load_status(self):
        def loaded(value):
            self.jobs=value['jobs'];result=value['results'].get(self.side.currentData());self.stats.setRowCount(0)
            phases='／'.join(side+':'+job['phase'] for side,job in self.jobs.items())
            if not result:self.status.setText(phases or '尚未建立執行工作');return
            for domain,summary in result['statistics']['domains'].items():
                for kind,data in summary['classes'].items():
                    row=self.stats.rowCount();self.stats.insertRow(row);counts=data['descriptive_counts'];interval=data['failure_rate_interval']
                    values=[LABELS[domain]+'／'+kind,'／'.join(str(counts[k]) for k in ('tp','fp','fn')) if counts else '不適用（尺寸誤差）','／'.join('資料不足' if counts[k] is None else f"{counts[k]:.4f}" for k in ('precision','recall')) if counts else '不適用',str(data['gold_objects']),str(data['positive_independent_groups']),str(data['failed_independent_groups']),f"{interval['lower']:.4f}～{interval['upper']:.4f}" if interval else '資料不足',data['state']]
                    for column,text in enumerate(values):self.stats.setItem(row,column,QTableWidgetItem(text))
            self.status.setText(f"{phases}；品質 {result['quality_gate']}；來源單位{result['required_source_pages_or_unparsed_files']}／邏輯檔{result['declared_logical_files']}／Gold作品{result['declared_gold_works']}／獨立群組{result['required_independent_groups']}；重大錯誤{result['critical_errors']}。未自動發布。")
            if not value.get('live_scope',{}).get('valid',True) or value.get('component_blocks',{}).get(self.side.currentData()):self.status.setText('歷史計算保留；目前來源／版本／答案獨立性或組件信任已失效，不能新放行。'+self.status.text())
        self.request('PAIR_STATUS',dict(protocol_id=self.selected()),loaded)

    def cancel_side(self):
        job=self.jobs.get(self.side.currentData())
        if not job:raise ValueError('先刷新並選擇工作')
        request=self.store.db.execute("SELECT id FROM runtime_requests WHERE json_extract(payload,'$.job_id')=? AND json_extract(payload,'$.state') IN ('WAITING','RUNNING','PAUSED_RESOURCES') ORDER BY seq DESC LIMIT 1",(job['id'],)).fetchone()
        if not request:raise ValueError('此側目前沒有可取消的執行請求')
        self.window.execution_queue.cancel(request[0]);self.status.setText('已要求取消；刷新持久進度後可明確續跑未完成來源。')

    def compare(self):self.request('COMPARE',dict(protocol_id=self.selected()),lambda value:self.previewed('REPORT',value))

    def decide(self):
        if QMessageBox.question(self,'明確品質決策','核准所填比較憑證的候選版本為品質依據？不覆寫舊安全版本、原稿、客戶或已發布模板。')!=QMessageBox.Yes:return
        def saved(value):self.decision_id.setText(value['id']);self.previewed(None,value)
        self.request('DECIDE',dict(report_id=self.report_id.text().strip(),actor=self.actor.text(),reason=self.reason.text(),approved=True),saved)

    def withdraw(self):
        if QMessageBox.question(self,'撤回品質接受','撤回所填品質決策？舊憑證與正式資料保留，不會把其他舊版本自動當安全替代。')!=QMessageBox.Yes:return
        def saved(value):self.previewed(None,value);self.status.setText('已撤回此品質接受；原報告與正式資料保留，不自動信任其他舊版本。')
        self.request('WITHDRAW_DECISION',dict(decision_id=self.decision_id.text().strip(),actor=self.actor.text(),reason=self.reason.text(),approved=True),saved)

    def list_quarantines(self):
        def loaded(value):
            self.quarantines.clear()
            for row in value['rows']:self.quarantines.addItem(row['label']+'／'+row['state']+'／'+row['id'][:12],row['id'])
            self.status.setText(f"符合重審項共{value['total']}；顯示最多50。縮小搜尋可定位其餘歷史項。")
        self.request('LIST',dict(kind='QUALITY_WORK_QUARANTINE',query=self.quarantine_query.text()),loaded)

    def preview_resolution(self):
        if not self.quarantines.currentData():raise ValueError('先搜尋並選取逐件重審項')
        self.request('RECHECK_ITEM',dict(identity=self.quarantines.currentData()),lambda value:self.previewed('RESOLVE',value))

    def source_facts(self):
        work_id=self.recheck_item['work_id'] if self.recheck_item else None
        selected=self.table.selectionModel().selectedRows()
        if selected and self.impact_mode:work_id=self.impact_rows[self.impact_offset+selected[0].row()]['work_id']
        elif selected and self.rows and selected[0].row()<len(self.rows):work_id=self.rows[selected[0].row()]['case'].get('work_id') or work_id
        if not work_id:raise ValueError('先選取具名作品案例／預覽逐件重審項')
        parent=self.parentWidget()
        while parent is not None and not hasattr(parent,'facts_panel'):parent=parent.parentWidget()
        if parent is not None and parent.facts_panel.loaded and parent.facts_panel.loaded['id']!=work_id and parent.facts_panel.has_pending_observation():raise ValueError('來源事實編輯器仍有尚未套用的人工內容；保留原編輯，不切換')
        from .training_navigation import require_clean_navigation,locate_work
        require_clean_navigation(self.window);locate_work(self.window,work_id)
        if parent is not None:
            if not parent.facts_panel.loaded or parent.facts_panel.loaded['id']!=work_id:parent.facts_panel.focus(work_id,[])
            parent.tabs.setCurrentWidget(parent.facts_panel)
        self.status.setText('已定位原作品／來源事實；需人工核對保存後回來刷新重審，未自動修改。')

    def show_impact(self):
        self.impact_mode=True;self.rows=[];rows=self.impact_rows[self.impact_offset:self.impact_offset+50];self.table.setRowCount(len(rows))
        for index,row in enumerate(rows):
            values=['版本待核對' if row['legacy_dependency_versions_unknown'] else '已記錄版本關聯',row['source_id']+'／'+row['work_id'],'歷史批次：'+','.join(row['batch_ids']),'事實r'+str(row['facts_revision'])+'／樣本'+str(len(row['samples']))]
            for column,text in enumerate(values):self.table.setItem(index,column,QTableWidgetItem(text))
        self.status.setText(f"重審影響候選{len(self.impact_rows)}；本頁{len(rows)}；含歷史已結案。先核對清單再確認。")

    def expose(self):
        role=self.store.get('QUALITY_PROTOCOL',self.selected())['scope'].get('evaluation_role','HOLDOUT')
        message='逐案對照會標記本保留集答案已揭露，不能再用它調參後重新驗收。舊報告保留；需新獨立來源才能再驗收。' if role=='HOLDOUT' else role+'只做本機描述診斷；答案及fit成績不能作獨立品質證據。'
        if QMessageBox.question(self,'明確揭露答案',message+'確定進入診斷？')!=QMessageBox.Yes:return
        self.request('EXPOSE',dict(identity=self.selected(),actor=self.actor.text(),reason=self.reason.text(),approved=True),lambda _:self.cases(0))

    def cases(self,delta):
        if self.impact_mode and delta:
            self.impact_offset=max(0,min(max(0,len(self.impact_rows)-1)//50*50,self.impact_offset+delta));self.show_impact();return
        self.impact_mode=False
        if self.source_mode and delta:return self.source_units(delta)
        self.source_mode=False
        offset=max(0,self.offset+delta) if delta else 0
        def loaded(value):
            self.offset=value['offset'];self.rows=value['rows'];self.table.setRowCount(len(self.rows))
            for row,entry in enumerate(self.rows):
                case=entry['case'];values=[entry['severity']+'／'+LABELS.get(entry['domain'],entry['domain']),str(entry['source_id'])+'／'+str(case.get('work_id','')),case.get('reason') or str(case.get('gold_kind',''))+'→'+str(case.get('predicted_kind','')),str(case.get('gold_rect',case.get('predicted_rect','')))+'／'+str(case.get('gold_owner',''))+'→'+str(case.get('predicted_owner',''))]
                for column,text in enumerate(values):self.table.setItem(row,column,QTableWidgetItem(text))
            self.status.setText(f"診斷共{value['total']}列／本頁{len(self.rows)}；固定來源單位{value['whole_source_units']}。問題列數不是品質分母；影像只在點選後載入。")
        self.request('DIAGNOSTICS',dict(protocol_id=self.selected(),side=self.side.currentData(),offset=offset,query=self.search.text(),severity=self.severity.currentText(),domain=self.domain.currentData(),field_type=self.field.currentText(),facets={key:widget.text().strip() for key,widget in self.facets.items() if widget.text().strip()}),loaded)

    def source_units(self,delta=0):
        offset=max(0,self.offset+delta) if delta else 0
        def loaded(value):
            self.impact_mode=False;self.source_mode=True;self.offset=value['offset'];self.rows=value['rows'];self.table.setRowCount(len(self.rows))
            for index,row in enumerate(self.rows):
                for column,text in enumerate(('來源樣本／非錯誤分數',row['source_label'],'包含零錯誤／未解析來源','點選才載入單件原稿與實際預測')):self.table.setItem(index,column,QTableWidgetItem(text))
            self.status.setText(f"已保存來源樣本共{value['total']}／本頁{len(self.rows)}；固定應評來源單位{value['whole_source_units']}。來源列數不是錯誤數。")
        self.request('SOURCE_UNITS',dict(protocol_id=self.selected(),side=self.side.currentData(),offset=offset,query=self.search.text()),loaded)

    def detail(self):
        if self.impact_mode:return self.source_facts()
        selected=self.table.selectionModel().selectedRows()
        if not selected:raise ValueError('先選取一個診斷案例')
        row=self.rows[selected[0].row()]
        def loaded(value):
            dialog=QualityCaseDialog(self.library,value,self)
            try:dialog.exec()
            finally:dialog.deleteLater()
        self.request('DIAGNOSTIC_DETAIL',dict(protocol_id=self.selected(),side=self.side.currentData(),row=row),loaded)

    def recheck(self):self.request('PLAN_RECHECK',dict(protocol_id=self.selected(),side=self.side.currentData(),component=self.component.currentText(),rule_id=self.rule.text().strip() or None),lambda value:self.previewed('RECHECK',value))


class QualityCaseDialog(QDialog):
    def __init__(self,library,detail,parent=None):
        super().__init__(parent);self.setWindowTitle('原始來源對照：人工真值 vs 實際AI候選（只讀）');self.resize(1350,850);layout=QVBoxLayout(self)
        self.golds=detail['golds'];self.predictions=detail['predictions'];self.canvases=[];self.case_detail=detail;self.panel=parent
        source=library.source(detail['source_id']) if detail['source_id'] else None
        header=QLabel('來源未解析／沒有合法Gold；來源仍保留在分母。' if not source else f"{source['original_path']}／頁{source['page']}／SHA256 {detail['source_hash']}\n左：人工原稿標註；右：實際固定版本推論。候選框不等於已確認客戶或正式模板。")
        header.setWordWrap(True);layout.addWidget(header)
        image=None
        if source and not detail.get('source_proof'):
            header.setText(header.text()+'\n本次沒有有效原稿對照證據／合法Gold；未讀取來源影像，保留來源分母。');source=None
        if source:
            from .source_links import check_verified,VerifiedSource
            from .batch_import import healthy_source
            proof=detail.get('source_proof')
            if not proof or source['hash']!=detail['source_hash'] or not healthy_source(source):raise ValueError('原稿／快取證據失效，未用新影像冒充舊模型結果')
            check_verified(VerifiedSource(proof['path'],proof['hash'],tuple(proof['stat'])),source['hash'])
            reader=QImageReader(source['image']);size=reader.size()
            if not size.isValid() or size.width()*size.height()>12_000_000:raise ValueError('來源影像超出本機對照像素預算，請用受控來源工具核對；未刪分母')
            size.scale(1600,1200,Qt.KeepAspectRatio);reader.setScaledSize(size);image=reader.read()
            if image.isNull():raise ValueError('來源影像不可讀')
        self.work=QComboBox()
        if detail['selected_work_id'] is None and detail['available_work_ids']:self.work.addItem('額外AI作品候選（沒有配對Gold）',None)
        for work_id in detail['available_work_ids']:self.work.addItem('人工作品 '+work_id,work_id)
        if not detail['available_work_ids']:self.work.addItem('來源未解析／額外候選',None)
        index=self.work.findData(detail['selected_work_id'])
        if index>=0:self.work.setCurrentIndex(index)
        layout.addWidget(self.work);split=QSplitter();layout.addWidget(split,1)
        from .gui import Canvas
        for title,color in (('人工核實', '#059669'),('實際AI預測','#dc2626')):
            frame=QWidget();box=QVBoxLayout(frame);box.addWidget(QLabel(title));canvas=Canvas();canvas.readonly=True;canvas.set_mode('pan');box.addWidget(canvas);split.addWidget(frame);self.canvases.append(canvas)
        self.note=QLabel('顏色表示左右來源，不表示品質通過；缺少／多出及歸屬請對照診斷原因。');self.note.setWordWrap(True);layout.addWidget(self.note)
        self.source=source;self.image=image;self.work.currentIndexChanged.connect(self.load_work);self.render()

    def load_work(self):
        detail=self.case_detail
        def loaded(value):
            from shiboken6 import isValid
            if not isValid(self):return
            self.golds=value['golds'];self.predictions=value['predictions'];self.case_detail=value;self.render()
        self.panel.request('DIAGNOSTIC_DETAIL',dict(protocol_id=detail['protocol_id'],side=detail['side'],row=detail['row'],work_id=self.work.currentData()),loaded)

    def render(self):
        from .quality_domains import predicted_objects
        if not self.source:return
        for canvas in self.canvases:canvas.set_content(self.source['width_mm'],self.source['height_mm'],self.image)
        golds=self.golds;predictions=self.predictions
        for canvas,works,pred,color in ((self.canvases[0],golds,False,'#059669'),(self.canvases[1],predictions,True,'#dc2626')):
            for work in works:
                pen=QPen(QColor(color),2,Qt.DashLine);pen.setCosmetic(True);crop=work['crop'];canvas.scene().addRect(QRectF(crop['x'],crop['y'],crop['w'],crop['h']),pen)
                objects=predicted_objects(work) if pred else work['objects']
                for obj in objects:
                    rect=obj['rect'];pen=QPen(QColor(color),1);pen.setCosmetic(True);canvas.scene().addRect(QRectF(rect['x'],rect['y'],rect['w'],rect['h']),pen)
                    text=canvas.scene().addSimpleText(obj['kind']+'／'+str(obj.get('owner') or '未定歸屬'));text.setBrush(QColor(color));text.setScale(.18);text.setPos(rect['x'],rect['y'])
            canvas.fit()

"""Lazy, paged coverage review. Each high-risk action is one work and one layer."""
import json
import threading
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QPushButton,QComboBox,QPlainTextEdit,QTableWidget,QTableWidgetItem,QHeaderView,QCheckBox,QFileDialog)
from .worker_callbacks import JobCallbacks
from .coverage_command import run_command

LAYER_LABELS={'native_or_ocr':'原生文字／OCR來源證據','people':'人物ROOT與跨人物邊界','companies':'公司及歸屬','whole_logo':'完整Logo與尺寸資產','fields':'欄位意涵及缺標記','customer':'客戶身分及來源關聯','styles':'版型候選／版本'}
STATE_LABELS={'BOUNDARY_FROZEN':'邊界已固定、尚未結案','OPEN':'審核中','CLOSED':'已存結案，仍需核對版本','REOPENED':'已保留並重開新版本','DECLARED_PENDING_PROOF':'等待來源核對','SOURCE_BYTES_VERIFIED_AWAITING_REVIEW':'位元相符，尚未完成審核','SOURCE_UNREGISTERED':'未登錄／未解析','SOURCE_UNRESOLVED':'來源失聯／改變／待釐清','SOURCE_VERSION_CONFLICT':'來源版本衝突'}


class CoverageClosurePanel(QWidget):
    def __init__(self,window,parent=None):
        super().__init__(parent);self.window=window;self.library=window.library;self.root=self.library.root;self.loading=False;self.started=False;self.offset=0;self.batch_offset=0;self.rows=[];self.batch=None;self.detail=None;self.pending=None;self.cancel_event=None
        layout=QVBoxLayout(self);self.status=QLabel('尚未讀取。指定批次的來源、作品與七層審核分開計數；分析完成不代表結案。');self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);layout.addWidget(self.status)
        bar=QHBoxLayout();self.batches=QComboBox();self.batches.setMinimumContentsLength(30);bar.addWidget(self.batches,1)
        self.button(bar,'前50批次',lambda:self.list_batches(-50));self.button(bar,'後50批次',lambda:self.list_batches(50));self.button(bar,'讀回批次',self.load_batch);layout.addLayout(bar)
        bar=QHBoxLayout();self.button(bar,'選檔建立範圍',self.choose_files);self.button(bar,'選目錄建立快照',self.choose_root);self.button(bar,'核對舊結案',self.check_closure);self.button(bar,'預覽重開新版本',self.plan_reopen);layout.addLayout(bar)
        self.versions=QLineEdit();self.versions.setPlaceholderText('必要時限定來源頁版本ID（空白納入所選檔案的全部已登錄版本；衝突會阻擋）');self.versions.setMaxLength(20000);layout.addWidget(self.versions)
        bar=QHBoxLayout();self.query=QLineEdit();self.query.setPlaceholderText('整個批次搜尋檔名／路徑');self.query.setMaxLength(500);bar.addWidget(self.query,1);self.button(bar,'搜尋',self.search);self.button(bar,'前50檔',lambda:self.page(-50));self.button(bar,'後50檔',lambda:self.page(50));layout.addLayout(bar)
        self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['來源檔案','登錄頁／作品紀錄','最近位元核對（非人審）','來源版本／下一步']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.SingleSelection);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);self.table.itemSelectionChanged.connect(self.selected);layout.addWidget(self.table,2)
        bar=QHBoxLayout();self.button(bar,'核對來源並載入各層',self.inspect);self.work_combo=QComboBox();bar.addWidget(self.work_combo,1);self.button(bar,'開啟實際作品畫布',self.locate);layout.addLayout(bar)
        self.actor=QLineEdit();self.actor.setPlaceholderText('審核者（必填）');self.actor.setMaxLength(120);layout.addWidget(self.actor)
        self.reason=QLineEdit();self.reason.setPlaceholderText('本次審核／排除／重開理由（必填）');self.reason.setMaxLength(2000);layout.addWidget(self.reason)
        self.evidence=QLineEdit();self.evidence.setPlaceholderText('實際來源頁、區域及證據定位說明（逐層審核必填）');self.evidence.setMaxLength(2000);layout.addWidget(self.evidence)
        self.segmentation_checked=QCheckBox('我已檢視本檔全部頁面，核對清單中的全部真實作品；沒有以畫板數推定作品數');layout.addWidget(self.segmentation_checked)
        bar=QHBoxLayout();self.button(bar,'預覽全檔切分確認',self.plan_segmentation);self.layer=QComboBox()
        for key,label in LAYER_LABELS.items():self.layer.addItem(label,key)
        bar.addWidget(self.layer);self.decision=QComboBox();self.decision.addItem('已個別確認','CONFIRMED');self.decision.addItem('核對來源後確認不存在','VERIFIED_ABSENT');self.decision.addItem('本次未形成版型候選','NO_CANDIDATE_RETAINED');bar.addWidget(self.decision);self.button(bar,'預覽此作品此層審核',self.plan_layer);layout.addLayout(bar)
        bar=QHBoxLayout();self.button(bar,'預覽明確排除此檔',self.plan_exclusion);self.button(bar,'重新核對並預覽結案',self.plan_close);self.confirm_button=self.button(bar,'儲存已核對的本次預覽',self.confirm);self.confirm_button.setEnabled(False);self.button(bar,'取消目前核對',self.cancel);layout.addLayout(bar)
        self.approved=QCheckBox('我已核對本次預覽的明列範圍及來源證據，明確同意這一次處置');layout.addWidget(self.approved)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details,2)
        self.library.observe_close(self.shutdown)

    def button(self,bar,label,callback):
        button=QPushButton(label);button.clicked.connect(callback);bar.addWidget(button);return button

    def activate(self):
        if not self.started:self.started=True;self.list_batches()

    def request(self,command,payload,callback):
        if self.loading:return self.status.setText('目前仍在核對；可取消後重新選擇')
        if self.library.closed or self.window.library is not self.library:return self.status.setText('專案環境已變更，未執行')
        if self.window.busy:return self.status.setText('已有背景工作執行，請待其完成後重送此明確操作')
        self.loading=True;self.cancel_event=threading.Event();cancel=self.cancel_event;self.confirm_button.setEnabled(False);self.status.setText('背景核對中；完成持久化讀回前不宣稱已儲存／結案')
        def failed(error):
            from shiboken6 import isValid
            if not isValid(self):return
            self.loading=False;self.pending=None;self.confirm_button.setEnabled(False);self.status.setText('本次結果未確認，請刷新持久資料；未自動重試：'+str(error))
        def done(value):
            from shiboken6 import isValid
            if not isValid(self):return
            self.loading=False
            if self.library.closed or self.window.library is not self.library:return self.status.setText('環境已變更；舊結果未套用，請重新讀回')
            callback(value)
        try:self.window.run_job('核對來源批次審核',lambda:run_command(self.root,command,payload,cancel=cancel),JobCallbacks(done,failed,cancel))
        except Exception as error:failed(error)

    def list_batches(self,delta=0):
        self.batch_offset=max(0,self.batch_offset+delta)
        def loaded(value):
            self.batches.clear()
            for row in value['rows']:self.batches.addItem(f"{STATE_LABELS.get(row['state'],row['state'])}／{row['file_count']}檔／{row['id'][:10]}",row['id'])
            self.status.setText(f"批次{self.batch_offset+1}起，本頁{len(value['rows'])}／總{value['total']}；選擇後讀回來源成員。")
        self.request('BATCHES',dict(offset=self.batch_offset),loaded)

    def selected_versions(self):return self.versions.text().split() or None

    def choose_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,'明列來源範圍，未解析檔案也保留於分母')
        if paths:self.request('PLAN_FILES',dict(paths=paths,selected_source_ids=self.selected_versions()),lambda plan:self.preview('CREATE',plan))

    def choose_root(self):
        root=QFileDialog.getExistingDirectory(self,'明列根目錄：包含子目錄，限定AI/PDF/SVG/EPS/PNG/JPG')
        if root:self.request('PLAN_ROOT',dict(root=root,selected_source_ids=self.selected_versions()),lambda plan:self.preview('CREATE',plan))

    def load_batch(self):
        identity=self.batches.currentData()
        if not identity:return
        self.request('MEMBERS',dict(batch_id=identity,offset=self.offset,query=self.query.text()),self.loaded)

    def loaded(self,value):
        self.batch=value['batch'];self.rows=value['page']['rows'];self.table.setRowCount(len(self.rows));self.pending=None;self.detail=None;self.work_combo.clear()
        for i,row in enumerate(self.rows):
            frozen=row['frozen'];values=(frozen['original_path'],f"{frozen['source_page_count']}登錄頁／{frozen['recorded_work_count']}作品紀錄",STATE_LABELS.get(row['check_state'],row['check_state']),row.get('source_error') or '需核對全檔切分及七個獨立審核層')
            for col,cell in enumerate(values):item=QTableWidgetItem(str(cell));item.setToolTip(str(cell));self.table.setItem(i,col,item)
        self.status.setText(f"固定批次{self.batch['file_count']}檔／{self.batch['source_page_count']}來源頁；本頁{len(self.rows)}／符合{value['page']['total']}。真實全部作品／當前有效已審數未逐檔核對時均為未知，未宣稱100%。")

    def search(self):self.offset=0;self.load_batch()
    def page(self,delta):self.offset=max(0,self.offset+delta);self.load_batch()
    def selected(self):self.detail=None;self.pending=None;self.confirm_button.setEnabled(False);self.work_combo.clear();self.segmentation_checked.setChecked(False);self.approved.setChecked(False)
    def member(self):
        row=self.table.currentRow()
        if row<0 or row>=len(self.rows):raise ValueError('先選擇明列來源檔案')
        return self.rows[row]
    def inspect(self):
        try:self.request('DETAIL',dict(member_id=self.member()['id']),self.show_detail)
        except ValueError as error:self.status.setText(str(error))
    def show_detail(self,value):
        self.detail=value;self.work_combo.clear()
        for index,work in enumerate(value['works']):self.work_combo.addItem(f"作品{index+1}／{work['work_id'][:10]}",work['work_id'])
        lines=[f"來源頁{value['source_page_count']}；已存作品紀錄{value['recorded_work_count']}；核對後真實作品總數{value['actual_work_count'] if value['actual_work_count'] is not None else '未知'}",f"處置：{value['disposition']}；待處理原因{len(value['blockers'])}項"]
        for key,counts in value['layer_counts'].items():lines.append(f"{LAYER_LABELS[key]}：當前已審{counts['current_reviewed']}／必要{counts['required']}（排除不計審核通過）")
        for blocker in value['blockers'][:50]:lines.append(blocker.get('reason','待審')+' '+LAYER_LABELS.get(blocker.get('layer'),''))
        self.details.setPlainText('\n'.join(lines));self.status.setText('已核對此檔實際位元與現有證據；各層仍須按來源逐項處置。')
    def guarded(self,function):
        try:function()
        except (ValueError,KeyError,TypeError,StopIteration) as error:self.status.setText('未能核對選擇，請先讀回批次與來源：'+str(error))
    def plan_segmentation(self):
        def run():
            if not self.segmentation_checked.isChecked():raise ValueError('先實際檢視全部頁面及作品，勾選全檔切分確認')
            member=self.member();ids=[w['id'] for p in member['frozen']['source_pins'] for w in p['works']]
            self.request('PLAN_SEGMENTATION',dict(member_id=member['id'],work_ids=ids,reason=self.reason.text()),lambda plan:self.preview('SEGMENTATION',plan))
        self.guarded(run)
    def plan_layer(self):
        self.guarded(lambda:self.request('PLAN_LAYER',dict(member_id=self.member()['id'],work_id=self.work_combo.currentData(),layer=self.layer.currentData(),decision=self.decision.currentData(),reason=self.reason.text(),evidence=self.evidence.text()),lambda plan:self.preview('LAYER',plan)))
    def plan_exclusion(self):self.guarded(lambda:self.request('PLAN_EXCLUSION',dict(member_id=self.member()['id'],reason=self.reason.text(),evidence=self.evidence.text()),lambda plan:self.preview('EXCLUSION',plan)))
    def plan_close(self):self.guarded(lambda:self.request('PLAN_CLOSE',dict(batch_id=self.batch['id']),lambda plan:self.preview('CLOSE',plan)))
    def plan_reopen(self):self.guarded(lambda:self.request('PLAN_REOPEN',dict(batch_id=self.batch['id'],reason=self.reason.text(),selected_source_ids=self.selected_versions()),lambda plan:self.preview('REOPEN',plan)))
    def check_closure(self):self.guarded(lambda:self.request('CLOSURE_STATUS',dict(batch_id=self.batch['id']),lambda value:self.details.setPlainText('當前有效結案：'+str(value['current_complete'])+'\n'+value['reason']+'\n'+str(value.get('failures',[]))[:12000])))
    def preview(self,action,plan):
        self.pending=(action,plan);self.approved.setChecked(False);allowed=action!='CLOSE' or plan['closure_allowed'];self.confirm_button.setEnabled(allowed)
        labels={'CREATE':'建立確切來源範圍','SEGMENTATION':'僅確認此檔全部作品切分','LAYER':'僅確認此作品此層','EXCLUSION':'明確排除此檔，不當學習／版型通過','CLOSE':'儲存本次範圍審核結案，不授權發布／輸出','REOPEN':'保留舊證據並建立新批次版本'}
        scope=plan.get('new_scope_plan',plan);lines=[labels[action],f"來源檔案：{scope.get('file_count','此檔')}；來源頁：{scope.get('source_page_count','此檔明列頁')}；未解決檔案：{scope.get('unresolved_files','待逐檔核對')}"]
        if action=='LAYER':
            context=plan['context'];lines += [LAYER_LABELS[plan['layer']],plan['decision'],plan['reason'],plan['evidence'],f"此作品觀察{context['observation_count']}；未確認{len(context['unconfirmed_observation_ids'])}；人物ROOT候選{len(context['person_root_candidates'])}；公司候選{len(context['company_candidates'])}；完整Logo候選{context['whole_logo_candidates']}；客戶關聯{context['association_count']}；版型版本{context['style_version_count']}"]
        if action in ('CREATE','REOPEN'):lines += [m['original_path'] for m in scope['members'][:50]]
        if action=='CLOSE':lines += [scope['scope_notice']]+[str(b) for b in scope['blockers'][:20]]+scope['scope_blockers']
        if action in ('SEGMENTATION','EXCLUSION'):lines += [plan['reason'],str(plan.get('impact',{})),f"明列作品數：{plan.get('actual_work_count',plan.get('impact',{}).get('recorded_work_count','未知'))}"]
        self.details.setPlainText('\n'.join(lines));self.status.setText('預覽已準備，尚未儲存。'+('核對後勾選本次明確同意。' if allowed else '仍有漏審／未知／衝突，不能結案。'))
    def confirm(self):
        def run():
            if not self.pending or not self.approved.isChecked():raise ValueError('需核對本次預覽並明確勾選同意')
            action,plan=self.pending
            def saved(value):
                self.pending=None;self.approved.setChecked(False);self.status.setText('已完成資料庫提交與讀回；請讀回批次核對現況。')
                if action in ('CREATE','REOPEN'):self.list_batches()
                elif action=='CLOSE':self.check_closure()
                else:self.inspect()
            self.request('CONFIRM',dict(action=action,plan=plan,actor=self.actor.text(),approved=True),saved)
        self.guarded(run)
    def locate(self):
        def run():
            identity=self.work_combo.currentData()
            if not identity or not self.detail:raise ValueError('先核對此來源並選擇實際作品')
            from .coverage_evidence import work_context
            from .coverage_batches import CoverageBatches
            expected=next(w for w in self.detail['works'] if w['work_id']==identity)
            if work_context(CoverageBatches(self.library),identity)['context_digest']!=expected['context_digest']:raise ValueError('作品依賴已變更，請重新核對')
            from .training_navigation import locate_work
            locate_work(self.window,identity)
        self.guarded(run)
    def cancel(self):
        if self.cancel_event:self.cancel_event.set()
    def shutdown(self):self.cancel()

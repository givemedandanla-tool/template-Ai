"""Native trusted-sample review in the existing training/quality center."""
import json
from PySide6.QtCore import Qt,QDateTime
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QTabWidget,QWidget,QLabel,QLineEdit,QComboBox,QPushButton,QCheckBox,QSpinBox,QTableWidget,QTableWidgetItem,QPlainTextEdit,QListWidget,QListWidgetItem,QAbstractItemView,QScrollArea)
from shiboken6 import isValid
from .trusted_sample_pool import PURPOSES

FILTERS=(('待驗證樣本','PENDING'),('准入','ADMITTED'),('反例與標記衝突','CONFLICTS'),('資料集分配','DATASETS'),('受污染／需重新核實','POLLUTED'),('模型使用追溯','LINEAGE'))
PURPOSE_LABELS=('幾何訓練','語意分類訓練','獨立品質驗收','品質問題診斷','通用規則支持／反例')


class TrustedSampleReviewDialog(QDialog):
    def __init__(self,panel):
        super().__init__(panel);self.panel=panel;self.window=panel.window;self.store=panel.store;self.pending=None;self.generation=0;self.offset=0;self.rows=[];self.bindings={};self.binding_widgets={};self.privacy_rows=[]
        self.setWindowTitle('可信樣本：核對、准入與用途追溯');self.resize(1120,820);outer=QVBoxLayout(self)
        self.status=QLabel('人工更正、樣本准入、實際訓練與品質驗收分開保存。');self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);outer.addWidget(self.status)
        bar=QHBoxLayout();self.actor=QLineEdit();self.actor.setMaxLength(120);self.actor.setPlaceholderText('本次核實人');bar.addWidget(self.actor);self.basis=QComboBox();self.basis.addItem('請明確選擇訓練權利',None)
        for label,value in (('自有','OWNED'),('已獲授權','AUTHORIZED'),('開放授權','OPEN_LICENSE')):self.basis.addItem(label,value)
        bar.addWidget(self.basis);self.reference=QLineEdit();self.reference.setMaxLength(2000);self.reference.setPlaceholderText('具體來源／授權依據；只限本機幾何用途');bar.addWidget(self.reference,2);outer.addLayout(bar)
        self.tabs=QTabWidget();outer.addWidget(self.tabs,1)
        page=self.tab_page('候選與逐項准入');layout=QVBoxLayout(page);bar=QHBoxLayout();self.collection=QComboBox()
        for label,value in FILTERS:self.collection.addItem(label,value)
        bar.addWidget(self.collection);self.query=QLineEdit();self.query.setMaxLength(500);self.query.setPlaceholderText('搜尋來源檔名／作品名稱');bar.addWidget(self.query,1);self.button(bar,'搜尋',lambda:self.reload(0));self.button(bar,'前50',lambda:self.reload(max(0,self.offset-50)));self.button(bar,'後50',lambda:self.reload(self.offset+50));layout.addLayout(bar)
        self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(['作品／來源','目前狀態','風險','本次逐項動作','高風險已逐項核實','標記候選版本']);self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.setSelectionMode(QAbstractItemView.SingleSelection);self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.table.horizontalHeader().setStretchLastSection(True);self.table.setColumnWidth(0,340);self.table.setColumnWidth(1,160);self.table.setColumnWidth(2,70);self.table.setColumnWidth(3,120);self.table.setColumnWidth(4,155);layout.addWidget(self.table,2)
        self.binding_form=QFormLayout();layout.addLayout(self.binding_form);bar=QHBoxLayout();self.button(bar,'核對選中項目前後標記',self.detail);self.button(bar,'預覽本頁已指定的逐項結果',self.preview_batch);layout.addLayout(bar)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details,2)
        page=self.tab_page('用途追溯與來源修復');layout=QVBoxLayout(page);bar=QHBoxLayout();self.button(bar,'讀取實際／潛在／未知依賴',self.trace);self.button(bar,'返回來源事實與畫布',self.source_facts);self.button(bar,'開啟既有受控修復',self.repair);layout.addLayout(bar);self.trace_details=QPlainTextEdit();self.trace_details.setReadOnly(True);layout.addWidget(self.trace_details)
        page=self.tab_page('用途停止與本機副本刪除');layout=QVBoxLayout(page);label=QLabel('停止使用會阻斷後續用途；撤銷不代表模型已去污染。刪除僅處理明列的本機訓練文字副本與歷史，原稿、業務資料、外部備份及安全擦除另行處理。');label.setWordWrap(True);layout.addWidget(label);self.purpose_checks=[]
        for title,purpose in zip(PURPOSE_LABELS,PURPOSES):
            check=QCheckBox(title);self.purpose_checks.append((purpose,check));layout.addWidget(check);check.toggled.connect(self.invalidate)
        form=QFormLayout();self.privacy_action=QComboBox();self.privacy_action.addItem('僅停止所選用途','STOP_USE');self.privacy_action.addItem('停止用途並登記本機刪除審核','REQUEST_LOCAL_ERASURE');form.addRow('本次要求',self.privacy_action);self.retention=QSpinBox();self.retention.setRange(0,365);self.retention.setValue(30);form.addRow('必要審核期限（天，0為即日）',self.retention);layout.addLayout(form);bar=QHBoxLayout();self.button(bar,'預覽所選來源停止用途',self.preview_restriction);self.button(bar,'列出該來源實際訓練副本',self.load_privacy_records);layout.addLayout(bar);self.privacy_records=QListWidget();layout.addWidget(self.privacy_records);bar=QHBoxLayout();self.button(bar,'預覽勾選副本的文字刪除',self.preview_redaction);layout.addLayout(bar);self.privacy_details=QPlainTextEdit();self.privacy_details.setReadOnly(True);layout.addWidget(self.privacy_details)
        self.consent=QCheckBox('我已核對目前預覽的來源、逐項結果、用途與影響；明確批准本次操作');outer.addWidget(self.consent);bar=QHBoxLayout();self.confirm_button=self.button(bar,'確認並保存目前預覽',self.confirm);self.button(bar,'關閉',self.reject);outer.addLayout(bar)
        self.table.itemSelectionChanged.connect(self.selection_changed);self.table.itemChanged.connect(self.invalidate);self.collection.currentIndexChanged.connect(lambda:self.reload(0));self.query.textChanged.connect(self.invalidate);self.actor.textChanged.connect(self.invalidate);self.basis.currentIndexChanged.connect(self.invalidate);self.reference.textChanged.connect(self.invalidate);self.privacy_action.currentIndexChanged.connect(self.invalidate);self.retention.valueChanged.connect(self.invalidate);self.privacy_records.itemChanged.connect(self.invalidate)
        self.reload(0)

    def tab_page(self,title):
        page=QWidget();scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(page);self.tabs.addTab(scroll,title);return page

    def button(self,bar,label,action):
        button=QPushButton(label);button.clicked.connect(lambda:self.guard(action));bar.addWidget(button);return button
    def guard(self,action):
        try:action()
        except (ValueError,KeyError,OSError,TypeError) as error:self.status.setText('未執行：'+str(error))
    def invalidate(self,*_):
        self.generation+=1;self.pending=None
        if hasattr(self,'consent'):self.consent.setChecked(False)
    def request(self,command,payload,callback,mutation=False):
        generation=self.generation;self.status.setText('正在本機核對所選來源與持久版本。')
        def done(value):
            if not isValid(self):return
            if generation!=self.generation and not mutation:self.status.setText('輸入已變更，舊結果不套用；請重新核對。');return
            callback(value)
        def failed(error):
            if isValid(self):self.invalidate();self.status.setText('未確認／未自動重試：'+str(error))
        self.panel.request('SAMPLE_'+command,payload,done,on_error=failed)
    def selected(self):
        indices={index.row() for index in self.table.selectionModel().selectedRows()}
        if len(indices)!=1:raise ValueError('先選取一項具名來源')
        return self.rows[indices.pop()]
    def reload(self,offset=0):
        self.invalidate();self.offset=offset
        def loaded(value):
            self.rows=value['rows'];self.table.blockSignals(True);self.table.setRowCount(len(self.rows))
            for i,row in enumerate(self.rows):
                values=(row['label']+'／'+str(row['source_label']),row['state']+'／'+str(row['current_sample_state'] or '尚未准入'),row['risk'],'','',str(row['revision']))
                for column,value in enumerate(values):self.table.setItem(i,column,QTableWidgetItem(value))
                action=QComboBox()
                for label,data in (('未指定',None),('准入','APPROVE'),('拒絕','REJECT'),('保留待審','DEFER')):action.addItem(label,data)
                action.currentIndexChanged.connect(self.invalidate);self.table.setCellWidget(i,3,action);check=self.table.item(i,4);check.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable);check.setCheckState(Qt.Unchecked)
            self.table.blockSignals(False);self.status.setText(f"掃描{value['scanned']}筆候選，本頁符合{len(self.rows)}筆；候選總數{value['total_candidates']}。篩選結果僅本掃描頁，分類不冒充全庫有效數。")
        self.request('LIST',dict(collection=self.collection.currentData(),offset=offset,query=self.query.text()),loaded)
    def selection_changed(self):
        self.invalidate();self.binding_widgets={}
        while self.binding_form.rowCount():self.binding_form.removeRow(0)
        try:row=self.selected()
        except ValueError:return
        work=self.store.library.artwork(row['work_id']);slots=work['payload']['slots'];people=sorted({s['owner'] for s in slots if s['owner'].startswith('p')});companies=sorted({s['owner'] for s in slots if s['owner'].startswith('c')})
        for person in people if companies else []:
            combo=QComboBox();combo.addItem('公司歸屬尚未核實',None)
            for company in companies:combo.addItem(company,company)
            selected=self.bindings.get(row['id'],{}).get(person);combo.setCurrentIndex(max(0,combo.findData(selected)));combo.currentIndexChanged.connect(lambda _,identity=row['id'],owner=person,widget=combo:self.bind(identity,owner,widget));self.binding_form.addRow(person+'的公司歸屬',combo);self.binding_widgets[person]=combo
    def bind(self,identity,owner,combo):self.bindings.setdefault(identity,{})[owner]=combo.currentData();self.invalidate()
    def detail(self):
        def loaded(value):
            detail=value['detail'];before=value['previous_human_label_version'];after=value['current_candidate_label_version'];lines=[detail['work_label'],str(detail['source_label']),'前一人工版本：'+str((before or {}).get('revision','無／歷史不足')),'目前候選標記：'+str((after or {}).get('revision','歷史不足')),'AI原判定：'+value['prior_AI_prediction'],'原判定與人工真值不混作正例。']
            confirmation=detail['current_confirmation'] or {};timestamp=confirmation.get('timestamp');pins=detail['candidate']['pins'];slots={slot['id']:slot for slot in detail['current_slots']}
            lines.extend(['確認者：'+str(confirmation.get('actor') or '尚未確認'),'確認時間：'+(QDateTime.fromSecsSinceEpoch(int(timestamp)).toString(Qt.ISODate) if timestamp else '尚未確認'),'來源連結版本：'+str(pins['link_revision'])+'／作品版本：'+str(pins['work_revision']),'尺寸：'+str(detail['dimensions']['width'])+' × '+str(detail['dimensions']['height'])+' mm','既有確認客戶關聯：'+str(len(detail['confirmed_customer_ids']))+'筆；未確認的歸屬不由樣本准入推定。'])
            for title,record in (('前一人工標記',before),('本次人工標記',after)):
                lines.append(title)
                lines.extend(o['classification']+'／'+str(slots.get(o.get('slot_id'),{}).get('kind','非欄位'))+'／'+str(slots.get(o.get('slot_id'),{}).get('owner','來源註記'))+'／'+o['text'] for o in (record or {}).get('observations',[]))
            if value['actual_AI_prediction_version']:
                lines.append('實際本機來源解析提案（非人工真值）')
                lines.extend(o['classification']+'／'+o['text'] for o in value['actual_AI_prediction_version']['observations'])
            lines.extend('使用者回報的舊判定（診斷，非黃金答案）：'+str(p['prediction']) for p in value['user_supplied_prior_predictions']);lines.extend(detail['errors']);self.details.setPlainText('\n'.join(lines));self.status.setText('已讀取具名來源及原標記版本；尚未准入或訓練。')
        self.request('DETAIL',dict(identity=self.selected()['id']),loaded)
    def preview(self,kind,payload):
        self.invalidate()
        def loaded(value):
            self.pending=(kind,value);self.consent.setChecked(False);target=self.details if kind=='CONFIRM' else self.privacy_details;target.setPlainText(self.describe_plan(kind,value));self.status.setText('已預覽目前確切範圍；核對後才確認保存。')
        command={'CONFIRM':'PLAN','RESTRICT':'RESTRICT_PLAN','REDACT':'REDACTION_PLAN'}[kind];self.request(command,payload,loaded)
    def describe_plan(self,kind,value):
        if kind=='CONFIRM':
            rights=value['rights'];lines=['本次逐項預覽：'+str(len(value['items']))+'項','准入僅供明列的本機幾何用途，不會啟動訓練。','授權依據：'+str(rights.get('reference',''))]
            for step in value['items']:
                detail=step['detail'];action={'APPROVE':'准入','REJECT':'拒絕','DEFER':'保留待審'}[step['item']['action']]
                lines.extend(['',detail['work_label']+'／'+str(detail['source_label']),'本次：'+action+'；風險：'+detail['risk'],'候選標記版本：'+str(detail['candidate']['facts_revision'])+'；目前核實版本：'+str(detail['current_facts_revision'])])
                lines.extend('阻擋：'+error for error in step['errors'])
                if not step['errors']:lines.append('目前明列條件核對通過；仍需下方明確批准。')
            return '\n'.join(lines)
        if kind=='RESTRICT':
            names=dict(zip(PURPOSES,PURPOSE_LABELS));impact=value['impact'];lines=['來源：'+self.selected()['label'],'停止用途：'+'、'.join(names[p] for p in value['purposes']),'必要審核期限：'+str(value['retention_days'])+'天','已記錄的依賴節點：'+str(len(impact['nodes'])),'歷史失聯：'+str(len(impact['missing_historical_nodes'])),'未登錄的舊依賴仍為未知；不宣稱模型已去污染。','本次不刪除原稿、業務事實或外部備份。']
            return '\n'.join(lines)
        lines=['僅刪除以下明列的本機訓練文字副本及其中的歷史文字：']
        lines.extend(('幾何樣本' if item['kind']=='SAMPLE' else '語意模型')+'／版本'+str(item['revision'])+'／'+item['id'][:12] for item in value['items'])
        lines.extend(['保留最少必要的來源／用途／版本與摘要憑證。','原稿、業務事實與外部備份未被刪除；不宣稱安全擦除或模型去污染。'])
        return '\n'.join(lines)

    def preview_batch(self):
        items=[]
        for i,row in enumerate(self.rows):
            action=self.table.cellWidget(i,3).currentData()
            if action:items.append(dict(id=row['id'],action=action,bindings={k:v for k,v in self.bindings.get(row['id'],{}).items() if v},high_risk_reviewed=self.table.item(i,4).checkState()==Qt.Checked))
        rights=dict(basis=self.basis.currentData(),reference=self.reference.text(),use='GEOMETRY_TRAINING_LOCAL');self.preview('CONFIRM',dict(items=items,rights=rights))
    def confirm(self):
        if not self.pending or not self.consent.isChecked():raise ValueError('先核對有效預覽並明確勾選批准')
        kind,plan=self.pending;self.pending=None;self.consent.setChecked(False)
        def saved(value):
            self.invalidate();self.status.setText('本次明列操作已保存；沒有自動啟動訓練、正式啟用模型或宣稱去污染。')
            for index in range(self.table.rowCount()):self.table.item(index,1).setText('已保存操作；請重載核對目前資格')
            target=self.details if kind=='CONFIRM' else self.privacy_details;target.setPlainText(self.describe_saved(kind,value))
        self.request(kind,dict(plan=plan,actor=self.actor.text(),approved=True),saved,mutation=True)
    def describe_saved(self,kind,value):
        if kind=='CONFIRM':
            names={row['id']:row['label'] for row in self.rows};labels={'ADMITTED':'已明確准入','REJECTED':'已拒絕','DEFERRED':'保留待審'}
            return '\n'.join([names.get(row['id'],'所選來源')+'：'+labels[row['state']] for row in value]+['沒有啟動訓練、發布模板或正式採用模型。'])
        if kind=='RESTRICT':
            names=dict(zip(PURPOSES,PURPOSE_LABELS));lines=['所選用途已停止；原資料未被自動刪除。']
            for row in value:lines.append(names[row['purpose']]+'：已停止；必要審核期限 '+QDateTime.fromSecsSinceEpoch(int(row['review_due_at'])).toString(Qt.ISODate))
            lines.append('舊資料／模型的實際使用證據仍保留；不宣稱已去污染。');return '\n'.join(lines)
        return '\n'.join(['已處理明列本機訓練副本：'+str(len(value['records']))+'筆','其中的歷史訓練文字已邏輯刪除，留下最少必要的用途與摘要憑證。','處理憑證：'+value['receipt']['id'][:12],'原稿、業務事實、外部備份未被刪除；未宣稱安全擦除或模型去污染。'])

    def trace(self):
        self.request('TRACE',dict(identity=self.selected()['id']),lambda value:self.trace_details.setPlainText(json.dumps(value,ensure_ascii=False,indent=2)))
    def source_facts(self):
        row=self.selected();parent=self.panel.parentWidget()
        while parent is not None and not hasattr(parent,'facts_panel'):parent=parent.parentWidget()
        if parent is None:raise ValueError('請由既有訓練中心核對來源')
        if parent.facts_panel.has_pending_observation():raise ValueError('來源事實有未套用內容，保留原編輯')
        from .training_navigation import require_clean_navigation,locate_work
        require_clean_navigation(self.window);locate_work(self.window,row['work_id']);parent.facts_panel.focus(row['work_id'],[]);parent.tabs.setCurrentWidget(parent.facts_panel);self.hide()
    def repair(self):
        row=self.selected();self.panel.open_repair(dict(origin='SOURCE_FACTS',origin_id=row['work_id'],work_id=row['work_id']))
    def preview_restriction(self):
        self.preview('RESTRICT',dict(work_id=self.selected()['work_id'],purposes=[purpose for purpose,check in self.purpose_checks if check.isChecked()],action=self.privacy_action.currentData(),retention_days=self.retention.value()))
    def load_privacy_records(self):
        def loaded(value):
            self.privacy_rows=value['rows'];self.privacy_records.blockSignals(True);self.privacy_records.clear()
            for row in self.privacy_rows:
                item=QListWidgetItem(('幾何樣本' if row['kind']=='SAMPLE' else '語意模型')+'／'+row['state']+'／版本'+str(row['revision']));item.setData(Qt.UserRole,dict(kind=row['kind'],id=row['id']));item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Unchecked);self.privacy_records.addItem(item)
            self.privacy_records.blockSignals(False);self.status.setText('僅列所選來源實際訓練副本；預設皆未勾選，未宣稱外部副本已掌握。')
        self.request('PRIVACY_RECORDS',dict(work_id=self.selected()['work_id']),loaded)
    def preview_redaction(self):
        records=[self.privacy_records.item(i).data(Qt.UserRole) for i in range(self.privacy_records.count()) if self.privacy_records.item(i).checkState()==Qt.Checked];self.preview('REDACT',dict(work_id=self.selected()['work_id'],records=records))
    def reject(self):
        if self.panel.loading:self.status.setText('來源核對尚未完成；請先取消既有背景工作或等待讀回。');return
        super().reject()

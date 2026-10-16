"""Explicit local quality configuration using named controls and actual records."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QTabWidget,QWidget,QLabel,QLineEdit,QPlainTextEdit,QComboBox,QPushButton,QCheckBox,QTableWidget,QTableWidgetItem,QFileDialog,QScrollArea)
from .quality_gold import DOMAINS,USE,DIAGNOSTIC_USE
from .model import KINDS

LABELS=dict(source_readability='來源可讀性',work_segmentation='完整作品切分',text_candidates='所有文字候選（含Logo文字）',field_types='各欄位類型',person_ownership='人物ROOT與聯絡歸屬',company_ownership='公司歸屬',whole_logo='完整Logo圖文構件',physical_size='作品物理尺寸',customer_style_mapping='來源→客戶→exact版型')


class QualitySetupDialog(QDialog):
    def __init__(self,panel):
        super().__init__(panel);self.panel=panel;self.library=panel.library;self.setWindowTitle('獨立品質驗收設定：本機、明確核對、保留版本');self.resize(1050,850)
        layout=QVBoxLayout(self);self.tabs=QTabWidget();layout.addWidget(self.tabs)
        self.gold_form();self.policy_form();self.set_form();self.version_form();self.protocol_form()
        self.note=QLabel('先預覽，再回主頁核對並確認保存；空白／不足不會自動變成通過。');self.note.setWordWrap(True);layout.addWidget(self.note)

    def tab(self,title):
        widget=QWidget();form=QFormLayout(widget);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(widget);self.tabs.addTab(scroll,title);return form

    def line(self,form,title):
        edit=QLineEdit();form.addRow(title,edit);return edit

    def catalog(self,kind,query=''):
        store=self.panel.store
        return store.db.execute("SELECT id,COALESCE(json_extract(payload,'$.name'),json_extract(payload,'$.manifest.name'),json_extract(payload,'$.plan.name'),json_extract(payload,'$.work_id'),id) FROM training_records WHERE kind=? AND instr(training_casefold(id||' '||payload),?)>0 ORDER BY rowid DESC LIMIT 50",(kind,query.casefold())).fetchall()

    def picker(self,form,title,kind,optional=False):
        bar=QHBoxLayout();query=QLineEdit();query.setPlaceholderText('全庫搜尋；每頁最多50個版本');combo=QComboBox();bar.addWidget(query);bar.addWidget(combo,1);form.addRow(title,bar)
        def refresh():
            combo.clear()
            if optional:combo.addItem('未使用',None)
            for identity,name in self.catalog(kind,query.text()):combo.addItem(str(name)+' · '+identity[:12],identity)
        query.textChanged.connect(refresh);refresh();return combo

    def button(self,form,title,callback):
        button=QPushButton(title);button.clicked.connect(lambda:self.guarded(callback));form.addRow(button);return button

    def guarded(self,callback):
        try:callback()
        except Exception as error:self.note.setText('未執行：'+str(error))

    def submit(self,command,payload,kind=None):
        self.panel.request(command,payload,lambda result:self.panel.previewed(kind,result))
        self.accept()

    def gold_form(self):
        form=self.tab('人工真值版本');query=self.line(form,'搜尋來源／作品');self.work=QComboBox();form.addRow('已人工核對的作品',self.work)
        def works():
            self.work.clear()
            for identity,name,path in self.library.db.execute("SELECT a.id,a.name,s.original_path FROM artworks a JOIN sources s ON s.id=a.source_id WHERE instr(training_casefold(a.id||' '||a.name||' '||s.original_path),?)>0 ORDER BY a.rowid DESC LIMIT 50",(query.text().casefold(),)):
                self.work.addItem(name+' · '+path,identity)
        query.textChanged.connect(works);works()
        self.basis=QComboBox();self.basis.addItems(['OWNED','AUTHORIZED','OPEN_LICENSE']);form.addRow('本機品質用途權利依據',self.basis)
        self.gold_use=QComboBox();self.gold_use.addItem('獨立品質驗收（不是訓練授權）',USE);self.gold_use.addItem('訓練／調參集描述診斷（不能當獨立驗收）',DIAGNOSTIC_USE);form.addRow('單獨明列本次合法用途',self.gold_use)
        self.rights=self.line(form,'可核對的權利證明／範圍');self.gold_reason=self.line(form,'人工原稿核對理由');self.gold_evidence=self.line(form,'原始作品及正確標註證據')
        self.truth={}
        for domain in DOMAINS:
            box=QCheckBox('已逐項核實：'+LABELS[domain]);form.addRow(box);self.truth[domain]=box
        form.addRow(QLabel('未勾選的層次維持「資料不足」。Logo原稿對照與客戶exact版型另列，不能由AI候選自動填答案。'))
        self.logo=QTableWidget(0,5);self.logo.setHorizontalHeaderLabels(['Logo觀察ID','原稿群組ID','完整構件ID（逗號分隔）','人工圖文對照依據','其中真實文字ID（含outline；確認無文字才留空）']);form.addRow('完整Logo真值',self.logo)
        def logos():
            self.logo.setRowCount(0)
            if not self.work.currentData():return
            facts=self.panel.store.facts(self.work.currentData());work=self.library.artwork(self.work.currentData());kinds={s['id']:s['kind'] for s in work['payload']['slots']}
            for observation in facts['observations']:
                if kinds.get(observation.get('slot_id'))!='logo':continue
                row=self.logo.rowCount();self.logo.insertRow(row);item=QTableWidgetItem(observation['id']);item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable);self.logo.setItem(row,0,item)
                for column in range(1,5):self.logo.setItem(row,column,QTableWidgetItem(''))
        self.work.currentIndexChanged.connect(logos);logos()
        self.mapping=QCheckBox('另核對已存在客戶與exact版型（不寫入客戶資料）');form.addRow(self.mapping)
        self.mapping_customer=self.line(form,'已核對的主客戶ID');self.mapping_style=self.line(form,'已核對的exact版型關聯ID');self.mapping_reason=self.line(form,'映射核對依據')
        self.button(form,'預覽這一件人工真值版本',self.plan_gold)

    def plan_gold(self):
        logos={}
        for row in range(self.logo.rowCount()):
            values=[self.logo.item(row,column).text().strip() for column in range(5)]
            if any(values[1:]):logos[values[0]]=dict(root_id=values[1],component_ids=[v.strip() for v in values[2].split(',') if v.strip()],text_component_ids=[v.strip() for v in values[4].split(',') if v.strip()],review_reason=values[3],original_correspondence_confirmed=self.truth['whole_logo'].isChecked())
        payload=dict(work_id=self.work.currentData(),rights=dict(basis=self.basis.currentText(),reference=self.rights.text(),use=self.gold_use.currentData()),domain_truth={key:'MANUALLY_VERIFIED' if box.isChecked() else 'INSUFFICIENT_EVIDENCE' for key,box in self.truth.items()},reason=self.gold_reason.text(),evidence=self.gold_evidence.text(),logo_truth=logos or None)
        if self.mapping.isChecked():payload['mapping_truth']=dict(customer_id=self.mapping_customer.text().strip(),style_id=self.mapping_style.text().strip(),review_reason=self.mapping_reason.text())
        self.submit('PLAN_GOLD',payload,'GOLD')

    def policy_form(self):
        form=self.tab('品質政策（不提供猜測門檻）');self.policy_name=self.line(form,'政策名稱');self.policy_basis=self.line(form,'各類門檻與樣本量的核實依據');self.policy_reference=self.line(form,'研究／授權參考');self.confidence=self.line(form,'群組信賴水準（0～1，必填）');self.iou=self.line(form,'框配對IoU（0～1，必填）')
        self.policy_scope=QComboBox();self.policy_scope.addItems(['SYNTHETIC_SELF_CHECK','AUTHORIZED_LOCAL_QUALITY_ACCEPTANCE']);form.addRow('適用範圍',self.policy_scope)
        self.thresholds=QTableWidget(len(DOMAINS),7);self.thresholds.setHorizontalHeaderLabels(['領域','最少獨立群組','最少Gold物件','最低Precision','最低Recall','最高群組失敗率','尺寸最大誤差mm'])
        for row,domain in enumerate(DOMAINS):
            self.thresholds.setItem(row,0,QTableWidgetItem(LABELS[domain]));self.thresholds.item(row,0).setFlags(Qt.ItemIsEnabled)
            for column in range(1,7):self.thresholds.setItem(row,column,QTableWidgetItem(''))
            for column in ((3,4) if domain=='physical_size' else (6,)):self.thresholds.item(row,column).setFlags(Qt.NoItemFlags)
        self.thresholds.setMinimumHeight(380);form.addRow(self.thresholds)
        self.button(form,'預覽逐領域／逐類別品質政策',self.plan_policy)

    def plan_policy(self):
        thresholds={}
        for row,domain in enumerate(DOMAINS):
            value=lambda column:self.thresholds.item(row,column).text().strip()
            data=dict(minimum_independent_groups=int(value(1)),minimum_gold_objects=int(value(2)),maximum_group_failure_rate=float(value(5)))
            if domain=='physical_size':data['maximum_absolute_error_mm']=float(value(6))
            else:data.update(minimum_precision=float(value(3)),minimum_recall=float(value(4)))
            if domain=='field_types':data['required_classes']=list(KINDS)
            thresholds[domain]=data
        self.submit('PLAN_POLICY',dict(name=self.policy_name.text(),thresholds=thresholds,matching_iou=float(self.iou.text()),confidence=float(self.confidence.text()),basis=self.policy_basis.text(),reference=self.policy_reference.text(),scope=self.policy_scope.currentText()),'POLICY')

    def set_form(self):
        form=self.tab('固定獨立驗收集');self.set_name=self.line(form,'驗收集名稱');self.gold_ids=self.line(form,'已核對Gold版本ID（空白分隔）');self.paths=QPlainTextEdit();self.paths.setPlaceholderText('每行一個原始來源檔案；無Gold／未解析來源也須明列');form.addRow('明列來源',self.paths)
        self.evaluation_role=QComboBox();self.evaluation_role.addItem('HOLDOUT：獨立驗收', 'HOLDOUT');self.evaluation_role.addItem('TRAIN：僅描述診斷，不執行訓練','TRAIN');self.evaluation_role.addItem('VALIDATION：僅調參診斷，不是獨立測試','VALIDATION');form.addRow('明確資料角色',self.evaluation_role)
        def choose():
            paths,_=QFileDialog.getOpenFileNames(self,'明列品質來源（本機）','','設計與來源 (*.ai *.pdf *.svg *.eps *.png *.jpg *.jpeg)')
            if paths:self.paths.setPlainText('\n'.join(paths))
        self.button(form,'選擇本機來源',choose)
        self.inventory=QCheckBox('已對照所有來源頁與其中全部實際作品，沒有省略未解析項');self.independence=QCheckBox('已核對內容／近重複／客戶／模板家族獨立性');form.addRow(self.inventory);form.addRow(self.independence);self.set_reason=self.line(form,'獨立群組核對依據')
        self.button(form,'預覽固定來源、真值與獨立群組分母',lambda:self.submit('PLAN_SET',dict(name=self.set_name.text(),gold_ids=self.gold_ids.text().split(),inventory_attested=self.inventory.isChecked(),independence_reviewed=self.independence.isChecked(),review_reason=self.set_reason.text(),declared_paths=[p.strip() for p in self.paths.toPlainText().splitlines() if p.strip()] or None,evaluation_role=self.evaluation_role.currentData()),'SET'))

    def version_form(self):
        form=self.tab('實際可執行版本');self.version_name=self.line(form,'版本名稱');self.model=self.picker(form,'實際語意模型版本','SEMANTIC_MODEL',True)
        self.rules_mode=QComboBox();self.rules_mode.addItem('當前已核實正式規則（保存exact版本）',True);self.rules_mode.addItem('不使用正式規則（作固定A/B比較）',False);form.addRow('規則執行版本',self.rules_mode)
        self.ocr_enabled=QCheckBox('對來源影像執行實際本機OCR（版本與語言模型另存指紋，不外傳）');form.addRow(self.ocr_enabled)
        self.ocr_languages=QComboBox();self.ocr_languages.addItem('繁體中文＋英文',['chi_tra','eng']);self.ocr_languages.addItem('英文',['eng']);form.addRow('實際本機語言模型',self.ocr_languages)
        self.ocr_psm=QComboBox();self.ocr_psm.addItem('稀疏文字（引擎模式11）',11);self.ocr_psm.addItem('單一文字塊（引擎模式6）',6);form.addRow('明確OCR分割模式',self.ocr_psm)
        self.mapping_enabled=QCheckBox('使用預先明列的既有客戶目錄映射');form.addRow(self.mapping_enabled);self.pattern=QComboBox();self.pattern.addItems([r'(?P<code>.+)',r'(?P<code>[0-9]+)',r'(?P<code>[^_]+)_.+',r'(?P<code>[A-Za-z0-9-]+)']);form.addRow('已支援的完整檔名規則',self.pattern);self.catalog_ids=self.line(form,'明列主客戶ID（空白分隔）');self.tolerance=self.line(form,'明確映射尺寸容差mm')
        self.button(form,'保存實際解析器／模型執行版本（不核准品質）',self.freeze_version)

    def freeze_version(self):
        config=None
        if self.mapping_enabled.isChecked():config=dict(code_pattern=self.pattern.currentText(),maximum_size_error_mm=float(self.tolerance.text()),customer_ids=self.catalog_ids.text().split())
        ocr=dict(languages=self.ocr_languages.currentData(),psm=self.ocr_psm.currentData()) if self.ocr_enabled.isChecked() else None
        self.submit('FREEZE_PIPELINE',dict(name=self.version_name.text(),model_id=self.model.currentData(),actor=self.panel.actor.text(),approved=True,mapping_config=config,rule_versions=None if self.rules_mode.currentData() else [],ocr_config=ocr))

    def protocol_form(self):
        form=self.tab('先固定雙側試驗');self.protocol_name=self.line(form,'試驗名稱');self.dataset=self.picker(form,'固定獨立驗收集','QUALITY_SET');self.policy=self.picker(form,'明確品質政策','QUALITY_POLICY');self.baseline=self.picker(form,'基準實際版本','QUALITY_PIPELINE');self.candidate=self.picker(form,'候選實際版本','QUALITY_PIPELINE');self.protocol_reason=self.line(form,'預先固定比較目的／條件')
        self.button(form,'預覽固定A/B、Gold、環境及計算口徑',lambda:self.submit('PLAN_PROTOCOL',dict(name=self.protocol_name.text(),dataset_id=self.dataset.currentData(),policy_id=self.policy.currentData(),pipelines=dict(BASELINE=self.baseline.currentData(),CANDIDATE=self.candidate.currentData()),reason=self.protocol_reason.text()),'PROTOCOL'))

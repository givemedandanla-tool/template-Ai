"""Professional family tools inside the existing native desktop workflow."""
from copy import deepcopy
import json

from PySide6.QtCore import Qt, QItemSelectionModel
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QPushButton, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTabWidget, QSplitter,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QListWidget, QListWidgetItem, QPlainTextEdit, QInputDialog, QCheckBox, QDialog)

from .family_workspace import FamilyWorkspace, records
from .family_rules import FamilyRuleDrafts, relation_key
from .family_scenarios import FamilyScenarios
from .family_batch import FamilyBatches
from .training_store import digest
from .model import Slot, Rect, KINDS, new_id
from .object_dialog import ObjectCanvas

HEALTH = {'READY_PREVIEW':'可試排／未具正式資格', 'QUALIFIED':'資格目前有效',
          'UNKNOWN':'有未確認來源資訊', 'STALE':'來源或版本已失效'}
SEMANTICS = dict(KINDS, mobile='手機', landline='市話')
METRIC_NAMES = dict(left_delta='左緣差', right_delta='右緣差', centre_delta='中心差',
                    vertical_gap='上下間隔', horizontal_gap='水平間隔', baseline_delta='基線差')


def table(headers):
    result = QTableWidget(0, len(headers)); result.setHorizontalHeaderLabels(headers)
    result.setSelectionBehavior(QAbstractItemView.SelectRows)
    result.setEditTriggers(QAbstractItemView.NoEditTriggers)
    return result


def fill(widget, rows):
    widget.setRowCount(len(rows))
    for i, row in enumerate(rows):
        for j, value in enumerate(row):
            widget.setItem(i, j, QTableWidgetItem(str(value) if value is not None else '未知'))
    widget.resizeColumnsToContents()


def checked_items(widget):
    return [widget.item(i).data(Qt.UserRole) for i in range(widget.count())
            if widget.item(i).checkState() == Qt.Checked]


class FamilyWorkbench(QWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner; self.window = owner.window; self.library = owner.library
        self.workspace = FamilyWorkspace(self.library); self.rules = FamilyRuleDrafts(self.library)
        self.scenarios = FamilyScenarios(self.library); self.batches = FamilyBatches(self.library)
        self.store = self.workspace.store
        self.ref = None; self.profile = None; self.draft = None; self.page = 0
        self.selection = {}; self.visible = []; self.worker = None; self.active_job = None
        self.close_after_worker = False; self.busy = False; self.overlays = []; self.buttons = {}
        self.build(); self.restore()

    def actor(self):
        value = self.owner.actor.text().strip()
        if not value:
            raise ValueError('請填寫本機管理者名稱')
        return value

    def say(self, message):
        self.owner.say(message)

    def attempt(self, action):
        try:
            return action()
        except Exception as error:
            self.say(str(error))
            return None

    def button(self, layout, label, action):
        button = QPushButton(label); self.buttons[label] = button
        button.clicked.connect(lambda checked=False: self.attempt(action)); layout.addWidget(button)
        return button

    def tab(self, title):
        widget = QWidget(); layout = QVBoxLayout(widget); self.details.addTab(widget, title)
        return layout

    def build(self):
        layout = QVBoxLayout(self)
        search = QHBoxLayout(); self.query = QLineEdit(); self.query.setPlaceholderText('搜尋家族／資料種類／版本')
        self.model_choice = QComboBox(); self.semantic = QComboBox(); self.semantic.addItem('全部資料種類', '')
        for code, name in SEMANTICS.items():self.semantic.addItem(name, code)
        self.health = QComboBox(); self.health.addItem('全部狀態', '')
        for code, name in HEALTH.items():self.health.addItem(name, code)
        for widget in (self.model_choice, self.query, self.semantic, self.health):search.addWidget(widget)
        self.button(search, '查詢家族', self.search); layout.addLayout(search)
        worksets = QHBoxLayout(); self.views = QComboBox(); worksets.addWidget(self.views)
        self.button(worksets, '開啟工作集', self.open_view); self.button(worksets, '保存目前篩選', self.save_view)
        self.button(worksets, '重新整理', self.refresh); self.button(worksets, '保存接續位置', self.remember)
        layout.addLayout(worksets)
        split = QSplitter(); layout.addWidget(split, 1)
        catalog = QWidget(); left = QVBoxLayout(catalog)
        self.families = table(['家族', '尺寸 mm', '人物', '欄位數', '獨立支持', '狀態'])
        self.families.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.families.itemSelectionChanged.connect(self.selected); left.addWidget(self.families, 1)
        paging = QHBoxLayout(); self.previous = self.button(paging, '上一頁家族', lambda:self.change_page(-1))
        self.next = self.button(paging, '下一頁家族', lambda:self.change_page(1)); left.addLayout(paging)
        self.summary = QLabel(); self.summary.setWordWrap(True); left.addWidget(self.summary)
        self.button(left, '比較兩個已選家族', self.compare_selected)
        self.button(left, '代表案例', self.representatives)
        self.button(left, '清除全部家族勾選', self.clear_selection)
        split.addWidget(catalog)
        self.details = QTabWidget(); split.addWidget(self.details); split.setSizes([440, 740])
        self.build_overview(); self.build_compatibility(); self.build_relations()
        self.build_variants(); self.build_typography(); self.build_sources()
        self.build_cases(); self.build_versions(); self.build_jobs()

    def build_overview(self):
        layout = self.tab('版面與角色')
        bar = QHBoxLayout(); self.draft_choice = QComboBox(); bar.addWidget(self.draft_choice, 1)
        self.draft_choice.currentIndexChanged.connect(lambda:self.attempt(self.load_draft))
        self.button(bar, '新規則草稿', self.new_draft); layout.addLayout(bar)
        edits = QHBoxLayout(); self.button(edits, '復原規則', lambda:self.history('UNDO'))
        self.button(edits, '重做規則', lambda:self.history('REDO')); layout.addLayout(edits)
        self.scope = QLabel('來源事實、家族規則與當次稿件分開保存；此處是專業規則草稿。')
        self.scope.setWordWrap(True); layout.addWidget(self.scope)
        split = QSplitter(); self.roles = QTreeWidget(); self.roles.setHeaderLabels(['人物／公司與欄位角色'])
        self.roles.currentItemChanged.connect(self.role_selected)
        self.canvas = ObjectCanvas(); self.canvas.readonly = True; self.canvas.resize_enabled = False
        self.canvas.set_mode('edit'); self.canvas.selection_ids.connect(self.canvas_selected)
        split.addWidget(self.roles); split.addWidget(self.canvas); split.setSizes([220, 480]); layout.addWidget(split, 1)
        self.role_info = QLabel(); self.role_info.setWordWrap(True); layout.addWidget(self.role_info)

    def build_compatibility(self):
        layout = self.tab('資料與容器')
        self.containers = table(['容器', '可觀察承接資料', '歸屬', '支持', '對應依據'])
        self.containers.currentCellChanged.connect(lambda *args:self.load_container())
        layout.addWidget(self.containers, 1)
        self.container_types = QListWidget(); layout.addWidget(self.container_types)
        self.button(layout, '保存容器承接限制', self.limit_container)
        form = QFormLayout(); self.semantic_role = QComboBox(); self.semantic_value = QComboBox()
        self.semantic_role.currentIndexChanged.connect(self.load_semantic)
        form.addRow('預設位置角色', self.semantic_role); form.addRow('優先資料種類', self.semantic_value); layout.addLayout(form)
        self.button(layout, '保存預設資料位置', self.default_semantic)
        note = QLabel('觀察、政策允許及實際排得下是三項檢查；框大小接近不代表可交換。')
        note.setWordWrap(True); layout.addWidget(note)

    def build_relations(self):
        layout = self.tab('相對關係')
        self.relations = table(['角色一', '角色二', '關係', '來源中心值 mm', '獨立支持', '強度'])
        layout.addWidget(self.relations, 1)
        self.strength = QComboBox()
        for name, code in [('保留柔性偏好','SOFT'), ('設為硬條件','HARD'), ('停用此項偏好','OFF')]:self.strength.addItem(name, code)
        layout.addWidget(self.strength); self.button(layout, '保存關係強度', self.set_strength)
        note = QLabel('僅調整已有來源支持的關係；客戶明確位置意圖優先，必要字面與欄框仍由核心聯動。')
        note.setWordWrap(True); layout.addWidget(note)

    def build_variants(self):
        layout = self.tab('合法變體')
        layout.addWidget(QLabel('預設順序：可拖動清單排序，再明確保存。'))
        self.order = QListWidget(); self.order.setDragDropMode(QAbstractItemView.InternalMove); layout.addWidget(self.order)
        self.button(layout, '保存預設順序', self.set_order)
        layout.addWidget(QLabel('來源曾出現的可選欄位；取消可選代表該角色必須存在。'))
        self.optional = QListWidget(); layout.addWidget(self.optional)
        self.button(layout, '保存可選欄位', lambda:self.apply_operation(dict(kind='OPTIONAL_ROLES',roles=checked_items(self.optional))))
        layout.addWidget(QLabel('已觀察聯合欄位組合；未勾選的組合不在此草稿允許範圍。'))
        self.patterns = QListWidget(); layout.addWidget(self.patterns)
        self.button(layout, '保存允許組合', lambda:self.apply_operation(dict(kind='ALLOWED_PATTERNS',patterns=checked_items(self.patterns))))

    def build_typography(self):
        layout = self.tab('聯合字面')
        self.style_role = QComboBox(); self.style_role.currentIndexChanged.connect(self.load_styles); layout.addWidget(self.style_role)
        self.styles = table(['來源例', '字型', '來源 pt', '水平比例', '字距 mm', '欄寬 mm', '欄高 mm', '對齊／文字流'])
        layout.addWidget(self.styles, 1); self.button(layout, '以此來源配置作預選', self.prefer_style)
        self.joint_info = QLabel(); self.joint_info.setWordWrap(True); layout.addWidget(self.joint_info)
        layout.addWidget(QLabel('字級、字寬、欄框與間距以聯合配置核對；不是客戶細參數控制。'))

    def build_sources(self):
        layout = self.tab('來源與補救')
        self.sources = table(['作品', '角色', '來源版次', '獨立來源群'])
        layout.addWidget(self.sources, 1)
        self.button(layout, '原稿欄位標記', self.annotate_source)
        self.button(layout, '來源文字與複合字面核對', self.review_source)
        self.button(layout, '本地還原與字型診斷', self.owner.open_recovery)
        for label, method in [('既有批次修正','batch_object_center'),('字型庫','font_center'),
                              ('來源重新連結','relink_source'),('本地備份與還原','backup_center')]:
            self.button(layout, label, lambda method=method:self.open_existing(method))
        note = QLabel('原稿、字型與案例資料留本地。來源事實更新後需重建受影響模型，不會直接修改舊模型。')
        note.setWordWrap(True); layout.addWidget(note)

    def build_cases(self):
        layout = self.tab('案例試排')
        bar = QHBoxLayout(); self.case_choice = QComboBox(); self.case_choice.currentIndexChanged.connect(self.load_case)
        bar.addWidget(self.case_choice, 1); self.button(bar, '新增案例', lambda:self.edit_case(True))
        self.button(bar, '編輯案例資料', lambda:self.edit_case(False)); layout.addLayout(bar)
        dims = QHBoxLayout(); self.case_name = QLineEdit('案例一'); dims.addWidget(self.case_name)
        self.width = QDoubleSpinBox(); self.height = QDoubleSpinBox()
        for widget in (self.width,self.height):widget.setRange(.01,2000);widget.setDecimals(3);dims.addWidget(widget)
        layout.addLayout(dims)
        self.case_mode = QComboBox(); self.case_mode.addItems(['目前草稿試排','原始規則試排','原始／草稿前後比較'])
        layout.addWidget(self.case_mode); self.button(layout, '執行所選案例', self.run_case)
        self.run_choice = QComboBox(); self.run_choice.currentIndexChanged.connect(self.show_run); layout.addWidget(self.run_choice)
        self.case_canvas = ObjectCanvas(); self.case_canvas.readonly = True; self.case_canvas.resize_enabled = False
        layout.addWidget(self.case_canvas, 1); self.case_status = QLabel(); self.case_status.setWordWrap(True); layout.addWidget(self.case_status)
        self.button(layout, '以此資料進入當次稿件', self.create_session)

    def build_versions(self):
        layout = self.tab('差異與影響')
        self.report = QPlainTextEdit(); self.report.setReadOnly(True); layout.addWidget(self.report, 1)
        self.button(layout, '查看草稿差異', self.show_differences)
        self.button(layout, '查看完整影響數量', self.show_impact)
        pages=QHBoxLayout();self.impact_page=0
        self.button(pages,'上一頁影響項目',lambda:self.show_impact(-1))
        self.button(pages,'下一頁影響項目',lambda:self.show_impact(1));layout.addLayout(pages)
        self.reviewed = QCheckBox('我已核對此草稿差異，建立待驗證的新模型候選'); layout.addWidget(self.reviewed)
        self.button(layout, '建立規則候選版本', self.create_candidate)
        self.button(layout, '將目前模型用於預覽／回退', self.activate_preview)
        self.button(layout, '啟用已具正式資格的目前模型', self.activate_formal)
        self.rebase_choice = QComboBox(); layout.addWidget(self.rebase_choice)
        self.button(layout, '將草稿核對後移至所選家族', self.rebase)

    def build_jobs(self):
        layout = self.tab('批次與接續')
        self.button(layout, '預覽將目前操作套至勾選家族', self.preview_batch)
        self.batch_review = QCheckBox('已核對下方逐項差異與固定目標版本'); layout.addWidget(self.batch_review)
        self.batch_table = table(['家族', '操作', '預檢', '說明']); layout.addWidget(self.batch_table, 1)
        self.button(layout, '建立並執行已核對批次', self.submit_batch)
        self.jobs = QComboBox(); layout.addWidget(self.jobs)
        self.button(layout, '接續所選批次', self.resume_job)
        self.button(layout, '處理完目前項目後暫停', self.pause_job)
        self.button(layout, '局部回復所選規則批次', self.undo_batch)
        self.job_status = QLabel(); self.job_status.setWordWrap(True); layout.addWidget(self.job_status)
        self.batch_plan = None; self.last_operation = None

    def query_value(self):
        result = dict(text=self.query.text(), semantic=self.semantic.currentData())
        if not result['semantic']:result.pop('semantic')
        if self.model_choice.currentData():result['model_id'] = self.model_choice.currentData()
        if self.health.currentData():result['health'] = self.health.currentData()
        return result

    def search(self):
        self.page = 0; self.refresh()

    def refresh(self):
        if self.busy:return
        self.busy = True
        try:
            selected_model = self.model_choice.currentData(); self.model_choice.clear(); self.model_choice.addItem('所有模型版本', '')
            for model in records(self.store,'DESIGN_MODEL'):
                self.model_choice.addItem(model['id'][:12]+' · '+model.get('formal_qualification','未驗證'),model['id'])
            index = self.model_choice.findData(selected_model)
            if index >= 0:self.model_choice.setCurrentIndex(index)
            self.result = self.workspace.index(self.query_value(),page=self.page)
            self.visible = self.result['rows']; self.families.blockSignals(True)
            fill(self.families, [[r['ref']['family_id'][:15], '／'.join('×'.join(map(str,s)) for s in r['sizes']),
                  r['people'], '/'.join(map(str,r['field_counts'])), r['independent_support'], HEALTH[r['health']]] for r in self.visible])
            for i,r in enumerate(self.visible):
                if r['id'] in self.selection:
                    self.families.selectionModel().select(self.families.model().index(i,0),QItemSelectionModel.Select|QItemSelectionModel.Rows)
            self.families.blockSignals(False)
            self.previous.setEnabled(self.page>0);self.next.setEnabled((self.page+1)*48<self.result['total'])
            self.summary.setText(f"共 {self.result['total']} 家族版本；第 {self.page+1} 頁；已勾選 {len(self.selection)}。來源／固定模板／當次稿件各自保存。")
            current_view=self.views.currentData();self.views.clear()
            for view in records(self.store,'FAMILY_VIEW'):self.views.addItem(view['name'],view['id'])
            if self.views.findData(current_view)>=0:self.views.setCurrentIndex(self.views.findData(current_view))
            self.refresh_jobs()
        finally:self.busy = False
        if self.ref:
            self.attempt(lambda:self.load_family(self.ref))
        elif self.visible:
            self.families.selectRow(0)

    def change_page(self, delta):
        self.page = max(0,self.page+delta); self.refresh()

    def selected(self):
        if self.busy:return
        indices={index.row() for index in self.families.selectionModel().selectedRows()}
        for i,row in enumerate(self.visible):
            if i in indices:self.selection.setdefault(row['id'],deepcopy(row['ref']))
            else:self.selection.pop(row['id'],None)
        self.summary.setText(f"共 {self.result['total']} 家族版本；已勾選 {len(self.selection)}，跨頁選取會保留。")
        current=self.families.currentRow()
        if current>=0 and current<len(self.visible):self.attempt(lambda:self.load_family(self.visible[current]['ref']))

    def clear_selection(self):
        self.selection.clear();self.families.clearSelection();self.refresh()

    def save_view(self):
        name,accepted=QInputDialog.getText(self,'保存工作集','名稱')
        if accepted:
            self.workspace.save_view(name,self.query_value(),self.actor());self.refresh()

    def open_view(self):
        view=self.store.get('FAMILY_VIEW',self.views.currentData())
        if not view:raise ValueError('請選擇已保存工作集')
        query=view['query'];self.query.setText(query.get('text',''))
        for widget,key in ((self.semantic,'semantic'),(self.health,'health'),(self.model_choice,'model_id')):
            index=widget.findData(query.get(key,''));widget.setCurrentIndex(max(0,index))
        self.page=0;self.refresh()

    def load_family(self,ref):
        self.workspace.resolve(ref);self.ref=deepcopy(ref)
        self.reload_drafts();self.load_draft();self.reload_cases()

    def reload_drafts(self, preferred=None):
        current=preferred or self.draft_choice.currentData();self.draft_choice.blockSignals(True);self.draft_choice.clear()
        self.draft_choice.addItem('原始學習規則（唯讀）',None)
        for row in records(self.store,'FAMILY_DRAFT'):
            if row['base_ref']==self.ref and row['state']!='ARCHIVED':self.draft_choice.addItem(row['name']+' · v'+str(row['revision']),row['id'])
        index=self.draft_choice.findData(current);self.draft_choice.setCurrentIndex(max(0,index));self.draft_choice.blockSignals(False)

    def load_draft(self):
        if not self.ref:return
        self.draft=None
        identity=self.draft_choice.currentData()
        if identity:self.draft,_,_,profile=self.rules.compiled(identity)
        else:_,_,profile=self.workspace.resolve(self.ref)
        self.profile=profile;self.render_profile()

    def new_draft(self):
        if not self.ref:raise ValueError('請先選擇家族')
        draft=self.rules.create(self.ref,self.actor(),'家族規則草稿')
        self.reload_drafts(draft['id']);self.load_draft();self.remember()

    def apply_operation(self,operation):
        if self.draft is None:self.new_draft()
        saved=self.rules.command(self.draft['id'],self.draft['revision'],new_id(),'APPLY',self.actor(),operation)
        self.last_operation=deepcopy(operation);self.batch_plan=None;self.batch_review.setChecked(False)
        self.reload_drafts(saved['id']);self.load_draft();self.remember()
        self.say('規則草稿已保存；來源、舊模型與已確認稿件保持原版本。')

    def history(self,action):
        if not self.draft:raise ValueError('請先選擇規則草稿')
        saved=self.rules.command(self.draft['id'],self.draft['revision'],new_id(),action,self.actor())
        self.reload_drafts(saved['id']);self.load_draft();self.remember()

    def render_profile(self):
        profile=self.profile;self.roles.blockSignals(True);self.roles.clear();groups={}
        for role in profile['roles']:
            owner=role['owner_port']
            if owner not in groups:
                groups[owner]=QTreeWidgetItem([('人物 ' if owner.startswith('p') else '公司 ')+owner]);self.roles.addTopLevelItem(groups[owner])
            item=QTreeWidgetItem([KINDS.get(role['kind'],role['kind'])+' · '+role['key']]);item.setData(0,Qt.UserRole,role['key']);groups[owner].addChild(item)
        self.roles.expandAll();self.roles.blockSignals(False)
        width,height=profile['observed_dimensions_mm'][0]
        slots=[Slot(r['kind'],r['owner_port'],Rect(r['frame_centre'][0]*width,r['frame_centre'][1]*height,
                    r['frame_centre'][2]*width,r['frame_centre'][3]*height),id=r['key']) for r in profile['roles']]
        self.canvas.set_content(width,height,slots=slots);self.canvas.fit();self.overlays=[]
        self.scope.setText(('草稿 v'+str(self.draft['revision']) if self.draft else '原始學習規則，唯讀')+'；此畫布顯示欄框與關係，實際字形請看案例試排。')
        self.semantic_role.blockSignals(True);self.style_role.blockSignals(True);self.semantic_role.clear();self.style_role.clear()
        for role in profile['roles']:
            self.semantic_role.addItem(role['key'],role['key'])
            if role['kind']!='logo':self.style_role.addItem(role['key'],role['key'])
        self.semantic_role.blockSignals(False);self.style_role.blockSignals(False);self.load_semantic();self.load_styles()
        self.container_rows=profile['field_capability_profiles']
        fill(self.containers,[[r['container_key'],', '.join(SEMANTICS.get(t,t) for t in r['observed_semantic_types']),
              ', '.join(r['owner_ports']),r['support'],', '.join(r['correspondence_basis'])] for r in self.container_rows])
        if self.container_rows:self.containers.selectRow(0)
        self.relation_rows=[]
        for relation in profile['relations']:
            for metric,distribution in relation['residuals'].items():
                if metric not in METRIC_NAMES or distribution.get('centre') is None:continue
                dimension=height if metric in ('baseline_delta','vertical_gap') else width
                strength=profile.get('editor_relation_strengths',{}).get(relation_key(relation['left'],relation['right'],metric),'SOFT')
                self.relation_rows.append(dict(relation,metric=metric,target=distribution['centre']*dimension,strength=strength,support=distribution.get('support',0)))
        fill(self.relations,[[r['left'],r['right'],METRIC_NAMES[r['metric']],round(r['target'],4),r['support'],r['strength']] for r in self.relation_rows])
        self.order.clear();all_keys=[r['key'] for r in profile['roles']]
        order=profile['grammar']['default_order']+[key for key in all_keys if key not in profile['grammar']['default_order']]
        for key in order:item=QListWidgetItem(key);item.setData(Qt.UserRole,key);self.order.addItem(item)
        self.optional.clear()
        for role in profile['roles']:
            if role['observed_optional']:
                item=QListWidgetItem(role['key']);item.setData(Qt.UserRole,role['key']);item.setFlags(item.flags()|Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if role['key'] in profile['grammar']['optional_roles'] else Qt.Unchecked);self.optional.addItem(item)
        self.patterns.clear();allowed=profile['grammar'].get('editor_allowed_patterns')
        for row in profile['grammar']['observed_joint_counts']:
            key=digest(row['pattern']);item=QListWidgetItem('、'.join(k+' ×'+str(v) for k,v in sorted(row['pattern'].items()))+'；獨立支持 '+str(row['independent_support']))
            item.setData(Qt.UserRole,key);item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Checked if allowed is None or key in allowed else Qt.Unchecked);self.patterns.addItem(item)
        self.source_rows=self.workspace.sources(self.ref)
        fill(self.sources,[[self.library.artwork(r['work_id'])['name'],r['role'],r['pins']['work_revision'],r['lineage_group'][:16]] for r in self.source_rows])
        self.rebase_choice.clear()
        for row in self.visible:self.rebase_choice.addItem(row['id'][:30],row['ref'])
        if profile['roles']:self.roles.setCurrentItem(groups[profile['roles'][0]['owner_port']].child(0))
        self.reviewed.setChecked(False)

    def role_selected(self, item, previous=None):
        if not item or not self.profile:return
        key=item.data(0,Qt.UserRole)
        if not key:return
        role=next(r for r in self.profile['roles'] if r['key']==key)
        self.role_info.setText(f"{key}；獨立支持 {role['support']}；字面已知 {role['typography_known_examples']}／{role['present_examples']}；可選 {role['observed_optional']}。")
        if self.canvas.selection_intent!={key}:self.canvas.select_id(key)
        for widget in (self.semantic_role,self.style_role):
            index=widget.findData(key)
            if index>=0:widget.setCurrentIndex(index)
        for overlay in self.overlays:
            if overlay.scene():self.canvas.scene().removeItem(overlay)
        self.overlays=[]
        roles={r['key']:r for r in self.profile['roles']};width,height=self.profile['observed_dimensions_mm'][0]
        for relation in self.profile['relations']:
            if key not in (relation['left'],relation['right']):continue
            a,b=roles[relation['left']]['frame_centre'],roles[relation['right']]['frame_centre']
            pen=QPen(QColor('#7c3aed'));pen.setCosmetic(True)
            line=self.canvas.scene().addLine((a[0]+a[2]/2)*width,(a[1]+a[3]/2)*height,
                                             (b[0]+b[2]/2)*width,(b[1]+b[3]/2)*height,pen)
            line.setZValue(1);self.overlays.append(line)

    def canvas_selected(self, ids):
        if not ids:return
        for i in range(self.roles.topLevelItemCount()):
            parent=self.roles.topLevelItem(i)
            for j in range(parent.childCount()):
                child=parent.child(j)
                if child.data(0,Qt.UserRole)==ids[0] and child!=self.roles.currentItem():
                    self.roles.setCurrentItem(child);return

    def load_container(self):
        self.container_types.clear();index=self.containers.currentRow()
        if not self.profile or not 0<=index<len(self.container_rows):return
        row=self.container_rows[index];allowed=self.profile.get('editor_container_types',{}).get(row['container_key'],row['observed_semantic_types'])
        for semantic in row['observed_semantic_types']:
            item=QListWidgetItem(SEMANTICS.get(semantic,semantic));item.setData(Qt.UserRole,semantic)
            item.setFlags(item.flags()|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Checked if semantic in allowed else Qt.Unchecked)
            self.container_types.addItem(item)

    def limit_container(self):
        index=self.containers.currentRow()
        if not 0<=index<len(self.container_rows):raise ValueError('先選擇容器')
        self.apply_operation(dict(kind='CONTAINER_TYPES',container=self.container_rows[index]['container_key'],types=checked_items(self.container_types)))

    def load_semantic(self):
        self.semantic_value.clear()
        if not self.profile:return
        key=self.semantic_role.currentData()
        values=sorted({s['semantic_type'] for data in self.profile['data_requirement_profiles'] for s in data['presentation_evidence'] if s['role_key']==key})
        for value in values:self.semantic_value.addItem(SEMANTICS.get(value,value),value)
        default=self.profile['grammar'].get('default_semantic_roles',{}).get(key)
        index=self.semantic_value.findData(default)
        if index>=0:self.semantic_value.setCurrentIndex(index)

    def default_semantic(self):
        self.apply_operation(dict(kind='DEFAULT_SEMANTIC',role=self.semantic_role.currentData(),semantic=self.semantic_value.currentData()))

    def set_strength(self):
        index=self.relations.currentRow()
        if not 0<=index<len(self.relation_rows):raise ValueError('先選擇來源支持的相對關係')
        row=self.relation_rows[index]
        self.apply_operation(dict(kind='RELATION_STRENGTH',left=row['left'],right=row['right'],metric=row['metric'],strength=self.strength.currentData()))

    def set_order(self):
        self.apply_operation(dict(kind='DEFAULT_ORDER',order=[self.order.item(i).data(Qt.UserRole) for i in range(self.order.count())]))

    def load_styles(self):
        if not self.profile:return
        key=self.style_role.currentData()
        self.style_rows=[s for data in self.profile['data_requirement_profiles'] for s in data['presentation_evidence'] if s['role_key']==key]
        fill(self.styles,[[s['example_id'][:15],', '.join((s.get('source_font_ref') or {}).get('families',[])) or '未知',
            s['joint']['source_pt'],s['joint']['horizontal_scale'],s['joint']['tracking_mm'],
            s['joint']['frame_width_mm'],s['joint']['frame_height_mm'],
            str(s['align'])+'／'+str((s.get('source_text_flow') or {}).get('break_rule','未確認'))] for s in self.style_rows])
        role=next((r for r in self.profile['roles'] if r['key']==key),{})
        model=role.get('conditional_joint_model',{})
        self.joint_info.setText('聯合模式 '+str(len(model.get('modes',[])))+'；輸出：字級、水平縮放、字距、欄寬與欄高。支持域外仍需實測，不能由各項最小最大值自由拼接。')

    def prefer_style(self):
        index=self.styles.currentRow()
        if not 0<=index<len(self.style_rows):raise ValueError('先選擇已核對來源配置')
        row=self.style_rows[index]
        self.apply_operation(dict(kind='PREFER_STYLE',role=row['role_key'],source_example=row['example_id']))

    def selected_source(self):
        index=self.sources.currentRow()
        if not 0<=index<len(self.source_rows):raise ValueError('先選擇來源作品')
        return self.source_rows[index]

    def annotate_source(self):
        from .annotation_dialog import AnnotationDialog
        dialog=AnnotationDialog(self.window,self.selected_source()['work_id'],self)
        dialog.exec()
        self.say('來源標記已由既有工作台處理；若事實改變，請重新建立學習模型。')

    def review_source(self):
        from .family_source_dialog import FamilySourceDialog
        dialog=FamilySourceDialog(self.window,self.selected_source()['work_id'],self)
        dialog.exec()

    def open_existing(self,method):
        action=getattr(self.window,method,None)
        if action is None:raise ValueError('請由完整本體主視窗開啟此既有工具')
        action()

    def representatives(self):
        if not self.ref:raise ValueError('先選擇家族')
        result=self.workspace.representatives(self.ref)
        lines=[f"已挑 {len(result['selected'])} 個獨立來源案例；未涵蓋分層 {result['uncovered_strata']}。"]
        lines.extend(row['example_id']+' · '+row['reason'] for row in result['selected'])
        lines.append('這是審查選取；未將抽樣結果當成全庫美學合格。')
        self.report.setPlainText('\n'.join(lines));self.details.setCurrentIndex(7)

    def compare_selected(self):
        refs=list(self.selection.values())
        if len(refs)!=2:raise ValueError('請跨頁或同頁精確選擇兩個家族版本')
        result=self.workspace.compare(*refs)
        self.report.setPlainText('家族比較：保留兩者來源，不自動合併。\n'+self.describe_differences(result['differences']))
        self.details.setCurrentIndex(7)

    @staticmethod
    def describe_differences(rows):
        names=dict(roles='欄位角色／聯合模型',grammar='可選／重複／預選',relations='相對關係',
            data_requirement_profiles='資料需求',field_capability_profiles='容器能力',conditional_geometry='條件幾何',
            object_spacing_rules='物件間距',observed_dimensions_mm='已觀察尺寸',editor_relation_strengths='關係強度',
            editor_container_types='承接限制',editor_preferred_sources='預選字面')
        return '\n\n'.join(names.get(row['section'],row['section'])+'\n修改前：'+json.dumps(row['before'],ensure_ascii=False,indent=2)+
            '\n修改後：'+json.dumps(row['after'],ensure_ascii=False,indent=2) for row in rows) if rows else '沒有功能規則差異。'

    def show_differences(self):
        if not self.draft:raise ValueError('先選擇草稿')
        self.report.setPlainText(self.describe_differences(self.rules.differences(self.draft['id'])))

    def show_impact(self,delta=0):
        if not self.ref:raise ValueError('先選擇家族')
        self.impact_page=max(0,self.impact_page+delta) if delta else 0
        result=self.workspace.impact(self.ref,page=self.impact_page)
        lines=[f"完整影響總數 {result['total']}；已確認輸出保留原檔，重用時仍核對權利。"]
        lines.extend(kind+'：'+str(count) for kind,count in sorted(result['counts'].items()))
        lines.append('影響項目第 '+str(self.impact_page+1)+' 頁；每頁100筆，可用上一頁／下一頁查看。')
        lines.extend(row['kind']+' · '+row['id']+' · '+row['action'] for row in result['rows'])
        self.report.setPlainText('\n'.join(lines));self.say('影響數量完整；此步沒有套用變更。')

    def create_candidate(self):
        if not self.draft:raise ValueError('先選擇草稿')
        candidate=self.rules.create_candidate(self.draft['id'],self.draft['revision'],self.actor(),self.reviewed.isChecked())
        if self.owner.models.findData(candidate['id'])<0:self.owner.models.addItem(candidate['id']+' · 待驗證',candidate['id'])
        self.owner.models.setCurrentIndex(self.owner.models.findData(candidate['id']))
        self.say('新規則候選已保存，尚未啟用；需分別核對預覽與正式資格。')
        self.refresh();self.remember()

    def activate_preview(self):
        if not self.ref:raise ValueError('先選擇模型中的家族')
        active=self.store.get('DESIGN_ACTIVE','local-layout')
        self.workspace.learning.activate(self.ref['model_id'],active['revision'] if active else 0,self.actor(),
            dict(version='family-workbench-preview-1',basis='管理者明確選擇此家族所在模型預覽／回退',
                 production=False,enable_joint_prediction=True),True)
        self.say('已明確選擇預覽模型；舊確認稿保持原檔。')

    def activate_formal(self):
        if not self.ref:raise ValueError('先選擇家族')
        from .design_qualification import validate_certificate
        model,_,_=self.workspace.resolve(self.ref);certificate=validate_certificate(self.library,model)
        active=self.store.get('DESIGN_ACTIVE','local-layout')
        self.workspace.learning.activate(model['id'],active['revision'] if active else 0,self.actor(),
            dict(certificate['plan']['layout_policy'],production=True,basis='管理者核對正式資格後採用'),True)
        self.say('已採用具目前有效正式資格的模型。')

    def rebase(self):
        if not self.draft:raise ValueError('先選擇草稿')
        target=self.rebase_choice.currentData()
        if not target:raise ValueError('先選擇目標家族版本')
        saved=self.rules.rebase(self.draft['id'],target,self.actor())
        self.ref=target;self.reload_drafts(saved['id']);self.load_draft();self.reload_cases();self.remember()

    def reload_cases(self,preferred=None):
        current=preferred or self.case_choice.currentData();self.case_choice.blockSignals(True);self.case_choice.clear()
        for row in records(self.store,'FAMILY_CASE'):
            if row['ref']==self.ref:self.case_choice.addItem(row['name']+' · v'+str(row['revision']),row['id'])
        index=self.case_choice.findData(current);self.case_choice.setCurrentIndex(max(0,index));self.case_choice.blockSignals(False)
        self.load_case()

    def load_case(self):
        identity=self.case_choice.currentData()
        if identity:
            case=self.store.get('FAMILY_CASE',identity);self.case_name.setText(case['name'])
            self.width.setValue(case['width_mm']);self.height.setValue(case['height_mm'])
        elif self.profile:
            self.width.setValue(self.profile['observed_dimensions_mm'][0][0]);self.height.setValue(self.profile['observed_dimensions_mm'][0][1])
        current=self.run_choice.currentData();self.run_choice.blockSignals(True);self.run_choice.clear()
        for run in records(self.store,'FAMILY_RUN'):
            if run['case_ref']['id']==identity:self.run_choice.addItem(('草稿' if run['draft_ref'] else '原規則')+' · '+run['status']+' · '+run['id'][-8:],run['id'])
        index=self.run_choice.findData(current);self.run_choice.setCurrentIndex(max(0,index));self.run_choice.blockSignals(False)
        self.show_run()

    def edit_case(self,new=False):
        if not self.ref:raise ValueError('先選擇家族')
        from .input_graph_dialog import InputGraphDialog
        identity=None if new else self.case_choice.currentData()
        if not new and not identity:raise ValueError('先選擇案例')
        old=self.scenarios.current(identity) if identity else None
        dialog=InputGraphDialog(self.window,old['input_graph'] if old else None)
        if dialog.exec()!=QDialog.Accepted:return
        case=self.scenarios.save(self.ref,self.case_name.text(),dialog.graph,self.width.value(),self.height.value(),
            self.actor(),case_id=identity,expected_revision=old['revision'] if old else 0,
            intents=old['intents'] if old else [],policy=old['policy'] if old else None)
        self.reload_cases(case['id']);self.remember();self.say('案例資料已保存於本地；不會變成訓練美學真值。')

    def run_case(self):
        identity=self.case_choice.currentData()
        if not identity:raise ValueError('先建立案例')
        mode=self.case_mode.currentIndex();draft_id=self.draft['id'] if self.draft and mode!=1 else None
        if mode==2 and not draft_id:raise ValueError('前後比較需要已選規則草稿')
        job=self.batches.cases([identity],self.actor(),draft_id)
        if mode==2:
            # Distinct original/draft items in one frozen job; no tuning labels.
            items=deepcopy(job['plan']['items']);original=deepcopy(items[0]);original['draft_id']=None;original['draft_revision']=None
            job=self.batches.jobs.create('FAMILY_CASE_REVIEW',dict(items=[original,*items]),self.actor(),True)
        self.start_job(job)

    def show_run(self):
        identity=self.run_choice.currentData()
        if not identity:return
        try:
            run=self.scenarios.checked(identity)
            if run['candidate']:
                candidate=self.scenarios.candidate(identity)
                from .render import card_view_image
                self.case_canvas.set_content(candidate.template.width_mm,candidate.template.height_mm,
                    image=card_view_image(candidate,120),slots=candidate.template.slots);self.case_canvas.fit()
            else:self.case_canvas.set_content(self.width.value(),self.height.value())
            self.case_status.setText(run['status']+'；實測合法候選 '+str(run['observed_legal_results'])+
                '；'+('已完成有限搜尋' if run['complete_search'] else '搜尋未完整')+'；未取得生產或美學資格。')
        except (ValueError,KeyError,OSError) as error:
            self.case_canvas.set_content(max(.01,self.width.value()),max(.01,self.height.value()))
            self.case_status.setText('歷史結果已過期：'+str(error))

    def create_session(self):
        case=self.scenarios.current(self.case_choice.currentData())
        from .input_graph import InputGraph
        session=self.owner.sessions.create(InputGraph(case['input_graph']),case['width_mm'],case['height_mm'],
            self.actor(),self.ref['model_id'],case['policy'])
        self.owner.session_id=session['id'];self.owner.refresh_draft();self.owner.save_workspace()
        self.owner.tabs.setCurrentIndex(2);self.say('已建立當次稿件；需重新求解、核對並確認輸出。')

    def preview_batch(self):
        if not self.last_operation:raise ValueError('先在單一家族保存一項規則操作，再預覽相同操作的適用範圍')
        self.batch_plan=self.batches.plan_rules(list(self.selection.values()),self.last_operation)
        fill(self.batch_table,[[r['ref']['family_id'][:16],r['operation']['kind'],r['precheck'],r['reason'] or '已核對來源與差異'] for r in self.batch_plan['items']])
        self.batch_review.setChecked(False);self.details.setCurrentIndex(8)

    def submit_batch(self):
        if not self.batch_plan:raise ValueError('請先預覽確切批次差異')
        job=self.batches.submit(self.batch_plan,self.actor(),self.batch_review.isChecked());self.start_job(job)

    def refresh_jobs(self):
        current=self.jobs.currentData();self.jobs.clear()
        for job in records(self.store,'DESIGN_JOB'):
            if job['kind'].startswith('FAMILY_'):
                self.jobs.addItem(job['id'][:12]+' · '+self.batches.jobs.state(job['id'])+' · '+str(job['next_index'])+'/'+str(job['item_count']),job['id'])
        index=self.jobs.findData(current)
        if index>=0:self.jobs.setCurrentIndex(index)

    def start_job(self,job):
        if self.worker is not None:raise ValueError('已有家族工作正在執行')
        from .design_learning_dialog import DesignWorker
        claimed=self.batches.jobs.claim(job['id'],job['revision']);self.active_job=job['id']
        self.worker=DesignWorker(self.library.root,job['id'],claimed['owner']['token'])
        self.worker.progress.connect(lambda p:self.job_status.setText('已完成 '+str(p['done'])+'／'+str(p['total'])))
        self.worker.failed.connect(self.say);self.worker.finished.connect(self.worker_finished)
        self.worker.start();self.remember()

    def worker_finished(self):
        worker=self.worker;self.worker=None
        if worker:worker.deleteLater()
        job=self.batches.jobs.current(self.active_job)
        rows=self.batches.jobs.results(self.active_job)
        self.job_status.setText(job['phase']+'；已保存 '+str(job['next_index'])+'／'+str(job['item_count'])+'；'+str(job.get('summary') or '可接續'))
        fill(self.batch_table,[[r['ref']['family_id'][:16],job['kind'],r['status'],r.get('reason','逐項結果已保存')] for r in rows])
        self.refresh_jobs();self.reload_cases();self.remember()
        if self.close_after_worker:self.owner.close()

    def resume_job(self):
        identity=self.jobs.currentData()
        if not identity:raise ValueError('先選擇批次')
        self.start_job(self.batches.jobs.current(identity))

    def pause_job(self):
        identity=self.active_job if self.worker else self.jobs.currentData()
        if not identity:raise ValueError('先選擇批次')
        self.batches.jobs.request_cancel(identity);self.say('已要求完成目前原子項目後暫停。')

    def undo_batch(self):
        identity=self.jobs.currentData()
        if not identity:raise ValueError('先選擇規則批次')
        self.start_job(self.batches.undo(identity,self.actor()))

    def remember(self):
        current=self.store.get('FAMILY_UI_STATE','desktop')
        value=dict(ref=self.ref,draft_id=self.draft['id'] if self.draft else None,
                   case_id=self.case_choice.currentData(),query=self.query_value(),page=self.page,
                   selection=deepcopy(self.selection),active_job=self.active_job)
        with self.store.transaction():
            self.store._write('FAMILY_UI_STATE','desktop',value,current['revision'] if current else 0,'family_workbench_position_saved')

    def restore(self):
        saved=self.store.get('FAMILY_UI_STATE','desktop')
        self.refresh()
        if not saved:return
        self.selection=deepcopy(saved['selection']);self.active_job=saved.get('active_job')
        query=saved.get('query',{});self.query.setText(query.get('text',''))
        for widget,key in ((self.semantic,'semantic'),(self.health,'health'),(self.model_choice,'model_id')):
            self_index=widget.findData(query.get(key,''))
            if self_index>=0:widget.setCurrentIndex(self_index)
        self.page=saved.get('page',0);self.refresh()
        try:
            if saved['ref']:
                self.load_family(saved['ref']);self.reload_drafts(saved['draft_id']);self.load_draft();self.reload_cases(saved['case_id'])
        except (ValueError,KeyError) as error:self.say('已保留舊接續位置，需重新核對版本：'+str(error))

    def request_close(self):
        if self.worker:
            self.close_after_worker=True;self.pause_job();return False
        return True

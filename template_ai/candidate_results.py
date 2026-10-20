"""Present existing candidate results; scores never confer output permission."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gui import MainWindow
import copy,math
from .training_store import digest

GATE_LABELS=dict(ENGINE_REQUIRED_CONDITIONS='語意／固定字級／框位與Logo',PUBLISHED_BASE_APPROVAL='核准模板版本',SOURCE_AND_QUALITY_TRUST='來源與品質依據',EXACT_PUBLISHED_SOURCE_VERSION='發布來源版本一致',ORIGINAL_SOURCE_BYTES='原稿內容核實',SNAPSHOT_FRESHNESS='輸入／資產與規則仍有效',MANUAL_RECHECK_PENDING='人工變更待整張重驗',CURRENT_RESULT_CONTEXT='目前資料與實體尺寸一致',COMPARISON_ONLY='非正式比較副本',TRANSIENT_HUMAN_REVIEW='人工核對事項')


def current_assessment(window,index):
    candidate=window.candidates[index];risk=copy.deepcopy(candidate.risk);reasons=[]
    if candidate.generation!=window.generation:reasons.append('輸入世代已變；須重驗目前資料')
    try:
        people,companies,logos=window.input_data()
        if candidate.risk_context.get('input_digest')!=digest(dict(people=people,companies=companies,logos=logos)):reasons.append('目前輸入與量測快照不一致')
    except (ValueError,TypeError):reasons.append('目前輸入尚無合法可核對結構，保留候選但不放行')
    if (candidate.template.width_mm,candidate.template.height_mm)!=(window.out_w.value(),window.out_h.value()):reasons.append('候選尺寸與目前指定尺寸不同；不能跨尺寸沿用檢查')
    try:
        source=window.library.object_snapshot('TEMPLATE',candidate.template.id)['payload'];pin=dict(id=source['id'],version=source['version'],digest=digest(source))
        if source.get('state')!='published' or candidate.risk_context.get('source_template_pin')!=pin:reasons.append('已核准模板exact版本需重新核對')
    except (ValueError,OSError):reasons.append('核准來源失聯或無法核實')
    if reasons:
        risk['conditions'].append(dict(id='CURRENT_RESULT_CONTEXT',status='UNKNOWN',reason='；'.join(reasons)));risk['formal_allowed']=False
        if risk['state']!='HARD_BLOCKED':risk.update(state='EVIDENCE_REQUIRED',label='目前資料／尺寸／來源待重驗，禁止正式輸出')
    risk['digest']=digest({k:v for k,v in risk.items() if k!='digest'})
    return risk


def selection_pin(window,index):
    from .candidate_edit import review_context_token
    c=window.candidates[index]
    try:source=window.library.object_snapshot('TEMPLATE',c.template.id)['payload']
    except (ValueError,OSError):source=None
    return digest(dict(index=index,root=str(window.library.root),requested_dimensions=[window.out_w.value(),window.out_h.value()],source=source,generation=window.generation,candidate_generation=c.generation,template=c.template.to_dict(),risk=current_assessment(window,index),manual_context=review_context_token(c.risk_context)))


def problem_rows(window,index):
    from .diagnostic_schema import MESSAGES
    c=window.candidates[index];pin=selection_pin(window,index);rows=[]
    for row in c.diagnostics[:200]:
        code=row['code'];route='font' if 'FONT' in code else 'logo' if 'LOGO' in code else 'source' if any(k in code for k in ('SOURCE','BACKGROUND','DEPENDENCY')) else 'input' if code in ('REQUIRED','MISSING_NAME','COMPANY_BINDING','UNBOUND_COMPANY','LOSSLESS') else 'candidate'
        rows.append(dict(candidate_index=index,pin=pin,code=code,slot_ids=list(row.get('slot_ids',[])),owner=row.get('owner',''),kind=row.get('kind','unknown'),reason=MESSAGES.get(code,'必要條件未通過，請核對本機完整問題說明'),route=route))
    for condition in current_assessment(window,index)['conditions']:
        if condition['status']=='PASS' or condition['id']=='ENGINE_REQUIRED_CONDITIONS':continue
        route='font' if 'FONT' in condition['id'] else 'source'
        rows.append(dict(candidate_index=index,pin=pin,code=condition['id'],slot_ids=[],owner='',kind='unknown',reason=condition['reason'],route=route))
    return rows[:200]


def locate_problem(window,row,*,open_input=True):
    from .gui import Box
    from PySide6.QtWidgets import QGraphicsItem
    index=row['candidate_index']
    if not 0<=index<len(window.candidates) or selection_pin(window,index)!=row['pin']:raise ValueError('問題所屬候選／人工版本已更新，請重新選取問題')
    c=window.candidates[index]
    if c.generation!=window.generation:raise ValueError('問題來自過期輸入；先重驗目前候選，不能推測新的欄位歸屬')
    window.candidate_list.setCurrentRow(index);window.choose_candidate(index);slots={s.id:s for s in c.template.slots};located=[]
    for identity in row['slot_ids']:
        if identity not in slots:raise ValueError('物件已不存在，不能推測框位')
        box=Box(copy.deepcopy(slots[identity]),lambda *args:None);box.setFlag(QGraphicsItem.ItemIsMovable,False);box.setFlag(QGraphicsItem.ItemIsSelectable,True);window.output_canvas.scene().addItem(box);box.setSelected(True);window.output_canvas.ensureVisible(box);located.append(identity)
    field_target=None
    if row['slot_ids']:
        slot=slots[row['slot_ids'][0]];people,companies,_=window.input_data();data=companies if slot.owner.startswith('c') else people;owner_index=int(slot.owner[1:])-1;kind='name' if slot.kind in ('company','logo') else slot.kind
        if not 0<=owner_index<len(data):raise ValueError('人物／公司已不存在，無法定位輸入')
        owner=data[owner_index];field_ids=owner.get('field_ids',{}).get(kind,[]);field_id=field_ids[slot.index] if slot.index<len(field_ids) else None
        field_target=dict(owner=slot.owner,kind=kind,index=slot.index,field_id=field_id,entity_id=owner.get('source_entity_id'))
        if open_input and window.active_input_graph is not None:
            if field_id is None:raise ValueError('缺穩定欄位ID，保留框位定位，請由人物卡片核對')
            window.edit_input_graph(focus_field_id=field_id,focus_entity_id=field_target['entity_id'])
        elif open_input:
            table=window.companies if slot.owner.startswith('c') else window.people;keys=['name'] if slot.owner.startswith('c') else ['name','title','phone','email','line','ig','address']
            if kind in keys:
                window.legacy_input_panel.setChecked(True);column=keys.index(kind);table.setCurrentCell(owner_index,column);table.scrollToItem(table.currentItem());table.setFocus()
                def reveal_field():
                    if hasattr(window,'output_page_scroll'):window.output_page_scroll.ensureWidgetVisible(table,0,20)
                    point=table.viewport().mapTo(window.legacy_table_scroll.widget(),table.visualRect(table.model().index(owner_index,column)).center());window.legacy_table_scroll.ensureVisible(point.x(),point.y(),30,18)
                QTimer.singleShot(0,window,reveal_field)
    window.statusBar().showMessage(row['reason']+'；修正後仍需整張重驗');return dict(slot_ids=located,field=field_target,route=row['route'])


def fix_problem(window,row):
    locate_problem(window,row,open_input=row['route']=='input')
    actions=dict(candidate=window.candidate_editor,font=window.font_center,logo=window.logo_center,source=window.source_scan_center)
    if row['route'] in actions:actions[row['route']]()


def gate_comparison(left,right):
    from .candidate_risk import conjunction
    def group(risk):
        result={}
        for c in risk['conditions']:result.setdefault(c['id'],[]).append(c)
        return {key:dict(status=conjunction([r['status'] for r in rows]),reason='；'.join(dict.fromkeys(r['reason'] for r in rows))) for key,rows in result.items()}
    a,b=group(left),group(right);unknown=dict(status='UNKNOWN',reason='此候選缺此項證據')
    return [dict(id=key,left=a.get(key,unknown),right=b.get(key,unknown),different=a.get(key)!=b.get(key)) for key in sorted(a.keys()|b.keys())]


def recommendation(window):
    """Argmax of finite existing rule scores over current qualified results only."""
    states=[current_assessment(window,index) for index in range(len(window.candidates))];eligible=[]
    for index,(candidate,state) in enumerate(zip(window.candidates,states)):
        if state['formal_allowed'] and isinstance(candidate.score,(int,float)) and not isinstance(candidate.score,bool) and math.isfinite(candidate.score):eligible.append(index)
    selected=min(eligible,key=lambda i:(-window.candidates[i].score,window.candidates[i].template.id,i)) if eligible else None
    summary=copy.deepcopy(getattr(window,'last_layout_summary',{}));complete=False
    if summary.get('generation')==window.generation:
        try:
            total,checked,unstarted,failed=(summary[k] for k in ('total','checked','unstarted','failed'))
            complete=all(type(v) is int and v>=0 for v in (total,checked,unstarted,failed)) and total>0 and checked==total and not unstarted and not failed and summary.get('state')=='COMPLETED'
            pins=summary.get('scope_template_pins',{})
            if len(pins)!=total:complete=False
            for identity,expected in pins.items():
                if digest(window.library.object_snapshot('TEMPLATE',identity)['payload'])!=expected:complete=False
        except (KeyError,ValueError,OSError,TypeError):complete=False
    label='目前尚無通過完整必要檢查的推薦候選'
    if selected is not None:
        c=window.candidates[selected];label='目前合格候選中的規則適配推薦：'+c.template.name+'／'+f'{c.template.width_mm:g}×{c.template.height_mm:g} mm'+'；規則分數 '+format(c.score,'.3f')+'（不是模型信心或美感保證）'
    scope='指定有限集合已完成檢查；不代表所有可能設計的全域最佳' if complete else '搜尋／核對範圍仍不完整；僅推薦目前已通過的候選'
    if summary.get('generation')==window.generation:scope+='；已檢查 '+str(summary.get('checked','未知'))+'／'+str(summary.get('total','未知'))+'，未開始 '+str(summary.get('unstarted','未知'))
    return dict(index=selected,label=label,scope_label=scope,scope_complete=complete,global_optimality_proven=False,calibrated_confidence=False,assessments=states)


from PySide6.QtCore import Qt,QTimer
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,
    QPushButton,QSplitter,QWidget,QTableWidget,QTableWidgetItem,QAbstractItemView)


class ResultComparisonDialog(QDialog):
    """Two read-only marked views of existing results; selection copies no geometry."""
    def __init__(self,window):
        super().__init__(window);self.host_window: MainWindow=window;self.pins=[];self.snapshots=[];self.setWindowTitle('比較既有候選與驗證差異（非正式）');layout=QVBoxLayout(self)
        self.status=QLabel('非正式並排檢視；選取只切換目前候選，不跨作品複製框位或解除阻擋。');self.status.setWordWrap(True);layout.addWidget(self.status)
        from .gui import Canvas
        split=QSplitter();self.combos=[];self.canvases=[];self.labels=[];self.view_buttons=[]
        for side in range(2):
            pane=QWidget();box=QVBoxLayout(pane);combo=QComboBox()
            for index,c in enumerate(window.candidates):combo.addItem(c.template.name+f' v{c.template.version}／{c.template.width_mm:g}×{c.template.height_mm:g} mm',index)
            box.addWidget(combo);label=QLabel();label.setWordWrap(True);box.addWidget(label);canvas=Canvas();canvas.readonly=True;canvas.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);canvas.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff);box.addWidget(canvas,1);button=QPushButton('選取此候選查看（保留原有風險）');button.clicked.connect(lambda checked=False,s=side:self.select_side(s));box.addWidget(button);split.addWidget(pane);self.combos.append(combo);self.canvases.append(canvas);self.labels.append(label);self.view_buttons.append(button)
        layout.addWidget(split,2);self.gates=QTableWidget(0,4);self.gates.setHorizontalHeaderLabels(['必要條件','左側','右側','原因／實際差異']);self.gates.setEditTriggers(QAbstractItemView.NoEditTriggers);self.gates.horizontalHeader().setStretchLastSection(True);layout.addWidget(self.gates,1);self.refresh_button=QPushButton('重新載入目前版本比較');self.refresh_button.clicked.connect(self.refresh);layout.addWidget(self.refresh_button);self.resize(1180,820)
        if window.candidates:
            self.combos[0].setCurrentIndex(max(0,window.candidate_list.currentRow()));self.combos[1].setCurrentIndex(1 if len(window.candidates)>1 else 0)
        for combo in self.combos:combo.currentIndexChanged.connect(self.refresh)
        self.watch=QTimer(self);self.watch.setInterval(300);self.watch.timeout.connect(self.check_current);self.watch.start();self.refresh()
    def resizeEvent(self,event):
        super().resizeEvent(event);QTimer.singleShot(0,self.fit_views)
    def fit_views(self):
        for canvas in self.canvases:canvas.fit()
        common=min(c.transform().m11() for c in self.canvases)
        for canvas in self.canvases:canvas.scale(common/canvas.transform().m11(),common/canvas.transform().m11())
    def refresh(self,*args):
        from .render import card_view_image
        try:
            self.indices=[combo.currentData() for combo in self.combos]
            if any(index is None or not 0<=index<len(self.host_window.candidates) for index in self.indices):raise ValueError('沒有可比較的現有候選')
            self.pins=[selection_pin(self.host_window,index) for index in self.indices];risks=[current_assessment(self.host_window,index) for index in self.indices];self.snapshots=[]
            for side,(index,risk) in enumerate(zip(self.indices,risks)):
                c=copy.deepcopy(self.host_window.candidates[index]);c.risk_context['comparison_only']=True;self.snapshots.append(c);details='；'.join(c.issues[:4]) or '；'.join(x['reason'] for x in risk['conditions'] if x['status']!='PASS') or '目前必要條件通過；仍需輸出前重核'
                self.labels[side].setText('非正式比較／'+risk['label']+'；規則分數 '+format(c.score,'.3f')+'，不是信心機率\n'+details)
                try:image=card_view_image(c)
                except (ValueError,OSError):image=None
                self.canvases[side].set_content(c.template.width_mm,c.template.height_mm,image);self.view_buttons[side].setEnabled(True)
            rows=gate_comparison(*risks);self.gates.setRowCount(len(rows))
            for i,row in enumerate(rows):
                for col,text in enumerate((GATE_LABELS.get(row['id'],'其他必要核對條件'),row['left']['status'],row['right']['status'],('【差異】' if row['different'] else '')+'左：'+row['left']['reason']+'；右：'+row['right']['reason'])):
                    item=QTableWidgetItem(text);item.setToolTip(row['id']);self.gates.setItem(i,col,item)
            self.gates.resizeRowsToContents();self.fit_views();self.status.setText('非正式比較：'+str(sum(r['different'] for r in rows))+'項驗證差異；目前候選與人工框位均未更動。')
        except (ValueError,TypeError,KeyError,IndexError) as error:
            self.pins=[];self.status.setText('比較待更新：'+str(error))
            for button in self.view_buttons:button.setEnabled(False)
    def check_current(self):
        try:current=bool(self.pins) and self.pins==[selection_pin(self.host_window,index) for index in self.indices]
        except (ValueError,OSError,TypeError,KeyError,IndexError):current=False
        if not current:
            self.status.setText('輸入／來源／人工版本已變，比較過期；請重新載入。保留原有候選與風險。')
            for button in self.view_buttons:button.setEnabled(False)
        return current
    def select_side(self,side):
        if not self.check_current():return False
        self.host_window.candidate_list.setCurrentRow(self.indices[side]);self.host_window.choose_candidate(self.indices[side]);self.status.setText('已切換查看此候選；未複製座標或解除任何輸出阻擋。');return True

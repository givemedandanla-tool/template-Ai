"""Edit one transient candidate instance through the existing geometry proposal engine."""
import copy,json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QListWidget,QListWidgetItem,QDoubleSpinBox,QPushButton,QPlainTextEdit,QLabel,QMessageBox
from .customers import digest
from .model import Template
from .object_tools import propose
from .layout import generate

def plan_candidate(window,index,ids,dx,dy):
    if not 0<=index<len(window.candidates):raise ValueError('候選不存在')
    c=window.candidates[index]
    if c.generation!=window.generation:raise ValueError('候選版本已過期')
    before=c.template.to_dict();local=copy.deepcopy(before);local['state']='draft'
    request={'operation':'MOVE','ids':list(ids),'dx':dx,'dy':dy,'cross_owner':False};plan=propose(local,'TEMPLATE',request)
    return {'index':index,'generation':window.generation,'before_digest':digest(before),'template_id':c.template.id,'size':[c.template.width_mm,c.template.height_mm],'request':request,'changes':plan['changes'],'warnings':plan['warnings'],'scope':'ONLY_THIS_CANDIDATE_SIZE','unaffected_candidates':len(window.candidates)-1}

def apply_candidate(window,plan,approved=False):
    if not approved:raise ValueError('需明確確認此候選尺寸差異')
    fresh=plan_candidate(window,plan['index'],plan['request']['ids'],plan['request']['dx'],plan['request']['dy'])
    if fresh!=plan:raise ValueError('候選／人工版本已改變，重新預覽')
    c=window.candidates[plan['index']];window.library._template_provenance(c.template);local=c.template.to_dict();local['state']='draft';after=propose(local,'TEMPLATE',plan['request'])['after'];after['state']=c.template.state;t=Template.from_dict(after)
    people,companies,logos=window.input_data();result=generate(t,people,companies,logos,window.generation);result.reasons.append('當次候選獨立毫米修改；其他候選／尺寸未改、發布模板未改；已重新執行數位Gate')
    if c.risk_context.get('source_template_pin'):result.risk_context['source_template_pin']=copy.deepcopy(c.risk_context['source_template_pin'])
    if c.risk_context.get('original_source_proof'):result.risk_context['original_source_proof']=copy.deepcopy(c.risk_context['original_source_proof'])
    result.risk_context['conditions']=copy.deepcopy(c.risk_context.get('conditions',[]))
    result.risk_context['manual_edit_receipt']=copy.deepcopy(plan)
    window.candidates[plan['index']]=result;window.choose_candidate(plan['index']);return result

class CandidateEditDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.index=window.candidate_list.currentRow();self.plan=None;self.setWindowTitle('當次候選／尺寸局部位移（不改模板）');l=QVBoxLayout(self);self.status=QLabel('只處理目前候選尺寸；不跨候選複製座標，不回寫模板。局部復原尚未實作。');l.addWidget(self.status);self.objects=QListWidget();self.objects.setSelectionMode(QListWidget.ExtendedSelection);l.addWidget(self.objects)
        if 0<=self.index<len(window.candidates):
            for s in window.candidates[self.index].template.slots:
                item=QListWidgetItem(s.owner+'／'+s.kind+'／'+s.id);item.setData(Qt.UserRole,s.id);self.objects.addItem(item)
        bar=QHBoxLayout();self.dx=QDoubleSpinBox();self.dy=QDoubleSpinBox()
        for spin in (self.dx,self.dy):spin.setRange(-2000,2000);spin.setDecimals(4);spin.setSuffix(' mm');bar.addWidget(spin)
        b=QPushButton('預覽exact差異');b.clicked.connect(self.preview);bar.addWidget(b);self.apply_button=QPushButton('確認當次局部套用');self.apply_button.clicked.connect(self.apply);bar.addWidget(self.apply_button);l.addLayout(bar);self.details=QPlainTextEdit();self.details.setReadOnly(True);l.addWidget(self.details);self.resize(900,650)
    def preview(self):
        try:self.plan=plan_candidate(self.window,self.index,[i.data(Qt.UserRole) for i in self.objects.selectedItems()],self.dx.value(),self.dy.value());self.details.setPlainText(json.dumps(self.plan,ensure_ascii=False,indent=2));self.status.setText('差異待確認；其他候選／尺寸不受影響')
        except Exception as e:self.plan=None;self.status.setText('未預覽：'+str(e))
    def apply(self):
        try:
            if not self.plan:raise ValueError('先預覽')
            current=plan_candidate(self.window,self.index,[i.data(Qt.UserRole) for i in self.objects.selectedItems()],self.dx.value(),self.dy.value())
            if current!=self.plan:raise ValueError('控制值已變，重新預覽')
            if QMessageBox.question(self,'當次作用範圍',self.details.toPlainText())!=QMessageBox.Yes:return
            apply_candidate(self.window,self.plan,True);self.plan=None;self.status.setText('僅當次候選已改並重驗；未改模板及其他候選')
        except Exception as e:self.status.setText('未套用：'+str(e))

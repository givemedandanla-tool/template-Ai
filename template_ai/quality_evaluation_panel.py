"""Classification/repair/recheck tabs inside the existing training quality center."""
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QLineEdit,QPlainTextEdit,QPushButton,QMessageBox,QInputDialog,QTableWidget,QTableWidgetItem
from .training_store import TrainingStore
from .quality_evaluation import evaluation_plan,save_evaluation,compare_evaluations,create_repair,rollback_gate,recheck_plan,start_recheck

class EvaluationPanel(QWidget):
    def __init__(self,window,parent=None):
        super().__init__(parent);self.window=window;self.store=TrainingStore(window.library);self.plan=None;self.setMinimumWidth(600);l=QVBoxLayout(self);self.status=QLabel('分類紀錄評估；不執行模型推論／不宣稱視覺或獨立品質PASS，需真正HOLDOUT。');self.status.setWordWrap(True);l.addWidget(self.status);self.datasets=QComboBox();l.addWidget(self.datasets);bar=QHBoxLayout();self.versions={}
        for k in ('model','parser','ocr','rules'):e=QLineEdit('UNVERIFIED-'+k+'-1');e.setPlaceholderText(k+' exact version');self.versions[k]=e;bar.addWidget(e)
        l.addLayout(bar);self.predictions=QPlainTextEdit('[]');self.predictions.setPlaceholderText('[{"sample_id":"…","slot_id":"…","kind":"name","owner":"p1"}]；人工／外部預測，不填真值充當模型輸出');self.predictions.setMaximumHeight(140);l.addWidget(self.predictions);bar=QHBoxLayout()
        for title,fn in [('刷新資料集／評估',self.reload),('計算分類分母與錯誤',self.preview),('確認保存當次評估',self.save),('選取已存評估的問題報告',self.report)]:b=QPushButton(title);b.clicked.connect(fn);bar.addWidget(b)
        l.addLayout(bar);self.details=QPlainTextEdit();self.details.setReadOnly(True);l.addWidget(self.details);bar=QHBoxLayout();self.left=QComboBox();self.right=QComboBox();bar.addWidget(self.left);bar.addWidget(self.right)
        for title,fn in [('固定集A/B比較',self.compare),('隔離根因修復待辦',self.repair),('檢查安全回退',self.rollback)]:b=QPushButton(title);b.clicked.connect(fn);bar.addWidget(b)
        l.addLayout(bar);self.reload()
    def reload(self):
        self.datasets.clear()
        for d in self.store.records('DATASET'):
            if d['entries'] and all(e['role']=='HOLDOUT' for e in d['entries']):self.datasets.addItem(d['manifest']['name']+'／'+d['id'],d['id'])
        previous=self.right.currentData();self.left.clear();self.right.clear()
        for e in self.store.records('EVALUATION'):
            title=e['id']+'／'+e['gate'];self.left.addItem(title,e['id']);self.right.addItem(title,e['id'])
        if previous:self.right.setCurrentIndex(self.right.findData(previous))
    def guarded(self,fn):
        try:return fn()
        except Exception as e:self.status.setText('未完成：'+str(e))
    def current_plan(self):return evaluation_plan(self.store,self.datasets.currentData(),{k:e.text() for k,e in self.versions.items()},json.loads(self.predictions.toPlainText()))
    def preview(self):
        def action():self.plan=self.current_plan();self.details.setPlainText(json.dumps(self.plan,ensure_ascii=False,indent=2));self.status.setText(self.plan['gate']+f"／真值{self.plan['gold_count']}／預測{self.plan['predicted_count']}／關鍵歸屬錯誤{self.plan['critical_owner_errors']}；不等於模型品質放行")
        self.guarded(action)
    def save(self):
        def action():
            if not self.plan or self.plan!=self.current_plan():raise ValueError('輸入／版本／資料變更，請重新計算')
            if QMessageBox.question(self,'保存評估紀錄','確認這是人工／外部提供的預測紀錄，非本工具執行模型推論？保存不代表品質PASS。')!=QMessageBox.Yes:return
            e=save_evaluation(self.store,self.plan,'Local Reviewer',True);self.reload();self.right.setCurrentIndex(self.right.findData(e['id']));self.status.setText('已保存exact版本分類紀錄；正式品質仍未驗證')
        self.guarded(action)
    def report(self):
        from .diagnostic_dialog import DiagnosticReportDialog
        selected=self.right.currentData()
        if not selected:self.status.setText('先選取已保存評估紀錄；不把未保存的文案當模型證據');return
        d=DiagnosticReportDialog(self.window,'evaluation',selected,parent=self)
        try:d.exec()
        finally:d.deleteLater()
    def compare(self):
        self.guarded(lambda:self.details.setPlainText(json.dumps(compare_evaluations(self.store,self.left.currentData(),self.right.currentData()),ensure_ascii=False,indent=2)))
    def repair(self):
        def action():
            hypothesis,ok=QInputDialog.getText(self,'根因候選','需依實際錯誤提出假說；不自動修改模型／真值')
            if not ok:return
            version,ok=QInputDialog.getText(self,'隔離候選版本','需與原模型／規則版本區別')
            if not ok:return
            if QMessageBox.question(self,'Holdout獨立性警告','這會記錄使用holdout失敗設計修復，後續必須更換新獨立驗收集。只建隔離待辦，不啟用候選。')!=QMessageBox.Yes:return
            r=create_repair(self.store,self.right.currentData(),hypothesis,version,'Local Reviewer',True);self.details.setPlainText(json.dumps(r,ensure_ascii=False,indent=2));self.status.setText('已保存隔離根因候選；原holdout已標記修復揭露，不能假稱獨立再驗收')
        self.guarded(action)
    def rollback(self):self.guarded(lambda:self.details.setPlainText(json.dumps(rollback_gate(self.store,self.left.currentData(),self.right.currentData()),ensure_ascii=False,indent=2)))

class RecheckPanel(QWidget):
    def __init__(self,window,parent=None):
        super().__init__(parent);self.window=window;self.store=TrainingStore(window.library);self.plan=None;l=QVBoxLayout(self);self.status=QLabel('跨歷史exact規則依賴重審；僅明確依賴，不宣稱模型／Logo／客戶全面掃描。');self.status.setWordWrap(True);l.addWidget(self.status);self.rules=QComboBox();l.addWidget(self.rules);self.reason=QLineEdit();self.reason.setPlaceholderText('重大錯誤證據／原因（必填）');l.addWidget(self.reason);bar=QHBoxLayout()
        for title,fn in [('刷新既有規則',self.reload),('預覽歷史依賴與範圍',self.preview),('確認選中樣本暫停信任',self.start)]:b=QPushButton(title);b.clicked.connect(fn);bar.addWidget(b)
        l.addLayout(bar);self.table=QTableWidget(0,3);self.table.setHorizontalHeaderLabels(['勾選（預設不選）','exact樣本／作品','目前狀態／影響']);l.addWidget(self.table);self.details=QPlainTextEdit();self.details.setReadOnly(True);l.addWidget(self.details);self.reload()
    def reload(self):
        self.rules.clear()
        for r in self.store.records('RULE'):self.rules.addItem(r['id']+'／r'+str(r['revision']),r['id'])
    def preview(self):
        try:
            self.plan=recheck_plan(self.store,self.rules.currentData());self.table.setRowCount(len(self.plan['rows']))
            for i,r in enumerate(self.plan['rows']):
                item=QTableWidgetItem();item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Unchecked);self.table.setItem(i,0,item)
                for j,v in ((1,r['sample_id']+'／'+r['work_id']),(2,r['sample_state']+'／'+str(r['impact']))):item=QTableWidgetItem(v);item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable);self.table.setItem(i,j,item)
            self.details.setPlainText(json.dumps(self.plan,ensure_ascii=False,indent=2));self.status.setText(f"exact依賴總數{self.plan['direct_total']}／已檢索{self.plan['scanned']}；其餘依賴族未知")
        except Exception as e:self.plan=None;self.status.setText('未完成：'+str(e))
    def start(self):
        try:
            if not self.plan or self.rules.currentData()!=self.plan['rule_id']:raise ValueError('先核對當前規則預覽')
            selected=[r['sample_id'] for i,r in enumerate(self.plan['rows']) if self.table.item(i,0).checkState()==Qt.Checked]
            if QMessageBox.question(self,'跨歷史重審隔離',f'規則{self.plan["rule_id"]}／{len(selected)}筆樣本暫停信任；歷史核准保留，未完成重審且不聲稱模型已去污染。原因：'+self.reason.text())!=QMessageBox.Yes:return
            result=start_recheck(self.store,self.plan,selected,self.reason.text(),'Local Reviewer',True);self.details.setPlainText(json.dumps(result,ensure_ascii=False,indent=2));self.status.setText('已原子保存REVIEW_REQUIRED；相關新學習／來源模板使用會因樣本隔離而阻擋，原模板未改')
        except Exception as e:self.status.setText('未開始：'+str(e))

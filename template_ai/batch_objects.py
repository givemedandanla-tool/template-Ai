"""Bounded text-alignment batch adapter: reuse proposals, CAS, history and per-item commits."""
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QPlainTextEdit,QMessageBox
from .customers import digest
from .object_tools import propose
from .model import new_id

def batch_plan(library,targets,align='left'):
    if not 1<=len(targets)<=50 or len({t['id'] for t in targets})!=len(targets):raise ValueError('明確選取1至50個不同作品')
    rows=[]
    for target in targets:
        try:
            snapshot=library.object_snapshot('ARTWORK',target['id']);request={'operation':'PATCH','ids':target['slot_ids'],'patch':{'align':align},'cross_owner':False};plan=propose(snapshot['payload'],'ARTWORK',request)
            if plan['warnings'] and any('重疊' in w or '邊界' in w for w in plan['warnings']):raise ValueError('作品幾何待人工處理')
            rows.append({'id':target['id'],'state':'READY','snapshot':snapshot,'request':request,'changes':plan['changes'],'warnings':plan['warnings']})
        except Exception as e:rows.append({'id':target['id'],'state':'BLOCKED','reason':str(e)})
    return {'operation_id':new_id(),'rows':rows,'scope':'MANUAL_TEXT_ALIGNMENT_ONLY','count':len(targets)}

def apply_batch(library,plan,approved=False,cancel=lambda:False):
    if not approved:raise ValueError('需明確確認範圍與逐項差異')
    results=[]
    for row in plan['rows']:
        if cancel():results.append({'id':row['id'],'state':'CANCELLED'});continue
        if row['state']!='READY':results.append({'id':row['id'],'state':'BLOCKED','reason':row['reason']});continue
        try:
            request=row['request']
            if request.get('operation')!='PATCH' or set(request.get('patch',{}))!={'align'} or request.get('cross_owner') is not False:raise ValueError('批次只允許已核對的文字對齊，不可改人物／公司／字級／Logo')
            recalculated=propose(row['snapshot']['payload'],'ARTWORK',request)
            if recalculated['changes']!=row['changes']:raise ValueError('預覽範圍已被改變')
            operation='batch:'+digest([plan['operation_id'],row['id']]);r=library.apply_object_edit(row['snapshot'],request,True,operation)
            results.append({'id':row['id'],'state':'ALREADY_APPLIED' if r.get('reused') else 'APPLIED_PENDING_FULL_VALIDATION','history_id':r['id']})
        except Exception as e:results.append({'id':row['id'],'state':'FAILED_OR_STALE','reason':str(e)})
    return results

class BatchObjectDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.plan=None;self.setWindowTitle('既有作品／低風險文字對齊批次');self.resize(1000,700);l=QVBoxLayout(self);self.status=QLabel('最多列出200作品；每批最多50，需明列文字ID；不自動核准／學習／發布，重試冪等，復原走既有歷史。');self.status.setWordWrap(True);l.addWidget(self.status)
        works=window.library.db.execute('SELECT id,name,payload FROM artworks ORDER BY id LIMIT 201').fetchall();self.rows=[]
        for wid,name,payload in works[:200]:
            slots=json.loads(payload)['slots'];ids=[s['id'] for s in slots if s['kind']!='logo' and not s.get('locked')]
            self.rows.append({'id':wid,'name':name,'slot_ids':ids})
        self.table=QTableWidget(len(self.rows),3);self.table.setHorizontalHeaderLabels(['選取','作品exactID','明列可編文字ID']);l.addWidget(self.table)
        for i,r in enumerate(self.rows):
            item=QTableWidgetItem();item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Unchecked);self.table.setItem(i,0,item)
            for j,v in ((1,r['name']+'／'+r['id']),(2,','.join(r['slot_ids']))):item=QTableWidgetItem(v);item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable);self.table.setItem(i,j,item)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);l.addWidget(self.details);bar=QHBoxLayout()
        for title,fn in [('預檢／逐項靠左差異',self.preview),('確認選中集合套用／安全重試',self.apply)]:b=QPushButton(title);b.clicked.connect(fn);bar.addWidget(b)
        l.addLayout(bar)
    def preview(self):
        try:
            from .training_navigation import require_clean_navigation
            require_clean_navigation(self.window);self.plan=batch_plan(self.window.library,[r for i,r in enumerate(self.rows) if self.table.item(i,0).checkState()==Qt.Checked]);self.selected_ids=[r['id'] for i,r in enumerate(self.rows) if self.table.item(i,0).checkState()==Qt.Checked];self.details.setPlainText(json.dumps(self.plan,ensure_ascii=False,indent=2));self.status.setText('已預檢exact集合；READY可核對，不等於整卡PASS')
        except Exception as e:self.plan=None;self.status.setText('未預檢：'+str(e))
    def apply(self):
        try:
            if not self.plan or self.selected_ids!=[r['id'] for i,r in enumerate(self.rows) if self.table.item(i,0).checkState()==Qt.Checked]:raise ValueError('勾選範圍改變或沒有預覽，請重新預檢')
            from .training_navigation import require_clean_navigation
            require_clean_navigation(self.window)
            if QMessageBox.question(self,'批次差異確認',self.details.toPlainText())!=QMessageBox.Yes:return
            results=apply_batch(self.window.library,self.plan,True);self.details.setPlainText(json.dumps(results,ensure_ascii=False,indent=2));self.status.setText('逐項結果（非整批通過）：'+str({state:sum(r['state']==state for r in results) for state in {r['state'] for r in results}}));self.window.invalidate()
        except Exception as e:self.status.setText('未套用：'+str(e))

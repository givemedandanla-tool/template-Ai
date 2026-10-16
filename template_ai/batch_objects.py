"""Bounded text-alignment batch adapter: reuse proposals, CAS, history and per-item commits."""
import json,copy,sqlite3
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QPlainTextEdit,QMessageBox,QComboBox
from .customers import digest
from .object_tools import propose,select_slots,NoObjectChange
from .model import new_id

def batch_plan(library,targets,align='left'):
    if not isinstance(targets,list) or not 1<=len(targets)<=50 or len({(t.get('kind','ARTWORK'),t['id']) for t in targets})!=len(targets):raise ValueError('明確選取1至50個不同作品／草稿；同一實體先合併明確選取範圍')
    rows=[]
    for target in targets:
        row=dict(id=target['id'],kind=target.get('kind','ARTWORK'),state='BLOCKED',risk='HIGH',formal_eligible=False)
        row['target_key']=row['kind']+':'+row['id']
        try:
            snapshot=library.object_snapshot(row['kind'],row['id']);ids=target['slot_ids'];selected=select_slots(snapshot['payload'],ids)
            if row['kind']=='ARTWORK' and snapshot['payload'].get('visual_confirmed') is not True:raise ValueError('來源標記尚待人工確認，不自動批次核准')
            if any(s.locked or s.kind=='logo' or not s.owner or s.owner.upper()=='UNKNOWN' for s in selected) or len({s.owner for s in selected})!=1:raise ValueError('鎖定／Logo／未知或跨人物公司歸屬須走既有逐筆人工核對，不批次自動核准')
            request=copy.deepcopy(target.get('request') or dict(operation='PATCH',ids=ids,patch={'align':align},cross_owner=False))
            request.setdefault('ids',list(ids));request.setdefault('cross_owner',False)
            if sorted(request['ids'])!=sorted(ids):raise ValueError('請求物件與明確選取範圍不同')
            validate_request(request)
            plan=propose(snapshot['payload'],row['kind'],request)
            if plan['warnings'] and any('重疊' in w or '邊界' in w for w in plan['warnings']):raise ValueError('作品幾何待人工處理')
            row.update(state='READY',risk='LOW' if request['operation']=='PATCH' and set(request['patch'])<={'align','color'} else 'CONFIRM',snapshot=snapshot,request=request,changes=plan['changes'],warnings=plan['warnings'])
            if not plan['changes']:row.update(state='UNCHANGED',risk='NONE',reason='目前已是相同值；未建立重複寫入')
        except NoObjectChange as e:row.update(state='UNCHANGED',risk='NONE',snapshot=snapshot,request=request,reason=str(e))
        except (ValueError,KeyError,TypeError,OSError,sqlite3.Error) as e:row['reason']=str(e)
        rows.append(row)
    plan=dict(operation_id=new_id(),rows=rows,scope='EXACT_SELECTED_DRAFT_METADATA_ONLY',count=len(targets),root_digest=digest(str(library.root.resolve())),schema=2)
    plan['seal']=digest(plan);return plan


def validate_request(request):
    if request.get('operation') not in ('PATCH','MOVE','ALIGN','DISTRIBUTE') or request.get('cross_owner') is not False:raise ValueError('批次不能解鎖、刪除或跨人物公司；請逐筆人工核對')
    if request['operation']=='PATCH' and (not request.get('patch') or set(request['patch'])-{'align','color','x','y','w','h'}):raise ValueError('批次不可修改人物／公司／字級／字型／文字下限或Logo')


def check_batch(library,plan,approved):
    if approved is not True:raise ValueError('需明確確認範圍與逐項差異')
    if plan.get('root_digest')!=digest(str(library.root.resolve())) or plan.get('seal')!=digest({k:v for k,v in plan.items() if k!='seal'}):raise ValueError('批次來源／精確範圍或預覽已變更，重新預檢')


def operation_id(plan,row):return 'batch:'+digest([plan['operation_id'],row['kind'],row['id']])


def reconcile_item(library,plan,row):
    raw=library.db.execute('SELECT payload FROM object_edits WHERE id=?',(operation_id(plan,row),)).fetchone()
    if not raw:return None
    record=json.loads(raw[0]);snapshot=row['snapshot']
    if record['kind']!=row['kind'] or record['entity_id']!=row['id'] or record['plan']['request']!=row['request'] or record['before_revision']!=snapshot['revision'] or record['before']!=snapshot['payload']:raise ValueError('歷史操作ID與原核對範圍不同')
    if record['phase']!='APPLIED':raise ValueError('此操作已復原；不能將安全重試當成重新套用')
    current=library.object_snapshot(row['kind'],row['id']);unchanged=current['revision']==record['expected_revision'] and current['payload']==record['after']
    return dict(id=row['id'],kind=row['kind'],target_key=row['target_key'],state='ALREADY_APPLIED',outcome='APPLIED_PENDING_FULL_VALIDATION' if unchanged else 'APPLIED_BUT_CURRENT_CHANGED',history_id=record['id'],attempted=False,formal_eligible=False,reason='核實原操作已保存；目前資格仍須整作品重驗' if unchanged else '原操作確有歷史，但目前已有新編輯；保留新版，未重複套用')

def apply_batch(library,plan,approved=False,cancel=lambda:False,progress=lambda row:None):
    check_batch(library,plan,approved)
    results=[]
    for row in plan['rows']:
        result=dict(id=row['id'],kind=row['kind'],target_key=row['target_key'],attempted=False,formal_eligible=False)
        try:
            previous=reconcile_item(library,plan,row) if row['state']=='READY' else None
            if previous:result=previous
            elif cancel():result.update(state='CANCELLED',outcome='CANCELLED',reason='尚未執行；既有完成項不因此撤銷')
            elif row['state']=='UNCHANGED':
                current=library.object_snapshot(row['kind'],row['id']);fresh=current==row['snapshot'];result.update(state='BLOCKED',outcome='SKIPPED_PRECONDITION' if fresh else 'STALE',reason=row['reason'] if fresh else '預檢後來源已變更；未猜測重試')
            elif row['state']!='READY':result.update(state='BLOCKED',outcome='SKIPPED_PRECONDITION' if row['state']=='UNCHANGED' else 'NEEDS_MANUAL_REVIEW',reason=row['reason'])
            else:
                progress(dict(result,outcome='PROCESSING'))
                request=row['request'];validate_request(request)
                recalculated=propose(row['snapshot']['payload'],row['kind'],request)
                if recalculated['changes']!=row['changes']:raise ValueError('預覽範圍已被改變')
                result['attempted']=True;r=library.apply_object_edit(row['snapshot'],request,True,operation_id(plan,row))
                result.update(state='APPLIED_PENDING_FULL_VALIDATION',outcome='APPLIED_PENDING_FULL_VALIDATION',history_id=r['id'],reason='只保存選取草稿／標記差異；尚未核實當前整作品印前條件')
        except Exception as e:
            try:
                reconciled=reconcile_item(library,plan,row) if row['state']=='READY' else None
                if reconciled:result=reconciled
                else:
                    current=library.object_snapshot(row['kind'],row['id']);stale=row.get('snapshot') and (current['revision']!=row['snapshot']['revision'] or current['payload']!=row['snapshot']['payload'])
                    result.update(state='FAILED_OR_STALE',outcome='STALE' if stale else 'FAILED',reason=str(e))
            except (ValueError,KeyError,TypeError,OSError,sqlite3.Error):result.update(state='FAILED_OR_STALE',outcome='STALE' if isinstance(e,ValueError) else 'RESULT_UNVERIFIED',reason=str(e)+'；結果未安全核實，不盲目重試')
        results.append(result);progress(copy.deepcopy(result))
    return results


def undo_batch(library,plan,results,approved=False,selected=None):
    check_batch(library,plan,approved);known={r['target_key']:r for r in plan['rows']};requested={r['target_key'] for r in results if r.get('history_id')}
    if selected is not None:
        requested=set()
        for value in selected:
            choices=[key for key,row in known.items() if value in (key,row['id'])]
            if len(choices)!=1:raise ValueError('回復實體ID不明確；請使用完整類型與ID')
            requested.add(choices[0])
    if not requested.issubset(known):raise ValueError('回復範圍含未核對目標')
    receipts={r['target_key']:r for r in results};out=[]
    for identity in reversed([r['target_key'] for r in plan['rows'] if r['target_key'] in requested]):
        row=known[identity];result=dict(id=row['id'],kind=row['kind'],target_key=identity,formal_eligible=False)
        try:
            if receipts.get(identity,{}).get('history_id')!=operation_id(plan,row):raise ValueError('沒有此目標原操作的已核實歷史')
            current=reconcile_item(library,plan,row)
            if current is None or current['outcome']=='APPLIED_BUT_CURRENT_CHANGED':raise ValueError('此目標後已有新編輯／版本；未覆寫，請人工核對')
            record=library.object_history_action(current['history_id'],'UNDO',True);result.update(outcome='UNDONE_PENDING_FULL_VALIDATION',history_id=record['id'])
        except Exception as error:result.update(outcome='UNDO_CONFLICT',reason=str(error))
        out.append(result)
    return out


def batch_summary(results):
    from collections import Counter
    counts=dict(Counter(r.get('outcome',r.get('state')) for r in results));applied=counts.get('APPLIED_PENDING_FULL_VALIDATION',0);changed=counts.get('APPLIED_BUT_CURRENT_CHANGED',0)
    return dict(checked=len(results),attempted=sum(bool(r.get('attempted')) for r in results),applied_pending_validation=applied,current_changed=changed,failed=counts.get('FAILED',0)+counts.get('RESULT_UNVERIFIED',0),stale=counts.get('STALE',0),manual=counts.get('NEEDS_MANUAL_REVIEW',0),cancelled=counts.get('CANCELLED',0),outcomes=counts,status='APPLIED_PENDING_REVALIDATION' if applied==len(results) and results else 'PARTIAL_OR_BLOCKED',formal_eligible=False)

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
        self.details=QPlainTextEdit();self.details.setReadOnly(True);l.addWidget(self.details);bar=QHBoxLayout();self.align=QComboBox();self.align.addItems(['center','left','right']);bar.addWidget(self.align)
        for title,fn in [('預檢／逐項文字對齊差異',self.preview),('確認選中集合套用／安全重試',self.apply)]:b=QPushButton(title);b.clicked.connect(fn);bar.addWidget(b)
        l.addLayout(bar)
    def preview(self):
        try:
            from .training_navigation import require_clean_navigation
            require_clean_navigation(self.window);self.plan=batch_plan(self.window.library,[r for i,r in enumerate(self.rows) if self.table.item(i,0).checkState()==Qt.Checked],self.align.currentText());self.preview_align=self.align.currentText();self.selected_ids=[r['id'] for i,r in enumerate(self.rows) if self.table.item(i,0).checkState()==Qt.Checked];self.details.setPlainText(json.dumps(self.plan,ensure_ascii=False,indent=2));self.status.setText('已預檢exact集合；READY可核對，不等於整卡PASS')
        except Exception as e:self.plan=None;self.status.setText('未預檢：'+str(e))
    def apply(self):
        try:
            if not self.plan or self.preview_align!=self.align.currentText() or self.selected_ids!=[r['id'] for i,r in enumerate(self.rows) if self.table.item(i,0).checkState()==Qt.Checked]:raise ValueError('勾選範圍改變或沒有預覽，請重新預檢')
            from .training_navigation import require_clean_navigation
            require_clean_navigation(self.window)
            if QMessageBox.question(self,'批次差異確認',self.details.toPlainText())!=QMessageBox.Yes:return
            results=apply_batch(self.window.library,self.plan,True);self.details.setPlainText(json.dumps(results,ensure_ascii=False,indent=2));self.status.setText('逐項結果（非整批通過）：'+str({state:sum(r['state']==state for r in results) for state in {r['state'] for r in results}}));self.window.invalidate()
        except Exception as e:self.status.setText('未套用：'+str(e))

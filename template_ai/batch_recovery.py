"""Safe-stopped recipes in the original short-lived encrypted recovery service."""
import copy
from .customers import digest
from .layout_recovery import LayoutRecovery,encode_candidate,decode_candidate
from .batch_objects import check_batch,apply_batch,candidate_target_seal


def store(root):return LayoutRecovery(root,kind='BATCH_CORRECTION')


def encode_checked(checked):
    result=copy.deepcopy(checked);result['candidate']=encode_candidate(checked['candidate']);result['target']['envelope']['before']=encode_candidate(checked['target']['envelope']['before']);return result


def decode_checked(value):
    result=copy.deepcopy(value);result['candidate']=decode_candidate(value['candidate']);result['target']['envelope']['before']=decode_candidate(value['target']['envelope']['before']);target=result['target']
    if target['seal']!=candidate_target_seal(target) or result['seal']!=digest(dict(target=target['seal'],candidate=encode_candidate(result['candidate']),outcome=result['outcome'])):raise ValueError('已保存候選的確切範圍／結果封印不符')
    return result


def payload(dialog):
    d=dialog;d.valid_context()
    if d.running or d.window.busy or not d.plan:raise ValueError('先安全停止並保留有效預檢，未保存進行中工作')
    if d.parameters()!=d.preview_parameters or d.selection_pin()!=d.selected_ids:raise ValueError('範圍／參數已變更，請重新預檢後保存')
    if d.results and all(r.get('outcome') in ('APPLIED_VALIDATED','ALREADY_APPLIED','APPLIED_PENDING_FULL_VALIDATION') for r in d.results):raise ValueError('本批已完成套用，不保留正常完成的私人暫存')
    candidate=d.scope.currentData()=='CANDIDATE'
    if candidate:d.candidate_batch.require_preview()
    else:check_batch(d.library,d.plan,True)
    return dict(kind='BATCH_CORRECTION',state='PAUSED_SAFE',scope=d.scope.currentData(),root_digest=digest(str(d.library.root.resolve())),plan=copy.deepcopy(d.plan),results=copy.deepcopy(d.results),parameters=d.parameters(),selected=d.selection_pin(),preflight_text=d.preflight_text,checked={k:encode_checked(v) for k,v in d.candidate_batch.checked.items()} if candidate else {})


def inspect(library,value):
    if value.get('kind')!='BATCH_CORRECTION' or value.get('state')!='PAUSED_SAFE' or value.get('root_digest')!=digest(str(library.root.resolve())):raise ValueError('批次用途／安全停止狀態／Library不符')
    plan=value['plan']
    if not 1<=len(plan['rows'])<=50:raise ValueError('恢復範圍需為1至50個確切交易')
    if value['scope']!='CANDIDATE':
        check_batch(library,plan,True)
        return apply_batch(library,plan,True,cancel=lambda:True)
    checked={key:decode_checked(item) for key,item in value['checked'].items()}
    if set(checked)-{r['target_key'] for r in plan['rows']}:raise ValueError('已保存候選超出明確交易範圍')
    return [dict(kind='CANDIDATE',id=row['id'],target_key=row['target_key'],outcome='RESULT_UNVERIFIED',formal_eligible=False,reason='已解密已保存預檢；原候選記憶體操作尚待目前視窗逐筆核對，不自動重播位移') for row in plan['rows']]


def reconnect(dialog,value,rows):
    d=dialog
    if value['scope']!='CANDIDATE':return rows,{}
    from .candidate_sync import candidate_pin
    checked={key:decode_checked(item) for key,item in value['checked'].items()};out=copy.deepcopy(rows)
    for row in out:
        key=row['target_key'];item=checked.get(key);pair=d.candidate_batch.adapters.get(key)
        if not item or not pair:continue
        adapter,index=pair;target=item['target'];current=adapter.candidates[index]
        if candidate_pin(current)==candidate_pin(item['candidate']):
            from .batch_objects import install_candidate_target
            try:row.update(install_candidate_target(adapter,item,True))
            except ValueError as error:row['reason']=str(error)
        elif candidate_pin(current)==target['before_pin']:
            row.update(outcome='CANCELLED',reason='原前置版面仍存在；未證明套用，明確核對後才允許原預檢安全重試')
        else:row['reason']='目前已有其他人工版面；保留目前工作，原結果未核實'
    # Cache can reconnect only to its original runtime origin. A restarted view
    # receives an inspection report and must not blindly replay old relative moves.
    return out,{key:item for key,item in checked.items() if key in d.candidate_batch.adapters}


class BatchRecoveryController:
    def __init__(self,dialog):self.d=dialog
    def save(self):
        from PySide6.QtWidgets import QInputDialog,QLineEdit
        d=self.d
        try:
            value=payload(d);password,ok=QInputDialog.getText(d,'保存安全停止的批次','12字以上密碼，24小時有效；不保存密碼。未落盤項不承諾可恢復。',QLineEdit.Password)
            if not ok:return
            d.running=True
            def done(receipt):d.running=False;d.batch_recovery_receipt=receipt;d.status.setText('已逐位元讀回加密停止快照；未保存的新進度不保證可恢復。')
            def failed(error):d.running=False;d.status.setText('未保存：'+str(error))
            d.window.run_job('保存短期加密批次快照',lambda:store(d.library.root).save(value,password),done,on_error=failed,resource_kind='RESTORE')
        except Exception as error:d.running=False;d.status.setText('未保存：'+str(error))
    def restore(self):
        from PySide6.QtWidgets import QInputDialog,QLineEdit,QMessageBox
        d=self.d
        try:
            d.valid_context()
            if d.running or d.window.busy:raise ValueError('原工作尚未安全停止')
            password,ok=QInputDialog.getText(d,'核對已保存批次','輸入原密碼；先讀回操作紀錄，不自動套用。',QLineEdit.Password)
            if not ok:return
            root=str(d.library.root);generation=d.window.generation;pin=d.selection_pin();d.running=True
            def work():
                from .storage import Library
                value=store(root).load(password);library=Library(root)
                try:return value,inspect(library,value)
                finally:library.close()
            def done(result):
                d.running=False;value,rows=result
                if d.window.generation!=generation or d.selection_pin()!=pin or str(d.window.library.root)!=root:d.status.setText('解密期間目前工作已變更，未載入或套用');return
                if QMessageBox.question(d,'核對恢復交易','只載入已保存的明確範圍與讀回結果。來源歷史可核實；候選若原記憶體／視窗已消失，保留未核實，不自動重播位移。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
                if d.window.generation!=generation or d.selection_pin()!=pin or str(d.window.library.root)!=root:d.status.setText('確認期間工作已變更，未載入');return
                d.scope.setCurrentIndex(d.scope.findData(value['scope']));d.reload();d.plan=copy.deepcopy(value['plan']);d.selected_ids=list(value['selected']);d.preview_parameters=list(value['parameters']);d.preflight_text=value['preflight_text']
                controls=[d.action,d.align,d.dx,d.dy,d.width,d.height,d.ratio]
                for control,parameter in zip(controls,d.preview_parameters):
                    if hasattr(control,'setValue'):control.setValue(parameter)
                    elif control is d.align:control.setCurrentIndex(control.findData(parameter))
                    else:control.setCurrentIndex(parameter)
                from PySide6.QtCore import Qt
                for i in range(d.table.rowCount()):
                    item=d.table.item(i,0);item.setCheckState(Qt.Checked if item.data(Qt.UserRole) in d.selected_ids else Qt.Unchecked)
                rows,checked=reconnect(d,value,rows)
                if value['scope']=='CANDIDATE':d.candidate_batch.checked=checked;d.candidate_batch.preview_seal=d.candidate_batch.seal()
                d.finished(rows,invalidate=False);d.status.setText('已載入保存範圍並讀回逐項結果；未自動續算、套用或正式輸出。\n'+d.status.text())
            def failed(error):d.running=False;d.status.setText('未恢復：'+str(error))
            d.window.run_job('解密核實批次恢復',work,done,on_error=failed,resource_kind='RESTORE')
        except Exception as error:d.running=False;d.status.setText('未恢復：'+str(error))
    def clear(self):
        from PySide6.QtWidgets import QMessageBox
        d=self.d
        if d.running or d.window.busy:return
        if QMessageBox.question(d,'清除批次恢復','只刪除本機批次恢復暫存，不是磁碟安全抹除。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        try:store(d.library.root).clear();d.status.setText('已清除批次短期暫存；未修改作品或原操作歷史。')
        except OSError as error:d.status.setText('清除未完成：'+str(error))

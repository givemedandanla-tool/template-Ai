"""Candidate scopes for the original batch dialog; reuse its one worker and editor."""
import copy
from dataclasses import asdict
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox
from .customers import digest
from .model import new_id
from .batch_objects import (candidate_origin_key,prepare_candidate_target,calculate_candidate_target,
    install_candidate_target,candidate_target_current,prepare_candidate_undo,fit_width_request)


class CandidateBatchController:
    def __init__(self,dialog,origin):
        self.d=dialog;self.origin=origin;self.adapters={};self.checked={};self.items=[];self.position=0

    def rows(self):
        from .multi_size_edit import SizeEditAdapter
        d=self.d;rows=[];self.adapters={};self.checked={};pairs=[]
        if self.origin is d.host_window:pairs=[(d.host_window,i) for i in range(len(d.host_window.candidates))]
        elif self.origin.is_current():
            for entry in self.origin.service.entries:
                for index in range(len(entry['candidates'])):
                    adapter=SizeEditAdapter(self.origin,entry,index);adapter.setParent(d);pairs.append((adapter,index))
        else:raise ValueError('多尺寸來源已過期，請先同步重驗')
        for adapter,index in pairs:
            candidate=adapter.candidates[index];key=candidate_origin_key(adapter,index);self.adapters[key]=(adapter,index)
            for slot in candidate.template.slots:
                if len(rows)>=200:break
                snapshot=candidate.risk_context.get('input_snapshot',{});owners=snapshot.get('companies' if slot.owner.startswith('c') else 'people',[])
                try:owner=owners[int(slot.owner[1:])-1] if int(slot.owner[1:])>0 else {}
                except (ValueError,IndexError):owner={}
                context='人物／公司 '+str(owner.get('name','歸屬待核實'))+'；來源實體 '+str(owner.get('source_entity_id','未知'))+'；版型版本ID '+candidate.template.id+'/v'+str(candidate.template.version)
                if slot.kind=='logo':
                    asset=next((item.logo for item in candidate.items if item.slot.id==slot.id),None) or {}
                    context+='；本尺寸Logo資產 '+str(asset.get('id','缺少合法資產'))+'；來源 '+str(asset.get('source_id',asset.get('path','待核實')))
                context+='；目前問題 '+'、'.join(str(item.get('code',''))+' '+str(item.get('severity','')) for item in candidate.diagnostics)
                rows.append(dict(key=key+':'+slot.id,scope_key=key,id=candidate.template.id,kind='CANDIDATE',slot_ids=[slot.id],name=candidate.template.name,slot=asdict(slot),context=context,size=[candidate.template.width_mm,candidate.template.height_mm],state='待預檢',risk='待預檢'))
        return rows,len(rows)>=200

    def seal(self):
        d=self.d
        return digest(dict(root=str(d.library.root),selected=d.selected_ids,parameters=d.preview_parameters,
            rows=d.plan['rows'],checked={key:value['seal'] for key,value in self.checked.items()}))

    def set_running(self,value):
        d=self.d;d.running=value
        for control in [d.scope,d.preview_button,d.apply_button,d.undo_button]:control.setEnabled(not value)

    def request(self,candidate,ids):
        d=self.d
        if d.action.currentIndex()==3:return fit_width_request(candidate,ids,d.ratio.value()/100)
        if d.action.currentIndex()==2:raise ValueError('跨候選框寬高請使用各框原字寬的X比例，或既有逐筆工具')
        return d.request(ids)

    def preview(self):
        d=self.d
        if d.running or d.host_window.busy:d.status.setText('原背景工作進行中，保留此批固定範圍，稍後再預檢');return
        try:
            d.valid_context()
            if d.running or d.host_window.busy:raise ValueError('原背景工作進行中，稍後再預檢')
            from .training_navigation import require_clean_navigation
            require_clean_navigation(d.host_window)
            groups={}
            for row in d.selected_rows():groups.setdefault(row['scope_key'],[]).extend(row['slot_ids'])
            if not 1<=len(groups)<=50:raise ValueError('請明確勾選1至50個候選交易')
            d.selected_ids=d.selection_pin();d.preview_parameters=d.parameters();d.results=[];self.checked={};self.items=[]
            d.plan=dict(operation_id=new_id(),rows=[],scope='EXACT_CANDIDATE_SIZE');d.execution_plan=d.plan
            for key,ids in groups.items():
                adapter,index=self.adapters[key];candidate=adapter.candidates[index]
                row=dict(kind='CANDIDATE',id=candidate.template.id,target_key=key,selected_slot_ids=ids,state='BLOCKED',risk='HIGH',changes=[])
                try:
                    target=prepare_candidate_target(adapter,index,self.request(candidate,ids),key=key)
                    row.update(state='PENDING',risk='CONFIRM',changes=copy.deepcopy(target['envelope']['plan']['changes']))
                    self.items.append(target)
                except Exception as error:row['reason']=str(error)
                d.plan['rows'].append(row)
            self.position=0;self.mode='PREVIEW';d.cancel_event.clear();self.set_running(True);self.next_preview()
        except Exception as error:d.plan=None;d.status.setText('未預檢：'+str(error))

    def next_preview(self):
        d=self.d
        if self.position>=len(self.items):self.finish_preview();return
        target=self.items[self.position];self.position+=1;key=target['target_key'];row=next(r for r in d.plan['rows'] if r['target_key']==key)
        if d.cancel_event.is_set():row.update(state='CANCELLED',reason='已停止尚未開始的預檢');QTimer.singleShot(0,self.next_preview);return
        root=str(d.library.root);d.status.setText(f'候選逐張整卡預檢 {self.position}/{len(self.items)}；尚未套用。')
        def work():
            from .storage import Library
            library=Library(root)
            try:return calculate_candidate_target(target,library)
            finally:library.close()
        def done(checked):
            adapter,_=self.adapters[key]
            if not candidate_target_current(adapter,target):row.update(state='BLOCKED',reason='預檢期間已有新資料／人工版面，舊結果未採用')
            else:
                self.checked[key]=checked;row.update(state='READY' if checked['outcome']=='READY' else 'BLOCKED',reason='整卡數位Gate合格，仍需明確核對套用' if checked['outcome']=='READY' else '；'.join(checked['candidate'].issues))
            QTimer.singleShot(0,self.next_preview)
        def failed(message):row.update(state='BLOCKED',reason=str(message));QTimer.singleShot(0,self.next_preview)
        try:d.host_window.run_job('批次候選預檢',work,done,on_error=failed,cancel=d.cancel_event)
        except Exception as error:failed(error)

    def finish_preview(self):
        d=self.d;self.set_running(False);lines=[]
        for row in d.plan['rows']:
            d.paint(row['target_key'],'可核對套用' if row['state']=='READY' else '需人工核對','需核對整卡' if row['state']=='READY' else '需逐筆人工核對')
            lines.extend([row['id']+'／'+row['target_key'],row.get('reason','尚未完成')])
            lines.extend(r.get('context','') for r in d.rows if r.get('scope_key')==row['target_key'] and r['slot_ids'][0] in row['selected_slot_ids'])
            for change in row['changes']:
                before=change['before'];after=change['after']
                lines.append(change['owner']+'／'+change['kind']+'／'+change['id'])
                for label,value in [('原',before),('新',after)]:
                    rect=value['rect'];lines.append(label+f' X {rect["x"]:g}、Y {rect["y"]:g}、寬 {rect["w"]:g}、高 {rect["h"]:g} mm；字級 {value["size_pt"]:g} pt；對齊 '+value['align'])
            checked=self.checked.get(row['target_key'])
            if checked:
                for label,candidate in [('原',checked['target']['envelope']['before']),('新',checked['candidate'])]:
                    for item in candidate.items:
                        if item.slot.id in row['selected_slot_ids']:lines.append(label+'文字X比例 '+str(round(item.scale*100,3))+'%；'+str(candidate.template.width_mm)+'×'+str(candidate.template.height_mm)+' mm')
        d.preflight_text='\n'.join(lines);d.details.setPlainText(d.preflight_text);self.preview_seal=self.seal();d.status.setText('逐候選／尺寸預檢完成；未套用，未發布。');d.filter_rows()

    def require_preview(self):
        d=self.d;d.valid_context()
        if d.running or d.host_window.busy:raise ValueError('既有工作進行中')
        if not d.plan or d.parameters()!=d.preview_parameters or d.selection_pin()!=d.selected_ids or self.seal()!=self.preview_seal:raise ValueError('範圍／參數／結果已變更，請重新預檢')

    def apply(self):
        d=self.d
        try:
            self.require_preview();d.details.setPlainText(d.preflight_text);pin=self.seal()
            if QMessageBox.question(d,'逐候選差異確認','核對原／新差異與各尺寸Gate。只套用本次勾選且預檢合格項；其餘保持待人工。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            self.require_preview()
            if pin!=self.seal():raise ValueError('確認期間預檢結果已變更')
            self.items=list(d.plan['rows']);self.position=0;self.mode='APPLY';self.output=[];d.cancel_event.clear();self.set_running(True);self.next_apply()
        except Exception as error:d.status.setText('未套用：'+str(error))

    def next_apply(self):
        d=self.d
        if self.position>=len(self.items):
            self.set_running(False);d.finished(self.output,self.mode=='UNDO',invalidate=False);return
        row=self.items[self.position];self.position+=1;key=row['target_key'];result=dict(kind='CANDIDATE',id=row['id'],target_key=key,attempted=False,formal_eligible=False)
        try:
            if d.cancel_event.is_set():result.update(outcome='CANCELLED',reason='已停止尚未套用項')
            elif row['state']!='READY':result.update(outcome='UNDO_CONFLICT' if self.mode=='UNDO' else 'NEEDS_MANUAL_REVIEW',reason=row.get('reason','預檢未合格'))
            else:
                adapter,_=self.adapters[key];result['attempted']=True
                result.update(install_candidate_target(adapter,self.checked[key],True))
        except Exception as error:result.update(outcome='UNDO_CONFLICT' if self.mode=='UNDO' else 'STALE',reason=str(error))
        self.output.append(result);d.paint(key,d.state_label(result['outcome']));d.status.setText(f'已核實 {self.position}/{len(self.items)} 個候選交易；可停止尚未開始項。');QTimer.singleShot(0,self.next_apply)

    def undo(self):
        d=self.d
        try:
            d.valid_context()
            if d.running or d.host_window.busy:raise ValueError('既有工作進行中')
            selected={r['scope_key'] for r in d.selected_rows()};receipts={r['target_key']:r for r in d.results if r.get('receipt_id')}
            items=[r for r in d.plan['rows'] if r['target_key'] in selected and r['target_key'] in receipts]
            if not items:raise ValueError('請勾選本批已套用的原交易')
            pin=d.selection_pin()
            if QMessageBox.question(d,'核對合法部分回復','只回復所選原交易實際屬性；較新相同屬性衝突不覆寫。回復版面仍先逐張整卡重驗。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            if pin!=d.selection_pin():raise ValueError('確認期間選取已變更')
            self.inverse_rows=items;self.inverse_receipts=receipts;self.saved_checked=self.checked;self.inverse_checked={};self.position=0;self.mode='UNDO_PREVIEW';d.cancel_event.clear();self.set_running(True);self.next_undo()
        except Exception as error:d.status.setText('未回復：'+str(error))

    def next_undo(self):
        d=self.d
        if self.position>=len(self.inverse_rows):
            self.items=self.inverse_rows;self.position=0;self.checked=self.inverse_checked;self.output=[];self.mode='UNDO';self.next_apply();return
        original=self.inverse_rows[self.position];self.position+=1;row=copy.deepcopy(original);key=row['target_key'];self.inverse_rows[self.position-1]=row
        if d.cancel_event.is_set():row.update(state='BLOCKED',reason='回復預檢已停止');QTimer.singleShot(0,self.next_undo);return
        try:
            adapter,_=self.adapters[key];target=prepare_candidate_undo(adapter,self.saved_checked[key]['target'],self.inverse_receipts[key]['receipt_id']);root=str(d.library.root)
            def work():
                from .storage import Library
                library=Library(root)
                try:return calculate_candidate_target(target,library)
                finally:library.close()
            def done(checked):
                if not candidate_target_current(adapter,target):row.update(state='BLOCKED',reason='回復預檢期間目前資料已變更')
                else:self.inverse_checked[key]=checked;row.update(state='READY' if checked['outcome']=='READY' else 'BLOCKED',reason='；'.join(checked['candidate'].issues))
                QTimer.singleShot(0,self.next_undo)
            def failed(message):row.update(state='BLOCKED',reason=str(message));QTimer.singleShot(0,self.next_undo)
            d.host_window.run_job('批次候選部分回復預檢',work,done,on_error=failed,cancel=d.cancel_event)
        except Exception as error:row.update(state='BLOCKED',reason=str(error));QTimer.singleShot(0,self.next_undo)

    def locate(self):
        from .candidate_edit import CandidateEditDialog
        from PySide6.QtCore import Qt
        d=self.d;d.valid_context()
        if d.running:raise ValueError('請先停止目前工作')
        item=d.table.item(d.table.currentRow(),0)
        if item is None:raise ValueError('請先選取確切物件列')
        row=d.by_key[item.data(Qt.UserRole)];adapter,index=self.adapters[row['scope_key']]
        if candidate_origin_key(adapter,index)!=row['scope_key']:raise ValueError('原候選已換代')
        controller=None
        if hasattr(adapter,'entry'):
            from .multi_size_edit import SizeEditController
            controller=SizeEditController(adapter)
        else:adapter.candidate_list.setCurrentRow(index)
        editor=CandidateEditDialog(adapter,controller)
        for i in range(editor.objects.count()):
            if editor.objects.item(i).data(Qt.UserRole)==row['slot_ids'][0]:editor.objects.item(i).setSelected(True)
        checked=self.checked.get(row['scope_key'])
        if checked and candidate_target_current(adapter,checked['target']):
            editor.show_canvas(editor.proposal_canvas,checked['candidate']);editor.status.setText('左：目前候選。右：本批預檢建議，尚未套用。原人物公司、固定字級與各尺寸整卡Gate仍適用。')
        try:editor.exec()
        finally:editor.deleteLater()

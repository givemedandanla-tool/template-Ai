"""Bounded, transient return locations for the existing workbench, never work copies."""
import copy,json,sqlite3
import time
import weakref
from dataclasses import asdict
from PySide6.QtCore import QPointF,QSignalBlocker,QTimer
from PySide6.QtGui import QTransform
from PySide6.QtWidgets import QGraphicsItem, QMessageBox
from .customers import digest

MODE_LABELS=('原稿標記','模板與 Logo','排版與輸出')


def work_token(window):
    """Only used at explicit recovery boundaries, not on a refresh timer."""
    from .layout_session import canvas_stamp
    return digest(dict(root=str(window.library.root),generation=window.generation,
                       input=window.input_data(),canvas=canvas_stamp(window),
                       reviews=[c.risk_context for c in window.candidates],
                       size=[window.out_w.value(),window.out_h.value()]))


class WorkbenchNavigation:
    def __init__(self,window,label,back):
        self.window=window;self.label=label;self.back=back;self.locations=[]
        self.route=None;self.notice='';self.recovery=None;self.save_error=None;self.restoring=False
        self.back.clicked.connect(self.return_to_work)
        window.tabs.currentChanged.connect(self.update)
        window.inputs_invalidated.connect(self.update)
        window.statusBar().messageChanged.connect(self.update)
        window.candidate_list.currentRowChanged.connect(self.update)
        self.update()

    def canvas(self,mode):
        return (self.window.train_canvas,self.window.edit_canvas,self.window.output_canvas)[mode]

    def pin(self,mode):
        w=self.window
        if mode==2:
            index=w.candidate_list.currentRow()
            if not 0<=index<len(w.candidates):return ('EMPTY',w.generation)
            return ('CANDIDATE',w.candidates[index].template.id,self.candidate_pin(index))
        if mode==0 and w.work:
            stored=w.library.artwork(w.work['id'])
            return ('WORK',w.work['id'],stored['revision'],digest(stored['payload']),
                    digest([asdict(s) for s in w.slots]),digest(asdict(w.crop)) if w.crop else None)
        if mode==1 and w.template:
            stored=w.library.object_snapshot('TEMPLATE',w.template.id)
            return ('TEMPLATE',w.template.id,digest(stored['payload']),digest(w.template.to_dict()))
        return ('EMPTY',)

    def candidate_pin(self,index):
        w=self.window
        return (self.multi_pin(w.candidates[index]),w.out_w.value(),w.out_h.value())

    def capture(self,mode=None):
        w=self.window;mode=w.tabs.currentIndex() if mode is None else mode;canvas=self.canvas(mode)
        from .gui import Box
        return dict(kind='MAIN',root=str(w.library.root),generation=w.generation,mode=mode,pin=self.pin(mode),
                    transform=QTransform(canvas.transform()),centre=QPointF(canvas.mapToScene(canvas.viewport().rect().center())),
                    selected=[item.slot.id for item in canvas.scene().selectedItems() if isinstance(item,Box)],
                    slot=w.current_slot.id if w.current_slot else None,
                    form_pin=self.form_pin(mode),
                    page_scroll=[w.output_page_scroll.horizontalScrollBar().value(),w.output_page_scroll.verticalScrollBar().value()] if mode==2 else None,
                    template_page=w.template_stack.currentIndex())

    def form_pin(self,mode):
        if mode==2:return None
        w=self.window
        if mode==w._active_mode:
            if w.current_slot is None:return None
            form=dict(kind=w.kind.currentData(),owner=w.owner.currentData(),index=w.index.value(),
                      coords=[s.value() for s in w.coords],font=w.font.currentFont().family(),
                      pt=w.pt.value(),color=w.text_color.text(),scale=w.scale.value(),
                      align=w.align.currentData(),required=w.required.isChecked(),incomplete=dict(w._property_raw_inputs))
            return digest(dict(slot=w.current_slot.id,form=form))
        selected,undo,redo,stored=w._mode_memory.get(mode,(None,[],[],None))
        if not selected or not stored:return None
        form={k:v for k,v in stored.items() if k not in ('font','font_display','source_pin','object_pin','pending')};form['font']=stored['font'].family()
        return digest(dict(slot=selected,form=form))

    def multi_pin(self,candidate):
        from .candidate_sync import candidate_pin
        from .candidate_edit import dependency_token
        w=self.window;snapshot=candidate.risk_context.get('input_snapshot',{})
        # Navigation compares versions and known-file stat stamps only. Actual
        # Logo hashing/quality and whole-card validation stay at existing gates.
        assets=[];bindings=[]
        for identity in sorted({item.logo['id'] for item in candidate.items if item.logo and item.logo.get('id')}):
            row=w.library.db.execute('SELECT payload FROM logos WHERE id=?',(identity,)).fetchone()
            assets.append([identity,json.loads(row[0]) if row else None])
        for company in snapshot.get('companies',[]):
            if not company.get('source_entity_id'):continue
            try:row=w.library.db.execute('SELECT company_id,confirmed_name FROM logo_entity_bindings WHERE entity_id=?',(company['source_entity_id'],)).fetchone()
            except sqlite3.OperationalError:row=None
            bindings.append([company['source_entity_id'],list(row) if row else None])
        return digest([candidate_pin(candidate),dependency_token(w,candidate.template,snapshot.get('logos',{})),assets,bindings])

    def capture_multi(self,origin):
        entry=origin.entry();candidate=origin.service.selected(entry)
        if candidate is None:raise ValueError('此尺寸沒有可返回的候選')
        return dict(kind='MULTI_SIZE',root=str(self.window.library.root),generation=self.window.generation,mode=2,
                    pin=self.multi_pin(candidate),origin=weakref.ref(origin),key=entry['key'],candidate=candidate.template.id,
                    scroll=[origin.table.horizontalScrollBar().value(),origin.table.verticalScrollBar().value()])

    def remember(self,mode=None,origin=None):
        try:location=self.capture_multi(origin) if origin is not None else self.capture(mode)
        except (ValueError,OSError,KeyError,TypeError):
            self.notice='目前物件尚無可核對的返回位置；修正後請由原列表重新選取。'
        else:
            if not self.locations or any(location[k]!=self.locations[-1][k] for k in ('kind','root','generation','mode','pin')):
                self.locations.append(location);self.locations=self.locations[-8:]
        self.update()

    def begin(self,route,origin=None):
        self.remember(origin=origin);self.route=route;self.update()

    def finish(self):
        self.route=None;self.update()

    def return_to_work(self):
        if not self.locations:return False
        w=self.window;location=self.locations.pop();mode=location['mode'];reason=None;self.restoring=True
        if location['kind']=='MULTI_SIZE':
            try:self.return_multi(location)
            except (ValueError,OSError,KeyError,TypeError,StopIteration) as error:
                self.notice='無法還原原位置：'+str(error)+'。保留目前尺寸候選，請重新選取或同步重驗。'
                from shiboken6 import isValid
                origin=location['origin']()
                if origin is not None and isValid(origin):origin.status.setText(self.notice)
                else:w.tabs.setCurrentIndex(2);w.export_button.setEnabled(False)
                reason=str(error)
            finally:self.restoring=False
            self.update();return reason is None
        try:
            if w.library.closed or str(w.library.root)!=location['root']:raise ValueError('工作資料位置已變更')
            if w.generation!=location['generation']:raise ValueError('當次人物資料或資產版本已改變，原候選需重新驗證')
            if self.form_pin(mode)!=location['form_pin']:raise ValueError('尚未套用的物件屬性已有更新，保留目前編輯')
            if mode==2 and location['pin'][0]=='CANDIDATE':
                matches=[i for i,c in enumerate(w.candidates) if c.template.id==location['pin'][1]]
                if len(matches)!=1:raise ValueError('原候選已移除或無法唯一辨識')
                index=matches[0]
                if w.candidates[index].generation!=w.generation:raise ValueError('原候選目前需重新驗證')
                if ('CANDIDATE',w.candidates[index].template.id,self.candidate_pin(index))!=location['pin']:raise ValueError('原候選、模板或人工編輯版本已變更')
            elif self.pin(mode)!=location['pin']:raise ValueError('原作品、模板或物件版本已變更')
            # Changing an existing tab retains its own pending property form/history.
            # Never copy business data or a previously safe risk assessment back.
            w.tabs.setCurrentIndex(mode)
            if mode==2 and location['pin'][0]=='CANDIDATE':
                if w.candidate_list.currentRow()!=index:w.candidate_list.setCurrentRow(index)
                from .gui import Box
                for item in list(w.output_canvas.scene().items()):
                    if isinstance(item,Box):w.output_canvas.scene().removeItem(item)
                slots={slot.id:slot for slot in w.candidates[index].template.slots}
                if any(identity not in slots for identity in location['selected']):raise ValueError('原定位物件已不存在')
                for identity in location['selected']:
                    box=Box(copy.deepcopy(slots[identity]),lambda *args:None)
                    box.setFlag(QGraphicsItem.ItemIsMovable,False);box.setFlag(QGraphicsItem.ItemIsSelectable,True)
                    w.output_canvas.scene().addItem(box);box.setSelected(True)
            else:
                if mode==1:w.template_stack.setCurrentIndex(location['template_page'])
                canvas=self.canvas(mode)
                # Selection callbacks normally populate the property form from
                # the saved object. A view-only return must retain pending fields.
                with QSignalBlocker(canvas):
                    for identity in location['selected']:canvas.select_id(identity)
            canvas=self.canvas(mode);canvas.setTransform(location['transform']);canvas.centerOn(location['centre']);canvas.view_changed.emit()
            if mode==2:
                w.output_page_scroll.horizontalScrollBar().setValue(location['page_scroll'][0])
                w.output_page_scroll.verticalScrollBar().setValue(location['page_scroll'][1])
            self.notice='已返回原工作視角；正式輸出仍依當前尺寸檢查。'
        except (ValueError,OSError,KeyError,TypeError) as error:
            reason=str(error);w.tabs.setCurrentIndex(mode)
            # Leave the newest actual geometry, selection and form untouched.
            self.notice='無法還原原位置：'+reason+'。已返回目前列表，請重新選取。'
            if mode==2:
                w.export_button.setEnabled(False);w.candidate_list.setFocus()
        finally:self.restoring=False
        self.update();return reason is None

    def return_multi(self,location):
        from shiboken6 import isValid
        w=self.window;origin=location['origin']()
        if origin is None or not isValid(origin):raise ValueError('原多尺寸視窗已關閉')
        if w.library.closed or str(w.library.root)!=location['root']:raise ValueError('工作資料位置已變更')
        if w.generation!=location['generation'] or not origin.is_current():raise ValueError('此尺寸所引用資料已變，需同步重驗')
        entry=next(e for e in origin.service.entries if e['key']==location['key'])
        matches=[c for c in entry['candidates'] if c.template.id==location['candidate']]
        if len(matches)!=1 or self.multi_pin(matches[0])!=location['pin']:raise ValueError('原尺寸候選、人工編輯或資產版本已變更')
        row=next(i for i,size in enumerate(origin.sizes) if size==entry['size_mm'])
        origin.table.setCurrentCell(row,1);origin.select_candidate(entry['key'],location['candidate'])
        origin.table.horizontalScrollBar().setValue(location['scroll'][0]);origin.table.verticalScrollBar().setValue(location['scroll'][1])
        self.notice='已返回原尺寸候選；各尺寸正式輸出仍需目前版本完整檢查。'
        origin.status.setText(self.notice);origin.show();origin.raise_()

    def recovery_started(self):
        self.save_error=None;self.notice='正在核實及寫入短期恢復資料；尚未保存。';self.update()

    def recovery_saved(self,receipt,token):
        if not all(receipt.get(k) is True for k in ('saved','encrypted','authenticated')):
            self.recovery_failed('未取得已驗證落盤收據');return
        from .layout_recovery import LayoutRecovery
        from .source_links import fingerprint
        path=LayoutRecovery(self.window.library.root).path
        try:
            if path.is_symlink() or list(fingerprint(path.stat()))!=receipt.get('stat'):raise ValueError('落盤收據與實際檔案不一致')
        except (ValueError,OSError):self.recovery_failed('恢復檔案缺失或已變更');return
        self.recovery=dict(token=token,expires=receipt['expires'],stat=receipt['stat']);self.save_error=None
        QTimer.singleShot(max(1,int((receipt['expires']-time.time())*1000)),self.window,self.update)
        self.notice='短期恢復資料已加密落盤；正式客戶與模板另行核准保存。';self.update()

    def recovery_failed(self,error):
        self.save_error='短期恢復保存失敗；當次操作尚未安全保存。'
        self.notice=self.save_error;self.update()

    def recovery_cleared(self):
        self.recovery=None;self.notice='短期恢復資料已清除；當次排版仍僅在記憶體。';self.update()

    def recovery_current(self):
        if not self.recovery or self.recovery['expires']<=time.time():return False
        from .layout_recovery import LayoutRecovery
        from .source_links import fingerprint
        path=LayoutRecovery(self.window.library.root).path
        try:return not path.is_symlink() and list(fingerprint(path.stat()))==self.recovery['stat'] and self.recovery['token']==work_token(self.window)
        except (ValueError,OSError,KeyError,TypeError):return False

    def pending_form(self):
        w=self.window
        if w.tabs.currentIndex()==2 or w.current_slot is None:return False
        if getattr(w,'_property_form_baseline',None) is not None:
            from .property_context import pending_main
            return pending_main(w)
        form=dict(kind=w.kind.currentData(),owner=w.owner.currentData(),index=w.index.value(),
                  coords=[s.value() for s in w.coords],font=w.font.currentFont(),pt=w.pt.value(),
                  color=w.text_color.text(),scale=w.scale.value(),align=w.align.currentData(),
                  required=w.required.isChecked(),font_display=getattr(w,'_selected_font_display',None))
        return not self.form_matches(w.current_slot,form)

    @staticmethod
    def form_matches(slot,form):
        if form.get('incomplete'):return False
        displayed=form.get('font_display')
        family=form['font'].family()
        same_font=family==slot.font or bool(displayed and displayed['slot_id']==slot.id and family==displayed['display'])
        return (same_font and form['kind']==slot.kind and form['owner']==slot.owner
                and form['index']==slot.index+1 and form['coords']==[slot.rect.x,slot.rect.y,slot.rect.w,slot.rect.h]
                and form['color'].strip()==slot.color and form['pt']==slot.size_pt
                and abs(form['scale']/100-slot.min_scale)<1e-8 and form['align']==slot.align
                and form['required']==slot.required)

    def close_impacts(self):
        w=self.window;impacts=[]
        if self.pending_form():impacts.append('目前物件有尚未套用的屬性。')
        if getattr(w,'pending_property_conflict',None):impacts.append('仍有舊物件的未套用輸入供核對；排版短期恢復不包含這份屬性。')
        from .object_dialog import ObjectToolsDialog
        if any(d.dirty or d.retained_patch for d in w.findChildren(ObjectToolsDialog)):impacts.append('既有物件編輯器仍有未套用屬性；排版恢復不包含這份輸入。')
        for mode,(selected,undo,redo,form) in w._mode_memory.items():
            if mode!=w.tabs.currentIndex() and selected and form:
                slots=w.slots if mode==0 else w.template.slots if mode==1 and w.template else []
                slot=next((s for s in slots if s.id==selected),None)
                if slot and not self.form_matches(slot,form):
                    impacts.append('其他功能頁有已保留、尚未套用的物件屬性。')
        if (w.candidates or self.input_present()) and not self.recovery_current():impacts.append('當次人物資料、排版及人工修改尚未保存為目前版本的短期恢復資料。')
        from .multi_size_dialog import MultiSizeDialog
        if any(getattr(d,'service',None) and any(e.get('candidates') for e in d.service.entries) for d in w.findChildren(MultiSizeDialog)):
            impacts.append('多尺寸候選僅保留在當次視窗；主排版短期恢復不包含這些獨立作品。')
        if self.save_error:impacts.append(self.save_error)
        return list(dict.fromkeys(impacts))

    def input_present(self):
        w=self.window
        # Inspect existing widgets only; no source files, customers or training DB.
        return any(table.item(row,col) and table.item(row,col).text().strip()
                   for table in (w.people,w.companies) for row in range(table.rowCount())
                   for col in range(table.columnCount()))

    def confirm_close(self):
        impacts=self.close_impacts()
        if not impacts:return True
        box=QMessageBox(self.window);box.setWindowTitle('當次工作尚未安全保存')
        box.setText('\n'.join(impacts));box.setInformativeText('切換功能會保留當次內容；關閉程式將結束記憶體工作。正式主檔另依原保存規則處理。')
        stay=box.addButton('返回繼續編輯',QMessageBox.RejectRole)
        recover=box.addButton('開啟安全恢復',QMessageBox.ActionRole)
        discard=box.addButton('明確放棄當次操作並關閉',QMessageBox.DestructiveRole)
        box.setDefaultButton(stay);box.exec();chosen=box.clickedButton()
        if chosen==recover:self.window.layout_session()
        return chosen==discard

    def update(self,*args):
        w=self.window;mode=w.tabs.currentIndex();parts=[self.route or MODE_LABELS[mode]]
        index=w.candidate_list.currentRow()
        if mode==2 and 0<=index<len(w.candidates):
            c=w.candidates[index];parts+=[f'候選 {index+1}',f'{c.template.width_mm:g}×{c.template.height_mm:g} mm']
            parts.append('需重新驗證' if c.generation!=w.generation else '正式輸出仍需當前檢查')
            parts.append('短期恢復已加密落盤；目前進度另需核對' if self.recovery and self.recovery['expires']>time.time() else '尚未保存的當次排版')
        elif mode==2 and self.input_present():parts.append('當次人物資料尚未保存；尚未產生候選')
        elif mode==1 and w.template:parts.append('已發布模板' if w.template.state=='published' else '模板草稿；依原流程保存')
        elif mode==0 and w.work:parts.append('原稿標記；未保存變更依原流程核對')
        if w.busy:parts.append('背景工作進行中')
        if self.pending_form():parts.append('尚未套用屬性；切換後保留')
        if self.save_error:parts.append(self.save_error)
        if self.notice.startswith('無法還原'):parts.append(self.notice)
        self.label.setText(' ｜ '.join(parts));self.label.setToolTip(self.notice or self.label.text())
        self.back.setEnabled(bool(self.locations));self.back.setToolTip(self.notice or '返回原工作；失效時回到目前列表')

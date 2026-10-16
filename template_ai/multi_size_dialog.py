"""結果輸出區的多尺寸矩陣：各尺寸、確切候選與正式／預覽分開。"""
from copy import deepcopy
import json
import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,
    QTableWidgetItem,QComboBox,QCheckBox,QDoubleSpinBox,QPlainTextEdit,QFileDialog,QMessageBox,QHeaderView)

from .worker_callbacks import JobCallbacks
from .customers import digest
from .input_graph import InputGraph
from .multi_size import MultiSizeWorkflow,size_key

SIZE_LABELS=dict(VALID='數位檢查通過',BLOCKED='有問題／禁止正式輸出',FAILED='驗證失敗',NO_TEMPLATE='無適用模板',CANCELLED='已取消',NOT_CHECKED='尚未檢查')


class MultiSizeDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.running=False;self.service=None
        self.selections={};self.stop=threading.Event();self.stale=threading.Event()
        self.setWindowTitle('多尺寸驗證總覽／部分正式輸出與獨立占位預覽');self.resize(1180,780)
        layout=QVBoxLayout(self);self.status=QLabel('勾選要計算的實體尺寸；每尺寸獨立驗證。輸出模式預設不選。');self.status.setWordWrap(True);layout.addWidget(self.status)
        bar=QHBoxLayout();self.width,self.height=QDoubleSpinBox(),QDoubleSpinBox()
        for spin,value in ((self.width,window.out_w.value()),(self.height,window.out_h.value())):
            spin.setRange(1,2000);spin.setDecimals(4);spin.setValue(value);spin.setSuffix(' mm');bar.addWidget(spin)
        self.button(bar,'加入尺寸',self.add_size);self.button(bar,'計算所選尺寸',self.start);self.button(bar,'安全取消計算',self.stop.set);layout.addLayout(bar)
        self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(['計算尺寸','實體尺寸 mm','確切模板／版本','最後驗證狀態','Logo狀態','輸出類別（預設不選）']);layout.addWidget(self.table,2)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        bar=QHBoxLayout();self.button(bar,'預覽目前尺寸與全部問題',self.preview);self.button(bar,'選此尺寸公司的確切Logo',self.choose_logo)
        self.formats={}
        for name in ('pdf','png','jpg'):
            box=QCheckBox(name.upper());box.setChecked(name=='pdf');self.formats[name]=box;bar.addWidget(box)
        layout.addLayout(bar);bar=QHBoxLayout();bar.addWidget(QLabel('非正式預覽格式（預設PNG）'));self.preview_formats={}
        for name in ('png','jpg','pdf'):
            box=QCheckBox(name.upper());box.setChecked(name=='png');self.preview_formats[name]=box;bar.addWidget(box)
        self.export_button=self.button(bar,'確認清單後輸出',self.export);self.export_button.setEnabled(False);layout.addLayout(bar)
        bar=QHBoxLayout();self.button(bar,'編輯此尺寸當次人工版面',self.edit_local_candidate);self.button(bar,'修改共用來源人物資料',lambda:self.window.edit_input_graph(return_origin=self));self.button(bar,'保留人工版面同步共用資料',self.sync_source);self.button(bar,'跨候選／尺寸屬性差異',self.cross_properties);self.button(bar,'批次候選修正',lambda:self.window.batch_object_center(origin=self));layout.addLayout(bar)
        bar=QHBoxLayout();self.button(bar,'開啟尺寸 Logo 管理',lambda:self.window.logo_center(return_origin=self));self.button(bar,'返回原候選／尺寸',self.window.navigation.return_to_work);layout.addLayout(bar)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details,1)
        sizes={(t.width_mm,t.height_mm) for t in window.library.templates(True)}|{(window.out_w.value(),window.out_h.value())}
        self.sizes=[]
        for size in sorted(sizes):self.insert_size(size,checked=list(size)==[window.out_w.value(),window.out_h.value()])
        window.inputs_invalidated.connect(self.changed)

    def button(self,bar,label,action):
        button=QPushButton(label);button.clicked.connect(action);bar.addWidget(button);return button

    def changed(self,*_):
        self.stale.set();self.export_button.setEnabled(False)
        self.status.setText('輸入／模板／Logo版本已變更，先重新計算；舊候選未獲放行。')
        for row in range(self.table.rowCount()):
            if self.table.item(row,3):self.table.item(row,3).setText('資料已變／保留人工版面待重驗')
            mode=self.table.cellWidget(row,5)
            if mode:mode.setCurrentIndex(0);mode.model().item(1).setEnabled(False)
        prefix='以下是前一版本的歷史結果；目前資料尚未重驗。\n'
        if self.service and not self.details.toPlainText().startswith(prefix):self.details.setPlainText(prefix+self.details.toPlainText())

    def insert_size(self,size,checked=True):
        if size_key(*size) in {size_key(*s) for s in self.sizes}:return
        self.sizes.append(list(size));row=self.table.rowCount();self.table.setRowCount(row+1)
        item=QTableWidgetItem();item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable);item.setCheckState(Qt.Checked if checked else Qt.Unchecked);self.table.setItem(row,0,item)
        for col,text in ((1,f'{size[0]:g}×{size[1]:g}'),(3,'NOT_CHECKED'),(4,'尚未匹配')):
            item=QTableWidgetItem(text);item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsSelectable);self.table.setItem(row,col,item)
        mode=QComboBox();mode.addItems(['不輸出','FINAL','PREVIEW']);self.table.setCellWidget(row,5,mode)

    def add_size(self):
        if not self.running:self.insert_size([self.width.value(),self.height.value()]);self.changed()

    def context_current(self):
        try:return not self.window.library.closed and self.window.library.root==self.context_root and not self.stale.is_set() and self.window.generation==self.generation and digest(self.window.input_data())==self.input_signature
        except (ValueError,TypeError,AttributeError):return False

    def is_current(self):
        return self.context_current() and self.service is not None and self.service.generation==self.generation and self.service.library is self.window.library

    def background(self,label,operation,finished,*,resource_kind='ANALYSIS',cancel=None,on_error=None,require_current=False):
        root=self.window.library.root;self.running=True;self.table.setEnabled(False);self.status.setText(label+' · 共用背景工作排程／核對中，尚未完成或保存')
        def worker():
            from .storage import Library
            library=None
            try:
                library=Library(root);return {'result':operation(library)}
            except Exception as error:return {'error':str(error)}
            finally:
                if library:library.close()
        def completed(result):
            self.running=False;self.table.setEnabled(True)
            if 'error' in result:
                self.status.setText('未完成：'+result['error'])
                if on_error:on_error(result['error'])
                return
            if require_current and (self.window.library.closed or self.window.library.root!=root or not self.context_current()):
                message='較新的輸入／來源已存在，舊結果已忽略；人工版面保留'
                self.status.setText(message)
                if on_error:on_error(message)
                return
            self.status.setText(label+' · 已完成實際計算；採用與輸出仍依各尺寸Gate')
            finished(result['result'])
        try:self.window.run_job(label,worker,JobCallbacks(completed,lambda error:completed({'error':str(error)})),resource_kind=resource_kind,cancel=cancel)
        except Exception:self.running=False;self.table.setEnabled(True);raise

    def start(self):
        if self.running or self.window.busy:return
        try:
            sizes=[s for i,s in enumerate(self.sizes) if self.table.item(i,0).checkState()==Qt.Checked]
            if self.service and (getattr(self,'sync_all',False) or any(c.risk_context.get('manual_edit_receipt') for entry in self.service.entries for c in entry['candidates'])):
                for entry in self.service.entries:
                    if entry['size_mm'] not in sizes:sizes.append(deepcopy(entry['size_mm']))
            if not sizes:raise ValueError('先勾選要計算的實體尺寸')
            if getattr(self.window,'active_input_graph',None) is None and not self.service:
                graph=InputGraph.from_legacy(*self.window.input_data());self.window.adopt_input_graph(graph.data,history=graph)
            self.inputs=deepcopy(self.window.input_data());self.generation=self.window.generation;self.input_signature=digest(self.inputs);self.context_root=self.window.library.root
            active=getattr(self.window,'active_input_graph',None)
            if active:self.graph=active.clone()
            elif not hasattr(self,'graph') or getattr(self,'graph_input_signature',None)!=self.input_signature:self.graph=InputGraph.from_legacy(*self.inputs)
            self.graph_input_signature=self.input_signature;self.stop.clear();self.stale.clear();self.export_button.setEnabled(False)
            inputs,graph,generation,chosen=deepcopy(self.inputs),deepcopy(self.graph.data),self.generation,deepcopy(self.selections)
            previous=deepcopy(self.service.entries) if self.service else []
            scope=None
            if getattr(self.window,'reorder_template_id',None):
                snapshot=getattr(self.window,'reorder_customer_snapshot',None)
                scope=[s['template_id'] for s in snapshot['styles']] if snapshot else [self.window.reorder_template_id]
            def operation(library):
                service=MultiSizeWorkflow(library,inputs,graph,generation)
                return service.calculate_preserving(sizes,previous,chosen,scope,self.stop) if previous else service.calculate(sizes,chosen,scope,self.stop)
            def finished(entries):
                if self.service:self.service.close_format_reviews()
                self.service=MultiSizeWorkflow(self.window.library,inputs,graph,generation);self.service.entries=entries;self.render_rows()
                self.export_button.setEnabled(self.is_current())
                self.status.setText(f'實際處理{len(entries)}個尺寸；未檢查／取消／失敗各自保留狀態。正式與PREVIEW須明確選擇。')
            self.background('逐尺寸計算／保留人工版面驗證',operation,finished,resource_kind='GEOMETRY',cancel=self.stop,require_current=True)
        except (ValueError,KeyError,OSError) as error:self.status.setText('未開始：'+str(error))

    def sync_source(self):
        if self.running or self.window.busy:return
        if not self.service:self.status.setText('先計算明確尺寸集合');return
        self.sync_all=True
        try:self.start()
        finally:self.sync_all=False

    def cross_properties(self):
        if self.running or self.window.busy:return
        try:
            if not self.is_current():raise ValueError('先同步目前資料並完成各尺寸計算')
            from .candidate_sync_dialog import CrossPropertyDialog
            dialog=CrossPropertyDialog(self)
            try:dialog.exec()
            finally:dialog.deleteLater()
        except (ValueError,KeyError,IndexError,StopIteration) as error:self.status.setText('未開啟跨候選比較：'+str(error))

    def edit_local_candidate(self):
        if self.running or self.window.busy:self.status.setText('原背景工作尚未完成，保留目前版面');return
        try:
            if not self.is_current():raise ValueError('共用資料已改，先保留人工版面同步重驗')
            entry=self.entry();index=next(i for i,c in enumerate(entry['candidates']) if c.template.id==entry['selected'])
            from .multi_size_edit import SizeEditAdapter,SizeEditController
            from .candidate_edit import CandidateEditDialog
            from shiboken6 import isValid
            adapter=SizeEditAdapter(self,entry,index);controller=SizeEditController(adapter);dialog=CandidateEditDialog(adapter,controller=controller)
            def closed(result):
                adapter.editor_closed=True;controller.release()
            dialog.finished.connect(closed)
            try:dialog.exec()
            finally:
                if isValid(dialog):dialog.deleteLater()
        except (ValueError,KeyError,IndexError,StopIteration) as error:self.status.setText('未開啟此尺寸人工編輯：'+str(error))

    def render_rows(self):
        for entry in self.service.entries:
            row=next(i for i,s in enumerate(self.sizes) if size_key(*s)==entry['key'])
            combo=QComboBox()
            for candidate in entry['candidates']:combo.addItem(f'{candidate.template.name}／v{candidate.template.version}／{candidate.template.id}',candidate.template.id)
            combo.setCurrentIndex(max(0,combo.findData(entry['selected'])))
            combo.activated.connect(lambda _,key=entry['key'],control=combo:self.select_candidate(key,control.currentData()))
            states=SIZE_LABELS
            self.table.setCellWidget(row,2,combo);self.table.item(row,3).setText(states.get(entry['state'],entry['state']))
            logo_states=dict(MISSING='缺少此尺寸已核准Logo',SINGLE_PREVIEW='單一版本待輸出驗證',MULTIPLE_REVIEW_REQUIRED='多版本需明確選擇',IDENTITY_REVIEW_REQUIRED='公司身分待核對',EXACT_VERSION_PENDING_OUTPUT='已選確切版本待輸出驗證',SELECTION_INVALID_NO_REPLACEMENT='原選擇已失效，未替換')
            self.table.item(row,4).setText('；'.join(port+'：'+logo_states.get(state,state) for port,state in entry['logo_states'].items()) or '此輸入無公司Logo')
            for col in (3,4):self.table.item(row,col).setToolTip(self.table.item(row,col).text())
            mode=self.table.cellWidget(row,5);mode.setCurrentIndex(0);mode.model().item(1).setEnabled(bool(self.service.selected(entry) and self.service.selected(entry).formal_eligible and self.is_current()))
        lines=[]
        for e in self.service.entries:
            c=self.service.selected(e);lines.append(f"{e['size_mm'][0]:g}×{e['size_mm'][1]:g} mm：{e['state']}")
            if c:
                lines.append(f'{c.template.name}／v{c.template.version}／人物容量{c.template.capacity}')
                lines.extend('需處理：'+issue for issue in c.issues)
                if not c.issues:lines.append('本次數位必要檢查通過；實體印刷條件需另行驗收。')
            lines.extend('模板驗證失敗：'+r['reason'] for r in e['failures'])
            lines.append('')
        self.details.setPlainText('\n'.join(lines))

    def select_candidate(self,key,identity):
        if self.running or not self.service:return
        self.service.select(key,identity)
        entry=next(e for e in self.service.entries if e['key']==key);row=next(i for i,s in enumerate(self.sizes) if size_key(*s)==key)
        combo=self.table.cellWidget(row,2)
        if combo is not None:combo.setCurrentIndex(combo.findData(identity))
        self.table.item(row,3).setText(SIZE_LABELS.get(entry['state'],entry['state']));self.table.cellWidget(row,5).setCurrentIndex(0);self.table.cellWidget(row,5).model().item(1).setEnabled(self.service.selected(entry).formal_eligible and self.is_current())

    def entry(self):
        if not self.service:raise ValueError('先完成所選尺寸計算')
        row=self.table.currentRow()
        if not 0<=row<len(self.sizes):raise ValueError('選取一個尺寸')
        entry=next((e for e in self.service.entries if e['key']==size_key(*self.sizes[row])),None)
        if entry is None:raise ValueError('此尺寸尚未計算')
        return entry

    def preview(self):
        try:
            entry=self.entry()
            if not self.is_current():raise ValueError('資料已變，先重新計算')
            candidate=self.service.revalidate(entry)
            from .gui import Canvas
            from .render import render_image,preview_height
            dialog=QDialog(self);dialog.setWindowTitle('此尺寸非正式預覽／所有未通過事項');dialog.resize(950,700);layout=QVBoxLayout(dialog)
            canvas=Canvas();canvas.set_content(candidate.template.width_mm,preview_height(candidate),render_image(candidate,96,True));canvas.set_mode('pan');layout.addWidget(canvas);canvas.fit()
            detail=QPlainTextEdit('\n'.join(candidate.issues) or '數位檢查通過；本畫面仍為預覽。');detail.setReadOnly(True);layout.addWidget(detail);dialog.exec()
        except (ValueError,KeyError,OSError) as error:self.status.setText('未預覽：'+str(error))

    def choose_logo(self):
        try:
            entry=self.entry();companies=self.graph.data['companies']
            if not companies:raise ValueError('此輸入無公司Logo關聯')
            from PySide6.QtWidgets import QInputDialog
            labels=[self.graph.label(c['id'])+'／'+c['id'] for c in companies]
            label,ok=QInputDialog.getItem(self,'此尺寸的公司','只改此尺寸選擇，不移植幾何',labels,0,False)
            if not ok:return
            cid=companies[labels.index(label)]['id']
            from .logo_choice_dialog import LogoChoiceDialog
            dialog=LogoChoiceDialog(self.window,self.graph,cid,self,width=entry['size_mm'][0],height=entry['size_mm'][1])
            if dialog.exec()==QDialog.Accepted and dialog.selected_asset:
                self.selections.setdefault(entry['key'],{})[cid]=dialog.selected_asset['id'];self.changed()
        except (ValueError,KeyError,OSError) as error:self.status.setText(str(error))

    def export(self):
        try:
            if self.running or not self.service or not self.is_current():raise ValueError('先完成目前資料的多尺寸驗證')
            requests=[]
            for i,size in enumerate(self.sizes):
                mode=self.table.cellWidget(i,5).currentText()
                if mode!='不輸出':requests.append(dict(key=size_key(*size),mode=mode,formats=[f for f,b in (self.preview_formats if mode=='PREVIEW' else self.formats).items() if b.isChecked()]))
            directory=QFileDialog.getExistingDirectory(self,'選一次本機輸出資料夾；FINAL／PREVIEW分開')
            if not directory:return
            plan=self.service.plan(directory,requests)
            lines=['請核對以下尺寸與輸出類別；占位預覽不能作正式成品。']
            for item in plan['items']:
                lines.append(item['mode']+'：'+item['path'])
                lines.extend('  待解問題：'+str(issue) for issue in item['issues'])
            for item in plan['omitted']:
                lines.append('不輸出 '+str(item['size_mm'])+' mm：'+('；'.join(map(str,item['issues'])) or item['state']))
            if plan['partial']:lines.append('本次為部分輸出。確認表示只輸出上述檔案，其他尺寸仍未完成。')
            if QMessageBox.question(self,'確認每尺寸類別、未輸出原因與實際檔案','\n'.join(lines))!=QMessageBox.Yes:return
            if not self.is_current():raise ValueError('確認期間輸入已變更，未輸出')
            from .output_batch_dialog import OutputBatchDialog
            dialog=OutputBatchDialog(self,plan);self.output_dialog=dialog;dialog.exec()
            results=dialog.engine.items;self.last_output=results
            self.details.setPlainText('\n'.join(r['mode']+'／'+r['status']+'：'+r['path']+('\n原因：'+r['reason'] if r.get('reason') else '') for r in results));passed=sum(r['status']=='SUCCESS' for r in results)
            self.status.setText(f'成功{passed}／清單{len(results)}檔；失敗、略過、阻擋與未完成逐筆保留。');dialog.deleteLater()
        except (ValueError,KeyError,OSError) as error:self.status.setText('未輸出：'+str(error))

    def closeEvent(self,event):
        if self.running:self.stop.set();self.status.setText('安全停止中；等待當前工作完成再關閉。');event.ignore()
        else:
            if self.service:self.service.close_format_reviews()
            super().closeEvent(event)
    def reject(self):
        if self.running:self.stop.set();self.status.setText('取消中；原背景工作結束後才能安全關閉。');return
        if self.service:self.service.close_format_reviews()
        super().reject()

"""Desktop body for shared-rule learning and persistent relative-layout drafts."""
from copy import deepcopy
import hashlib
import threading

from PySide6.QtCore import Qt,QThread,Signal,QTimer
from PySide6.QtGui import QPixmap,QPen,QColor,QBrush
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTabWidget,QWidget,
    QComboBox,QTableWidget,QTableWidgetItem,QLineEdit,QCheckBox,QDoubleSpinBox,QGraphicsView,
    QGraphicsScene,QGraphicsRectItem,QFileDialog,QMessageBox,QSplitter,QPlainTextEdit,QGroupBox)

from .design_learning import CrossWorkLearning,USE
from .design_source_binding import SourceTypographyReview
from .design_session import DesignSessions
from .design_synthesis import input_facts
from .design_jobs import DesignJobs,run_design_job
from .fonts import FontManager
from .input_graph import InputGraph
from .model import new_id


class DesignWorker(QThread):
    progress=Signal(object);completed=Signal(object);failed=Signal(str)
    def __init__(self,root,job,token,parent=None):
        super().__init__(parent);self.root=root;self.job=job;self.token=token;self.cancel=threading.Event()
    def run(self):
        try:self.completed.emit(run_design_job(self.root,self.job,self.token,self.cancel.is_set,self.progress.emit))
        except Exception as error:self.failed.emit(str(error)[:1000])


class DraftSolveWorker(QThread):
    progress=Signal(object);completed=Signal(object);failed=Signal(str)
    def __init__(self,root,identity,revision,parent=None):
        super().__init__(parent);self.root=root;self.identity=identity;self.revision=revision;self.cancel=threading.Event()
    def run(self):
        from .storage import Library
        library=Library(self.root)
        try:self.completed.emit(DesignSessions(library).solve(self.identity,self.revision,cancel=self.cancel.is_set,progress=self.progress.emit))
        except Exception as error:self.failed.emit(type(error).__name__+': '+str(error))
        finally:library.close()


class RelativeBox(QGraphicsRectItem):
    def __init__(self,identity,rect,canvas):
        super().__init__(0,0,rect.w,rect.h);self.identity=identity;self.canvas=canvas
        self.setPos(rect.x,rect.y);self.start_position=self.pos()
        self.setFlags(QGraphicsRectItem.ItemIsMovable|QGraphicsRectItem.ItemIsSelectable)
        self.setPen(QPen(QColor('#2563eb'),.2));self.setBrush(QBrush(Qt.NoBrush))
        self.setToolTip('拖至另一欄附近，調整兩欄的相對位置')
    def mousePressEvent(self,event):self.start_position=self.pos();super().mousePressEvent(event)
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        if self.pos()==self.start_position:return
        centre=self.sceneBoundingRect().center()
        others=[box for box in self.canvas.boxes if box is not self]
        if not others:self.setPos(self.start_position);return
        target=min(others,key=lambda box:((box.sceneBoundingRect().center()-centre).manhattanLength(),box.identity))
        delta=centre-target.sceneBoundingRect().center()
        relation=('LEFT_OF' if delta.x()<0 else 'RIGHT_OF') if abs(delta.x())>abs(delta.y()) else ('ABOVE' if delta.y()<0 else 'BELOW')
        self.setPos(self.start_position)
        canvas=self.canvas;identity=self.identity;other=target.identity
        QTimer.singleShot(0,canvas,lambda:canvas.requested.emit(identity,relation,other))


class RelativeCanvas(QGraphicsView):
    requested=Signal(str,str,str)
    def __init__(self,parent=None):
        super().__init__(parent);self.owner=parent;self.setScene(QGraphicsScene(self));self.boxes=[]
        self.setAccessibleName('完整稿件預覽；亦可用相對位置選單操作')
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if not self.sceneRect().isEmpty():self.fitInView(self.sceneRect(),Qt.KeepAspectRatio)
    def show_candidate(self,candidate,*,editable=True):
        from .render import card_view_image
        self.scene().clear();self.boxes=[]
        if candidate is None:return
        image=card_view_image(candidate,120);item=self.scene().addPixmap(QPixmap.fromImage(image))
        item.setScale(candidate.template.width_mm/image.width());item.setZValue(-1)
        movable=set(self.owner.current_policy().get('movable_kinds',('phone','email','line','ig','address')))
        for placed in candidate.items:
            if not editable:break
            if placed.slot.kind not in movable:continue
            box=RelativeBox(placed.slot.id,placed.slot.rect,self);self.scene().addItem(box);self.boxes.append(box)
        self.setSceneRect(0,0,candidate.template.width_mm,candidate.template.height_mm)
        self.fitInView(self.sceneRect(),Qt.KeepAspectRatio)


class DesignLearningDialog(QDialog):
    def __init__(self,window):
        super().__init__(window);self.window=window;self.library=window.library
        self.service_window=window if hasattr(window,'run_job') else getattr(window,'service_window',None)
        self.learning=CrossWorkLearning(self.library);self.sessions=DesignSessions(self.library);self.jobs=DesignJobs(self.library)
        self.font_manager=FontManager(self.library);self.worker=None;self.solve_worker=None;self.session_id=None;self.close_after_worker=False;self.bound_to_main=False
        workspace=self.jobs.store.get('DESIGN_WORKSPACE','desktop')
        if workspace and self.jobs.store.get('DESIGN_SESSION',workspace.get('session_id','')):self.session_id=workspace['session_id']
        self.setWindowTitle('共用設計規則與當次稿件');self.resize(1180,800)
        layout=QVBoxLayout(self);self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText)
        layout.addWidget(self.status);self.tabs=QTabWidget();layout.addWidget(self.tabs,1)
        self._source_tab();self._training_tab();self._draft_tab();self.refresh()
        from .family_workbench import FamilyWorkbench
        self.family_workbench=FamilyWorkbench(self)
        self.tabs.addTab(self.family_workbench,'家族與專業規則')
        self.say('先核對來源字型與文字規則，再學習共用版面。未通過正式資格的規則可建立預覽稿。')

    def say(self,value):self.status.setText(value)
    def attempt(self,action):
        try:return action()
        except (ValueError,OSError,KeyError,TypeError) as error:
            from .production_report import explain_error
            report=explain_error(error);self.say(report['summary']+' '+report['next_step'])
            if hasattr(self,'result_details'):self.result_details.setPlainText(report['details'])
            return None
    def button(self,layout,text,action):
        button=QPushButton(text);button.clicked.connect(lambda:self.attempt(action));layout.addWidget(button);return button
    def page(self,label):
        page=QWidget();layout=QVBoxLayout(page);self.tabs.addTab(page,label);return layout
    def _source_tab(self):
        layout=self.page('來源核對');row=QHBoxLayout();self.source_work=QComboBox();row.addWidget(self.source_work,1)
        self.button(row,'讀取欄位與原稿文字',self.load_source);layout.addLayout(row)
        self.button(layout,'本地來源還原／字型影像診斷',self.open_recovery)
        self.source_fields=QComboBox();layout.addWidget(self.source_fields);self.source_fields.currentIndexChanged.connect(lambda:self.load_source_runs())
        self.source_runs=QComboBox();layout.addWidget(self.source_runs);self.source_fonts=QComboBox();layout.addWidget(self.source_fonts)
        self.source_basis=QLineEdit();self.source_basis.setPlaceholderText('原稿、欄位與字型對應的核對依據');layout.addWidget(self.source_basis)
        self.source_confirm=QCheckBox('已對照原稿，確認這個文字欄與實際字型檔的對應');layout.addWidget(self.source_confirm)
        self.use_visual=QCheckBox('使用已核對的本機影像字型／幾何候選（原生資訊可能未知）');layout.addWidget(self.use_visual)
        self.visual_match_id=None
        self.parameter_space=QComboBox();self.parameter_space.addItem('量測使用原稿座標','SOURCE');self.parameter_space.addItem('量測使用作品座標（含非等比轉換）','WORK');layout.addWidget(self.parameter_space)
        row=QHBoxLayout();self.parameter_review=QCheckBox('字寬與字距已量測');row.addWidget(self.parameter_review)
        self.source_scale=QDoubleSpinBox();self.source_scale.setRange(.05,10);self.source_scale.setValue(1);self.source_scale.setDecimals(4)
        self.source_tracking=QDoubleSpinBox();self.source_tracking.setRange(-99,99);self.source_tracking.setDecimals(4)
        row.addWidget(QLabel('來源水平縮放'));row.addWidget(self.source_scale);row.addWidget(QLabel('來源字距 mm'));row.addWidget(self.source_tracking);layout.addLayout(row)
        row=QHBoxLayout();self.source_word_review=QCheckBox('原稿詞距已另行量測');row.addWidget(self.source_word_review)
        self.source_word_spacing=QDoubleSpinBox();self.source_word_spacing.setRange(-99,99);self.source_word_spacing.setDecimals(4)
        row.addWidget(QLabel('來源詞距 mm'));row.addWidget(self.source_word_spacing);layout.addLayout(row)
        row=QHBoxLayout();self.work_pt_review=QCheckBox('作品座標字級有獨立實測依據');row.addWidget(self.work_pt_review)
        self.work_pt=QDoubleSpinBox();self.work_pt.setRange(1,200);self.work_pt.setValue(10);self.work_pt.setDecimals(4)
        row.addWidget(QLabel('作品字級 pt'));row.addWidget(self.work_pt);layout.addLayout(row)
        row=QHBoxLayout();self.label_mode=QComboBox();self.label_mode.addItems(['原稿欄位沒有固定前綴','資料前有固定前綴'])
        self.label_prefix=QLineEdit();self.label_prefix.setPlaceholderText('例如 TEL：');row.addWidget(self.label_mode);row.addWidget(self.label_prefix);layout.addLayout(row)
        self.source_alignment=QComboBox()
        for label,code in [('來源切齊尚未確認','UNKNOWN'),('來源靠左','left'),('來源置中','center'),('來源靠右','right'),('來源為核准職稱／地址分散','distributed')]:self.source_alignment.addItem(label,code)
        layout.addWidget(self.source_alignment)
        self.button(layout,'保存來源對應',self.bind_source);layout.addStretch()
    def _training_tab(self):
        layout=self.page('學習與版本');self.samples=QTableWidget(0,3);self.samples.setHorizontalHeaderLabels(['已核准作品','集合角色','樣本版本'])
        layout.addWidget(self.samples,1);self.actor=QLineEdit('本機管理者');layout.addWidget(self.actor)
        self.rights_basis=QLineEdit();self.rights_basis.setPlaceholderText('本次跨作品規則學習的用途與授權依據');layout.addWidget(self.rights_basis)
        self.rights=QCheckBox('已核對所選作品允許本機跨作品規則學習；原稿、個資與字型留在本機');layout.addWidget(self.rights)
        row=QHBoxLayout();self.train_button=self.button(row,'建立共用規則候選',self.train)
        self.pause_button=self.button(row,'處理完目前項目後暫停',self.pause);layout.addLayout(row)
        row=QHBoxLayout();self.job_choices=QComboBox();row.addWidget(self.job_choices,1);self.button(row,'接續所選工作',self.resume_job);layout.addLayout(row)
        row=QHBoxLayout();self.models=QComboBox();row.addWidget(self.models,1);self.button(row,'採用所選規則建立預覽',self.activate_preview);self.button(row,'啟用通過驗證的正式規則',self.activate_qualified);layout.addLayout(row)
        self.button(layout,'重新讀取已保存狀態',self.refresh)
    def _draft_tab(self):
        layout=self.page('當次稿件');row=QHBoxLayout();self.session_choices=QComboBox();row.addWidget(self.session_choices,1)
        self.button(row,'接續稿件',self.resume_session);self.new_button=self.button(row,'建立新稿件',self.new_session)
        self.button(row,'使用主視窗已填資料',self.use_main_input);layout.addLayout(row)
        row=QHBoxLayout();self.out_w=QDoubleSpinBox();self.out_h=QDoubleSpinBox()
        for spin,value in ((self.out_w,90),(self.out_h,54)):spin.setRange(1,2000);spin.setValue(value);spin.setSuffix(' mm');row.addWidget(spin)
        self.edit_button=self.button(row,'填資料／改內容',self.edit_data);self.solve_button=self.button(row,'產生完整稿件',self.solve_async)
        self.undo_button=self.button(row,'復原位置調整',lambda:self.undo_layout(background=True));self.redo_button=self.button(row,'重做位置調整',lambda:self.redo_layout(background=True));layout.addLayout(row)
        self.solve_status=QLabel('填好資料後產生稿件；可直接拖動藍框內的聯絡資料調整位置。');self.solve_status.setWordWrap(True);layout.addWidget(self.solve_status)
        self.cancel_solve_button=self.button(layout,'停止這次排版',self.cancel_solve);self.cancel_solve_button.setEnabled(False)
        self.capacity_summary=QLabel();self.capacity_summary.setWordWrap(True);layout.addWidget(self.capacity_summary)
        self.canvas=RelativeCanvas(self);self.canvas.requested.connect(lambda a,r,b:self.attempt(lambda:self.set_relation(a,r,b,background=True)))
        layout.addWidget(self.canvas,1);row=QHBoxLayout();self.subject=QComboBox();self.reference=QComboBox();self.relation=QComboBox()
        for text,code in [('在左側','LEFT_OF'),('在右側','RIGHT_OF'),('在上方','ABOVE'),('在下方','BELOW')]:self.relation.addItem(text,code)
        for widget in (self.subject,self.relation,self.reference):row.addWidget(widget)
        self.button(row,'調整兩欄相對位置',lambda:self.set_relation(self.subject.currentData(),self.relation.currentData(),self.reference.currentData(),background=True));layout.addLayout(row)
        row=QHBoxLayout();self.candidate_choices=QComboBox();row.addWidget(self.candidate_choices,1);self.button(row,'查看這個方案',self.choose_candidate);layout.addLayout(row)
        box=QGroupBox('查看詳細原因（進階）');box.setCheckable(True);box.setChecked(False);box_layout=QVBoxLayout(box)
        self.result_details=QPlainTextEdit();self.result_details.setReadOnly(True);self.result_details.setMaximumHeight(110);self.result_details.hide();box_layout.addWidget(self.result_details);box.toggled.connect(self.result_details.setVisible);layout.addWidget(box)
        row=QHBoxLayout();self.switch_button=self.button(row,'已檢視並採用變更版面',self.review_switch)
        self.confirm_button=self.button(row,'確認目前完整預覽稿',self.confirm_preview)
        self.export_button=self.button(row,'輸出已確認預覽稿',self.export_preview);layout.addLayout(row)
        row=QHBoxLayout();self.formal_button=self.button(row,'核對當次實例並確認正式稿',self.confirm_formal);self.formal_export_button=self.button(row,'正式數位輸出',self.export_formal);layout.addLayout(row)
        row=QHBoxLayout();self.artifacts=QComboBox();row.addWidget(self.artifacts,1);self.button(row,'開啟已保存的相同檔案',self.replay);layout.addLayout(row)

    def source_candidates(self):
        if self.bound_to_main:return self.window.source_candidates()
        if not self.session_id:return []
        try:_,_,candidate=self.sessions.checked_result(self.session_id)
        except ValueError:return []
        return [('這份稿件',candidate)]

    def use_main_input(self):
        from .production_bridge import attach
        if not hasattr(self.window,'input_data'):raise ValueError('請從主視窗的資料輸入入口開啟。')
        attach(self);self.say('已接上主視窗的資料、公司與圖片；請產生稿件。')
    def refresh(self):
        current_model=self.models.currentData();self.models.clear();self.job_choices.clear();self.session_choices.clear();self.source_work.clear()
        samples=[row for row in self.jobs.store.records('SAMPLE',limit=200) if self.jobs.store.sample_state(row['id'])=='APPROVED']
        self.samples.setRowCount(len(samples));self.sample_ids=[]
        for index,sample in enumerate(samples):
            work=self.library.artwork(sample['work_id']);self.sample_ids.append(sample['id']);self.source_work.addItem(work['name'],work['id'])
            self.samples.setItem(index,0,QTableWidgetItem(work['name']));self.samples.setItem(index,2,QTableWidgetItem(str(sample['revision'])))
            combo=QComboBox();combo.addItems(['UNASSIGNED','TRAIN','VALIDATION','HOLDOUT'])
            role=self.jobs.store.get('GROUP_ROLE',sample['pins']['source_hash'])
            if role:combo.setCurrentText(role['role'])
            self.samples.setCellWidget(index,1,combo)
        for model in self.jobs.store.records('DESIGN_MODEL',limit=200):
            self.models.addItem(model['id']+' · '+model['formal_qualification'],model['id'])
        if self.models.findData(current_model)>=0:self.models.setCurrentIndex(self.models.findData(current_model))
        for job in self.jobs.store.records('DESIGN_JOB',limit=200):
            if job['kind']=='TRAIN_SHARED_MODEL' and job['phase']!='COMPLETE':self.job_choices.addItem(job['id']+' · '+self.jobs.state(job['id']),job['id'])
        for session in self.jobs.store.records('DESIGN_SESSION',limit=200):self.session_choices.addItem(session['id']+' · '+session['result_state'],session['id'])
        self.source_fonts.clear()
        for asset in self.library.fonts():self.source_fonts.addItem(' / '.join(asset.get('families',[]))+' · '+asset.get('original_name',''),asset)
        self.load_source();self.refresh_draft()
    def open_recovery(self):
        from .recovery_dialog import RecoveryDialog
        work_id=self.source_work.currentData()
        if not work_id:
            RecoveryDialog(self.window).exec()
            return
        work=self.library.artwork(work_id);source=self.library.source(work['source_id'])
        fact=self.source_fields.currentData();slot_id=fact['slot_id'] if fact else None
        slot=next((row for row in work['payload']['slots'] if row['id']==slot_id),None)
        def accept_candidate(candidate,evidence):
            if self.source_work.currentData()!=work_id or (self.source_fields.currentData() or {}).get('slot_id')!=slot_id:
                raise ValueError('來源欄位已變更，請重新比對')
            asset=self.font_manager.import_font(candidate['face']['path'],True,face_index=candidate['face'].get('face_index',0))
            from .local_font_recovery import LocalFontRecovery
            match=LocalFontRecovery(self.library).record(work_id,slot_id,evidence['crop_rect'],evidence['report'],evidence['candidate_index'],self.actor.text(),True)
            self.visual_match_id=match['id'];self.use_visual.setChecked(False)
            self.source_fonts.addItem(' / '.join(asset['families'])+' · 本機視覺候選',asset);self.source_fonts.setCurrentIndex(self.source_fonts.count()-1)
            payload=work['payload'];sx=payload['work_width']/payload['crop']['w'];sy=payload['work_height']/payload['crop']['h']
            self.parameter_space.setCurrentIndex(self.parameter_space.findData('WORK'))
            if candidate['size_pt'] is not None:self.work_pt.setValue(candidate['size_pt']*sy)
            self.source_scale.setValue(candidate['horizontal_scale']*sx/sy)
            if candidate['size_pt'] is not None:self.source_tracking.setValue(candidate['tracking_em']*candidate['size_pt']*25.4/72*sx)
            self.parameter_review.setChecked(False);self.work_pt_review.setChecked(False);self.source_confirm.setChecked(False)
            self.source_basis.setText('本機影像比對候選，待核對；字面 '+candidate['face_fingerprint'][:16])
        dialog=RecoveryDialog(self.window,source,work=work,field=slot,on_candidate=accept_candidate)
        if fact:dialog.text.setText(fact.get('text',''))
        dialog.exec()

    def load_source(self):
        self.source_fields.clear();work_id=self.source_work.currentData()
        if not work_id:return
        facts=self.jobs.store.facts(work_id)
        if self.jobs.store.facts_state(work_id)!='CONFIRMED':return
        selected=set(facts['confirmation']['observation_ids'])
        for row in facts['observations']:
            if row['id'] in selected and row.get('slot_id') and row['classification']=='FIELD':
                self.source_fields.addItem(row['text'][:80],row)
        self.load_source_runs()
    def load_source_runs(self):
        self.visual_match_id=None;self.use_visual.setChecked(False)
        self.source_runs.clear();field=self.source_fields.currentData();work_id=self.source_work.currentData()
        if not field or not work_id:return
        original=self.jobs.store._design_observation_document(work_id)['original_text_evidence']
        rows=sorted(original['runs'],key=lambda row:('PDF_GLYPH_RUN' not in row['id'],row['id']))
        match=hashlib.sha256(field['text'].encode()).hexdigest()
        for row in rows:
            if row['text_sha256']!=match:continue
            self.source_runs.addItem(str(row.get('source_locator'))+' · pt='+str(row['source_pt']['value']),row['id'])
    def bind_source(self):
        if not self.source_confirm.isChecked():raise ValueError('請先核對原稿、欄位與字型來源')
        field=self.source_fields.currentData();asset=self.source_fonts.currentData()
        if not field or not asset or not self.source_runs.currentData():raise ValueError('尚無可明確對應的欄位、原稿文字或字型')
        label=dict(status='CONFIRMED',kind='DYNAMIC_PREFIX' if self.label_mode.currentIndex() else 'NO_FIXED_LABEL',
                   evidence_refs=[self.source_basis.text()])
        if self.label_mode.currentIndex():label['prefix']=self.label_prefix.text()
        review=dict(source_identity_confirmed=True,basis=self.source_basis.text(),label_binding=label,source_alignment=self.source_alignment.currentData())
        if self.source_alignment.currentData()=='distributed':review['source_distribution']=dict(approved=True,actor=self.actor.text(),reason=self.source_basis.text())
        parameter_prefix='work_' if self.parameter_space.currentData()=='WORK' else ''
        if self.parameter_review.isChecked():
            review.update({parameter_prefix+'horizontal_scale':self.source_scale.value(),parameter_prefix+'tracking':self.source_tracking.value(),
                'parameter_measurement_refs':[self.source_basis.text()]})
        if self.source_word_review.isChecked():review.update({parameter_prefix+'word_spacing':self.source_word_spacing.value(),'parameter_measurement_refs':[self.source_basis.text()]})
        if self.work_pt_review.isChecked():review.update(physical_work_pt=self.work_pt.value(),physical_work_measurement_refs=[self.source_basis.text()])
        service=SourceTypographyReview(self.library)
        if self.use_visual.isChecked():
            review['visual_geometry_confirmed']=True
            plan=service.plan_visual(self.source_work.currentData(),field['slot_id'],self.visual_match_id,asset,review)
        else:plan=service.plan(self.source_work.currentData(),field['slot_id'],self.source_runs.currentData(),asset,review)
        service.confirm(plan,self.actor.text(),True)
        self.say('已保存原稿對應；目前觀察仍不等於跨作品規則已通過驗證。')
    def train(self):
        if not self.rights.isChecked():raise ValueError('請核對本次跨作品規則學習用途')
        roles={sid:self.samples.cellWidget(i,1).currentText() for i,sid in enumerate(self.sample_ids)
               if self.samples.cellWidget(i,1).currentText()!='UNASSIGNED'}
        permission=dict(use=USE,actor=self.actor.text(),basis=self.rights_basis.text())
        dataset=self.learning.freeze_dataset(self.learning.dataset_plan(roles,permission),self.actor.text(),True)
        job=self.jobs.create('TRAIN_SHARED_MODEL',dict(dataset_id=dataset['id'],items=[dict(dataset_id=dataset['id'])]),self.actor.text(),True)
        self.start_job(job)
    def start_job(self,job):
        if self.worker and self.worker.isRunning():raise ValueError('目前已有學習工作')
        claimed=self.jobs.claim(job['id'],job['revision']);self.worker=DesignWorker(self.library.root,job['id'],claimed['owner']['token'],self)
        self.worker.progress.connect(lambda row:self.say(f"已保存 {row['done']} / {row['total']} 個工作項目"))
        self.worker.completed.connect(lambda row:self.say('已完成候選學習；請檢視後採用預覽規則。' if row['phase']=='COMPLETE' else '已暫停；可從保存位置接續。'))
        self.worker.failed.connect(self.say);self.worker.finished.connect(self.worker_finished);self.train_button.setEnabled(False);self.worker.start()
    def worker_finished(self):
        self.train_button.setEnabled(True);self.refresh()
        if self.close_after_worker:self.close()
    def pause(self):
        if self.worker and self.worker.isRunning():self.worker.cancel.set();self.say('將在完整處理完目前項目後暫停。')
    def resume_job(self):
        identity=self.job_choices.currentData()
        if not identity:raise ValueError('沒有待接續的學習工作')
        self.start_job(self.jobs.current(identity))
    def activate_preview(self):
        identity=self.models.currentData()
        if not identity:raise ValueError('先建立共用規則候選')
        active=self.jobs.store.get('DESIGN_ACTIVE','local-layout')
        policy=dict(version='desktop-preview-1',basis='本機管理者檢視共用候選後採用預覽',production=False,enable_joint_prediction=True)
        self.learning.activate(identity,active['revision'] if active else 0,self.actor.text(),policy,True)
        self.say('已採用預覽規則；既有定稿與已確認輸出保持原版本。');self.tabs.setCurrentIndex(2)
    def activate_qualified(self):
        identity=self.models.currentData()
        model,_=self.learning.checked_model(identity)
        from .design_qualification import validate_certificate
        certificate=validate_certificate(self.library,model)
        policy=dict(certificate['plan']['layout_policy'],production=True,basis='本機管理者採用已驗證正式規則')
        active=self.jobs.store.get('DESIGN_ACTIVE','local-layout')
        self.learning.activate(identity,active['revision'] if active else 0,self.actor.text(),policy,True)
        self.say('已採用通過驗證的正式規則；既有稿件保留原版本。')
    def save_workspace(self):
        with self.jobs.store.transaction():
            current=self.jobs.store.get('DESIGN_WORKSPACE','desktop')
            self.jobs.store._write('DESIGN_WORKSPACE','desktop',dict(session_id=self.session_id),
                current['revision'] if current else 0,'desktop_design_workspace_saved')
    def current_policy(self):
        if self.session_id:return self.sessions.current(self.session_id)['policy']
        return {}
    def input_data(self):
        if self.session_id:return InputGraph(self.sessions.current(self.session_id)['input_graph']).compile(self.library.logos())
        return [dict(name='')],[],{}
    def new_session(self):
        if self.solve_worker and self.solve_worker.isRunning():raise ValueError('請先停止目前排版，再建立新稿件。')
        from .input_graph_dialog import InputGraphDialog
        dialog=InputGraphDialog(self,InputGraph.from_legacy([dict(name='')],[]).data)
        if dialog.exec()!=QDialog.Accepted:return
        saved=self.sessions.create(dialog.graph,self.out_w.value(),self.out_h.value(),self.actor.text())
        self.session_id=saved['id'];self.save_workspace()
        from .production_bridge import sync_input
        if self.bound_to_main:
            self.window.reorder_customer_snapshot=None;self.window.reorder_template_id=None
        sync_input(self,dialog.graph)
        if self.bound_to_main:self.window.production_session_id=saved['id']
        self.refresh();self.say('資料已保存；可以產生完整稿件。')
    def resume_session(self):
        identity=self.session_choices.currentData()
        if not identity:raise ValueError('沒有已保存稿件')
        self.session_id=identity;self.save_workspace();row=self.sessions.current(identity)
        if self.bound_to_main:
            self.window.reorder_customer_snapshot=None;self.window.reorder_template_id=None
            self.window.out_w.setValue(row['width_mm']);self.window.out_h.setValue(row['height_mm'])
            from .production_bridge import sync_input
            sync_input(self,InputGraph(row['input_graph']));self.window.production_session_id=identity
        self.out_w.setValue(row['width_mm']);self.out_h.setValue(row['height_mm']);self.refresh_draft()
    def edit_data(self):
        if self.solve_worker and self.solve_worker.isRunning():raise ValueError('請先停止目前排版，再改資料。')
        if not self.session_id:return self.new_session()
        from .input_graph_dialog import InputGraphDialog
        current=self.sessions.current(self.session_id);self.out_w.setValue(current['width_mm']);self.out_h.setValue(current['height_mm']);dialog=InputGraphDialog(self,current['input_graph'])
        if dialog.exec()!=QDialog.Accepted:return
        self.sessions.replace_input(current['id'],current['revision'],new_id(),dialog.graph);self.refresh_draft()
        from .production_bridge import sync_input
        sync_input(self,dialog.graph)
        self.say('更正資料已保存；原相對位置意圖保留，請重新產生稿件。')
    def solve(self):
        if not self.session_id:raise ValueError('請先建立或接續稿件')
        row=self.sessions.current(self.session_id);result=self.sessions.solve(row['id'],row['revision']);self.refresh_draft()
        self.say('已產生完整預覽稿；請檢視後確認。' if result['selected'] else '目前規則或來源資料不足，尚無可完整承接這筆資料的稿件。')

    def solve_async(self):
        if not self.session_id:raise ValueError('請先填資料，再產生稿件。')
        if self.solve_worker and self.solve_worker.isRunning():return
        runtime=getattr(self.window,'runtime',None)
        if runtime:
            decision=runtime.admit('GEOMETRY',foreground=True)
            if not decision.allowed:
                self.solve_status.setText('電腦目前較忙，這次尚未開始排版；資料已保留，稍後可重試。');return
        row=self.sessions.current(self.session_id)
        self.last_solve_error=None
        self.solve_worker=DraftSolveWorker(self.library.root,row['id'],row['revision'],self)
        self.solve_worker.completed.connect(self.solve_completed);self.solve_worker.failed.connect(self.solve_failed)
        self.solve_worker.progress.connect(lambda value:self.solve_status.setText(f"正在比較可用版面：{value['done']+1}／{value['total']}。資料仍保留，可停止。"))
        self.solve_worker.finished.connect(self.solve_finished)
        self.set_solving(True);self.solve_status.setText('正在依文字、尺寸與圖片產生稿件…')
        try:self.solve_worker.start()
        except BaseException:self.set_solving(False);raise

    def set_solving(self,running):
        for button in (self.new_button,self.edit_button,self.solve_button,self.undo_button,self.redo_button):button.setEnabled(not running)
        self.canvas.setEnabled(not running);self.cancel_solve_button.setEnabled(running)
        if self.bound_to_main:self.window.busy=running
        if running:
            for button in (self.confirm_button,self.export_button,self.formal_button,self.formal_export_button):button.setEnabled(False)

    def cancel_solve(self):
        if self.solve_worker and self.solve_worker.isRunning():
            self.solve_worker.cancel.set();self.solve_status.setText('正在停止；處理完目前項目後返回，資料不會遺失。')

    def solve_completed(self,result):
        if not self.session_id or result['session_id']!=self.session_id:return
        self.refresh_draft()
        self.say('稿件已更新，請檢視後確認。' if result['selected'] else '尚未找到合適稿件；請展開詳細原因。')

    def solve_failed(self,error):
        self.last_solve_error=error
        self.refresh_draft()
        from .production_report import explain_error
        report=explain_error(error);self.solve_status.setText(report['summary']+' '+report['next_step']);self.result_details.setPlainText(report['details'])

    def solve_finished(self):
        self.set_solving(False);self.refresh_draft()
        if getattr(self,'last_solve_error',None):
            from .production_report import explain_error
            report=explain_error(self.last_solve_error);self.solve_status.setText(report['summary']+' '+report['next_step']);self.result_details.setPlainText(report['details'])
        if self.close_after_worker:self.close()

    def set_relation(self,subject,relation,reference,*,background=False):
        if self.solve_worker and self.solve_worker.isRunning():raise ValueError('目前正在排版，請稍候或先停止。')
        if not self.session_id or not subject or not reference or subject==reference:raise ValueError('請選擇兩個不同欄位')
        row=self.sessions.current(self.session_id);self.sessions.set_relation(row['id'],row['revision'],new_id(),subject,relation,reference)
        self.refresh_draft();self.solve_async() if background else self.solve()
    def undo_layout(self,*,background=False):
        if not self.session_id:return
        row=self.sessions.current(self.session_id);self.sessions.undo_layout(row['id'],row['revision'],new_id())
        self.refresh_draft();self.solve_async() if background else self.solve()
    def redo_layout(self,*,background=False):
        if not self.session_id:return
        row=self.sessions.current(self.session_id);self.sessions.redo_layout(row['id'],row['revision'],new_id())
        self.refresh_draft();self.solve_async() if background else self.solve()

    def choose_candidate(self):
        if self.solve_worker and self.solve_worker.isRunning():raise ValueError('請等待目前排版完成。')
        if not self.session_id:return
        row=self.sessions.current(self.session_id);self.sessions.select_candidate(row['id'],row['revision'],self.candidate_choices.currentIndex());self.refresh_draft()
    def refresh_draft(self):
        self.subject.clear();self.reference.clear();self.artifacts.clear();self.candidate_choices.clear();candidate=None;current=None;result=None;accepted=None;self.matching_accepted_id=None
        if self.session_id:
            current=self.sessions.current(self.session_id)
            index=self.session_choices.findData(self.session_id)
            if index<0:self.session_choices.addItem('',self.session_id);index=self.session_choices.count()-1
            states={'CURRENT':'稿件已更新','STALE':'資料已改，需重新排版','NEEDS_SOLVE':'待排版'}
            self.session_choices.setItemText(index,'目前稿件 · '+states.get(current['result_state'],'待核對'))
            self.session_choices.setCurrentIndex(index)
            graph=InputGraph(current['input_graph']);movable=set(current['policy'].get('movable_kinds',('phone','email','line','ig','address')))
            for field in input_facts(graph):
                from .model import KINDS
                label=graph.label(field['entity_id'])+'／'+KINDS.get(field['kind'],field['kind'])+'／'+field['value'][:35]
                self.reference.addItem(label,field['render_id'])
                if field['kind'] in movable:self.subject.addItem(label,field['render_id'])
            try:_,result,candidate=self.sessions.checked_result(self.session_id)
            except ValueError:pass
            for index,choice in enumerate(result.get('choices',[]) if result else []):
                self.candidate_choices.addItem(('建議方案' if index==0 else '其他方案 '+str(index+1))+' · '+str(len(choice['serialized']['items']))+'項資料',index)
                if result['selected']['id']==choice['id']:self.candidate_choices.setCurrentIndex(index)
            for artifact in self.jobs.store.records('DESIGN_ACCEPTED_ARTIFACT',limit=200):
                if artifact['session_id']==self.session_id:self.artifacts.addItem(artifact['path'],artifact['id'])
            try:
                accepted=self.sessions.find_accepted(graph,current['width_mm'],current['height_mm'],current['intents'],production=current['policy'].get('production') is True)
                if accepted and self.artifacts.findData(accepted['id'])<0:self.artifacts.insertItem(0,'可沿用的已確認稿：'+accepted['path'],accepted['id'])
                if accepted:self.artifacts.setCurrentIndex(self.artifacts.findData(accepted['id']))
                if accepted:self.matching_accepted_id=accepted['id']
            except ValueError as error:self.solve_status.setText('先前確認稿目前不能沿用；請查看原因。'+str(error))
            from .production_report import result_report,explain_error
            try:
                report=result_report(self.library,current,result,candidate)
                self.solve_status.setText(report['summary']+' '+report['next_step']);self.capacity_summary.setText(report['capacity_summary']);self.result_details.setPlainText(report['details'])
            except (ValueError,KeyError) as error:
                self.capacity_summary.setText('目前無法核對學習建議；正式輸出不因此放寬。');self.result_details.setPlainText(explain_error(error)['details'])
        self.switch_button.setVisible(bool(current and current.get('result_id') and self.jobs.store.get('DESIGN_RESULT',current['result_id']).get('family_switch_requires_review')))
        qualified_model=self.jobs.store.get('DESIGN_MODEL',current['model_id']) if current else None
        self.formal_button.setEnabled(bool(candidate and qualified_model and qualified_model.get('formal_qualification')=='PASS'
            and current['policy'].get('production') is True and candidate.risk_context.get('design_size_admission')=='SOURCE_OR_LEARNED_DOMAIN'))
        self.formal_export_button.setEnabled(bool(candidate and current and (current.get('confirmation') or {}).get('for_production') and candidate.formal_eligible))
        self.formal_button.setToolTip('需要真實作品驗證及正式模型資格；尺寸須有來源或學習範圍支持')
        if candidate is None and accepted and accepted.get('accepted_candidate'):
            from .design_session import _candidate
            self.canvas.show_candidate(_candidate(accepted['accepted_candidate']),editable=False)
            self.solve_status.setText('已找到相同資料的確認稿。可直接「開啟已保存的相同檔案」沿用；如要重新排版，請明確按產生稿件。')
        else:self.canvas.show_candidate(candidate)
        self.confirm_button.setEnabled(candidate is not None)
        self.export_button.setEnabled(candidate is not None and bool(current and current.get('confirmation')))
        self.out_w.setEnabled(True);self.out_h.setEnabled(True)
        if current:
            # A saved draft has pinned dimensions. Change size in the main
            # production entry, or before creating a new standalone draft.
            self.out_w.setValue(current['width_mm']);self.out_h.setValue(current['height_mm'])
            self.out_w.setEnabled(False);self.out_h.setEnabled(False)
        from .production_bridge import publish_preview
        publish_preview(self)
    def review_switch(self):
        row=self.sessions.current(self.session_id);self.sessions.review_family_switch(row['id'],row['revision'],self.actor.text())
        self.say('已保存對目前變更版面的明確採用。')
    def confirm_formal(self):
        row=self.sessions.current(self.session_id);self.sessions.qualify_result(row['id'],row['revision'],self.actor.text())
        self.refresh_draft();row=self.sessions.current(self.session_id)
        self.sessions.confirm(row['id'],row['revision'],self.actor.text(),for_production=True)
        self.refresh_draft();self.say('已核對並確認目前正式數位稿；輸出仍會再次核驗資產與格式。')
    def export_formal(self):
        path,_=QFileDialog.getSaveFileName(self,'保存已確認正式數位稿','design.png','PNG (*.png);;PDF (*.pdf);;JPG (*.jpg)')
        if not path:return
        artifact=self.sessions.export(self.session_id,path,preview=False);self.refresh_draft();self.say('已保存正式數位檔與原版本憑證：'+artifact['path'])
    def confirm_preview(self):
        row=self.sessions.current(self.session_id);self.sessions.confirm(row['id'],row['revision'],self.actor.text());self.refresh_draft();self.say('已確認目前顯示的完整預覽稿。')
    def export_preview(self):
        path,_=QFileDialog.getSaveFileName(self,'保存已確認預覽稿','PREVIEW-design.png','PNG (*.png);;PDF (*.pdf);;JPG (*.jpg)')
        if not path:return
        artifact=self.sessions.export(self.session_id,path,preview=True);self.refresh_draft();self.say('已保存相同稿件的檔案與完整性憑證：'+artifact['path'])
    def replay(self):
        identity=self.artifacts.currentData()
        if not identity:raise ValueError('尚無已確認並保存的檔案')
        artifact=self.sessions.replay_artifact(identity)
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(artifact['path']))
    def closeEvent(self,event):
        if hasattr(self,'family_workbench') and not self.family_workbench.request_close():
            event.ignore();return
        if self.worker and self.worker.isRunning():
            self.close_after_worker=True;self.pause();event.ignore();return
        if self.solve_worker and self.solve_worker.isRunning():
            self.close_after_worker=True;self.cancel_solve();event.ignore();return
        self.font_manager.close();event.accept()

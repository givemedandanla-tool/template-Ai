"""Professional source correspondence form using the existing review engine.

All controls describe inspected source facts. They are never customer typography
controls, and a default spin-box value is not submitted without explicit review.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gui import MainWindow
from copy import deepcopy
from pathlib import Path
import hashlib

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QCheckBox, QLineEdit, QDoubleSpinBox, QSpinBox, QPlainTextEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QLabel, QTabWidget, QWidget,
    QFileDialog, QDialogButtonBox, QScrollArea)

from .design_source_binding import SourceTypographyReview
from .training_store import digest
from .background import file_digest


def number(low, high, value=0., decimals=4):
    widget=QDoubleSpinBox();widget.setRange(low,high);widget.setDecimals(decimals);widget.setValue(value)
    return widget


class FamilySourceDialog(QDialog):
    def __init__(self, window, work_id, parent=None):
        super().__init__(parent or window)
        self.host_window: MainWindow=window;self.library=window.library;self.work_id=work_id
        self.reviewer=SourceTypographyReview(self.library);self.store=self.reviewer.store
        self.spans=[];self.plan=None;self.icon_asset=None
        self.setWindowTitle('專業來源文字／複合字面核對');self.resize(1000,780)
        layout=QVBoxLayout(self);self.status=QLabel('先看原稿與完整文字，再確認來源對應；未核對的數值保持未知。')
        self.status.setWordWrap(True);self.status.setTextFormat(Qt.PlainText);layout.addWidget(self.status)
        bar=QHBoxLayout();self.slots=QComboBox();bar.addWidget(self.slots)
        self.button(bar,'以原稿標記工具對照',self.open_annotation);layout.addLayout(bar)
        self.tabs=QTabWidget();layout.addWidget(self.tabs,1)
        self.build_runs();self.build_flow();self.build_components()
        review=QFormLayout();self.actor=QLineEdit('本機來源核對者');self.basis=QLineEdit()
        review.addRow('核對者',self.actor);review.addRow('實際檢視／量測依據',self.basis);layout.addLayout(review)
        self.confirmed=QCheckBox('已核對來源字型身分、完整文字、歸屬、標籤與圖示');layout.addWidget(self.confirmed)
        self.preview=QPlainTextEdit();self.preview.setReadOnly(True);self.preview.setMaximumHeight(125);layout.addWidget(self.preview)
        buttons=QHBoxLayout();self.button(buttons,'產生對應預檢',self.prepare)
        self.button(buttons,'明確保存已核對對應',self.commit);layout.addLayout(buttons)
        close=QDialogButtonBox(QDialogButtonBox.Close);close.rejected.connect(self.reject);layout.addWidget(close)
        work=self.library.artwork(work_id)
        for slot in work['payload']['slots']:
            if slot['kind']!='logo':self.slots.addItem(slot['kind']+' · '+slot['owner'],slot)
        document=self.store._design_observation_document(work_id)
        self.runs=document.get('original_text_evidence',{}).get('runs',[])
        for i,run in enumerate(self.runs):
            point=run.get('source_pt',{}).get('value')
            label=run['id'][:24]+' · '+str(run.get('decoded_character_count','未知'))+' 字 · 原生pt '+(f'{point:g}' if type(point) in (float,int) else '未知')
            self.run_choice.addItem(label,i);self.label_run.addItem(label,i)
        self.run_choice.currentIndexChanged.connect(self.suggest_range)
        for asset in self.library.fonts():
            label=' / '.join(asset.get('families',[]))+' · '+asset['hash'][:10]
            self.font_input.addItem(label,asset);self.label_font.addItem(label,asset)
        self.slots.currentIndexChanged.connect(self.load_slot);self.load_slot()

    def button(self,layout,label,action):
        button=QPushButton(label);button.clicked.connect(lambda checked=False:self.attempt(action));layout.addWidget(button);return button

    def attempt(self,action):
        try:return action()
        except Exception as error:self.status.setText(str(error));return None

    def tab(self,name):
        widget=QWidget();layout=QVBoxLayout(widget);scroll=QScrollArea();scroll.setWidgetResizable(True)
        scroll.setWidget(widget);self.tabs.addTab(scroll,name);return layout

    def build_runs(self):
        layout=self.tab('完整文字與來源 run')
        self.field_text=QPlainTextEdit();self.field_text.setReadOnly(True);self.field_text.setMaximumHeight(85);layout.addWidget(self.field_text)
        form=QFormLayout();self.run_choice=QComboBox();self.font_input=QComboBox();self.font_input.addItem('請選擇實際本地字型',None)
        self.start=QSpinBox();self.end=QSpinBox()
        for widget in (self.start,self.end):widget.setRange(0,100000)
        form.addRow('來源文字 run',self.run_choice);form.addRow('字型檔與字面',self.font_input)
        form.addRow('在完整文字中的起點',self.start);form.addRow('終點（不包含）',self.end);layout.addLayout(form)
        metrics=QHBoxLayout();self.metrics=QCheckBox('字寬與字距有獨立量測');metrics.addWidget(self.metrics)
        self.scale=number(.05,10,1);self.tracking=number(-99,99)
        self.scale.setEnabled(False);self.tracking.setEnabled(False)
        self.metrics.toggled.connect(self.scale.setEnabled);self.metrics.toggled.connect(self.tracking.setEnabled)
        metrics.addWidget(QLabel('水平比例'));metrics.addWidget(self.scale);metrics.addWidget(QLabel('字距 mm'));metrics.addWidget(self.tracking);layout.addLayout(metrics)
        word=QHBoxLayout();self.word_review=QCheckBox('原稿詞距已量測');self.word=number(-99,99)
        word.addWidget(self.word_review);word.addWidget(self.word);layout.addLayout(word)
        self.word.setEnabled(False);self.word_review.toggled.connect(self.word.setEnabled)
        work=QHBoxLayout();self.work_pt_review=QCheckBox('非等比來源的作品字級有獨立量測');self.work_pt=number(1,200,10)
        work.addWidget(self.work_pt_review);work.addWidget(self.work_pt);layout.addLayout(work)
        self.work_pt.setEnabled(False);self.work_pt_review.toggled.connect(self.work_pt.setEnabled)
        self.spans_table=QTableWidget(0,5);self.spans_table.setHorizontalHeaderLabels(['來源run','起點','終點','字型','量測狀態'])
        layout.addWidget(self.spans_table,1)
        row=QHBoxLayout();self.button(row,'加入所選完整／分段來源',self.add_span)
        self.button(row,'移除所選分段',self.remove_span);self.button(row,'清除分段',self.clear_spans);layout.addLayout(row)
        self.alignment=QComboBox()
        for label,value in [('切齊尚未確認','UNKNOWN'),('靠左','left'),('置中','center'),('靠右','right')]:self.alignment.addItem(label,value)
        layout.addWidget(self.alignment)
        self.container_review=QCheckBox('已核對跨作品容器對應');self.container=QLineEdit()
        self.container.setPlaceholderText('已確認的共用容器識別，例如 p1-contact-left')
        layout.addWidget(self.container_review);layout.addWidget(self.container)
        self.label_kind=QComboBox()
        for label,value in [('標籤尚未確認',None),('沒有固定標籤','NO_FIXED_LABEL'),('固定前綴','DYNAMIC_PREFIX'),('獨立固定標籤','SEPARATE_STATIC_LABEL')]:self.label_kind.addItem(label,value)
        self.prefix=QLineEdit();self.prefix.setPlaceholderText('固定前綴（來源確實存在時）');layout.addWidget(self.label_kind);layout.addWidget(self.prefix)

    def build_flow(self):
        layout=self.tab('來源換行與分散')
        self.flow_review=QCheckBox('已從來源核對以下完整文字流規則');layout.addWidget(self.flow_review)
        form=QFormLayout();self.break_rule=QComboBox()
        for label,value in [('不換行','NO_WRAP'),('詞邊界換行','WORD_WRAP'),('詞或字元群換行','WORD_OR_ANYWHERE')]:self.break_rule.addItem(label,value)
        self.max_lines=QSpinBox();self.max_lines.setRange(1,16);self.leading=number(.5,3,1)
        self.flow_align=QComboBox()
        for value in ['left','center','right','justify']:self.flow_align.addItem(value,value)
        self.spacing_mode=QComboBox()
        for label,value in [('間距未另行核對',None),('詞邊界','WORDS'),('塑形字元群邊界','CHARACTERS')]:self.spacing_mode.addItem(label,value)
        self.spacing_value=number(0,2);self.maximum_gap=number(0,2,.5)
        self.last_line=QComboBox();self.last_line.addItems(['NATURAL','DISTRIBUTE'])
        for label,widget in [('換行',self.break_rule),('已觀察最大行數',self.max_lines),('行高比例',self.leading),
            ('切齊',self.flow_align),('分散邊界',self.spacing_mode),('已量測間距 mm',self.spacing_value),
            ('單邊額外間距上限 mm',self.maximum_gap),('末行',self.last_line)]:form.addRow(label,widget)
        layout.addLayout(form);layout.addStretch()

    def build_components(self):
        layout=self.tab('固定標籤／欄位圖示')
        self.presentation_review=QCheckBox('已核對固定部分、動態值框及其相對位置');layout.addWidget(self.presentation_review)
        form=QFormLayout();self.label_run=QComboBox();self.label_run.addItem('無獨立固定文字',None)
        self.label_font=QComboBox();self.label_font.addItem('固定文字的實際字型',None)
        self.label_text=QLineEdit()
        self.label_pt=number(1,200,10);self.label_measured=QCheckBox('固定文字作品字級已獨立量測')
        self.label_pt.setEnabled(False);self.label_measured.toggled.connect(self.label_pt.setEnabled)
        form.addRow('固定文字來源',self.label_run);form.addRow('固定文字字型',self.label_font)
        form.addRow('固定文字（須與來源run完全相符）',self.label_text)
        form.addRow('固定文字字級 pt',self.label_pt);form.addRow(self.label_measured)
        self.frames={}
        for name,label,default in [('value','動態值框',[.2,0,.8,1]),('label','固定文字框',[0,0,.18,1]),('icon','欄位圖示框',[0,0,.15,1])]:
            row=QHBoxLayout();self.frames[name]=[number(0,1,v) for v in default]
            for widget in self.frames[name]:row.addWidget(widget)
            form.addRow(label+' x/y/w/h 比例',row)
        layout.addLayout(form);self.icon_text=QLabel('未選擇欄位圖示');layout.addWidget(self.icon_text)
        self.button(layout,'選擇純向量欄位圖示',self.choose_icon)
        self.icon_rights=QCheckBox('已核對此欄位圖示的列印使用權');layout.addWidget(self.icon_rights)
        layout.addWidget(QLabel('此處只處理欄位裝飾圖示；完整公司 Logo 使用既有 Logo 庫。'));layout.addStretch()

    def load_slot(self):
        slot=self.slots.currentData()
        self.plan=None;self.preview.clear();self.confirmed.setChecked(False);self.clear_spans()
        if not slot:return
        facts=self.store.facts(self.work_id)
        rows=[r for r in facts.get('observations',[]) if r.get('slot_id')==slot['id'] and r.get('classification')=='FIELD']
        value=rows[0].get('text','') if len(rows)==1 else ''
        self.field_text.setPlainText(value);self.end.setValue(len(value))
        self.start.setMaximum(len(value));self.end.setMaximum(len(value))
        for control in (self.metrics,self.word_review,self.work_pt_review,self.flow_review,self.presentation_review,self.container_review):
            control.setChecked(False)
        self.label_measured.setChecked(False);self.icon_rights.setChecked(False);self.label_text.clear()
        self.font_input.setCurrentIndex(0);self.label_font.setCurrentIndex(0);self.label_kind.setCurrentIndex(0)
        self.container.clear();self.prefix.clear();self.icon_asset=None;self.suggest_range()

    def suggest_range(self):
        selected=self.run_choice.currentData()
        if selected is not None:
            length=self.runs[selected].get('decoded_character_count')
            if type(length) is int:self.end.setValue(min(len(self.field_text.toPlainText()),self.start.value()+length))

    def measured_review(self):
        result={}
        if any(control.isChecked() for control in (self.metrics,self.word_review,self.work_pt_review)) and not self.basis.text().strip():
            raise ValueError('獨立量測需先填寫實際依據')
        if self.metrics.isChecked():result.update(horizontal_scale=self.scale.value(),tracking=self.tracking.value(),parameter_measurement_refs=[self.basis.text()])
        if self.word_review.isChecked():result.update(word_spacing=self.word.value(),parameter_measurement_refs=[self.basis.text()])
        if self.work_pt_review.isChecked():result.update(work_pt=self.work_pt.value(),physical_work_measurement_refs=[self.basis.text()])
        return result

    def add_span(self):
        selected=self.run_choice.currentData();asset=self.font_input.currentData()
        if selected is None or asset is None:raise ValueError('請選擇實際來源run與本地字型檔')
        start,end=self.start.value(),self.end.value()
        if end<=start:raise ValueError('完整文字分段範圍不合法')
        self.spans.append(dict(source_run_id=self.runs[selected]['id'],start=start,end=end,font_asset=deepcopy(asset),review=self.measured_review()))
        self.start.setValue(end);self.paint_spans();self.plan=None

    def paint_spans(self):
        self.spans_table.setRowCount(len(self.spans))
        for i,span in enumerate(self.spans):
            values=[span['source_run_id'],span['start'],span['end'],','.join(span['font_asset']['families']),
                    '有獨立量測' if span['review'] else '依來源證據；未知不補值']
            for j,value in enumerate(values):self.spans_table.setItem(i,j,QTableWidgetItem(str(value)))

    def remove_span(self):
        index=self.spans_table.currentRow()
        if index>=0:self.spans.pop(index)
        self.paint_spans();self.plan=None

    def clear_spans(self):
        self.spans=[];self.spans_table.setRowCount(0);self.start.setValue(0);self.plan=None

    def choose_icon(self):
        path,_=QFileDialog.getOpenFileName(self,'本地欄位圖示','','SVG (*.svg)')
        if not path:return
        from .design_components import checked_icon
        asset=dict(path=str(Path(path).resolve()),hash=file_digest(path),semantic_scope='DECORATIVE_FIELD_SYMBOL')
        checked_icon(asset);self.icon_asset=asset;self.icon_rights.setChecked(False);self.icon_text.setText(Path(path).name);self.plan=None

    def review(self):
        if not self.confirmed.isChecked() or not self.basis.text().strip():
            raise ValueError('需先明確核對來源身分與實際依據')
        result=dict(source_identity_confirmed=True,basis=self.basis.text(),source_alignment=self.alignment.currentData(),**self.measured_review())
        label=self.label_kind.currentData()
        if label is None:raise ValueError('請確認固定標籤狀態')
        if label=='SEPARATE_STATIC_LABEL' and not self.presentation_review.isChecked():
            raise ValueError('獨立固定標籤需核對固定部分與動態值框')
        result['label_binding']=dict(status='CONFIRMED',kind=label,evidence_refs=[self.basis.text()])
        if label=='DYNAMIC_PREFIX':result['label_binding']['prefix']=self.prefix.text()
        if self.container_review.isChecked():
            if not self.container.text().strip():raise ValueError('共用容器識別不可為空')
            result['container_binding']=dict(status='CONFIRMED',key=self.container.text().strip(),evidence_refs=[self.basis.text()])
        if self.flow_review.isChecked():
            flow=dict(status='HUMAN_CONFIRMED_SOURCE_RULE',evidence_refs=[self.basis.text()],break_rule=self.break_rule.currentData(),
                      max_lines_observed=self.max_lines.value(),line_height_factor=self.leading.value(),alignment=self.flow_align.currentData())
            mode=self.spacing_mode.currentData()
            if mode:
                flow['spacing_rule']=dict(status='HUMAN_CONFIRMED_SOURCE_RULE',evidence_refs=[self.basis.text()],mode=mode,
                    boundary_policy='ASCII_SPACE_QT_WORD_SPACING' if mode=='WORDS' else 'QT_SHAPED_GRAPHEME_TRACKING',
                    justification='WORD_BOUNDARIES_ONLY' if mode=='WORDS' else 'SHAPED_CLUSTER_BOUNDARIES_ONLY',
                    allowed_scripts=['Latn','Hani','Bopo'],value_mm=self.spacing_value.value(),last_line=self.last_line.currentText(),
                    zero_boundaries='KEEP_NATURAL',maximum_extra_gap_mm=self.maximum_gap.value())
            result['source_text_flow']=flow
        return result

    def add_presentation(self,review,base_pt):
        if not self.presentation_review.isChecked():return
        flow=review.setdefault('source_text_flow',dict(status='HUMAN_CONFIRMED_SOURCE_RULE',evidence_refs=[self.basis.text()],
            break_rule='NO_WRAP',max_lines_observed=1,line_height_factor=1.,alignment='left'))
        parts=[];run_index=self.label_run.currentData()
        if run_index is not None:
            if review['label_binding']['kind']!='SEPARATE_STATIC_LABEL':
                raise ValueError('獨立固定文字需選擇獨立固定標籤對應')
            if not self.label_measured.isChecked() or self.label_font.currentData() is None:
                raise ValueError('固定標籤字型與作品字級需獨立核對')
            value=self.label_text.text();run=self.runs[run_index]
            if hashlib.sha256(value.encode()).hexdigest()!=run['text_sha256']:
                raise ValueError('固定文字與所選原生run的完整文字不符')
            parts.append(dict(kind='STATIC_TEXT',text=value,font_asset=self.label_font.currentData(),source_run_id=run['id'],
                physical_pt_measurement_refs=[self.basis.text()],
                pt_ratio=self.label_pt.value()/base_pt,frame=[w.value() for w in self.frames['label']]))
        elif review['label_binding']['kind']=='SEPARATE_STATIC_LABEL':
            raise ValueError('請選擇獨立固定文字的實際來源run')
        if self.icon_asset:
            asset=deepcopy(self.icon_asset)
            asset.update(source_hash=self.library.source(self.library.artwork(self.work_id)['source_id'])['hash'],reviewed_source_association=True)
            if self.icon_rights.isChecked():asset['usage_rights']=dict(print_export=True,actor=self.actor.text(),basis=self.basis.text())
            parts.append(dict(kind='SVG_ICON',asset=asset,frame=[w.value() for w in self.frames['icon']]))
            review['icon_binding']=dict(status='CONFIRMED',evidence_refs=[self.basis.text()],asset=asset)
        presentation=dict(status='HUMAN_CONFIRMED_SOURCE_RULE',evidence_refs=[self.basis.text()],
                          value_frame=[w.value() for w in self.frames['value']],components=parts)
        if run_index is not None:presentation['evidence_refs'].append(self.runs[run_index]['id'])
        from .design_components import validate_presentation
        validate_presentation(presentation);flow['presentation']=presentation

    def make_plan(self,review):
        slot=self.slots.currentData()
        if not slot or not self.spans:raise ValueError('先加入來源對應分段')
        if len(self.spans)>1:return self.reviewer.plan_composite(self.work_id,slot['id'],self.spans,review)
        span=self.spans[0]
        if span['start']!=0 or span['end']!=len(self.field_text.toPlainText()):raise ValueError('單run需完整涵蓋欄位文字')
        return self.reviewer.plan(self.work_id,slot['id'],span['source_run_id'],span['font_asset'],dict(review,**span['review']))

    def prepare(self):
        self.plan=self.assembled_plan()
        typography=self.plan['typography']
        def scalar(key):
            row=typography.get(key) or {};value=row.get('value')
            if value is None:return '未知'
            status={'OBSERVED':'原稿證據','DERIVED':'有依據的推導','UNKNOWN':'未知'}.get(row.get('status'),row.get('status',''))
            return f"{value:g} {row.get('unit','')}（{status}）"
        self.preview.setPlainText('完整文字已核對；分段 '+str(len(self.spans))+'\n作品字級：'+scalar('source_pt')+
            '；原生字級：'+scalar('source_page_pt')+'\n水平比例：'+scalar('horizontal_scale')+'；字距：'+scalar('tracking')+
            '；詞距：'+scalar('word_spacing')+'\n尚未保存；保存時再次核對來源、字型、事實與版本。')
        self.status.setText('預檢通過；請確認後明確保存。')

    def commit(self):
        if not self.plan:raise ValueError('請先產生對應預檢')
        fresh=self.assembled_plan()
        if fresh!=self.plan:raise ValueError('預檢後的選項或來源已改變，請重新預檢')
        saved=self.reviewer.confirm(self.plan,self.actor.text(),True)
        self.status.setText('來源對應已保存 v'+str(saved['revision'])+'；受影響的舊模型需重建，不會被改寫。');self.plan=None

    def assembled_plan(self):
        review=self.review();measurement=deepcopy(review)
        if self.presentation_review.isChecked():
            # Obtain the dynamic run's evidenced base pt before constructing the
            # fixed component ratios. This preliminary plan is never saved.
            measurement['label_binding']=dict(status='CONFIRMED',kind='NO_FIXED_LABEL',evidence_refs=[self.basis.text()])
        first=self.make_plan(measurement)
        self.add_presentation(review,first['typography']['source_pt']['value'])
        return self.make_plan(review)

    def open_annotation(self):
        from .annotation_dialog import AnnotationDialog
        AnnotationDialog(self.host_window,self.work_id,self).exec()

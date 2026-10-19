"""Expert local recovery diagnostics; share only an explicit content-free view."""
from copy import deepcopy
import json
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QTextEdit, QVBoxLayout)

from .background import file_digest
from .recovery_diagnostics import issue, shareable_report, export_shareable


class RecoveryWorker(QThread):
    result=Signal(object)

    def __init__(self, operation, parent=None):
        super().__init__(parent);self.operation=operation

    def run(self):
        try:self.result.emit(dict(value=self.operation(self)))
        except Exception as error:self.result.emit(dict(error=str(error),report=getattr(error,'recovery_report',None)))


class RecoveryDialog(QDialog):
    def __init__(self, window, source=None, *, work=None, field=None,on_candidate=None):
        super().__init__(window);self.window=window;self.worker=None;self.source=deepcopy(source)
        self.report=deepcopy((source or {}).get('recovery',{}));self.last_match=None;self.faces=[];self.offset=0;self.match_pages=[]
        self.on_candidate=on_candidate
        self.setWindowTitle('本地來源還原與字型影像診斷');self.resize(1000,820)
        layout=QVBoxLayout(self)
        label=QLabel('原稿、影像、字型與辨識內容只在本機處理。外觀候選需核對；不自動修改模板或訓練真值。')
        label.setWordWrap(True);layout.addWidget(label)
        row=QHBoxLayout();self.path=QLineEdit((source or {}).get('current_path',''));row.addWidget(self.path)
        self.add_button(row,'選擇本機作品',self.choose_source);self.add_button(row,'重新分析還原',self.import_source);layout.addLayout(row)
        self.preview=QLabel();self.preview.setAlignment(Qt.AlignCenter);self.preview.setMinimumHeight(180);layout.addWidget(self.preview)
        row=QHBoxLayout();self.crop_controls=[]
        for label in ('左 px','上 px','寬 px','高 px'):
            row.addWidget(QLabel(label));box=QSpinBox();box.setRange(0,20000);row.addWidget(box);self.crop_controls.append(box)
        layout.addLayout(row)
        self.text=QLineEdit();self.text.setPlaceholderText('此裁切區的完整單行文字，可手動核對或由本機 OCR 取得');layout.addWidget(self.text)
        self.ocr_language=QComboBox();self.ocr_language.addItem('繁體中文與英文 OCR',['chi_tra','eng']);self.ocr_language.addItem('英文 OCR',['eng']);layout.addWidget(self.ocr_language)
        self.verified=QCheckBox('已核對裁切區的完整文字（仍需另外核對字型候選）');layout.addWidget(self.verified)
        row=QHBoxLayout();self.add_button(row,'盤點 Windows 本機字型',self.scan_fonts)
        self.add_button(row,'選擇本機字型檔',self.choose_fonts);self.add_button(row,'本機 OCR',self.ocr)
        self.add_button(row,'比較本批字型',self.match);self.add_button(row,'下一批字型',self.next_page);layout.addLayout(row)
        self.local=QTextEdit();self.local.setReadOnly(True);layout.addWidget(self.local)
        row=QHBoxLayout();self.candidate_choices=QComboBox();row.addWidget(self.candidate_choices)
        draft=self.add_button(row,'將候選加入來源核對草稿（不授予印製權）',self.use_candidate);draft.setEnabled(on_candidate is not None);layout.addLayout(row)
        self.public=QTextEdit();self.public.setReadOnly(True);layout.addWidget(QLabel('以下為可分享診斷預覽，不含原稿文字、路徑、字型名、圖片或原稿雜湊：'));layout.addWidget(self.public)
        row=QHBoxLayout();self.add_button(row,'匯出上述診斷 JSON',self.export)
        self.add_button(row,'取消目前工作',self.cancel);self.add_button(row,'關閉',self.close);layout.addLayout(row)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        if source:self.show_source(source,work,field)
        self.show_report()

    def add_button(self,layout,label,operation):
        button=QPushButton(label);button.clicked.connect(lambda:self.attempt(operation));layout.addWidget(button)
        return button

    def attempt(self,operation):
        try:operation()
        except Exception as error:self.status.setText(str(error))

    def start(self,operation,done):
        if self.worker and self.worker.isRunning():raise ValueError('目前本機工作尚未完成，可先取消。')
        worker=RecoveryWorker(operation,self);self.worker=worker
        def receive(value):
            if 'error' in value:
                self.status.setText(value['error'])
                if value.get('report'):self.report=value['report'];self.show_report()
            else:done(value['value'])
        worker.result.connect(receive)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(lambda:setattr(self,'worker',None))
        worker.start();self.status.setText('本機處理中；關閉前會等待工作結束。')

    def choose_source(self):
        path,_=QFileDialog.getOpenFileName(self,'選擇本機作品','','作品 (*.ai *.pdf *.svg *.eps *.png *.jpg *.jpeg)')
        if path:self.path.setText(path)

    def import_source(self):
        from .importer import import_file
        path=self.path.text();assets=self.window.library.assets
        self.start(lambda worker:dict(import_file(path,assets),current_path=path),self.show_source)

    def show_source(self,source,work=None,field=None):
        self.source=deepcopy(source);self.report=deepcopy(source.get('recovery',{}));self.last_match=None
        image=QImage(source['image'])
        if image.isNull():raise ValueError('本機來源預覽不可用')
        self.preview.setPixmap(QPixmap.fromImage(image).scaled(920,220,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        x=y=0;w=image.width();h=image.height()
        if work and field:
            payload=work['payload'];crop=payload['crop'];r=field['rect']
            sx=image.width()/source['width_mm'];sy=image.height()/source['height_mm']
            x=round((crop['x']+r['x']*crop['w']/payload['work_width'])*sx)
            y=round((crop['y']+r['y']*crop['h']/payload['work_height'])*sy)
            w=round(r['w']*crop['w']/payload['work_width']*sx);h=round(r['h']*crop['h']/payload['work_height']*sy)
        for box,value in zip(self.crop_controls,(x,y,w,h)):box.setValue(value)
        self.show_report();self.status.setText('已讀取本機還原診斷；請裁切單一文字區後比對。')

    def crop(self):
        if not self.source:raise ValueError('請先讀取作品')
        image=QImage(self.source['image']);x,y,w,h=[box.value() for box in self.crop_controls]
        if min(w,h)<=0 or x+w>image.width() or y+h>image.height():raise ValueError('裁切區超出來源影像')
        return image.copy(x,y,w,h)

    def scan_fonts(self):
        from .windows_font_sources import windows_font_sources_all
        from .visual_font_match import registered_faces
        def done(report):
            self.faces=registered_faces(report);self.offset=0
            self.catalog_complete=report.get('status')=='COMPLETE'
            self.status.setText(f'已核對 {len(self.faces)} 個本機字面；來源完整性：'+report['status'])
        self.start(lambda worker:windows_font_sources_all(cancelled=worker.isInterruptionRequested),done)

    def choose_fonts(self):
        from .font_evidence import inspect_font
        paths,_=QFileDialog.getOpenFileNames(self,'選擇本機字型','','字型 (*.ttf *.otf *.ttc)')
        if not paths:return
        def scan(worker):
            faces=[]
            for path in paths:
                if worker.isInterruptionRequested():break
                proof=inspect_font(path)
                faces.extend(dict(path=path,sha256=proof['hash'],face_index=f['index']) for f in proof['faces'])
            return faces
        def done(faces):self.faces=faces;self.offset=0;self.catalog_complete=True;self.status.setText(f'已核對所選 {len(faces)} 個字面。')
        self.start(scan,done)

    def ocr(self):
        from .quality_ocr import freeze
        from .visual_font_match import ocr_text_candidates
        crop=self.crop();assets=self.window.library.assets;languages=self.ocr_language.currentData()
        def run(worker):return ocr_text_candidates(crop,freeze(assets,dict(languages=languages,psm=6)))
        def done(rows):
            self.verified.setChecked(False)
            if len(rows)==1:self.text.setText(rows[0]['text'])
            self.report.setdefault('issues',[]).append(issue('OCR_REVIEW_REQUIRED'));self.show_report()
            self.status.setText('OCR 完成；'+('請核對此行完整文字。' if len(rows)==1 else '未取得唯一文字行，請縮小裁切區。'))
        self.start(run,done)

    def match(self,reset=True):
        from .visual_font_match import match_fonts,merge_font_pages
        if not self.faces:raise ValueError('請先盤點或選擇本機字型檔')
        if reset:self.offset=0;self.match_pages=[]
        crop=self.crop();texts=[dict(text=self.text.text(),origin='REVIEWED_TEXT' if self.verified.isChecked() else 'UNREVIEWED_TEXT')]
        faces=deepcopy(self.faces);offset=self.offset
        ppm=QImage(self.source['image']).width()/self.source['width_mm'] if self.source.get('calibrated') else None
        def done(result):
            self.match_pages.append(result);result=merge_font_pages(self.match_pages)
            self.last_match=result;self.report['font_match_status']=result['font_match_status']
            self.report['issues']=[r for r in self.report.get('issues',[]) if r['stage'] not in ('FONT','BUDGET','OCR')]+result['issues']
            if not getattr(self,'catalog_complete',False):self.report['issues'].append(issue('SEARCH_INCOMPLETE'))
            self.report.setdefault('counts',{}).update(checked_faces=result['checked_faces'],omitted_faces=result['omitted_faces'])
            self.local.setPlainText(json.dumps(result,ensure_ascii=False,indent=2));self.show_report()
            self.candidate_choices.clear()
            for candidate in result['candidates']:self.candidate_choices.addItem(candidate['family']+' / '+candidate['style']+' · '+format(candidate['score'],'.4f'),candidate)
            self.status.setText('本批比對：'+result['status']+'；屬視覺候選，核對後才可作來源依據。')
        self.start(lambda worker:match_fonts(crop,texts,faces,pixels_per_mm=ppm,max_faces=64,offset=offset,
            cancelled=worker.isInterruptionRequested),done)

    def next_page(self):
        if not self.last_match:raise ValueError('請先完成本批比對')
        self.offset=self.last_match['next_offset']
        if self.offset>=len(self.faces):raise ValueError('所選字型批次已完成；可擴充候選來源。')
        self.match(reset=False)

    def show_report(self):self.public.setPlainText(json.dumps(shareable_report(self.report),ensure_ascii=False,indent=2))

    def use_candidate(self):
        if not self.on_candidate or not self.candidate_choices.currentData():raise ValueError('請先選擇本機比對候選')
        if self.worker and self.worker.isRunning():raise ValueError('請等待目前工作結束')
        self.on_candidate(deepcopy(self.candidate_choices.currentData()),dict(report=deepcopy(self.last_match),
            candidate_index=self.candidate_choices.currentIndex(),crop_rect=[box.value() for box in self.crop_controls]))
        self.status.setText('已帶回來源核對草稿；請核對來源、參數與完整文字後明確確認。')

    def export(self):
        target,_=QFileDialog.getSaveFileName(self,'匯出已預覽的無內容診斷','','JSON (*.json)')
        if target:export_shareable(self.report,target);self.status.setText('已保存診斷；由你自行決定分享，程式未上傳。')

    def cancel(self):
        if self.worker:self.worker.requestInterruption();self.status.setText('已要求取消；目前轉換階段完成或逾時後停止。')

    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():self.cancel();event.ignore();return
        event.accept()

    def reject(self):
        if self.worker and self.worker.isRunning():self.cancel();return
        super().reject()

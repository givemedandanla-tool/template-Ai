"""逐欄審核／有界背景驗證／明確新草稿交易／持久Undo與Redo。"""
import copy
import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox,QDialog,QDialogButtonBox,QHBoxLayout,QLabel,QLineEdit,
    QMessageBox,QPushButton,QScrollArea,QTableWidget,QTableWidgetItem,QVBoxLayout)

from .font_catalog import build_inventory
from .font_candidates import render_candidate
from .font_review import FontReviewEngine,SCOPE,field_key,fingerprint


class FontReviewDialog(QDialog):
    def __init__(self,window,target=None,seed_text="",parent=None):
        super().__init__(parent or window)
        self.window=window;self.target=copy.deepcopy(target);self.busy=False;self.generation=0
        self.report=None;self.rows=[];self.approved=set();self.preview_data=None
        if not hasattr(window,'font_review_engine'):window.font_review_engine=FontReviewEngine()
        self.engine=window.font_review_engine
        self.setWindowTitle('字型替代影響審核 · 新草稿與歷史復原');self.resize(1320,920)
        layout=QVBoxLayout(self)
        self.title=QLabel(('目標：'+' / '.join(target.get('families',[])) if target else '歷史管理；新替代請由核准候選進入')+'。'+SCOPE)
        self.title.setTextFormat(Qt.PlainText);self.title.setWordWrap(True);layout.addWidget(self.title)
        toolbar=QHBoxLayout()
        self.seed=QLineEdit(seed_text);self.seed.setMaxLength(4096);self.seed.setPlaceholderText('僅填到明確選取欄位的匿名驗證文字');toolbar.addWidget(self.seed,1)
        self.fill_button=QPushButton('將文字填入所選一欄');self.fill_button.clicked.connect(self.fill_selected);toolbar.addWidget(self.fill_button)
        self.check_button=QPushButton('背景驗證逐欄差異');self.check_button.clicked.connect(self.validate);self.check_button.setEnabled(target is not None);toolbar.addWidget(self.check_button)
        self.refresh_button=QPushButton('重新載入影響範圍');self.refresh_button.clicked.connect(self.reload);toolbar.addWidget(self.refresh_button)
        layout.addLayout(toolbar)
        self.status=QLabel('所有欄位預設不選、不核准；驗證文字不持久保存。')
        self.status.setTextFormat(Qt.PlainText);self.status.setWordWrap(True);layout.addWidget(self.status)
        self.summary=QLabel('影響最多200欄／每輪量測20欄；不同本機字型64 MiB大小預算。只改明確選取的新草稿。')
        self.summary.setTextFormat(Qt.PlainText);self.summary.setWordWrap(True);layout.addWidget(self.summary)
        self.table=QTableWidget(0,7);self.table.setHorizontalHeaderLabels(['勾選','模板／版次／來源','人物公司／欄位／框位','此欄臨時驗證文字','原字型 → 目標款式','風險／驗證','尺寸差異與原因'])
        self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.itemSelectionChanged.connect(self.selection_changed);layout.addWidget(self.table,3)
        actions=QHBoxLayout()
        self.review_button=QPushButton('詳審所選欄差異與預覽');self.review_button.clicked.connect(self.review_selected);self.review_button.setEnabled(False);actions.addWidget(self.review_button)
        self.apply_button=QPushButton('核對勾選範圍並建立新草稿');self.apply_button.clicked.connect(self.apply_selected);self.apply_button.setEnabled(False);actions.addWidget(self.apply_button)
        layout.addLayout(actions)
        self.preview=QLabel('需先驗證，才可查看候選實際字形預覽。');self.preview.setTextFormat(Qt.PlainText);self.preview.setAlignment(Qt.AlignCenter)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(self.preview);scroll.setMinimumHeight(95);layout.addWidget(scroll,1)
        self.details=QLabel(SCOPE);self.details.setTextFormat(Qt.PlainText);self.details.setWordWrap(True);self.details.setTextInteractionFlags(Qt.TextSelectableByMouse);layout.addWidget(self.details)
        self.history=QTableWidget(0,3);self.history.setHorizontalHeaderLabels(['歷史階段／批次','本批新草稿與文字框','驗證及隱私限制'])
        self.history.setEditTriggers(QTableWidget.NoEditTriggers);self.history.setSelectionBehavior(QTableWidget.SelectRows);self.history.setSelectionMode(QTableWidget.SingleSelection)
        self.history.itemSelectionChanged.connect(self.history_selection);layout.addWidget(self.history,1)
        history_actions=QHBoxLayout()
        self.undo_button=QPushButton('復原所選批次草稿字型');self.undo_button.clicked.connect(lambda:self.history_action('UNDO'));history_actions.addWidget(self.undo_button)
        self.redo_button=QPushButton('重新核對並重做此批次');self.redo_button.clicked.connect(lambda:self.history_action('REDO'));history_actions.addWidget(self.redo_button)
        close=QDialogButtonBox(QDialogButtonBox.Close);close.button(QDialogButtonBox.Close).setText('關閉');close.rejected.connect(self.reject);history_actions.addWidget(close);layout.addLayout(history_actions)
        self.reload()

    def clean_editor(self):
        t=self.window.template
        if t and t.state=='draft':
            saved=next((s['template'] for s in self.window.library.template_snapshots() if s['template']['id']==t.id),None)
            from .model import Template
            if saved and fingerprint(Template.from_dict(saved).to_dict())!=fingerprint(t.to_dict()):
                self.status.setText('主工作台有未保存編輯；請先保存或放棄，再進行替代／復原。');return False
        return True

    def invalidate(self,*_):
        self.generation+=1;self.report=None;self.approved.clear();self.preview_data=None
        self.preview.clear();self.preview.setText('輸入已變更，舊核准與預覽失效；請重新驗證。')
        for i in range(self.table.rowCount()):
            checkbox=self.table.cellWidget(i,0)
            if checkbox:checkbox.setChecked(False);checkbox.setEnabled(False)
        self.apply_button.setEnabled(False);self.review_button.setEnabled(False)
        self.status.setText('驗證文字或條件變更，核准及勾選已清除。')

    def reload(self,force=False):
        if self.busy and not force:return
        self.snapshots=self.window.library.template_snapshots();self.invalidate();self.rows=[]
        for snapshot in self.snapshots:
            t=snapshot['template']
            for slot in t['slots']:
                if slot['kind']=='logo':continue
                self.rows.append({'key':field_key(t['id'],slot['id']),'template':t,'slot':slot})
        self.all_count=len(self.rows);self.rows=self.rows[:200]
        self.table.blockSignals(True);self.table.setRowCount(len(self.rows))
        for i,row in enumerate(self.rows):
            t,s=row['template'],row['slot'];box=s['rect']
            checkbox=QCheckBox();checkbox.setChecked(False);checkbox.setEnabled(False);self.table.setCellWidget(i,0,checkbox)
            edit=QLineEdit();edit.setMaxLength(4096);edit.textChanged.connect(self.invalidate);self.table.setCellWidget(i,3,edit)
            texts={1:f"{t['name']} v{t['version']}（{t['state']}）\n{t['width_mm']:g}×{t['height_mm']:g} mm\n來源作品 {t.get('source_work_id') or '未知'}／{t.get('source_work_revision',0)}",
                   2:f"{s['owner']}／{s['kind']}／{s['id']}\n({box['x']:g},{box['y']:g}) {box['w']:g}×{box['h']:g} mm · {s['size_pt']:g} pt",
                   4:f"{s['font']} / {s.get('font_style') or '預設／待核驗'}",5:'未核驗',6:'未提供本欄文字；原稿身份／字寬差異未知'}
            for col,value in texts.items():item=QTableWidgetItem(value);item.setToolTip(value);self.table.setItem(i,col,item)
        self.table.blockSignals(False)
        for col,width in enumerate((45,250,245,200,200,115,390)):self.table.setColumnWidth(col,width)
        self.table.resizeRowsToContents();self.table.clearSelection()
        self.summary.setText(f'展示 {len(self.rows)}／{self.all_count} 個文字欄位；超額範圍不自動套用。每輪最多量測20欄，64 MiB不同資產大小。')
        self.refresh_history()

    def selected_index(self):
        rows=self.table.selectionModel().selectedRows();return rows[0].row() if rows else None

    def selection_changed(self):
        i=self.selected_index();self.review_button.setEnabled(bool(self.report and i is not None and self.report['rows'][i]['eligible']) and not self.busy)

    def fill_selected(self):
        i=self.selected_index()
        if i is not None and not self.busy:self.table.cellWidget(i,3).setText(self.seed.text())

    def start(self,message,work,done,allow_input=True):
        if self.busy or self.window.busy:return
        generation=self.generation;self.busy=True;self.status.setText(message)
        for b in (self.check_button,self.refresh_button,self.fill_button,self.apply_button,self.review_button,self.undo_button,self.redo_button):b.setEnabled(False)
        self.table.setEnabled(allow_input);self.history.setEnabled(False)
        def guarded():
            try:return {'value':work()}
            except Exception as error:return {'error':str(error)}
        def finished(payload):
            try:
                if generation!=self.generation:self.status.setText('背景期間輸入改變，結果過期；請重新驗證。')
                elif 'error' in payload:self.status.setText('未完成：'+payload['error']+'；可重新核對。')
                else:done(payload['value'])
            except Exception as error:self.status.setText('未提交／處理失敗：'+str(error))
            finally:
                self.busy=False;self.table.setEnabled(True);self.history.setEnabled(True)
                self.check_button.setEnabled(self.target is not None);self.refresh_button.setEnabled(True);self.fill_button.setEnabled(True)
                self.apply_button.setEnabled(self.report is not None);self.selection_changed();self.history_selection()
        try:self.window.run_job(message,guarded,finished)
        except Exception:
            finished({'error':'背景工作未啟動'});raise

    def validate(self):
        if not self.target or self.busy:return
        self.snapshots=self.window.library.template_snapshots()
        texts={row['key']:self.table.cellWidget(i,3).text() for i,row in enumerate(self.rows)}
        self.invalidate()
        self.start('背景核對每欄固定字級、字形、毫米差異與高度',lambda:self.engine.analyze(self.snapshots,self.target,texts),self.show_report)

    def show_report(self,report):
        if [r['key'] for r in report['rows']]!=[r['key'] for r in self.rows]:
            self.status.setText('模板範圍已變更，請重新載入影響範圍。');return
        self.report=report
        for i,row in enumerate(report['rows']):
            box=self.table.cellWidget(i,0);box.setChecked(False);box.setEnabled(row['eligible'] and row['risk']=='LOW')
            a,o=row['proposed'],row['original']
            fmt=lambda n:'未知' if n is None else f'{n:.4f} mm'
            details='；'.join(row['reasons'])
            if a:
                details=f"原寬 {fmt(o.get('width_mm') if o and o.get('measurement_verified') else None)} → 候選 {fmt(a['width_mm'])}；候選高 {fmt(a.get('height_mm'))}；水平 {a['scale']*100:.3f}%\n"+details if a['scale'] is not None else details
            for col,value in ((4,row['before']['font']+' / '+(row['before']['font_style'] or '預設')+' → '+(a.get('family','未知')+' / '+a.get('style','未知') if a else '未核驗')),(5,row['risk']+' · '+('待逐欄核准' if row['risk']=='HIGH' else '不合格' if not row['eligible'] else '可勾選')),(6,details)):
                item=QTableWidgetItem(value);item.setToolTip(value);self.table.setItem(i,col,item)
        self.table.resizeRowsToContents()
        self.summary.setText(f"{'部分核驗' if report['status']=='PARTIAL' else '本輪核驗完成'}：{report['checked_fields']}欄，未展示{report['omitted_rows']}；不同資產 {report['bytes_budgeted']} bytes。HIGH須逐欄詳審；不宣稱原稿／輸出合格。")
        self.status.setText('差異已列出，所有欄位仍未勾選；高風險需詳審後才可勾選。')

    def review_selected(self):
        i=self.selected_index()
        if self.busy or not self.report or i is None:return
        row=copy.deepcopy(self.report['rows'][i])
        if not row['eligible']:return
        text=self.table.cellWidget(i,3).text();s=row['slot']
        inputs={'text':text,'size_pt':s['size_pt'],'width_mm':s['rect']['w'],'min_scale':s['min_scale']}
        candidate={'row':self.report['target'],'analysis':row['proposed'],'requested_style':row['proposed']['style'],'input':inputs}
        def show(result):
            pixmap=QPixmap();pixmap.loadFromData(result['png'],'PNG');self.preview.setPixmap(pixmap);self.preview_data=result
            self.details.setText(f"{row['template_name']} v{row['version']}／{s['owner']}／{s['kind']}／{s['id']}\n"+self.table.item(i,6).text()+'\n'+SCOPE)
            if QMessageBox.question(self,'逐欄核准草稿字型替代',self.details.text()+'\n核准僅此欄進入勾選候選；不等於正式輸出／原稿一致。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
                self.approved.add(row['key']);self.table.cellWidget(i,0).setEnabled(True);self.table.item(i,5).setText(row['risk']+' · 已逐欄核准，尚未勾選')
        self.start('重新核對所選欄候選字面，建立人工詳審預覽',lambda:render_candidate(candidate,inputs),show,allow_input=False)

    def apply_selected(self):
        if self.busy or not self.report or not self.clean_editor():return
        selected=[{'key':r['key'],'reviewed':r['key'] in self.approved} for i,r in enumerate(self.report['rows']) if self.table.cellWidget(i,0).isChecked()]
        if not selected:self.status.setText('尚未勾選欄位，沒有修改。');return
        keys={s['key'] for s in selected};summary='\n'.join(f"{r['template_name']} v{r['version']}／{r['slot']['owner']}／{r['slot']['kind']}／{r['slot_id']} → {r['after']['font']} / {r['after']['font_style']}" for r in self.report['rows'] if r['key'] in keys)
        if QMessageBox.question(self,'確認選取範圍與新草稿',summary+'\n僅上述欄位建立新版本草稿；原版本保留，版次在交易內分配。不發布或核准正式輸出。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        def apply(token):
            record=self.engine.commit(self.window.library,token,confirmed=True)
            self.after_commit(record);self.reload(force=True);self.status.setText(f"已原子建立 {len(record['drafts'])} 份新版本草稿；可在下方歷史復原。原版本未改。")
        self.start('背景重新驗證全部勾選欄位，再提交草稿交易',lambda:self.engine.prepare_apply(self.report['review_id'],selected),apply,allow_input=False)

    def after_commit(self,record):
        self.window.template=None
        self.window.refresh_templates(record['drafts'][0]['template_id']);self.window.invalidate()

    def refresh_history(self):
        self.records=self.window.library.font_change_history();self.history.setRowCount(len(self.records))
        for i,record in enumerate(self.records):
            scope='\n'.join(f"v{d['version']} · {d['template_id']} · {len(d['fields'])}欄" for d in record['drafts'])
            for j,value in enumerate((record['phase']+' / '+record['id'],scope,'驗證文字僅存hash；Redo沿用歷史樣本核驗並重新檢查目標bytes；正式輸出另驗')):
                self.history.setItem(i,j,QTableWidgetItem(value))
        for j,w in enumerate((300,440,520)):self.history.setColumnWidth(j,w)
        self.history.resizeRowsToContents();self.history.clearSelection();self.history_selection()

    def history_selected(self):
        selected=self.history.selectionModel().selectedRows();return self.records[selected[0].row()] if selected else None

    def history_selection(self):
        row=self.history_selected();self.undo_button.setEnabled(bool(row and row['phase']=='APPLIED') and not self.busy)
        self.redo_button.setEnabled(bool(row and row['phase']=='UNDONE') and not self.busy)

    def history_action(self,action):
        record=self.history_selected()
        if self.busy or not record or not self.clean_editor():return
        if QMessageBox.question(self,'確認歷史草稿'+('復原' if action=='UNDO' else '重做'),
                record['id']+'\n僅此批次草稿；後續編輯或發布時拒絕。原字型可能仍失聯，仍須正式輸出重新驗證。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        def commit(token):
            result=self.engine.commit(self.window.library,token,confirmed=True);self.after_commit(result);self.reload(force=True)
            self.status.setText('本批草稿已'+('復原' if action=='UNDO' else '重做')+'；正式輸出與原稿一致仍未核准。')
        self.start('背景核對歷史字型與範圍，提交'+action,lambda:self.engine.prepare_history(record,action),commit,allow_input=False)

    def reject(self):
        if self.busy:self.status.setText('背景核對中，請完成後關閉。');return
        super().reject()

    def closeEvent(self,event):
        if self.busy:event.ignore()
        else:event.accept()

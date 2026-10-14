"""Actual stored traces versus fresh decisions, with source/work navigation and bounded counts."""
import json
from collections import Counter
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QPlainTextEdit
from .training_store import TrainingStore
from .training_navigation import locate_work


class NoiseHitsPanel(QWidget):
    def __init__(self,window,parent=None):
        super().__init__(parent);self.window=window;self.store=TrainingStore(window.library);self.rows=[];self.offset=0;self.loading=False;outer=QVBoxLayout(self);bar=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('全命中完整文字／work／observation／rule ID搜尋');self.search.textChanged.connect(self.search_changed);bar.addWidget(self.search,1);self.reload_button=QPushButton('重查目前決定');self.reload_button.clicked.connect(self.reload);bar.addWidget(self.reload_button);outer.addLayout(bar)
        self.status=QLabel('新確認觀察對合法已核准條件自動評估，不重問規則批准。儲存命中與目前決定分開。');self.status.setWordWrap(True);outer.addWidget(self.status);self.count=QLabel();self.count.setWordWrap(True);outer.addWidget(self.count)
        self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(['目前決定','保存決定／版次','完整文字','作品','規則／版本','觀察ID']);self.table.setEditTriggers(QTableWidget.NoEditTriggers);self.table.setSelectionBehavior(QTableWidget.SelectRows);self.table.setSelectionMode(QTableWidget.SingleSelection);self.table.itemSelectionChanged.connect(self.selected);outer.addWidget(self.table,2);self.details=QPlainTextEdit();self.details.setReadOnly(True);outer.addWidget(self.details,2)
        bar=QHBoxLayout();self.previous_button=QPushButton('上一頁');self.next_button=QPushButton('下一頁');self.locate_button=QPushButton('定位exact來源／作品');self.refresh_button=QPushButton('保存選中作品的目前追溯');self.previous_button.clicked.connect(lambda:self.page(-200));self.next_button.clicked.connect(lambda:self.page(200));self.locate_button.clicked.connect(self.locate);self.refresh_button.clicked.connect(self.refresh)
        for b in (self.previous_button,self.next_button,self.locate_button,self.refresh_button):bar.addWidget(b)
        outer.addLayout(bar);self.reload()
        bar=QHBoxLayout();self.actor=QLineEdit();self.actor.setPlaceholderText('恢復／白名單提出者（本機）');self.actor.setMaxLength(120);bar.addWidget(self.actor);self.keep_button=QPushButton('不是雜訊：只保留此項');self.whitelist_button=QPushButton('保留並建立待審白名單');self.keep_button.clicked.connect(self.keep);self.whitelist_button.clicked.connect(self.whitelist);bar.addWidget(self.keep_button);bar.addWidget(self.whitelist_button);outer.addLayout(bar);self.selected()
    def search_changed(self,*_):self.offset=0;self.reload()
    def page(self,delta):self.offset=max(0,self.offset+delta);self.reload()
    def selected_row(self):
        rows=self.table.selectionModel().selectedRows();return self.rows[rows[0].row()] if rows and rows[0].row()<len(self.rows) else None
    def reload(self,*_):
        if self.loading:return
        self.loading=True
        try:
            where=['kind=?'];args=['HIT']
            for token in self.search.text().casefold().split():where.append("training_casefold(payload||id) LIKE ? ESCAPE '\\'");args.append('%'+token.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%')
            condition=' AND '.join(where);total=self.store.db.execute('SELECT count(*) FROM training_records WHERE '+condition,args).fetchone()[0];ids=[r[0] for r in self.store.db.execute('SELECT id FROM training_records WHERE '+condition+' ORDER BY id LIMIT 200 OFFSET ?',args+[self.offset])];self.rows=[];cache={}
            for rid in ids:
                stored=self.store.get('HIT',rid);wid=stored['work_id']
                if wid not in cache:cache[wid]={r['observation_id']:r for r in self.store.noise_decisions(wid)}
                current=cache[wid].get(stored['observation_id'],{'state':'OBSERVATION_REMOVED','reason':'只保留舊追溯'});self.rows.append({'id':rid,'stored':stored,'current':current,'trace_current':{k:v for k,v in stored.items() if k not in ('id','revision')}==current})
            self.rows.sort(key=lambda r:(r['current']['state'],r['stored']['work_id'],r['stored']['observation_id']));self.table.setRowCount(len(self.rows))
            for i,row in enumerate(self.rows):
                stored=row['stored'];current=row['current'];values=(current['state'],stored['state']+' / r'+str(stored['revision']),stored['text'],stored['work_id'],', '.join(r['id']+' / r'+str(r['revision']) for r in current.get('rule_matches',[])),stored['observation_id'])
                for j,v in enumerate(values):item=QTableWidgetItem(v);item.setToolTip(v);self.table.setItem(i,j,item)
            counts=Counter(r['current']['state'] for r in self.rows);excluded=sum(v for k,v in counts.items() if k.startswith('EXCLUDED'));kept=sum(v for k,v in counts.items() if k.startswith('KEPT') or k=='INCLUDED');self.count.setText(f'本頁目前排除{excluded}／保留{kept}／疑義或歷史{len(self.rows)-excluded-kept}；本頁{len(self.rows)}／搜尋保存記錄{total}／全保存記錄{self.store.count("HIT")}。未掃其他頁，不冒當全庫目前計數。');self.previous_button.setEnabled(self.offset>0);self.next_button.setEnabled(self.offset+len(ids)<total)
        except Exception as error:self.rows=[];self.table.setRowCount(0);self.status.setText('追溯讀取失敗：'+str(error))
        finally:self.loading=False;self.selected()
    def selected(self):
        if self.loading:return
        row=self.selected_row();detail={**row,'history':self.store.history('HIT',row['id'])} if row else {};self.details.setPlainText(json.dumps(detail,ensure_ascii=False,indent=2));self.locate_button.setEnabled(bool(row) and not self.window.busy);self.refresh_button.setEnabled(bool(row) and not self.window.busy)
        if hasattr(self,'keep_button'):self.keep_button.setEnabled(bool(row) and not self.window.busy);self.whitelist_button.setEnabled(bool(row) and not self.window.busy)
    def locate(self):
        try:
            row=self.selected_row()
            if not row:raise ValueError('先選取追溯')
            stored=row['stored'];_,observation=self.store.observation(stored['work_id'],stored['observation_id'],confirmed=False);locate_work(self.window,stored['work_id'],[observation['slot_id']] if observation['slot_id'] else []);self.status.setText('已定位exact作品；輔助觀察区域見詳情，沒有改原稿／欄位')
        except Exception as error:self.status.setText('未定位：'+str(error))
    def refresh(self):
        try:
            row=self.selected_row()
            if not row:raise ValueError('先選取追溯')
            current=row['current'];self.store.refresh_noise(row['stored']['work_id'],current['facts_revision']);self.reload()
        except Exception as error:self.status.setText('未保存追溯：'+str(error));self.selected()

    def keep(self):
        try:
            from PySide6.QtWidgets import QMessageBox
            row=self.selected_row()
            if not row or self.window.busy:raise ValueError('先選取exact觀察，結束背景工作')
            stored=row['stored'];local=self.store.local_record(stored['work_id']);facts=self.store.facts(stored['work_id'])
            if QMessageBox.question(self,'只恢復此觀察',stored['work_id']+'／'+stored['observation_id']+'\n只保留此項，不建立或批准通用白名單。原稿與欄位不改。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
            self.store.local_keep(stored['work_id'],[stored['observation_id']],local['revision'],facts['revision'],True);self.reload()
        except Exception as error:self.status.setText('未恢復：'+str(error));self.selected()

    def whitelist(self):
        try:
            row=self.selected_row()
            if not row or self.window.busy:raise ValueError('先選取exact觀察')
            from .noise_authoring_dialog import NoiseAuthoringDialog
            stored=row['stored'];dialog=NoiseAuthoringDialog(self.store,stored['work_id'],stored['observation_id'],self.actor.text(),self,action='KEEP')
            try:dialog.exec()
            finally:dialog.deleteLater()
            self.reload()
        except Exception as error:self.status.setText('未建立白名單：'+str(error));self.selected()

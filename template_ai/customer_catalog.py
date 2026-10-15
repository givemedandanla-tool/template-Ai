"""Identity confirmed before browsing a customer's exact style links."""
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QDialogButtonBox,QMessageBox
from PySide6.QtCore import Qt
from .catalog_widget import CatalogWidget
from .customers import CustomerStore,digest


def apply_reorder(window,draft):
    from .training_navigation import require_clean_navigation
    from .input_graph import InputGraph
    require_clean_navigation(window)
    if not draft.get('graph'):raise ValueError('客戶歸屬遷移尚待核對，未預填')
    InputGraph.validate(draft['graph'])
    window.out_w.setValue(draft['width_mm']);window.out_h.setValue(draft['height_mm']);window.reorder_template_id=draft['template_id']
    window.adopt_input_graph(draft['graph'],draft['snapshot']);window.invalidate()


class CustomerStyleDialog(QDialog):
    def __init__(self,window,snapshot,parent=None):
        super().__init__(parent or window);self.window=window;self.snapshot=snapshot;self.store=CustomerStore(window.library);self.adopted=False
        self.setWindowTitle('客戶exact尺寸／版型版本：先比較，再確認當次沿用');self.resize(1280,780);layout=QVBoxLayout(self)
        label=QLabel('已確認客戶 '+snapshot['code']+' · '+snapshot['name']+' · ID '+snapshot['id']+' · 主檔 v'+str(snapshot['revision'])+'；原值可能過時，預填後仍需重新排版。');label.setTextFormat(Qt.PlainText);label.setWordWrap(True);layout.addWidget(label)
        self.catalog=CatalogWidget(window,snapshot,self.prefill,False);layout.addWidget(self.catalog,1);buttons=QDialogButtonBox(QDialogButtonBox.Close);buttons.button(QDialogButtonBox.Close).setText('關閉');buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.finished.connect(lambda:self.catalog.close_previews())
    def prefill(self,entry):
        current=self.store.get(self.snapshot['id'])
        if digest(current)!=digest(self.snapshot):raise ValueError('客戶主檔已變，重新核對身份與款式')
        self.check_source_ready(entry)
        draft=self.store.reorder(self.snapshot['id'],entry['link']['id'],True)
        summary='客戶 '+current['code']+'／'+current['name']+'\n確切版型 '+entry['template_id']+' v'+str(entry['version'])+f"\n{entry['width']:g}×{entry['height']:g} mm · {entry['state']}\n"
        from .input_graph import InputGraph
        graph=InputGraph(draft['graph'])
        summary+='人物：'+'／'.join(graph.label(p['id']) for p in graph.data['people'])+'\n公司：'+'／'.join(graph.label(c['id']) for c in graph.data['companies'])
        summary+='\n會替換本次輸入；不改客戶主檔、原稿或已發布模板。缺Logo／來源／字型仍由原Gate阻擋，不代表可正式輸出。'
        if QMessageBox.question(self,'確認exact版型與當次資料替換',summary)!=QMessageBox.Yes:return
        # Recheck after the modal confirmation; another process may have written.
        now=self.store.get(self.snapshot['id'])
        if digest(now)!=digest(self.snapshot):raise ValueError('確認期間主檔已更新，未預填')
        self.check_source_ready(entry)
        draft=self.store.reorder(self.snapshot['id'],entry['link']['id'],True);apply_reorder(self.window,draft);self.adopted=True;self.catalog.status.setText('exact版本已預填本次，主檔未改；請重新排版與逐尺寸驗證')

    def check_source_ready(self,entry):
        if entry['template'].get('source_id'):
            proof=self.catalog.source_results.get(entry['id'])
            if not proof or proof['signature']!=entry['signature'] or proof['result']['status']!='VERIFIED_DERIVATIVE' or not self.catalog.cache_current(proof):
                raise ValueError('來源圖尚未核對／失聯或異動；只供參考，不能直接沿用')

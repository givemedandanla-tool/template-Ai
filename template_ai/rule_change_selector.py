from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QComboBox,QLabel,QPushButton
from .noise_authoring_dialog import NoiseAuthoringDialog


class RuleChangeSelector(QDialog):
    def __init__(self,store,rule_id,actor,reason,parent=None):
        super().__init__(parent);self.store=store;self.rule_id=rule_id;self.actor=actor;self.reason=reason;self.offset=0;self.setWindowTitle('以目前人工觀察建立規則新版本');self.resize(800,260);layout=QVBoxLayout(self);self.status=QLabel('選擇已確認來源文字；舊版將停止，新版仍需原審核中心批准。');self.status.setWordWrap(True);layout.addWidget(self.status);self.work_combo=QComboBox();self.observation_combo=QComboBox();layout.addWidget(self.work_combo);layout.addWidget(self.observation_combo);self.work_combo.currentIndexChanged.connect(self.load_observations);bar=QHBoxLayout();self.previous_button=QPushButton('上一頁作品');self.next_button=QPushButton('下一頁作品');self.previous_button.clicked.connect(lambda:self.page(-200));self.next_button.clicked.connect(lambda:self.page(200));self.open_button=QPushButton('預覽新條件與影響');self.open_button.clicked.connect(self.open);bar.addWidget(self.previous_button);bar.addWidget(self.next_button);bar.addWidget(self.open_button);layout.addLayout(bar);self.reload()
    def page(self,delta):self.offset=max(0,self.offset+delta);self.reload()
    def reload(self):
        self.work_combo.blockSignals(True);self.work_combo.clear()
        for row in self.store.records('FACTS',self.offset):
            if self.store.facts_state(row['id'])=='CONFIRMED':self.work_combo.addItem(self.store.library.artwork(row['id'])['name']+' / '+row['id'],row['id'])
        self.work_combo.blockSignals(False);self.previous_button.setEnabled(self.offset>0);self.next_button.setEnabled(self.offset+200<self.store.count('FACTS'));self.load_observations()
    def load_observations(self,*_):
        self.observation_combo.clear();wid=self.work_combo.currentData()
        if not wid:return
        facts=self.store.facts(wid)
        for row in facts['observations']:
            if row['id'] in facts['confirmation']['observation_ids']:self.observation_combo.addItem(row['text']+' / '+row['classification']+' / '+row['id'],row['id'])
    def open(self):
        try:
            dialog=NoiseAuthoringDialog(self.store,self.work_combo.currentData(),self.observation_combo.currentData(),self.actor,self,replace_rule_id=self.rule_id,reason=self.reason)
            try:
                dialog.exec()
                if dialog.saved_rule:self.accept()
            finally:dialog.deleteLater()
        except Exception as error:self.status.setText('未建立版本：'+str(error))

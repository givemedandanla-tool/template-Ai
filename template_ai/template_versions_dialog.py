import json
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QPushButton,QPlainTextEdit,QMessageBox,QInputDialog
from .template_versions import TemplateVersions,differences


class TemplateVersionsDialog(QDialog):
    def __init__(self,window,parent=None):
        super().__init__(parent or window);self.window=window;self.service=TemplateVersions(window.library);self.setWindowTitle('同一模板的保存版本差異／回退為新草稿');self.resize(1100,780)
        layout=QVBoxLayout(self);self.status=QLabel('比較已保存版本；主畫布未保存內容保留。回退產生同一模板的新版本草稿，正式版仍供原輸出使用。');self.status.setWordWrap(True);layout.addWidget(self.status);bar=QHBoxLayout();self.left=QComboBox();self.right=QComboBox();bar.addWidget(self.left);bar.addWidget(self.right);layout.addLayout(bar)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details,1);button=QPushButton('明確回退左側版本為新草稿');button.clicked.connect(self.restore);layout.addWidget(button)
        family=window.template.family_id
        rows=window.library.db.execute('SELECT id,version,state FROM templates WHERE family_id=? ORDER BY version DESC LIMIT 200',(family,)).fetchall()
        for combo in (self.left,self.right):
            for identity,version,state in rows:combo.addItem(f'v{version}／{state}／{identity}',identity)
        if len(rows)>1:self.right.setCurrentIndex(1)
        self.left.currentIndexChanged.connect(self.compare);self.right.currentIndexChanged.connect(self.compare);self.compare()

    def compare(self,*_):
        if not self.left.currentData() or not self.right.currentData():return
        a=self.window.library.object_snapshot('TEMPLATE',self.left.currentData());b=self.window.library.object_snapshot('TEMPLATE',self.right.currentData());changes=differences(a['payload'],b['payload'])
        self.details.setPlainText(json.dumps(dict(left=dict(id=a['id'],revision=a['revision'],version=a['payload']['version'],state=a['payload']['state']),right=dict(id=b['id'],revision=b['revision'],version=b['payload']['version'],state=b['payload']['state']),changes=changes),ensure_ascii=False,indent=2)+'\n未提供實際人物文字的字形／輸出檢查仍須在實際排版與輸出階段驗證。')

    def restore(self):
        try:
            from .training_navigation import require_clean_navigation
            require_clean_navigation(self.window);plan=self.service.plan(self.left.currentData());reason,ok=QInputDialog.getText(self,'回退理由','保留來源／版次與審核歷史；新草稿仍需驗證及人工發布')
            if not ok:return
            if QMessageBox.question(self,'回退為新版本草稿',self.left.currentText()+f"\n將建立v{plan['next_version']}，不改其他版本或既有輸出。")!=QMessageBox.Yes:return
            template=self.service.clone(plan,'LOCAL_OPERATOR',reason,True,rollback=True);self.window.refresh_templates(template.id);self.status.setText('已保存回退草稿 '+template.id+'；未發布。')
        except Exception as error:self.status.setText('未回退：'+str(error))

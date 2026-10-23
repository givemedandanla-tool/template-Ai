"""Two pinned family/source views, reusing the existing canvas and source verifier."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gui import MainWindow
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QComboBox,QCheckBox,QDialogButtonBox

from .family_workspace import FamilyWorkspace
from .catalog import preview_request, source_preview
from .object_dialog import ObjectCanvas
from .model import Slot,Rect
from .training_store import digest


class FamilyComparisonDialog(QDialog):
    def __init__(self,window,refs,parent=None):
        super().__init__(parent or window)
        if len(refs)!=2:raise ValueError('Choose exactly two family versions')
        self.host_window: MainWindow=window;self.workspace=FamilyWorkspace(window.library);self.library=window.library
        self.setWindowTitle('兩個家族／版本與來源對照');self.resize(1180,740)
        layout=QVBoxLayout(self);layout.addWidget(QLabel('來源影像與共用規則欄框分開；比較不合併家族，也不授予輸出資格。'))
        self.overlay=QCheckBox('疊加共用規則欄框');layout.addWidget(self.overlay)
        row=QHBoxLayout();layout.addLayout(row,1);self.panes=[]
        for ref in refs:
            _,_,profile=self.workspace.resolve(ref);entries=self.workspace.sources(ref)
            column=QVBoxLayout();row.addLayout(column,1)
            title=QLabel(ref['family_id']+'\n獨立支持 '+str(profile['independent_support']));title.setWordWrap(True);column.addWidget(title)
            choices=QComboBox();column.addWidget(choices)
            for entry in entries:choices.addItem(self.library.artwork(entry['work_id'])['name']+' · '+entry['sample_id'][:10],entry)
            canvas=ObjectCanvas();canvas.readonly=True;canvas.resize_enabled=False;column.addWidget(canvas,1)
            status=QLabel();status.setWordWrap(True);status.setTextFormat(Qt.PlainText);column.addWidget(status)
            pane=dict(ref=ref,profile=profile,choices=choices,canvas=canvas,status=status,result=None)
            self.panes.append(pane)
            choices.currentIndexChanged.connect(lambda index,pane=pane:self.load(pane))
        self.overlay.toggled.connect(lambda checked:[self.load(pane) for pane in self.panes])
        buttons=QDialogButtonBox(QDialogButtonBox.Close);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        for pane in self.panes:self.load(pane)

    def load(self,pane):
        entry=pane['choices'].currentData()
        if not entry:
            pane['status'].setText('無可核對來源');return
        work=self.library.artwork(entry['work_id']);payload=work['payload']
        width,height=payload['work_width'],payload['work_height']
        item=dict(id=pane['ref']['model_id']+':'+entry['sample_id'],reference_state='CURRENT',
            signature=digest([pane['ref'],entry]),width=width,height=height,
            template=dict(source_id=work['source_id'],source_work_id=work['id'],
                          source_work_revision=entry['pins']['work_revision'],artwork=payload['crop']))
        result=source_preview(preview_request(self.library,item));pane['result']=result
        slots=[]
        if self.overlay.isChecked():
            for role in pane['profile']['roles']:
                f=role['frame_centre'];slots.append(Slot(role['kind'],role['owner_port'],Rect(f[0]*width,f[1]*height,f[2]*width,f[3]*height),id=role['key']))
        pane['canvas'].set_content(width,height,image=result['image'],slots=slots);pane['canvas'].fit()
        pane['status'].setText(f"{width:g} × {height:g} mm；"+result['status']+'；'+result.get('reason','來源參考'))

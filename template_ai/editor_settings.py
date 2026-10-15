"""Shared view defaults in existing preferences; no customer/work-session save."""
import json
import math
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QLabel,QCheckBox,QDoubleSpinBox,QDialogButtonBox

DEFAULTS=dict(snap_enabled=False,guides_enabled=True,safety_visible=True,resize_enabled=True,nudge_mm=.1)


def validate(value):
    if not isinstance(value,dict) or set(value)!=set(DEFAULTS) or any(type(value[k]) is not bool for k in DEFAULTS if k!='nudge_mm') or type(value['nudge_mm']) not in (float,int) or not math.isfinite(value['nudge_mm']) or not .01<=value['nudge_mm']<=10:raise ValueError('畫布預設設定不合法')
    return dict(value)


def load(library):
    row=library.db.execute("SELECT value FROM preferences WHERE key='editor_view_defaults'").fetchone()
    try:return validate(json.loads(row[0])) if row else dict(DEFAULTS)
    except (ValueError,TypeError):return dict(DEFAULTS)


class EditorSettingsDialog(QDialog):
    def __init__(self,window,parent=None):
        super().__init__(parent or window);self.window=window;self.setWindowTitle('三模式共用畫布設定');layout=QVBoxLayout(self);layout.addWidget(QLabel('僅保存操作輔助預設；不保存未完成客戶工作、修改模板幾何或停用驗證。'));form=QFormLayout();self.fields={};values=load(window.library)
        for key,label in [('snap_enabled','預設吸附'),('guides_enabled','對齊參考線'),('safety_visible','作品邊界疊圖'),('resize_enabled','單框縮放控制點')]:
            checkbox=QCheckBox();checkbox.setChecked(values[key]);self.fields[key]=checkbox;form.addRow(label,checkbox)
        self.step=QDoubleSpinBox();self.step.setDecimals(2);self.step.setRange(.01,10);self.step.setValue(values['nudge_mm']);form.addRow('鍵盤微調毫米（Shift×10）',self.step);layout.addLayout(form);self.status=QLabel();layout.addWidget(self.status);buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);layout.addWidget(buttons)

    def save(self):
        try:
            if self.window.busy:raise ValueError('背景作業中，先保留目前設定')
            value=validate({key:field.isChecked() for key,field in self.fields.items()}|dict(nudge_mm=self.step.value()))
            with self.window.library.db:self.window.library.db.execute("INSERT INTO preferences VALUES('editor_view_defaults',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps(value),))
            from .object_dialog import ObjectCanvas
            for canvas in self.window.findChildren(ObjectCanvas):
                for key,item in value.items():
                    setattr(canvas,key,item);control=getattr(canvas,'preference_widgets',{}).get(key)
                    if control is not None:
                        if isinstance(control,QCheckBox):control.setChecked(item)
                        else:control.setValue(item)
                canvas.viewport().update()
            self.accept()
        except Exception as error:self.status.setText('未保存：'+str(error))

"""Shared view defaults in existing preferences; no customer/work-session save."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .gui import MainWindow
import json
import math
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QDialog,QVBoxLayout,QFormLayout,QLabel,QCheckBox,QDoubleSpinBox,QDialogButtonBox,QKeySequenceEdit

DEFAULTS=dict(snap_enabled=False,guides_enabled=True,safety_visible=True,resize_enabled=True,nudge_mm=.1)
COMMAND_KEYS=dict(UNDO='Ctrl+Z',REDO='Ctrl+Y',DELETE='Del')
# Deliberately bounded research profile, not an OS/IME compatibility assertion.
ALLOWED_KEYS={'Ctrl+Z','Ctrl+Y','Ctrl+Shift+Z','Ctrl+Shift+Y','Ctrl+Shift+U','Ctrl+Shift+D','Ctrl+Shift+R','Del','Backspace','F7','F8','F9'}


def validate_commands(value):
    if not isinstance(value,dict) or set(value)!=set(COMMAND_KEYS):raise ValueError('快捷鍵作用域不合法')
    result={};used=set()
    for command,raw in value.items():
        if not isinstance(raw,str):raise ValueError('快捷鍵必須是文字')
        key=QKeySequence(raw,QKeySequence.PortableText);name=key.toString(QKeySequence.PortableText)
        if raw and (key.count()!=1 or name not in ALLOWED_KEYS):raise ValueError('此鍵位保留給系統／輸入法／文字／既有畫布操作，或尚未支援；未保存。')
        if name and name in used:raise ValueError('同作用域快捷鍵衝突：'+name+'；請明確重新指派，未保存。')
        if name:used.add(name)
        result[command]=name
    return result


def load_commands(library):
    row=library.db.execute("SELECT value FROM preferences WHERE key='canvas_command_bindings'").fetchone()
    try:return validate_commands(json.loads(row[0])) if row else dict(COMMAND_KEYS)
    except (ValueError,TypeError):return dict(COMMAND_KEYS)


def validate(value):
    if not isinstance(value,dict) or set(value)!=set(DEFAULTS) or any(type(value[k]) is not bool for k in DEFAULTS if k!='nudge_mm') or type(value['nudge_mm']) not in (float,int) or not math.isfinite(value['nudge_mm']) or not .01<=value['nudge_mm']<=10:raise ValueError('畫布預設設定不合法')
    return dict(value)


def load(library):
    row=library.db.execute("SELECT value FROM preferences WHERE key='editor_view_defaults'").fetchone()
    try:return validate(json.loads(row[0])) if row else dict(DEFAULTS)
    except (ValueError,TypeError):return dict(DEFAULTS)


class EditorSettingsDialog(QDialog):
    def __init__(self,window,parent=None):
        super().__init__(parent or window);self.host_window: MainWindow=window;self.setWindowTitle('三模式共用畫布設定');layout=QVBoxLayout(self);layout.addWidget(QLabel('僅保存操作輔助預設；不保存未完成客戶工作、修改模板幾何或停用驗證。'));form=QFormLayout();self.fields={};values=load(window.library)
        for key,label in [('snap_enabled','預設吸附'),('guides_enabled','對齊參考線'),('safety_visible','作品邊界疊圖'),('resize_enabled','單框縮放控制點')]:
            checkbox=QCheckBox();checkbox.setChecked(values[key]);self.fields[key]=checkbox;form.addRow(label,checkbox)
        self.step=QDoubleSpinBox();self.step.setDecimals(2);self.step.setRange(.01,10);self.step.setValue(values['nudge_mm']);form.addRow('鍵盤微調毫米（Shift×10）',self.step);layout.addLayout(form);self.status=QLabel();layout.addWidget(self.status);buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        key_form=QFormLayout();self.command_keys={}
        for command,label in [('UNDO','畫布目前工作復原／歷史'),('REDO','畫布目前工作重做／歷史'),('DELETE','刪除候選：先預覽與確認')]:
            editor=QKeySequenceEdit(QKeySequence(load_commands(window.library)[command]));editor.setMaximumSequenceLength(1);self.command_keys[command]=editor;key_form.addRow(label,editor)
        layout.insertLayout(layout.count()-2,key_form)
        note=QLabel('僅作用於聚焦畫布；文字欄仍使用自己的快捷鍵。留空可停用。拒絕衝突／系統與輸入法保留鍵；Windows 實機相容性尚未驗證。\n目前可選：'+'、'.join(sorted(ALLOWED_KEYS)));note.setWordWrap(True);layout.insertWidget(layout.count()-2,note)

    def save(self):
        try:
            if self.host_window.busy:raise ValueError('背景作業中，先保留目前設定')
            value=validate({key:field.isChecked() for key,field in self.fields.items()}|dict(nudge_mm=self.step.value()))
            commands=validate_commands({key:editor.keySequence().toString(QKeySequence.PortableText) for key,editor in self.command_keys.items()})
            with self.host_window.library.db:
                self.host_window.library.db.execute("INSERT INTO preferences VALUES('editor_view_defaults',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps(value),))
                self.host_window.library.db.execute("INSERT INTO preferences VALUES('canvas_command_bindings',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(json.dumps(commands),))
            from .gui import Canvas
            for canvas in self.host_window.findChildren(Canvas):canvas.command_bindings=dict(commands)
            from .object_dialog import ObjectCanvas
            for canvas in self.host_window.findChildren(ObjectCanvas):
                for key,item in value.items():
                    setattr(canvas,key,item);control=getattr(canvas,'preference_widgets',{}).get(key)
                    if control is not None:
                        if isinstance(control,QCheckBox):control.setChecked(item)
                        else:control.setValue(item)
                canvas.viewport().update()
            self.accept()
        except Exception as error:self.status.setText('未保存：'+str(error))

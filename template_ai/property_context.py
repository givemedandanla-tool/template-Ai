"""View policy and explicit pending-property ownership for existing GUI controls."""
from PySide6.QtCore import QSignalBlocker,Qt
from PySide6.QtWidgets import QMessageBox
from .customers import digest


def property_values(window):
    family=window.font.currentFont().family();display=getattr(window,'_selected_font_display',None);slot=window.current_slot
    if slot and display and display['slot_id']==slot.id and family==display['display']:family=slot.font
    return dict(coords=[s.value() for s in window.coords],kind=window.kind.currentData(),owner=window.owner.currentData(),
                index=window.index.value(),font=family,pt=window.pt.value(),color=window.text_color.text().strip(),
                scale=window.scale.value(),align=window.align.currentData(),required=window.required.isChecked())


def pending_main(window):
    baseline=getattr(window,'_property_form_baseline',None)
    return bool(window.current_slot and baseline is not None and window._property_mode==window.tabs.currentIndex() and property_values(window)!=baseline)


def discard_pending_selection(parent):
    box=QMessageBox(parent);box.setWindowTitle('目前物件有待套用輸入')
    box.setText('目前輸入尚未套用至原物件。切換選取不會把這些值套用至另一個物件。')
    stay=box.addButton('返回目前物件繼續編輯',QMessageBox.RejectRole)
    discard=box.addButton('放棄未套用輸入並切換',QMessageBox.DestructiveRole)
    box.setDefaultButton(stay);box.exec();return box.clickedButton()==discard


def restore_main_selection(window):
    slot=window.current_slot
    if slot is None:return
    if window.tabs.currentIndex()==0:
        with QSignalBlocker(window.train_canvas):window.train_canvas.select_id(slot.id)
    elif window.tabs.currentIndex()==1:
        with QSignalBlocker(window.edit_canvas):window.edit_canvas.select_ids([slot.id])
        with QSignalBlocker(window.editor_tree):
            for item in getattr(window,'editor_tree_nodes',[]):item.setSelected(item.data(0,Qt.UserRole)==[slot.id])


def retain_pending_main(window):
    """A bounded diagnostic of layout controls, never customer text or a draft DB."""
    slot=window.current_slot
    window.pending_property_conflict=dict(slot_id=slot.id,mode=window.tabs.currentIndex(),root=str(window.library.root),values=property_values(window))
    window.statusBar().showMessage('原物件已變更；未套用屬性保留供核對，未套至新物件。')

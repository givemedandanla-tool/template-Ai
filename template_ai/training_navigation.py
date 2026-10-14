"""Cross-workflow navigation checks all unsaved facts, not only the selected property row."""
from dataclasses import asdict
from .batch_dialog import navigation_clean
from .font_review import fingerprint
from .model import Rect


def require_clean_navigation(window):
    if window.busy: raise ValueError('背景工作尚未完成，不能切換目前作用範圍')
    if not navigation_clean(window): raise ValueError('屬性有未套用內容，先處理後再定位')
    if window.current_slot:
        try:
            pending = window.make_slot(Rect(*(spin.value() for spin in window.coords)), preserve=True)
            pending.id = window.current_slot.id
            if pending != window.current_slot: raise ValueError('屬性座標有未套用內容，保留人工資料')
        except (TypeError, KeyError): raise ValueError('屬性資料未能核對，不能切換') from None
    if window.work:
        current = window.library.artwork(window.work['id'])
        if current['revision'] != window.work['revision'] or fingerprint(current['payload']) != fingerprint(window.work['payload']):
            raise ValueError('主作品已過期，不能由定位動作暗中覆蓋新版本')
        payload = current['payload']
        if ([asdict(s) for s in window.slots] != payload['slots'] or asdict(window.crop) != payload['crop']
                or (window.work_width, window.work_height) != (payload['work_width'], payload['work_height'])
                or window.visual.isChecked() != bool(payload.get('visual_confirmed'))):
            raise ValueError('主畫布有未保存內容，保留手工資料；請先保存或明確放棄')
    if window.template:
        snapshot = window.library.object_snapshot('TEMPLATE', window.template.id)
        if fingerprint(window.template.to_dict()) != fingerprint(snapshot['payload']):
            raise ValueError('模板有未保存內容，不能由來源定位暗中丟棄')


def locate_work(window, work_id, slot_ids=()):
    require_clean_navigation(window)
    work = window.library.artwork(work_id)
    ids = [r['id'] for r in work['payload']['slots']]
    if len(ids) != len(set(ids)) or any(sid not in ids for sid in slot_ids):
        raise ValueError('物件ID重複或已不存在，不能定位任意物件')
    window.tabs.setCurrentIndex(0); window.refresh_sources(work['source_id'])
    index = window.work_combo.findData(work_id)
    if index < 0: raise ValueError('來源作品未載入')
    window.work_combo.setCurrentIndex(index)
    if slot_ids:
        window.train_canvas.set_mode('edit'); window.train_canvas.select_id(slot_ids[0])
    return work

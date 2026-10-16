"""Read-only batch geometry comparisons on the original canvas/renderers."""
import copy
from PySide6.QtCore import Qt,QRectF,QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel
from .object_dialog import ObjectCanvas
from .object_tools import select_slots,propose
from .model import Template


def make_preview(batch):
    batch.valid_context()
    if batch.running:raise ValueError('請先安全停止目前處理')
    item=batch.table.item(batch.table.currentRow(),0)
    if item is None:raise ValueError('請先選取確切物件列')
    row=batch.by_key[item.data(Qt.UserRole)];dialog=QDialog(batch);dialog.resize(1100,650);dialog.setWindowTitle('原／新差異：不修改內容');layout=QVBoxLayout(dialog);notice=QLabel();notice.setWordWrap(True);notice.setTextFormat(Qt.PlainText);layout.addWidget(notice);views=QHBoxLayout();layout.addLayout(views);canvases=[]
    if row['kind']=='CANDIDATE':
        checked=batch.candidate_batch.checked.get(row['scope_key'])
        if not checked:raise ValueError('此確切候選尚無完成的預檢，請先預檢')
        from .render import card_view_image
        from .batch_objects import candidate_target_current
        pair=batch.candidate_batch.adapters[row['scope_key']];current=candidate_target_current(pair[0],checked['target'])
        notice.setText(('目前前置版面仍一致。' if current else '這是已保存的歷史預檢，目前版面／資料已改變，不能套用。')+' 原／新各尺寸整卡Gate見預檢清單；固定字級、人物公司歸屬仍適用。')
        values=[('原預檢版面',checked['target']['envelope']['before']),('預檢建議（未套用）',checked['candidate'])]
        for title,candidate in values:
            canvas=ObjectCanvas();canvas.readonly=True
            try:image=card_view_image(candidate)
            except (ValueError,OSError):image=None
            canvas.set_content(candidate.template.width_mm,candidate.template.height_mm,image=image,slots=candidate.template.slots,safe_margin_mm=candidate.template.safe_margin_mm);canvases.append((title,canvas))
    else:
        key=row['kind']+':'+row['id'];planned=next((r for r in (batch.plan or {}).get('rows',[]) if r['target_key']==key),None)
        snapshot=planned.get('snapshot') if planned else None
        if not snapshot:raise ValueError('此列尚無可核實原版本的預檢；請使用定位逐筆核對')
        before=copy.deepcopy(snapshot['payload']);after=propose(before,row['kind'],planned['request'])['after'] if planned['state']=='READY' else before
        current=batch.library.object_snapshot(row['kind'],row['id']);notice.setText(('目前來源版本仍一致。' if current==snapshot else '來源已有新版本；以下只是原預檢歷史，不能覆寫目前資料。')+' 標記幾何與安全區比較；尚須整作品驗證。原稿內容可由「定位」查看。')
        image=None
        if row['kind']=='ARTWORK':
            source=batch.library.source(batch.library.artwork(row['id'])['source_id']);original=QImage(source['image']);crop=before['crop']
            if not original.isNull():image=original.copy(QRectF(crop['x']*original.width()/source['width_mm'],crop['y']*original.height()/source['height_mm'],crop['w']*original.width()/source['width_mm'],crop['h']*original.height()/source['height_mm']).toAlignedRect())
        elif before.get('background'):
            from .render import render_background
            image=render_background(Template.from_dict(before),96)
        for title,value in [('原預檢標記',before),('預檢建議（未套用）',after)]:
            canvas=ObjectCanvas();canvas.readonly=True;slots=select_slots(value,[s['id'] for s in value['slots']]);w,h=(value['work_width'],value['work_height']) if row['kind']=='ARTWORK' else (value['width_mm'],value['height_mm']);canvas.set_content(w,h,image=image,slots=slots,safe_margin_mm=value.get('safe_margin_mm',0));canvases.append((title,canvas))
    dialog.canvases=[]
    for title,canvas in canvases:
        pane=QVBoxLayout();pane.addWidget(QLabel(title));pane.addWidget(canvas);views.addLayout(pane);canvas.set_mode('pan');QTimer.singleShot(0,canvas.fit);dialog.canvases.append(canvas)
    return dialog

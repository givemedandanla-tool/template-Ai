"""Adapters for existing desktop entry points; DesignSessions remains the truth."""
from copy import deepcopy

from .input_graph import InputGraph
from .training_store import digest


def current_graph(window):
    graph=getattr(window,'active_input_graph',None)
    if graph is not None:return graph.clone()
    people,companies,logos=window.input_data()
    return InputGraph.from_legacy(people,companies,logos)


def uses_learning(window):
    # An explicitly selected historical style keeps its exact published version.
    if getattr(window,'reorder_template_id',None):return False
    from .training_store import TrainingStore
    store=TrainingStore(window.library)
    if not store.get('DESIGN_ACTIVE','local-layout'):return False
    from .design_learning import CrossWorkLearning
    model,state=CrossWorkLearning(window.library).active()
    if model is None:raise ValueError('學習規則目前無法使用，請先在學習管理核對原因。未自動改用其他版型。\n'+str(state.get('reason',state)))
    return True


def routes_to_learning(window):
    if getattr(window,'reorder_template_id',None):return False
    if getattr(window,'production_view',None)=='FIXED':return False
    if getattr(window,'production_session_id',None):return True
    if any(c.generation==window.generation for c in window.candidates):return False
    return uses_learning(window)


def attach(dialog):
    window=dialog.window
    graph=current_graph(window)
    if getattr(window,'active_input_graph',None) is None:
        window.adopt_input_graph(graph.data,history=graph)
    size=(window.out_w.value(),window.out_h.value())
    identity=getattr(window,'production_session_id',None)
    row=dialog.sessions.current(identity) if identity else None
    origin=deepcopy(getattr(window,'reorder_customer_snapshot',None))
    origin_ref=dict(id=origin['id'],revision=origin['revision'],code=origin['code']) if origin else None
    if row and row.get('customer_reference')!=origin_ref:row=None
    if row and not ({p['id'] for p in row['input_graph']['people']} & {p['id'] for p in graph.data['people']}):row=None
    if row and (row['width_mm'],row['height_mm'])!=size:
        from .model import new_id
        dialog.sessions.resize(row['id'],row['revision'],new_id(),*size)
        row=dialog.sessions.current(row['id'])
    if row is None:
        # The exact accepted artifact takes precedence over a newer active
        # model. Reuse its session only while it still describes that artifact.
        from .design_learning import CrossWorkLearning
        _,active=CrossWorkLearning(window.library).active()
        accepted=dialog.sessions.find_accepted(graph,*size,production=active.get('policy',{}).get('production') is True)
        if accepted:
            saved=dialog.sessions.current(accepted['session_id'])
            if (saved['input_graph']==graph.data and not saved['intents'] and saved.get('result_id')==accepted['result_id']
                    and saved.get('confirmation') and saved.get('customer_reference')==origin_ref):row=saved
    if row:
        if row['input_graph']!=graph.data:
            from .model import new_id
            dialog.sessions.replace_input(row['id'],row['revision'],new_id(),graph)
            row=dialog.sessions.current(row['id'])
    else:
        row=dialog.sessions.create(graph,*size,dialog.actor.text())
        if origin_ref:
            with dialog.sessions.store.transaction():
                value={k:v for k,v in row.items() if k not in ('id','revision')}
                value['customer_reference']=origin_ref
                row=dialog.sessions.store._write('DESIGN_SESSION',row['id'],value,row['revision'],'production_customer_reference_pinned')
    dialog.session_id=row['id'];dialog.bound_to_main=True
    window.production_session_id=row['id'];window.production_generation=window.generation
    window.production_view='LEARNED'
    dialog.out_w.setValue(size[0]);dialog.out_h.setValue(size[1]);dialog.save_workspace()
    dialog.tabs.setCurrentIndex(2);dialog.refresh_draft()
    return row


def sync_input(dialog,graph):
    if not getattr(dialog,'bound_to_main',False):return
    window=dialog.window
    window.adopt_input_graph(graph.data,history=graph)
    window.production_generation=window.generation
    window.production_view='LEARNED'


def publish_preview(dialog):
    if not getattr(dialog,'bound_to_main',False) or not dialog.session_id:return
    window=dialog.window;row=dialog.sessions.current(dialog.session_id)
    if getattr(window,'production_view',None)!='LEARNED' or getattr(window,'production_session_id',None)!=dialog.session_id:return
    if window.generation!=getattr(window,'production_generation',None):return
    if digest(current_graph(window).data)!=digest(row['input_graph']):return
    if (window.out_w.value(),window.out_h.value())!=(row['width_mm'],row['height_mm']):return
    try:_,_,candidate=dialog.sessions.checked_result(row['id'])
    except ValueError:
        window.preview_button.setEnabled(False);window.export_button.setEnabled(False)
        window.issues.setText('資料已保存，畫面待重新排版；舊稿不能作為這次資料的確認結果。');return
    from .render import card_view_image
    window.output_canvas.set_content(row['width_mm'],row['height_mm'],card_view_image(candidate,150))
    window.output_canvas.set_mode('pan');window.output_canvas.fit()
    window.sync_property_mode()
    window.navigation.update()
    window.refresh_input_problems()
    window.output_properties.setPlainText('目前顯示學習稿件；填資料、位置調整、確認及檢查報告皆由同一份稿件接續。')
    window.preview_button.setEnabled(True)
    window.export_button.setEnabled(bool(row.get('confirmation',{} ) and row['confirmation'].get('for_production') and candidate.formal_eligible))
    window.issues.setText('已使用學到的版面規則產生稿件。按「預覽／拖動調整」可移動聯絡資料、改內容及確認。\n'+dialog.status.text())


def is_learning_view(window):
    return bool(not getattr(window,'reorder_template_id',None) and getattr(window,'production_view',None)=='LEARNED' and getattr(window,'production_session_id',None))


def learning_input_status(window):
    """Read-only presentation status; never solve, activate or rewrite master data."""
    if getattr(window,'reorder_template_id',None) or getattr(window,'production_view',None)=='FIXED':return None
    # Navigation also runs before learning storage exists and during shutdown.
    import sqlite3
    from .training_store import TrainingStore
    try:
        if not window.library.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='training_records'").fetchone():return None
        store=TrainingStore.bind(window.library)
        if is_learning_view(window):
            row=store.get('DESIGN_SESSION',window.production_session_id)
            if not row:return '學習稿狀態需要重新核對；請開啟目前稿件。'
            same=(getattr(window,'production_generation',None)==window.generation
                  and current_graph(window).data==row['input_graph']
                  and (window.out_w.value(),window.out_h.value())==(row['width_mm'],row['height_mm']))
            if not same or row['result_state']!='CURRENT':return '學習稿已保存；資料或尺寸已修改，請更新稿件。'
            state='已確認；輸出前仍會核對目前版本' if row.get('confirmation') else '待檢查與確認'
            return f"學習稿已保存 · {row['width_mm']:g}×{row['height_mm']:g} mm · "+state
        if not any(c.generation==window.generation for c in window.candidates) and store.get('DESIGN_ACTIVE','local-layout'):
            return '已選用學習規則；請產生稿件，核對資料、容量與可用版面。'
    except (sqlite3.Error,ValueError,TypeError,KeyError):
        if is_learning_view(window):return '學習稿狀態需要重新核對；請開啟目前稿件。'
    return None


def has_current(window):
    return bool(is_learning_view(window) and getattr(window,'production_generation',None)==window.generation)


def export_current(window,preview):
    from .design_session import DesignSessions
    from PySide6.QtWidgets import QFileDialog
    if not has_current(window):raise ValueError('目前畫面不是這份有效學習稿，請先開啟並核對。')
    sessions=DesignSessions(window.library);row,_,candidate=sessions.checked_result(window.production_session_id)
    if current_graph(window).data!=row['input_graph'] or (window.out_w.value(),window.out_h.value())!=(row['width_mm'],row['height_mm']):
        raise ValueError('資料或尺寸已改變，請重新排版再確認。')
    confirmation=row.get('confirmation')
    if not confirmation or not preview and not confirmation.get('for_production'):
        window.shared_design_learning(use_current_input=True)
        return
    target,_=QFileDialog.getSaveFileName(window,'儲存這份已確認的稿件','PREVIEW-design.png' if preview else 'design.png','PNG (*.png);;PDF (*.pdf);;JPG (*.jpg)')
    if not target:return
    artifact=sessions.export(row['id'],target,preview=preview)
    window.statusBar().showMessage('已儲存稿件：'+artifact['path'])
    return artifact

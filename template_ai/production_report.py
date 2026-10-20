"""Plain explanations with retained expert evidence; never an approval gate."""
import json
import math
from pathlib import Path
import tempfile
from datetime import datetime,timezone


def explain_error(error):
    details=str(error);lower=details.lower()
    if 'cancel' in lower:
        summary='這次排版已停止，資料仍然保留。';step='可以繼續編輯，或重新產生稿件。'
    elif any(word in lower for word in ('stale','revision','changed','differs','版本','過期')):
        summary='資料或使用的規則已更新，這個結果需要重新核對。';step='請回到目前稿件，重新排版並確認。'
    elif any(word in lower for word in ('font','字型','glyph')):
        summary='有文字所需的字型還沒核對完成。';step='請在字型管理查看缺少項目，完成後重新排版。'
    elif any(word in lower for word in ('logo','asset','圖片')):
        summary='有圖片的公司、尺寸或可用狀態需要核對。';step='請重新選擇對應公司的圖片，再產生稿件。'
    elif any(word in lower for word in ('relation','intent','protected','對象','相對')):
        summary='這次位置調整無法符合目前版面規則。';step='資料沒有被刪除；請復原這次調整，或核對是否更換了相關欄位。'
    elif any(word in lower for word in ('model','learning','規則')):
        summary='目前沒有可使用的學習規則，或規則的來源需要重新核對。';step='請到學習管理查看狀態；既有已確認稿仍可另外核對沿用。'
    else:
        summary='這個步驟尚未完成，請先查看原因再重試。';step='可展開詳細原因，或把診斷報告交給維護人員。'
    return dict(schema=1,summary=summary,impact='尚未把失敗結果當成可輸出的新稿。',next_step=step,details=details)


def input_advice(library,graph,width,height,model_id=None):
    from .design_learning import CrossWorkLearning
    learning=CrossWorkLearning(library)
    if model_id:model,_=learning.checked_model(model_id)
    else:model,_=learning.active()
    if model is None:return dict(status='NO_ACTIVE_MODEL',summary='尚未啟用學習規則；目前依已保存版型檢查。',hard_limit=None)
    from .design_synthesis import input_facts
    from collections import Counter
    counts=dict(Counter(row['owner_port']+':'+row['kind'] for row in input_facts(graph)))
    families=model['artifact']['profile_model']['families']
    matched=[f for f in families if counts in [p['pattern'] for p in f.get('grammar',{}).get('observed_joint_count_patterns',[])]]
    summary=('這組欄位有已學習的組合可參考。' if matched else '這組欄位尚未有足夠的學習依據。')+' 實際能否排入，需按目前尺寸、文字及圖片試排；不會用固定字數猜測。'
    return dict(status='OBSERVED_COMBINATION' if matched else 'UNKNOWN_COMBINATION',summary=summary,hard_limit=None,
                model_id=model['id'],weights_digest=model['weights_digest'],field_counts=counts,
                physical_size=[width,height],matching_families=[f['family_id'] for f in matched],actual_layout_required=True)


def result_report(library,session,result,candidate):
    from .input_graph import InputGraph
    advice=input_advice(library,InputGraph(session['input_graph']),session['width_mm'],session['height_mm'],session['model_id'])
    capacity=[]
    if candidate is not None:
        from .design_capacity import LocalCapacityCalibration,capacity_advice,joint_demand
        service=LocalCapacityCalibration(library)
        context,demand=joint_demand(candidate,InputGraph(session['input_graph']),session['width_mm'],session['height_mm'])
        for row in service.store.records('DESIGN_CAPACITY',limit=200):
            if row['model_id']!=session['model_id']:continue
            try:checked=service.checked(row['id']);value=capacity_advice(checked['artifact'],context,demand)
            except ValueError:continue
            capacity.append(dict(calibration_id=row['id'],**value))
    validated=next((r for r in capacity if r['status']=='WITHIN_VALIDATED_EMPIRICAL_REGION'),None)
    capacity_text='目前資料落在已驗證的適合範圍，這份稿仍須通過實際檢查。' if validated else '這筆資料的容量適合範圍尚未核實；不等於排不下，也不代表已通過正式輸出。'
    summary='已產生完整稿件，可以拖動聯絡資料調整位置。' if candidate else '目前還沒有找到能完整承接這些資料的稿件。'
    next_step='請檢視內容後確認；需要時可改資料或位置。' if candidate else '請查看詳細原因，核對缺少的來源、欄位、字型或圖片，再重新試排。'
    return dict(schema=1,summary=summary,impact='輸入資料完整保留；正式輸出仍依這份稿的有效驗證。',next_step=next_step,
        capacity_summary=capacity_text,input_advice=advice,capacity=capacity,
        details=json.dumps(dict(attempts=result.get('attempts',[]) if result else [],selected=result.get('selected',{}).get('family_id') if result and result.get('selected') else None,
                               ranking_scope=result.get('ranking_scope') if result else None,capacity=capacity,input_advice=advice),ensure_ascii=False,indent=2))


def save_report(sessions,identity,revision,target):
    """Local JSON handoff without input text, source paths or font bytes."""
    from .training_store import digest
    from .safe_publish import publish_complete
    row=sessions.current(identity,revision);candidate=None;validation_summary='這份結果對應目前資料。'
    try:_,_,candidate=sessions.checked_result(identity)
    except ValueError as error:validation_summary=explain_error(error)['summary']
    plain=dict(summary='已產生稿件，請檢視內容及目前驗證狀態。' if candidate else '這份資料仍需重新排版或核對，現在不能作為完成稿。',
               impact='資料仍保留；本報告不會修改稿件，也不能代替正式輸出驗證。',next_step='先在軟體檢視稿件及問題；需要協助時，把這份報告交給維護人員。')
    fields=[]
    if candidate:
        for index,item in enumerate(candidate.items):
            slot=item.slot
            numbers=dict(x_mm=slot.rect.x,y_mm=slot.rect.y,width_mm=slot.rect.w,height_mm=slot.rect.h,size_pt=slot.size_pt,horizontal_scale=item.scale,tracking_mm=item.tracking_mm)
            fields.append(dict(field='欄位'+str(index+1),kind=slot.kind,owner_port=slot.owner,
                measurements={k:v for k,v in numbers.items() if type(v) in (int,float) and math.isfinite(v)}))
    data=dict(schema=1,kind='TEMPLATE_AI_PRODUCTION_DIAGNOSTIC',created_utc=datetime.now(timezone.utc).isoformat(),plain_summary=plain,
        privacy='NO_INPUT_TEXT_SOURCE_PATHS_OR_FONT_BYTES',historical=True,
        technical=dict(session_id=row['id'],revision=row['revision'],data_revision=row['data_revision'],layout_revision=row['layout_revision'],
            physical_size_mm=[row['width_mm'],row['height_mm']],model_id=row['model_id'],model_revision=row['model_revision'],weights_digest=row['weights_digest'],validation_summary=validation_summary,
            policy_version_digest=digest(row['policy']['version']),result_state=row['result_state'],
            result_valid_for_current_input=candidate is not None,formal_output_allowed=bool(candidate and candidate.formal_eligible and (row.get('confirmation') or {}).get('for_production')),
            fields=fields,actual_field_count=len(row['input_graph']['fields']),hard_global_capacity=None))
    body=json.dumps(data,ensure_ascii=False,indent=2).encode()
    if len(body)>1024*1024:raise ValueError('報告超過可保存預算；尚未保存，請縮小本次檢查範圍。')
    target=Path(target);temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent,prefix='.layout-report-',delete=False) as output:
            temporary=Path(output.name);output.write(body)
        publish_complete(temporary,target,lambda:sessions.current(identity,revision))
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)
    return data

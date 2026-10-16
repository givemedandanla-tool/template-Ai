"""Present existing candidate results; scores never confer output permission."""
import copy,math
from .training_store import digest


def current_assessment(window,index):
    candidate=window.candidates[index];risk=copy.deepcopy(candidate.risk);reasons=[]
    if candidate.generation!=window.generation:reasons.append('輸入世代已變；須重驗目前資料')
    try:
        people,companies,logos=window.input_data()
        if candidate.risk_context.get('input_digest')!=digest(dict(people=people,companies=companies,logos=logos)):reasons.append('目前輸入與量測快照不一致')
    except (ValueError,TypeError):reasons.append('目前輸入尚無合法可核對結構，保留候選但不放行')
    if (candidate.template.width_mm,candidate.template.height_mm)!=(window.out_w.value(),window.out_h.value()):reasons.append('候選尺寸與目前指定尺寸不同；不能跨尺寸沿用檢查')
    try:
        source=window.library.object_snapshot('TEMPLATE',candidate.template.id)['payload'];pin=dict(id=source['id'],version=source['version'],digest=digest(source))
        if source.get('state')!='published' or candidate.risk_context.get('source_template_pin')!=pin:reasons.append('已核准模板exact版本需重新核對')
    except (ValueError,OSError):reasons.append('核准來源失聯或無法核實')
    if reasons:
        risk['conditions'].append(dict(id='CURRENT_RESULT_CONTEXT',status='UNKNOWN',reason='；'.join(reasons)));risk['formal_allowed']=False
        if risk['state']!='HARD_BLOCKED':risk.update(state='EVIDENCE_REQUIRED',label='目前資料／尺寸／來源待重驗，禁止正式輸出')
    return risk


def recommendation(window):
    """Argmax of finite existing rule scores over current qualified results only."""
    states=[current_assessment(window,index) for index in range(len(window.candidates))];eligible=[]
    for index,(candidate,state) in enumerate(zip(window.candidates,states)):
        if state['formal_allowed'] and isinstance(candidate.score,(int,float)) and not isinstance(candidate.score,bool) and math.isfinite(candidate.score):eligible.append(index)
    selected=min(eligible,key=lambda i:(-window.candidates[i].score,window.candidates[i].template.id,i)) if eligible else None
    summary=copy.deepcopy(getattr(window,'last_layout_summary',{}));complete=False
    if summary.get('generation')==window.generation:
        try:
            total,checked,unstarted,failed=(summary[k] for k in ('total','checked','unstarted','failed'))
            complete=all(type(v) is int and v>=0 for v in (total,checked,unstarted,failed)) and total>0 and checked==total and not unstarted and not failed and summary.get('state')=='COMPLETED'
            pins=summary.get('scope_template_pins',{})
            if len(pins)!=total:complete=False
            for identity,expected in pins.items():
                if digest(window.library.object_snapshot('TEMPLATE',identity)['payload'])!=expected:complete=False
        except (KeyError,ValueError,OSError,TypeError):complete=False
    label='目前尚無通過完整必要檢查的推薦候選'
    if selected is not None:
        c=window.candidates[selected];label='目前合格候選中的規則適配推薦：'+c.template.name+'／'+f'{c.template.width_mm:g}×{c.template.height_mm:g} mm'+'；規則分數 '+format(c.score,'.3f')+'（不是模型信心或美感保證）'
    scope='指定有限集合已完成檢查；不代表所有可能設計的全域最佳' if complete else '搜尋／核對範圍仍不完整；僅推薦目前已通過的候選'
    if summary.get('generation')==window.generation:scope+='；已檢查 '+str(summary.get('checked','未知'))+'／'+str(summary.get('total','未知'))+'，未開始 '+str(summary.get('unstarted','未知'))
    return dict(index=selected,label=label,scope_label=scope,scope_complete=complete,global_optimality_proven=False,calibrated_confidence=False,assessments=states)

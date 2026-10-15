"""Bounded tracking search with fixed point size and explicit semantic permission."""
import math


def policy_errors(slot):
    values=(slot.tracking_min_mm,slot.tracking_mm,slot.tracking_max_mm)
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in values) or not 0<=values[0]<=values[1]<=values[2]<=2:return ['字距需0≤下限≤設計值≤上限≤2mm；不以負字距破壞可讀性']
    if slot.align=='distributed':
        approval=slot.distribution_approval
        if slot.kind not in ('title','address') or not isinstance(approval,dict) or approval.get('approved') is not True or not all(isinstance(approval.get(k),str) and 0<len(approval[k].strip())<=512 for k in ('actor','reason')):return ['分散對齊限明確核准的職稱／地址欄位規則；姓名、Email、電話、公司不可一律分散']
    return []


def tracking_geometry(slot,text,measure):
    errors=policy_errors(slot)
    if errors:return 0,0,errors,slot.tracking_mm,'INVALID_POLICY'
    def evaluate(value):return measure(slot.font,slot.size_pt,text,slot.font_style,slot.font_asset,value)
    base=evaluate(slot.tracking_mm)
    if base[2]:return *base,slot.tracking_mm,'FONT_UNVERIFIED'
    lo,hi=slot.tracking_min_mm,slot.tracking_mm
    if base[0]<=slot.rect.w and slot.align!='distributed':return *base,slot.tracking_mm,'DESIGN_TRACKING'
    if slot.align=='distributed' and base[0]<=slot.rect.w:lo,hi=slot.tracking_mm,slot.tracking_max_mm
    low=evaluate(lo) if lo!=slot.tracking_mm else base;high=evaluate(hi) if hi!=slot.tracking_mm else base
    if low[2] or high[2]:return 0,0,low[2]+high[2],lo,'FONT_UNVERIFIED'
    if low[0]>=slot.rect.w:return *low,lo,'MIN_TRACKING_THEN_BOUNDED_HORIZONTAL_SCALE'
    if high[0]<=slot.rect.w:return *high,hi,'APPROVED_TRACKING_LIMIT'
    # Qt shapes the text at each candidate; the interpolation is accepted only
    # after actual width verification. Fall back to a bounded monotone search.
    candidate=lo+(hi-lo)*(slot.rect.w-low[0])/(high[0]-low[0]);measured=evaluate(candidate)
    if measured[2]:return *measured,candidate,'FONT_UNVERIFIED'
    if abs(measured[0]-slot.rect.w)>.0001:
        for _ in range(20):
            candidate=(lo+hi)/2;measured=evaluate(candidate)
            if measured[2]:return *measured,candidate,'FONT_UNVERIFIED'
            if measured[0]>slot.rect.w:hi=candidate
            else:lo=candidate
        candidate=lo;measured=evaluate(candidate)
    return *measured,candidate,'FIXED_PT_MEASURED_TRACKING_SEARCH'


def analyse_slot_font(row,slot,text,style=None,analyzer=None):
    from .font_catalog import analyze_font as default_analyzer
    analyze_font=analyzer or default_analyzer
    measured_results=[]
    def measure(family,pt,value,old_style,asset,tracking):
        result=analyze_font(row,value,pt,2000,.05,style,tracking_mm=tracking)
        measured_results.append(result)
        return result.get('width_mm') or 0,result.get('height_mm') or 0,[] if result.get('measurement_verified') else (result['issues'] or ['字面未核實，不能判定可用'])
    width,height,errors,tracking,strategy=tracking_geometry(slot,text,measure)
    if errors:
        result=dict(measured_results[-1]) if measured_results else {}
        result.update(status='BLOCKED',issues=errors,measurement_verified=False,tracking_mm=tracking,tracking_strategy=strategy);return result
    result=analyze_font(row,text,slot.size_pt,slot.rect.w,slot.min_scale,style,tracking_mm=tracking);result.update(tracking_mm=tracking,tracking_strategy=strategy);return result

"""受控字型替代：背景核驗、短期內部票據與GUI上的原子草稿交易。"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import threading
import time
import uuid

from .font_catalog import analyze_font, asset_health, raw_asset, face_fingerprint
from .model import Template, template_errors

SCOPE="草稿替代審核；原稿身份／效果、正式輸出、印刷與嵌入授權仍待各自驗證"


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()


def field_key(template_id,slot_id): return template_id+":"+slot_id


def binding(slot):
    return {"font":slot.font,"font_style":slot.font_style,"font_asset":copy.deepcopy(slot.font_asset)}


def source_row(slot):
    return ({"kind":"ASSET","asset":copy.deepcopy(slot.font_asset)} if slot.font_asset else
            {"kind":"QT","families":[slot.font],"styles":[slot.font_style] if slot.font_style else []})


def evaluate_review(snapshots,target,texts,max_fields=20,max_rows=200,max_bytes=64*1024*1024):
    if type(max_fields) is not int or not 1<=max_fields<=20 or type(max_rows) is not int or not 1<=max_rows<=200 or not 0<=max_bytes<=64*1024*1024:
        raise ValueError("審核預算不合法")
    target=copy.deepcopy(target)
    report={"rows":[],"status":"COMPLETE","omitted_rows":0,"checked_fields":0,"scope":SCOPE,"target":target}
    target_issue=None;target_face=None
    if target.get("kind")!="ASSET": target_issue="Qt來源未知候選僅可唯讀，請先合法匯入並核准本機字型"
    else:
        try:
            raw=raw_asset(target['asset']);target_face=face_fingerprint(raw)
            target['family'],target['style']=raw.familyName(),raw.styleName()
        except (ValueError,KeyError) as error: target_issue=str(error)
    used,bytes_used=set(),0
    def budget(asset):
        nonlocal bytes_used
        if not asset:return True
        key=(asset.get('hash'),asset.get('path'))
        if key in used:return True
        try:length=Path(asset['path']).stat().st_size
        except (KeyError,OSError,TypeError):length=0
        if bytes_used+length>max_bytes:return False
        used.add(key);bytes_used+=length;return True
    if not target_issue and not budget(target['asset']):target_issue="目標字型超出本輪資產預算";report['status']='PARTIAL'
    for snapshot in snapshots:
        template=Template.from_dict(snapshot['template'])
        geometric=copy.deepcopy(template)
        for slot in geometric.slots:slot.font_asset=None;slot.font_style=''
        geometry_errors=template_errors(geometric)
        for slot in template.slots:
            if slot.kind=='logo':continue
            if len(report['rows'])>=max_rows:report['omitted_rows']+=1;report['status']='PARTIAL';continue
            key=field_key(template.id,slot.id)
            row={'key':key,'template_id':template.id,'slot_id':slot.id,'template_name':template.name,'version':template.version,
                 'state':template.state,'dimensions':[template.width_mm,template.height_mm],'source_id':template.source_id,
                 'source_work_id':template.source_work_id,'source_work_revision':template.source_work_revision,
                 'slot':copy.deepcopy(template.to_dict()['slots'][template.slots.index(slot)]),'before':binding(slot),
                 'risk':'BLOCKED','eligible':False,'reasons':[],'original':None,'proposed':None,'width_delta_ratio':None,
                 'template_hash':fingerprint(snapshot['template']),'revision':snapshot['revision'],'scope':SCOPE}
            report['rows'].append(row)
            text=texts.get(key,'')
            if not isinstance(text,str):row['reasons']=['驗證文字必須是字串'];continue
            if not text.strip():row['reasons']=['未提供此欄實際驗證文字，不能借用別人的姓名'];continue
            if report['checked_fields']>=max_fields:
                row['reasons']=['超出20欄本輪量測預算'];report['status']='PARTIAL';continue
            if target_issue:row['reasons']=[target_issue];continue
            if not budget(slot.font_asset):row['reasons']=['原字型超出本輪資產預算，未核驗'];report['status']='PARTIAL';continue
            report['checked_fields']+=1
            row['text_sha256']=hashlib.sha256(text.encode()).hexdigest()
            try:
                proposed=analyze_font(target,text,slot.size_pt,slot.rect.w,slot.min_scale,target['style'])
                original=analyze_font(source_row(slot),text,slot.size_pt,slot.rect.w,slot.min_scale,slot.font_style or None)
                if original.get('family')!=slot.font:original['measurement_verified']=False;original['issues'].append('原綁定家族與實際字面不符')
                row.update(proposed=proposed,original=original)
            except ValueError as error:row['reasons']=[str(error)];continue
            reasons=list(geometry_errors)+list(proposed['issues'])
            if proposed.get('height_mm') is not None and proposed['height_mm']>slot.rect.h+1e-6:reasons.append('固定字級單行高度超出文字框，不能裁切或暗改字級')
            if proposed['status']!='FEASIBLE_WIDTH' or reasons:row['reasons']=reasons or ['目標字面未通過'];continue
            after={'font':proposed['family'],'font_style':proposed['style'],'font_asset':copy.deepcopy(target['asset'])}
            row['after']=after
            if row['before']==after:row['risk']='LOW';row['reasons']=['字型綁定完全相同，無需建立替代草稿'];continue
            known=original.get('measurement_verified') is True
            if known:row['width_delta_ratio']=proposed['width_mm']/original['width_mm']-1
            same=known and slot.font_asset and original.get('face_fingerprint')==target_face
            row.update(eligible=True,risk='LOW' if same else 'HIGH',reasons=[
                '核准複本同字面綁定修正，仍僅草稿' if same else '不同字面或原稿身份未證實，需逐欄人工詳審',
                '原自然字寬已量測' if known else '原自然字寬未知；不宣稱外觀等同',SCOPE])
    report['bytes_budgeted']=bytes_used
    return report


class FontReviewEngine:
    """returned reports非權威資料；內部cache與one-use ticket保留實際核驗。"""
    def __init__(self):
        self._lock=threading.Lock();self._reviews={};self._tickets={}

    def analyze(self,snapshots,target,texts):
        snapshots,target,texts=copy.deepcopy((snapshots,target,texts))
        report=evaluate_review(snapshots,target,texts);review_id=uuid.uuid4().hex
        report['review_id']=review_id
        with self._lock:
            if len(self._reviews)>=8:self._reviews.pop(next(iter(self._reviews)))
            self._reviews[review_id]={'snapshots':snapshots,'target':target,'texts':texts,'report':copy.deepcopy(report)}
        return report

    def _ticket(self,data):
        token=uuid.uuid4().hex
        with self._lock:
            self._tickets={k:v for k,v in self._tickets.items() if time.monotonic()-v[0]<120}
            if len(self._tickets)>=8:self._tickets.pop(next(iter(self._tickets)))
            self._tickets[token]=(time.monotonic(),copy.deepcopy(data))
        return token

    def prepare_apply(self,review_id,selections):
        with self._lock:review=copy.deepcopy(self._reviews.get(review_id))
        if not review:raise ValueError('審核已過期，請重新驗證')
        if not selections or len(selections)>20:raise ValueError('需明確選取1至20欄')
        keys=[s['key'] for s in selections]
        if len(keys)!=len(set(keys)):raise ValueError('選取欄位重複')
        known={r['key']:r for r in review['report']['rows']}
        for selection in selections:
            row=known.get(selection['key'])
            if not row or not row['eligible']:raise ValueError('選取包含未核驗／不合格欄位')
            if row['risk']=='HIGH' and selection.get('reviewed') is not True:raise ValueError('高風險欄位必須逐欄詳審並核准')
        fresh=evaluate_review(review['snapshots'],review['target'],{k:review['texts'][k] for k in keys})
        fresh_rows={r['key']:r for r in fresh['rows']}
        rows=[]
        for selection in selections:
            row=fresh_rows[selection['key']]
            if not row['eligible'] or fingerprint(row)!=fingerprint(known[selection['key']]):raise ValueError('字型／核驗結果已變更，請重新審核')
            rows.append(row)
        return self._ticket({'kind':'APPLY','snapshots':review['snapshots'],'target':fresh['target'],'rows':rows})

    def prepare_history(self,record,action):
        record=copy.deepcopy(record)
        expected='APPLIED' if action=='UNDO' else 'UNDONE' if action=='REDO' else None
        if not expected or record['phase']!=expected:raise ValueError('歷史階段不符，請刷新')
        if action=='REDO':
            raw=raw_asset(record['target']['asset'])
            if face_fingerprint(raw)!=record['target_face']:raise ValueError('重做字面不同，請重新審核')
        return self._ticket({'kind':action,'record':record})

    def commit(self,library,token,confirmed=False):
        if confirmed is not True:raise ValueError('尚未明確確認選取的草稿修改範圍')
        with self._lock:ticket=self._tickets.pop(token,None)
        if not ticket or time.monotonic()-ticket[0]>120:raise ValueError('核驗票據不存在或已過期，請重新核對')
        data=ticket[1]
        return library._commit_font_change(data) if data['kind']=='APPLY' else library._commit_font_history(data)

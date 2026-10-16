"""Frozen, bounded lookup candidates; never consult holdout associations or facts."""
import json
import math
from .training_store import digest, text
from .model import Template


def configuration(config):
    if config is None: return None
    if not isinstance(config,dict) or set(config)!={'code_pattern','maximum_size_error_mm','customer_ids'}:raise ValueError('映射需明確檔名規則、尺寸容差及候選客戶ID')
    from .customer_candidates import source_code
    source_code('synthetic.svg',config['code_pattern'])
    tolerance=config['maximum_size_error_mm'];ids=config['customer_ids']
    if type(tolerance) not in (int,float) or not math.isfinite(tolerance) or tolerance<0:raise ValueError('映射尺寸容差需明確非負毫米數，無預設')
    if not isinstance(ids,list) or not 1<=len(ids)<=200 or len(set(ids))!=len(ids) or any(not isinstance(i,str) for i in ids):raise ValueError('需明列1～200客戶候選，不默認全庫')
    return dict(code_pattern=config['code_pattern'],maximum_size_error_mm=tolerance,customer_ids=sorted(ids))


def customer_snapshot(library,customer_id):
    db=library.db
    row=db.execute('SELECT id,code,revision FROM customers WHERE id=?',(customer_id,)).fetchone()
    if not row:raise ValueError('映射候選客戶已失聯')
    if db.execute('SELECT 1 FROM customer_identity_redirects WHERE secondary_id=?',(customer_id,)).fetchone():raise ValueError('需選目前主客戶，不能把合併前身分當獨立候選')
    from .customer_identity import members
    ids=members(db,customer_id)
    if len(ids)>200:raise ValueError('客戶合併家族超過200，需縮小明列範圍')
    aliases=[r[0] for r in db.execute('SELECT code FROM customer_code_aliases WHERE customer_id=? ORDER BY code',(customer_id,)).fetchmany(201)]
    if len(aliases)>200:raise ValueError('客戶代號別名超過200，不截斷')
    styles=[]
    for cid in ids:
        for style in db.execute('SELECT id,template_id,template_hash,width,height FROM customer_styles WHERE customer_id=? ORDER BY id',(cid,)).fetchmany(201):
            if len(styles)>=200:raise ValueError('客戶映射版型超過200，不截斷')
            template=db.execute('SELECT payload FROM templates WHERE id=?',(style[1],)).fetchone()
            if not template or len(template[0].encode())>1048576:raise ValueError('映射版型失聯或metadata超過1MiB')
            actual=Template.from_dict(json.loads(template[0])).to_dict()
            if digest(actual)!=style[2]:raise ValueError('映射版型與客戶已確認版本不一致')
            styles.append(dict(id=style[0],template_id=style[1],template_hash=style[2],width_mm=style[3],height_mm=style[4]))
    return dict(customer_id=row[0],code=row[1],revision=row[2],aliases=aliases,styles=sorted(styles,key=lambda s:s['id']))


def catalog(library,config):
    config=configuration(config)
    return None if config is None else dict(configuration=config,customers=[customer_snapshot(library,i) for i in config['customer_ids']],
                                             input_scope='EXPLICIT_PREEXISTING_CATALOG_NOT_HOLDOUT_GOLD_OR_SOURCE_ASSOCIATIONS')


def predict(source,work,frozen):
    if frozen is None:return dict(state='NOT_CONFIGURED',candidates=[],selected=None)
    from .customer_candidates import source_code
    config=frozen['configuration'];code=source_code(source['original_path'],config['code_pattern']);candidates=[]
    for customer in frozen['customers']:
        if code not in [customer['code'],*customer['aliases']]:continue
        for style in customer['styles']:
            if max(abs(style['width_mm']-work['work_width']),abs(style['height_mm']-work['work_height']))<=config['maximum_size_error_mm']:
                candidates.append(dict(customer_id=customer['customer_id'],style_id=style['id'],template_id=style['template_id'],template_hash=style['template_hash']))
    return dict(state='UNIQUE_SOURCE_CODE_AND_SIZE_CANDIDATE' if len(candidates)==1 else 'AMBIGUOUS_OR_ABSTAINED',
                candidates=candidates,selected=candidates[0] if len(candidates)==1 else None,
                source_code=code,catalog_digest=digest(frozen),human_identity_confirmation=False)


def truth(library,evidence):
    if not isinstance(evidence,dict) or set(evidence)!={'customer_id','style_id','review_reason'}:raise ValueError('映射真值需人工核對客戶、exact版型及理由')
    text(evidence['review_reason'],'來源→客戶→版型人工對照依據',2000)
    customer=customer_snapshot(library,evidence['customer_id'])
    style=next((s for s in customer['styles'] if s['id']==evidence['style_id']),None)
    if not style:raise ValueError('exact版型不屬於已確認客戶')
    return dict(customer_id=customer['customer_id'],style_id=style['id'],template_id=style['template_id'],template_hash=style['template_hash'],
                review_reason=evidence['review_reason'],customer_snapshot_digest=digest(customer),manually_verified=True)

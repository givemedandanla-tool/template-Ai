"""Read-only, bounded dependency evidence for a source-location change; never a quality approval."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

MAX_CONTEXT_ROWS=2000
MAX_SNAPSHOT_CONTEXT_BYTES=8*1024*1024
from .asset_references import is_asset_path


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def source_context(library, source_id):
    db=library.db;source=library.source(source_id)
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    def rows(sql,args=()):
        cursor=db.execute(sql,args);names=[c[0] for c in cursor.description];values=cursor.fetchmany(MAX_CONTEXT_ROWS+1)
        if len(values)>MAX_CONTEXT_ROWS:raise ValueError('單一來源關聯超過2000筆；請先分組核對，未建立完整影響預覽')
        return [dict(zip(names,row)) for row in values]
    works=rows('SELECT id,revision,payload FROM artworks WHERE source_id=? ORDER BY id',(source_id,))
    work_ids=[w['id'] for w in works];refs=[source_id]+work_ids;marks=','.join('?' for _ in refs)
    associations=rows('SELECT * FROM customer_source_associations WHERE source_id=? ORDER BY id',(source_id,)) if 'customer_source_associations' in tables else []
    template_ids=sorted({a['template_id'] for a in associations})
    templates=rows("SELECT id,payload FROM templates WHERE json_extract(payload,'$.source_id')=? OR json_extract(payload,'$.source_work_id') IN (SELECT id FROM artworks WHERE source_id=?) OR id IN (SELECT value FROM json_each(?)) ORDER BY id",(source_id,source_id,json.dumps(template_ids)))
    template_ids=[t['id'] for t in templates]
    styles=rows('SELECT * FROM customer_styles WHERE template_id IN (SELECT value FROM json_each(?)) ORDER BY id',(json.dumps(template_ids),)) if 'customer_styles' in tables else []
    style_scopes=rows('SELECT * FROM customer_style_scopes WHERE style_id IN (SELECT value FROM json_each(?)) ORDER BY style_id',(json.dumps([s['id'] for s in styles]),)) if 'customer_style_scopes' in tables else []
    customer_ids=sorted({a['customer_id'] for a in associations+styles})
    customers=rows('SELECT id,code,revision FROM customers WHERE id IN (SELECT value FROM json_each(?)) ORDER BY id',(json.dumps(customer_ids),)) if 'customers' in tables else []
    aliases=rows('SELECT * FROM customer_code_aliases WHERE customer_id IN (SELECT value FROM json_each(?)) ORDER BY code',(json.dumps(customer_ids),)) if 'customer_code_aliases' in tables else []
    redirects=rows('SELECT * FROM customer_identity_redirects WHERE secondary_id IN (SELECT value FROM json_each(?)) OR primary_id IN (SELECT value FROM json_each(?)) ORDER BY secondary_id',(json.dumps(customer_ids),json.dumps(customer_ids))) if 'customer_identity_redirects' in tables else []
    candidates=rows("SELECT id,revision,state,payload FROM customer_import_candidates WHERE json_extract(payload,'$.pins.source_id')=? ORDER BY id",(source_id,)) if 'customer_import_candidates' in tables else []
    training=rows(f"SELECT kind,id,revision,payload FROM training_records t WHERE EXISTS (SELECT 1 FROM json_tree(t.payload) j WHERE j.atom IN ({marks})) ORDER BY kind,id",refs) if 'training_records' in tables else []
    logos=rows("SELECT id,payload FROM logos WHERE json_extract(payload,'$.source_id')=? ORDER BY id",(source_id,))
    # Template bindings can refer to another source's size-specific logo. Include those exact records too.
    bound=set()
    for item in templates:
        payload=json.loads(item['payload'])
        for value in payload.get('company_bindings',{}).values():
            bound.update([value] if isinstance(value,str) else value if isinstance(value,list) else [])
    known={l['id'] for l in logos}
    if bound-known:logos+=rows('SELECT id,payload FROM logos WHERE id IN (SELECT value FROM json_each(?)) ORDER BY id',(json.dumps(sorted(bound-known)),))
    assets={}
    def walk(value,origin):
        if isinstance(value,dict):
            for key,item in value.items():
                if is_asset_path(key,item):
                    record=dict(path=item,expected_sha256=value.get('file_hashes',{}).get(key) or value.get('sha256',value.get('hash')),declared_by=origin)
                    assets[(item,origin)]=record
                    if len(assets)>MAX_CONTEXT_ROWS:raise ValueError('單一來源資產依賴超過2000件；未建立完整影響預覽')
                else:walk(item,origin)
        elif isinstance(value,list):
            for item in value:walk(item,origin)
    walk(source,'SOURCE:'+source_id)
    for name,items in [('ARTWORK',works),('TEMPLATE',templates),('LOGO',logos),('TRAINING',training)]:
        for item in items:walk(json.loads(item['payload']),name+':'+item['id'])
    records={name:[{k:(digest(json.loads(v)) if k=='payload' else v) for k,v in item.items()} for item in items]
             for name,items in [('works',works),('templates',templates),('logos',logos),('training',training),('candidates',candidates)]}
    evidence=dict(source={key:source.get(key) for key in ['id','hash','byte_size','original_path','current_path','link_revision']},
                  records=records,customers=customers,customer_aliases=aliases,customer_redirects=redirects,customer_associations=associations,
                  customer_styles=styles,customer_style_scopes=style_scopes,assets=sorted(assets.values(),key=lambda a:(a['path'],a['declared_by'])),
                  dependency_basis='Exact persisted source/work/template IDs and declared references; missing or changed dependencies still require their own validation; no automatic customer or quality approval')
    raw=json.dumps(evidence,ensure_ascii=False,sort_keys=True,allow_nan=False).encode()
    if len(raw)>1_048_576:raise ValueError('來源完整影響證據超過1MiB；請先分組核對，未省略關聯')
    return dict(work_ids=work_ids,template_ids=template_ids,logo_ids=sorted(l['id'] for l in logos),customer_ids=customer_ids,
                style_ids=[s['id'] for s in styles],training_ids=[{'kind':t['kind'],'id':t['id'],'revision':t['revision']} for t in training],
                context=evidence,context_sha256=digest(evidence),
                summary=f"作品{len(works)}／模板{len(templates)}／Logo{len(logos)}／客戶{len(customers)}／版型{len(styles)}／訓練{len(training)}／資產{len(assets)}；僅登錄關聯，品質仍需驗證")


def snapshot_contexts(root, source_ids, cancel=None):
    """Independent read-only SQLite connection, one consistent snapshot, bounded query time."""
    from contextlib import closing
    import sqlite3,time
    from .storage import Library
    from .source_links import ScanCancelled
    if len(source_ids)>2000:raise ValueError('單次最多2000條來源，未截斷來源清單')
    deadline=time.monotonic()+30
    def stopped():return bool(cancel and cancel.is_set())
    with closing(sqlite3.connect((Path(root)/'library.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)) as db:
        db.set_progress_handler(lambda:int(stopped() or time.monotonic()>deadline),1000)
        view=object.__new__(Library);view.db=db;view.root=Path(root);view.assets=view.root/'assets';sources=[];context_bytes=0
        try:
            db.execute('BEGIN')
            for identity in source_ids:
                if stopped():raise ScanCancelled()
                source=view.source(identity);source['impacts']=source_context(view,identity)
                context_bytes+=len(json.dumps(source,ensure_ascii=False).encode())
                if context_bytes>MAX_SNAPSHOT_CONTEXT_BYTES:raise ValueError('整批來源關聯預覽超過8MiB；請分組核對，未省略來源')
                sources.append(source)
        except sqlite3.OperationalError as error:
            if stopped():raise ScanCancelled() from error
            raise ValueError('完整來源關聯查詢未完成／超過30秒；未省略資料') from error
        finally:db.rollback()
    for source in sources:
        statuses={}
        for asset in source['impacts']['context']['assets']:
            if stopped():raise ScanCancelled()
            path=Path(asset['path'])
            try:statuses[asset['path']]='存在，內容／使用權利仍需原用途驗證' if path.is_file() else '失聯或不是一般檔案'
            except OSError:statuses[asset['path']]='不可讀，需人工重新定位'
        source['impacts']['asset_availability']=statuses
    return sources


def presentation_rows(impact):
    c=impact['context'];s=c['source'];rows=[['來源／'+s['id'],f"SHA256 {s['hash']}；{s['byte_size']} bytes；位置版次{s['link_revision']}",s['original_path']+' → '+s['current_path']]]
    for kind,items in c['records'].items():
        for item in items:rows.append([kind+'／'+item['id'],'；'.join(f'{k}={v}' for k,v in item.items() if k!='id'),'保留確切版本；不自動改寫'])
    for label,key in [('客戶','customers'),('歷史編號','customer_aliases'),('身份轉向','customer_redirects'),('來源關聯','customer_associations'),('獨立版型','customer_styles'),('版型人物範圍','customer_style_scopes')]:
        for item in c[key]:rows.append([label+'／'+str(item.get('id',item.get('code',item.get('style_id','')))),json.dumps(item,ensure_ascii=False),'保留原關聯；不合併客戶'])
    for asset in c['assets']:rows.append(['資產／'+asset['declared_by'],str(asset.get('expected_sha256') or '沒有內容指紋；待原用途驗證'),asset['path']+'；'+impact.get('asset_availability',{}).get(asset['path'],'僅登錄路徑，尚未核驗')])
    return rows

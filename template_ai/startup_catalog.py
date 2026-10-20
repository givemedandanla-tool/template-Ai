"""Bounded payload reads and global SQL filtering, without opening original files."""
import json
from .model import Template

MAX_PAYLOAD=1024*1024
PAGE_SIZE=48


from .metadata_snapshot import snapshot_read

def payload(library,table,identity):
    if table not in ('templates','sources'):raise ValueError('未知目錄種類')
    row=library.db.execute('SELECT CASE WHEN length(CAST(payload AS BLOB))<=? THEN payload END FROM '+table+' WHERE id=?',(MAX_PAYLOAD,identity)).fetchone()
    if not row:raise ValueError('目錄項目已失聯：'+identity)
    if row[0] is None:raise ValueError('單項目錄超過1MiB；請從診斷核對，不在啟動時展開：'+identity)
    return json.loads(row[0])


@snapshot_read(lambda library,*args,**kwargs:library.db)
def editor_page(library,table,offset=0,selected=None,limit=48):
    if table not in ('sources','templates') or type(offset) is not int or offset<0 or type(limit) is not int or not 1<=limit<=100:raise ValueError('目錄需有效分頁')
    total=library.db.execute('SELECT count(*) FROM '+table).fetchone()[0]
    if selected:
        rank=library.db.execute('SELECT count(*) FROM '+table+' WHERE rowid>(SELECT rowid FROM '+table+' WHERE id=?)',(selected,)).fetchone()[0]
        if library.db.execute('SELECT 1 FROM '+table+' WHERE id=?',(selected,)).fetchone():offset=(rank//limit)*limit
    offset=min(offset,max(0,((total-1)//limit)*limit));ids=[r[0] for r in library.db.execute('SELECT id FROM '+table+' ORDER BY rowid DESC LIMIT ? OFFSET ?',(limit,offset))]
    result=[];issues=[]
    for identity in ids:
        try:
            value=payload(library,table,identity)
            result.append(library.source(identity) if table=='sources' else Template.from_dict(value))
        except (ValueError,TypeError,KeyError) as error:issues.append(str(error))
    return dict(items=result,total=total,offset=offset,issues=issues)


def facets(library):
    rows=library.db.execute("SELECT json_extract(payload,'$.width_mm'),json_extract(payload,'$.height_mm'),json_extract(payload,'$.capacity'),count(*) FROM templates GROUP BY 1,2,3 ORDER BY 1,2,3 LIMIT 201").fetchall()
    tree={}
    for width,height,capacity,count in rows[:200]:tree.setdefault((width,height),{})[capacity]=count
    versions=[r[0] for r in library.db.execute('SELECT DISTINCT version FROM templates ORDER BY version LIMIT 201')]
    return dict(tree=tree,versions=versions[:200],partial_facets=len(rows)>200 or len(versions)>200)


def search(library,query='',size=None,capacity=None,state=None,version=None,page=0):
    if not isinstance(query,str) or len(query)>500 or len(query.split())>20:raise ValueError('搜尋限制500字／20詞')
    library.db.create_function('runtime_casefold',1,lambda v:str(v).casefold(),deterministic=True)
    words="runtime_casefold(COALESCE(json_extract(payload,'$.name'),'')||' '||id||' '||family_id||' '||version||' '||state||' CURRENT '||COALESCE(json_extract(payload,'$.source_id'),'')||' '||COALESCE(json_extract(payload,'$.source_work_id'),''))"
    clauses=['1=1'];params=[]
    for token in query.casefold().split():clauses.append('instr('+words+',?)>0');params.append(token)
    if size:clauses.extend(["json_extract(payload,'$.width_mm')=?","json_extract(payload,'$.height_mm')=?"]);params.extend(size)
    if capacity is not None:clauses.append("json_extract(payload,'$.capacity')=?");params.append(capacity)
    if state:clauses.append('state=?');params.append(state)
    if version is not None:clauses.append('version=?');params.append(version)
    where=' AND '.join(clauses);total=library.db.execute('SELECT count(*) FROM templates WHERE '+where,params).fetchone()[0]
    page=min(max(0,page),max(0,(total-1)//PAGE_SIZE))
    order="json_extract(payload,'$.width_mm'),json_extract(payload,'$.height_mm'),json_extract(payload,'$.capacity'),runtime_casefold(json_extract(payload,'$.name')),version,id"
    ids=[r[0] for r in library.db.execute('SELECT id FROM templates WHERE '+where+' ORDER BY '+order+' LIMIT ? OFFSET ?',(*params,PAGE_SIZE,page*PAGE_SIZE))]
    return dict(ids=ids,total=total,page=page)

"""Extend the one CustomerStore database with normalized entity ownership.

customer_fields keeps its original stable IDs and text. Additional FK tables
identify the actual owner and references. No second customer/order database.
"""
from copy import deepcopy
from .input_graph import InputGraph
from .model import new_id


SCHEMA = '''
CREATE UNIQUE INDEX IF NOT EXISTS customer_field_identity ON customer_fields(customer_id,id);
CREATE TABLE IF NOT EXISTS customer_graph_states(customer_id TEXT PRIMARY KEY REFERENCES customers(id),schema_version INTEGER NOT NULL,status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customer_entities(
 id TEXT PRIMARY KEY,customer_id TEXT NOT NULL REFERENCES customers(id),kind TEXT NOT NULL CHECK(kind IN ('PERSON','COMPANY')),
 position INTEGER NOT NULL CHECK(position>=0),logo_id TEXT NOT NULL,UNIQUE(customer_id,id),UNIQUE(customer_id,kind,position));
CREATE TABLE IF NOT EXISTS customer_entity_fields(
 id TEXT PRIMARY KEY REFERENCES customer_fields(id),customer_id TEXT NOT NULL,owner_id TEXT NOT NULL,
 UNIQUE(customer_id,id),FOREIGN KEY(customer_id,id) REFERENCES customer_fields(customer_id,id),
 FOREIGN KEY(customer_id,owner_id) REFERENCES customer_entities(customer_id,id));
CREATE TABLE IF NOT EXISTS customer_field_users(
 customer_id TEXT NOT NULL,field_id TEXT NOT NULL,entity_id TEXT NOT NULL,position INTEGER NOT NULL,
 PRIMARY KEY(field_id,entity_id),UNIQUE(field_id,position),
 FOREIGN KEY(customer_id,field_id) REFERENCES customer_entity_fields(customer_id,id),
 FOREIGN KEY(customer_id,entity_id) REFERENCES customer_entities(customer_id,id));
CREATE TABLE IF NOT EXISTS customer_company_links(
 customer_id TEXT NOT NULL,person_id TEXT NOT NULL,company_id TEXT NOT NULL,
 PRIMARY KEY(person_id,company_id),FOREIGN KEY(customer_id,person_id) REFERENCES customer_entities(customer_id,id),
 FOREIGN KEY(customer_id,company_id) REFERENCES customer_entities(customer_id,id));
'''


def from_legacy_fields(rows):
    """No string deduplication. Preserve every existing field ID; ambiguity blocks."""
    owners=sorted({r['owner'] for r in rows},key=lambda x:int(x[1:]))
    if any(not o.startswith('p') or not o[1:].isdigit() for o in owners):raise ValueError('舊欄位歸屬需人工核對')
    ids={o:new_id() for o in owners}
    data=dict(schema=1,revision=0,people=[{'id':ids[o]} for o in owners],companies=[],links=[],fields=[])
    for f in rows:data['fields'].append(dict(id=f['id'],owner_id=ids[f['owner']],kind=f['kind'],value=f['value'],users=[ids[f['owner']]]))
    InputGraph.validate(data);return data


def insert_graph(db,cid,data,write_fields=False):
    InputGraph.validate(data)
    ports={}
    for key,kind,prefix in (('people','PERSON','p'),('companies','COMPANY','c')):
        for pos,e in enumerate(data[key]):
            ports[e['id']]=prefix+str(pos+1)
            db.execute('INSERT INTO customer_entities VALUES(?,?,?,?,?)',(e['id'],cid,kind,pos,e.get('logo_id','')))
    for f in data['fields']:
        if write_fields:db.execute('INSERT INTO customer_fields VALUES(?,?,?,?,?)',(f['id'],cid,ports[f['owner_id']],f['kind'],f['value']))
        db.execute('INSERT INTO customer_entity_fields VALUES(?,?,?)',(f['id'],cid,f['owner_id']))
        db.executemany('INSERT INTO customer_field_users VALUES(?,?,?,?)',[(cid,f['id'],u,n) for n,u in enumerate(f['users'])])
    db.executemany('INSERT INTO customer_company_links VALUES(?,?,?)',[(cid,p,c) for p,c in data['links']])
    db.execute('INSERT INTO customer_graph_states VALUES(?,1,?)',(cid,'HUMAN_CONFIRMED'))


def read_graph(db,cid,revision):
    state=db.execute('SELECT status FROM customer_graph_states WHERE customer_id=?',(cid,)).fetchone()
    if not state or state[0]!='HUMAN_CONFIRMED':return None
    d=dict(schema=1,revision=revision,people=[],companies=[],fields=[],links=[])
    for eid,kind,logo in db.execute('SELECT id,kind,logo_id FROM customer_entities WHERE customer_id=? ORDER BY kind,position',(cid,)):
        d['people' if kind=='PERSON' else 'companies'].append(dict(id=eid) if kind=='PERSON' else dict(id=eid,logo_id=logo))
    for fid,owner,kind,value in db.execute('SELECT f.id,e.owner_id,f.kind,f.value FROM customer_fields f JOIN customer_entity_fields e ON f.id=e.id AND f.customer_id=e.customer_id WHERE f.customer_id=? ORDER BY f.rowid',(cid,)):
        users=[r[0] for r in db.execute('SELECT entity_id FROM customer_field_users WHERE customer_id=? AND field_id=? ORDER BY position',(cid,fid))]
        d['fields'].append(dict(id=fid,owner_id=owner,kind=kind,value=value,users=users))
    d['links']=[list(r) for r in db.execute('SELECT person_id,company_id FROM customer_company_links WHERE customer_id=? ORDER BY rowid',(cid,))]
    InputGraph.validate(d);return d


def clone_for_master(data):
    """A second customer is a distinct identity even if the whole text matches."""
    d=deepcopy(data);InputGraph.validate(d)
    mapping={r['id']:new_id() for k in ('people','companies','fields') for r in d[k]}
    for key in ('people','companies'):
        for e in d[key]:e['id']=mapping[e['id']]
    for f in d['fields']:
        f.update(id=mapping[f['id']],owner_id=mapping[f['owner_id']],users=[mapping[u] for u in f['users']])
    d['links']=[[mapping[p],mapping[c]] for p,c in d['links']];d['revision']=1
    return d


def migrate(db):
    """Idempotent transaction; ambiguous legacy records remain intact for review."""
    db.executescript(SCHEMA)
    with db:
        for (cid,) in db.execute('SELECT id FROM customers WHERE id NOT IN (SELECT customer_id FROM customer_graph_states)').fetchall():
            rows=[dict(zip(('id','owner','kind','value'),r)) for r in db.execute('SELECT id,owner,kind,value FROM customer_fields WHERE customer_id=? ORDER BY rowid',(cid,))]
            try:data=from_legacy_fields(rows)
            except (ValueError,TypeError,IndexError):
                db.execute('INSERT INTO customer_graph_states VALUES(?,1,?)',(cid,'LEGACY_OWNERSHIP_REVIEW_REQUIRED'));continue
            insert_graph(db,cid,data)

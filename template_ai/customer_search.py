"""Search keys are clues only; raw values and identity remain unchanged."""
import unicodedata

FIELDS=('ANY','CODE','NAME','PHONE','LINE','IG','EMAIL','COMPANY')


def fold(value):
    return unicodedata.normalize('NFKC',str(value or '')).casefold()


def phone_key(value):
    text=unicodedata.normalize('NFKC',str(value or '')).strip()
    compact=''.join(c for c in text if c not in ' ()-+.\u00a0')
    return compact if compact and compact.isascii() and compact.isdigit() else ''


def search(store,query,offset=0,field='ANY'):
    if field not in FIELDS or type(offset) is not int or offset<0:raise ValueError('搜尋條件／分頁不合法')
    if not isinstance(query,str) or len(query)>2048:raise ValueError('搜尋字串不合法')
    q=fold(query.strip())
    if not q:return []
    db=store.db;db.create_function('ta_fold',1,fold,deterministic=True);db.create_function('ta_phone_key',1,phone_key,deterministic=True)
    # instr is literal; neither % nor _ grants wildcard/all-customer access.
    if field=='CODE':condition='instr(ta_fold(c.code),?)';args=[q]
    elif field=='NAME':condition="instr(ta_fold(c.name),?) OR (f.kind='name' AND instr(ta_fold(f.value),?))";args=[q,q]
    elif field=='PHONE':
        key=phone_key(query)
        if not key:raise ValueError('電話格式含未知標記；請改用全部欄位查詢原字串，不猜分機／國碼')
        condition="f.kind='phone' AND instr(ta_phone_key(f.value),?)";args=[key]
    elif field in ('LINE','IG','EMAIL'):condition='f.kind=? AND instr(ta_fold(f.value),?)';args=[field.lower(),q]
    elif field=='COMPANY':
        condition="f.kind='name' AND instr(ta_fold(f.value),?) AND EXISTS (SELECT 1 FROM customer_entity_fields o JOIN customer_entities e ON e.id=o.owner_id WHERE o.id=f.id AND e.kind='COMPANY')";args=[q]
    else:
        condition='instr(ta_fold(c.code),?) OR instr(ta_fold(c.name),?) OR instr(ta_fold(f.value),?)';args=[q,q,q]
        key=phone_key(query)
        if key:condition+=" OR (f.kind='phone' AND instr(ta_phone_key(f.value),?))";args.append(key)
    ids=db.execute('SELECT DISTINCT c.id FROM customers c LEFT JOIN customer_fields f ON f.customer_id=c.id WHERE ('+condition+') ORDER BY c.code LIMIT 101 OFFSET ?',(*args,offset)).fetchall()
    return [store.get(row[0]) for row in ids]

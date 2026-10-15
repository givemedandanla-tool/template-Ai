"""以穩定 ID 比較當次圖與主檔；明確選取、CAS 與單一 SQLite 交易。

集合差集決定增刪，欄位 ID 決定修改，不以姓名、電話或顯示順序猜身分。
所有寫入沿用 CustomerStore；回復也形成新版本，不回寫任何製作畫布。
"""
from copy import deepcopy
from datetime import datetime, timezone
import json

from .customers import digest
from .input_graph import InputGraph
from .model import new_id


def _index(graph):
    result = {}
    for collection in ('people', 'companies', 'fields'):
        for item in graph[collection]:
            result[collection + ':' + item['id']] = deepcopy(item)
    for person, company in graph['links']:
        result['links:' + person + ':' + company] = [person, company]
    return result


def _apply(graph, rows, selected):
    """只組合明確選取的差異，再驗證全部參照，不默默補選相依項。"""
    result = deepcopy(graph)
    for row in rows:
        if row['id'] not in selected:
            continue
        collection = row['collection']
        before, after = row['before'], row['after']
        if collection == 'links':
            result['links'] = [x for x in result['links'] if x != before]
            if after is not None:
                result['links'].append(deepcopy(after))
        else:
            identity = (after or before)['id']
            items = result[collection]
            index = next((i for i, item in enumerate(items) if item['id'] == identity), None)
            if after is None and index is not None:
                items.pop(index)
            elif index is None:
                items.append(deepcopy(after))
            else:
                items[index] = deepcopy(after)
    InputGraph.validate(result)
    g = InputGraph(result)
    if any(g.label(e['id']) == '未命名／待補' for e in result['people'] + result['companies']):
        raise ValueError('主檔人物／公司名稱不可清空；刪除實體需另選完整關聯差異')
    return result


def differences(store, snapshot, working):
    if not snapshot.get('graph'):
        raise ValueError('舊資料所有權未確認，需先核對，不能按字串重建身分')
    InputGraph.validate(working)
    current = store.get(snapshot['id'])
    old, new, live = _index(snapshot['graph']), _index(working), _index(current['graph'])
    original = InputGraph(snapshot['graph'])
    proposed = InputGraph(working)
    rows = []
    for key in sorted(old.keys() | new.keys()):
        before, after = old.get(key), new.get(key)
        if before == after:
            continue
        collection = key.split(':', 1)[0]
        if collection == 'companies' and before and after and before['logo_id'] != after['logo_id']:
            raise ValueError('Logo 版本變更須使用資產核准流程，不能由主檔聯絡同步改寫')
        if collection == 'companies' and before is None and after['logo_id']:
            raise ValueError('新增公司先核對身分，再由獨立 Logo 流程選擇資產')
        if collection == 'fields':
            affected = set()
            for graph, value in ((original, before), (proposed, after)):
                if value is not None:
                    affected.update(graph.field_impact(value['id']))
        elif collection == 'links':
            affected = set(before or after)
        else:
            eid = (before or after)['id']
            affected = set()
            for graph, value in ((original, before), (proposed, after)):
                if value is not None:
                    affected.update(graph.references(eid))
        rows.append(dict(id=key, collection=collection, before=before, after=after,
                         current=live.get(key), operation='ADD' if before is None else
                         'DELETE' if after is None else 'EDIT', affected=sorted(affected),
                         customer_id=snapshot['id'], customer_code=snapshot['code'],
                         source_revision=snapshot['revision'],
                         related_style_count=len(snapshot['styles']),
                         affected_customer_count=1))
    return dict(customer_id=snapshot['id'], customer_code=snapshot['code'],
                source_revision=snapshot['revision'], current_revision=current['revision'],
                stale=digest(current) != digest(snapshot), rows=rows,
                snapshot_digest=digest(snapshot), work_digest=digest(working))


def writeback(store, snapshot, working, selected, approved=False, source_ref='', restore_of=None):
    if not approved or not selected or len(set(selected)) != len(selected):
        raise ValueError('同步需明確勾選且確認；預設只用本次，不自動全選')
    if not isinstance(source_ref, str) or len(source_ref) > 256:
        raise ValueError('來源快照引用不合法')
    store.db.execute('BEGIN IMMEDIATE')
    try:
        plan = differences(store, snapshot, working)
        if plan['stale']:
            raise ValueError('主檔已更新；請核對原先值／目前值／本次值，不能覆寫')
        rows = {r['id']: r for r in plan['rows']}
        if set(selected) - rows.keys():
            raise ValueError('選取包含非本次差異或其他客戶項目')
        chosen = [rows[key] for key in selected]
        result = _apply(snapshot['graph'], chosen, set(selected))
        # FK 採子資料先刪、父資料後刪；所有動作都在同一交易內。
        cid = snapshot['id']
        for table in ('customer_field_users', 'customer_company_links', 'customer_entity_fields',
                      'customer_fields', 'customer_entities', 'customer_graph_states'):
            store.db.execute('DELETE FROM ' + table + ' WHERE customer_id=?', (cid,))
        from .customer_entities import insert_graph
        insert_graph(store.db, cid, result, write_fields=True)
        revision = snapshot['revision'] + 1
        count = store.db.execute('UPDATE customers SET revision=? WHERE id=? AND revision=?',
                                 (revision, cid, snapshot['revision'])).rowcount
        if count != 1:
            raise ValueError('客戶版本競爭，整個同步已取消')
        payload = dict(fields=[], graph_changes=chosen, source_ref=source_ref,
                       snapshot_digest=plan['snapshot_digest'], restore_of=restore_of,
                       created_utc=datetime.now(timezone.utc).isoformat(), outcome='COMMITTED')
        store.db.execute('INSERT INTO customer_changes VALUES(?,?,?,?)',
                         (new_id(), cid, revision, json.dumps(payload, ensure_ascii=False)))
        store.library.event(cid, 'customer_graph_selected_changes_committed')
        store.db.commit()
    except BaseException:
        store.db.rollback()
        raise
    return store.get(snapshot['id'])


def restore_plan(store, snapshot, change_id):
    change = next((x for x in store.history(snapshot['id']) if x['id'] == change_id), None)
    if not change or not change['payload'].get('graph_changes'):
        raise ValueError('此客戶沒有指定的圖同步歷史')
    current = _index(snapshot['graph'])
    reverse = []
    for row in change['payload']['graph_changes']:
        if current.get(row['id']) != row['after']:
            raise ValueError('歷史之後已有修改；先三方核對，不自動覆寫後續值')
        reverse.append({**row, 'before': row['after'], 'after': row['before']})
    working = _apply(snapshot['graph'], reverse, {r['id'] for r in reverse})
    return working, differences(store, snapshot, working)


def delete_history(store, snapshot, change_id, approved=False):
    """不把舊私人電話自動建成搜尋別名；允許明確清理不再需要的修訂。"""
    if not approved:
        raise ValueError('清理修訂紀錄需明確確認')
    store.db.execute('BEGIN IMMEDIATE')
    try:
        if digest(store.get(snapshot['id'])) != digest(snapshot):
            raise ValueError('主檔已更新，重新確認清理範圍')
        store.db.execute('DELETE FROM customer_changes WHERE id=? AND customer_id=?',
                         (change_id, snapshot['id']))
        store.db.commit()
    except BaseException:
        store.db.rollback()
        raise

"""Explainable per-work exceptions over the same persistent pipeline and facts."""
from .automatic_training import AutomaticTraining
from .training_quality import analyse_work
from .semantic_fields import review_issues


def exception_rows(library,query='',order='SMART',severity='ALL',offset=0):
    if type(offset) is not int or offset<0 or order not in ('SMART','SEVERITY','SOURCE','TYPE') or severity not in ('ALL','BLOCK','REVIEW','EXCLUDED'):raise ValueError('例外排序／篩選／頁次不合法')
    service=AutomaticTraining(library);rows=[]
    # Rank the stored queue before paging; recheck the visible works against
    # current facts. Searching never starts from an arbitrary first 100 IDs.
    where=["u.kind='AUTO_UNIT'", "COALESCE(json_extract(a.payload,'$.segmentation_state'),'')!='SUPERSEDED'", "json_extract(u.payload,'$.state')"+('=' if severity=='EXCLUDED' else '!=')+"'EXCLUDED'"]
    args=[]
    for token in query.casefold().split():
        where.append("instr(training_casefold(a.name||' '||a.id||' '||a.source_id||' '||s.original_path||' '||u.payload),?)>0");args.append(token)
    rank="CASE WHEN json_extract(u.payload,'$.state')='FAILED' THEN 3 ELSE COALESCE((SELECT max(CASE json_extract(e.value,'$.severity') WHEN 'BLOCK' THEN 3 WHEN 'REVIEW' THEN 2 ELSE 1 END) FROM json_each(u.payload,'$.issues') e),0) END DESC"
    impact="(SELECT count(*) FROM templates t WHERE json_extract(t.payload,'$.source_work_id')=a.id) DESC"
    ordering={'SMART':rank+','+impact+",a.source_id,a.id",'SEVERITY':rank+",a.source_id,a.id",'SOURCE':"a.source_id,a.id",'TYPE':"COALESCE(json_extract(u.payload,'$.issues[0].code'),''),a.source_id,a.id"}[order]
    sql="SELECT u.id FROM training_records u JOIN artworks a ON a.id=json_extract(u.payload,'$.work_id') JOIN sources s ON s.id=a.source_id WHERE "+' AND '.join(where)+' ORDER BY '+ordering+' LIMIT 100 OFFSET ?'
    units=[service.store.get('AUTO_UNIT',identity) for identity, in library.db.execute(sql,(*args,offset))]
    for unit in units:
        work=library.artwork(unit['work_id']);source=library.source(work['source_id']);issues=analyse_work(work,source)+review_issues(work,service.store.facts(work['id']),service.store.facts_state(work['id'])=='CONFIRMED')
        if work['payload'].get('segmentation_state')=='SUPERSEDED':continue
        if unit['state']=='EXCLUDED':
            if severity!='EXCLUDED':continue
            issues=[dict(code='WORK_EXCLUDED',severity='REVIEW',reason=unit['exclusion_reason'],slot_ids=[])]
        elif severity=='EXCLUDED':continue
        if unit['state']=='FAILED':issues=unit['issues']+issues
        dependencies=[r[0] for r in library.db.execute("SELECT id FROM templates WHERE json_extract(payload,'$.source_work_id')=? ORDER BY id LIMIT 200",(work['id'],))]
        total=library.db.execute("SELECT count(*) FROM templates WHERE json_extract(payload,'$.source_work_id')=?",(work['id'],)).fetchone()[0]
        for issue in issues:
            if issue['severity']=='INFO' or severity not in ('ALL','EXCLUDED') and issue['severity']!=severity:continue
            words=' '.join((work['name'],work['id'],work['source_id'],source['original_path'],source['current_path'],unit['state'],issue['code'],issue['reason'])).casefold()
            if not all(word in words for word in query.casefold().split()):continue
            rows.append(dict(unit_id=unit['id'],unit_revision=unit['revision'],work_id=work['id'],work_name=work['name'],
                work_revision=work['revision'],source_id=work['source_id'],severity=issue['severity'],code=issue['code'],reason=issue['reason'],
                slot_ids=issue['slot_ids'],template_ids=dependencies,dependency_ids_truncated=total>len(dependencies),impact_count=1+total,
                ranking_reason=f"{issue['severity']}；實際1作品＋{total}個引用模板；模板ID至多列200，未推測其他人物／公司"))
    key=lambda row:(-{'BLOCK':3,'REVIEW':2}[row['severity']],-row['impact_count'],row['source_id'],row['work_id'],row['code'])
    if order=='SOURCE':key=lambda row:(row['source_id'],row['work_id'],row['code'])
    if order=='TYPE':key=lambda row:(row['code'],row['source_id'],row['work_id'])
    return sorted(rows,key=key)[:2000]


def exclude_work(service,unit_id,revision,reason,approved=False):
    if approved is not True or not reason.strip() or len(reason)>512:raise ValueError('排除需明確作品、理由與確認，來源不刪除')
    with service.store.transaction():
        row=service.store.get('AUTO_UNIT',unit_id)
        if not row or row['revision']!=revision:raise ValueError('作品例外已更新，請重新核對')
        row.update(state='EXCLUDED',exclusion_reason=reason)
        return service.store._write('AUTO_UNIT',unit_id,row,revision,'automatic_work_explicitly_excluded')


def restore_work(service,unit_id,revision,reason,approved=False):
    if approved is not True or not reason.strip() or len(reason)>512:raise ValueError('恢復排除需明確理由與確認')
    with service.store.transaction():
        row=service.store.get('AUTO_UNIT',unit_id)
        if not row or row['revision']!=revision or row['state']!='EXCLUDED':raise ValueError('排除狀態已更新，請重新核對')
        row.update(state='WAITING_REVIEW',input_signature=None,restoration_reason=reason)
        return service.store._write('AUTO_UNIT',unit_id,row,revision,'automatic_work_explicit_exclusion_restored_pending')

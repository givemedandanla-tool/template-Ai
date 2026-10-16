"""Source-evidence major cases in the existing review records, never a second ledger."""
import copy,time
from .training_store import digest,text
from .model import new_id


def plan(service,issue_id,category,correct_example,wrong_example,severity='CRITICAL',case_id=None):
    from .quality_repairs import QualityRepairs
    if severity not in ('HIGH','CRITICAL'):raise ValueError('重大重審需明確嚴重程度')
    for value,label,limit in [(category,'問題類別',120),(correct_example,'可核對正確例子',2000),(wrong_example,'可核對錯誤例子',2000)]:text(value,label,limit)
    if correct_example.strip()==wrong_example.strip():raise ValueError('正確與錯誤例子不能相同')
    issue=QualityRepairs(service.library).current_issue(issue_id);wid=issue['evidence'].get('work_id')
    if not wid:raise ValueError('先由既有原稿／例外流程核實確切作品，不猜測失聯來源')
    proof=service.store.source_proof(wid);service.store.checked(wid,proof)
    dependencies=service.source_dependencies(wid,include_quality_evidence=True);rows=[];templates=[];proofs={};matches={r['key']:r['dependency_match'] for r in dependencies['nodes']}
    for identity in dependencies['affected_work_ids']:
        work=service.library.artwork(identity)
        if not work:continue  # Explicit missing_historical_nodes remains UNKNOWN in the frozen case.
        source_id=work['source_id'];reason=''
        try:
            if source_id not in proofs:proofs[source_id]=service.store.source_proof(identity)
            service.store.checked(identity,proofs[source_id]);verified=proofs[source_id];source_proof=dict(path=verified.path,hash=verified.hash,stat=list(verified.stat))
        except (ValueError,OSError) as error:source_proof=None;reason=str(error)
        samples=[(r[0],r[1]) for r in service.db.execute("SELECT id,revision FROM training_records WHERE kind='SAMPLE' AND json_extract(payload,'$.work_id')=? ORDER BY id",(identity,))]
        rows.append(dict(work_id=identity,source_id=source_id,pins=service.store.pins(identity),facts_revision=service.store.facts(identity)['revision'],source_proof=source_proof,samples=samples,dependency_match=matches['WORK:'+identity],precheck='SOURCE_CURRENT' if source_proof else 'SOURCE_UNKNOWN',reason=reason))
    for node in dependencies['nodes']:
        if not node['key'].startswith('TEMPLATE:'):continue
        _,identity,version=node['key'].split(':');snapshot=service.library.object_snapshot('TEMPLATE',identity)
        if snapshot['payload']['version']!=int(version):raise ValueError('受影響模板版次已變更，需重新核對範圍')
        templates.append(dict(template_id=identity,version=int(version),snapshot_digest=digest(snapshot),dependency_match=node['dependency_match']))
    result=dict(mode='SOURCE_EVIDENCE',case_id=case_id or new_id(),issue_id=issue_id,issue_digest=digest(issue),work_id=wid,category=category,correct_example=correct_example,wrong_example=wrong_example,severity=severity,rows=rows,templates=templates,dependency_digest=dependencies['digest'],dependency_nodes=dependencies['nodes'],missing_historical_nodes=dependencies['missing_historical_nodes'],unknown_unrecorded_dependencies=True,whole_corpus_safe=False,coverage=dict(registered_sources=service.db.execute('SELECT count(*) FROM sources').fetchone()[0],registered_works=service.db.execute('SELECT count(*) FROM artworks').fetchone()[0],affected_sources=len({r['source_id'] for r in rows}),affected_works=len(rows),affected_templates=len(templates),known_nodes=len(dependencies['nodes']),known_edges=len(dependencies['edges']),known_graph_complete=dependencies['complete_known_graph']))
    result['digest']=digest(result);return result


def confirm(service,value,actor,reason,approved=False):
    if approved is not True:raise ValueError('需核對使用者證據、影響範圍與未知部分，明確啟動重審')
    text(actor,'重審發起人',120);text(reason,'隔離依據',2000)
    if value.get('digest')!=digest({k:v for k,v in value.items() if k!='digest'}):raise ValueError('重大重審證據／精確範圍已變更')
    with service.store.transaction():
        existing=service.store.get('QUALITY_MAJOR_RECHECK',value['case_id'])
        if existing:
            if existing.get('plan_digest')!=value['digest']:raise ValueError('此案件ID已對應其他範圍，未覆寫')
            return dict(existing,replayed=True)
        fresh=plan(service,**{k:value[k] for k in ('issue_id','category','correct_example','wrong_example','severity','case_id')})
        if fresh['digest']!=value['digest']:raise ValueError('來源／作品／版本／歷史依賴已變更，未啟動隔離')
        case_id=value['case_id'];now=time.time()
        for row in value['rows']:
            service.store._write('QUALITY_WORK_QUARANTINE',digest([case_id,row['work_id']]),dict(row,case_id=case_id,state='REVIEW_REQUIRED',review_state='UNSCANNED',actor=actor,reason=reason,at=now),0,'major_source_evidence_work_quarantined')
            for identity,revision in row['samples']:
                sample=service.store.get('SAMPLE',identity)
                if sample and sample['state']=='APPROVED':
                    sample.update(state='QUARANTINED',quality_recheck_case=case_id,transition_actor=actor,transition_reason=reason);service.store._write('SAMPLE',identity,sample,revision,'major_source_evidence_sample_quarantined')
        for row in value['templates']:
            service.store._write('QUALITY_TEMPLATE_QUARANTINE',digest([case_id,'TEMPLATE',row['template_id'],row['version']]),dict(row,case_id=case_id,state='REVIEW_REQUIRED',review_state='UNSCANNED',actor=actor,reason=reason,at=now),0,'major_source_evidence_template_availability_suspended')
        header={k:copy.deepcopy(v) for k,v in value.items() if k not in ('rows','templates','digest')}
        return service.store._write('QUALITY_MAJOR_RECHECK',case_id,dict(plan=header,plan_digest=value['digest'],affected_works=len(value['rows']),affected_templates=len(value['templates']),state='REVIEW_REQUIRED',actor=actor,reason=reason,at=now,completed=False,old_closure_receipts_preserved=True,models_decontaminated=False,formal_versions_changed=False),0,'major_source_evidence_case_started_not_completed')


def source_or_template_blocked(store,template):
    if not store.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='training_records'").fetchone():return False
    from .quality_rechecks import blocked
    if template.source_work_id and blocked(store,template.source_work_id):return True
    return bool(store.db.execute("SELECT 1 FROM training_records WHERE kind='QUALITY_TEMPLATE_QUARANTINE' AND json_extract(payload,'$.template_id')=? AND json_extract(payload,'$.version')=? AND json_extract(payload,'$.state')='REVIEW_REQUIRED' LIMIT 1",(template.id,template.version)).fetchone())


def current_condition(candidate):
    import sqlite3
    from pathlib import Path
    from types import SimpleNamespace
    root=candidate.risk_context.get('source_trust_root')
    if not root:return []
    connection=None
    try:
        connection=sqlite3.connect((Path(root)/'library.sqlite3').resolve().as_uri()+'?mode=ro',uri=True,timeout=.05)
        pending=source_or_template_blocked(SimpleNamespace(db=connection),candidate.template)
        return [dict(id='CURRENT_MAJOR_REVIEW_TRUST',status='UNKNOWN' if pending else 'PASS',reason='重大共通錯誤重審尚未解除此來源／模板版本隔離' if pending else '目前來源／模板版本未受重大重審隔離')]
    except (sqlite3.Error,OSError,ValueError):return [dict(id='CURRENT_MAJOR_REVIEW_TRUST',status='UNKNOWN',reason='目前重大重審紀錄無法讀回，未沿用舊通過狀態')]
    finally:
        if connection is not None:connection.close()

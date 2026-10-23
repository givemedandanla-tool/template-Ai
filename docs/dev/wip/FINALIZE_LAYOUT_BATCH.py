"""Publish metadata only AFTER a complete immutable layout batch and actual shell exit0.
Never run this on LAYOUT001/002 failures. No app/source changes; no main merge/EXE.
"""
import argparse,hashlib,json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'tools'))
from dev_common import manifest,manifest_digest,contract_digest,write_json
from dev_governance import render,test_ids
D=ROOT/'docs/dev';NEW={'UI-055':11,'UI-056':8,'UI-057':9,'UI-058':10}

def read(path):return json.loads(path.read_text())

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True);parser.add_argument('--parent-exit',type=Path,required=True);args=parser.parse_args()
    folder=ROOT/'docs/evidence/runs'/args.run_id;run=read(folder/'run.json');records=read(folder/'tests.json');modules=read(folder/'test-modules.json');claims=read(folder/'claims.json');state=read(D/'STATE.json');registry=read(D/'REQUIREMENTS.json');contract=read(D/'FIXED70_REMAINING28_CONTRACT.json');parent_audit=read(folder/'remaining28-full-parent-audit.json');expected=test_ids(ROOT)
    assert args.run_id not in ('RUN-REMAINING28-LAYOUT-001','RUN-REMAINING28-LAYOUT-002'),'Interrupted/failed history is never completion evidence'
    assert args.parent_exit.read_text().strip()=='0','Actual owned parent exit0 required'
    assert run['id']==args.run_id and run['status']=='PASS' and run['test_count']==run['passed']==len(expected)
    assert run['planned_test_count']==len(expected) and run['not_completed_test_count']==0
    assert {r['id'] for r in records}==expected and len(records)==len(expected) and all(r['status']=='PASS' for r in records)
    assert run['source_unchanged'] and run['capture_exit_code']==0 and run['unhandled_runtime_errors']==0
    assert manifest_digest(manifest(code_only=True))==run['source_manifest_sha256']
    assert modules['planned_tests']==modules['completed_tests']==len(expected) and len(modules['modules'])==len({t.split('.')[0] for t in expected})
    assert all(m['exit_code']==0 and m['healthy'] and not m['timed_out'] and not m['remaining_owned_pids'] and not m['missing_test_ids'] and not m['unexpected_test_ids'] and not m['duplicate_ids'] and not m['failure'] for m in modules['modules'])
    assert parent_audit['verified_count']==12 and not parent_audit['all_28_complete'] and parent_audit['source_commit']==run['source_commit']
    actual_parents=[p for p in parent_audit['parents'] if p['software_self_verified']];assert len(actual_parents)==12 and sum(len(p['clauses']) for p in actual_parents)==120
    pending=state['pending_revalidation_ids'];assert len(set(pending))==150 and set(NEW)<=set(pending)
    for row in registry['requirements']:
        if row['id'] not in pending:continue
        actual=[c for c in claims if c['requirement_id']==row['id']]
        assert actual and len(actual)==len(row['acceptance']) and all(c['status']=='PASS' and c['contract_sha256']==contract_digest(row) for c in actual),row['id']
        if row['id'] in NEW:assert row['full_acceptance_registered'] and len(row['acceptance'])==NEW[row['id']]
    for name,pin in run['attachments'].items():
        path=folder/name;assert path.stat().st_size==pin['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest()==pin['sha256'],name
    native=read(folder/'layout-risk-session-capture.json');assert native['status']=='PASS' and not native['qt_uncaught'] and len(native['screens'])==13 and native['preexisting_manual_layout_protected'] and native['encrypted_recovery_preserves_current_manual_geometry']
    assert all(name in run['attachments'] for name in native['screens'])
    ref=str((folder/'run.json').relative_to(ROOT));audit=read(D/'REMAINING28_CLAUSE_AUDIT.json');assert len(audit['parents'])==8 and not(set(NEW)&{p['id'] for p in audit['parents']}),'Already finalized; do not repeat'
    writes={}
    for row in registry['requirements']:
        if row['id'] not in pending:continue
        row.update(completed=True,status='VERIFIED',review_level='SELF_VERIFIED',evidence_run=ref)
        if row['id'] in NEW:
            row['first_full_completion_evidence']=ref;row['next_step']='完整原始軟體條款SELF；Linux匿名合成及實際來源/原生GUI。非生產準確率、native Illustrator或指定Windows參考機資格；下一UI059。'
    counts=Counter(r['status'] for r in registry['requirements'] if r['kind']=='topic');assert counts==dict(VERIFIED=56,PARTIAL=16,DEFERRED=3),counts
    for pid in NEW:
        coverage=read(D/(pid.replace('-','')+'_CLAUSE_COVERAGE.json'));assert len(coverage['clauses'])==NEW[pid]
        audit['parents'].append(dict(id=pid,source_clauses_sha256=coverage['source_clauses_sha256'],implementation=coverage['implementation'],clauses=coverage['clauses'],status='SELF_VERIFIED_SOFTWARE',limits=coverage['limits'],evidence_run=ref,source_commit=run['source_commit']))
        audit['unregistered_parent_ids'].remove(pid);coverage.update(status='SELF_VERIFIED_SOFTWARE',evidence_run=ref,source_commit=run['source_commit']);writes[D/(pid.replace('-','')+'_CLAUSE_COVERAGE.json')]=coverage
    for item in audit['parents']:item.update(evidence_run=ref,source_commit=run['source_commit'])
    done=[p['id'] for p in audit['parents']];assert len(done)==12 and len(audit['unregistered_parent_ids'])==16 and sum(len(p['clauses']) for p in audit['parents'])==120
    contract.update(verified_parent_count=12,remaining_parent_count=16)
    for item in contract['acceptance']:
        if item['parent'] in done:item.update(status='VERIFIED',unresolved=[],evidence_run=ref)
    full=read(D/'FULL70_PROGRESS.json')
    for row in full['rows']:
        if row['id'] in done:row.update(state='CLOSED_FULL_SOFTWARE_SELF_VERIFIED',evidence=ref)
    full.update(closed=54,remaining=16,latest_evidence=ref)
    queue=read(D/'REMAINING28_EXECUTION_QUEUE.json');queue.update(completed_historical=done,active_parent='UI-059',remaining_after_active=[p for p in contract['target_parent_ids'] if p not in done and p!='UI-059'],implemented_pending_full_formal=[],remaining_to_fully_implement=[p for p in contract['target_parent_ids'] if p not in done])
    for row in queue['items']:
        if row['id'] in done:row.update(status='SELF_VERIFIED_SOFTWARE',evidence_run=ref)
    note=f'剩餘28已完成12父題／120原條款；{len(expected)}/{len(expected)}正式PASS、140健康owned modules、0skip/0Qt、capture0、source unchanged、actual parent exit0。全75：56 VERIFIED／16 PARTIAL／3 DEFERRED；固定70：54閉合／16仍部分。CORE87／GOV7另計。下一UI059與剩餘16，總目標尚未完成。'
    road=read(D/'PROJECT_ROADMAP.json')
    for row in road['topics']:
        if row['id'] in NEW:row.update(current_status='VERIFIED',review_level='SELF_VERIFIED',registered_acceptance_reference='docs/dev/REQUIREMENTS.json#'+row['id'],next_step='完整原軟體條款SELF；'+ref+'。Linux匿名合成，非指定Windows/nativeAI/生產效能資格；下一UI059。')
        if row['current_status']=='VERIFIED':row['software_evidence']=ref
    road.update(current_parent_counts=dict(counts),latest_status_note=note)
    state.update(previous_evidence_run=state.get('previous_evidence_run'),latest_evidence_run=ref,pending_revalidation_ids=[],implementation_pending_original_parents=[],next_work_package='Implement UI059 original10 using UI059_EXECUTION_PLAN; continue remaining16 without milestone stop',current_work_package='UI059 dependency/recompute/manual-conflict/undo',current_work=note,next_step='Complete ordinary GitHub publication/readback/Gate, then UI059 and remaining16',planned_evidence_run=None)
    state['formal_execution_watch'].update(status='COMPLETED_PASS_ACTUAL_EXIT_0',source_commit=run['source_commit'],source_frozen=True,actual_parent_exit=0)
    state['last_formal_validation']=dict(id=run['id'],source_commit=run['source_commit'],tests=len(expected),passed=len(expected),skipped=0,qt_uncaught=0,capture_exit=0,actual_parent_exit=0)
    state['remaining28_result']=dict(verified=12,remaining=16,new_original_parents=0,revised_original_parents=12,completed_original_parent_ids=done,parent_counts=dict(verified=56,partial=16,deferred=3),core_verified=87,governance_verified=7,full_original_clauses=120)
    state['publication_status']=dict(run=run['id'],remote_verified=False,publication_scope_gate='PENDING_ACTUAL_CHECK',new_run_all_attachments_published=False,previous_explicit_media_exceptions_unchanged=True)
    verification=dict(status='PASS_MILESTONE_12_OF_28_NOT_FINAL_GOAL',goal_complete=False,target_parents=28,verified=12,remaining=16,verified_parent_ids=done,source_commit=run['source_commit'],evidence_run=ref,full_original_clauses=120,tests=len(expected),passed=len(expected),skipped=0,unhandled_runtime_errors=0,capture_exit_code=0,source_unchanged=True,requirements_revalidated=150,attachments=len(run['attachments']),limits=['Current authored synthetic Linux/native GUI self-verification; no independent review, private Illustrator corpus or specified Windows reference hardware qualification'])
    writes.update({D/'REQUIREMENTS.json':registry,D/'FIXED70_REMAINING28_CONTRACT.json':contract,D/'REMAINING28_CLAUSE_AUDIT.json':audit,D/'FULL70_PROGRESS.json':full,D/'REMAINING28_EXECUTION_QUEUE.json':queue,D/'PROJECT_ROADMAP.json':road,D/'STATE.json':state,D/'REMAINING28_LAYOUT_VERIFICATION.json':verification})
    for path,value in writes.items():write_json(path,value)
    lines=['# 全75父題狀態與接續順序','',note,'','|順序組|原父題|名稱|狀態|下一步／證據|','|---|---|---|---|---|']
    for row in sorted(road['topics'],key=lambda r:(r['order_group'],r['id'])):lines.append('|'+ '|'.join(str(v).replace('|','／').replace('\n',' ') for v in (row['order_group'],row['id'],row['title'],row['current_status'],row['next_step']))+'|')
    (D/'PROJECT_ROADMAP.md').write_text('\n'.join(lines)+'\n');(D/'FULL70_PROGRESS.md').write_text('# 固定70進度\n\n'+note+'\n\n|原父題|狀態|證據|\n|---|---|---|\n'+'\n'.join('|'+r['id']+'|'+r['state']+'|'+str(r.get('evidence',''))+'|' for r in full['rows'])+'\n')
    for name in ('PARTIAL_70_GAP_REPORT.md','PROJECT_GOAL.md'):
        path=D/name;text=path.read_text();path.write_text('> '+note+'\n'+text[text.index('\n'):])
    with (D/'ACTIVE_DEVELOPMENT_HANDOFF.md').open('a') as stream:stream.write('\n## Actual layout batch closure; publication Gate pending\n\n'+note+' Source '+run['source_commit']+'; raw failures LAYOUT001/002 retained. New batch attachments must all use ordinary GitHub publication, then actualrequire-evidence/publication-scope Gate. Do not re-run this finalizer.\n')
    with (D/'WORK_LOG.md').open('a') as stream:stream.write('\n## Actual layout batch self-verification\n\n'+note+' Source '+run['source_commit']+'; exact150claim hashes and all attachments verified; pending ordinary remote publication Gate. Continue UI059.\n')
    render();print(json.dumps(dict(status=verification['status'],source=run['source_commit'],tests=len(expected),claims=150,parents=12,clauses=120,attachments=len(run['attachments']))))

if __name__=='__main__':main()

"""Close only actual source-bound scoped evidence; keep all parent FULL clauses unfinished."""
import argparse,json
from pathlib import Path
from dev_common import ROOT,read_json,write_json,contract_digest
from dev_governance import verify_run,render
from dev_progress import snapshot

def finish(run_id):
    runpath=f'docs/evidence/runs/{run_id}/run.json';run,results=verify_run(ROOT,runpath)
    if run['status']!='PASS' or run['passed']!=run['test_count'] or not all(r['status']=='PASS' for r in results.values()):raise ValueError('全回歸未PASS／有跳過，不可提升狀態')
    claims=read_json(ROOT/Path(runpath).parent/'claims.json');audit=read_json(ROOT/Path(runpath).parent/'seventy-parent-audit.json')
    if not audit['all_scopes_pass'] or audit['source_commit']!=run['source_commit'] or len(audit['new_scopes'])!=17:raise ValueError('17實作範圍對帳未完成')
    registry=read_json(ROOT/'docs/dev/REQUIREMENTS.json');contract=read_json(ROOT/'docs/dev/SEVENTY_PARENTS_CONTRACT.json')
    for r in registry['requirements']:
        if r['kind']=='topic' or r['status']=='NOT_IMPLEMENTED':continue
        matches=[c for c in claims if c['requirement_id']==r['id']]
        if len(matches)!=len(r['acceptance']) or not all(c['status']=='PASS' and c['contract_sha256']==contract_digest(r) for c in matches):raise ValueError('具名要求／契約證據不足：'+r['id'])
        r.update(completed=True,status='VERIFIED',review_level='SELF_VERIFIED',evidence_run=runpath,next_step='具名範圍完成；父題剩餘條款不消失，後續改碼須重驗')
    byid={r['id']:r for r in registry['requirements']}
    for s in contract['scopes']:
        if not byid[s['id']]['completed']:raise ValueError('實作子項尚未完成')
        parent=byid[s['parent']]
        if parent['status']!='NOT_IMPLEMENTED':raise ValueError('原父題基準已改變，需重做差異對帳')
        parent.update(status='PARTIAL',completed=False,review_level='SELF_VERIFIED_SUBSET_ONLY',evidence_run=runpath,next_step=s['remaining']+'；原FULL全部條款保留，不代表完整實作')
        s.update(status='SCOPED_SELF_VERIFIED',source_commit=run['source_commit'],evidence=runpath)
    topics=[r for r in registry['requirements'] if r['kind']=='topic'];counts={status:sum(r['status']==status for r in topics) for status in ('PARTIAL','NOT_IMPLEMENTED','BLOCKED','DEFERRED','VERIFIED')}
    if counts!={'PARTIAL':70,'NOT_IMPLEMENTED':0,'BLOCKED':2,'DEFERRED':3,'VERIFIED':0}:raise ValueError('原75父題目標或排除集合不符')
    write_json(ROOT/'docs/dev/REQUIREMENTS.json',registry);write_json(ROOT/'docs/dev/SEVENTY_PARENTS_CONTRACT.json',contract)
    p=ROOT/'docs/dev/SEVENTY_PARENTS_PUBLICATION.json';pub=read_json(p);pub['runs'][run_id]={'source_commit':run['source_commit'],'attachments':{name:r for name,r in run['attachments'].items() if Path(name).suffix in ('.png','.jpg','.pdf')}};write_json(p,pub)
    state=read_json(ROOT/'docs/dev/STATE.json');state.update(active_task='SEVENTY-PARENTS-FORMAL-PASS-PENDING-REMOTE',latest_evidence_run=runpath,latest_progress_snapshot='docs/dev/progress/PROGRESS-20261015-SEVENTY-END.json',next_tasks=[{'id':'SEVENTY-FINAL','status':'PENDING_REMOTE','action':'官方最終scope checkpoint/API讀回、乾淨text Gate；70部分非70完整'}]);state['seventy_parents']={'baseline_partial':53,'target_partial':70,'achieved_partial':70,'new_scoped_core':16,'new_governance':1,'source_commit':run['source_commit'],'evidence':runpath,'tests':run['passed'],'status':'FORMAL_PASS_PENDING_REMOTE'};state['evidence_publication'].update(manifest='docs/dev/SEVENTY_PARENTS_PUBLICATION.json',local_formal=f"{run['passed']}PASS/0SKIP/{len(run['attachments'])}local attachments/source unchanged",new_media_uploads='NONE');write_json(ROOT/'docs/dev/STATE.json',state)
    snapshot(ROOT,'PROGRESS-20261015-SEVENTY-END','docs/dev/progress/PROGRESS-20261015-SEVENTY-BEGIN.json');render(ROOT)
    print(json.dumps({'parents':counts,'core_verified':sum(r['kind']=='core' and r['completed'] for r in registry['requirements']),'gov_verified':sum(r['kind']=='governance' and r['completed'] for r in registry['requirements']),'tests':run['passed']}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run');finish(p.parse_args().run)

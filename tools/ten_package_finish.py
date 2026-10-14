import argparse,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tools'))
from dev_common import write_json,contract_digest
from dev_governance import verify_run,render
from dev_progress import snapshot
parser=argparse.ArgumentParser();parser.add_argument('number',type=int);parser.add_argument('run');parser.add_argument('--saved');parser.add_argument('--checkpoint');args=parser.parse_args()
n=args.number;runpath='docs/evidence/runs/'+args.run+'/run.json';state=json.loads((root/'docs/dev/STATE.json').read_text());pack=state['ten_packages']['packages'][n-1]
if args.saved:
 checkpoint_id=args.checkpoint or f'CP-20261014-TEN-P{n:02}-VERIFIED';receipt=json.loads((root/'docs/checkpoints'/f'{checkpoint_id}.receipt.json').read_text());assert receipt['phase']=='REMOTE_VERIFIED' and receipt['snapshot_commit']==args.saved
 pack.update(status='COMPLETED_SAVED_SCOPE',snapshot_commit=args.saved,checkpoint='docs/checkpoints/'+(args.checkpoint or f'CP-20261014-TEN-P{n:02}-VERIFIED')+'.receipt.json');state['ten_packages']['completed']=n
 state['next_tasks']=[{'id':state['ten_packages']['packages'][n]['id'] if n<10 else 'TEN-FINAL','status':'CONTINUE','action':'直接下一包；不等待HUMAN' if n<10 else '10包正式整合／保存範圍讀回，完整父需求仍按原清單續做'}]
else:
 run,results=verify_run(root,runpath);assert run['status']=='PASS' and run['passed']==run['test_count'] and all(r['status']=='PASS' for r in results.values())
 claims=json.loads((root/Path(runpath).parent/'claims.json').read_text())
 p=root/'docs/dev/TEN_PACKAGES_PUBLICATION.json';pub=json.loads(p.read_text());pub['runs'][run['id']]={'source_commit':run['source_commit'],'attachments':{name:item for name,item in run['attachments'].items() if Path(name).suffix in ('.png','.jpg','.pdf')},'media_publication':'LOCAL_WITH_EXACT_HASH; metadata mandatory; existing identical blobs may be retained, no binary upload retry'};write_json(p,pub)
 p=root/'docs/dev/REQUIREMENTS.json';registry=json.loads(p.read_text())
 for r in registry['requirements']:
  if r['kind']!='topic' and r['status']!='NOT_IMPLEMENTED' and r['acceptance'] and all(a['tests'] and all(results.get(t,{}).get('status')=='PASS' for t in a['tests']) for a in r['acceptance']):
   matching=[c for c in claims if c['requirement_id']==r['id']];assert len(matching)==len(r['acceptance']) and all(c['contract_sha256']==contract_digest(r) and c['status']=='PASS' for c in matching)
   r.update(status='VERIFIED',completed=True,review_level='SELF_VERIFIED',evidence_run=runpath)
 parents={pid for r in registry['requirements'] if r['id'] in pack['requirements'] for pid in r['parents']}
 for r in registry['requirements']:
  if r['id'] in parents and r['status']=='NOT_IMPLEMENTED':r['status']='PARTIAL'
 write_json(p,registry);state.update(latest_evidence_run=runpath,product_version='0.1.'+str(14+n));pack.update(status='FORMAL_PASS_PENDING_REMOTE',source_commit=run['source_commit'],evidence=runpath,tests=run['passed']);state['latest_progress_snapshot']=f'docs/dev/progress/PROGRESS-20261014-TEN-P{n:02}-END.json'
 baseline='docs/dev/progress/PROGRESS-20261014-TEN-BEGIN.json' if n==1 else f'docs/dev/progress/PROGRESS-20261014-TEN-P{n-1:02}-END.json'
 snapshot(root,f'PROGRESS-20261014-TEN-P{n:02}-END',baseline)
 p=root/'docs/dev/WORK_LOG.md';s=p.read_text();p.write_text('# 開發工作紀錄\n\n## 十包 '+str(n)+'/10 正式驗收\n\n'+args.run+'／source '+run['source_commit']+'：'+str(run['passed'])+'PASS／0SKIP，'+str(len(run['attachments']))+'本機附件、source unchanged。'+','.join(pack['requirements'])+'及全部已實作CORE／GOV具名再驗。原GUI／media本機保留、source-bound hash清單與metadata/tests/JUnit/claims/audit/CP保存；不宣稱全media已上傳。保存後直接下一包。\n\n'+s.removeprefix('# 開發工作紀錄\n'))
write_json(root/'docs/dev/STATE.json',state);render(root)
p=root/'docs/dev/HANDOFF.md';p.write_text('# 十包最新接續：'+str(state['ten_packages']['completed'])+'/10已保存；'+pack['id']+' '+pack['status']+'\n\n最新source與驗收 '+runpath+'；按STATE下一包與TEN契約直接續做，不能把既有包／checkpoint重算。CORE基準45，本輪目標+20；每包2CORE。原75父需求保持完整缺口，SELF_VERIFIED／Linux／匿名合成，無EXE／代理／main合併。metadata-first source-bound政策，原失敗與本機媒體保留。\n\n'+p.read_text())
print(json.dumps({'package':n,'status':pack['status'],'completed_saved':state['ten_packages']['completed']}))

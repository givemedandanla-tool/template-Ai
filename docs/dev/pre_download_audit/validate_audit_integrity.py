"""Validate ledger identity and evidence references, not the truth of every proof."""
import collections,hashlib,json,re,subprocess
from pathlib import Path
F=Path(__file__).resolve().parent;ROOT=F.parents[2];rows=[json.loads(x) for x in (F/'diagnostic-ledger.jsonl').read_text().splitlines()];assert len(rows)==11798;assert len({r['id'] for r in rows})==len(rows);assert len({(r['scope'],r['fingerprint'],r['occurrence']) for r in rows})==len(rows);assert not any(r['status']=='UNREVIEWED' for r in rows)
comparison={};files={};cache={};fragments=0
for scope in ('application','tools','tests'):
 path=ROOT/f'docs/dev/debug_tooling/baselines/{scope}.json';baseline=json.loads(path.read_text());left=collections.Counter(r['fingerprint'] for r in baseline['findings'] if r['tool']=='pyright');right=collections.Counter(r['original']['fingerprint'] for r in rows if r['scope']==scope);assert left==right;comparison[scope]=dict(baseline_count=sum(left.values()),ledger_count=sum(right.values()),missing=0,extra=0,baseline_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
for r in rows:
 assert r['evidence'],r['id']
 for ref in r['evidence']:
  name,_,fragment=ref.partition('#');name=re.sub(r':\d+$','',name);q=F/name
  if not q.exists():q=ROOT/name
  assert q.exists(),(r['id'],ref)
  if q.is_file() and q not in files:files[q]=hashlib.sha256(q.read_bytes()).hexdigest()
  if fragment and q.suffix=='.json':
   if q not in cache:cache[q]=json.dumps(json.loads(q.read_text()),ensure_ascii=False)
   assert fragment in cache[q],(r['id'],ref);fragments+=1
commits=sorted({r['fix_commit'] for r in rows if r['status']=='FIXED_AND_VERIFIED'})
for c in commits:subprocess.run(['git','cat-file','-e',c+'^{commit}'],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
result=dict(status='PASS',original_occurrences=len(rows),original_multiset=comparison,unique_ids=True,unique_occurrence_keys=True,statuses=dict(collections.Counter(r['status'] for r in rows)),evidence_files=len(files),literal_json_fragments_resolved=fragments,all_evidence_files_exist=True,fix_commits_exist=commits,scope='Identity/reference integrity only; each proof has its own bounded source/runtime qualification, not all branches/inputs.',file_hashes={str(q.relative_to(ROOT)):h for q,h in files.items()})
(F/'ledger-integrity-final.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('PASS',len(rows),'original occurrences, references resolved')
# All exact clones remain the original seven; carry source-bounded reviewed decisions.
backlog=json.loads((ROOT/'docs/dev/debug_tooling/BACKLOG.json').read_text());prior={r['fingerprint']:r for r in backlog['clone_reviews']};reviews=[]
for scope in ('application','tools','tests'):
 profile=F/f'final-release-{scope}-standard-002/report.json';report=json.loads(profile.read_text())
 for r in report['findings']:
  if r['tool']!='jscpd':continue
  old=prior[r['fingerprint']];locations=[]
  for name,span in zip(r['paths'],r['ranges']):
   p=ROOT/name;locations.append(dict(path=name,range=span,source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),snippet='\n'.join(p.read_text().splitlines()[span[0]-1:span[1]])))
  reviews.append(dict(finding=r,status='REVIEWED',decision=old['decision'],reason=old['reason'],callers=old.get('callers'),locations=locations,profile=profile.relative_to(F).as_posix(),baseline_refreshed=False))
assert len(reviews)==7
(F/'exact-clone-final-review.json').write_text(json.dumps(dict(status='ALL_7_REVIEWED',new_exact_groups=0,reviews=reviews),ensure_ascii=False,indent=2)+'\n');print('7 exact clone groups reviewed; original baseline unchanged')

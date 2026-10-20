"""Bind local supported-case execution without promoting deferred requirements."""
import ast,collections,hashlib,json,subprocess
from pathlib import Path
F=Path(__file__).resolve().parent;ROOT=F.parents[2];run=F/'full-regression-final-009';summary=json.loads((run/'summary.json').read_text());assert summary['software_execution']=='PASS' and summary['planned']==1920 and summary['original_test_ids_preserved'];tests=json.loads((run/'tests.json').read_text());status={r['id']:r['status'] for r in tests};source=json.loads((run/'source.json').read_text());assert all(v=='PASS' for v in status.values())
# Requirement status is a historical qualification, separate from current case execution.
p=F/'requirements-test-matrix.json';matrix=json.loads(p.read_text());missing=set();empty=[]
for requirement in matrix['requirements']:
 for clause in requirement['clauses']:
  ids=clause['tests'];missing.update(set(ids)-status.keys())
  if not ids:empty.append(clause['id'])
  clause['local_execution']=dict(run='full-regression-final-009',source=source['commit'],results={t:status.get(t,'MISSING') for t in ids},qualification='Only listed actual cases. Original requirement/parent qualification unchanged; no exhaustive clause coverage claim.')
assert not missing
matrix['current_binding']=dict(source=source['commit'],catalog_size=len(status),original_catalog_preserved=True,requirements=len(matrix['requirements']),missing_test_ids=[],clauses_without_test_links=empty,prior_statuses_unchanged=True,formal_remote_governance='BLOCKED_CURRENT_SOURCE_REMOTE_PROVENANCE_NOT_AVAILABLE')
p.write_text(json.dumps(matrix,ensure_ascii=False,indent=2)+'\n')
# Refresh exact input/version entry anchors and their actual candidate test results.
p=F/'entry-path-audit.json';entries=json.loads(p.read_text());cache={}
for entry in entries['entries']:
 for anchor in entry['source_anchors']:
  file=ROOT/anchor['path']
  if file not in cache:cache[file]=ast.parse(file.read_text())
  candidates=[n for n in ast.walk(cache[file]) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==anchor['function']];assert candidates,anchor
  node=min(candidates,key=lambda n:abs(n.lineno-anchor['line']));anchor.update(line=node.lineno,source_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),scope='Source anchor exists; related cases do not establish all branch coverage')
 ids=entry['candidate_regression_test_ids'];assert ids and not set(ids)-status.keys();entry['runtime_status']='LISTED_CASES_PASS_CURRENT_SOURCE';entry['local_binding']=dict(run='full-regression-final-009',source=source['commit'],results={t:status[t] for t in ids});entry['followup']='Native Windows/private corpus/physical print remain external; supported local cases complete.'
entries['final_binding']=dict(source=source['commit'],entry_paths=len(entries['entries']),anchors=sum(len(x['source_anchors']) for x in entries['entries']),qualification='Existing core/desktop input paths only; web/mobile deferred; fixed/family/confirmed versions and customer constraints retained')
p.write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n')
# A fresh connection inventory is not an execution-coverage claim.
connections=[]
for file in sorted((ROOT/'template_ai').glob('*.py')):
 tree=ast.parse(file.read_text());digest=hashlib.sha256(file.read_bytes()).hexdigest()
 for n in ast.walk(tree):
  if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='connect':connections.append(dict(path=file.relative_to(ROOT).as_posix(),line=n.lineno,signal=ast.unparse(n.func.value)[:220],target=ast.unparse(n.args[0])[:220] if n.args else None,source_sha256=digest))
(F/'gui-signal-inventory-final.json').write_text(json.dumps(dict(source=source['commit'],count=len(connections),qualification='Static signal/callback inventory, not proof every signal was separately triggered; actual native/stock captures recorded separately',connections=connections),ensure_ascii=False,indent=2)+'\n')
# Fault matrix keeps explicit assertions and exact case statuses; name selection is only an index.
script=(F/'build_fault_matrix.py').read_text().replace("full-regression-005/catalog.json","full-regression-final-009/catalog.json").replace("runtime_status='FINAL_FULL005_PENDING'","runtime_status='PASS'").replace("Pending exact full005 results; root7 test/fix results must be added separately","full-regression-final-009/tests.json actual1920PASS, including root7/root4/root10 regressions")
exec(compile(script,str(F/'build_fault_matrix.py'),'exec'),dict(__file__=str(F/'build_fault_matrix.py'),__name__='__audit_final_binding__'))
# Current/new/profile-only findings all dispositioned, retain original unresolved type debts.
p=F/'release-diagnostic-comparison.json';diagnostics=json.loads(p.read_text());assert diagnostics['unreviewed']==0
for row in diagnostics['findings']:
 if row['status']=='ORIGINAL_REVIEW_LINKED':continue
 path=Path(row['finding']['path']);module=path.stem
 if row['finding']['path'].startswith('tests/'):
  related={t:v for t,v in status.items() if t.split('.')[0]==module};assert related,(row['id'],module);row['current_stock_execution']=dict(run='full-regression-final-009',results=related,not_claimed='All-expression or arbitrary-input coverage')
 elif row['finding']['path'].startswith('tools/capture_'):
  row['current_stock_capture']='gui-stock-captures-final-002/jobs.json exact original authored command; no instrumented window'
 else:row['current_stock_execution']='full-regression-final-009 and source/producer proof; current exact expressions reviewed, not all possible branches'
diagnostics['final_binding']=dict(run='full-regression-final-009',source=source['commit'],unreviewed=0,original_baselines_unchanged=True,not_a_zero_warning_claim=True)
p.write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2)+'\n')
# Archive the earlier38 findings as historical, with the corrected targeted root7 proof.
p=F/'new-diagnostics.json';older=json.loads(p.read_text());older['superseded_current_review']='release-diagnostic-comparison.json';older['historical_profile_only']=True
for row in older['findings']:
 if row['finding']['path'].endswith('text_policy_dialog.py'):
  row.update(status='FIXED_AND_VERIFIED',review='Corrected exact confirmation fixtures on isolated old92977b77:2FAIL1ERROR; fixed source3PASS and current full1920PASS. Earlier max_tracking=0 fixture never reached confirmation and is rejected as evidence.',evidence=['text-policy-context-before-corrected.log','full-regression-final-009/summary.json'])
p.write_text(json.dumps(older,ensure_ascii=False,indent=2)+'\n')
# All fixed original occurrences retain their original root-specific before/after evidence.
p=F/'diagnostic-ledger.jsonl';rows=[json.loads(x) for x in p.read_text().splitlines()]
for row in rows:
 if row['status']=='FIXED_AND_VERIFIED':row['final_source_regression']=dict(run='full-regression-final-009',source=source['commit'],result='1920PASS/0runtime/original1850preserved');row['remaining_condition']='External qualifications unchanged; local current-source full regression passed'
p.write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows))
print(json.dumps(dict(requirements=len(matrix['requirements']),entry_paths=len(entries['entries']),connections=len(connections),empty_clause_links=len(empty),missing=0,source=source['commit'])))

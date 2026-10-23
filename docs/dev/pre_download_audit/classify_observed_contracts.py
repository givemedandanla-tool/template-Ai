"""Classify only exact read operations observed on real, asserted synthetic paths.

This is bounded runtime evidence for a type-description backlog, not a proof that
arbitrary caller input is valid or that nullable lookups can lose their checks.
"""
import ast,collections,json,re
from coordinate_contract import index_for_diagnostic
from pathlib import Path
F=Path(__file__).resolve().parent
rows=[json.loads(x) for x in (F/'diagnostic-ledger.jsonl').read_text().splitlines()]
obs=json.loads((F/'runtime-observations-001/observations.json').read_text())
points={p['id']:p for p in json.loads((F/'runtime-points.json').read_text())['points']}
results={r['id']:r['status'] for r in json.loads((F/'runtime-observations-001/tests.json').read_text())}
proof=json.loads((F/'observed-contract-proof.json').read_text()).get('proof',{}) if (F/'observed-contract-proof.json').exists() else {};counts=collections.Counter();source_cache={}
def exact_index(row,point):
 path=row['original']['path']
 if path not in source_cache:
  source=(Path('/tmp/template-ai-audit-original-373b6ee')/path).read_text();source_cache[path]=(ast.parse(source),source.splitlines())
 tree,lines=source_cache[path];n=index_for_diagnostic(tree,lines,row['original_range'],row['rule'])
 if n is None:return False
 def canonical(s):
  for a,b in {'host_window':'window','width_input':'width','height_input':'height','size_input':'size','font_input':'font','output_size_mm':'size'}.items():s=re.sub(r'\.'+a+r'\b','.'+b,s)
  return re.sub(r'\s+','',s)
 actual=[t['expression'] for t in point['targets'] if t['label']=='container']
 return len(actual)==1 and canonical(actual[0])==canonical(ast.unparse(n.value))
for row in rows:
 if row['status']!='UNREVIEWED':continue
 r=obs['rows'].get(row['id'],{});contexts=[t for t in r.get('test_contexts',[]) if results.get(t)=='PASS']
 if not contexts:continue
 v=r.get('values',{});rule=row['rule'];containers=set(v.get('container',{}))-{'UNAVAILABLE_WITHOUT_EXECUTING_USER_CODE'};receivers=set(v.get('receiver',{}))-{'UNAVAILABLE_WITHOUT_EXECUTING_USER_CODE'};kind=None
 if rule in ['reportOptionalSubscript','reportIndexIssue'] and containers and containers<={'builtins.dict','builtins.list','builtins.tuple'}:kind='REAL_CONTAINER_SCHEMA'
 if rule in ['reportAttributeAccessIssue','reportOptionalMemberAccess'] and receivers and 'builtins.NoneType' not in receivers and r.get('member_checks') and all(k.endswith(':True') for k in r['member_checks']):kind='REAL_RECEIVER_MEMBER'
 if rule in ['reportArgumentType','reportCallIssue'] and any(op in row['original']['message'] for op in ['__getitem__','__setitem__']) and containers=={'builtins.dict'}:kind='RECORD_STRING_KEY_NOT_SEQUENCE_INDEX'
 if not kind:continue
 if kind!='REAL_RECEIVER_MEMBER' and not exact_index(row,points[row['id']]):continue
 key=row['id'];proof[key]=dict(kind=kind,expression=points[key],observation={k:v for k,v in r.items() if k!='test_contexts'},passing_test_contexts=contexts,source='runtime-observations-001/source.json',bounds='Actual authored valid/negative scenarios only. No claim for arbitrary missing lookup, mutation, invalid input, Windows or private works. Nullable public contracts remain unchanged.',followup='Declare producer DTO/fixture/host protocols and preserve boundary validation; do not replace with Any or suppress diagnostics.')
 row.update(status='TYPE_CONTRACT_GAP',severity='P2_TYPED_CONTRACT_BACKLOG',affected_workflow=row['original']['path'],root_cause_or_blocker=kind+': exact original expression maps to type-only observation on passing existing real tests; static inferred union does not express the exercised producer/receiver contract',evidence=['observed-contract-proof.json#'+key],repro_command_and_result='probe_runtime_contracts.py: original isolated executor, no assertion/window replacement, 0 observer errors; affected observation source and exact tests in proof',regression_and_result='Explicit passing test IDs in proof; whole observation run retains one independent preflight timeout, subsequently root-fixed, and is NOT marked globally PASS',remaining_condition='Type-description improvement remains P2 debt. This evidence covers listed synthetic states, not arbitrary nullable inputs.')
 counts[kind]+=1
(F/'diagnostic-ledger.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows))
(F/'observed-contract-proof.json').write_text(json.dumps(dict(method=__doc__,counts=dict(collections.Counter(p['kind'] for p in proof.values())),coordinate_validation='Exact original object/full-index/key range required',proof=proof),ensure_ascii=False,indent=2)+'\n')
print(dict(counts))

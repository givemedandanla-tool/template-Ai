"""Classify exact original diagnostic positions in deliberate unittest assertions.

Retains the static diagnostics as typing debt; does not certify arbitrary product
inputs or treat a passing test as proof that every warning is a false positive.
"""
import ast
from collections import defaultdict, Counter
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
FOLDER=Path(__file__).resolve().parent
ORIGINAL=Path('/tmp/template-ai-audit-original-373b6ee')
sys.path.insert(0,str(ROOT/'docs/dev/debug_tooling'))
import quality

ledger=FOLDER/'diagnostic-ledger.jsonl'
rows=[json.loads(line) for line in ledger.read_text().splitlines()]
positions=defaultdict(list)
for scope in ['application','tools','tests']:
 raw=json.loads((FOLDER/('original-position-'+scope)/'pyright.stdout.txt').read_text())
 for diagnostic in raw['generalDiagnostics']:
  path=Path(diagnostic['file']).relative_to(ORIGINAL).as_posix()
  item=quality.diagnostic('pyright',diagnostic.get('rule','unknown'),path,diagnostic['range']['start']['line']+1,diagnostic['message'],ORIGINAL)
  positions[scope,item['fingerprint']].append(diagnostic['range'])

cache={};proof={};counts=Counter();unmatched=[]
for row in rows:
 matching=positions[row['scope'],row['fingerprint']]
 if len(matching)<row['occurrence']:
  unmatched.append(row['id']);continue
 position=matching[row['occurrence']-1]
 row['original_range']=position
 if row['status']!='UNREVIEWED' or row['scope']!='tests':continue
 path=row['original']['path']
 if path not in cache:
  source=(ORIGINAL/path).read_text();tree=ast.parse(source);parents={c:n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
  cache[path]=(source.splitlines(),tree,parents)
 lines,tree,parents=cache[path]
 point=(position['start']['line'],position['start']['character'])
 def coordinate(line,byte):
  return (line-1,len(lines[line-1].encode()[:byte].decode().encode('utf-16-le'))//2)
 def contains(n):
  return hasattr(n,'lineno') and coordinate(n.lineno,n.col_offset)<=point<=coordinate(n.end_lineno,n.end_col_offset)
 def assertion(call):
  return (isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute)
    and isinstance(call.func.value,ast.Name) and call.func.value.id=='self'
    and call.func.attr.startswith('assert'))
 negative=None
 for node in ast.walk(tree):
  if isinstance(node,ast.With) and contains(node):
   for item in node.items:
    if assertion(item.context_expr) and item.context_expr.func.attr.startswith('assertRaises'):
     negative=node;break
  elif assertion(node) and node.func.attr.startswith('assertRaises') and contains(node):negative=node
 if negative:
  key=row['id'];proof[key]={'kind':'DELIBERATELY_INVALID_INPUT_TEST','path':path,'range':position,'context_line':negative.lineno,'context':ast.unparse(negative.items[0].context_expr if isinstance(negative,ast.With) else negative)[:650],'reason':'Exact diagnostic position is inside unittest assertRaises block/call; invalid data/type is intentional. Actual pass/error outcome remains independently recorded.'}
  row.update(status='TYPE_CONTRACT_GAP',severity='EXPECTED_NEGATIVE_TEST_INPUT',affected_workflow='Negative unit-test validation boundary',root_cause='Intentional invalid input under an exact unittest assertRaises boundary, rather than a production call-site acceptance claim',root_cause_or_blocker='Negative test data conflicts with the valid-input static signature by design',evidence=['assertion-contract-proof.json#'+key],repro_command_and_result=['assertion-contract-proof.json#'+key],regression_and_result='Final exact original test ID result pending')
  counts['negative']+=1;continue
 positives=[n for n in ast.walk(tree) if assertion(n) and not n.func.attr.startswith('assertRaises') and contains(n)]
 if not positives:continue
 call=min(positives,key=lambda n:(n.end_lineno-n.lineno,n.end_col_offset-n.col_offset))
 # Exclude deferred/conditionally evaluated subexpressions: the assertion need
 # not evaluate a comprehension body or short-circuited branch.
 descendants=[n for n in ast.walk(call) if contains(n)]
 if any(isinstance(n,(ast.BoolOp,ast.IfExp,ast.ListComp,ast.DictComp,ast.SetComp,ast.GeneratorExp,ast.Lambda)) for n in descendants):continue
 rule=row['rule'];message=row['original']['message']
 eligible=rule in ['reportOptionalSubscript','reportOptionalMemberAccess','reportOptionalOperand','reportOptionalIterable']
 if rule in ['reportIndexIssue','reportUnhashable','reportArgumentType','reportCallIssue','reportGeneralTypeIssues']:
  eligible=('Unknown' in message or ' | ' in message) and any(isinstance(n,ast.Subscript) for n in descendants)
 if rule=='reportAttributeAccessIssue':
  eligible=('for class "str"' in message or 'for class "int"' in message or 'for class "bool"' in message or 'for class "list[' in message or 'for class "dict[' in message) and any(isinstance(n,ast.Subscript) for n in descendants)
 if not eligible:continue
 key=row['id'];proof[key]={'kind':'POSITIVE_RECORD_ASSERTION_TYPING_DEBT','path':path,'range':position,'assertion_line':call.lineno,'assertion':ast.unparse(call)[:650],'reason':'Exact diagnostic is evaluated in a positive unittest record/property assertion with a nullable/heterogeneous static record type. The assertion intentionally enforces the positive fixture postcondition; the static warning is retained as missing narrowing/schema typing, not erased or a blanket false-positive verdict.'}
 row.update(status='TYPE_CONTRACT_GAP',severity='TEST_RECORD_TYPING_DEBT',affected_workflow='Positive fixture record/property assertions',root_cause='Nullable/heterogeneous record typing is not narrowed before a deliberate positive assertion; exact assertion/diagnostic position is preserved',root_cause_or_blocker='Test needs an explicit record schema or positive-fixture narrowing for static checking; product nullable-input paths require their own review',evidence=['assertion-contract-proof.json#'+key],repro_command_and_result=['assertion-contract-proof.json#'+key],regression_and_result='Final exact original test ID result pending')
 counts['positive_record_assertion']+=1
ledger.write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows))
(FOLDER/'assertion-contract-proof.json').write_text(json.dumps({'method':'Original Pyright counts exactly reproduced on isolated Git 373b6ee snapshot; each fingerprint occurrence maps back to original UTF-16 diagnostic coordinates and containing unittest assertion. Conditional/deferred positive expressions excluded.','counts':dict(counts),'unmatched_original_positions':unmatched,'proof':proof},ensure_ascii=False,indent=2)+'\n')
print('assertion contract classification',dict(counts),'unmatched original positions',len(unmatched))

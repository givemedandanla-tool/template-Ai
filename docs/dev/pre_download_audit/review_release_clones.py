"""Carry forward reviewed clone decisions and examine five new local candidates."""
import ast,difflib,hashlib,json
from pathlib import Path
F=Path(__file__).resolve().parent;ROOT=F.parents[2]
old=json.loads((F/'final-clone-review-ledger.json').read_text())
def identity(scope,kind,paths,fragment):return scope,kind,tuple(paths),fragment
existing={identity(r['scope'],r['kind'],[l['path'] for l in r['locations']],r['locations'][0]['snippet']):r for r in old['reviews']}
def location(scope,info):
 p=ROOT/info['name']
 if not p.is_file():p=ROOT/('tools' if scope=='tools' else 'tests')/info['name']
 source=p.read_text();a,b=info['start'],info['end'];tree=ast.parse(source)
 return dict(path=p.relative_to(ROOT).as_posix(),start=a,end=b,source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),snippet='\n'.join(source.splitlines()[a-1:b]),functions=[n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.lineno<=b and n.end_lineno>=a])
reviews=[]
for scope in ['application','tools','tests']:
 profile='final-release-'+scope+'-clones-002/report.json';report=json.loads((F/profile).read_text());assert report['source_unchanged']
 for i,c in enumerate(report['findings']):
  left,right=[location(scope,c[k]) for k in ['firstFile','secondFile']];key=identity(scope,c['kind'],[left['path'],right['path']],c['fragment']);prior=existing.get(key)
  if prior:decision,reason=prior['decision'],prior['reason']
  elif scope=='application' and left['path']==right['path']=='template_ai/training_store.py':decision,reason='KEEP_OVERLAPPING_IMPORTS','Renamed-token detector matched adjacent overlapping import windows within the same module after the selected-row decoder import was added. These are distinct imported mixins, each imported once; no duplicated runtime implementation exists.'
  elif scope=='tests' and left['path']==right['path']=='tests/test_solve_callback_lifetime.py':decision,reason='KEEP_OPPOSITE_LIFECYCLE_ASSERTIONS','The stale-worker test must preserve busy state, while the current-worker test must release it. Similar realQt signal setup is intentional; opposite assertions are the regression boundary, not interchangeable behavior.'
  elif scope=='tests' and right['path']=='tests/test_record_snapshot_oracle.py':decision,reason='KEEP_INDEPENDENT_IMPORT_FIXTURES','Shared Library/TrainingStore/SQLite fixture imports overlap unrelated customer/multi-size/provenance test imports. Snapshot tests require independent connections/interleavings and different assertions. No product implementation duplication.'
  elif scope=='tests' and left['path']=='tests/test_background_context.py' and right['path'] in ('tests/test_local_visual_binding.py','tests/test_work_load_atomicity.py'):decision,reason='KEEP_DISTINCT_REAL_GUI_FIXTURE_SETUP','Common Qt imports, retained QApplication and temporary workspace setup surround different critical behavior: background approval retargeting, local font recovery, and atomic work/source loading. Each test uses actual MainWindow and distinct corruption/modal transitions with independent assertions. Unifying only these short lifecycle preambles would add coupling without removing duplicated product logic.'
  elif scope=='tests' and right['path']=='tests/test_read_view_snapshot.py':decision,reason='KEEP_INDEPENDENT_READ_VIEW_FIXTURE','Common Qt/database/source fixture imports and retained QApplication precede different behavior. Automatic training exercises workers/jobs and qualification; read-view tests use two connections and interleaving row factories to verify coherent filtered metadata plus caller transaction preservation. No duplicated product implementation; retain independent lifetime/setup and assertions.'
  else:raise RuntimeError('Unreviewed new candidate '+str(key[:3]))
  reviews.append(dict(id=f'FINAL-CLONE-{scope.upper()}-{i+1:03}',scope=scope,kind=c['kind'],locations=[left,right],profile=profile,decision=decision,reason=reason,differences='\n'.join(difflib.unified_diff(left['snippet'].splitlines(),right['snippet'].splitlines(),n=1)),callers=dict(entry='application import/Qt callback' if scope=='application' else 'owned unittest discovery' if scope=='tests' else 'standalone authored capture',functions=left['functions']+right['functions'],dynamic_call_graph_complete=False),refactored=False,baseline_refreshed=False))
(F/'final-clone-review-ledger.json').write_text(json.dumps(dict(profile='Exact scan plus renamed-token/one-line-gap/normalized AST local comparison; no paid semantic service',counts={s:sum(r['scope']==s for r in reviews) for s in ['application','tools','tests']},all_candidates_reviewed=True,reviewed_new_candidates=1,reviews=reviews),ensure_ascii=False,indent=2)+'\n');print('reviewed final candidates',len(reviews))

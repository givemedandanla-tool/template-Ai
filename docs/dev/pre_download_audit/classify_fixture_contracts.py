import ast,json,re,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];folder=ROOT/'docs/dev/pre_download_audit'
modules={};classes={}
for p in (ROOT/'tests').glob('*.py'):
 tree=ast.parse(p.read_text());aliases={}
 for n in tree.body:
  if isinstance(n,ast.Import):
   for a in n.names:aliases[a.asname or a.name]=a.name
  if isinstance(n,ast.ImportFrom):
   for a in n.names:aliases[a.asname or a.name]=(n.module or '')+'.'+a.name
 modules[p.stem]={'path':p,'aliases':aliases}
 for c in tree.body:
  if isinstance(c,ast.ClassDef):classes[p.stem,c.name]=c

def reference(module,expr):
 try: parts=ast.unparse(expr).split('.')
 except: return
 aliases=modules[module]['aliases']
 if parts[0] in aliases:parts=aliases[parts[0]].split('.')+parts[1:]
 if len(parts)==3 and (parts[0],parts[1]) in classes:return (parts[0],parts[1],parts[2])
 if len(parts)==2 and (module,parts[0]) in classes:return (module,parts[0],parts[1])

def collect(key,seen=None):
 seen=set() if seen is None else seen
 if key in seen:return {}
 seen.add(key);mod,cls,name=key;c=classes.get((mod,cls));found={}
 if c is None:return found
 fn=next((n for n in c.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name),None)
 if fn is None:
  alias=next((n.value for n in c.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets)),None)
  ref=reference(mod,alias) if alias is not None else None
  return collect(ref,seen) if ref else found
 # Only top-level statements in an initializer: do not assume conditional or nested work executed.
 for stmt in fn.body:
  if isinstance(stmt,(ast.Assign,ast.AnnAssign)):
   targets=stmt.targets if isinstance(stmt,ast.Assign) else [stmt.target]
   for target in targets:
    for n in ast.walk(target):
     if isinstance(n,ast.Attribute) and isinstance(n.ctx,ast.Store) and isinstance(n.value,ast.Name) and n.value.id=='self':
      p=modules[mod]['path'];found[n.attr]={'initializer':'.'.join(key),'path':p.relative_to(ROOT).as_posix(),'line':n.lineno,'assignment':ast.unparse(stmt)[:350],'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
  def evaluated_nodes(node):
   yield node
   if isinstance(node,(ast.Lambda,ast.GeneratorExp,ast.ListComp,ast.SetComp,ast.DictComp,ast.IfExp,ast.BoolOp)):
    return
   for child in ast.iter_child_nodes(node):
    yield from evaluated_nodes(child)
  for n in evaluated_nodes(stmt):
   # Only calls that are themselves direct expression/assignment statement evaluation.
   if isinstance(stmt,(ast.If,ast.For,ast.While,ast.Try,ast.With,ast.FunctionDef,ast.ClassDef)):break
   if not isinstance(n,ast.Call):continue
   if isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='self':
    found.update(collect((mod,cls,n.func.attr),seen))
   elif n.args and isinstance(n.args[0],ast.Name) and n.args[0].id=='self':
    ref=reference(mod,n.func)
    if ref:found.update(collect(ref,seen))
 return found

ledger=folder/'diagnostic-ledger.jsonl';rows=[json.loads(x) for x in ledger.read_text().splitlines()];proof={};count=0
for r in rows:
 if (r.get('root_cause') or '').startswith('Pyright does not transfer self attributes through delegated unittest'):
  r.update(status='UNREVIEWED',severity='NOT_YET_ASSESSED',affected_workflow=None,root_cause=None,root_cause_or_blocker=None,evidence=[],repro_command_and_result=None,regression_and_result=None)
for r in rows:
 if r['status']!='UNREVIEWED' or r['scope']!='tests':continue
 m=re.match(r'^Cannot access attribute "([^"]+)" for class "([^"]+)"',r['original']['message'])
 if not m:continue
 member,cls=m.groups();cls=cls.rstrip('*');module=Path(r['original']['path']).stem
 if (module,cls) not in classes:continue
 initialized=collect((module,cls,'setUp'))
 if member not in initialized:continue
 key=module+'.'+cls+'.'+member;proof[key]={'consumer_class':module+'.'+cls,'member':member,'unconditional_initialization':initialized[member],'scope':'Static evidence of delegated fixture initialization; runtime regression recorded separately'}
 r.update(status='TYPE_CONTRACT_GAP',severity='TYPE_CONTRACT_DEBT',affected_workflow='Test fixture setup contract',root_cause='Pyright does not transfer self attributes through delegated unittest setUp/helper assignment; exact member is unconditionally assigned in the resolved setup call graph',root_cause_or_blocker='Explicit fixture host typing is missing; runtime result remains separate',evidence=['fixture-contract-proof.json#'+key],repro_command_and_result=['fixture-contract-proof.json#'+key],regression_and_result='Full isolated audit regression pending')
 count+=1
ledger.write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows));(folder/'fixture-contract-proof.json').write_text(json.dumps({'method':'AST-resolved imports, delegated unittest setUp and direct self-helper calls; only unconditional initializer statements counted','contracts':proof,'matched_occurrences':count},ensure_ascii=False,indent=2)+'\n');print('fixture occurrences classified',count,'contracts',len(proof))

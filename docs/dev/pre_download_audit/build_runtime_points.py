"""Map original diagnostics to unchanged current expressions for type-only probes."""
import ast,json,re,hashlib
from coordinate_contract import index_for_diagnostic
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];FOLDER=Path(__file__).resolve().parent
ORIGINAL=Path('/tmp/template-ai-audit-original-373b6ee')
renames={'host_window':'window','font_input':'font','size_input':'size','width_input':'width','height_input':'height','style_input':'style','measurement_label':'result','root_layout':'layout','scroll_area':'scroll','output_size_mm':'size'}
def canonical(text):
 for new,old in renames.items():text=re.sub(r'\.'+new+r'\b','.'+old,text)
 return re.sub(r'\s+','',text)
def read(path):
 text=path.read_text();tree=ast.parse(text);parents={c:n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
 return {'text':text,'tree':tree,'parents':parents,'lines':text.splitlines()}
def scope(info,n):
 names=[]
 while n is not None:
  if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)):names.append(n.name)
  n=info['parents'].get(n)
 return tuple(reversed(names))
def span(n):return [n.lineno,n.col_offset,n.end_lineno,n.end_col_offset]
rows=[json.loads(s) for s in (FOLDER/'diagnostic-ledger.jsonl').read_text().splitlines()]
cache={};points=[];unmapped=[]
for row in rows:
 if row['status']!='UNREVIEWED' or 'original_range' not in row:continue
 path=row['original']['path']
 if not (ROOT/path).exists():unmapped.append([row['id'],'MISSING_CURRENT_SOURCE']);continue
 if path not in cache:cache[path]=(read(ORIGINAL/path),read(ROOT/path))
 old,new=cache[path];position=row['original_range']['start'];p=(position['line'],position['character'])
 def coord(line,byte):return (line-1,len(old['lines'][line-1].encode()[:byte].decode().encode('utf-16-le'))//2)
 nodes=[n for n in ast.walk(old['tree']) if hasattr(n,'lineno') and coord(n.lineno,n.col_offset)<=p<=coord(n.end_lineno,n.end_col_offset)]
 if not nodes:unmapped.append([row['id'],'NO_ORIGINAL_AST']);continue
 inner=min(nodes,key=lambda n:(n.end_lineno-n.lineno,n.end_col_offset-n.col_offset));old_scope=scope(old,inner)
 old_context=canonical(row['original']['context'])
 candidates=[i+1 for i,line in enumerate(new['lines']) if canonical(line.strip())==old_context]
 candidates=[ln for ln in candidates if any(hasattr(n,'lineno') and n.lineno<=ln<=n.end_lineno and scope(new,n)==old_scope for n in ast.walk(new['tree']))]
 if len(candidates)!=1:unmapped.append([row['id'],'CHANGED_OR_AMBIGUOUS_CONTEXT']);continue
 line=candidates[0];at_line=[n for n in ast.walk(new['tree']) if isinstance(n,ast.expr) and n.lineno<=line<=n.end_lineno]
 wanted=[];calls=[];member=None
 rule=row['rule'];message=row['original']['message']
 subnodes=[n for n in nodes if isinstance(n,ast.Subscript)]
 attrs=[n for n in nodes if isinstance(n,ast.Attribute)]
 if rule in ['reportOptionalSubscript','reportIndexIssue'] or '__getitem__' in message or '__setitem__' in message:
  chosen=index_for_diagnostic(old['tree'],old['lines'],row['original_range'],rule)
  if chosen is not None:wanted+=[('container',chosen.value),('result',chosen)]
 elif rule in ['reportOptionalMemberAccess','reportAttributeAccessIssue']:
  match=re.search(r'(?:attribute "([^"]+)"|"([^"]+)" is not a known attribute)',message)
  member=(match[1] or match[2]) if match else None
  options=[n for n in attrs if member is None or n.attr==member]
  if options:
   chosen=min(options,key=lambda n:(n.end_lineno-n.lineno,n.end_col_offset-n.col_offset));wanted.append(('receiver',chosen.value));member=chosen.attr
 else:
  options=[n for n in nodes if isinstance(n,ast.expr) and not isinstance(n,(ast.Constant,ast.Name))]
  if options:wanted.append(('value',min(options,key=lambda n:(n.end_lineno-n.lineno,n.end_col_offset-n.col_offset))))
  if isinstance(inner,ast.Name):wanted.append(('value',inner))
 # Capture exact operator operands and iterable sources without evaluating them.
 if rule in ['reportOperatorIssue','reportOptionalOperand']:
  operations=[n for n in nodes if isinstance(n,ast.BinOp)]
  if operations:
   op=min(operations,key=lambda n:(n.end_lineno-n.lineno,n.end_col_offset-n.col_offset))
   wanted += [('operator_left',op.left),('operator_right',op.right)]
 if rule in ['reportGeneralTypeIssues','reportOptionalIterable'] and 'iterable' in message:
  sources=[n.iter for n in nodes if isinstance(n,(ast.For,ast.AsyncFor))]
  for n in nodes:
   if isinstance(n,(ast.ListComp,ast.SetComp,ast.DictComp,ast.GeneratorExp)):sources += [g.iter for g in n.generators]
  if sources:
   source=min(sources,key=lambda n:(n.end_lineno-n.lineno,n.end_col_offset-n.col_offset))
   wanted.append(('iterable',source))
 parent_calls=[n for n in nodes if isinstance(n,ast.Call)]
 if rule=='reportArgumentType' and parent_calls:
  call=min(parent_calls,key=lambda n:(n.end_lineno-n.lineno,n.end_col_offset-n.col_offset))
  args=[arg for arg in [*call.args,*[k.value for k in call.keywords]] if coord(arg.lineno,arg.col_offset)<=p<coord(arg.end_lineno,arg.end_col_offset)]
  if len(args)==1:wanted.append(('argument',args[0]))
 if parent_calls:
  chosen=min(parent_calls,key=lambda n:(n.end_lineno-n.lineno,n.end_col_offset-n.col_offset));calls.append(chosen)
  if isinstance(chosen.func,ast.Attribute) and chosen.func.attr in ['len','get']:pass
 targets=[]
 for label,expr in wanted:
  if isinstance(expr,ast.Starred):expr=expr.value
  text=canonical(ast.unparse(expr));matches=[n for n in at_line if canonical(ast.unparse(n))==text]
  # Repeated identical expressions on a line are equivalent read-only targets.
  if matches:targets.append({'label':label,'expression':ast.unparse(matches[0])})
 call_ranges=[];producer_names=[]
 for call in calls:
  key=canonical(ast.unparse(call));matches=[n for n in at_line if isinstance(n,ast.Call) and canonical(ast.unparse(n))==key]
  if len(matches)==1:call_ranges.append(span(matches[0]));producer_names.append(ast.unparse(matches[0].func).split('.')[-1])
 for label,expr in wanted:
  if isinstance(expr,ast.Call):producer_names.append(ast.unparse(expr.func).split('.')[-1])
 if not targets and not call_ranges and not producer_names:unmapped.append([row['id'],'NO_SAFE_TARGET']);continue
 method=next((name for name in old_scope if name.startswith('test_')),None)
 test_id='.'.join([Path(path).stem,*old_scope[:old_scope.index(method)+1]]) if path.startswith('tests/') and method else None
 points.append({'id':row['id'],'scope':row['scope'],'path':path,'line':line,'rule':rule,'targets':targets,'member':member,'call_ranges':call_ranges,'producer_names':sorted(set(producer_names)),'test_id':test_id,'source_sha256':hashlib.sha256((ROOT/path).read_bytes()).hexdigest()})
result={'scope':'TYPE_ONLY_NO_PAYLOADS_NO_PROPERTY_GETTERS','source_files':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in cache},'points':points,'unmapped':unmapped}
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=FOLDER/'runtime-points.json');args=parser.parse_args()
args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('mapped runtime points',len(points),'unmapped',len(unmapped),'direct test IDs',len({p['test_id'] for p in points if p['test_id']}))

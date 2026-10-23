"""Conservative literal-record field proofs, not a replacement type checker."""
import ast,json,re,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];FOLDER=Path(__file__).resolve().parent
ORIGINAL=Path('/tmp/template-ai-audit-original-373b6ee')
UNKNOWN={'kind':'unknown'}
modules={}
for p in ORIGINAL.rglob('*.py'):
 rel=p.relative_to(ORIGINAL).as_posix()
 if rel.split('/')[0] not in ['template_ai','tools','tests']:continue
 key=rel[:-3].replace('/','.')
 tree=ast.parse(p.read_text());parents={c:n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)};imports={}
 for n in tree.body:
  if isinstance(n,ast.Import):
   for a in n.names:imports[a.asname or a.name]=a.name
  elif isinstance(n,ast.ImportFrom):
   base=('.'.join(key.split('.')[:-n.level])+'.'+(n.module or '')).strip('.') if n.level else n.module
   for a in n.names:imports[a.asname or a.name]=(base or '')+'.'+a.name
 modules[key]={'path':rel,'tree':tree,'parents':parents,'imports':imports,'lines':p.read_text().splitlines()}

def merge(values):
 if not values or any(v['kind']=='unknown' for v in values):return UNKNOWN
 kinds={v['kind'] for v in values}
 if len(kinds)!=1:return UNKNOWN
 out={'kind':next(iter(kinds))}
 if out['kind']=='dict':
  common=set(values[0].get('fields',{}))
  for v in values[1:]:common&=v.get('fields',{}).keys()
  out['fields']={k:merge([v['fields'][k] for v in values]) for k in common}
 if out['kind']=='list':out['element']=merge([v.get('element',UNKNOWN) for v in values])
 out['origins']=[x for v in values for x in v.get('origins',[])][:8]
 return out

def context(module,node):
 parent=modules[module]['parents'];fn=None;cls=None;n=node
 while n is not None:
  if isinstance(n,ast.FunctionDef) and fn is None:fn=n
  if isinstance(n,ast.ClassDef):cls=n;break
  n=parent.get(n)
 return fn,cls

def infer(module,node,fn,cls,bindings=None,seen=None,depth=0):
 if node is None or depth>12:return UNKNOWN
 bindings={} if bindings is None else bindings;seen=set() if seen is None else seen
 marker=(module,id(node))
 if marker in seen:return UNKNOWN
 seen=set(seen);seen.add(marker)
 def sub(n,other_bindings=None):return infer(module,n,fn,cls,bindings if other_bindings is None else other_bindings,seen,depth+1)
 def origin(v):
  if v['kind']!='unknown':v=dict(v,origins=[{'path':modules[module]['path'],'line':node.lineno,'expression':ast.unparse(node)[:300]}]+v.get('origins',[]))
  return v
 if isinstance(node,ast.Constant):return {'kind':type(node.value).__name__}
 if isinstance(node,ast.Dict):
  fields={}
  for k,v in zip(node.keys,node.values):
   if k is None:
    shape=sub(v)
    if shape['kind']=='dict':fields.update(shape.get('fields',{}))
    else:fields={}
   elif isinstance(k,ast.Constant) and isinstance(k.value,str):fields[k.value]=sub(v)
  return origin({'kind':'dict','fields':fields})
 if isinstance(node,(ast.List,ast.Tuple,ast.Set)):
  kind={ast.List:'list',ast.Tuple:'tuple',ast.Set:'set'}[type(node)]
  return origin({'kind':kind,'element':merge([sub(n) for n in node.elts])})
 if isinstance(node,ast.Name):
  if node.id in bindings:return bindings[node.id]
  # Resolve exact comprehension/loop bindings, retaining the actual iterable schema.
  par=modules[module]['parents'];anc=node
  while anc is not None and anc is not fn:
   if isinstance(anc,(ast.ListComp,ast.SetComp,ast.GeneratorExp,ast.DictComp)):
    for g in anc.generators:
     if isinstance(g.target,ast.Name) and g.target.id==node.id:
      it=sub(g.iter);return it.get('element',UNKNOWN) if it['kind'] in ['list','tuple','set'] else UNKNOWN
   if isinstance(anc,ast.For) and isinstance(anc.target,ast.Name) and anc.target.id==node.id:
    it=sub(anc.iter);return it.get('element',UNKNOWN) if it['kind'] in ['list','tuple','set'] else UNKNOWN
   anc=par.get(anc)
  body=fn.body if fn else modules[module]['tree'].body
  assignments=[a for stmt in body for a in ast.walk(stmt) if isinstance(a,ast.Assign) and a.lineno<node.lineno and any(isinstance(t,ast.Name) and t.id==node.id for t in a.targets) and context(module,a)[0] is fn and (fn is not None or context(module,a)[1] is None)]
  if not assignments:return UNKNOWN
  # Every possible earlier binding must establish a consistent field schema.
  values=[sub(a.value) for a in assignments]
  value=merge(values)
  read_only={'len','str','bool','int','float','json.dumps','copy.deepcopy','deepcopy','dict','list','tuple','set','sorted'}
  aliases=set()
  for stmt in body:
   for a in ast.walk(stmt):
    if not hasattr(a,'lineno') or not min(x.lineno for x in assignments)<a.lineno<node.lineno:continue
    if isinstance(a,ast.Assign) and isinstance(a.value,ast.Name) and a.value.id==node.id:
     aliases.update(t.id for t in a.targets if isinstance(t,ast.Name))
    if isinstance(a,ast.Call):
     escaped=any(isinstance(v,ast.Name) and v.id in ({node.id}|aliases) for v in [*a.args,*[k.value for k in a.keywords]])
     if escaped and ast.unparse(a.func) not in read_only:
      if value['kind']=='dict':value=dict(value,fields={})
      if value['kind']=='list':value=dict(value,element=UNKNOWN)
     if isinstance(a.func,ast.Attribute) and isinstance(a.func.value,ast.Name) and a.func.value.id in ({node.id}|aliases) and a.func.attr in ['append','extend','insert','remove','pop','clear','sort','reverse']:
      if value['kind']=='list':value=dict(value,element=UNKNOWN)
  if aliases:
   # An aliased object can be changed outside this local name; do not infer its
   # individual field/element types from the initial literal.
   if value['kind']=='dict':value=dict(value,fields={})
   if value['kind']=='list':value=dict(value,element=UNKNOWN)
  # Any keyed reassignment or opaque mutation invalidates its corresponding field.
  if value['kind']=='dict':
   fields=dict(value.get('fields',{}))
   for stmt in body:
    for a in ast.walk(stmt):
     if not hasattr(a,'lineno') or not min(x.lineno for x in assignments)<a.lineno<node.lineno:continue
     if isinstance(a,ast.Assign):
      for t in a.targets:
       if isinstance(t,ast.Subscript):
        root=t
        while isinstance(root.value,ast.Subscript):root=root.value
        if isinstance(root.value,ast.Name) and root.value.id==node.id:
         if root is t and isinstance(t.slice,ast.Constant) and isinstance(t.slice.value,str):fields[t.slice.value]=merge([fields.get(t.slice.value,UNKNOWN),sub(a.value)])
         elif isinstance(root.slice,ast.Constant) and isinstance(root.slice.value,str):fields[root.slice.value]=UNKNOWN
         else:fields={}
     if isinstance(a,ast.Call) and isinstance(a.func,ast.Attribute) and isinstance(a.func.value,ast.Name) and a.func.value.id==node.id and a.func.attr in ['update','clear','pop','popitem','setdefault']:
      if a.func.attr=='update' and not a.args:
       for kw in a.keywords:
        if kw.arg:fields[kw.arg]=merge([fields.get(kw.arg,UNKNOWN),sub(kw.value)])
        else:fields={}
      else:fields={}
   value=dict(value,fields=fields)
  return value
 if isinstance(node,ast.Subscript):
  value=sub(node.value)
  if value['kind']=='dict' and isinstance(node.slice,ast.Constant) and isinstance(node.slice.value,str):return value.get('fields',{}).get(node.slice.value,UNKNOWN)
  if value['kind'] in ['list','tuple'] and isinstance(node.slice,ast.Constant) and type(node.slice.value) is int:return value.get('element',UNKNOWN)
  return UNKNOWN
 if isinstance(node,(ast.ListComp,ast.SetComp,ast.GeneratorExp)):
  return origin({'kind':'list' if isinstance(node,ast.ListComp) else 'set' if isinstance(node,ast.SetComp) else 'iterator','element':sub(node.elt)})
 if isinstance(node,ast.IfExp):return merge([sub(node.body),sub(node.orelse)])
 if isinstance(node,ast.BinOp):
  a,b=sub(node.left),sub(node.right)
  if isinstance(node.op,ast.Add) and a['kind']==b['kind']=='str':return {'kind':'str'}
  if a['kind'] in ['int','float'] and b['kind'] in ['int','float']:return {'kind':'float' if 'float' in [a['kind'],b['kind']] or isinstance(node.op,ast.Div) else 'int'}
 if isinstance(node,ast.Call):
  name=ast.unparse(node.func)
  if name=='dict':
   fields={}
   if node.args:
    start=sub(node.args[0]);fields=dict(start.get('fields',{})) if start['kind']=='dict' else {}
   for kw in node.keywords:
    if kw.arg:fields[kw.arg]=sub(kw.value)
    else:
     value=sub(kw.value)
     if value['kind']=='dict':fields.update(value.get('fields',{}))
     else:fields={}
   return origin({'kind':'dict','fields':fields})
  if name in ['str','int','float','bool']:return {'kind':name}
  if name in ['list','tuple','set','sorted']:
   src=sub(node.args[0]) if node.args else UNKNOWN
   return {'kind':'list' if name=='sorted' else name,'element':src.get('element',UNKNOWN)}
  if name=='len':return {'kind':'int'}
  if name=='range':return {'kind':'list','element':{'kind':'int'}}
  if name in ['copy.deepcopy','deepcopy'] and node.args:return sub(node.args[0])
  target_module=module;target_fn=None;target_class=None
  if isinstance(node.func,ast.Name):
   parts=modules[module]['imports'].get(name,name).split('.')
   if len(parts)>1 and '.'.join(parts[:-1]) in modules:target_module='.'.join(parts[:-1]);name=parts[-1]
   target_fn=next((n for n in modules[target_module]['tree'].body if isinstance(n,ast.FunctionDef) and n.name==name),None)
  elif cls and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='self':
   target_fn=next((n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==node.func.attr),None);target_class=cls
  if target_fn and target_fn.body and isinstance(target_fn.body[-1],ast.Return):
   returns=[n for n in ast.walk(target_fn) if isinstance(n,ast.Return) and context(target_module,n)[0] is target_fn]
   params=[a.arg for a in target_fn.args.args if a.arg!='self'];arguments={k:sub(v) for k,v in zip(params,node.args)}
   arguments.update({k.arg:sub(k.value) for k in node.keywords if k.arg})
   return merge([infer(target_module,n.value,target_fn,target_class,arguments,seen,depth+1) for n in returns])
 return UNKNOWN


# Pure inference/index definitions only; importing does not modify evidence.

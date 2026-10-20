"""Prove only new Python data attributes, excluding every native/property name."""
import importlib,inspect,json,os
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication,QDialog
ROOT=Path(__file__).resolve().parents[3];F=Path(__file__).resolve().parent
import sys
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
app=QApplication.instance() or QApplication([])
rows=[json.loads(x) for x in (F/'diagnostic-ledger.jsonl').read_text().splitlines()];proof=json.loads((F/'qobject-data-attribute-proof.json').read_text()).get('proof',{}) if (F/'qobject-data-attribute-proof.json').exists() else {};dummy=QDialog();marker=object()
for runname,result_file in [('runtime-ast-observations-001','tests.json'),('ast-module-contexts-003','tests.json'),('runtime-ast-observations-004','tests.json'),('capture-type-evidence-001','capture-contexts.json')]:
 o=json.loads((F/runname/'observations.json').read_text());results={r['id']:r['status'] for r in json.loads((F/runname/result_file).read_text())};assert not o['observer_errors'] and o['business_ast_equivalence_verified']
 module_contexts=json.loads((F/runname/'module-contexts.json').read_text()) if (F/runname/'module-contexts.json').exists() else {}
 for row in rows:
  if row['status']!='UNREVIEWED' or row['rule']!='reportAttributeAccessIssue' or not row['original']['message'].startswith('Cannot assign to attribute'):continue
  import re
  match=re.match(r'Cannot assign to attribute "([^"]+)"',row['original']['message']);member=match[1] if match else None;r=o['rows'].get(row['id'],{});types=set(r.get('values',{}).get('receiver',{}));contexts=[t for t in r.get('test_contexts',[]) if results.get(t)=='PASS']
  if not contexts:contexts=['owned-module:'+m for m in r.get('module_contexts',[]) if m in module_contexts and module_contexts[m]['receipt']['healthy'] and all(results.get(t)=='PASS' for t in module_contexts[m]['tests'])]
  if not member or not types or not contexts:continue
  evidence=[]
  for name in types:
   try:
    module,cls_name=name.rsplit('.',1);cls=getattr(importlib.import_module(module),cls_name)
    if not isinstance(cls,type) or not issubclass(cls,QObject):break
    if any(member in base.__dict__ for base in cls.__mro__):break
    setters=[base for base in cls.__mro__ if '__setattr__' in base.__dict__]
    if any(not base.__module__.startswith(('PySide6','shiboken6','Shiboken','builtins')) for base in setters):break
    setattr(dummy,member,marker);assert getattr(dummy,member) is marker;delattr(dummy,member)
    evidence.append(dict(receiver=name,mro=[x.__module__+'.'+x.__name__ for x in cls.__mro__],native_or_property_collision=False,custom_setattr=False,qt_python_namespace_roundtrip=True))
   except (AttributeError,ImportError,TypeError):break
  else:
   key=row['id'];proof[key]=dict(original=row['original'],member=member,receiver_contracts=evidence,run=runname,contexts=contexts,scope='Only creation of this absent Python data name; native APIs/property setters and arbitrary non-QObject hosts excluded')
   row.update(status='TYPE_CONTRACT_GAP',severity='P2_DECLARED_QOBJECT_DATA_MEMBER',affected_workflow=row['original']['path'],root_cause_or_blocker='Real QObject subclass supports this new Python data name; exact MRO contains no native/property collision and no custom setter. The stub/class declarations omit the dynamic field. Declare its precise optional member type.',evidence=['qobject-data-attribute-proof.json#'+key],regression_and_result=contexts,repro_command_and_result='Exact observed QObject class/MRO plus Qt Python namespace marker roundtrip; no actual window replaced and no payload persisted')
dummy.deleteLater();(F/'diagnostic-ledger.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows));(F/'qobject-data-attribute-proof.json').write_text(json.dumps(dict(method=__doc__,proof=proof),ensure_ascii=False,indent=2)+'\n');print('new QObject data members',len(proof))

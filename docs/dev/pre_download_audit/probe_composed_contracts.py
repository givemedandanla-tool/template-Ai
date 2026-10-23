"""Safe member/type-only inspection on real empty/authored local composition."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import json,re,hashlib,sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from PySide6.QtWidgets import QWidget,QApplication
from template_ai.coverage_batches import CoverageBatches
from test_quality_repair_gui import QualityRepairGuiTests

folder=Path(__file__).resolve().parent
path=folder/'diagnostic-ledger.jsonl'
rows=[json.loads(x) for x in path.read_text().splitlines()]
case=QualityRepairGuiTests('runTest');case.setUp();proof={};count=0
try:
 panel,dialog=case.dialog()
 objects=[case.store,CoverageBatches(case.library),panel.host_window,dialog,*dialog.findChildren(QWidget)]
 for row in rows:
  if row['status']!='UNREVIEWED':continue
  match=re.match(r'^Cannot access attribute "([^"]+)" for class "([^"]+)"',row['original']['message'])
  if not match:continue
  member,expected=match.groups();expected=expected.rstrip('*')
  for obj in objects:
   mro=type(obj).__mro__
   if not any(c.__name__==expected and c.__module__.startswith('template_ai.') for c in mro):continue
   if not hasattr(obj,member):continue
   cls=type(obj);value=getattr(obj,member);key=cls.__module__+'.'+cls.__name__+'::'+expected+'.'+member
   proof[key]={'exact_missing_static_class':expected,'real_concrete_type':cls.__module__+'.'+cls.__name__,'member_exists':True,'member_value_type':type(value).__module__+'.'+type(value).__name__,'mro':[c.__module__+'.'+c.__name__ for c in mro],'construction':'Original authored QualityRepairGuiTests setup and real dialog factory, plus CoverageBatches; no business methods executed for inspection'}
   row.update(status='TYPE_CONTRACT_GAP',severity='COMPOSED_HOST_TYPING_DEBT',affected_workflow='Composed quality review / coverage / desktop host interfaces',root_cause='Static class or mixin host declaration omits a member supplied by actual concrete constructor/MRO composition; exact live member type is recorded',root_cause_or_blocker='Explicit host/constructor typing missing; this is not a blanket claim about all runtime inputs',evidence=['composed-host-proof.json#'+key],repro_command_and_result=['composed-host-proof.json#'+key],regression_and_result='Final full isolated regression pending')
   count+=1;break
finally:
 case.tearDown();case.doCleanups();QApplication.processEvents()
path.write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows))
(folder/'composed-host-proof.json').write_text(json.dumps({'method':'Exact MRO and member existence on real application/backend composition; only types/names, no payloads or fonts persisted','matched_occurrences':count,'members':proof},ensure_ascii=False,indent=2)+'\n')
print('composed host occurrences',count,'member contracts',len(proof))

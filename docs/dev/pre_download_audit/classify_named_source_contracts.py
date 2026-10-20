"""Reviewed named schema/lifetime contracts; keep per-occurrence source evidence."""
import ast,json,hashlib
from pathlib import Path
F=Path(__file__).resolve().parent;ROOT=F.parents[2]
rows=[json.loads(s) for s in (F/'diagnostic-ledger.jsonl').read_text().splitlines()];proof=json.loads((F/'named-source-contract-proof.json').read_text()).get('proof',{}) if (F/'named-source-contract-proof.json').exists() else {};catalog=json.loads((F/'full-regression-005/catalog.json').read_text())
keys=["['people']","['companies']","['fields']","['links']"]
for row in rows:
 if row['status']!='UNREVIEWED':continue
 path=row['original']['path'];text=(ROOT/path).read_text();tree=ast.parse(text);context=row['original']['context'];kind=None;reason=None;anchors=[];tests=[]
 if path=='template_ai/input_graph.py' or (path in ['tests/test_entity_relations.py','template_ai/input_graph_dialog.py'] and any(k in context for k in keys)):
  kind='VALIDATED_INPUT_GRAPH_NAMED_SCHEMA'
  reason='InputGraph.__init__ validates exact keys/types; people/companies/fields/links are lists, stable IDs/value are strings, users are string lists, revision/serial are ints. compile validates again, commands preview on cloned graph, validate before commit and preserve this schema in undo/redo. Heterogeneous dict inference merges revision integer with collections; it does not describe individual named keys. compile values() explicitly creates per-kind lists plus source_entity_id/field_ids; company/companies ports are distinct named fields. Invalid caller data and private _execute bypass remain outside this precondition.'
  anchors=['template_ai/input_graph.py:21','template_ai/input_graph.py:34','template_ai/input_graph.py:127','template_ai/input_graph.py:146','template_ai/input_graph_dialog.py:25']
  tests=[t for t in catalog if t.startswith('test_entity_relations.')]
 if row['rule']=='reportOptionalMemberAccess' and 'processEvents' in row['original']['message']:
  # Verify this concrete alias is formed by the real QApplication factory.
  found=[]
  for n in ast.walk(tree):
   if isinstance(n,ast.Assign) and 'QApplication.instance() or QApplication(' in ast.unparse(n.value):
    for target in n.targets:
     if isinstance(target,ast.Name) and target.id+'.processEvents' in context:found.append(n.lineno)
  if found:
   kind='GUI_APPLICATION_FACTORY_LIFETIME'
   reason='Exact receiver alias is established by QApplication.instance() or QApplication([]), in an owned GUI process where any existing application is QApplication. Qt .instance() has nullable QCoreApplication stub, while this factory ensures the GUI application before widgets/event pumping. Does not license arbitrary use of instance() without factory/lifetime guards.'
   anchors=[path+':'+str(n) for n in found];tests=['native-gui-003:19PASS; actual QApplication, desktop/navigation/event/report/recovery']
 if path=='app.py' and '_template_ai_support_journal' in context:
  kind='QAPPLICATION_LOCAL_JOURNAL_ATTACHMENT';reason='QApplication supports Python instance attributes. This distinct non-native attribute deliberately retains the local journal lifetime; Qt native-member collision inventory does not contain this name. No payload upload or extra cloud service is introduced.';anchors=['app.py:65'];tests=['qapplication-attachment-proof.json']
 if not kind:continue
 ident=row['id'];proof[ident]=dict(kind=kind,reason=reason,original=row['original'],source_sha256=hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),anchors=anchors,affected_tests=tests,qualification='Local synthetic/source contract only; original diagnosis retained, typed schema/protocol followup remains P2')
 row.update(status='TYPE_CONTRACT_GAP',severity='P2_NAMED_SOURCE_CONTRACT_DEBT',affected_workflow=path,root_cause_or_blocker=reason,evidence=['named-source-contract-proof.json#'+ident],repro_command_and_result=anchors,regression_and_result=tests,remaining_condition='Add precise named-field/application host types while preserving runtime validation; no Any, ignore, baseline refresh or qualification waiver')
(F/'diagnostic-ledger.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows));(F/'named-source-contract-proof.json').write_text(json.dumps(dict(method=__doc__,proof=proof),ensure_ascii=False,indent=2)+'\n');print('classified',len(proof))

"""Selected builtin/Qt binding contracts with exact successful original calls.

Bounded executed-path type debt, not general semantic correctness. Each source
location and its actual receiver/result stays independently recorded.
"""
import argparse,ast,json,re
from pathlib import Path
F=Path(__file__).resolve().parent;p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--points',default='runtime-points-006.json');p.add_argument('--capture',action='store_true');a=p.parse_args();run=F/a.run;o=json.loads((run/'observations.json').read_text());assert not o['runtime_errors'] and not o['observer_errors'] and o['source_unchanged'] and o['business_ast_equivalence_verified'];passed={r['id'] for r in json.loads((run/('capture-contexts.json' if a.capture else 'tests.json')).read_text()) if r['status']=='PASS'};modules=json.loads((run/'module-contexts.json').read_text()) if (run/'module-contexts.json').exists() else {};points={p['id']:p for p in json.loads((F/a.points).read_text())['points']};rows=[json.loads(x) for x in (F/'diagnostic-ledger.jsonl').read_text().splitlines()];dest=F/'executed-binding-review-proof.json';proof=json.loads(dest.read_text()).get('proof',{}) if dest.exists() else {};count=0
for row in rows:
 if row['status']!='UNREVIEWED' or row['rule'] not in ['reportArgumentType','reportCallIssue']:continue
 actual=o['rows'].get(row['id'],{});v=actual.get('values',{});contexts=[t for t in actual.get('test_contexts',[]) if t in passed]
 if not contexts:contexts=['owned-module:'+m for m in actual.get('module_contexts',[]) if m in modules and modules[m]['receipt']['healthy'] and set(modules[m]['tests'])<=passed]
 if not contexts or not v.get('call_result'):continue
 point=points.get(row['id']);calls=[t for t in point['targets'] if t['label']=='call_result']
 if len(calls)!=1:continue
 call=ast.parse(calls[0]['expression'],mode='eval').body
 if not isinstance(call,ast.Call):continue
 name=call.func.attr if isinstance(call.func,ast.Attribute) else call.func.id if isinstance(call.func,ast.Name) else None;message=row['original']['message'];function=re.search(r'in function "([^"]+)"',message);overload=re.search(r'No overloads for "([^"]+)"',message)
 if function and function[1]!=name and not (function[1] in ['__init__','__new__'] and name=='QTableWidgetItem'):continue
 if overload and overload[1]!=name and not(overload[1] in ['__init__','__new__'] and name=='QTableWidgetItem'):continue
 receiver=set(v.get('call_receiver',{}));returned=set(v['call_result']);reason=None
 if isinstance(call.func,ast.Attribute) and name=='join' and receiver=={'builtins.str'} and returned=={'builtins.str'}:
  reason='Builtin str.join returned normally, which consumes and validates the complete executed iterable as strings. The original inferred union mixes errors/labels lists with bool/scalar record fields. This proves only the retained actual collection, not future generic contents.'
 elif isinstance(call.func,ast.Name) and name=='sum' and returned<={'builtins.int','builtins.float','numpy.int64','numpy.float64'}:
  reason='The exact builtin sum consumed its actual iterable and completed with the recorded numeric result; generator values supported addition on these authored paths. Numeric assertions are retained separately. This is the inferred heterogeneous-field/protocol contract debt, not a claim arbitrary iterable values are numeric.'
 elif isinstance(call.func,ast.Attribute) and name in ['get','setdefault','pop'] and receiver=={'builtins.dict'}:
  reason='The exact receiver is builtin dict and its actual get/setdefault/pop call returned normally, using dictionary rather than list/string overloads. Heterogeneous named-record value/default types require a precise DTO; returned field contents and existence still require their own original guards.'
 elif name=='QTableWidgetItem' and returned=={'PySide6.QtWidgets.QTableWidgetItem'}:
  reason='The exact Qt item constructor accepted its actual argument binding and returned the intended item type on successful real-table paths. Static overload resolution over an inferred union remains incomplete. This does not waive independent text-content assertions or arbitrary constructor inputs.'
 elif isinstance(call.func,ast.Attribute) and name in ['save','loadFromData'] and receiver and receiver<={'PySide6.QtGui.QImage','PySide6.QtGui.QPixmap'} and returned=={'builtins.bool'}:
  reason='The exact native image binding accepted its actual arguments and returned bool; original save/decode failure guards and assertions remain unchanged. str format acceptance has an independent pinned PySide PNG roundtrip proof. This closes binding typing debt only, not source-image fidelity or arbitrary successful decoding.'
 if not reason:continue
 proof[row['id']]=dict(original=row['original'],point=point,exact_call=calls[0],actual_types=v,passing_contexts=contexts,source=run.name+'/source.json',observations=run.name+'/observations.json',reason=reason,bounds='Original unchanged authored assertions and real product windows; exact expression type evidence. Unseen values, deferred platforms and all-content correctness are not established.')
 row.update(status='TYPE_CONTRACT_GAP',severity='P2_EXACT_BUILTIN_OR_BINDING_CONTRACT',affected_workflow=row['original']['path'],root_cause_or_blocker=reason,evidence=['executed-binding-review-proof.json#'+row['id']],repro_command_and_result='Precisely selected original builtin/native call returned on listed successful context; raw static diagnostic retained',regression_and_result=contexts,remaining_condition='Precise record/protocol/overload typing remains P2; no suppression or baseline refresh');count+=1
(F/'diagnostic-ledger.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows));dest.write_text(json.dumps(dict(method=__doc__,proof=proof),ensure_ascii=False,indent=2)+'\n');print('bounded builtin/binding occurrences',count)

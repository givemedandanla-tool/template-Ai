"""Review concrete dict.update field-contract debt, preserving content validation."""
import argparse,ast,collections,json
from pathlib import Path
F=Path(__file__).resolve().parent;p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--points',default='runtime-points-006.json');p.add_argument('--capture',action='store_true');a=p.parse_args();run=F/a.run;o=json.loads((run/'observations.json').read_text());assert not o['runtime_errors'] and not o['observer_errors'] and o['source_unchanged'] and o['business_ast_equivalence_verified'];contexts=json.loads((run/('capture-contexts.json' if a.capture else 'tests.json')).read_text());passed={r['id'] for r in contexts if r['status']=='PASS'};modules=json.loads((run/'module-contexts.json').read_text()) if (run/'module-contexts.json').exists() else {};points={p['id']:p for p in json.loads((F/a.points).read_text())['points']};rows=[json.loads(x) for x in (F/'diagnostic-ledger.jsonl').read_text().splitlines()];dest=F/'dict-update-contract-proof.json';proof=json.loads(dest.read_text()).get('proof',{}) if dest.exists() else {};count=0
for r in rows:
 if r['status']!='UNREVIEWED' or r['rule'] not in ['reportArgumentType','reportCallIssue']:continue
 message=r['original']['message']
 if 'in function "update"' not in message and not message.startswith('No overloads for "update"'):continue
 actual=o['rows'].get(r['id'],{});values=actual.get('values',{});valid=[t for t in actual.get('test_contexts',[]) if t in passed]
 if not valid:valid=['owned-module:'+m for m in actual.get('module_contexts',[]) if m in modules and modules[m]['receipt']['healthy'] and set(modules[m]['tests'])<=passed]
 if not valid or set(values.get('call_receiver',{}))!={'builtins.dict'} or not values.get('call_result'):continue
 point=points[r['id']];calls=[t for t in point['targets'] if t['label']=='call_result']
 if len(calls)!=1:continue
 call=ast.parse(calls[0]['expression'],mode='eval').body
 if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Attribute) or call.func.attr!='update':continue
 named_fields=[k.arg for k in call.keywords if k.arg];reason='Concrete builtin dict.update accepts heterogeneous values in distinct named fields; the inferred homogeneous value union rejects this schema extension. The exact update call completed in its retained successful context. This is record/DTO typing debt, not permission to skip downstream content, source, ownership, generation or qualification checks.'
 proof[r['id']]=dict(original=r['original'],exact_call=calls[0],named_fields=named_fields,observed_types=values,contexts=valid,source=run.name+'/source.json',bounds='Only executed exact builtin dict update. Does not establish every value is semantically valid for every consumer, nor any unexecuted branch.',followup='Declare tagged/TypedDict record per producer and consumer; original raw warning remains retained')
 r.update(status='TYPE_CONTRACT_GAP',severity='P2_HETEROGENEOUS_RECORD_SCHEMA',affected_workflow=r['original']['path'],root_cause_or_blocker=reason,evidence=['dict-update-contract-proof.json#'+r['id']],repro_command_and_result='Exact original builtin update call returned on source-bound successful authored paths',regression_and_result=valid,remaining_condition='Producer/consumer DTO work remains P2; original content validators and deferred qualifications retained');count+=1
(F/'diagnostic-ledger.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows));dest.write_text(json.dumps(dict(method=__doc__,proof=proof),ensure_ascii=False,indent=2)+'\n');print('reviewed exact update',count)

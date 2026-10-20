"""Explicitly reviewed schemas for heterogeneous command/status/observation dicts."""
import ast,json,collections
from pathlib import Path
F=Path(__file__).resolve().parent
notes={
 'template_ai/batch_objects.py':'Rows start with id/kind/status strings and formal_eligible/attempted booleans. Prepared rows add snapshot/request dictionaries and changes/warnings lists. Execution results add state/outcome/reason/history strings. validate_request and exact selection/source/revision/seal checks remain active; formal_eligible stays false until whole-card validation. These are separate named fields, not one bool/string value type.',
 'template_ai/candidate_edit.py':'The command starts with ids list and cross_owner boolean, then adds operation PATCH/LOCK strings, a numeric patch dictionary or locked boolean. propose/prepare_edit validate exact target, generation and current input; distinct command fields require a typed tagged record.',
 'template_ai/candidate_sync.py':'A prepared row adds READY_FOR_EXPLICIT_CONFIRMATION status/reason strings and the explicit changed-property list. Manual delta/revision/dependency validation still gates adoption; the changes key is a list distinct from string/flag fields.',
 'template_ai/design_observation.py':'Unknown typography is deliberately represented by optional font_asset_ref=None and UNKNOWN source_font_status/text_run_segmentation/distribution_mode/alignment strings. These are absence-of-evidence markers, never a font truth/production approval. The observation record has heterogeneous named fields.',
 'template_ai/quality_source_rechecks.py':'Current validity adds component fingerprint and pipeline-ID lists plus the gold-version dictionary, each computed from exact current sources. These metadata keys are distinct from status booleans and do not waive pin/epoch/source checks.'}
rows=[json.loads(x) for x in (F/'diagnostic-ledger.jsonl').read_text().splitlines()];proof_path=F/'named-record-update-proof.json';proof=json.loads(proof_path.read_text()).get('proof',{}) if proof_path.exists() else {};count=0
for runname in ['runtime-ast-observations-001','ast-module-contexts-001','capture-type-evidence-001']:
 folder=F/runname;o=json.loads((folder/'observations.json').read_text());assert not o['observer_errors'] and not o['runtime_errors'] and o['business_ast_equivalence_verified'];contexts=json.loads((folder/('tests.json' if runname!='capture-type-evidence-001' else 'capture-contexts.json')).read_text());passed={c['id'] for c in contexts if c['status']=='PASS'}
 module_contexts=json.loads((folder/'module-contexts.json').read_text()) if (folder/'module-contexts.json').exists() else {}
 points={p['id']:p for p in json.loads((F/'runtime-points-006.json').read_text())['points']}
 for row in rows:
  if row['status']!='UNREVIEWED' or row['original']['path'] not in notes or row['rule']!='reportArgumentType' or 'in function "update"' not in row['original']['message']:continue
  actual=o['rows'].get(row['id'],{});values=actual.get('values',{});good_contexts=[c for c in actual.get('test_contexts',[]) if c in passed]
  if not good_contexts:good_contexts=['owned-module:'+m for m in actual.get('module_contexts',[]) if m in module_contexts and module_contexts[m]['receipt']['healthy'] and set(module_contexts[m]['tests'])<=passed]
  if not good_contexts or set(values.get('call_receiver',{}))!={'builtins.dict'} or not values.get('call_result'):continue
  p=points[row['id']];calls=[t for t in p['targets'] if t['label']=='call_result']
  if len(calls)!=1:continue
  call=ast.parse(calls[0]['expression'],mode='eval').body
  if not isinstance(call.func,ast.Attribute) or call.func.attr!='update':continue
  key=row['id'];reason=notes[row['original']['path']];proof[key]=dict(original=row['original'],schema_reason=reason,exact_call=calls[0],actual_values=values,successful_contexts=good_contexts,run=runname,validation_scope='Named-field schema debt only; original guards and all static findings retained; does not approve arbitrary payloads')
  row.update(status='TYPE_CONTRACT_GAP',severity='P2_EXPLICIT_NAMED_RECORD_SCHEMA',affected_workflow=row['original']['path'],root_cause_or_blocker=reason,evidence=['named-record-update-proof.json#'+key],regression_and_result=good_contexts,repro_command_and_result='Exact original dict receiver and normal update return observed on unchanged real source/Qt/assertions; explicit field schema reviewed')
  count+=1
(F/'diagnostic-ledger.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows));proof_path.write_text(json.dumps(dict(method=__doc__,proof=proof),ensure_ascii=False,indent=2)+'\n');print('named schema occurrences',count)

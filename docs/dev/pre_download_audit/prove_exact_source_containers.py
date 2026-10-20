"""Prove an exact highlighted object is a builtin container, without assuming keys exist."""
import ast,collections,json
from pathlib import Path
from coordinate_contract import index_for_diagnostic
from source_contract_engine import modules,infer,context
F=Path(__file__).resolve().parent;rows=[json.loads(x) for x in (F/'diagnostic-ledger.jsonl').read_text().splitlines()];proof=json.loads((F/'exact-source-container-proof.json').read_text()).get('proof',{}) if (F/'exact-source-container-proof.json').exists() else {}
for row in rows:
 if row['status']!='UNREVIEWED':continue
 if row['rule'] not in ['reportOptionalSubscript','reportIndexIssue','reportCallIssue','reportArgumentType']:continue
 if row['rule'] in ['reportCallIssue','reportArgumentType'] and not any(op in row['original']['message'] for op in ['__getitem__','__setitem__']):continue
 module=row['original']['path'][:-3].replace('/','.');info=modules.get(module)
 if info is None:continue
 n=index_for_diagnostic(info['tree'],info['lines'],row['original_range'],row['rule'])
 if n is None:continue
 fn,cls=context(module,n);value=infer(module,n.value,fn,cls)
 if value['kind'] not in ['dict','list','tuple','str','bytes']:continue
 # The indexed object's type is proven. This does not prove a key/index exists.
 if row['rule'] in ['reportCallIssue','reportArgumentType'] and value['kind']!='dict':continue
 key=row['id'];proof[key]=dict(original_range=row['original_range'],exact_object_expression=ast.unparse(n.value),object_kind=value['kind'],source_origins=value.get('origins',[]),original=row['original'],condition='Literal/consistent source-factory normal return; no nullable/unknown source accepted; exact UTF-16 range required',not_claimed='Key/index presence, arbitrary caller validity, or a replacement for runtime/revision validation')
 row.update(status='TYPE_CONTRACT_GAP',severity='P2_EXACT_CONTAINER_CONTRACT_DEBT',affected_workflow=row['original']['path'],root_cause_or_blocker='The precisely highlighted receiver has a concrete builtin container normal postcondition, rather than the unrelated scalar/None members of a heterogeneous inferred union',evidence=['exact-source-container-proof.json#'+key],repro_command_and_result='Original Git373b6ee AST pure inference; no product code execution or assertion/diagnostic suppression',regression_and_result='Exact full-module regression results bound separately; source constructor/factory locations in proof',remaining_condition='Preserve runtime key/range/ownership validation. Introduce precise named-field DTOs rather than Any.')
(F/'diagnostic-ledger.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n' for r in rows));(F/'exact-source-container-proof.json').write_text(json.dumps(dict(method=__doc__,proof=proof),ensure_ascii=False,indent=2)+'\n');print('exact source containers',len(proof))

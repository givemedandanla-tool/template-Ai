"""Annotation-only counterfactuals for two SQLite record postcondition hypotheses.

No application checkout, baseline or runtime behavior is changed. Diagnostics
stay visible in the original ledger; resolving a counterfactual is evidence of
missing typing under the documented postconditions, not a product certificate.
"""
import ast,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'docs/dev/debug_tooling'))
import quality
FOLDER=Path(__file__).resolve().parent
source=Path('/tmp/template-ai-audit-original-373b6ee')
previous=source
proof=[]
for stage,old,new,root_name in [
 ('write', 'def _write(self, kind, record_id, payload, expected_revision, action):', 'def _write(self, kind, record_id, payload, expected_revision, action) -> dict:', 'TRAINING_STORE_WRITE_READBACK'),
 ('records', 'def records(self, kind, offset=0, limit=200):', 'def records(self, kind, offset=0, limit=200) -> list[dict]:', 'TRAINING_STORE_SQL_CURSOR_RECORDS')]:
 variant=Path('/tmp/template-ai-audit-contract-'+stage)
 shutil.copytree(previous,variant)
 path=variant/'template_ai/training_store.py';body=path.read_text()
 if body.count(old)!=1:raise RuntimeError('Expected exact unique signature')
 path.write_text(body.replace(old,new))
 original=ast.parse((source/'template_ai/training_store.py').read_text());changed=ast.parse(path.read_text())
 for tree in [original,changed]:
  for node in ast.walk(tree):
   if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
    node.returns=None
    for arg in [*node.args.posonlyargs,*node.args.args,*node.args.kwonlyargs]:arg.annotation=None
 if ast.dump(original)!=ast.dump(changed):raise RuntimeError('Business AST changed in counterfactual')
 results={}
 for scope in ['application','tools','tests']:
  report=quality.scan(variant,scope,FOLDER/('record-contract-'+stage+'-'+scope))
  before=json.loads((FOLDER/(('original-position-' if stage=='write' else 'record-contract-write-')+scope)/'report.json').read_text())
  comparison=quality.compare(report,before)
  results[scope]={'original_count':len(before['findings']),'current_count':len(report['findings']),'resolved_count':comparison['resolved_count'],'new_count':comparison['new_count'],'resolved_fingerprints':list((__import__('collections').Counter(r['fingerprint'] for r in before['findings'])-__import__('collections').Counter(r['fingerprint'] for r in report['findings'])).items())}
  print(stage,scope,results[scope]['resolved_count'],results[scope]['new_count'],flush=True)
 proof.append({'stage':stage,'root':root_name,'old_signature':old,'counterfactual_signature':new,'business_ast_unchanged':True,'production_checkout_changed':False,'proof_scope':'SQL write readback / selected-row snapshot only; get() intentionally remains nullable','results':results})
 previous=variant
(FOLDER/'record-return-contract-proof.json').write_text(json.dumps({'stages':proof,'postconditions':{'TRAINING_STORE_WRITE_READBACK':'_write upserts the exact kind/id, writes history and epoch, calls the internal event inserter, then reads that same record on the same connection before returning. Normal validated schema has no deleting trigger; nullable get annotation loses this write-readback guarantee.','TRAINING_STORE_SQL_CURSOR_RECORDS':'records selects IDs for the same kind and obtains each record through the active SELECT cursor on the same SQLite connection/snapshot. It does not query arbitrary caller-supplied absent IDs.','not_asserted':'Missing arbitrary get lookups are still nullable. Corruption/custom callbacks or external qualification are not licensed by these two postconditions.'}},ensure_ascii=False,indent=2)+'\n')

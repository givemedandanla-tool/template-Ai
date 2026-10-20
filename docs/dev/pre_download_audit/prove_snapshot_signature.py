"""Isolated static negative sample: read decorator must retain public parameter checking."""
import hashlib,importlib.util,json,pathlib,subprocess,sys,tempfile
F=pathlib.Path(__file__).resolve().parent;ROOT=F.parents[2];sys.path.insert(0,str(ROOT/'docs/dev/debug_tooling'));spec=importlib.util.spec_from_file_location('audit_quality',ROOT/'docs/dev/debug_tooling/quality.py');quality=importlib.util.module_from_spec(spec);spec.loader.exec_module(quality)
source="""from sqlite3 import connect
from template_ai.metadata_snapshot import snapshot_read
@snapshot_read(lambda value: connect(':memory:'))
def typed_read(value: int) -> int:
    return value
valid = typed_read(1)
invalid = typed_read('authored invalid string')
"""
with tempfile.TemporaryDirectory(prefix='template-ai-signature-') as temp:
 p=pathlib.Path(temp);sample=p/'sample.py';sample.write_text(source);config=json.loads((F/'final-release-application-standard-002/pyrightconfig.json').read_text());config['include']=[str(sample)];config['extraPaths']=[str(ROOT)];(p/'pyrightconfig.json').write_text(json.dumps(config))
 command=['node',str(quality.home()/'node/node_modules/pyright/index.js'),'--project',str(p/'pyrightconfig.json'),'--pythonpath',str(ROOT/'.venv/bin/python'),'--outputjson'];r=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30);report=json.loads(r.stdout);diagnostics=[d for d in report['generalDiagnostics'] if d['file']==str(sample)];assert r.returncode==1 and len(diagnostics)==1 and diagnostics[0].get('rule')=='reportArgumentType',diagnostics
 proof=dict(status='PASS_ISOLATED_EXPECTED_STATIC_ERROR',qualification='Authored demonstration, not a product test failure or baseline change',tool_version=report['version'],sample=source,sample_sha256=hashlib.sha256(source.encode()).hexdigest(),diagnostic=diagnostics[0],exit_code=r.returncode,meaning='ParamSpec preserves typed_read(int)->int through snapshot_read; invalid string is still rejected. No Any/ignore/baseline refresh used.',source_sha256=hashlib.sha256((ROOT/'template_ai/metadata_snapshot.py').read_bytes()).hexdigest());(F/'snapshot-signature-proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n');print(proof['status'])

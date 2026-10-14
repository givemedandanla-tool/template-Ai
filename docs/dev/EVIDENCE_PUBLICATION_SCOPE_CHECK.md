# 有核准上傳例外時的只讀證據核對

本輪9件證明附件依使用者指令未上傳，乾淨GitHub checkout不會有這9件原檔。既有`dev_governance.py check`在這種checkout會回報附件失聯；它不是新程式失敗。全附件Gate維持未滿足。本頁只核對使用者核准的保存範圍，不宣稱229項測試覆蓋這段審核命令，也不修改原程式／測試／run。

先正常執行check；**只有**明列9件證明附件缺失時可採下列核對。缺程式／測試／metadata、已存在但hash不符、其他附件缺失、scope／來源或test失敗仍是阻塞，不得略過。最新回歸仍須依新來源重新執行，不能把這段命令替代軟體測試。

在repository根目錄執行：

```bash
python - <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, 'tools')
from dev_common import contract_digest, digest, manifest, manifest_digest
root = Path.cwd()
load = lambda p: json.loads((root / p).read_text(encoding='utf-8'))
state = load('docs/dev/STATE.json')
run_path = state['latest_evidence_run']
run = load(run_path)
folder = Path(run_path).parent
source = load(folder / 'source-manifest.json')
assert run['status'] == 'PASS' and run['source_unchanged']
assert manifest_digest(source) == run['source_manifest_sha256']
assert manifest_digest(manifest(root, code_only=True)) == run['source_manifest_sha256']
commit, tree = load(folder / 'commit.json'), load(folder / 'tree.json')
assert commit['sha'] == run['source_commit'] and commit['tree']['sha'] == tree['sha']
assert not tree.get('truncated')
remote = {r['path']: r['sha'] for r in tree['tree'] if r['type'] == 'blob'}
assert all(remote.get(p) == r['git_blob_sha1'] for p, r in source.items())
policy = load('docs/dev/EVIDENCE_PUBLICATION_EXCEPTIONS.json')
assert policy['policy'] == 'USER_AUTHORIZED_SKIP_EVIDENCE_ATTACHMENT_UPLOAD'
exceptions = {r['path']: r for r in policy['excluded_original_files']}
assert len(exceptions) == len(policy['excluded_original_files']) == 9
assert all(p.startswith(str(folder) + '/') and p.endswith(('.png', '.jpg', '.pdf')) for p in exceptions)
for p, r in exceptions.items():
    evidence = run['attachments'][Path(p).name]
    assert (r['bytes'], r['sha256']) == (evidence['bytes'], evidence['sha256'])
missing = []
for name, expected in run['attachments'].items():
    relative = str(folder / name)
    path = root / relative
    if not path.is_file():
        assert relative in exceptions, '未核准的附件缺失: ' + relative
        missing.append(relative)
    else:
        assert path.stat().st_size == expected['bytes'] and digest(path.read_bytes()) == expected['sha256']
tests_path = root / folder / 'tests.json'
assert digest(tests_path.read_bytes()) == run['tests_sha256']
tests = json.loads(tests_path.read_text())
results = {r['id']: r for r in tests}
assert len(results) == len(tests) == run['test_count'] == run['passed']
assert all(r['status'] == 'PASS' for r in tests)
claims = load(folder / 'claims.json')
for row in load('docs/dev/REQUIREMENTS.json')['requirements']:
    if not row['completed']:
        continue
    assert row['status'] == 'VERIFIED' and row['review_level'] == 'SELF_VERIFIED'
    assert row['evidence_run'] == run_path
    matched = [c for c in claims if c['requirement_id'] == row['id']]
    assert matched and all(c['contract_sha256'] == contract_digest(row) for c in matched)
    assert row['acceptance']
    for acceptance in row['acceptance']:
        assert acceptance['tests'] and all(results[t]['status'] == 'PASS' for t in acceptance['tests'])
print(json.dumps({'publication_scope_check': 'PASS', 'formal_tests': len(tests),
                  'locally_missing_authorized_attachments': missing,
                  'full_attachment_publication': 'NOT_CLAIMED'}, ensure_ascii=False))
PY
```

此命令已在原工作區（附件仍在）與只缺核准9件的乾淨保存view實際執行。正式結果與驗收保持原run；本命令只支援clone後的恢復與保存例外核對。

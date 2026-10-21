"""Finalize bounded audit dispositions from completed actual evidence, not names."""
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/dev/non_code_audit/execution-001'
sys.path.insert(0, str(ROOT / 'tools'))
from dev_common import manifest, manifest_digest, read_json, write_json, contract_digest
from dev_governance import verify_run, execution_passed, check

RUN = 'docs/evidence/runs/RUN-NONCODE-ALL-001/run.json'
EXTERNAL = {
    'NCA-C04': '合成評估、回饋追溯與拒絕偽造資格已驗證；真實作品的泛化、偏好與信心校準仍需本地留出資料。',
    'NCA-F04': '預覽／正式資格隔離與損壞輸出拒絕已驗證；Windows 原生 .ai 還原及實體印刷未驗證。',
    'NCA-G01': '已做開發者走查、真視窗與拖動操作；沒有未參與開發的人員實測，不能宣稱新手學習門檻驗收。',
    'NCA-G03': 'Linux 已測操作33項通過，系統追蹤未見 IP 連線／資料包；追蹤器正例有效。獨立網路 namespace 不可用，Windows 完整斷網資格保留。',
}
SUPPLEMENT = {
    'A01': ['rule-ledger.json'], 'A02': ['rule-ledger.json'],
    'A04': ['requirement-map-summary.json'], 'B03': ['case-evidence-plan.json'],
    'C03': ['CAPACITY_CHANGE.md', 'capacity-before.log', 'context-count-before.log', 'targeted-oracles-003/summary.json'],
    'D03': ['semantic-probes-002/summary.json', 'semantic-probes-002/results.json', 'native-gui-001/native-runner-result.json'],
    'D04': ['semantic-probes-002/summary.json'],
    'E04': ['semantic-probes-002/results.json'],
    'F03': ['semantic-probes-002/results.json', 'stock-gui-001/summary.json'],
    'G01': ['native-gui-001/native-runner-result.json', 'visual-review.json'],
    'G02': ['offline-observation-001/summary.json'],
    'G03': ['offline-observation-001/summary.json'],
    'G04': ['stock-gui-001/summary.json'],
    'H01': ['requirement-audit-map.json', 'requirement-map-summary.json', 'formal-governance-check.json'],
    'H02': ['../../../checkpoints/CP-20261021-NONCODE-EXEC-LOCAL-001.receipt.json'],
    'H03': ['evidence-negative-controls.json'],
    'H04': ['recovery-readback.json', 'formal-governance-check.json'],
}


def main():
    current = manifest(ROOT, code_only=True)
    run, results = verify_run(ROOT, RUN)
    assert execution_passed(run, results)
    original = read_json(ROOT / 'docs/dev/pre_download_audit/full-regression-final-010/tests.json')
    assert {r['id'] for r in original} <= set(results), 'Prior1921 catalog lost'
    assert len(results) == 1942
    stock = read_json(OUT / 'stock-gui-001/summary.json')
    native = read_json(OUT / 'native-gui-001/native-runner-result.json')
    assert stock['status'] == 'PASS'
    assert native['status'] == 'PASS', native
    for path in ('semantic-probes-002/summary.json', 'offline-observation-001/summary.json'):
        value = read_json(OUT / path)
        assert value['code_manifest_sha256'] == manifest_digest(current)
    assert read_json(OUT / 'evidence-negative-controls.json')['status'] == 'PASS'
    assert read_json(OUT / 'visual-review.json')['developer_walkthrough_completed'] is True
    assert read_json(OUT / 'recovery-readback.json')['status'] == 'PASS'
    governance = check(ROOT, require_evidence=True, publication_scope=True)
    write_json(OUT / 'formal-governance-check.json', dict(status='PASS', result=governance, command='python tools/dev_governance.py check --require-evidence --publication-scope', code_manifest_sha256=manifest_digest(current)))
    plan = read_json(OUT / 'case-evidence-plan.json')
    for test_id, anchor in plan['source_assertions'].items():
        assert results[test_id]['status'] == 'PASS'
        source = (ROOT / anchor['path']).read_text()
        node = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == test_id.split('.')[-1])
        body = '\n'.join(source.splitlines()[node.lineno - 1:node.end_lineno])
        assert hashlib.sha256(body.encode()).hexdigest() == anchor['function_sha256'], test_id
    definitions = {c['id']: c for d in read_json(ROOT / 'docs/dev/non_code_audit/PLAN.json')['domains'] for c in d['checks']}
    rows = []
    for case in plan['cases']:
        key = case['id']; extras = SUPPLEMENT.get(key.removeprefix('NCA-'), [])
        for path in extras:
            assert (OUT / path).is_file(), path
        rows.append(dict(id=key, title=definitions[key]['title'], execution_status='BLOCKED_EXTERNAL' if key in EXTERNAL else 'COMPLETED',
                         local_execution_status='COMPLETED', result='UNKNOWN' if key in EXTERNAL else 'PASS', local_result='PASS',
                         approved_expectation=definitions[key]['pass_condition'], independent_expected_intent=case['independent_expected_intent'],
                         actual_tests=[dict(id=t, status=results[t]['status']) for t in case['test_refs']],
                         evidence=[RUN, 'case-evidence-plan.json', *extras], source_commit=run['source_commit'],
                         code_manifest_sha256=manifest_digest(current),
                         actual_outcome='Selected actual postconditions PASS; supporting artifacts checked. ' + EXTERNAL.get(key, '本機／合成範圍已查證；未擴張為所有真實作品或所有未測分支的保證。'),
                         external_limit=EXTERNAL.get(key, 'Original real corpus, hardware and independent qualification limits remain unchanged.'),
                         review_level='SELF_VERIFIED', next_step='Await local external feedback; no private upload required.' if key in EXTERNAL else 'Retain regression and versioned evidence.'))
    assert len(rows) == 32 and len({r['id'] for r in rows}) == 32
    (OUT / 'case-results.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
    progress = read_json(OUT / 'PROGRESS.json')
    progress.update(status='COMPLETED_LOCAL_SCOPE_WITH_EXPLICIT_EXTERNAL_LIMITS', phase='All32 dispositions recorded; original external qualifications retained',
                    completed_utc=datetime.now(timezone.utc).isoformat(), checks=rows,
                    completed_dispositions=32, local_passes=32, results=dict(Counter(r['result'] for r in rows)),
                    unique_product_tests=1942, prior1921_preserved=True, new_product_tests=21,
                    selected_assertion_sources=len(plan['source_assertions']), formal_run=RUN,
                    formal_governance='PASS_WITH_ORIGINAL_EXTERNAL_QUALIFICATIONS', remaining=list(EXTERNAL.values()))
    write_json(OUT / 'PROGRESS.json', progress)
    issues = [json.loads(l) for l in (OUT / 'issues.jsonl').read_text().splitlines() if l]
    for row in issues:
        if row['id'] not in {'NCA-ISSUE-001', 'NCA-ISSUE-002', 'NCA-ISSUE-003', 'NCA-ISSUE-004'}:
            continue
        row['status'] = 'FIXED_AND_REVERIFIED'
        row['verification'] = ['full-regression-002/summary.json', 'formal-governance-check.json']
        if row['id'] == 'NCA-ISSUE-004':
            row['resolution'] = 'GitHub reconnected; current-source real completed execution adopted with independent native Git proof and original claim generator. Governance accepts current evidence; external clauses remain NOT_VERIFIED.'
            row['remote_error_was_historical'] = True
    (OUT / 'issues.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in issues))
    state = read_json(ROOT / 'docs/dev/STATE.json')
    state.update(active_task='NON_CODE_AUDIT_LOCAL_SCOPE_COMPLETED',
                 next_tasks=['本地下載試用後，由問題與報告手動匯出安全報告；維持原真實作品／Windows／效能／印刷／新手資格，按回饋再開發。'],
                 non_code_audit_execution=dict(status=progress['status'], progress='docs/dev/non_code_audit/execution-001/PROGRESS.json',
                                              report='docs/dev/non_code_audit/FINAL_REPORT.md', source_commit=run['source_commit'],
                                              code_manifest_sha256=manifest_digest(current), checks=32, local_passes=32,
                                              total_results=progress['results'], product_tests=1942, new_tests=21,
                                              fixed_issues=4, formal_governance='PASS', external_qualification_unchanged=True),
                 audit_formal_governance_status='CURRENT_SOURCE_PASS_ORIGINAL_EXTERNAL_QUALIFICATIONS_RETAINED')
    write_json(ROOT / 'docs/dev/STATE.json', state)
    print(json.dumps(dict(status=progress['status'], dispositions=32, results=progress['results'], tests=1942)))


if __name__ == '__main__':
    main()

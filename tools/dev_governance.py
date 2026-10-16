"""驗證要求／證據／交接的一致性；機器清單生成 Human 視圖，不反向猜狀態。"""
import argparse
import ast
import json
from pathlib import Path
import re

from dev_common import ROOT, contract_digest, digest, manifest, manifest_digest, read_json, safe_path


def test_ids(root):
    ids = set()
    for path in (Path(root) / "tests").glob("test_*.py"):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.ClassDef):
                for method in node.body:
                    if isinstance(method, ast.FunctionDef) and method.name.startswith("test_"):
                        ids.add(f"{path.stem}.{node.name}.{method.name}")
    return ids


def verify_run(root, run_path, current=True):
    root = Path(root)
    run_file = safe_path(root, run_path)
    run = read_json(run_file)
    folder = run_file.parent
    files = read_json(folder / "source-manifest.json")
    if manifest_digest(files) != run["source_manifest_sha256"]:
        raise ValueError("證據的來源 manifest 已变更")
    if current and manifest_digest(manifest(root, code_only=True)) != run["source_manifest_sha256"]:
        raise ValueError("證據已過期：程式／測試／fixture 已變更，需重新驗證")
    commit, tree = read_json(folder / "commit.json"), read_json(folder / "tree.json")
    if commit["sha"] != run["source_commit"] or commit["tree"]["sha"] != tree["sha"] or tree.get("truncated"):
        raise ValueError("證據來源 commit／tree 不符")
    remote = {item["path"]: item["sha"] for item in tree["tree"] if item["type"] == "blob"}
    if any(remote.get(path) != item["git_blob_sha1"] for path, item in files.items()):
        raise ValueError("證據來源與 GitHub 讀回 tree 不一致")
    from evidence_publication import waived_attachments
    waived, _ = waived_attachments(root, run_path, run)
    for name, item in run["attachments"].items():
        path = safe_path(folder, name)
        if not path.is_file() and str(path.relative_to(root)).replace('\\', '/') in waived:
            continue  # Existing-but-corrupt originals never qualify for a publication waiver.
        if not path.is_file() or path.stat().st_size != item["bytes"] or digest(path.read_bytes()) != item["sha256"]:
            raise ValueError("證據附件失聯或内容變更：" + name)
    tests = read_json(folder / "tests.json")
    if digest((folder / "tests.json").read_bytes()) != run["tests_sha256"]:
        raise ValueError("個別測試結果已變更")
    ids = [test["id"] for test in tests]
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError("測試結果重複或沒有實際測試")
    return run, {test["id"]: test for test in tests}


def check(root=ROOT, require_evidence=False, publication_scope=False):
    require_evidence = require_evidence or publication_scope
    root = Path(root)
    for path in ("AGENTS.md", ".github/copilot-instructions.md", "docs/dev/STATE.json", "docs/dev/HANDOFF.md",
                 "docs/dev/WORK_LOG.md", "docs/dev/REQUIREMENTS.json", "docs/dev/DEVELOPMENT_PROTOCOL.md", "docs/dev/EVIDENCE_DESIGN.md"):
        if not (root / path).is_file():
            raise ValueError("缺少開工入口或交接檔：" + path)
    state = read_json(root / "docs/dev/STATE.json")
    registry = read_json(root / "docs/dev/REQUIREMENTS.json")
    rows = registry["requirements"]
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("要求 ID 重複")
    remaining_contract = root / "docs/dev/FIXED70_REMAINING28_CONTRACT.json"
    if remaining_contract.is_file():
        contract = read_json(remaining_contract)
        indexed = contract.get("acceptance", [])
        for row in rows:
            if row["id"] in contract.get("target_parent_ids", []) and row.get("full_acceptance_registered"):
                entry = next((item for item in indexed if item.get("parent") == row["id"]), {})
                if not row["acceptance"] or entry.get("clause_count") != len(row["acceptance"]):
                    raise ValueError("完整父題條款數與索引不符：" + row["id"])
    tests = test_ids(root)
    runs = {}
    for row in rows:
        if not isinstance(row["completed"], bool):
            raise ValueError("要求需有明確 completed 布林")
        for parent in row.get("parents", []):
            if parent not in ids:
                raise ValueError("父要求不存在：" + parent)
        for acceptance in row["acceptance"]:
            if any(test not in tests for test in acceptance["tests"]):
                raise ValueError("驗收引用不存在的測試：" + row["id"])
        if not row["completed"]:
            continue
        if row["status"] != "VERIFIED" or row["review_level"] != "SELF_VERIFIED":
            raise ValueError("完成要求沒有合法驗證狀態：" + row["id"])
        run_path = row.get("evidence_run")
        if not run_path:
            raise ValueError("完成要求缺少證據 run：" + row["id"])
        if run_path not in runs:
            runs[run_path] = verify_run(root, run_path)
        run, results = runs[run_path]
        claims = read_json(safe_path(root, run_path).parent / "claims.json")
        matching_claims = [claim for claim in claims if claim["requirement_id"] == row["id"]]
        if not matching_claims or any(claim.get("contract_sha256") != contract_digest(row) for claim in matching_claims):
            raise ValueError("要求驗收範圍已變更，舊證據不可沿用：" + row["id"])
        if not row["acceptance"] or run["status"] != "PASS":
            raise ValueError("沒有驗收條件或執行失敗")
        for acceptance in row["acceptance"]:
            if not acceptance["tests"] or any(results.get(test, {}).get("status") != "PASS" for test in acceptance["tests"]):
                raise ValueError("驗收尚未逐項 PASS：" + row["id"])
    if state["exe_policy"] != "DEFERRED_NO_AUTOMATIC_BUILD":
        raise ValueError("EXE 政策與使用者要求不符")
    if "GOV-006" in ids:
        from dev_progress import validate
        validate(root)
    workflow = (root / ".github/workflows/first-version.yml").read_text(encoding="utf-8")
    if re.search(r"^  (push|pull_request):", workflow, re.MULTILINE):
        raise ValueError("EXE 工作流程仍會自動觸發")
    receipt = read_json(safe_path(root, state["last_confirmed_checkpoint"]))
    if receipt["phase"] != "REMOTE_VERIFIED":
        raise ValueError("交接沒有已確認 GitHub checkpoint")
    checkpoint = read_json(root / "docs/checkpoints" / (receipt["checkpoint_id"] + ".json"))
    if receipt["source_manifest_sha256"] != manifest_digest(checkpoint["source_files"]):
        raise ValueError("checkpoint 收據與原快照 manifest 不符")
    if require_evidence and not state.get("latest_evidence_run"):
        raise ValueError("框架尚未有最新實際證據")
    if state.get("latest_evidence_run"):
        latest, _ = verify_run(root, state["latest_evidence_run"])
        if require_evidence:
            folder = str(Path(state["latest_evidence_run"]).parent).replace("\\", "/")
            required = [state["latest_evidence_run"], *[folder + "/" + name for name in latest["attachments"]]]
            if publication_scope:
                from evidence_publication import waived_attachments
                waived, policies = waived_attachments(root, state['latest_evidence_run'], latest)
                required = [path for path in required if path not in waived] + policies
                for policy in policies:
                    recorded = checkpoint['source_files'].get(policy)
                    if not recorded or recorded['sha256'] != digest(safe_path(root, policy).read_bytes()):
                        raise ValueError('證據保存例外policy未在該checkpoint核對，不能略過')
            if any(path not in checkpoint["source_files"] for path in required):
                raise ValueError("證據還未全部納入已確認的遠端 checkpoint，不能當作永久保存完成")
    return {"status": "PASS", "requirements": len(rows), "completed_scoped": sum(row["completed"] for row in rows),
            "parent_topics": sum(row["kind"] == "topic" for row in rows), "tests_known": len(tests)}


def render(root=ROOT):
    root = Path(root)
    rows = read_json(root / "docs/dev/REQUIREMENTS.json")["requirements"]
    lines = ["# 程式要求與功能清單", "", "本檔由 REQUIREMENTS.json 生成；完整 UI 主題與具明確驗收範圍的 CORE 分開。完成只表示該列的驗收範圍，不代表全產品或 Windows／真實 AI 已驗證。", "",
             "| ID | 功能／要求 | 實作狀態 | 完成 | 範圍／延後條件 | 證據 |", "| --- | --- | --- | --- | --- | --- |"]
    for row in rows:
        evidence = f"[run](../../{row['evidence_run']})" if row.get("evidence_run") else "無有效新版證據"
        name = row["title"].replace("|", "／")
        scope = row["scope"].replace("|", "／")
        lines.append(f"| {row['id']} | {name} | {row['status']} | {'是' if row['completed'] else '否'} | {scope} | {evidence} |")
    lines += ["", "驗收細節、來源、具名測試、父要求、阻擋與下一步請讀 [REQUIREMENTS.json](REQUIREMENTS.json)。歷史 UI CSV 是來源索引，不再當作即時完成度。"]
    (root / "docs/dev/FEATURES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    from dev_progress import render as render_progress
    render_progress(root)
    return {"rendered": len(rows)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("check", "render"))
    parser.add_argument("--require-evidence", action="store_true")
    parser.add_argument("--publication-scope", action="store_true", help="核對已核准保存範圍；不等於全附件永久保存")
    args = parser.parse_args()
    result = render() if args.command == "render" else check(require_evidence=args.require_evidence, publication_scope=args.publication_scope)
    print(json.dumps(result))


if __name__ == "__main__":
    main()

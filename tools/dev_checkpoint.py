"""先做本機可恢復快照；GitHub 讀回後才能寫入遠端確認收據。"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import zipfile

from dev_common import ROOT, digest, manifest, manifest_digest, read_json, safe_path, valid_id, write_json


def prepare(root, checkpoint_id, source_commit, summary, next_step, requirement_ids):
    valid_id(checkpoint_id)
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("需提供已知 GitHub 基底提交 SHA")
    root = Path(root)
    record = root / "docs/checkpoints" / (checkpoint_id + ".json")
    local = root / ".checkpoints" / checkpoint_id
    if record.exists() or local.exists():
        raise FileExistsError("checkpoint ID 已存在；不可覆寫歷史")
    state_path = root / "docs/dev/STATE.json"
    if state_path.exists():
        state = read_json(state_path)
        state["pending_remote"] = list(dict.fromkeys([*state.get("pending_remote", []), checkpoint_id]))
        write_json(state_path, state)
    files = manifest(root)
    local.mkdir(parents=True)
    archive = local / "source.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            bundle.write(safe_path(root, path), path)
        bundle.writestr("CHECKPOINT_MANIFEST.json", json.dumps(files, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip():
            raise ValueError("checkpoint ZIP 完整性失敗")
    data = {"schema_version": 1, "id": checkpoint_id, "created_utc": datetime.now(timezone.utc).isoformat(),
            "base_commit": source_commit, "phase": "PREPARED", "summary": summary,
            "requirement_ids": requirement_ids, "next_step": next_step,
            "source_files": files, "source_manifest_sha256": manifest_digest(files),
            "local_snapshot": {"path": str(archive.relative_to(root)), "sha256": digest(archive.read_bytes())},
            "remote_confirmation": "尚未確認；本機快照不能冒稱已在 GitHub 保存"}
    write_json(record, data)
    return data


def acknowledge(root, checkpoint_id, commit_path, tree_path):
    valid_id(checkpoint_id)
    root = Path(root)
    checkpoint = read_json(root / "docs/checkpoints" / (checkpoint_id + ".json"))
    commit, tree = read_json(commit_path), read_json(tree_path)
    if commit["tree"]["sha"] != tree["sha"] or tree.get("truncated"):
        raise ValueError("遠端 commit／tree 不符或樹被截斷，不能確認")
    remote = {item["path"]: item["sha"] for item in tree["tree"] if item["type"] == "blob"}
    mismatches = [path for path, item in checkpoint["source_files"].items() if remote.get(path) != item["git_blob_sha1"]]
    if mismatches:
        raise ValueError("遠端快照未吻合：" + ", ".join(mismatches[:10]))
    record_path = f"docs/checkpoints/{checkpoint_id}.json"
    record_data = safe_path(root, record_path).read_bytes()
    import hashlib
    expected_record = hashlib.sha1(b"blob " + str(len(record_data)).encode() + b"\0" + record_data).hexdigest()
    if remote.get(record_path) != expected_record:
        raise ValueError("遠端 checkpoint 記錄本身未讀回一致")
    receipt = {"schema_version": 1, "checkpoint_id": checkpoint_id, "phase": "REMOTE_VERIFIED",
               "snapshot_commit": commit["sha"], "tree_sha": tree["sha"], "verified_utc": datetime.now(timezone.utc).isoformat(),
               "verified_files": len(checkpoint["source_files"]) + 1,
               "source_manifest_sha256": checkpoint["source_manifest_sha256"],
               "next_step": checkpoint["next_step"], "verification": "GitHub API commit/tree 讀回；逐檔 Git blob SHA 比對"}
    path = root / "docs/checkpoints" / (checkpoint_id + ".receipt.json")
    if path.exists():
        raise FileExistsError("遠端確認收據不可覆寫")
    write_json(path, receipt)
    state_path = root / "docs/dev/STATE.json"
    if state_path.exists():
        state = read_json(state_path)
        state["last_confirmed_checkpoint"] = str(path.relative_to(root)).replace("\\", "/")
        state["last_confirmed_commit"] = commit["sha"]
        state["pending_remote"] = [value for value in state.get("pending_remote", []) if value != checkpoint_id]
        write_json(state_path, state)
    return receipt


def restore_copy(root, checkpoint_id, destination):
    valid_id(checkpoint_id)
    root, destination = Path(root), Path(destination)
    if destination.exists():
        raise FileExistsError("恢復目錄必須不存在；不覆蓋工作區")
    record = read_json(root / "docs/checkpoints" / (checkpoint_id + ".json"))
    archive = safe_path(root, record["local_snapshot"]["path"])
    if digest(archive.read_bytes()) != record["local_snapshot"]["sha256"]:
        raise ValueError("本機快照內容已變更，不可恢復")
    with zipfile.ZipFile(archive) as bundle:
        for relative, item in record["source_files"].items():
            path = safe_path(destination, relative)
            content = bundle.read(relative)
            if digest(content) != item["sha256"]:
                raise ValueError("快照檔案不完整：" + relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    return {"restored": str(destination), "files": len(record["source_files"])}


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--id", required=True)
    prepare_parser.add_argument("--base-commit", required=True)
    prepare_parser.add_argument("--summary", required=True)
    prepare_parser.add_argument("--next", required=True)
    prepare_parser.add_argument("--requirements", nargs="*", default=[])
    ack = commands.add_parser("acknowledge")
    ack.add_argument("--id", required=True)
    ack.add_argument("--commit-json", type=Path, required=True)
    ack.add_argument("--tree-json", type=Path, required=True)
    restore = commands.add_parser("restore-copy")
    restore.add_argument("--id", required=True)
    restore.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(ROOT, args.id, args.base_commit, args.summary, args.next, args.requirements)
        print(json.dumps({"id": result["id"], "phase": result["phase"], "files": len(result["source_files"])}))
    elif args.command == "acknowledge":
        print(json.dumps(acknowledge(ROOT, args.id, args.commit_json, args.tree_json)))
    else:
        print(json.dumps(restore_copy(ROOT, args.id, args.destination)))


if __name__ == "__main__":
    main()

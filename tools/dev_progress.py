"""按穩定要求 ID 對帳；父需求、功能子項與治理不混算完成率。"""
import argparse
from datetime import datetime, timezone
from pathlib import Path

from dev_common import ROOT, contract_digest, digest, read_json, safe_path, valid_id, write_json

BUCKETS = ("verified", "implemented_pending", "partial", "in_progress", "not_implemented", "blocked", "deferred")
STATUSES = {"VERIFIED": "verified", "IMPLEMENTED_PENDING_VERIFICATION": "implemented_pending",
            "IMPLEMENTED_UNVERIFIED": "implemented_pending", "PARTIAL": "partial", "IN_PROGRESS": "in_progress",
            "NOT_IMPLEMENTED": "not_implemented", "BLOCKED": "blocked", "DEFERRED": "deferred"}
KINDS = ("topic", "core", "governance")


def summarize(rows):
    groups = {kind: {"total": 0, **{b: 0 for b in BUCKETS}} for kind in KINDS}
    seen = set()
    for row in rows:
        if row["id"] in seen or row["kind"] not in KINDS or row["status"] not in STATUSES:
            raise ValueError("進度要求 ID 重複、類別或狀態未知")
        seen.add(row["id"])
        bucket = STATUSES[row["status"]]
        if type(row["completed"]) is not bool or row["completed"] != (bucket == "verified"):
            raise ValueError("進度 completed 與驗證狀態不符")
        groups[row["kind"]]["total"] += 1
        groups[row["kind"]][bucket] += 1
    for group in groups.values():
        group["not_complete"] = group["total"] - group["verified"]
        group["has_implementation"] = group["verified"] + group["implemented_pending"] + group["partial"]
    return groups


def current(root=ROOT):
    path = Path(root) / "docs/dev/REQUIREMENTS.json"
    registry = read_json(path)
    rows = [{key: r[key] for key in ("id", "kind", "status", "completed")} |
            {"contract_sha256": contract_digest(r)} for r in registry["requirements"]]
    return {"schema_version": 1, "registry_sha256": digest(path.read_bytes()), "groups": summarize(rows), "rows": rows}


def compare(before, after):
    old = {r["id"]: r for r in before["rows"]}
    new = {r["id"]: r for r in after["rows"]}
    common = old.keys() & new.keys()
    return {"baseline_id": before.get("id"), "added": sorted(new.keys() - old.keys()),
            "removed": sorted(old.keys() - new.keys()),
            "scope_changed": sorted(i for i in common if old[i]["contract_sha256"] != new[i]["contract_sha256"]),
            "state_changed": [{"id": i, "before": old[i]["status"], "after": new[i]["status"]}
                              for i in sorted(common) if (old[i]["status"], old[i]["completed"]) != (new[i]["status"], new[i]["completed"])],
            "newly_verified": sorted(i for i in new if new[i]["completed"] and not old.get(i, {}).get("completed", False)),
            "delta": {k: {b: summarize(after["rows"])[k][b] - summarize(before["rows"])[k][b]
                          for b in ("total", *BUCKETS)} for k in KINDS}}


def render(root=ROOT):
    root = Path(root)
    data = current(root)
    write_json(root / "docs/dev/CURRENT_PROGRESS.json", data)
    lines = ["# 開發進度統計", "", "由 REQUIREMENTS.json 自動生成。父需求未滿足全部條件不能標完整完成；CORE 為明列驗收範圍，GOV 不計軟體功能。", "",
             "| 層級 | 總數 | 已驗證完成 | 已實作待驗證 | 部分實作 | 開發中 | 未實作 | 受阻 | 延後 | 尚未完整完成 |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for kind, name in (("topic", "原始需求"), ("core", "功能子項"), ("governance", "開發治理")):
        group = data["groups"][kind]
        lines.append("| " + name + " | " + " | ".join(str(group[k]) for k in ("total", *BUCKETS, "not_complete")) + " |")
    lines += ["", "「尚未完整完成」包含部分實作、待驗證、開發中、未實作、受阻與延後；「未實作」是其中一桶。不同粒度不能相加成產品完成百分比。", "",
              "每輪基準與結束快照見 progress/；差異包含新增／移除 ID、驗收範圍修訂、狀態轉移與新增完成。詳見機器統計 CURRENT_PROGRESS.json 及 FEATURES.md。"]
    (root / "docs/dev/PROGRESS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return data


def validate(root=ROOT):
    if read_json(Path(root) / "docs/dev/CURRENT_PROGRESS.json") != current(root):
        raise ValueError("進度統計與要求登錄不同步，先執行 render")


def snapshot(root, snapshot_id, baseline=None):
    valid_id(snapshot_id)
    root = Path(root)
    path = root / "docs/dev/progress" / (snapshot_id + ".json")
    if path.exists():
        raise FileExistsError("進度快照不可覆寫")
    data = current(root)
    data.update(id=snapshot_id, created_utc=datetime.now(timezone.utc).isoformat())
    if baseline:
        data["comparison"] = compare(read_json(safe_path(root, baseline)), data)
    write_json(path, data)
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("render", "snapshot"))
    parser.add_argument("--id")
    parser.add_argument("--baseline")
    args = parser.parse_args()
    result = render() if args.command == "render" else snapshot(ROOT, args.id, args.baseline)
    import json
    print(json.dumps({"groups": result["groups"], "comparison": result.get("comparison")}, ensure_ascii=False))

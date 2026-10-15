"""執行真實 unittest，保存單項結果／JUnit／來源版本／公開合成附件。"""
import argparse
from datetime import datetime, timezone
import io
import json
import mimetypes
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import unittest
import xml.etree.ElementTree as ET

from dev_common import ROOT, contract_digest, digest, manifest, manifest_digest, read_json, valid_id, write_json

sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class EvidenceResult(unittest.TextTestResult):
    def __init__(self, *args):
        super().__init__(*args)
        self.records = {}

    def startTest(self, test):
        super().startTest(test)
        self.records[test.id()] = {"id": test.id(), "status": "RUNNING", "started": time.perf_counter(), "details": []}

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records[test.id()]["status"] = "PASS"

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.records[test.id()]["status"] = "FAIL"
        self.records[test.id()]["details"].append(self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self.records[test.id()]["status"] = "ERROR"
        self.records[test.id()]["details"].append(self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.records[test.id()]["status"] = "SKIP"
        self.records[test.id()]["details"].append(reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self.records[test.id()]["status"] = "EXPECTED_FAILURE"

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self.records[test.id()]["status"] = "UNEXPECTED_SUCCESS"

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err:
            self.records[test.id()]["status"] = "FAIL"
            self.records[test.id()]["details"].append(str(subtest) + "\n" + self._exc_info_to_string(err, test))

    def stopTest(self, test):
        record = self.records[test.id()]
        record["seconds"] = round(time.perf_counter() - record.pop("started"), 6)
        super().stopTest(test)


def junit(records, path):
    suite = ET.Element("testsuite", name="template-Ai", tests=str(len(records)),
                       failures=str(sum(r["status"] in ("FAIL", "UNEXPECTED_SUCCESS") for r in records)),
                       errors=str(sum(r["status"] == "ERROR" for r in records)),
                       skipped=str(sum(r["status"] in ("SKIP", "EXPECTED_FAILURE") for r in records)))
    for record in records:
        identity, method = record["id"].rsplit(".", 1)
        case = ET.SubElement(suite, "testcase", classname=identity, name=method, time=str(record["seconds"]),
                             file="tests/" + identity.split(".")[0] + ".py")
        if record["status"] != "PASS":
            kind = "skipped" if record["status"] in ("SKIP", "EXPECTED_FAILURE") else "error" if record["status"] == "ERROR" else "failure"
            ET.SubElement(case, kind, message=record["status"]).text = "\n".join(record["details"])
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--commit-json", type=Path, required=True)
    parser.add_argument("--tree-json", type=Path, required=True)
    args = parser.parse_args()
    valid_id(args.run_id)
    folder = ROOT / "docs/evidence/runs" / args.run_id
    if folder.exists():
        raise FileExistsError("run ID 已存在，不能覆寫歷史驗證")
    commit, tree = read_json(args.commit_json), read_json(args.tree_json)
    before = manifest(ROOT, code_only=True)
    remote = {item["path"]: item["sha"] for item in tree["tree"] if item["type"] == "blob"}
    if commit["sha"] != args.source_commit or commit["tree"]["sha"] != tree["sha"] or tree.get("truncated"):
        raise ValueError("測試來源 commit／tree 不符")
    missing = [path for path, item in before.items() if remote.get(path) != item["git_blob_sha1"]]
    if missing:
        raise ValueError("請先 checkpoint 並保存待測程式到 GitHub：" + ", ".join(missing[:10]))
    folder.mkdir(parents=True)
    write_json(folder / "commit.json", commit)
    write_json(folder / "tree.json", tree)
    write_json(folder / "source-manifest.json", before)
    log = io.StringIO()
    runner = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=EvidenceResult)
    result = runner.run(unittest.defaultTestLoader.discover(str(ROOT / "tests")))
    records = list(result.records.values())
    write_json(folder / "tests.json", records)
    (folder / "tests.log").write_text(log.getvalue(), encoding="utf-8")
    junit(records, folder / "junit.xml")
    capture_log = folder / "capture.log"
    capture_code = 1
    if result.wasSuccessful() and records:
        generated = ROOT / ".checkpoints/evidence-workspaces" / args.run_id
        command = [sys.executable, str(ROOT / "tools/validate_first_version.py"), "--skip-tests",
                   "--artifacts-dir", str(generated), "--dpi", "96"]
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        capture_code = process.returncode
        capture_log.write_text(process.stdout + process.stderr, encoding="utf-8")
        if capture_code == 0:
            extra=subprocess.run([sys.executable,str(ROOT / 'tools/capture_fixed70_ten.py'),'--artifacts-dir',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
            with capture_log.open('a') as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
        if capture_code == 0:
            for path in generated.glob('fixed70-*'):
                if path.is_file():shutil.copyfile(path,folder/path.name)
        if capture_code == 0:
            extra=subprocess.run([sys.executable,str(ROOT / "tools/capture_diagnostics.py"),"--artifacts-dir",str(generated)],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=60)
            with capture_log.open("a") as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
        if capture_code == 0:
            extra=subprocess.run([sys.executable,str(ROOT / "tools/capture_entities.py"),"--artifacts-dir",str(generated)],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=60)
            with capture_log.open("a") as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
        if capture_code == 0:
            extra=subprocess.run([sys.executable,str(ROOT / "tools/capture_catalog.py"),"--artifacts-dir",str(generated)],cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=60)
            with capture_log.open("a") as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
        if capture_code == 0:
            for name in ("output-workspace.png", "training-workspace.png", "template-workspace.png", "decorated-output-workspace.png", "multiple-artworks-workspace.png", "batch-source-preview.png", "font-center-workspace.png", "font-center-diagnostics.png",
                         "font-candidates-ranked.png", "font-candidates-preview.png", "font-candidate-line.png", "font-candidates-report.json",
                         "font-review-differences.png", "font-review-approved.png", "font-review-draft-history.png", "font-review-undone.png", "font-review-audit.json",
                         "canvas-compare-overview.png", "canvas-compare-focused.png", "canvas-compare-source.png", "canvas-compare-before.png", "canvas-compare-after.png", "canvas-compare-report.json",
                         "object-tools-multiselect.png", "object-tools-mixed-patch.png", "object-tools-difference.png", "object-tools-history.png", "object-tools-locked.png", "object-tools-training.png", "object-tools-audit.json",
                         "semantic-tree-shared.png", "semantic-search-preserved.png", "semantic-viewport-isolated.png", "semantic-derived-structure.png", "semantic-index-audit.json",
                         "batch-import-preflight.png", "batch-import-running.png", "batch-import-cancelled.png", "batch-import-resumed.png", "batch-import-audit.json",
                         "exception-center-ranked.png", "exception-center-excluded.png", "exception-center-restored.png", "exception-center-retry-preview.png", "exception-center-retried.png", "exception-center-audit.json",
                         "ten-quality-overview.png", "ten-facts-confirmed.png", "ten-noise-authoring.png", "ten-rule-review.png", "ten-noise-auto-hit.png", "ten-noise-recovery.png", "ten-trusted-sample.png", "ten-dataset-learned-draft.png", "ten-coverage-distribution.png", "ten-training-queue-completed.png", "ten-packages-audit.json",
                         "synthetic-FINAL.pdf", "synthetic-FINAL.png", "synthetic-FINAL.jpg", "decorated-FINAL.pdf", "decorated-FINAL.png", "decorated-FINAL.jpg",
                         "diagnostic-preview.png", "diagnostic-saved-reopened.png", "diagnostic-stale-refused.png", "diagnostic-work-issues.png", "diagnostic-safe-report.json", "diagnostic-gui-audit.json", "entity-person-cards.png", "entity-adopted-input.png", "entity-customer-diff.png", "entity-gui-audit.json", "catalog-template-icons.png", "catalog-template-list.png", "catalog-explicit-editor.png", "catalog-customer-source-preview.png", "catalog-customer-compare.png", "catalog-customer-prefilled.png", "catalog-gui-audit.json"):
                if not (generated / name).is_file():
                    capture_code = 1
                    break
                shutil.copyfile(generated / name, folder / name)
    else:
        capture_log.write_text("測試未成功，未將畫面產物冒稱驗證成功\n", encoding="utf-8")
    source_unchanged = manifest_digest(before) == manifest_digest(manifest(ROOT, code_only=True))
    from PySide6 import __version__ as qt_version
    from template_ai.importer import inkscape_path
    converter = inkscape_path()
    inkscape_version = subprocess.run([converter, "--version"], capture_output=True, text=True, timeout=10).stdout.strip() if converter else None
    status = "PASS" if result.wasSuccessful() and records and capture_code == 0 and source_unchanged else "FAIL"
    tests_lookup = {item["id"]: item["status"] for item in records}
    registry = read_json(ROOT / "docs/dev/REQUIREMENTS.json")
    claims = []
    for row in registry["requirements"]:
        if row["kind"] == "topic" and (not row.get("full_acceptance_registered",False) and row["id"] not in ("UI-066-R1","UI-066-R2")):
            continue
        for acceptance in row["acceptance"]:
            passed = status == "PASS" and bool(acceptance["tests"]) and all(tests_lookup.get(test) == "PASS" for test in acceptance["tests"])
            claims.append({"requirement_id": row["id"], "acceptance_id": acceptance["id"], "expected": acceptance["expected"],
                           "tests": acceptance["tests"], "status": "PASS" if passed else "NOT_VERIFIED", "scope": row["scope"], "contract_sha256": contract_digest(row)})
    write_json(folder / "claims.json", claims)
    seventy = ROOT / "docs/dev/SEVENTY_PARENTS_CONTRACT.json"
    if seventy.is_file():
        contract = read_json(seventy)
        trace = [{"parent": s["parent"], "scoped_requirement": s["id"], "implemented_subset": s["acceptance"], "remaining_parent_scope": s["remaining"], "tests": [{"id": tid, "status": tests_lookup.get(tid, "MISSING")} for tid in s["tests"]], "scoped_pass": status == "PASS" and bool(s["tests"]) and all(tests_lookup.get(tid) == "PASS" for tid in s["tests"])} for s in contract["scopes"]]
        write_json(folder / "seventy-parent-audit.json", {"evidence_kind": "DERIVED_TRACEABILITY_FROM_ACTUAL_TESTS_NOT_EXTRA_EXECUTION", "source_commit": args.source_commit, "source_unchanged": source_unchanged, "baseline_partial": 53, "target_partial": 70, "new_scopes": trace, "all_scopes_pass": all(s["scoped_pass"] for s in trace), "full_parent_completion_claim": False, "historical_contract_blocked": 2, "historical_contract_deferred": 3, "current_parent_states": {state:sum(r["kind"]=="topic" and r["status"]==state for r in registry["requirements"]) for state in ("PARTIAL","BLOCKED","DEFERRED","VERIFIED","NOT_IMPLEMENTED","IMPLEMENTED_PENDING_VERIFICATION")}})
    attachments = {path.name: {"bytes": path.stat().st_size, "sha256": digest(path.read_bytes()), "mime": mimetypes.guess_type(path.name)[0] or "text/plain"}
                   for path in folder.iterdir() if path.is_file()}
    run = {"schema_version": 1, "id": args.run_id, "created_utc": datetime.now(timezone.utc).isoformat(), "source_commit": args.source_commit,
           "source_manifest_sha256": manifest_digest(before), "source_unchanged": source_unchanged, "status": status,
           "test_count": len(records), "passed": sum(r["status"] == "PASS" for r in records), "capture_exit_code": capture_code,
           "tests_sha256": digest((folder / "tests.json").read_bytes()), "attachments": attachments,
           "environment": {"python": platform.python_version(), "os": platform.platform(), "PySide6": qt_version, "inkscape": inkscape_version, "qt_platform": os.environ.get("QT_QPA_PLATFORM")},
           "command": "python tools/run_evidence.py --run-id " + args.run_id + " --source-commit " + args.source_commit + " --commit-json <readback> --tree-json <readback>",
           "review_level": "SELF_VERIFIED", "scope": "合成資料／Linux 或實際執行器；個別測試結果與真實匿名附件",
           "not_verified": ["真實私人 Illustrator 全面視覺一致", "VivoBook／RTX 5050", "實體印刷", "Windows EXE", "獨立覆核"]}
    write_json(folder / "run.json", run)
    print(json.dumps({"run": args.run_id, "status": status, "tests": len(records), "passed": run["passed"], "attachments": len(attachments)}))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

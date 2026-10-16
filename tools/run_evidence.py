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
import traceback
import unittest
import faulthandler
import xml.etree.ElementTree as ET

from dev_common import ROOT, contract_digest, digest, manifest, manifest_digest, read_json, valid_id, write_json

sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class EvidenceResult(unittest.TextTestResult):
    def __init__(self, *args, progress_path=None):
        super().__init__(*args)
        self.records = {}
        self.progress_path=progress_path

    def progress(self,test,phase):
        if self.progress_path is None:return
        completed=[record for record in self.records.values() if 'seconds' in record]
        value=dict(phase=phase,current_test=test.id() if test else None,started=len(self.records),completed=len(completed),passed=sum(record['status']=='PASS' for record in completed),failed_ids=[record['id'] for record in completed if record['status'] in ('FAIL','ERROR','UNEXPECTED_SUCCESS')][:20],formal_complete=False,updated_at=datetime.now(timezone.utc).isoformat())
        temporary=self.progress_path.with_suffix('.tmp');write_json(temporary,value);os.replace(temporary,self.progress_path)

    def startTest(self, test):
        super().startTest(test)
        self.records[test.id()] = {"id": test.id(), "status": "RUNNING", "started": time.perf_counter(), "details": []}
        self.progress(test,'RUNNING_TEST')

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
        if self.progress_path is not None:
            with self.progress_path.with_suffix('.jsonl').open('a',encoding='utf-8') as journal:journal.write(json.dumps(record,ensure_ascii=False)+'\n')
        self.progress(test,'TEST_FINISHED')


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
    live=ROOT/'.checkpoints'/'formal-live'/args.run_id;live.mkdir(parents=True,exist_ok=False)
    def test_catalog(suite):
        for test in suite:
            if isinstance(test,unittest.TestSuite):yield from test_catalog(test)
            else:yield test.id()
    from evidence_modules import run_modules
    result,runtime_errors,module_log=run_modules(list(test_catalog(unittest.defaultTestLoader.discover(str(ROOT/'tests')))),live)
    log.write(module_log)
    for diagnostic in live.iterdir():
        if diagnostic.is_file():shutil.copy2(diagnostic,folder/diagnostic.name)
    write_json(folder/'runtime-errors.json',runtime_errors)
    records = list(result.records.values())
    write_json(folder / "tests.json", records)
    (folder / "tests.log").write_text(log.getvalue(), encoding="utf-8")
    junit(records, folder / "junit.xml")
    capture_log = folder / "capture.log"
    capture_code = 1
    if result.wasSuccessful() and records and not runtime_errors:
        generated = ROOT / ".checkpoints/evidence-workspaces" / args.run_id
        command = [sys.executable, str(ROOT / "tools/validate_first_version.py"), "--skip-tests",
                   "--artifacts-dir", str(generated), "--dpi", "96"]
        process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
        capture_code = process.returncode
        capture_log.write_text(process.stdout + process.stderr, encoding="utf-8")
        if capture_code == 0:
            extra=subprocess.run([sys.executable,str(ROOT / 'tools/capture_next_twenty.py'),'--artifacts-dir',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90)
            with capture_log.open('a') as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
        if capture_code == 0:
            for path in generated.glob('next20-*'):
                if path.is_file():shutil.copyfile(path,folder/path.name)
        if capture_code == 0:
            extra=subprocess.run([sys.executable,str(ROOT/'tools/capture_next_twentyeight.py'),'--artifacts-dir',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90)
            with capture_log.open('a') as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
            if capture_code==0:
                for path in generated.glob('next28-*'):
                    if path.is_file():shutil.copyfile(path,folder/path.name)
        if capture_code == 0:
            extra=subprocess.run([sys.executable,str(ROOT/'tools/capture_remaining28.py'),'--artifacts-dir',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
            with capture_log.open('a') as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
            if capture_code==0:
                for path in generated.glob('remaining28-*'):
                    if path.is_file():shutil.copyfile(path,folder/path.name)
        if capture_code == 0:
            # Keep the real repair chain in its own owned capture process so
            # previous Qt captures do not share live widgets/model graphs.
            extra=subprocess.run([sys.executable,str(ROOT/'tools/capture_quality_repair.py'),'--artifacts-dir',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
            with capture_log.open('a') as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
            if capture_code==0:
                for path in generated.glob('remaining28-repair-*'):
                    if path.is_file():shutil.copyfile(path,folder/path.name)
        if capture_code == 0:
            extra=subprocess.run([sys.executable,str(ROOT/'tools/capture_trusted_samples.py'),'--artifacts-dir',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
            with capture_log.open('a') as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
            if capture_code==0:
                for path in generated.glob('trusted-samples-*'):
                    if path.is_file():shutil.copyfile(path,folder/path.name)
        if capture_code == 0:
            extra=subprocess.run([sys.executable,str(ROOT/'tools/capture_qualified_coverage.py'),'--artifacts-dir',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
            with capture_log.open('a') as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
            if capture_code==0:
                for path in generated.glob('qualified-coverage-*'):
                    if path.is_file():shutil.copyfile(path,folder/path.name)
        if capture_code == 0:
            extra=subprocess.run([sys.executable,str(ROOT/'tools/capture_layout_risk_session.py'),'--folder',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60)
            with capture_log.open('a') as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
            if capture_code==0:
                for path in generated.glob('layout-risk-session-*'):
                    if path.is_file():shutil.copyfile(path,folder/path.name)
        if capture_code == 0:
            extra=subprocess.run([sys.executable,str(ROOT/'tools/capture_candidate_changes.py'),'--folder',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
            with capture_log.open('a') as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
            if capture_code==0:
                for path in generated.glob('candidate-changes-*'):
                    if path.is_file():shutil.copyfile(path,folder/path.name)
        if capture_code == 0:
            extra=subprocess.run([sys.executable,str(ROOT/'tools/capture_candidate_results.py'),'--folder',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
            with capture_log.open('a') as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
            if capture_code==0:
                for path in generated.glob('candidate-results-*'):
                    if path.is_file():shutil.copyfile(path,folder/path.name)
        if capture_code == 0:
            extra=subprocess.run([sys.executable,str(ROOT/'tools/capture_sync_workflow.py'),'--folder',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
            with capture_log.open('a') as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
            if capture_code==0:
                for path in generated.glob('sync-workflow-*'):
                    if path.is_file():shutil.copyfile(path,folder/path.name)
        if capture_code == 0:
            extra=subprocess.run([sys.executable,str(ROOT/'tools/capture_workbench_navigation.py'),'--folder',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
            with capture_log.open('a') as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
            if capture_code==0:
                for path in generated.glob('workbench-navigation-*'):
                    if path.is_file():shutil.copyfile(path,folder/path.name)
        if capture_code == 0:
            extra=subprocess.run([sys.executable,str(ROOT/'tools/capture_property_context.py'),'--folder',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
            with capture_log.open('a') as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
            if capture_code==0:
                for path in generated.glob('property-context-*'):
                    if path.is_file():shutil.copyfile(path,folder/path.name)
        if capture_code == 0:
            extra=subprocess.run([sys.executable,str(ROOT/'tools/capture_canvas_commands.py'),'--folder',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
            with capture_log.open('a') as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
            if capture_code==0:
                for path in generated.glob('canvas-command-*'):
                    if path.is_file():shutil.copyfile(path,folder/path.name)
        if capture_code == 0:
            extra=subprocess.run([sys.executable,str(ROOT/'tools/capture_batch_correction.py'),'--folder',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
            with capture_log.open('a') as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
            if capture_code==0:
                for pattern in ('batch-correction-*','batch-source-metadata.json','batch-candidate-metadata.json'):
                    for path in generated.glob(pattern):
                        if path.is_file():shutil.copyfile(path,folder/path.name)
        if capture_code == 0:
            extra=subprocess.run([sys.executable,str(ROOT/'tools/capture_major_review.py'),'--folder',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
            with capture_log.open('a') as log:log.write(extra.stdout+extra.stderr)
            capture_code=extra.returncode
            if capture_code==0:
                for path in generated.glob('major-review-*'):
                    if path.is_file():shutil.copyfile(path,folder/path.name)
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
    status = "PASS" if result.wasSuccessful() and records and capture_code == 0 and source_unchanged and not runtime_errors else "FAIL"
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
    ten_contract=ROOT/'docs/dev/FIXED70_NEXT_TEN_CONTRACT.json'
    if ten_contract.is_file():
        ten=read_json(ten_contract);targets=set(ten['target_parent_ids'])
        actual=[c for c in claims if c['requirement_id'] in targets]
        write_json(folder/'fixed70-ten-parent-audit.json',dict(
            kind='DERIVED_CLAUSE_TRACEABILITY_FROM_ACTUAL_TEST_EXECUTION',source_commit=args.source_commit,
            source_unchanged=source_unchanged,parent_count=len(targets),clause_count=len(actual),
            parents=[dict(id=pid,clauses=[c for c in actual if c['requirement_id']==pid]) for pid in ten['target_parent_ids']],
            all_registered_clauses_pass=bool(actual) and all(c['status']=='PASS' for c in actual),
            independent_review=False,physical_print_verified=False,private_ai_comprehensive_verified=False))
    twenty_eight=ROOT/'docs/dev/FIXED70_NEXT_TWENTYEIGHT_CONTRACT.json'
    if twenty_eight.is_file():
        contract=read_json(twenty_eight);targets=contract['target_parent_ids'];parent_clauses=[dict(id=pid,clauses=[c for c in claims if c['requirement_id']==pid]) for pid in targets]
        expected={a['parent']:a.get('clause_count',0) for a in contract['acceptance']}
        complete=all(parent['clauses'] and len(parent['clauses'])==expected.get(parent['id']) and all(c['status']=='PASS' for c in parent['clauses']) for parent in parent_clauses)
        write_json(folder/'fixed70-twentyeight-parent-audit.json',dict(kind='DERIVED_CLAUSE_TRACEABILITY_FROM_ACTUAL_TEST_EXECUTION',source_commit=args.source_commit,source_unchanged=source_unchanged,parent_count=len(targets),clause_count=sum(len(p['clauses']) for p in parent_clauses),parents=parent_clauses,all_registered_clauses_pass=complete,independent_review=False,physical_print_verified=False,private_ai_comprehensive_verified=False))
        if not complete:status='FAIL'
    remaining=ROOT/'docs/dev/FIXED70_REMAINING28_CONTRACT.json'
    if remaining.is_file():
        contract=read_json(remaining);targets=contract['target_parent_ids']
        expected={a['parent']:a.get('clause_count',0) for a in contract['acceptance']}
        parents=[]
        for pid in targets:
            actual=[c for c in claims if c['requirement_id']==pid]
            registered=expected.get(pid,0)>0
            passed=registered and len(actual)==expected[pid] and all(c['status']=='PASS' for c in actual)
            parents.append(dict(id=pid,registered=registered,clauses=actual,software_self_verified=passed))
            if registered and not passed:status='FAIL'
        complete=len(parents)==28 and all(p['software_self_verified'] for p in parents)
        write_json(folder/'remaining28-full-parent-audit.json',dict(kind='DERIVED_FROM_ACTUAL_TESTS_NOT_EXTRA_EXECUTION',
            source_commit=args.source_commit,source_unchanged=source_unchanged,target_count=28,parents=parents,
            verified_count=sum(p['software_self_verified'] for p in parents),all_28_complete=complete,
            goal_status='SELF_VERIFIED_SOFTWARE' if complete else 'IN_PROGRESS',
            independent_review=False,windows_reference_hardware_verified=False))
    seventy = ROOT / "docs/dev/SEVENTY_PARENTS_CONTRACT.json"
    if seventy.is_file():
        contract = read_json(seventy)
        trace = [{"parent": s["parent"], "scoped_requirement": s["id"], "implemented_subset": s["acceptance"], "remaining_parent_scope": s["remaining"], "tests": [{"id": tid, "status": tests_lookup.get(tid, "MISSING")} for tid in s["tests"]], "scoped_pass": status == "PASS" and bool(s["tests"]) and all(tests_lookup.get(tid) == "PASS" for tid in s["tests"])} for s in contract["scopes"]]
        write_json(folder / "seventy-parent-audit.json", {"evidence_kind": "DERIVED_TRACEABILITY_FROM_ACTUAL_TESTS_NOT_EXTRA_EXECUTION", "source_commit": args.source_commit, "source_unchanged": source_unchanged, "baseline_partial": 53, "target_partial": 70, "new_scopes": trace, "all_scopes_pass": all(s["scoped_pass"] for s in trace), "full_parent_completion_claim": False, "historical_contract_blocked": 2, "historical_contract_deferred": 3, "current_parent_states": {state:sum(r["kind"]=="topic" and r["status"]==state for r in registry["requirements"]) for state in ("PARTIAL","BLOCKED","DEFERRED","VERIFIED","NOT_IMPLEMENTED","IMPLEMENTED_PENDING_VERIFICATION")}})
    attachments = {path.name: {"bytes": path.stat().st_size, "sha256": digest(path.read_bytes()), "mime": mimetypes.guess_type(path.name)[0] or "text/plain"}
                   for path in folder.iterdir() if path.is_file()}
    run = {"schema_version": 1, "id": args.run_id, "created_utc": datetime.now(timezone.utc).isoformat(), "source_commit": args.source_commit,
           "source_manifest_sha256": manifest_digest(before), "source_unchanged": source_unchanged, "status": status,
           "unhandled_runtime_errors":len(runtime_errors), "test_count": len(records), "passed": sum(r["status"] == "PASS" for r in records), "capture_exit_code": capture_code,
           "tests_sha256": digest((folder / "tests.json").read_bytes()), "attachments": attachments,
           "environment": {"python": platform.python_version(), "os": platform.platform(), "PySide6": qt_version, "inkscape": inkscape_version, "qt_platform": os.environ.get("QT_QPA_PLATFORM")},
           "command": "python tools/run_evidence.py --run-id " + args.run_id + " --source-commit " + args.source_commit + " --commit-json <readback> --tree-json <readback>",
           "review_level": "SELF_VERIFIED", "scope": "合成資料／Linux 或實際執行器；個別測試結果與真實匿名附件",
           "not_verified": ["真實私人 Illustrator 全面視覺一致", "VivoBook／RTX 5050", "實體印刷", "Windows EXE", "獨立覆核"]}
    run.update(test_execution_strategy='SERIAL_OWNED_FRESH_MODULE_PROCESSES',test_module_count=len(result.modules),planned_test_count=len(result.expected),not_completed_test_count=len(result.expected)-len(result.records))
    write_json(folder / "run.json", run)
    print(json.dumps({"run": args.run_id, "status": status, "tests": len(records), "passed": run["passed"], "attachments": len(attachments)}))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

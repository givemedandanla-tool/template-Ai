"""治理故障演練：不完整、跳過、過期或未保存不能被當作完成。"""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from dev_common import contract_digest, digest, manifest, manifest_digest, read_json, write_json
from dev_checkpoint import acknowledge, prepare, restore_copy
from dev_governance import check, verify_run


class DevFrameworkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("AGENTS.md", ".github/copilot-instructions.md", "docs/dev/HANDOFF.md", "docs/dev/WORK_LOG.md", "docs/dev/DEVELOPMENT_PROTOCOL.md", "docs/dev/EVIDENCE_DESIGN.md"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("持久入口\n", encoding="utf-8")
        (self.root / "app.py").write_text("print('synthetic code')\n", encoding="utf-8")
        tests = self.root / "tests/test_sample.py"
        tests.parent.mkdir()
        tests.write_text("class SampleTests:\n    def test_ok(self):\n        pass\n", encoding="utf-8")
        workflow = self.root / ".github/workflows/first-version.yml"
        workflow.parent.mkdir(parents=True)
        workflow.write_text("on:\n  workflow_dispatch:\n", encoding="utf-8")
        self.record = {"id": "CORE-X", "kind": "core", "title": "合成驗收", "completed": False,
            "status": "IMPLEMENTED_UNVERIFIED", "review_level": "NOT_REVIEWED", "parents": [], "scope": "合成",
            "acceptance": [{"id": "CORE-X-A1", "expected": "PASS", "tests": ["test_sample.SampleTests.test_ok"]}], "evidence_run": None}
        write_json(self.root / "docs/dev/REQUIREMENTS.json", {"requirements": [self.record]})
        cp = prepare(self.root, "CP-TEST", "a" * 40, "合成快照", "合成下一步", ["CORE-X"])
        commit, tree = self.remote_context(cp)
        acknowledge(self.root, "CP-TEST", commit, tree)
        self.state = {"exe_policy": "DEFERRED_NO_AUTOMATIC_BUILD", "last_confirmed_checkpoint": "docs/checkpoints/CP-TEST.receipt.json", "latest_evidence_run": None}
        write_json(self.root / "docs/dev/STATE.json", self.state)

    def remote_context(self, checkpoint):
        files = manifest(self.root)
        tree = {"sha": "b" * 40, "truncated": False, "tree": [{"path": path, "sha": item["git_blob_sha1"], "type": "blob"} for path, item in files.items()]}
        commit = {"sha": "a" * 40, "tree": {"sha": tree["sha"]}}
        write_json(self.root / "commit-readback.json", commit)
        write_json(self.root / "tree-readback.json", tree)
        return self.root / "commit-readback.json", self.root / "tree-readback.json"

    def make_run(self, status="PASS"):
        folder = self.root / "docs/evidence/runs/RUN-TEST"
        files = manifest(self.root, code_only=True)
        write_json(folder / "source-manifest.json", files)
        write_json(folder / "commit.json", {"sha": "a" * 40, "tree": {"sha": "b" * 40}})
        write_json(folder / "tree.json", {"sha": "b" * 40, "truncated": False, "tree": [{"path": path, "type": "blob", "sha": item["git_blob_sha1"]} for path, item in files.items()]})
        write_json(folder / "tests.json", [{"id": "test_sample.SampleTests.test_ok", "status": status}])
        write_json(folder / "claims.json", [{"requirement_id": "CORE-X", "contract_sha256": contract_digest(self.record)}])
        attachment = folder / "actual.txt"
        attachment.write_text("合成實際附件", encoding="utf-8")
        write_json(folder / "run.json", {"source_commit": "a" * 40, "source_manifest_sha256": manifest_digest(files), "status": "PASS",
            "attachments": {"actual.txt": {"bytes": attachment.stat().st_size, "sha256": digest(attachment.read_bytes())}},
            "tests_sha256": digest((folder / "tests.json").read_bytes())})
        return "docs/evidence/runs/RUN-TEST/run.json"

    def complete(self, path):
        row = copy.deepcopy(self.record)
        row.update(completed=True, status="VERIFIED", review_level="SELF_VERIFIED", evidence_run=path)
        write_json(self.root / "docs/dev/REQUIREMENTS.json", {"requirements": [row]})

    def test_checkpoint_restore_and_remote_ack(self):
        restored = self.root / "recovered"
        restore_copy(self.root, "CP-TEST", restored)
        self.assertEqual((restored / "app.py").read_bytes(), (self.root / "app.py").read_bytes())
        self.assertEqual(read_json(self.root / "docs/checkpoints/CP-TEST.receipt.json")["phase"], "REMOTE_VERIFIED")
        with self.assertRaises(FileExistsError):
            restore_copy(self.root, "CP-TEST", restored)

    def test_checkpoint_rejects_mismatched_remote_and_existing_id(self):
        with self.assertRaises(FileExistsError):
            prepare(self.root, "CP-TEST", "a" * 40, "不可覆寫", "下一步", [])
        checkpoint = prepare(self.root, "CP-NEW", "a" * 40, "新快照", "下一步", [])
        commit, tree_path = self.remote_context(checkpoint)
        tree = read_json(tree_path)
        next(item for item in tree["tree"] if item["path"] == "app.py")["sha"] = "c" * 40
        write_json(tree_path, tree)
        with self.assertRaisesRegex(ValueError, "未吻合"):
            acknowledge(self.root, "CP-NEW", commit, tree_path)
        self.assertFalse((self.root / "docs/checkpoints/CP-NEW.receipt.json").exists())
        with self.assertRaises(ValueError):
            prepare(self.root, "../../bad", "a" * 40, "錯誤", "下一步", [])

    def test_missing_entry_blocks_work(self):
        self.assertEqual(check(self.root)["status"], "PASS")
        (self.root / "AGENTS.md").unlink()
        with self.assertRaisesRegex(ValueError, "缺少開工入口"):
            check(self.root)

    def test_skipped_or_missing_test_cannot_complete(self):
        path = self.make_run(status="SKIP")
        self.complete(path)
        with self.assertRaisesRegex(ValueError, "逐項 PASS"):
            check(self.root)
        write_json(self.root / "docs/dev/REQUIREMENTS.json", {"requirements": [self.record]})
        self.assertEqual(check(self.root)["completed_scoped"], 0)
        row = copy.deepcopy(self.record)
        row["acceptance"][0]["tests"] = ["not_a_real_test"]
        write_json(self.root / "docs/dev/REQUIREMENTS.json", {"requirements": [row]})
        with self.assertRaisesRegex(ValueError, "不存在的測試"):
            check(self.root)

    def test_changed_source_and_attachment_invalidate_evidence(self):
        path = self.make_run()
        self.complete(path)
        self.assertEqual(check(self.root)["completed_scoped"], 1)
        original = (self.root / "app.py").read_bytes()
        (self.root / "app.py").write_text("changed code\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "證據已過期"):
            verify_run(self.root, path)
        (self.root / "app.py").write_bytes(original)
        (self.root / "docs/evidence/runs/RUN-TEST/actual.txt").write_text("changed output", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "附件失聯"):
            check(self.root)

    def test_automatic_exe_trigger_is_rejected(self):
        (self.root / ".github/workflows/first-version.yml").write_text("on:\n  push:\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "自動觸發"):
            check(self.root)

    def test_changed_acceptance_cannot_reuse_old_pass(self):
        path = self.make_run()
        self.complete(path)
        registry = read_json(self.root / "docs/dev/REQUIREMENTS.json")
        registry["requirements"][0]["acceptance"][0]["expected"] = "新的驗收要求"
        write_json(self.root / "docs/dev/REQUIREMENTS.json", registry)
        with self.assertRaisesRegex(ValueError, "範圍已變更"):
            check(self.root)

    def test_checkpoint_records_pending_and_clears_after_ack(self):
        checkpoint = prepare(self.root, "CP-NEXT", "a" * 40, "下一工作包", "下一步", [])
        self.assertEqual(read_json(self.root / "docs/dev/STATE.json")["pending_remote"], ["CP-NEXT"])
        commit, tree = self.remote_context(checkpoint)
        acknowledge(self.root, "CP-NEXT", commit, tree)
        state = read_json(self.root / "docs/dev/STATE.json")
        self.assertEqual(state["pending_remote"], [])
        self.assertEqual(state["last_confirmed_checkpoint"], "docs/checkpoints/CP-NEXT.receipt.json")

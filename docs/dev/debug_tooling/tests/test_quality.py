"""Tooling contract tests; isolated demo, never customer-data acceptance."""
from __future__ import annotations

import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import bootstrap
import quality


class BaselineSafetyTests(unittest.TestCase):
    def report(self, findings):
        return {"profile": {"sha256": "fixed", "scope": "application"}, "versions": {"ruff": "fixed"}, "findings": findings, "source": {"head": "demo"}}

    def test_duplicate_occurrence_is_new_even_when_fingerprint_matches(self):
        finding = {"fingerprint": "identical", "tool": "ruff"}
        result = quality.compare(self.report([finding, finding]), self.report([finding]))
        self.assertEqual(result["status"], "NEW_FINDINGS")
        self.assertEqual(result["existing_count"], 1)
        self.assertEqual(result["new_count"], 1)

    def test_tool_or_profile_changes_cannot_reuse_old_baseline(self):
        old = self.report([])
        for field in ("profile", "versions"):
            current = copy.deepcopy(old)
            current[field]["changed"] = True
            with self.assertRaisesRegex(ValueError, "mismatch"):
                quality.compare(current, old)

    def test_line_shift_does_not_hide_or_reclassify_same_issue(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "example.py"
            source.write_text("return missing_value\n")
            first = quality.diagnostic("ruff", "F821", "example.py", 1, "Undefined name", root)
            source.write_text("# added unrelated line\nreturn missing_value\n")
            shifted = quality.diagnostic("ruff", "F821", "example.py", 2, "Undefined name", root)
            self.assertEqual(first["fingerprint"], shifted["fingerprint"])
            shifted["fingerprint"] = "different-new-problem"
            self.assertEqual(quality.compare(self.report([shifted]), self.report([first]))["new_count"], 1)

    def test_initial_baseline_cannot_overwrite_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "baseline.json"
            quality.dump(path, {"original": True}, exclusive=True)
            with self.assertRaises(FileExistsError):
                quality.dump(path, {"original": False}, exclusive=True)
            self.assertIn('"original": true', path.read_text())


class ScopeAndIntegrityTests(unittest.TestCase):
    def test_inventory_includes_new_untracked_and_entrypoint_but_no_private_or_vendor(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            app = root / "template_ai"
            app.mkdir()
            for relative in ("first.py", "new_untracked.py", "vendor/external.py", ".private/customer.py"):
                path = app / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("pass\n")
            (root / "app.py").write_text("pass\n")
            names = {p.relative_to(root).as_posix() for p in quality.inventory(root, "application")}
            self.assertEqual(names, {"app.py", "template_ai/first.py", "template_ai/new_untracked.py"})

    def test_empty_and_missing_scope_never_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(ValueError):
                quality.inventory(root, "application")
            (root / "template_ai").mkdir()
            with self.assertRaisesRegex(ValueError, "Empty"):
                quality.inventory(root, "application")

    def test_ambiguous_or_unlisted_report_paths_are_rejected(self):
        root = Path("/demo")
        files = [root / "one/same.py", root / "two/same.py"]
        with self.assertRaisesRegex(ValueError, "Ambiguous"):
            quality.locate("same.py", files, root)
        with self.assertRaises(ValueError):
            quality.locate("missing.py", files, root)

    def test_tampered_skill_refuses_use(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "skill.md").write_text("altered upstream")
            quality.dump(directory / "TOOLCHAIN.json", {"skills": {"skill.md": {"sha256": "0" * 64}}})
            with patch.object(bootstrap, "HERE", directory):
                with self.assertRaisesRegex(RuntimeError, "integrity"):
                    bootstrap.verify_sources()

    def test_existing_report_directory_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FileExistsError):
                quality.scan(Path(temporary), "application", Path(temporary))


class LiveLocalToolTests(unittest.TestCase):
    def test_known_ruff_parser_limit_is_retained_and_classified(self):
        source = "value = 1;match = 2\n"
        compile(source, "soft-keyword-demo.py", "exec")
        result = subprocess.run([str(bootstrap.executable(bootstrap.home() / "python", "ruff")), "check", "--config", str(HERE / "ruff.toml.txt"), "--output-format", "json", "--stdin-filename", "soft-keyword-demo.py", "-"], input=source, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 1, "Known upstream limitation changed; review and migrate the documented baseline")
        self.assertIn("invalid-syntax", result.stdout)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "valid.py").write_text(source)
            finding = quality.diagnostic("ruff", "invalid-syntax", "valid.py", 1, "Parser limitation", root, syntax_validated=True)
            self.assertEqual(finding["category"], "TOOL_PARSER_LIMITATION_CPYTHON_ACCEPTS")
            self.assertEqual(quality.compare(self.report_for(finding), self.report_for(None))["new_count"], 1)

    def report_for(self, finding):
        return {"profile": {}, "versions": {}, "source": {}, "findings": [finding] if finding else []}

    def test_real_tools_catch_then_clear_only_isolated_new_findings(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = quality.selftest(Path(temporary) / "evidence")
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(len(result["checks"]), 9)
            self.assertTrue(all(result["checks"].values()))
            self.assertEqual(result["before"], result["repaired"])


if __name__ == "__main__":
    unittest.main()

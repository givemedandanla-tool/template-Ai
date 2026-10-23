import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from dev_common import write_json
from dev_progress import compare, current, render, snapshot, summarize, validate


class DevProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = [dict(id="UI-X",kind="topic",status="PARTIAL",completed=False,scope="full",parents=[],acceptance=[]),
                     dict(id="CORE-X",kind="core",status="VERIFIED",completed=True,scope="subset",parents=["UI-X"],acceptance=[]),
                     dict(id="GOV-X",kind="governance",status="DEFERRED",completed=False,scope="future",parents=[],acceptance=[])]
        write_json(self.root / "docs/dev/REQUIREMENTS.json", {"requirements": self.rows})

    def test_groups_conserve_counts_without_parent_completion(self):
        groups = summarize(self.rows)
        self.assertEqual(groups["topic"]["verified"], 0)
        self.assertEqual(groups["topic"]["not_complete"], 1)
        self.assertEqual(groups["core"]["verified"], 1)
        self.assertEqual(groups["governance"]["deferred"], 1)
        for group in groups.values():
            self.assertEqual(sum(group[k] for k in ("verified","implemented_pending","partial","in_progress","not_implemented","blocked","deferred")), group["total"])

    def test_added_scope_and_status_changes_are_distinct(self):
        before = current(self.root)
        changed = copy.deepcopy(self.rows)
        changed[0]["scope"] = "revised full"
        changed[2]["status"] = "IN_PROGRESS"
        changed.append(dict(id="CORE-Y",kind="core",status="VERIFIED",completed=True,scope="new",parents=["UI-X"],acceptance=[]))
        write_json(self.root / "docs/dev/REQUIREMENTS.json", {"requirements": changed})
        delta = compare(before, current(self.root))
        self.assertEqual(delta["added"], ["CORE-Y"])
        self.assertEqual(delta["scope_changed"], ["UI-X"])
        self.assertEqual(delta["newly_verified"], ["CORE-Y"])
        self.assertEqual(delta["delta"]["topic"]["verified"], 0)
        self.assertEqual(delta["state_changed"], [{"id":"GOV-X","before":"DEFERRED","after":"IN_PROGRESS"}])

    def test_snapshots_immutable_and_current_report_detects_drift(self):
        render(self.root)
        validate(self.root)
        snapshot(self.root, "BEFORE")
        with self.assertRaises(FileExistsError):
            snapshot(self.root, "BEFORE")
        self.rows[0]["status"] = "NOT_IMPLEMENTED"
        write_json(self.root / "docs/dev/REQUIREMENTS.json", {"requirements": self.rows})
        with self.assertRaisesRegex(ValueError, "不同步"):
            validate(self.root)
        after = snapshot(self.root, "AFTER", "docs/dev/progress/BEFORE.json")
        self.assertEqual(after["comparison"]["delta"]["topic"]["partial"], -1)

    def test_invalid_or_duplicate_status_cannot_hide_unfinished_work(self):
        for change in ({"status":"UNKNOWN"}, {"completed":True}, {"kind":"everything"}):
            rows = copy.deepcopy(self.rows); rows[0].update(change)
            with self.assertRaises(ValueError): summarize(rows)
        with self.assertRaises(ValueError): summarize([self.rows[0], self.rows[0]])

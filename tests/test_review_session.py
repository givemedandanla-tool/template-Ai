"""Behaviour tests for the private review snapshot and human/analysis separation."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from template_ai.review_tool.session import SessionCorruptError, SessionStore


def make_font(path, family="Review Test Sans"):
    """Small valid font, parsed by the real fontTools path in annotate_font."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder([".notdef", "space", "A"])
    builder.setupCharacterMap({32: "space", 65: "A"})
    glyphs = {}
    for name in [".notdef", "space", "A"]:
        pen = TTGlyphPen(None)
        if name == "A":
            pen.moveTo((80, 0)); pen.lineTo((300, 700)); pen.lineTo((520, 0)); pen.closePath()
        glyphs[name] = pen.glyph()
    builder.setupGlyf(glyphs)
    builder.setupHorizontalMetrics({name: (600, 0) for name in glyphs})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": family, "styleName": "Regular",
                            "uniqueFontIdentifier": family + "-fixture-1",
                            "fullName": family + " Regular",
                            "psName": family.replace(" ", "") + "-Regular", "version": "Version 1.0"})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    builder.setupMaxp()
    builder.save(str(path))


def result(text="private-person@example.com"):
    return {"status": "ANALYSED", "source": {"hash": "source-content-hash", "page_count": 1},
            "pages": [{"id": "page-1", "page": 1, "image": "/private/source-preview.png",
                       "width_mm": 60, "height_mm": 30}],
            "works": [{"id": "work-1", "page_id": "page-1", "page": 1,
                       "crop": {"x": 10, "y": 5, "w": 60, "h": 30},
                       "image": "/private/source-preview.png", "relations": [],
                       "fields": [{"id": "field-1", "rect": {"x": 3, "y": 4, "w": 20, "h": 3},
                                   "source_rect": {"x": 13, "y": 9, "w": 20, "h": 3},
                                   "text": text, "kind": "email", "owner": None,
                                   "evidence": {"status": "OBSERVED"},
                                   "measurements": {"source_pt": {"value": None, "status": "UNKNOWN"}}},
                                  {"id": "field-2", "rect": {"x": 3, "y": 10, "w": 18, "h": 3},
                                   "text": "0900-000-000", "kind": "mobile", "owner": None}]}],
            "issues": [{"code": "FONT_UNKNOWN", "summary": "private detail should not enter safe report"}]}


def partial_and_full():
    partial = result()
    partial.update(schema_version=1, analysis_version="review-observations-1", status="PARTIAL")
    partial["source"].update(hash="a" * 64, lineage="a" * 64, page_count=2)
    partial["pages"][0].update(image_hash="first-preview-hash", calibrated=True)
    full = deepcopy(partial)
    full["status"] = "ANALYSED"
    second_page = deepcopy(full["pages"][0])
    second_page.update(id="page-2", page=2, image_hash="second-preview-hash")
    second_work = deepcopy(full["works"][0])
    second_work.update(id="work-2", page_id="page-2", page=2)
    full["pages"].append(second_page)
    full["works"].append(second_work)
    return partial, full


class ReviewSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="review-session-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "private-customer-name.ai"
        self.source.write_text("synthetic source; original bytes remain unchanged")
        self.store = SessionStore(self.root / "data")
        self.source_id = self.store.add_files([self.source])[0]["id"]

    def analyse(self):
        self.store.apply_analysis(self.source_id, result())
        return self.store.get_work("work-1")

    def test_register_deduplicates_path_but_does_not_hash_or_change_original(self):
        self.assertEqual(self.store.add_files([self.source]), [])
        self.assertNotIn("hash", self.store.get_source(self.source_id))
        self.assertEqual(self.source.read_text(), "synthetic source; original bytes remain unchanged")
        self.store.save()
        reopened = SessionStore(self.store.root)
        self.assertEqual(reopened.sources()[0]["id"], self.source_id)
        self.assertFalse(reopened.dirty)

    def test_edit_owner_share_relation_and_selection_survive_save_and_reopen(self):
        self.analyse()
        person = self.store.add_owner("private-person", "PERSON")
        company = self.store.add_owner("private-company", "COMPANY")
        original = deepcopy(self.store.get_field("work-1", "field-1")["prediction"])
        self.store.update_field("work-1", "field-1", text="corrected@example.com",
                                owner=person["id"], shared_with=[company["id"]], review_state="REVIEWED")
        relation = self.store.add_relation("work-1", ["field-1", "field-2"], "aligned_left")
        self.store.select(self.source_id, "work-1", "field-1")
        self.store.save()
        reopened = SessionStore(self.store.root)
        field = reopened.get_field("work-1", "field-1")
        self.assertEqual(field["text"], "corrected@example.com")
        self.assertEqual(field["owner"], person["id"])
        self.assertEqual(field["shared_with"], [company["id"]])
        self.assertEqual(field["prediction"], original)
        self.assertEqual(reopened.get_work("work-1")["relations"][0]["id"], relation["id"])
        self.assertEqual(reopened.data["selection"]["field_id"], "field-1")

    def test_complete_keeps_unknown_separate_and_does_not_grant_training(self):
        self.analyse()
        self.assertEqual(self.store.complete_work("work-1")["status"], "INCOMPLETE")
        self.assertTrue(all(f["review_state"] == "UNCHECKED" for f in self.store.get_work("work-1")["fields"]))
        self.store.update_field("work-1", "field-1", review_state="REVIEWED")
        self.store.update_field("work-1", "field-2", review_state="UNKNOWN")
        complete = self.store.complete_work("work-1")
        self.assertEqual(complete["status"], "REVIEWED_WITH_UNKNOWNS")
        self.assertEqual((complete["reviewed"], complete["unknown"], complete["unchecked"]), (1, 1, 0))
        self.assertEqual(complete["training_admission"], "NOT_GRANTED_BY_REVIEW")
        self.assertIsNone(self.store.get_field("work-1", "field-1")["measurements"]["source_pt"]["value"])

    def test_reanalysis_never_replaces_manual_records_or_their_active_dependencies(self):
        self.analyse()
        before = deepcopy(self.store.get_source(self.source_id)["analysis"])
        self.store.update_field("work-1", "field-1", text="manual correction")
        self.store.apply_analysis(self.source_id, result("new analysis"))
        source = self.store.get_source(self.source_id)
        self.assertEqual(source["analysis"], before)
        self.assertEqual(self.store.get_field("work-1", "field-1")["text"], "manual correction")
        self.assertTrue(source["analysis_update_pending"])
        self.assertEqual(len(source["analysis_versions"]), 2)
        self.assertEqual(source["analysis_versions"][1]["result"]["works"][0]["fields"][0]["text"], "new analysis")

    def test_invalid_analysis_is_rejected_without_partial_mutation(self):
        self.analyse()
        before = deepcopy(self.store.data)
        broken = result()
        broken["works"][0]["fields"].append(deepcopy(broken["works"][0]["fields"][0]))
        with self.assertRaises(ValueError):
            self.store.apply_analysis(self.source_id, broken)
        self.assertEqual(self.store.data, before)

    def test_remove_annotation_cleans_relations_and_undo_restores_them(self):
        self.analyse()
        self.store.add_relation("work-1", ["field-1", "field-2"], "aligned_left")
        self.store.remove_annotation("work-1", "field-1")
        self.assertEqual(self.store.get_work("work-1")["relations"], [])
        self.assertTrue(self.store.undo())
        self.assertEqual(len(self.store.get_work("work-1")["relations"]), 1)
        self.assertEqual(self.store.get_field("work-1", "field-1")["text"], "private-person@example.com")
        self.assertEqual(self.store.data["history"][-1]["operation"], "UNDO")

    def test_geometry_edits_preserve_source_prediction_and_page_positions(self):
        self.analyse()
        self.store.resize_annotation("work-1", "field-1", {"x": 5, "y": 6, "w": 22, "h": 4})
        field = self.store.get_field("work-1", "field-1")
        self.assertEqual(field["prediction"]["rect"]["x"], 3)
        self.assertEqual(field["source_rect"]["x"], 13)
        self.assertEqual(field["current_source_rect"]["x"], 15)
        self.store.resize_work("work-1", {"x": 12, "y": 8, "w": 40, "h": 15})
        field = self.store.get_field("work-1", "field-1")
        self.assertEqual((field["rect"]["x"], field["rect"]["y"]), (3, 3))
        self.assertEqual((field["current_source_rect"]["x"], field["current_source_rect"]["y"]), (15, 11))
        self.assertEqual(field["prediction"]["rect"]["x"], 3)
        self.store.save()

    def test_missing_region_can_be_added_and_removed_without_touching_source(self):
        self.analyse()
        added = self.store.add_work(self.source_id, "page-1", {"x": 2, "y": 3, "w": 20, "h": 10})
        field = self.store.add_annotation(added["id"], "LOGO", {"x": 1, "y": 1, "w": 3, "h": 3})
        self.assertEqual(field["prediction"], {})
        self.store.update_field(added["id"], field["id"], review_state="UNKNOWN")
        self.assertEqual(self.store.complete_work(added["id"])["status"], "REVIEWED_WITH_UNKNOWNS")
        self.store.remove_work(added["id"])
        self.assertTrue(self.store.undo())
        self.assertEqual(self.store.get_work(added["id"])["fields"][0]["id"], field["id"])
        self.assertEqual(self.source.read_text(), "synthetic source; original bytes remain unchanged")

    def test_corrupt_main_recovers_verified_backup_and_keeps_good_backup(self):
        self.analyse()
        self.store.save()
        self.store.update_field("work-1", "field-1", text="new saved value")
        self.store.save()
        backup = self.store.backup_path.read_bytes()
        self.store.path.write_bytes(b"truncated")
        reopened = SessionStore(self.store.root)
        self.assertIsNotNone(reopened.recovery_notice)
        self.assertTrue(reopened.dirty)
        self.assertEqual(reopened.get_field("work-1", "field-1")["text"], "private-person@example.com")
        self.assertEqual(reopened.path.read_bytes(), b"truncated")
        reopened.save()
        self.assertEqual(reopened.backup_path.read_bytes(), backup)
        self.assertFalse(reopened.dirty)

    def test_all_corrupt_snapshots_raise_and_are_not_silently_replaced(self):
        self.store.path.write_bytes(b"bad-main")
        self.store.backup_path.write_bytes(b"bad-backup")
        with self.assertRaises(SessionCorruptError):
            SessionStore(self.store.root)
        self.assertEqual(self.store.path.read_bytes(), b"bad-main")
        self.assertEqual(self.store.backup_path.read_bytes(), b"bad-backup")

    def test_failed_atomic_save_preserves_old_snapshot_and_dirty_changes(self):
        import template_ai.review_tool.session as module
        self.analyse()
        self.store.save()
        self.store.update_field("work-1", "field-1", text="unsaved")
        original_write = module._atomic_write
        def fail_main(path, data):
            if Path(path) == self.store.path:
                raise OSError("disk full")
            original_write(path, data)
        with patch.object(module, "_atomic_write", side_effect=fail_main):
            with self.assertRaises(OSError):
                self.store.save()
        self.assertTrue(self.store.dirty)
        self.assertEqual(self.store.get_field("work-1", "field-1")["text"], "unsaved")
        reopened = SessionStore(self.store.root)
        self.assertEqual(reopened.get_field("work-1", "field-1")["text"], "private-person@example.com")

    def test_private_package_and_safe_report_have_different_privacy_boundaries(self):
        self.analyse()
        self.store.add_owner("SENSITIVE OWNER NAME")
        self.store.stage_status(self.source_id, "PARTIAL", "private local error /secret/location")
        package_path = self.store.export_observation_package(self.root / "private-package.json")
        package = json.loads(package_path.read_text())
        self.assertTrue(package["private_data_included"])
        self.assertEqual(package["qualification"], "OBSERVATION_AND_MANUAL_REVIEW_ONLY")
        self.assertIn("private-person@example.com", package_path.read_text())
        report = json.dumps(self.store.safe_report(), ensure_ascii=False)
        for private in ["private-person", "private-customer", str(self.root), "SENSITIVE OWNER", "0900-000-000", "secret", "source-content-hash", self.source_id]:
            self.assertNotIn(private, report)
        self.assertEqual(self.store.safe_report()["source_status_counts"], {"PARTIAL": 1})

    def test_running_source_reopens_paused_and_does_not_claim_background_progress(self):
        self.store.stage_status(self.source_id, "ANALYSING", "reading")
        self.store.save()
        reopened = SessionStore(self.store.root)
        self.assertEqual(reopened.get_source(self.source_id)["status"], "PAUSED")
        self.assertEqual(reopened.interrupted_sources, [self.source_id])
        self.assertTrue(reopened.dirty)

    def test_equal_owner_names_do_not_merge_identity_and_unknown_refs_are_rejected(self):
        self.analyse()
        a, b = self.store.add_owner("same name"), self.store.add_owner("same name")
        self.assertNotEqual(a["id"], b["id"])
        with self.assertRaises(ValueError):
            self.store.update_field("work-1", "field-1", owner="not-an-owner-id")
        with self.assertRaises(ValueError):
            self.store.update_field("work-1", "field-1", shared_with=["not-an-owner-id"])
        with self.assertRaises(KeyError):
            self.store.add_relation("work-1", ["field-1", "missing"], "aligned_left")

    def test_original_prediction_tampering_is_detected_before_save(self):
        self.analyse()
        self.store.get_field("work-1", "field-1")["prediction"]["text"] = "tampered"
        with self.assertRaises(ValueError):
            self.store.save()

    def test_reanalysis_reconciles_selection_without_claiming_a_missing_field(self):
        self.analyse()
        self.store.select(self.source_id, "work-1", "field-1")
        changed = result()
        changed["works"][0]["id"] = "different-work"
        self.store.apply_analysis(self.source_id, changed)
        self.assertEqual(self.store.data["selection"],
                         {"source_id": self.source_id, "work_id": None, "field_id": None})

    def test_rejected_manual_input_does_not_leave_invalid_data(self):
        self.analyse()
        before = deepcopy(self.store.data)
        with self.assertRaises(ValueError):
            self.store.add_annotation("work-1", "TEXT", {"x": 1, "y": 1, "w": 2, "h": 2},
                                      review_state="MADE_UP")
        self.assertEqual(self.store.data, before)
        with self.assertRaises(ValueError):
            self.store.add_relation("work-1", ["field-1", "field-2"], status="OBSERVED")
        self.assertEqual(self.store.data, before)

    def test_font_file_annotation_preserves_source_evidence_and_other_parameters(self):
        self.analyse()
        font = self.root / "review-test-font.ttf"
        make_font(font)
        field = self.store.get_field("work-1", "field-1")
        protected = {key: deepcopy(field[key]) for key in ("prediction", "evidence", "measurements")}
        sha = hashlib.sha256(font.read_bytes()).hexdigest()
        record = self.store.annotate_font("work-1", "field-1",
                    {"path": str(font), "file_hash": sha, "face": 0, "family": "Review Test Sans",
                     "pt_confirmed": True, "horizontal_scale_confirmed": True})
        self.assertEqual(record["file_sha256"], sha)
        self.assertEqual(record["family"], "Review Test Sans")
        self.assertEqual(record["face_index"], 0)
        self.assertEqual(record["source"], "HUMAN_VISUAL_REVIEW")
        self.assertEqual(record["font_file_identity"], "VERIFIED_LOCAL_FILE_FACE")
        self.assertEqual(record["status"], "ANNOTATED")
        self.assertFalse(record["pt_confirmed"])
        self.assertFalse(record["horizontal_scale_confirmed"])
        for key, value in protected.items():
            self.assertEqual(field[key], value)
        self.store.save()
        reopened = SessionStore(self.store.root)
        self.assertEqual(reopened.get_field("work-1", "field-1")["human_font_annotation"], record)
        package = reopened.observation_package()
        self.assertEqual(package["payload"]["sources"][0]["works"][0]["fields"][0]["human_font_annotation"], record)
        report = json.dumps(reopened.safe_report())
        self.assertNotIn(sha, report)
        self.assertNotIn("Review Test Sans", report)
        self.assertNotIn(str(font), report)

    def test_family_only_visual_choice_keeps_file_identity_and_pt_unknown_and_can_undo(self):
        self.analyse()
        before = deepcopy(self.store.get_field("work-1", "field-1"))
        record = self.store.annotate_font("work-1", "field-1", {"family": "Local Logical Family", "style": "Bold"})
        self.assertEqual(record["status"], "ANNOTATED_FAMILY_ONLY")
        self.assertEqual(record["font_file_identity"], "UNKNOWN")
        self.assertIsNone(record["file_sha256"])
        self.assertIsNone(record["face_index"])
        self.assertFalse(record["pt_confirmed"])
        self.assertFalse(record["horizontal_scale_confirmed"])
        self.assertTrue(self.store.undo())
        self.assertEqual(self.store.get_field("work-1", "field-1"), before)
        self.assertEqual(self.store.data["history"][-2]["operation"], "FONT_ANNOTATED")
        self.store.save()
        self.assertNotIn("human_font_annotation", SessionStore(self.store.root).get_field("work-1", "field-1"))

    def test_font_hash_and_face_mismatch_reject_without_modifying_session(self):
        self.analyse()
        font = self.root / "review-test-font.ttf"
        make_font(font)
        before = deepcopy(self.store.data)
        with self.assertRaises(ValueError):
            self.store.annotate_font("work-1", "field-1", {"path": str(font), "sha256": "0" * 64,
                                                           "family": "Review Test Sans"})
        self.assertEqual(self.store.data, before)
        with self.assertRaises(ValueError):
            self.store.annotate_font("work-1", "field-1", {"path": str(font), "face_index": 1,
                                                           "family": "Review Test Sans"})
        self.assertEqual(self.store.data, before)

    def test_collection_font_annotation_records_selected_actual_face(self):
        from fontTools.ttLib import TTCollection, TTFont
        self.analyse()
        first, second = self.root / "first.ttf", self.root / "second.ttf"
        make_font(first, "First Fixture")
        make_font(second, "Second Fixture")
        collection = TTCollection()
        collection.fonts = [TTFont(str(first)), TTFont(str(second))]
        combined = self.root / "faces.ttc"
        collection.save(str(combined))
        for face in collection.fonts:
            face.close()
        record = self.store.annotate_font("work-1", "field-1",
                                         {"file_path": str(combined), "face_index": 1, "family": "Second Fixture"})
        self.assertEqual(record["face_index"], 1)
        self.assertEqual(record["family"], "Second Fixture")
        self.assertTrue(record["selected_family_matches_face"])

    def test_family_only_annotation_cannot_be_upgraded_by_false_pt_claim(self):
        self.analyse()
        self.store.annotate_font("work-1", "field-1", {"family": "Unknown Physical Font"})
        self.store.get_field("work-1", "field-1")["human_font_annotation"]["pt_confirmed"] = True
        with self.assertRaises(ValueError):
            self.store.save()

    def test_duplicate_content_sources_keep_separate_ids_manual_data_and_raw_lineage(self):
        packet = result()
        packet["source"].update(hash="a" * 64, lineage="a" * 64)
        packet["works"][0]["relations"] = [{"id": "relation-1", "kind": "aligned_left",
                                           "source": "field-1", "target": "field-2",
                                           "field_ids": ["field-1", "field-2"]}]
        packet["works"][0]["geometry_relations"] = deepcopy(packet["works"][0]["relations"])
        self.store.apply_analysis(self.source_id, packet)
        self.store.update_field("work-1", "field-1", text="first customer manual text")
        copied = self.root / "different-customer.ai"
        copied.write_bytes(self.source.read_bytes())
        second_id = self.store.add_files([copied])[0]["id"]
        self.store.apply_analysis(second_id, packet)
        first_work = self.store.works(self.source_id)[0]
        second_work = self.store.works(second_id)[0]
        self.assertNotEqual(first_work["id"], second_work["id"])
        self.assertNotEqual(first_work["fields"][0]["id"], second_work["fields"][0]["id"])
        self.assertEqual(second_work["source_work_id"], "work-1")
        self.assertEqual(second_work["fields"][0]["source_field_id"], "field-1")
        self.assertEqual(second_work["fields"][0]["text"], "private-person@example.com")
        field_ids = [field["id"] for field in second_work["fields"]]
        for key in ("relations", "geometry_relations"):
            self.assertEqual(second_work[key][0]["field_ids"], field_ids)
            self.assertEqual(second_work[key][0]["source"], field_ids[0])
            self.assertEqual(second_work[key][0]["target"], field_ids[1])
        self.assertEqual(self.store.get_source(second_id)["analysis_versions"][0]["result"], packet)
        second_before = deepcopy(second_work)
        self.store.save()
        reopened = SessionStore(self.store.root)
        reopened.apply_analysis(second_id, packet)
        self.assertEqual(reopened.works(second_id)[0]["id"], second_before["id"])
        self.assertEqual(reopened.works(second_id)[0]["fields"][0]["id"], field_ids[0])
        self.assertEqual(reopened.get_field("work-1", "field-1")["text"], "first customer manual text")
        for source in reopened.sources():
            self.assertEqual(source["analysis"]["source"]["lineage"], "a" * 64)

    def test_continuation_appends_new_page_without_replacing_human_work_or_base_version(self):
        partial, full = partial_and_full()
        self.store.apply_analysis(self.source_id, partial)
        self.store.update_field("work-1", "field-1", text="human checked page one")
        before = deepcopy(self.store.get_work("work-1"))
        base_version = self.store.get_source(self.source_id)["analysis"]["version_id"]
        self.store.apply_analysis(self.source_id, full)
        source = self.store.get_source(self.source_id)
        self.assertEqual(self.store.get_work("work-1"), before)
        self.assertEqual(source["analysis"]["version_id"], base_version)
        self.assertEqual([page["page"] for page in source["analysis"]["pages"]], [1, 2])
        self.assertEqual(len(source["works"]), 2)
        added = next(work for work in source["works"] if work["page"] == 2)
        self.assertEqual(source["continuation_refs"][-1]["work_ids"], [added["id"]])
        self.assertEqual(added["analysis_version_ref"], source["pending_analysis_version"])
        self.assertIsInstance(source["pending_analysis_version"], str)
        self.store.save()
        reopened = SessionStore(self.store.root)
        self.assertEqual(reopened.get_work("work-1"), before)
        reopened.apply_analysis(self.source_id, full)
        self.assertEqual(len(reopened.works(self.source_id)), 2)

    def test_explicit_adoption_adds_only_unseen_same_page_work_and_can_undo(self):
        partial, _ = partial_and_full()
        self.store.apply_analysis(self.source_id, partial)
        self.store.update_field("work-1", "field-1", text="manual")
        changed = deepcopy(partial)
        extra = deepcopy(changed["works"][0])
        extra["id"] = "work-new-on-existing-page"
        changed["works"].append(extra)
        self.store.apply_analysis(self.source_id, changed)
        source = self.store.get_source(self.source_id)
        self.assertEqual(len(source["works"]), 1)
        before = deepcopy(source["works"])
        adopted = self.store.adopt_new_unseen_works(self.source_id, source["pending_analysis_version"])
        self.assertEqual(len(adopted["work_ids"]), 1)
        self.assertEqual(adopted["page_ids"], [])
        self.assertEqual(self.store.get_work("work-1")["fields"][0]["text"], "manual")
        self.assertEqual(self.store.adopt_new_unseen_works(self.source_id, source["pending_analysis_version"]),
                         {"work_ids": [], "page_ids": []})
        self.assertTrue(self.store.undo())
        self.assertEqual(self.store.works(self.source_id), before)
        self.store.save()

    def test_hash_or_engine_version_change_never_merges_or_adopts(self):
        for difference in ("hash", "analysis_version", "runtime"):
            with self.subTest(difference=difference):
                local = SessionStore(self.root / ("isolated-" + difference))
                sid = local.add_files([self.source])[0]["id"]
                partial, full = partial_and_full()
                local.apply_analysis(sid, partial)
                local.update_field("work-1", "field-1", text="manual")
                before = deepcopy(local.works(sid))
                if difference == "hash":
                    full["source"]["hash"] = "b" * 64
                elif difference == "analysis_version":
                    full["analysis_version"] = "different-extractor-2"
                else:
                    full["capabilities"] = {"inkscape_runtime": {"version": "changed-runtime"}}
                local.apply_analysis(sid, full)
                self.assertEqual(local.works(sid), before)
                state = deepcopy(local.data)
                with self.assertRaises(ValueError):
                    local.adopt_new_unseen_works(sid, local.get_source(sid)["pending_analysis_version"])
                self.assertEqual(local.data, state)

    def test_undo_manual_work_addition_keeps_later_background_continuation(self):
        partial, full = partial_and_full()
        self.store.apply_analysis(self.source_id, partial)
        manual = self.store.add_work(self.source_id, "page-1", {"x": 0, "y": 0, "w": 10, "h": 10})
        self.store.apply_analysis(self.source_id, full)
        self.assertEqual(len(self.store.works()), 3)
        self.assertTrue(self.store.undo())
        self.assertEqual(len(self.store.works()), 2)
        self.assertFalse(any(work["id"] == manual["id"] for work in self.store.works()))
        self.assertTrue(any(work["page"] == 2 for work in self.store.works()))
        self.store.save()

    def test_manual_geometry_has_explicit_override_while_original_measurements_remain(self):
        packet = result()
        packet["works"][0]["fields"][0]["measurements"]["width_mm"] = {
            "value": 20, "unit": "mm", "status": "DERIVED", "basis": "SOURCE_FRAME"}
        self.store.apply_analysis(self.source_id, packet)
        original = deepcopy(self.store.get_field("work-1", "field-1")["measurements"])
        self.store.resize_annotation("work-1", "field-1", {"x": 5, "y": 6, "w": 22, "h": 4})
        field = self.store.get_field("work-1", "field-1")
        self.assertEqual(field["measurements"], original)
        self.assertTrue(field["measurement_geometry_stale"])
        self.assertEqual(field["annotation_measurements"]["frame"]["rect"], field["rect"])
        self.assertEqual(field["annotation_measurements"]["width_mm"]["value"], 22)
        self.assertEqual(field["annotation_measurements"]["width_mm"]["status"], "ANNOTATED")
        self.store.resize_work("work-1", {"x": 12, "y": 8, "w": 50, "h": 20})
        self.store.save()
        reopened = SessionStore(self.store.root)
        field = reopened.get_field("work-1", "field-1")
        self.assertEqual(field["annotation_measurements"]["frame"]["rect"], field["rect"])
        self.assertEqual(field["current_source_rect"]["x"], 15)
        self.assertEqual(field["measurements"], original)


if __name__ == "__main__":
    unittest.main()

"""Build/inventory security fixtures; not evidence of actual Windows OCR.

The authored PE headers below only exercise packaging checks. Real installer
extraction and actual EXE inference have separate release acceptance evidence.
"""
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from tools import bundled_tesseract as bundle


def sha(data):
    return hashlib.sha256(data).hexdigest()


def authored_pe(marker, machine=0x8664):
    data = bytearray(192)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 64)
    data[64:68] = b"PE\0\0"
    struct.pack_into("<H", data, 68, machine)
    struct.pack_into("<H", data, 88, 0x20B)
    return bytes(data) + b"AUTHORED_NOT_EXECUTABLE_TEST_FIXTURE:" + marker


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


class BundledTesseractBuildTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="OCR public fixture space ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.product = self.root / "product"
        self.engine = self.product / "engines/tesseract"
        self.engine.mkdir(parents=True)
        self.contents = {"tesseract.exe": authored_pe(b"main"),
                         "dependency.dll": authored_pe(b"dependency"),
                         "licenses/AUTHORED_NOTICE.txt": b"Public authored notice fixture.\n"}
        rows = [dict(path=name, bytes=len(data), sha256=sha(data)) for name, data in self.contents.items()]
        self.lock = dict(schema_version=1, architecture="windows-x86_64", version="5.4.0.20240606",
            legal_status="REVIEWED", runtime_files=[dict(rows[0], imports=["dependency.dll", "KERNEL32.dll"]),
                dict(rows[1], imports=["KERNEL32.dll"])], system_dlls=["KERNEL32.dll"],
            notices=[dict(rows[2], source_member="doc/NOTICE")], extra_notices=[],
            installer=dict(url="https://example.invalid/immutable-authored-fixture.exe",
                asset_name="authored-fixture.exe", bytes=3, sha256=sha(b"zip")))
        self.lock_path = self.root / "distribution.json"
        self._write_lock()
        self._write_engine()

    def _write_lock(self):
        self.lock_path.write_bytes(json_bytes(self.lock))

    def _write_engine(self):
        for name, content in self.contents.items():
            path = self.engine / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        raw = self.lock_path.read_bytes()
        (self.engine / bundle.SOURCE_MAP).write_bytes(raw)
        rows = [dict(path=name, bytes=len(data), sha256=sha(data)) for name, data in self.contents.items()]
        rows.append(dict(path=bundle.SOURCE_MAP, bytes=len(raw), sha256=sha(raw)))
        rows.sort(key=lambda row: row["path"])
        self.manifest = dict(schema_version=1, kind="BUNDLED_TESSERACT_RUNTIME",
            version="5.4.0.20240606", executable="tesseract.exe",
            distribution_lock_sha256=sha(raw), files=rows)
        (self.engine / bundle.MANIFEST).write_bytes(json_bytes(self.manifest))
        self.pin = dict(version=self.manifest["version"], manifest_sha256=sha(json_bytes(self.manifest)),
            executable_sha256=sha(self.contents["tesseract.exe"]), files=len(rows))
        (self.product / "_internal").mkdir(exist_ok=True)
        for location in ("release-info.json", "_internal/release-info.json"):
            (self.product / location).write_bytes(json_bytes(dict(tesseract_runtime=self.pin)))

    def validate(self):
        return bundle.validate(self.engine, lock_path=self.lock_path, pin=self.pin)

    def test_exact_inventory_and_both_release_pins_are_accepted(self):
        self.assertEqual(self.validate(), self.pin)
        expected = {"engines/tesseract/" + name for name in self.contents}
        expected |= {"engines/tesseract/" + bundle.MANIFEST, "engines/tesseract/" + bundle.SOURCE_MAP}
        self.assertEqual(bundle.vendor_inventory(self.product, lock_path=self.lock_path), expected)

    def test_equal_size_dependency_tamper_is_not_a_cache_hit(self):
        path = self.engine / "dependency.dll"
        path.write_bytes(path.read_bytes()[:-1] + b"X")
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            self.validate()

    def test_missing_dependency_is_rejected(self):
        (self.engine / "dependency.dll").unlink()
        with self.assertRaisesRegex(ValueError, "Missing or unlisted"):
            self.validate()

    def test_unlisted_dll_or_private_file_is_rejected(self):
        for name in ("unlisted.dll", "customers.sqlite", "unexpected.traineddata"):
            with self.subTest(name=name):
                path = self.engine / name
                path.write_bytes(b"AUTHORED_PUBLIC_FIXTURE")
                with self.assertRaisesRegex(ValueError, "Missing or unlisted"):
                    self.validate()
                path.unlink()

    def test_rewriting_manifest_and_both_pins_does_not_bypass_committed_lock(self):
        (self.engine / "dependency.dll").write_bytes(b"untrusted replacement")
        row = next(row for row in self.manifest["files"] if row["path"] == "dependency.dll")
        row.update(bytes=21, sha256=sha(b"untrusted replacement"))
        (self.engine / bundle.MANIFEST).write_bytes(json_bytes(self.manifest))
        forged = dict(self.pin, manifest_sha256=sha(json_bytes(self.manifest)))
        for location in ("release-info.json", "_internal/release-info.json"):
            (self.product / location).write_bytes(json_bytes(dict(tesseract_runtime=forged)))
        with self.assertRaisesRegex(ValueError, "reviewed distribution lock"):
            bundle.vendor_inventory(self.product, lock_path=self.lock_path)

    def test_external_and_internal_release_pin_mismatch_is_rejected(self):
        (self.product / "release-info.json").write_bytes(json_bytes(dict(
            tesseract_runtime=dict(self.pin, version="9.0.0.20990101"))))
        with self.assertRaisesRegex(ValueError, "inconsistent"):
            bundle.vendor_inventory(self.product, lock_path=self.lock_path)

    def test_manifest_file_count_pin_is_verified(self):
        with self.assertRaisesRegex(ValueError, "release pin"):
            bundle.validate(self.engine, lock_path=self.lock_path, pin=dict(self.pin, files=100))

    def test_symlink_dependency_cannot_escape_runtime(self):
        outside = self.root / "outside.dll"
        outside.write_bytes(self.contents["dependency.dll"])
        path = self.engine / "dependency.dll"
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            self.validate()

    def test_path_traversal_windows_aliases_and_case_collision_are_rejected(self):
        for name in ("../outside", "/absolute", "C:/outside", "folder\\outside", "file:stream",
                     "dir/../outside", "CON.txt", "dir/NUL", "trailing.", "trailing ", "x//y"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                bundle.safe_member(name)
        self.lock["runtime_files"].append(dict(self.lock["runtime_files"][1], path="DEPENDENCY.DLL"))
        self._write_lock()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            bundle.load_lock(self.lock_path)

    def test_missing_dependency_closure_fails_before_extraction(self):
        self.lock["runtime_files"][0]["imports"].append("absent.dll")
        self._write_lock()
        with self.assertRaisesRegex(ValueError, "dependency closure"):
            bundle.load_lock(self.lock_path)

    def test_unreviewed_redistribution_fails_before_any_download(self):
        self.lock["legal_status"] = "PENDING"
        self._write_lock()
        with patch.object(bundle.urllib.request, "urlopen") as network:
            with self.assertRaisesRegex(ValueError, "redistribution"):
                bundle.install(self.root / "cache", self.root / "new", lock_path=self.lock_path)
            network.assert_not_called()

    def test_wrong_machine_cannot_pass_merely_by_updating_file_hash(self):
        self.contents["dependency.dll"] = authored_pe(b"dependency", machine=0x14C)
        row = self.lock["runtime_files"][1]
        row.update(bytes=len(self.contents["dependency.dll"]), sha256=sha(self.contents["dependency.dll"]))
        self._write_lock()
        self._write_engine()
        with self.assertRaisesRegex(ValueError, "x86-64"):
            self.validate()

    def test_verified_existing_stage_is_reused_without_network_or_extract(self):
        with patch.object(bundle.urllib.request, "urlopen") as network, patch.object(bundle, "_extract") as extract:
            result = bundle.install(self.root / "cache", self.engine, lock_path=self.lock_path)
            self.assertEqual(result, self.pin)
            network.assert_not_called()
            extract.assert_not_called()

    def test_corrupt_existing_stage_is_not_overwritten(self):
        path = self.engine / "dependency.dll"
        path.write_bytes(b"corrupt")
        with patch.object(bundle.urllib.request, "urlopen") as network:
            with self.assertRaises(ValueError):
                bundle.install(self.root / "cache", self.engine, lock_path=self.lock_path)
            self.assertEqual(path.read_bytes(), b"corrupt")
            network.assert_not_called()

    def _fixture_extract(self, archive, directory, lock, seven_zip):
        self.assertEqual(archive.read_bytes(), b"zip")
        for row in lock["runtime_files"] + lock["notices"]:
            name = row.get("source_member", row["path"])
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.contents[row["path"]])

    def test_fresh_stage_includes_pinned_local_notices_and_reuses_verified_download(self):
        cache = self.root / "cache"
        cache.mkdir()
        (cache / "authored-fixture.exe").write_bytes(b"zip")
        notice = self.root / "public-notice.txt"
        notice.write_bytes(b"Additional public attribution.")
        self.lock["extra_notices"] = [dict(path="licenses/ADDITIONAL.txt",
            repository_path="public-notice.txt", bytes=notice.stat().st_size, sha256=sha(notice.read_bytes()))]
        self._write_lock()
        destination = self.root / "new-stage"
        with patch.object(bundle, "ROOT", self.root), patch.object(bundle, "_extract", side_effect=self._fixture_extract), \
                patch.object(bundle.urllib.request, "urlopen") as network:
            pin = bundle.install(cache, destination, lock_path=self.lock_path)
            self.assertEqual(bundle.validate(destination, lock_path=self.lock_path, pin=pin), pin)
            network.assert_not_called()
        self.assertEqual((destination / "licenses/ADDITIONAL.txt").read_bytes(), notice.read_bytes())
        self.assertFalse(any(path.suffix == ".traineddata" for path in destination.rglob("*")))

    def test_changed_notice_fails_without_publishing_a_partial_stage(self):
        cache = self.root / "cache"
        cache.mkdir()
        (cache / "authored-fixture.exe").write_bytes(b"zip")
        notice = self.root / "public-notice.txt"
        original = b"Approved public attribution."
        notice.write_bytes(b"Different public attribution.")
        self.lock["extra_notices"] = [dict(path="licenses/ADDITIONAL.txt",
            repository_path="public-notice.txt", bytes=len(original), sha256=sha(original))]
        self._write_lock()
        destination = self.root / "new-stage"
        with patch.object(bundle, "ROOT", self.root), patch.object(bundle, "_extract", side_effect=self._fixture_extract):
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                bundle.install(cache, destination, lock_path=self.lock_path)
        self.assertFalse(destination.exists())
        self.assertFalse(list(self.root.glob("ocr-stage-*")))

    def test_empty_upstream_notice_is_preserved_but_empty_runtime_is_rejected(self):
        data = b""
        name = "licenses/EMPTY_UPSTREAM_NOTICE"
        self.contents[name] = data
        self.lock["notices"].append(dict(path=name, source_member="doc/EMPTY", bytes=0, sha256=sha(data)))
        self._write_lock()
        self._write_engine()
        self.assertEqual(self.validate(), self.pin)
        self.assertTrue((self.engine / name).is_file())
        self.lock["runtime_files"][1].update(bytes=0, sha256=sha(b""))
        self._write_lock()
        with self.assertRaisesRegex(ValueError, "empty or truncated PE"):
            bundle.load_lock(self.lock_path)

    def test_upstream_cache_hit_checks_hash_and_never_uses_network(self):
        row = self.lock["installer"]
        path = self.root / "cached.exe"
        path.write_bytes(b"zip")
        with patch.object(bundle.urllib.request, "urlopen") as network:
            self.assertEqual(bundle.fetch(row, path), path)
            path.write_bytes(b"bad")
            with self.assertRaisesRegex(ValueError, "Cached OCR"):
                bundle.fetch(row, path)
            network.assert_not_called()

    def test_oversized_download_is_rejected_and_no_target_is_adopted(self):
        class Response(io.BytesIO):
            def geturl(self):
                return "https://example.invalid/immutable-authored-fixture.exe"
        path = self.root / "new-cache/fixture.exe"
        with patch.object(bundle.urllib.request, "urlopen", return_value=Response(b"four")):
            with self.assertRaisesRegex(ValueError, "exceeded"):
                bundle.fetch(self.lock["installer"], path)
        self.assertFalse(path.exists())
        self.assertEqual(list(path.parent.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

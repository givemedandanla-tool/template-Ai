"""Assemble a pinned Windows OCR runtime without executing its installer.

This is a build-time tool. The desktop program never imports it, downloads an
engine, installs software, or requests administrator rights. Language models
remain a separately pinned component in ``engines/ocr-models``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import tempfile
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "tools/tesseract_distribution_lock.json"
MANIFEST = "BUNDLED_RUNTIME.json"
SOURCE_MAP = "TESSERACT_DISTRIBUTION_LOCK.json"
KIND = "BUNDLED_TESSERACT_RUNTIME"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    name + str(number) for name in ("COM", "LPT") for number in range(1, 10)
}


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def safe_member(name):
    if not isinstance(name, str) or not name or "\\" in name:
        raise ValueError("Invalid OCR component path")
    parts = name.split("/")
    if (PurePosixPath(name).is_absolute() or any(
        not part or part in {".", ".."} or part[-1:] in {".", " "}
        or any(ord(char) < 32 or char in ':*?<>|"' for char in part)
        or part.split(".", 1)[0].upper() in _RESERVED for part in parts
    )):
        raise ValueError("Unsafe OCR component path")
    return name


def no_links(path):
    """Reject symlinks and Windows junctions before resolving a trusted path."""
    path = Path(path).absolute()
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            raise ValueError("Symlink in OCR component path")
        if candidate.exists() and getattr(candidate.lstat(), "st_file_attributes", 0) & 0x400:
            raise ValueError("Reparse point in OCR component path")
    return path


def _record(row):
    name = safe_member(row.get("path"))
    if type(row.get("bytes")) is not int or not 0 <= row["bytes"] <= 200_000_000:
        raise ValueError("Invalid OCR file size")
    if not isinstance(row.get("sha256"), str) or not _SHA256.fullmatch(row["sha256"]):
        raise ValueError("Invalid OCR file digest")
    return dict(path=name, bytes=row["bytes"], sha256=row["sha256"])


def load_lock(path=LOCK):
    path = no_links(path)
    raw = path.read_bytes()
    if len(raw) > 2_000_000:
        raise ValueError("OCR distribution lock exceeds its budget")
    lock = json.loads(raw)
    if (lock.get("schema_version") != 1 or lock.get("architecture") != "windows-x86_64"
            or lock.get("legal_status") != "REVIEWED"
            or not re.fullmatch(r"\d+\.\d+\.\d+\.\d{8}", lock.get("version", ""))):
        raise ValueError("OCR distribution lock is unsupported or redistribution is not reviewed")
    rows = lock.get("runtime_files", []) + lock.get("notices", []) + lock.get("extra_notices", [])
    if not 2 <= len(rows) <= 256:
        raise ValueError("Invalid OCR runtime inventory size")
    records = [_record(row) for row in rows]
    names = [row["path"].casefold() for row in records]
    if len(set(names)) != len(names) or {MANIFEST.casefold(), SOURCE_MAP.casefold()} & set(names):
        raise ValueError("Duplicate OCR component path")
    runtime = {row["path"].casefold(): row for row in lock["runtime_files"]}
    if "tesseract.exe" not in runtime:
        raise ValueError("OCR inventory has no executable")
    system = {name.casefold() for name in lock.get("system_dlls", [])}
    for row in lock["runtime_files"]:
        if row["bytes"] < 64:
            raise ValueError("OCR runtime cannot be an empty or truncated PE file")
        if "/" in row["path"] or (row["path"] != "tesseract.exe" and not row["path"].lower().endswith(".dll")):
            raise ValueError("Unexpected executable in OCR runtime")
        if any(safe_member(name).casefold() not in set(runtime) | system for name in row.get("imports", [])):
            raise ValueError("Incomplete OCR DLL dependency closure")
    for row in lock.get("notices", []):
        safe_member(row["source_member"])
    _download_record(lock["installer"])
    if lock["installer"]["bytes"] == 0:
        raise ValueError("OCR installer cannot be empty")
    for row in lock.get("extra_notices", []):
        if "repository_path" in row:
            safe_member(row["repository_path"])
            if "url" in row:
                raise ValueError("Ambiguous OCR notice source")
        else:
            _download_record(row)
    return lock, raw


def _download_record(row):
    _record(dict(path=row.get("asset_name", row.get("path")), bytes=row.get("bytes"), sha256=row.get("sha256")))
    parsed = urllib.parse.urlsplit(row.get("url", ""))
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError("OCR upstream object must have a public HTTPS source")


def fetch(row, target):
    """Verify every cache hit, bound downloads, never execute downloaded bytes."""
    _download_record(row)
    target = no_links(target)
    if target.exists():
        if not target.is_file() or target.stat().st_size != row["bytes"] or digest(target) != row["sha256"]:
            raise ValueError("Cached OCR upstream object failed its fixed size/hash")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="ocr-download-", dir=target.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            count = 0
            with urllib.request.urlopen(row["url"], timeout=60) as source:
                if urllib.parse.urlsplit(source.geturl()).scheme != "https":
                    raise ValueError("OCR upstream redirected outside HTTPS")
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    count += len(block)
                    if count > row["bytes"]:
                        raise ValueError("OCR upstream exceeded its fixed size")
                    stream.write(block)
            stream.flush()
            if count != row["bytes"] or digest(temporary) != row["sha256"]:
                raise ValueError("OCR upstream failed its fixed size/hash")
        except BaseException:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    temporary.replace(target)
    return target


def _file(path, row, *, pe=False):
    path = no_links(path)
    if not path.is_file() or path.stat().st_size != row["bytes"] or digest(path) != row["sha256"]:
        raise ValueError("OCR runtime identity mismatch: " + row["path"])
    if pe:
        with path.open("rb") as stream:
            header = stream.read(64)
            if len(header) < 64 or header[:2] != b"MZ":
                raise ValueError("OCR runtime is not a PE executable")
            offset = struct.unpack_from("<I", header, 60)[0]
            if offset > min(row["bytes"] - 26, 4_000_000):
                raise ValueError("Invalid OCR PE header offset")
            stream.seek(offset)
            header = stream.read(26)
            if (len(header) != 26 or header[:4] != b"PE\0\0"
                    or struct.unpack_from("<H", header, 4)[0] != 0x8664
                    or struct.unpack_from("<H", header, 24)[0] != 0x20B):
                raise ValueError("OCR runtime is not Windows x86-64 PE32+")


def _manifest(lock, raw):
    files = [_record(row) for key in ("runtime_files", "notices", "extra_notices") for row in lock.get(key, [])]
    files.append(dict(path=SOURCE_MAP, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    files.sort(key=lambda row: row["path"])
    return dict(schema_version=1, kind=KIND, version=lock["version"], executable="tesseract.exe",
                distribution_lock_sha256=hashlib.sha256(raw).hexdigest(), files=files)


def _pin(value):
    executable = next(row for row in value["files"] if row["path"] == "tesseract.exe")
    return dict(version=value["version"], manifest_sha256=hashlib.sha256(encoded(value)).hexdigest(),
                executable_sha256=executable["sha256"], files=len(value["files"]))


def validate(root, *, lock_path=LOCK, pin=None):
    lock, raw = load_lock(lock_path)
    root = no_links(root)
    expected = _manifest(lock, raw)
    manifest = root / MANIFEST
    no_links(manifest)
    if not manifest.is_file() or manifest.read_bytes() != encoded(expected):
        raise ValueError("OCR manifest differs from the reviewed distribution lock")
    expected_pin = _pin(expected)
    if pin is not None and any(pin.get(key) != value for key, value in expected_pin.items()):
        raise ValueError("OCR runtime differs from its frozen release pin")
    actual = set()
    for path in root.rglob("*"):
        no_links(path)
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    names = {row["path"] for row in expected["files"]} | {MANIFEST}
    if actual != names:
        raise ValueError("Missing or unlisted file in OCR runtime inventory")
    binaries = {row["path"] for row in lock["runtime_files"]}
    for row in expected["files"]:
        _file(root / row["path"], row, pe=row["path"] in binaries)
    return expected_pin


def _extract(archive, directory, lock, seven_zip=None):
    executable = seven_zip or shutil.which("7z") or shutil.which("7zz")
    if not executable:
        raise ValueError("Build requires an existing local 7-Zip extractor; the installer is never executed")
    members = [row["path"] for row in lock["runtime_files"]]
    members += [row["source_member"] for row in lock.get("notices", [])]
    if len(set(name.casefold() for name in members)) != len(members):
        raise ValueError("Duplicate source member in OCR installer")
    result = subprocess.run([str(executable), "x", "-y", "-o" + str(directory), str(archive), *members],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180, check=False)
    if result.returncode:
        raise ValueError("7-Zip failed to extract the pinned OCR installer")
    actual = set()
    for path in directory.rglob("*"):
        no_links(path)
        if path.is_file():
            actual.add(path.relative_to(directory).as_posix())
    if actual != set(members):
        raise ValueError("OCR extractor produced missing or unexpected members")


def install(cache, destination, *, seven_zip=None, lock_path=LOCK):
    lock, raw = load_lock(lock_path)
    destination, cache = no_links(destination), no_links(cache)
    if destination.exists():
        return validate(destination, lock_path=lock_path)
    cache.mkdir(parents=True, exist_ok=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    installer = fetch(lock["installer"], cache / lock["installer"]["asset_name"])
    with tempfile.TemporaryDirectory(prefix="ocr-extract-", dir=cache) as temporary:
        extracted = Path(temporary) / "unpacked"
        extracted.mkdir()
        _extract(installer, extracted, lock, seven_zip)
        with tempfile.TemporaryDirectory(prefix="ocr-stage-", dir=destination.parent) as staging:
            staged = Path(staging) / "runtime"
            staged.mkdir()
            for row in lock["runtime_files"] + lock.get("notices", []):
                source = extracted / row.get("source_member", row["path"])
                _file(source, row, pe=row in lock["runtime_files"])
                target = staged / row["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            for row in lock.get("extra_notices", []):
                if "repository_path" in row:
                    source = ROOT / safe_member(row["repository_path"])
                    _file(source, row)
                else:
                    source = fetch(row, cache / "notices" / safe_member(row.get("asset_name", row["path"])))
                target = staged / row["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            (staged / SOURCE_MAP).write_bytes(raw)
            (staged / MANIFEST).write_bytes(encoded(_manifest(lock, raw)))
            pin = validate(staged, lock_path=lock_path)
            if destination.exists():
                raise FileExistsError("Refuse to replace an OCR runtime staged by another process")
            staged.rename(destination)
    return pin


def vendor_inventory(product_root, *, lock_path=LOCK):
    """Return an exact public-vendor allowlist after checking every file."""
    product_root = no_links(product_root)
    pins = []
    for location in ("_internal/release-info.json", "release-info.json"):
        path = product_root / location
        if path.exists():
            no_links(path)
            info = json.loads(path.read_text(encoding="utf-8"))
            pins.append(info.get("tesseract_runtime"))
    if not pins or any(not isinstance(pin, dict) or pin != pins[0] for pin in pins):
        raise ValueError("Missing or inconsistent OCR frozen release pin")
    root = product_root / "engines/tesseract"
    validate(root, lock_path=lock_path, pin=pins[0])
    return {"engines/tesseract/" + path.relative_to(root).as_posix()
            for path in root.rglob("*") if path.is_file()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--seven-zip", type=Path)
    arguments = parser.parse_args()
    print(json.dumps(install(arguments.cache, arguments.destination, seven_zip=arguments.seven_zip)))

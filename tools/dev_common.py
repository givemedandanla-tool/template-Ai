"""開發治理共用函式；不讀取本機客戶資料、字型或密鑰。"""
from pathlib import Path
import hashlib
import json
import os
import re
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def valid_id(value):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", value):
        raise ValueError("識別碼只能使用英數、底線、點及連字號，不接受路徑")
    return value


def safe_path(root, relative):
    root = Path(root).resolve()
    if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("記錄中含不安全的相對路徑")
    path = root / relative
    if path.is_symlink() or root not in path.resolve().parents:
        raise ValueError("路徑指向工作區外或符號連結")
    return path


def source_files(root=ROOT, code_only=False):
    root = Path(root)
    directories = ("template_ai", "tests", "examples", "tools") if code_only else ("template_ai", "tests", "examples", "tools", "docs", ".github")
    root_names = ("app.py", "requirements.txt", "requirements-lock.txt") if code_only else ("app.py", "requirements.txt", "requirements-lock.txt", "requirements-build.txt", "README.md", "AGENTS.md", "START_WINDOWS.bat", ".gitignore")
    allowed = {".py", ".md", ".json", ".jsonl", ".csv", ".txt", ".log", ".svg", ".xml", ".ui", ".yml", ".yaml", ".ps1", ".bat"}
    files = [root / name for name in root_names if (root / name).is_file()]
    for directory in directories:
        for path in (root / directory).rglob("*"):
            relative = path.relative_to(root)
            if any(part in ("__pycache__", "assets", ".venv", ".private", "ten-package-data") or part.startswith("anonymous-smoke-data") for part in relative.parts):
                continue
            evidence_binary = relative.parts[:3] == ("docs", "evidence", "runs") and path.suffix in (".png", ".jpg", ".pdf")
            gui_license = relative.parts[:3] == ("docs", "dev", "gui_tooling") and path.name == "LICENSE"
            if path.is_file() and not path.is_symlink() and (path.suffix in allowed or evidence_binary or gui_license):
                files.append(path)
    return sorted(set(files))


def manifest(root=ROOT, code_only=False):
    result = {}
    for path in source_files(root, code_only):
        data = path.read_bytes()
        result[path.relative_to(root).as_posix()] = {"bytes": len(data), "sha256": digest(data),
            "git_blob_sha1": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}
    return result


def manifest_digest(files):
    return digest(json.dumps(files, sort_keys=True, separators=(",", ":")).encode())


def contract_digest(row):
    return digest(json.dumps({key: row.get(key) for key in ("id", "kind", "scope", "parents", "acceptance")},
                             sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())

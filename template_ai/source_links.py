"""原稿位置可變，內容身份不變；唯讀驗證可在背景工作執行。"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
import stat

MAX_SOURCE_BYTES = 200_000_000


def fingerprint(value) -> tuple:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


@dataclass(frozen=True)
class VerifiedSource:
    path: str
    hash: str
    stat: tuple


def verify_source(path: str | Path, expected_hash: str) -> VerifiedSource:
    """1 MiB 緩衝；拒絕不同內容、超額或讀取期間異動。不修改原檔。"""
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise ValueError("來源內容識別不完整，請重新匯入並審核")
    path = Path(path).resolve(strict=True)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_SOURCE_BYTES:
        raise ValueError("來源需為一般檔案，單檔不超過 200 MB")
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as stream:
        import os
        opened = os.fstat(stream.fileno())
        if fingerprint(opened) != fingerprint(before):
            raise ValueError("來源在驗證期間變更，請重新選取")
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            total += len(chunk)
            if total > MAX_SOURCE_BYTES:
                raise ValueError("來源在驗證期間超過 200 MB")
            digest.update(chunk)
        after_open = os.fstat(stream.fileno())
    after = path.stat()
    if fingerprint(before) != fingerprint(after_open) or fingerprint(before) != fingerprint(after) or total != before.st_size:
        raise ValueError("來源在驗證期間變更，請重新選取")
    if digest.hexdigest() != expected_hash:
        raise ValueError("來源內容已變更；同名不代表同內容，請另外匯入並重新審核")
    return VerifiedSource(str(path), expected_hash, fingerprint(after))


def check_verified(proof: VerifiedSource, expected_hash: str) -> None:
    # proof 來自本程式背景工作，非外部認證；stat 防止正常編輯競態，不是安全簽章。
    if not isinstance(proof, VerifiedSource) or proof.hash != expected_hash:
        raise ValueError("重連驗證不屬於此來源")
    if fingerprint(Path(proof.path).stat()) != proof.stat:
        raise ValueError("來源在驗證後變更，請重新驗證")


def source_status(source: dict) -> dict:
    path = source.get("current_path", source["original_path"])
    try:
        proof = verify_source(path, source["hash"])
        return {"status": "OK", "path": proof.path, "message": "來源在場，內容與匯入時一致"}
    except FileNotFoundError:
        return {"status": "MISSING", "path": path, "message": "原稿失聯；可選取同內容檔案重新連結"}
    except OSError:
        return {"status": "UNREADABLE", "path": path, "message": "來源無法讀取；請檢查檔案存取權限"}
    except (ValueError, KeyError):
        return {"status": "CHANGED", "path": path, "message": "來源內容異動或無法驗證；需另行匯入並審核"}

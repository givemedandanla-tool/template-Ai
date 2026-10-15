"""Publish a complete same-directory temporary file exclusively; no overwrite fallback."""
import os
from pathlib import Path


def publish_complete(temporary,target,check=lambda:None):
    temporary,target=Path(temporary),Path(target)
    if temporary.parent.resolve()!=target.parent.resolve():raise ValueError('暫存檔與目的地必須同目錄')
    if not temporary.is_file() or temporary.is_symlink() or temporary.stat().st_size==0:raise ValueError('暫存檔不完整')
    with temporary.open('r+b') as f:os.fsync(f.fileno())
    check()
    os.link(temporary,target)

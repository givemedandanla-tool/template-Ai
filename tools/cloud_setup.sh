#!/usr/bin/env bash
set -euo pipefail
task_repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_repo_root"
export XDG_CACHE_HOME=/workspace/.cache
export UV_CACHE_DIR=/workspace/.cache/uv
mkdir -p "$XDG_CACHE_HOME"
if ! command -v inkscape >/dev/null || ! command -v tesseract >/dev/null; then
  if [ "$(id -u)" -eq 0 ]; then
    apt-get update
    apt-get install -y --no-install-recommends inkscape tesseract-ocr fonts-noto-cjk libegl1 libopengl0 libxcb-cursor0
  else
    echo '需要系統安裝 Inkscape、Tesseract、Noto CJK 與 Qt runtime；現有來源與本機變更均保留。' >&2
    exit 1
  fi
fi
if command -v uv >/dev/null; then
  if [ ! -x .venv/bin/python ]; then uv venv --python 3.12 .venv; fi
  uv pip sync --python .venv/bin/python requirements-lock.txt
else
  if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
  .venv/bin/python -m pip install -r requirements-lock.txt
fi
.venv/bin/python tools/install_ocr_models.py
QT_QPA_PLATFORM=offscreen .venv/bin/python -c 'from PySide6.QtWidgets import QApplication; from PySide6.QtPdf import QPdfDocument; from pypdf import PdfReader; import sqlite3; a=QApplication([]); print("Qt/PDF/SQLite ready", sqlite3.sqlite_version)'
.venv/bin/python tools/dev_governance.py check

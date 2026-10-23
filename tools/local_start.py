"""Local desktop preflight/launcher. Standard library only; never installs packages."""
from __future__ import annotations

import argparse
from importlib import metadata
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def locked_dependencies(path=None):
    """Read the project's existing exact pins, without evaluating requirement text."""
    rows = []
    for raw in Path(path or ROOT / 'requirements-lock.txt').read_text(encoding='utf-8').splitlines():
        value = raw.split('#', 1)[0].strip()
        if not value: continue
        if value.count('==') != 1 or value.startswith(('-', 'http:', 'https:')):
            raise ValueError('鎖定依賴清單包含目前啟動器無法辨識的格式。')
        name, version = value.split('==')
        if not name or not version or any(token in value for token in (';', '/', '\\', ' ')):
            raise ValueError('鎖定依賴清單需使用明確的套件名稱與版本。')
        rows.append((name, version))
    if not rows: raise ValueError('鎖定依賴清單是空的。')
    return rows


def check_dependencies():
    problems = []
    if sys.version_info < (3, 11): problems.append('請改用 Python 3.11 或相容版本；首次準備使用 Python 3.11。')
    if struct.calcsize('P') * 8 != 64: problems.append('請改用 64 位元 Python。')
    for name, required in locked_dependencies():
        try: actual = metadata.version(name)
        except metadata.PackageNotFoundError:
            problems.append(name + ' 尚未安裝（需要 ' + required + '）。'); continue
        if actual != required: problems.append(name + ' 版本不符（目前 ' + actual + '；需要 ' + required + '）。')
    return problems


def local_inkscape_available():
    from template_ai.offline_runtime import assert_local_path, OfflineAccessError
    candidates = [os.environ.get('TEMPLATE_AI_INKSCAPE', ''), r'C:\Program Files\Inkscape\bin\inkscape.exe', r'C:\Program Files\Inkscape\inkscape.exe']
    safe_parts = []
    for part in os.get_exec_path():
        try: assert_local_path(part)
        except OfflineAccessError: continue
        safe_parts.append(part)
    executable = shutil.which('inkscape', path=os.pathsep.join(safe_parts))
    if executable: candidates.append(executable)
    for value in candidates:
        if not value: continue
        try: assert_local_path(value)
        except OfflineAccessError: continue
        if Path(value).is_file(): return True
    return False


def main(argv=None):
    from template_ai.offline_runtime import assert_local_path, enable_offline_guard, OfflineAccessError
    enable_offline_guard()
    parser = argparse.ArgumentParser(description='離線檢查與啟動；不會下載或安裝套件。')
    parser.add_argument('--check', action='store_true', help='只檢查目前環境，不開啟軟體')
    args, app_args = parser.parse_known_args(argv)
    try:
        assert_local_path(ROOT)
        assert_local_path(sys.executable)
        for index, value in enumerate(app_args):
            for option in ['--data-dir', '--capture', '--support-report']:
                if value == option:
                    if index + 1 >= len(app_args):
                        print('請在 ' + option + ' 後填寫本機位置。', file=sys.stderr); return 2
                    assert_local_path(app_args[index + 1])
                elif value.startswith(option + '='): assert_local_path(value.split('=', 1)[1])
        report_only = any(value == '--support-report' or value.startswith('--support-report=') for value in app_args)
        problems = [] if report_only and not args.check else check_dependencies()
        if problems:
            print('尚未準備好啟動；本次沒有下載或安裝任何套件。', file=sys.stderr)
            for item in problems: print('• ' + item, file=sys.stderr)
            print('請明確執行 PREPARE_WINDOWS.bat 完成首次準備；已有本機套件時可使用 --offline wheelhouse。', file=sys.stderr)
            print('私人作品、字型與資料庫不需要上傳。', file=sys.stderr)
            return 2
        if args.check:
            print('鎖定的 Python 套件已備妥；未開啟主視窗、未建立私人資料庫、未連網。')
            print('Inkscape：已找到本機程式。' if local_inkscape_available() else 'Inkscape：尚未找到。部分 AI 匯入會使用備援，無法還原時會提示；可另行準備本機 Inkscape。')
            print('這是依賴預檢；Windows 原生視窗、字型及實際作品仍需在本機操作核對。')
            return 0
        result = subprocess.run([sys.executable, str(ROOT / 'app.py'), *app_args], cwd=ROOT, check=False)
        if result.returncode:
            print('這次操作尚未完成。可用新的本機 ZIP 名稱執行 --support-report 匯出安全紀錄，再交給 Codex。', file=sys.stderr)
        return result.returncode
    except OfflineAccessError:
        print('只接受本機檔案與資料夾。請改用未同步到雲端的本機位置。', file=sys.stderr); return 2
    except (OSError, ValueError):
        print('本機啟動檢查尚未完成。請確認原始碼已完整解壓縮、環境可讀取，再查看快速開始文件。', file=sys.stderr); return 2


if __name__ == '__main__':
    raise SystemExit(main())

import json
import os
from pathlib import Path
from datetime import datetime
import subprocess
import sys
import time

root = Path(__file__).resolve().parents[2]
logs = root / ".local-dev" / ("review-checks-" + datetime.now().strftime("%Y%m%dT%H%M%S-%f"))
logs.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, PYTHONUTF8="1", QT_QPA_PLATFORM="windows" if os.name == "nt" else "offscreen")
targets = [
    ("diagnostics", ["discover", "-s", "tests", "-p", "test_review_diagnostics.py", "-v"]),
    ("stdio", ["discover", "-s", "tests", "-p", "test_review_stdio.py", "-v"]),
    ("source-compatibility", ["discover", "-s", "tests", "-p", "test_review_source_compatibility.py", "-v"]),
    ("dark-menu", ["test_review_tool_gui.ReviewToolGuiTests.test_popup_menus_remain_readable_with_dark_system_palette", "-v"]),
]
rows = []
for name, args in targets:
    started = time.monotonic()
    # Native PDF baseline took 410 s including real Inkscape conversion.
    # This runner budget does not change the application stage deadlines.
    timeout_seconds = 600 if name == "source-compatibility" else 150
    command = [sys.executable, "-m", "unittest", *args]
    if name == "dark-menu":
        command = [sys.executable, "-c", "import sys,unittest;sys.path.insert(0,'tests');unittest.main(module=None,argv=['unittest',*sys.argv[1:]])", *args]
    try:
        result = subprocess.run(command, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=timeout_seconds, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        (logs / (name + ".log")).write_bytes(result.stdout)
        text = result.stdout.decode("utf-8", errors="replace")
        row = {"name": name, "exit_code": result.returncode, "seconds": round(time.monotonic()-started, 2), "summary": text.splitlines()[-5:]}
    except subprocess.TimeoutExpired as error:
        (logs / (name + ".log")).write_bytes(error.stdout or b"")
        row = {"name": name, "status": "TIMEOUT", "seconds": timeout_seconds}
    rows.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
    (logs / "test-summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
raise SystemExit(0 if all(row.get("exit_code") == 0 for row in rows) else 1)

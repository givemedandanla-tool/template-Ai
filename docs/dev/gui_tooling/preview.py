"""Native design-tool demonstration. Never imports or changes the production core."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from PySide6.QtCore import QFile, QIODevice, Qt
from PySide6.QtTest import QTest
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, help="Save two authored prototype screenshots and smoke JSON")
    parser.add_argument("--xdotool", type=Path, help="Focus this owned window when running in Xvfb without a window manager")
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    source = QFile(str(Path(__file__).with_name("production-workspace.ui")))
    if not source.open(QIODevice.ReadOnly):
        raise RuntimeError(source.errorString())
    loader = QUiLoader()
    window = loader.load(source)
    source.close()
    if window is None:
        raise RuntimeError(loader.errorString())
    name = window.findChild(QLineEdit, "personName")
    action = window.findChild(QPushButton, "primaryAction")
    summary = window.findChild(QLabel, "summary")
    preview_name = window.findChild(QLabel, "previewName")
    detail = window.findChild(QPushButton, "detailsAction")
    technical = window.findChild(QLabel, "technical")
    technical.hide()

    def update_example() -> None:
        if not name.text().strip():
            summary.setText("請先填寫姓名，再更新範例。原有預覽已保留。")
            name.setFocus()
            return
        preview_name.setText(name.text())
        summary.setText("範例畫面已更新。這是設計工具示範，尚未連接正式排版。")

    action.clicked.connect(update_example)
    detail.clicked.connect(lambda: technical.setVisible(not technical.isVisible()))
    window.show()
    if args.xdotool:
        app.processEvents()
        subprocess.run([str(args.xdotool), 'windowfocus', '--sync', str(int(window.winId()))], check=True, timeout=5)
    if args.capture:
        args.capture.mkdir(parents=True, exist_ok=True)
        QTest.qWait(150)
        name.setFocus()
        name.selectAll()
        QTest.keyClicks(name, "Alex Chen")
        QTest.mouseClick(action, Qt.LeftButton)
        app.processEvents()
        assert preview_name.text() == "Alex Chen"
        assert "範例畫面已更新" in summary.text()
        assert window.grab().save(str(args.capture / "workspace-prototype.png"))
        name.clear()
        QTest.mouseClick(action, Qt.LeftButton)
        app.processEvents()
        assert "請先填寫姓名" in summary.text()
        assert preview_name.text() == "Alex Chen"
        assert name.hasFocus()
        QTest.mouseClick(detail, Qt.LeftButton)
        app.processEvents()
        assert technical.isVisible()
        assert window.grab().save(str(args.capture / "workspace-recovery-prototype.png"))
        (args.capture / "prototype-smoke.json").write_text(json.dumps({
            "status": "PASS", "scope": "DESIGN_TOOL_PROTOTYPE_ONLY",
            "checks": ["real QUiLoader window", "keyboard text input", "pointer action updates example",
                       "invalid input retains preview and focuses field", "technical details disclosure"],
            "production_engine_connected": False,
            "qt_platform": app.platformName(),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        window.close()
        return
    app.exec()


if __name__ == "__main__":
    main()

"""桌面啟動入口；預設資料放使用者本機，--data-dir 可指定測試隔離目錄。"""
import argparse
import os
from pathlib import Path
import sys

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from template_ai.gui import MainWindow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir")
    parser.add_argument("--capture", help="只建立真實 GUI 截圖後退出，使用匿名測試資料目錄")
    args = parser.parse_args()
    app = QApplication(sys.argv)
    app.setApplicationName("TemplateAI")
    app.setOrganizationName("TemplateAI")
    root = args.data_dir or QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation)
    window = MainWindow(root)
    window.show()
    if args.capture:
        from PySide6.QtCore import QTimer
        def capture():
            window.grab().save(args.capture)
            window.close()
            app.quit()
        QTimer.singleShot(700, capture)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

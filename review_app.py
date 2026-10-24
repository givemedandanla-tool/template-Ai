"""Independent, offline artwork review entry; no legacy database migration."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


def default_data_dir():
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData/Local')
    else:
        base = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    return base / 'TemplateAI' / 'ReviewTool'


def main():
    parser = argparse.ArgumentParser(description='離線作品判讀與核對')
    parser.add_argument('--data-dir')
    parser.add_argument('--analysis-worker', help=argparse.SUPPRESS)
    parser.add_argument('--release-check', help=argparse.SUPPRESS)
    parser.add_argument('--capture', help=argparse.SUPPRESS)
    args = parser.parse_args()
    from template_ai.review_tool.stdio import (
        WORKER_STDOUT_UNAVAILABLE, prepare_standard_streams,
    )
    stdout_ready = prepare_standard_streams(
        redirected=bool(args.analysis_worker or args.release_check))
    if args.analysis_worker and not stdout_ready:
        # A windowed worker must not silently lose the JSON protocol and leave
        # its parent waiting until the stage timeout.
        return WORKER_STDOUT_UNAVAILABLE
    from template_ai.offline_runtime import assert_local_path, enable_offline_guard
    enable_offline_guard()
    for value in (args.data_dir, args.analysis_worker, args.release_check, args.capture):
        if value:
            assert_local_path(value)
    engine_root = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
    tessdata = engine_root / 'engines/ocr-models'
    if tessdata.is_dir():
        os.environ.setdefault('TEMPLATE_AI_TESSDATA', str(tessdata))
    if args.analysis_worker:
        from template_ai.review_tool.worker import main as worker
        return worker(args.analysis_worker)
    if args.release_check:
        from template_ai.review_tool.release_check import run
        return run(args.release_check)

    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
    from template_ai.review_tool.ui_font import configure_ui_font
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName('TemplateAIReview')
    app.setOrganizationName('TemplateAI')
    configure_ui_font(app)
    splash = QWidget(None, Qt.WindowType.SplashScreen)
    splash.setWindowTitle('作品判讀與核對：正在開啟')
    splash.setStyleSheet('background:#ffffff;color:#172033;font-size:16px;')
    layout = QVBoxLayout(splash)
    title = QLabel('作品判讀與核對')
    title.setStyleSheet('font-size:23px;font-weight:600;padding:12px;')
    status = QLabel('正在開啟介面，請稍候…')
    status.setStyleSheet('padding:12px;')
    layout.addWidget(title)
    layout.addWidget(status)
    splash.resize(440, 150)
    splash.show()
    windows = []

    def start():
        try:
            status.setText('正在讀取本機保存紀錄…')
            app.processEvents()
            from template_ai.review_tool.window import ReviewWindow
            window = ReviewWindow(Path(args.data_dir) if args.data_dir else default_data_dir())
            windows.append(window)
            window.show()
            splash.close()
            if args.capture:
                def capture():
                    target = Path(args.capture)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    window.grab().save(str(target))
                    window._allow_close = True
                    window.close()
                    app.quit()
                QTimer.singleShot(600, capture)
        except Exception as error:
            # Keep an actionable window visible even when a dependency/store fails.
            status.setText('尚未成功開啟。請保留本機資料，使用另一個資料目錄，\n或匯出安全問題報告後聯絡維護者。')
            from PySide6.QtWidgets import QPushButton
            close = QPushButton('關閉')
            close.clicked.connect(app.quit)
            layout.addWidget(close)
            import traceback
            target = Path(args.data_dir) if args.data_dir else default_data_dir()
            try:
                target.mkdir(parents=True, exist_ok=True)
                (target / 'startup-error.local.txt').write_text(traceback.format_exc(), encoding='utf-8')
            except OSError:
                pass
            startup_error_type = type(error).__name__
            def report_failure():
                from PySide6.QtWidgets import QFileDialog
                import json
                destination, _ = QFileDialog.getSaveFileName(splash, '保存安全啟動報告', 'review-startup-report.json', 'JSON (*.json)')
                if destination:
                    try:
                        Path(destination).write_text(json.dumps({'component':'TemplateAIReview','stage':'startup',
                            'error_type':startup_error_type,'code':'LOCAL_START_FAILED',
                            'private_text_paths_and_traceback_included':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                        status.setText('安全啟動報告已保存，請檢查後手動分享。')
                    except OSError:
                        status.setText('啟動報告未保存，請改選可寫入的本機位置。')
            report = QPushButton('保存安全啟動報告')
            report.clicked.connect(report_failure)
            layout.addWidget(report)
    QTimer.singleShot(0, start)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())

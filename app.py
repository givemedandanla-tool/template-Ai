"""桌面啟動入口；預設資料放使用者本機，--data-dir 可指定測試隔離目錄。"""
import argparse
import os
from pathlib import Path
import sys


def default_data_dir():
    """The existing Qt AppLocalDataLocation convention, without requiring Qt.

    This keeps startup-failure reporting usable when GUI dependencies cannot
    import. Runtime data stays in the same TemplateAI/TemplateAI directory.
    """
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        configured = os.environ.get('XDG_DATA_HOME')
        base = Path(configured) if configured and Path(configured).is_absolute() else Path.home() / '.local' / 'share'
    return base / 'TemplateAI' / 'TemplateAI'


def main():
    from template_ai.launch import dispatch_worker
    if dispatch_worker():
        return 0
    from template_ai.offline_runtime import assert_local_path, enable_offline_guard
    from template_ai.offline_support import OfflineJournal, install_exception_reporting, save_support_bundle
    enable_offline_guard()
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir")
    parser.add_argument("--release-check", help=argparse.SUPPRESS)
    parser.add_argument("--capture", help="只建立真實 GUI 截圖後退出，使用匿名測試資料目錄")
    parser.add_argument("--support-report", help="不開主視窗，將最近的安全操作紀錄匯出到新的本機 ZIP")
    args = parser.parse_args()
    if args.release_check:
        from template_ai.release_check import run
        return run(args.release_check)
    for value in (args.data_dir, args.capture, args.support_report):
        if value:
            assert_local_path(value)
    root = args.data_dir or default_data_dir()
    assert_local_path(root)
    journal = OfflineJournal(root)
    enable_offline_guard(lambda: journal.record('APPLICATION', 'NETWORK_BLOCKED'))
    if args.support_report:
        try:
            save_support_bundle(args.support_report, journal.bundle())
            journal.record('SUPPORT', 'REPORT_EXPORTED')
            journal.record('APPLICATION', 'APP_CLOSED')
            print('已保存本機問題報告；請手動附到 Codex 對話。')
            return 0
        except Exception as error:
            journal.record('SUPPORT', 'REPORT_SAVE_FAILED', error=error)
            print('報告尚未保存；請使用可寫入的本機資料夾及新的 ZIP 檔名。', file=sys.stderr)
            return 1
    window_ref = []
    def notify():
        if window_ref and hasattr(window_ref[0], 'offline_support'):
            window_ref[0].offline_support.problem.emit()
    restore = install_exception_reporting(journal, notify)
    restore_qt = None
    try:
        from PySide6.QtWidgets import QApplication
        from template_ai.gui import MainWindow
        from template_ai.offline_support import install_qt_message_reporting
        restore_qt = install_qt_message_reporting(journal)
        app = QApplication(sys.argv)
        app.setApplicationName('TemplateAI')
        from template_ai import __version__
        app.setApplicationVersion(__version__)
        app.setOrganizationName('TemplateAI')
        app._template_ai_support_journal = journal
        window = MainWindow(root)
        window_ref.append(window)
        window.navigate_mode(2)
        window.show()
        if args.capture:
            from PySide6.QtCore import QTimer
            def capture():
                saved = window.grab().save(args.capture)
                if not saved:
                    print("真實 GUI 截圖尚未保存，請檢查本機目的地。", file=sys.stderr)
                window.close()
                app.exit(0 if saved else 1)
            QTimer.singleShot(700, capture)
        return app.exec()
    except Exception as error:
        journal.capture_exception(error, error.__traceback__)
        print('軟體尚未啟動；可用 --support-report 匯出本機安全紀錄。', file=sys.stderr)
        return 1
    finally:
        if restore_qt:
            restore_qt()
        restore()


if __name__ == "__main__":
    raise SystemExit(main())

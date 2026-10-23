"""Review the real desktop window using an empty local library, never user data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import tempfile
import time

from tooling_extensions import verify_extensions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--native', action='store_true', help='Use isolated Xvfb and original OS screenshot helper')
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--height', type=int, default=860)
    args = parser.parse_args()
    if args.width < 640 or args.height < 480:
        parser.error('Review size must be at least 640 by 480')
    here = Path(__file__).resolve().parent
    repository = here.parents[2]
    verify_extensions(here)
    def application_hashes() -> dict[str, str]:
        return {str(path.relative_to(repository)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted((repository / 'template_ai').rglob('*.py'))}
    before_hashes = application_hashes()
    sys.path.insert(0, str(repository))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    process = None
    logfile = None
    read_fd = write_fd = None
    started = time.monotonic()
    try:
        if args.native:
            native = repository.parent / 'template-ai-gui-tools/root'
            server = native / 'usr/bin/Xvfb'
            if not server.is_file():
                raise RuntimeError('Run bootstrap_gui.py --with-x11 to rebuild verified native tools')
            library = str(native / 'usr/lib/x86_64-linux-gnu')
            os.environ['LD_LIBRARY_PATH'] = library + (':' + os.environ['LD_LIBRARY_PATH'] if os.environ.get('LD_LIBRARY_PATH') else '')
            os.environ['QT_QPA_PLATFORM'] = 'xcb'
            read_fd, write_fd = os.pipe()
            logfile = (output / 'owned-xvfb.log').open('w')
            process = subprocess.Popen([str(server), '-displayfd', str(write_fd), '-screen', '0',
                str(max(args.width + 100, 1500)) + 'x' + str(max(args.height + 100, 1000)) + 'x24',
                '-nolisten', 'tcp'], pass_fds=(write_fd,), stdout=logfile, stderr=logfile,
                start_new_session=True)
            os.close(write_fd)
            write_fd = None
            if not select.select([read_fd], [], [], 10)[0]:
                raise RuntimeError('Owned X display did not become ready')
            display = os.read(read_fd, 64).decode().strip()
            if not display.isdigit():
                raise RuntimeError('Unexpected display identifier')
            os.environ['DISPLAY'] = ':' + display
        else:
            os.environ['QT_QPA_PLATFORM'] = 'offscreen'

        from PySide6.QtCore import Qt
        from PySide6.QtGui import QImage
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication, QPushButton, QWidget
        from template_ai.gui import MainWindow

        app = QApplication.instance() or QApplication([])
        captures = []
        with tempfile.TemporaryDirectory(prefix='template-ai-owned-gui-') as temporary:
            window = MainWindow(Path(temporary))
            window.resize(args.width, args.height)
            window.show()
            QTest.qWait(200)
            app.processEvents()
            win_id = int(window.winId())
            if args.native:
                # An isolated Xvfb has no window manager to activate a mapped window.
                # Establish that prerequisite before checking real keyboard movement.
                subprocess.run([str(native / 'usr/bin/xdotool'), 'windowfocus', '--sync', str(win_id)],
                               check=True, timeout=5, capture_output=True, text=True)
                QTest.qWait(80)
                app.processEvents()
            for page in range(window.tabs.count()):
                window.tabs.setCurrentIndex(page)
                QTest.qWait(120)
                app.processEvents()
                if window.tabs.currentIndex() != page:
                    raise RuntimeError('A real workspace page could not be selected')
                destination = output / ('owned-workspace-' + str(page) + '.png')
                if args.native:
                    environment = os.environ.copy()
                    for name in ['CODEX_SCREENSHOT_TEST_MODE', 'CODEX_SCREENSHOT_TEST_PLATFORM',
                                 'CODEX_SCREENSHOT_TEST_WINDOWS', 'CODEX_SCREENSHOT_TEST_DISPLAYS']:
                        environment.pop(name, None)
                    subprocess.run([sys.executable,
                        str(here / 'vendor/openai-screenshot/scripts/take_screenshot.py'),
                        '--window-id', str(win_id), '--path', str(destination)],
                        check=True, env=environment, timeout=20, capture_output=True, text=True)
                elif not window.grab().save(str(destination)):
                    raise RuntimeError('Owned widget screenshot failed')
                image = QImage(str(destination))
                if image.isNull() or image.width() < 640 or image.height() < 480:
                    raise RuntimeError('Screenshot is missing or too small to verify the workspace')
                buttons = [b for b in window.findChildren(QPushButton) if b.isVisible() and b.isEnabled()]
                focusable = [w for w in window.findChildren(QWidget)
                             if w.isVisible() and w.isEnabled() and w.focusPolicy() != Qt.NoFocus]
                unnamed = [b.objectName() or type(b).__name__ for b in buttons
                           if not b.text().strip() and not b.accessibleName().strip() and not b.toolTip().strip()]
                tab_focus_moved = None
                if len(focusable) > 1:
                    focusable[0].setFocus()
                    previous = app.focusWidget()
                    QTest.keyClick(focusable[0], Qt.Key_Tab)
                    app.processEvents()
                    current = app.focusWidget()
                    tab_focus_moved = current is not None and current is not previous and current.isVisible()
                    if not tab_focus_moved:
                        raise RuntimeError('A visible workspace could not move keyboard focus with Tab')
                captures.append(dict(page_index=page, width=image.width(), height=image.height(),
                    screenshot=destination.name, sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                    visible_enabled_buttons=len(buttons), focusable_controls=len(focusable),
                    unnamed_button_warnings=unnamed, tab_focus_moved=tab_focus_moved))
            window.close()
            window.deleteLater()
            app.processEvents()
        source_hashes = application_hashes()
        if source_hashes != before_hashes:
            raise RuntimeError('Application sources changed during the capture; freeze and rerun')
        result = dict(schema=1, status='PASS', scope='Owned real MainWindow visual capture and reachability only',
            source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repository, text=True).strip(),
            source_hashes=source_hashes, native=args.native,
            source_unchanged=True,
            capture_backend='Original OpenAI screenshot helper; explicit owned window ID; test mode disabled'
                            if args.native else 'Real Qt widget grab; offscreen',
            library='Generated empty local library; no private data opened',
            elapsed_seconds=round(time.monotonic() - started, 3), captures=captures,
            not_verified=['Human beginner usability', 'Windows and IME', 'Full accessibility qualification',
                          'Layout engine or production print qualification'])
        (output / 'owned-workspace-review.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(dict(status=result['status'], captures=len(captures), native=args.native,
            report=str(output / 'owned-workspace-review.json')), ensure_ascii=False))
    finally:
        for fd in [read_fd, write_fd]:
            if fd is not None:
                os.close(fd)
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        if logfile is not None:
            logfile.close()


if __name__ == '__main__':
    main()

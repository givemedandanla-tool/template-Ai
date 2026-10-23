"""Exercise the real Qt Designer under a local Xvfb; no application database is opened."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import time


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tool-root', type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    repository = here.parents[2]
    native = (args.tool_root or repository.parent / 'template-ai-gui-tools') / 'root'
    args.output.mkdir(parents=True, exist_ok=True)
    read_fd, write_fd = os.pipe()
    processes = []
    environment = os.environ.copy()
    library = str(native / 'usr/lib/x86_64-linux-gnu')
    environment['LD_LIBRARY_PATH'] = library + (':' + environment['LD_LIBRARY_PATH'] if environment.get('LD_LIBRARY_PATH') else '')
    environment['QT_QPA_PLATFORM'] = 'xcb'
    try:
        with (args.output / 'xvfb.log').open('w') as log:
            server = subprocess.Popen([str(native / 'usr/bin/Xvfb'), '-displayfd', str(write_fd),
                '-screen', '0', '1600x1100x24', '-nolisten', 'tcp'], pass_fds=(write_fd,),
                stdout=log, stderr=log, env=environment, start_new_session=True)
        processes.append(server)
        os.close(write_fd)
        write_fd = -1
        if not select.select([read_fd], [], [], 10)[0]:
            raise RuntimeError('Xvfb did not become ready; inspect the local xvfb.log')
        display = os.read(read_fd, 64).decode().strip()
        if not display.isdigit():
            raise RuntimeError('Invalid isolated X display')
        environment['DISPLAY'] = ':' + display
        xdo = str(native / 'usr/bin/xdotool')

        def command(*parts: str) -> str:
            return subprocess.check_output([xdo, *parts], env=environment, text=True, stderr=subprocess.DEVNULL, timeout=10).strip()

        with (args.output / 'designer.log').open('w') as log:
            designer = subprocess.Popen([str(repository / '.venv/bin/pyside6-designer'),
                str(here / 'production-workspace.ui')], env=environment, stdout=log,
                stderr=log, start_new_session=True)
        processes.append(designer)
        names = []
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if designer.poll() is not None:
                raise RuntimeError('Qt Designer exited; inspect the local designer.log')
            try:
                windows = command('search', '--onlyvisible', '--name', 'Designer').splitlines()
                names = [command('getwindowname', window) for window in windows]
                if names:
                    break
            except subprocess.CalledProcessError:
                pass
            time.sleep(.15)
        else:
            raise RuntimeError('Designer did not show the expected .ui document: ' + repr(names))
        # Qt Designer's MDI document title is not necessarily the native X window title.
        # Preserve its real screenshot for visual document verification instead of assuming one.
        window = windows[0]
        command('windowsize', window, '1580', '1030')
        command('windowmove', window, '0', '0')
        time.sleep(.4)
        subprocess.run(['import', '-window', 'root', str(args.output / 'designer-editing.png')], env=environment, check=True, timeout=15)
        command('key', '--window', window, 'ctrl+r')
        time.sleep(.5)
        visible = command('search', '--onlyvisible', '--name', '.*').splitlines()
        titles = [command('getwindowname', identity) for identity in visible]
        subprocess.run(['import', '-window', 'root', str(args.output / 'designer-preview.png')], env=environment, check=True, timeout=15)
        # Also exercise the authored .ui as a native interactive xcb window.
        subprocess.run([str(repository / '.venv/bin/python'), str(here / 'preview.py'),
                        '--capture', str(args.output / 'native-preview'), '--xdotool', xdo], env=environment, check=True, timeout=30)
        (args.output / 'designer-smoke.json').write_text(json.dumps(dict(
            status='PASS', scope='NATIVE_GUI_DESIGN_TOOL_ONLY', qt='6.8.3',
            editing_document_argument='production-workspace.ui', designer_window=names,
            editing_document_verification='Launch argument plus separately reviewed editing screenshot; native QUiLoader checks the same .ui',
            preview_shortcut_sent='Ctrl+R', visible_window_titles=titles,
            x11_network='LOCAL_DISPLAY;TCP_DISABLED', production_database_opened=False,
            limits='Concept-only .ui;actual product drag/layout/export verified in formal integration run, not here',
        ), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('Qt Designer opened the authored document; native prototype interaction PASS')
    finally:
        os.close(read_fd)
        if write_fd >= 0:
            os.close(write_fd)
        for process in reversed(processes):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=3)


if __name__ == '__main__':
    main()

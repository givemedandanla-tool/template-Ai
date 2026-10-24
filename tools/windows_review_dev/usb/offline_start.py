"""Offline, additive Windows setup. Never downloads, updates Git or copies user data."""
from __future__ import annotations

import argparse
import contextlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import struct
import subprocess
import sys
import time
import uuid

BRANCH = 'feature/review-tool-v0.1.0'
CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def safe_member(root, name):
    rel = PurePosixPath(name)
    if not name or '\\' in name or ':' in name or rel.is_absolute() or any(p in ('..', '.', '') for p in name.split('/')):
        raise ValueError('Unsafe manifest path')
    # Names cannot contain an absolute path, drive, dot or parent component.
    # Resolve the stable root only: resolving a not-yet-created leaf while other
    # workers mkdir its parents can yield inconsistent Windows canonical paths.
    root = Path(root).resolve()
    target = root.joinpath(*rel.parts)
    cursor = target
    while cursor != root:
        try:
            info = cursor.lstat()  # inspect links/junctions themselves, never follow them
        except FileNotFoundError:
            cursor = cursor.parent
            continue
        import stat
        if stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400):
            raise ValueError('Reparse points are not supported')
        cursor = cursor.parent
    return target


def verify_bundle(root, progress=False):
    manifest = json.loads((root / 'transfer-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('branch') != BRANCH or manifest.get('schema_version') != 1:
        raise ValueError('Wrong branch or transfer format')
    entries = manifest.get('files', [])
    names = [row['path'] for row in entries]
    if not entries or len(names) != len(set(n.casefold() for n in names)):
        raise ValueError('Empty or duplicate manifest')
    def verify_one(row):
        path = safe_member(root, row['path'])
        if not path.is_file() or path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise ValueError('Missing or changed transfer file: ' + row['path'])
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(verify_one, row) for row in entries]
        for index, future in enumerate(as_completed(futures), 1):
            future.result()
            if progress and index % 2000 == 0:
                print(f'完整性檢查：{index}/{len(entries)} 個檔案', flush=True)
    required = {'python/python.exe', 'python/pythonw.exe', 'inkscape/bin/inkscape.exe',
                'source/review_app.py', 'source/requirements-lock.txt', 'offline-requirements.txt'}
    if not required <= set(names):
        raise ValueError('Incomplete transfer')
    return manifest, digest(root / 'transfer-manifest.json')


def new_install(base):
    base = Path(base).resolve()
    if str(base).startswith('\\\\') or len(str(base)) > 65:
        raise ValueError('Use a short local installation directory (at most 65 characters)')
    if os.name == 'nt' and ctypes.windll.kernel32.GetDriveTypeW(str(base.anchor)) != 3:
        raise ValueError('Installation must use a fixed local disk, not USB or a network drive')
    base.mkdir(parents=True, exist_ok=True)
    target = base / ('r' + uuid.uuid4().hex[:10])
    target.mkdir(exist_ok=False)
    return target


def clone_transfer(bundle, target, manifest):
    # Exact manifest allowlist: extra USB files, originals, databases and logs never copied.
    total = len(manifest['files'])
    def copy_one(row):
        src = safe_member(bundle, row['path'])
        dest = safe_member(target, row['path'])
        dest.parent.mkdir(parents=True, exist_ok=True)
        with src.open('rb') as source, dest.open('xb') as output:
            shutil.copyfileobj(source, output, 1024 * 1024)
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = [pool.submit(copy_one, row) for row in manifest['files']]
        for index, future in enumerate(as_completed(jobs), 1):
            future.result()
            if index % 2000 == 0:
                print(f'複製本機環境：{index}/{total} 個檔案', flush=True)
    with (bundle / 'transfer-manifest.json').open('rb') as source, (target / 'transfer-manifest.json').open('xb') as output:
        shutil.copyfileobj(source, output)
    verify_bundle(target, progress=True)


def child_env(target):
    env = dict(os.environ)
    for key in list(env):
        if key.upper().startswith(('PYTHON', 'PIP_', 'QT_', 'TEMPLATE_AI_', 'INKSCAPE_')):
            env.pop(key)
    env.update(PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1',
               PIP_CONFIG_FILE=os.devnull, PIP_DISABLE_PIP_VERSION_CHECK='1',
               PIP_NO_INDEX='1', QT_QPA_PLATFORM='windows',
               TEMPLATE_AI_INKSCAPE=str(target / 'inkscape/bin/inkscape.exe'),
               INKSCAPE_PROFILE_DIR=str(target / 'data/inkscape-profile'))
    env['PATH'] = str(target / 'inkscape/bin') + os.pathsep + env.get('PATH', '')
    return env


def run_logged(args, log, target, *, timeout=900):
    with Path(log).open('xb') as stream:
        result = subprocess.run([str(x) for x in args], cwd=target / 'source',
                                env=child_env(target), stdout=stream, stderr=subprocess.STDOUT,
                                timeout=timeout, creationflags=CREATE_NO_WINDOW)
    return result.returncode


def prepare_environment(target, logs):
    python = target / 'python/python.exe'
    vpython = target / '.venv/Scripts/python.exe'
    steps = [
        ([python, '-I', '-B', '-m', 'venv', target / '.venv'], '01-venv.log'),
        ([vpython, '-I', '-B', '-m', 'pip', '--isolated', 'install', '--no-index', '--no-cache-dir',
          '--disable-pip-version-check', '--only-binary=:all:', '--require-hashes',
          '--find-links', target / 'wheels', '-r', target / 'offline-requirements.txt'], '02-dependencies.log'),
        ([vpython, '-I', '-B', '-m', 'pip', '--isolated', 'check'], '03-pip-check.log'),
        ([vpython, '-B', target / 'source/tools/local_start.py', '--check'], '04-environment.log'),
        ([target / 'inkscape/bin/inkscape.exe', '--version'], '05-inkscape.log'),
    ]
    for index, (cmd, name) in enumerate(steps, 1):
        print(f'準備環境 {index}/{len(steps)}：{name}', flush=True)
        if run_logged(cmd, logs / name, target):
            raise RuntimeError('Environment preparation failed; see ' + str(logs / name))
    write_new(target / 'environment-ready.json', {'prepared': True, 'offline': True})


def smoke_passed(folder, returncode):
    # A zero process exit alone is insufficient: require the real-smoke receipt too.
    try:
        summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return False
    return (returncode == 0 and summary.get('status') == 'AUTOMATED_PASS'
            and summary.get('synthetic_only') is True and summary.get('real_illustrator_verified') is True
            and summary.get('source_unchanged') is True
            and summary.get('checks_total', 0) >= 6
            and summary.get('checks_passed') == summary.get('checks_total'))


def qualify_illustrator(target, logs, retest=False):
    history = target / 'qualifications'
    previous = sorted(history.glob('*.json'), key=lambda p: p.stat().st_mtime_ns)
    if previous and not retest:
        receipt = json.loads(previous[-1].read_text(encoding='utf-8'))
        folder = safe_member(target, receipt['smoke_directory'])
        if receipt.get('passed'):
            if not smoke_passed(folder, 0):
                raise RuntimeError('Saved synthetic qualification is invalid; use RETEST_ILLUSTRATOR.cmd')
            return True
    folder = target / 'synthetic' / uuid.uuid4().hex[:8]
    print('正在呼叫 Illustrator 建立合成 AI 並驗證判讀。請處理 Illustrator 的提示視窗。', flush=True)
    rc = run_logged([target / '.venv/Scripts/python.exe', '-B',
                     target / 'source/tools/windows_review_dev/illustrator_bridge/smoke.py',
                     '--output', folder], logs / '06-illustrator-smoke.log', target, timeout=1500)
    passed = smoke_passed(folder, rc)
    write_new(history / (str(time.time_ns()) + '-' + uuid.uuid4().hex[:8] + '.json'),
              {'passed': passed, 'smoke_directory': folder.relative_to(target).as_posix(), 'manual_visual_review': 'REQUIRED'})
    if not passed:
        print('Illustrator 合成驗收未通過，尚未啟動 review-tool。請查看診斷記錄。', flush=True)
        return False
    return True


@contextlib.contextmanager
def exclusive_lock(path):
    import msvcrt
    with Path(path).open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError('此工作階段正在準備或已開啟，請使用現有視窗。') from exc
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def gui_running(target):
    try:
        with exclusive_lock(target / 'gui.lock'):
            return False
    except RuntimeError:
        return True


def launch(target, logs):
    helper = target / 'source/tools/windows_review_dev/usb/gui_session.py'
    proc = subprocess.Popen([str(target / '.venv/Scripts/pythonw.exe'), '-B', str(helper),
                             str(target), str(logs)], cwd=target / 'source', env=child_env(target),
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=CREATE_NO_WINDOW | 0x00000008)
    time.sleep(3)
    if proc.poll() is not None:
        raise RuntimeError('review-tool exited during startup; see ' + str(logs))
    write_new(logs / 'launch.json', {'pid': proc.pid, 'status': 'PROCESS_RUNNING_UI_NOT_AUTOMATICALLY_VERIFIED'})
    print('review-tool 已送出啟動。原稿請從「更多 → 使用 Illustrator 匯入 AI（實驗性）」加入。', flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--local-root', type=Path, help='Optional short LOCAL installation parent')
    parser.add_argument('--check-transfer', action='store_true')
    parser.add_argument('--prepare-only', action='store_true', help='Still requires Illustrator synthetic qualification; does not open GUI')
    parser.add_argument('--retest', action='store_true')
    args = parser.parse_args(argv)
    if os.name != 'nt' or struct.calcsize('P') != 8:
        raise RuntimeError('Windows x64 is required')
    bundle = args.bundle.resolve()
    print('核對隨身碟來源與工具完整性（不連網）…', flush=True)
    manifest, identity = verify_bundle(bundle, progress=True)
    if args.check_transfer:
        print('TRANSFER_VERIFIED: ' + identity)
        return 0
    state_home = Path(os.environ['LOCALAPPDATA']) / 'TemplateAIReviewUSB'
    state_home.mkdir(parents=True, exist_ok=True)
    index = state_home / (identity[:20] + '.json')
    with exclusive_lock(state_home / (identity[:20] + '.lock')):
        needs_copy = False
        if index.exists():
            receipt = json.loads(index.read_text(encoding='utf-8'))
            if receipt.get('manifest_sha256') != identity:
                raise RuntimeError('Local receipt mismatch; existing files left unchanged')
            target = Path(receipt['installation'])
            if not (target / 'environment-ready.json').is_file():
                raise RuntimeError('Existing environment is incomplete; existing files left unchanged')
            if gui_running(target):
                print('review-tool 已在執行，請使用現有視窗。')
                return 0
            _, local_identity = verify_bundle(target, progress=True)
            if local_identity != identity:
                raise RuntimeError('Local source changed; existing files left unchanged')
        else:
            if args.local_root:
                target = new_install(args.local_root)
            else:
                try:
                    target = new_install(Path(os.environ.get('SystemDrive', 'C:') + '/') / 'ReviewToolLocal')
                except PermissionError:
                    target = new_install(Path(os.environ['LOCALAPPDATA']) / 'TR')
            print('新的本機環境：' + str(target), flush=True)
            needs_copy = True
        logs = target / 'diagnostics' / (time.strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6])
        logs.mkdir(parents=True, exist_ok=False)
        print('本機診斷：' + str(logs), flush=True)
        try:
            if needs_copy:
                clone_transfer(bundle, target, manifest)
            if not index.exists():
                prepare_environment(target, logs)
                write_new(index, {'manifest_sha256': identity, 'installation': str(target)})
            elif run_logged([target / '.venv/Scripts/python.exe', '-B', target / 'source/tools/local_start.py', '--check'],
                            logs / '04-environment.log', target):
                raise RuntimeError('Existing environment check failed; files left unchanged')
            if not qualify_illustrator(target, logs, args.retest):
                write_new(logs / 'result.json', {'status': 'SYNTHETIC_NOT_PASSED', 'gui_started': False})
                return 3
            if not args.prepare_only:
                launch(target, logs)
            write_new(logs / 'result.json', {'status': 'SYNTHETIC_PASSED', 'launch_requested': not args.prepare_only,
                                           'private_fidelity_verified': False})
            print('環境及資料保留於：' + str(target), flush=True)
            print('之後可直接雙擊該資料夾的 START_REVIEW.cmd；不需要隨身碟。', flush=True)
            return 0
        except Exception as exc:
            write_new(logs / 'failure.local.json', {'error': str(exc), 'private_log_do_not_upload': True})
            raise


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    try:
        raise SystemExit(main())
    except Exception as error:
        print('未完成：' + str(error), file=sys.stderr)
        try:
            failure = Path(os.environ['LOCALAPPDATA']) / 'TemplateAIReviewUSB/failures' / (uuid.uuid4().hex + '.local.json')
            write_new(failure, {'error': str(error), 'private_log_do_not_upload': True})
            print('失敗記錄：' + str(failure), file=sys.stderr)
        except OSError:
            pass
        raise SystemExit(2)

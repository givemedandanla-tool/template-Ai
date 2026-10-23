"""Bounded local demonstration; no claim of actual frozen Windows execution."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import runpy
import sys
import types
from unittest.mock import patch


def verify():
    hook = Path(__file__).with_name('frozen_runtime_hook.py')
    def original(*args, **kwargs):
        return None
    fake = types.SimpleNamespace(enable=original, dump_traceback_later=original,
                                 cancel_dump_traceback_later=original)
    stream = io.StringIO()
    with patch.dict(sys.modules, {'faulthandler': fake}), \
            patch.object(sys, 'platform', 'win32'), \
            patch.object(sys, 'frozen', True, create=True), \
            patch.dict(os.environ, {'GITHUB_ACTIONS': 'true', 'BUNDLE_DIAGNOSTIC_TRACE': 'false'}), \
            patch.object(sys, 'stderr', io.StringIO()):
        namespace = runpy.run_path(str(hook))
        fake.dump_traceback_later(.01, file=stream)
        namespace['timer'][0].join(1)
        assert 'SAFE_FROZEN_TRACEBACK' in stream.getvalue() and 'Thread ' in stream.getvalue()
        assert str(Path.cwd()) not in stream.getvalue()
        cancelled = io.StringIO()
        fake.dump_traceback_later(.1, file=cancelled)
        timer = namespace['timer'][0]
        fake.cancel_dump_traceback_later()
        timer.join(1)
        assert not cancelled.getvalue()
    fake.dump_traceback_later = original
    with patch.dict(sys.modules, {'faulthandler': fake}), \
            patch.dict(os.environ, {'GITHUB_ACTIONS': 'false'}):
        runpy.run_path(str(hook))
        assert fake.dump_traceback_later is original
    return dict(scope='ISOLATED_DIAGNOSTIC_TIMER_DEMONSTRATION_NOT_WINDOWS_PROOF',
                command='python docs/dev/releases/verify_frozen_diagnostic_timer.py',
                python=platform.python_version(), hook_sha256=hashlib.sha256(hook.read_bytes()).hexdigest(),
                checks=[dict(case=name, status='PASS') for name in (
                    'referenced_frame_dump_without_absolute_paths', 'cancel_preserved',
                    'ordinary_launch_does_not_install_GHA_timer')],
                unchanged=['original release-check 45s call', 'parent 240s hard deadline',
                           'original 21 EXE assertions'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = json.dumps(verify(), indent=2)+'\n'
    if args.output:
        args.output.write_text(result, encoding='utf-8')
    print(result, end='')

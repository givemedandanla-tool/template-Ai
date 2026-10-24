"""Own the local session lock inside pythonw, independently of the setup console."""
from pathlib import Path
import runpy
import sys

from offline_start import exclusive_lock


def main():
    target, logs = map(Path, sys.argv[1:3])
    with (logs / 'gui-stdio.local.log').open('x', encoding='utf-8', buffering=1) as stream:
        sys.stdout = sys.stderr = stream
        try:
            with exclusive_lock(target / 'gui.lock'):
                root = target / 'source'
                sys.path.insert(0, str(root))
                sys.argv = [str(root / 'review_app.py'), '--data-dir', str(target / 'data'),
                            '--diagnostics-dir', str(logs / 'qt')]
                runpy.run_path(str(root / 'review_app.py'), run_name='__main__')
        except Exception:
            import traceback
            traceback.print_exc()
            return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

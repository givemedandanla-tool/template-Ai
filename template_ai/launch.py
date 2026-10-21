"""Keep existing local subprocess protocols working in a frozen desktop build."""
from pathlib import Path
import runpy
import sys

WORKER_MODULES = frozenset({
    'template_ai.runtime_worker',
    'template_ai.coverage_command',
    'template_ai.quality_command',
    'template_ai.review_ledger',
})


def dispatch_worker(arguments=None):
    """Handle only the application's existing -m protocols, never arbitrary code."""
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    if not arguments or arguments[0] != '-m':
        return False
    if len(arguments) < 2 or arguments[1] not in WORKER_MODULES:
        raise ValueError('不支援的內部背景工作入口')
    from .offline_runtime import enable_offline_guard
    enable_offline_guard()
    original = sys.argv
    try:
        sys.argv = [arguments[1], *arguments[2:]]
        runpy.run_module(arguments[1], run_name='__main__', alter_sys=True)
    finally:
        sys.argv = original
    return True


def desktop_arguments(root):
    """A frozen executable is its own launcher; Python still needs app.py."""
    prefix = [] if getattr(sys, 'frozen', False) else [str(Path(__file__).resolve().parents[1] / 'app.py')]
    return [*prefix, '--data-dir', str(root)]

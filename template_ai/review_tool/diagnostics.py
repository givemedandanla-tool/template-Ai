"""Opt-in, process-local Qt diagnostics. Never include raw logs in safe reports.

Install before QApplication so native platform/font initialization is covered.
The parent passes only the opt-in directory through its existing environment;
each process creates a unique file and leaves worker stdout as JSON IPC.
"""
from __future__ import annotations

import atexit
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import threading
import uuid

ENVIRONMENT_VARIABLE = 'TEMPLATE_AI_REVIEW_DIAGNOSTICS_DIR'
MAX_LOG_BYTES = 2 * 1024 * 1024
MAX_MESSAGE_CHARACTERS = 8192
CANARY = 'REVIEW_DIAGNOSTIC_CANARY_SYNTHETIC'
_active = None


class LocalQtDiagnostics:
    """Bounded raw local log and an explicitly content-free summary."""

    def __init__(self, directory, *, role):
        from ..offline_runtime import assert_local_path
        from PySide6.QtCore import qInstallMessageHandler
        if role not in {'gui', 'worker', 'probe', 'test'}:
            raise ValueError('Unsupported diagnostic role')
        assert_local_path(directory)
        directory = Path(directory).absolute()
        if any(p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction())
               for p in (directory, *directory.parents)):
            raise ValueError('Diagnostic directory must not use links')
        assert_local_path(directory.resolve())
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f'qt-{role}-{os.getpid()}-{uuid.uuid4().hex}.local.jsonl'
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self._stream = os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n')
        self._lock = threading.Lock()
        self._closed = False
        self._bytes = 0
        self._counts = dict(qt_messages=0, directwrite_messages=0, font_messages=0,
                            canary_messages=0, dropped_messages=0, write_errors=0)
        self._write({'event': 'start', 'role': role, 'platform_requested': os.getenv('QT_QPA_PLATFORM'),
                     'utc': datetime.now(timezone.utc).isoformat(), 'raw_local_only': True})
        self._previous = qInstallMessageHandler(self._handle)
        atexit.register(self.close)

    def _write(self, event):
        try:
            line = json.dumps(event, ensure_ascii=False) + '\n'
            self._stream.write(line)
            self._stream.flush()
            self._bytes += len(line.encode('utf-8'))
        except (OSError, ValueError, UnicodeError):
            self._counts['write_errors'] += 1

    def _handle(self, kind, context, message):
        with self._lock:
            if not self._closed:
                self._counts['qt_messages'] += 1
                folded = message.casefold()
                self._counts['directwrite_messages'] += int('directwrite' in folded or 'dwrite' in folded)
                self._counts['font_messages'] += int('font' in folded)
                self._counts['canary_messages'] += int(message == CANARY)
                bounded = message[:MAX_MESSAGE_CHARACTERS]
                # Reserve room for the final summary and JSON escaping.
                if self._bytes + len(bounded.encode('utf-8')) * 6 + 2048 < MAX_LOG_BYTES:
                    self._write({'event': 'qt_message', 'type': int(kind), 'message': bounded,
                                 'truncated': len(message) > len(bounded)})
                else:
                    self._counts['dropped_messages'] += 1
        # Keep the previous sink; never allocate a console or write IPC stdout.
        if self._previous:
            self._previous(kind, context, message)
        elif sys.stderr is not None:
            try:
                sys.stderr.write(message + '\n')
                sys.stderr.flush()
            except (OSError, ValueError, UnicodeError):
                pass

    def safe_summary(self):
        with self._lock:
            return dict(self._counts, raw_text_paths_font_names_included=False)

    def close(self):
        global _active
        from PySide6.QtCore import qInstallMessageHandler
        with self._lock:
            if self._closed:
                return
            self._closed = True
            qInstallMessageHandler(self._previous)
            self._write(dict(event='summary', **self._counts, raw_text_paths_font_names_included=False))
            self._stream.close()
        atexit.unregister(self.close)
        if _active is self:
            _active = None


def start_diagnostics(directory=None, *, role='gui'):
    """Explicit argument or environment opt-in; no log/files by default."""
    global _active
    directory = directory or os.environ.get(ENVIRONMENT_VARIABLE)
    if not directory:
        return None
    if _active is not None:
        raise RuntimeError('Qt diagnostics already active in this process')
    _active = LocalQtDiagnostics(directory, role=role)
    return _active

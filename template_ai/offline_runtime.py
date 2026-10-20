"""Local-use policy. This is an application guard, not an operating-system firewall.

Only app.py opts in. Importing this module never changes another Python process.
AF_UNIX remains available for Qt/X11/IPC. Native third-party executables do not
run Python audit hooks; external document references are separately rejected.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import socket
import sys
import threading


class OfflineAccessError(PermissionError):
    """A fixed, content-free error suitable for beginner-facing messages."""


_installed = False
_lock = threading.Lock()
_listeners = []
MESSAGE = '離線模式不允許網路連線、網路資料夾或遠端檔案；請改用本機檔案。'


def _blocked():
    for callback in tuple(_listeners):
        try:
            callback()
        except Exception:
            pass
    raise OfflineAccessError(MESSAGE)


def assert_local_path(value):
    """Reject UNC and URI paths before resolve/stat/open can contact a host."""
    if isinstance(value, (str, bytes, os.PathLike)):
        text = os.fsdecode(value)
        if text.startswith(('\\\\', '//')) or (
            re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', text)
            and not re.match(r'^[A-Za-z]:[\\/]', text)
        ):
            _blocked()
    return value


def assert_local_document(path):
    """Reject remote SVG resources before Qt or the converter sees the file.

    Namespace identifiers and literal displayed URLs remain legal; only resource
    attributes, CSS imports/urls and external DTDs are inspected. Local resources
    and data: image payloads remain available. This does not parse AI internals.
    """
    assert_local_path(path)
    p = Path(path)
    if p.suffix.lower() != '.svg':
        return
    raw = p.read_bytes()
    if len(raw) > 200_000_000:
        raise ValueError('SVG 超過本版支援預算')
    text = raw.decode('utf-8-sig', errors='replace')
    refs = re.findall(r'(?:\bhref|\bsrc)\s*=\s*[\"\']([^\"\']+)', text, re.I)
    refs += re.findall(r'url\(\s*[\"\']?([^\)\"\']+)', text, re.I)
    refs += re.findall(r'@import\s+[\"\']([^\"\']+)', text, re.I)
    refs += re.findall(r'\b(?:SYSTEM|PUBLIC)\s+[\"\']([^\"\']+)', text, re.I)
    for ref in refs:
        ref = ref.strip()
        if ref.startswith(('#', 'data:')):
            continue
        assert_local_path(ref)


def enable_offline_guard(callback=None):
    """Install a permanent, idempotent Python-process audit guard at startup."""
    global _installed
    if callback is not None and callback not in _listeners:
        _listeners.append(callback)
    with _lock:
        if _installed:
            return

        def audit(event, args):
            if event in ('socket.getaddrinfo', 'socket.gethostbyname', 'socket.gethostbyaddr'):
                _blocked()
            if event == 'socket.__new__' and len(args) >= 2:
                if args[1] in (socket.AF_INET, socket.AF_INET6):
                    _blocked()
            if event in ('socket.connect', 'socket.bind', 'socket.sendto') and args:
                if getattr(args[0], 'family', None) in (socket.AF_INET, socket.AF_INET6):
                    _blocked()
            if event == 'open' and args:
                assert_local_path(args[0])
            if event in ('os.listdir', 'os.scandir', 'os.chdir') and args:
                assert_local_path(args[0])
            if event == 'subprocess.Popen' and len(args) >= 3:
                assert_local_path(args[0])
                if args[2] is not None:
                    assert_local_path(args[2])
                arguments = args[1]
                if isinstance(arguments, (list, tuple)):
                    for argument in arguments:
                        # CLI switches are not filenames; resource URLs never
                        # need to be supplied to Template AI's local tools.
                        if isinstance(argument, (str, bytes, os.PathLike)):
                            assert_local_path(argument)

        sys.addaudithook(audit)
        _installed = True


def offline_guard_enabled():
    return _installed

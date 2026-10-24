"""Restore only redirected output for a Windows GUI worker, without a console.

``pythonw`` and PyInstaller's windowed bootloader can set ``sys.stdout`` to
``None`` even when QProcess supplied a valid output pipe.  The worker's JSON
protocol must use that pipe; allocating or attaching a console would recreate
the user-visible window whose Close button terminates the application.
"""
from __future__ import annotations

import os
import sys


WORKER_STDOUT_UNAVAILABLE = 74


class _WindowsHandles:
    """Own only duplicates, never a standard handle belonging to our parent."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        import msvcrt

        self.ctypes = ctypes
        self.wintypes = wintypes
        self.msvcrt = msvcrt
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.GetStdHandle.argtypes = [wintypes.DWORD]
        self.kernel.GetStdHandle.restype = wintypes.HANDLE
        self.kernel.GetFileType.argtypes = [wintypes.HANDLE]
        self.kernel.GetFileType.restype = wintypes.DWORD
        self.kernel.GetCurrentProcess.argtypes = []
        self.kernel.GetCurrentProcess.restype = wintypes.HANDLE
        self.kernel.DuplicateHandle.argtypes = [
            wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE,
            ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD, wintypes.BOOL,
            wintypes.DWORD,
        ]
        self.kernel.DuplicateHandle.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.invalid_handle = ctypes.c_void_p(-1).value

    def standard(self, identity):
        return self.kernel.GetStdHandle(identity)

    def file_type(self, handle):
        return self.kernel.GetFileType(handle)

    def duplicate(self, handle):
        current = self.kernel.GetCurrentProcess()
        duplicate = self.wintypes.HANDLE()
        if not self.kernel.DuplicateHandle(current, handle, current,
                self.ctypes.byref(duplicate), 0, False, 2):  # DUPLICATE_SAME_ACCESS
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        return duplicate.value

    def file_descriptor(self, handle):
        return self.msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)

    def close_handle(self, handle):
        self.kernel.CloseHandle(handle)


def _open_redirected_stream(identity, handles):
    """Accept a parent-owned pipe/file, rejecting invalid/console handles."""
    handle = handles.standard(identity)
    if handle in (None, 0, -1, handles.invalid_handle):
        return None
    if handles.file_type(handle) not in (1, 3):  # FILE_TYPE_DISK, FILE_TYPE_PIPE
        return None
    duplicate = handles.duplicate(handle)
    try:
        descriptor = handles.file_descriptor(duplicate)
    except (OSError, ValueError):
        handles.close_handle(duplicate)
        return None
    # open_osfhandle transferred ownership to the CRT descriptor.  Only close
    # that descriptor from this point on; closing both would double-close it.
    try:
        return os.fdopen(descriptor, 'w', buffering=1, encoding='utf-8',
                         errors='replace', newline='\n', closefd=True)
    except (OSError, ValueError):
        try:
            os.close(descriptor)
        except OSError:
            pass
        return None


def prepare_standard_streams(*, redirected=False):
    """Return whether stdout works; normal GUI startup never requires it.

    Only explicitly selected worker/acceptance modes restore missing streams.
    This function does not attach to a terminal, allocate a console, create a
    log containing private output, or replace an already functioning stream.
    """
    if redirected and os.name == 'nt':
        handles = None
        for name, identity in (('stdout', -11), ('stderr', -12)):
            if getattr(sys, name, None) is not None:
                continue
            try:
                if handles is None:
                    handles = _WindowsHandles()
                stream = _open_redirected_stream(identity, handles)
                if stream is not None:
                    setattr(sys, name, stream)
            except (ImportError, AttributeError, OSError, ValueError):
                # The caller rejects a worker without stdout immediately.
                # A normal GUI has its own visible startup error mechanism.
                continue
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8', errors='replace')
            except (OSError, ValueError):
                pass
    if sys.stdout is None or getattr(sys.stdout, 'closed', False):
        return False
    try:
        sys.stdout.flush()
    except (OSError, ValueError):
        return False
    return True

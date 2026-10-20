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
import html
import xml.etree.ElementTree as ET
import base64
import binascii
from urllib.parse import unquote, unquote_to_bytes


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


def assert_local_document(path, *, require_svg=False):
    """Reject remote SVG resources before Qt or the converter sees the file.

    Namespace identifiers and literal displayed URLs remain legal; only resource
    attributes, CSS imports/urls and external DTDs are inspected. Local resources
    and data: image payloads remain available. This does not parse AI internals.
    """
    assert_local_path(path)
    p = Path(path)
    if p.suffix.lower() != '.svg' and not require_svg:
        return
    if p.stat().st_size > 200_000_000:
        raise ValueError('SVG 超過本版支援預算')
    raw = p.read_bytes()
    if len(raw) > 200_000_000:
        raise ValueError('SVG 超過本版支援預算')
    encoding = 'utf-32' if raw.startswith((b'\xff\xfe\x00\x00', b'\x00\x00\xfe\xff')) else 'utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
    text = raw.decode(encoding, errors='replace')
    if re.search(r'<\?xml-stylesheet\b|@import\b', text, re.I):
        raise OfflineAccessError('離線 SVG 不載入外部樣式；請將樣式內嵌後再匯入。')
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        raise ValueError('SVG 結構無法核對；尚未交給轉換器') from error
    refs = [v for node in root.iter() for k, v in node.attrib.items() if k.rsplit('}', 1)[-1].lower() in ('href', 'src')]
    css_refs = re.findall(r'url\(\s*[\"\']?([^\)\"\']+)', text, re.I)
    css_refs += re.findall(r'@import\s+[\"\']([^\"\']+)', text, re.I)
    for ref in css_refs:
        # Ambiguous CSS escapes cannot establish a local resource. They must be
        # expanded/embed locally before entering the offline converter.
        if '\\' in ref:
            _blocked()
    refs += css_refs
    refs += re.findall(r'\b(?:SYSTEM|PUBLIC)\s+[\"\']([^\"\']+)', text, re.I)
    for declaration in re.findall(r'<!DOCTYPE.*?>|<!ENTITY.*?>', text, re.I | re.S):
        if re.search(r'\b(?:SYSTEM|PUBLIC)\b', declaration, re.I):
            refs += re.findall(r'[\"\']([^\"\']+)[\"\']', declaration)
    for ref in refs:
        ref = html.unescape(ref).strip()
        if ref.startswith('#'):
            continue
        if ref.startswith('data:'):
            if not re.match(r'^data:image/(?:png|jpeg|jpg|webp|gif|bmp)(?:;|,)', ref, re.I):
                _blocked()
            header, separator, payload = ref.partition(',')
            if not separator:
                raise ValueError('SVG 內嵌圖片資料不完整')
            try:
                body = base64.b64decode(re.sub(r'\s+', '', payload), validate=True) if ';base64' in header.lower() else unquote_to_bytes(payload)
            except (ValueError, binascii.Error) as error:
                raise ValueError('SVG 內嵌圖片編碼無法核對') from error
            if not _raster_signature(body[:16]):
                raise OfflineAccessError('SVG 內嵌資源不是已核對的點陣圖片；不載入巢狀向量或外部文件。')
            continue
        assert_local_path(ref)
        # Preserve ordinary local raster/font resources, but do not hand native
        # converters an uninspected SVG/CSS/document dependency which could in
        # turn resolve remote resources. Extensions alone are not sufficient:
        # a .png containing SVG must not bypass this boundary.
        local = unquote(ref.split('#', 1)[0])
        assert_local_path(local)
        dependency = Path(local)
        if not dependency.is_absolute():
            dependency = p.parent / dependency
        if dependency.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tif', '.tiff', '.ttf', '.otf', '.woff', '.woff2'):
            raise OfflineAccessError('離線 SVG 含尚未核對的外部子資源；請先內嵌圖片、向量與樣式。')
        if not dependency.is_file() or dependency.stat().st_size > 200_000_000:
            raise ValueError('SVG 的本機資源不存在或超過預算；請內嵌後再匯入。')
        with dependency.open('rb') as stream:
            signature = stream.read(16)
        raster = _raster_signature(signature)
        font = signature.startswith((b'\x00\x01\x00\x00', b'OTTO', b'wOFF', b'wOF2'))
        if not (raster or font):
            raise OfflineAccessError('SVG 外部資源不是已核對的本機圖片或字型；請先內嵌後再匯入。')


def _raster_signature(signature):
    return (signature.startswith((b'\x89PNG\r\n\x1a\n', b'\xff\xd8\xff', b'GIF87a', b'GIF89a', b'BM', b'II*\x00', b'MM\x00*'))
            or signature.startswith(b'RIFF') and signature[8:12] == b'WEBP')


def assert_local_raster(path):
    """Prevent native image auto-detection from treating disguised SVG as raster."""
    assert_local_path(path)
    with Path(path).open('rb') as stream:
        if not _raster_signature(stream.read(16)):
            raise ValueError('圖片不是已核對的本機點陣格式，請使用 PNG／JPG 等圖片。')


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

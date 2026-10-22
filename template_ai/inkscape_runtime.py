"""Versioned bundled engine selection; frozen applications never search the host."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import threading

VERSION = '1.4.2'
_VERIFIED = {}
_LOCK = threading.RLock()


def file_sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            result.update(block)
    return result.hexdigest()


def _read_json(path, maximum=8*1024*1024):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError('內附 Inkscape 的版本資料缺少或不合法，請重新完整解壓下載包')
    return json.loads(path.read_text(encoding='utf-8'))


def bundled_runtime():
    app = Path(sys.executable).resolve().parent
    root = app/'engines/inkscape'
    try:
        root.resolve(strict=True).relative_to(app)
        manifest_path = root/'manifest.json'
        manifest = _read_json(manifest_path)
        info_root = Path(getattr(sys, '_MEIPASS', app))
        release = _read_json(info_root/'release-info.json', 65536)
        pin = release.get('inkscape_runtime', {})
        manifest_sha = file_sha(manifest_path)
        if (manifest.get('schema_version') != 1 or manifest.get('kind') != 'BUNDLED_INKSCAPE_RUNTIME'
                or manifest.get('version') != VERSION or pin.get('version') != VERSION
                or pin.get('manifest_sha256') != manifest_sha
                or manifest.get('executable') != 'bin/inkscape.exe'):
            raise ValueError('內附 Inkscape 的版本或檔案清單與本程式不一致')
        rows = manifest.get('files')
        if not isinstance(rows, list) or not rows or len(rows) > 20000:
            raise ValueError('內附 Inkscape 的檔案清單不完整')
        paths, stamps, names, parents = [], [], set(), set()
        for row in rows:
            name = row['path']
            relative = PurePosixPath(name)
            if (not name or '\\' in name or ':' in name or relative.is_absolute()
                    or '..' in relative.parts or relative.as_posix() != name
                    or name.casefold() in names or name == 'manifest.json'):
                raise ValueError('內附 Inkscape 含不安全或重複的檔案路徑')
            names.add(name.casefold())
            path = root.joinpath(*relative.parts)
            st = path.lstat()
            if not stat.S_ISREG(st.st_mode) or st.st_size != row['bytes']:
                raise ValueError('內附 Inkscape 的檔案缺少或被變更：'+name)
            paths.append((path,row))
            stamps.append((name,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_ino))
            parents.add(path.parent)
        if 'bin/inkscape.exe' not in names:
            raise ValueError('內附 Inkscape 的執行檔未列入驗證')
        for parent in sorted(parents):
            st = parent.stat()
            stamps.append((str(parent.relative_to(root)),st.st_mtime_ns,st.st_ctime_ns,st.st_ino))
        key = (str(root),manifest_sha,tuple(stamps))
        with _LOCK:
            if key not in _VERIFIED:
                actual = {p.relative_to(root).as_posix().casefold() for p in root.rglob('*') if p.is_file()}
                if actual != names | {'manifest.json'}:
                    raise ValueError('內附 Inkscape 的實際檔案清單已變更')
                resolved_root = root.resolve(strict=True)
                for parent in parents:
                    parent.resolve(strict=True).relative_to(resolved_root)
                for path,row in paths:
                    if file_sha(path) != row['sha256']:
                        raise ValueError('內附 Inkscape 的檔案校驗失敗：'+row['path'])
                _VERIFIED.clear()
                _VERIFIED[key] = True
        executable = root/'bin/inkscape.exe'
        return dict(policy='BUNDLED_ONLY', executable=str(executable.resolve()), version=VERSION,
                    executable_sha256=next(r['sha256'] for r in rows if r['path']=='bin/inkscape.exe'),
                    runtime_manifest_sha256=manifest_sha, verified_files=len(rows))
    except (OSError, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('內附 Inkscape 不完整或無法讀取，請重新完整解壓下載包') from error


def inkscape_path():
    if getattr(sys, 'frozen', False):
        return bundled_runtime()['executable']
    options = [os.environ.get('TEMPLATE_AI_INKSCAPE',''), shutil.which('inkscape') or '',
               r'C:\Program Files\Inkscape\bin\inkscape.exe', r'C:\Program Files\Inkscape\inkscape.exe']
    return next((p for p in options if p and Path(p).is_file()), None)


def runtime_identity(executable):
    if not executable:
        from PySide6.QtCore import qVersion
        return dict(policy='BUILTIN_QT_FALLBACK', qt_version=qVersion())
    if getattr(sys, 'frozen', False):
        result = bundled_runtime()
        if Path(executable).resolve() != Path(result['executable']):
            raise ValueError('內附 Inkscape 路徑不一致，拒絕改用系統工具')
        return result
    from .source_recovery import converter_version
    return dict(policy='SOURCE_EXTERNAL', executable=str(Path(executable).resolve()),
                version=converter_version(executable), executable_sha256=file_sha(executable))

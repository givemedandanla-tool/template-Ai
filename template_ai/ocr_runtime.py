"""Local OCR selection; a packaged application never searches the host.

The Windows runtime is pinned by the release's embedded manifest digest. The
language files keep the existing official tessdata_fast Git-blob pins. Source
development may explicitly select a staged bundle; that switch is ignored by
frozen applications and does not weaken the distributed package's policy.
"""
from __future__ import annotations

import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile

VERSION = '5.4.0.20240606'
MODEL_COMMIT = '65727574dfcd264acbb0c3e07860e4e9e9b22185'
# Same official objects as tools/install_ocr_models.py; no runtime downloader.
MODEL_BLOBS = {
    'chi_tra.traineddata': '1955cd8b8d076b898616e9c2c1ace65b43105356',
    'eng.traineddata': 'bbef4675053b5b468cdb477053e28b1c698ba08e',
    'LICENSE': 'd645695673349e3947e8e5ae42332d0ac3164cd7',
}


class OcrRuntimeError(ValueError):
    def __init__(self, code, message, origin='BUNDLED'):
        super().__init__(message)
        self.code, self.origin = code, origin


class OcrProcessingError(ValueError):
    """A controlled failure code; raw CLI stderr never enters private reports."""
    def __init__(self, code, message):
        self.code = code
        super().__init__('[' + code + '] ' + message)


def processing_error(stderr):
    value = stderr.lower()
    if any(marker in value for marker in ('error opening data file', 'failed loading language',
                                          "couldn't load any languages", 'failed to init api')):
        return OcrProcessingError('OCR_MODEL_INITIALIZATION_FAILED',
            '文字辨識無法載入固定語言資料；原稿仍保留，可人工標記並匯出問題報告。')
    if any(marker in value for marker in ('cannot read input file', 'error in pixread', 'image file cannot')):
        return OcrProcessingError('OCR_IMAGE_INPUT_FAILED',
            '文字辨識無法讀取這份預覽；原稿仍保留，可人工標記並匯出問題報告。')
    return OcrProcessingError('OCR_PROCESS_FAILED',
        '文字辨識未完成；原稿仍保留，可人工標記並匯出問題報告。')


def uses_model_stage():
    return sys.platform == 'win32'


def _short_model_path(path):
    value = str(path)
    if sys.platform == 'win32':
        import ctypes
        buffer = ctypes.create_unicode_buffer(32768)
        short_path = ctypes.windll.kernel32.GetShortPathNameW
        short_path.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        short_path.restype = ctypes.c_uint32
        length = short_path(value, buffer, len(buffer))
        if 0 < length < len(buffer):
            value = buffer.value
        if not value.isascii() or len(value) >= 240:
            raise ValueError('No short local model directory is available')
    return value


@contextmanager
def model_directory(data_dir, *, require_fixed=False):
    """Stage selected model bytes for Windows CRT interoperability.

    Packaged/staged bundles require the fixed official weights. Source-only
    custom models keep their exact selected bytes instead of changing models.
    No work image, text, customer data or new weights enter this directory.
    Callers must keep this context open until the owned child has stopped.
    Source-mode engines using their default system directory remain supported.
    """
    if not data_dir or not uses_model_stage():
        yield data_dir
        return
    temporary = None
    try:
        source_root = Path(data_dir)
        from .offline_runtime import assert_local_path
        assert_local_path(source_root)
        temporary = tempfile.TemporaryDirectory(prefix='ta-ocr-')
        stage = Path(temporary.name)
        assert_local_path(stage)
        present = 0
        for language in ('eng', 'chi_tra'):
            name = language + '.traineddata'
            source = source_root / name
            if not source.exists():
                continue
            if source.is_symlink() or not source.is_file() or source.stat().st_size > 20_000_000:
                raise ValueError('Model file is not a bounded regular file')
            raw = source.read_bytes()
            blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            if require_fixed and blob != MODEL_BLOBS[name]:
                raise ValueError('Model differs from the fixed public weights')
            target = stage / name
            with target.open('xb') as output:
                output.write(raw)
            if _sha(target) != hashlib.sha256(raw).hexdigest():
                raise ValueError('Staged model bytes changed')
            present += 1
        if not present:
            raise ValueError('No fixed language model is available')
        directory = _short_model_path(stage)
    except (OSError, ValueError, KeyError) as error:
        if temporary is not None:
            temporary.cleanup()
        raise OcrProcessingError('OCR_MODEL_STAGE_UNAVAILABLE',
            '固定文字辨識資料尚未準備成功；原稿仍保留，可人工標記並匯出問題報告。') from error
    try:
        yield directory
    finally:
        temporary.cleanup()


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            digest.update(block)
    return digest.hexdigest()


def _json(path, maximum=8_388_608):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError('版本記錄缺少或不合法')
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError('版本記錄不是物件')
    return value


def _models(root):
    """Verify exact official models, never silently use installed languages."""
    if root.is_symlink() or not root.is_dir():
        raise ValueError('內附語言資料夾缺少')
    identities = {}
    for name, expected in MODEL_BLOBS.items():
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 20_000_000:
            raise ValueError('內附語言檔案缺少或不合法')
        raw = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if blob != expected:
            raise ValueError('內附語言資料與固定官方版本不符')
        identities[name] = hashlib.sha256(raw).hexdigest()
    return identities


def _validate_bundle(root, model_root, pin):
    if root.is_symlink() or not root.is_dir():
        raise ValueError('內附執行器資料夾缺少')
    manifest_path = root / 'BUNDLED_RUNTIME.json'
    manifest = _json(manifest_path)
    manifest_sha = _sha(manifest_path)
    if (not isinstance(pin, dict) or manifest.get('schema_version') != 1
            or manifest.get('kind') != 'BUNDLED_TESSERACT_RUNTIME'
            or manifest.get('version') != VERSION or pin.get('version') != VERSION
            or pin.get('manifest_sha256') != manifest_sha
            or manifest.get('executable') != 'tesseract.exe'):
        raise ValueError('內附執行器版本與本程式不一致')
    rows = manifest.get('files')
    if not isinstance(rows, list) or not rows or len(rows) > 4096:
        raise ValueError('內附執行器清單不完整')
    names, executable_sha = set(), None
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get('path'), str)
                or not isinstance(row.get('bytes'), int) or isinstance(row['bytes'], bool)
                or row['bytes'] < 0 or not isinstance(row.get('sha256'), str)
                or not re.fullmatch('[0-9a-f]{64}', row['sha256'])):
            raise ValueError('內附執行器清單格式不正確')
        name = row['path']
        relative = PurePosixPath(name)
        if (not name or '\\' in name or ':' in name or relative.is_absolute()
                or '..' in relative.parts or relative.as_posix() != name
                or name.casefold() in names or name.casefold() == 'bundled_runtime.json'):
            raise ValueError('內附執行器含不合法檔案位置')
        names.add(name.casefold())
        path = root.joinpath(*relative.parts)
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size != row['bytes'] or _sha(path) != row['sha256']:
            raise ValueError('內附執行器檔案校驗失敗')
        if name == 'tesseract.exe':
            executable_sha = row['sha256']
    if executable_sha is None or pin.get('executable_sha256') != executable_sha:
        raise ValueError('內附執行檔未與本程式綁定')
    actual = set()
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('內附執行器不能含符號連結')
        if path.is_file():
            actual.add(path.relative_to(root).as_posix().casefold())
    if actual != names | {'bundled_runtime.json'}:
        raise ValueError('內附執行器實際清單已變更')
    models = _models(model_root)
    return dict(policy='BUNDLED_ONLY', origin='BUNDLED',
                executable=str((root / 'tesseract.exe').resolve()), data_dir=str(model_root.resolve()),
                version=VERSION, executable_sha256=executable_sha,
                runtime_manifest_sha256=manifest_sha, verified_files=len(rows),
                model_commit=MODEL_COMMIT, model_sha256=models)


def bundled_runtime():
    """Select the immutable package, or an explicitly pinned source fixture."""
    try:
        from .offline_runtime import assert_local_path
        if getattr(sys, 'frozen', False):
            app = Path(sys.executable).resolve().parent
            assert_local_path(app)
            root = app / 'engines/tesseract'
            models = app / 'engines/ocr-models'
            root.resolve(strict=True).relative_to(app)
            models.resolve(strict=True).relative_to(app)
            release = _json(Path(getattr(sys, '_MEIPASS', app)) / 'release-info.json', 65536)
            pin = release.get('tesseract_runtime')
        else:
            root = Path(os.environ['TEMPLATE_AI_BUNDLED_TESSERACT_ROOT'])
            models = Path(os.environ['TEMPLATE_AI_TESSDATA'])
            pin_path = Path(os.environ['TEMPLATE_AI_BUNDLED_TESSERACT_PIN'])
            for path in (root, models, pin_path):
                assert_local_path(path)
            pin = _json(pin_path, 65536)
        return _validate_bundle(root, models, pin)
    except (OSError, KeyError, TypeError, ValueError, UnicodeError) as error:
        raise OcrRuntimeError('BUNDLED_OCR_RUNTIME_INVALID',
            '內附文字辨識配套缺少、已變更或無法驗證。請重新完整解壓下載包；'
            '不會改用電腦上的其他版本，仍可在原稿上人工標記。') from error


def resolve_runtime():
    if getattr(sys, 'frozen', False) or os.environ.get('TEMPLATE_AI_BUNDLED_TESSERACT_ROOT'):
        return bundled_runtime()
    explicit = os.environ.get('TEMPLATE_AI_TESSERACT')
    executable = explicit or shutil.which('tesseract')
    origin = 'ENV_LOCAL' if explicit else 'SYSTEM_PATH'
    if not executable:
        raise OcrRuntimeError('LOCAL_OCR_UNAVAILABLE',
                              '本機文字辨識執行器不可用；原向量與人工核對路徑仍可使用。', origin)
    from .offline_runtime import assert_local_path
    assert_local_path(executable)
    if not Path(executable).is_file():
        raise OcrRuntimeError('LOCAL_OCR_UNAVAILABLE',
                              '本機文字辨識執行器不可用；原向量與人工核對路徑仍可使用。', origin)
    configured = os.environ.get('TEMPLATE_AI_TESSDATA')
    local = Path(__file__).resolve().parents[1] / 'local-data/tessdata'
    data = Path(configured) if configured else local if local.is_dir() else None
    if data is not None:
        assert_local_path(data)
    return dict(policy='SOURCE_LOCAL', origin=origin, executable=str(Path(executable).resolve()),
                data_dir=str(data.resolve()) if data else None)


def runtime_report(context=None, *, error=None):
    """Safe metadata only: never expose executable, model or customer paths."""
    if error is not None:
        return dict(state='UNAVAILABLE', origin=getattr(error, 'origin', 'UNKNOWN'),
                    policy='BUNDLED_ONLY' if getattr(error, 'origin', None) == 'BUNDLED' else 'SOURCE_LOCAL',
                    error_code=getattr(error, 'code', 'OCR_RUNTIME_UNAVAILABLE'))
    context = context or {}
    allowed = ('origin', 'policy', 'version', 'executable_sha256', 'runtime_manifest_sha256',
               'verified_files', 'model_commit', 'model_sha256')
    return dict(state='READY', **{key: context[key] for key in allowed if key in context})

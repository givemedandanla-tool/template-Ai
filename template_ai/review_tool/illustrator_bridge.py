"""Optional Windows Illustrator -> local PDF-copy adapter; never auto-enabled.

The Adobe COM/JSX boundary requires installed-Illustrator qualification. Synthetic
host tests are not a fidelity guarantee. All paths, copies and provenance stay local.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import uuid

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

MESSAGES = {
    'MISSING_BRIDGE': '尚未安裝 Illustrator 接口的選配 Windows COM 套件。請依部件指南安裝後重試。',
    'NOT_INSTALLED': '這台 Windows 電腦未註冊 Illustrator 接口。請在已安裝並可正常啟動 Illustrator 的電腦使用。',
    'INVALID_SOURCE': '請選擇仍在本機的 AI 原檔。',
    'OUTPUT_EXISTS': '副本位置已存在檔案，未覆寫。請重新執行以使用新位置。',
    'SOURCE_OPEN': '原檔已在 Illustrator 開啟。請先自行保存並關閉該文件，再重試；既有文件未修改。',
    'ALERTS_DISABLED': 'Illustrator 目前隱藏警告。請正常重新啟動 Illustrator 後重試，避免漏掉缺字型或連結提示。',
    'PAGE_LIMIT': '畫板數超過此接口目前支援的 1–100 頁範圍。',
    'CLOSE_FAILED': 'Illustrator 未能關閉本次文件。請切換到 Illustrator 檢查；本次副本未加入。',
    'EXPORT_FAILED': 'Illustrator 未完成轉換。請切換到 Illustrator 檢查提示、字型或連結，再重試。',
    'HOST_FAILED': '無法呼叫 Illustrator。請確認 Illustrator 能正常啟動，並已安裝接口的選配 COM 套件。',
    'CANCELLED': '已停止等候；本次副本不會加入。Illustrator 可能仍在處理，請自行檢查其視窗。',
    'TIMEOUT': '等候 Illustrator 已逾時；本次副本不會加入。請檢查 Illustrator 的提示視窗，再重試。',
    'SOURCE_CHANGED': '轉換期間原檔內容有變動，本次副本未加入。請確認原檔後重試。',
    'INVALID_PDF': '產生的副本未通過 PDF 頁數或內容檢查，尚未加入作品。',
    'PLACEHOLDER': '產生的副本仍包含 Illustrator PDF 相容提示頁，尚未加入作品。',
    'LOCAL_IO': '本機接口資料無法建立或讀取，請確認權限與儲存空間，並使用較短的本機保存路徑。',
}


class BridgeError(ValueError):
    def __init__(self, code):
        self.code = code if code in MESSAGES else 'EXPORT_FAILED'
        super().__init__(MESSAGES[self.code])


def available():
    """Registry-only capability check. Does not start or attach to Illustrator."""
    if os.name != 'nt':
        return False
    from .illustrator_host import registered_clsid
    return registered_clsid() is not None


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def local_path(path):
    from ..offline_runtime import assert_local_path
    assert_local_path(path)
    value = Path(os.path.abspath(path))
    if os.name == 'nt':
        import ctypes
        # Reject UNC and mapped network drives, even if the input used a drive letter.
        if not re.match(r'^[A-Za-z]:\\', str(value)) or ctypes.windll.kernel32.GetDriveTypeW(value.anchor) == 4:
            raise BridgeError('LOCAL_IO')
        if len(str(value)) > 220:
            raise BridgeError('LOCAL_IO')
    resolved = value.resolve()
    assert_local_path(resolved)
    if os.name == 'nt' and (not re.match(r'^[A-Za-z]:\\', str(resolved))
                              or ctypes.windll.kernel32.GetDriveTypeW(resolved.anchor) == 4
                              or len(str(resolved)) > 220):
        raise BridgeError('LOCAL_IO')
    return resolved


def prepare(source, root):
    source = local_path(source)
    if source.suffix.casefold() != '.ai' or not source.is_file() or not 0 < source.stat().st_size <= 200_000_000:
        raise BridgeError('INVALID_SOURCE')
    root = local_path(root)
    root.mkdir(parents=True, exist_ok=True)
    job = root / uuid.uuid4().hex[:16]
    local_path(job / 'compatible.pdf')
    job.mkdir(exist_ok=False)
    request = dict(source=str(source), output=str(job / 'compatible.pdf'), cancel=str(job / 'cancel'))
    info = dict(schema_version=1, source_sha256=digest(source), request=request,
                state='PREPARED', visual_fidelity='NOT_VERIFIED', original_unchanged=None)
    (job / 'provenance.local.json').write_text(json.dumps(info, ensure_ascii=True, indent=2), encoding='utf-8')
    template = Path(__file__).with_name('illustrator_export.jsx').read_text(encoding='utf-8')
    # JSON-escaped ASCII literals, no shell interpolation or executable source text from filenames.
    (job / 'run.jsx').write_text(template + '\nreviewExport(' + json.dumps(request, ensure_ascii=True) + ');\n', encoding='utf-8')
    return job, info


def validate_result(job, info, response):
    request = info['request']
    if (job / 'cancel').exists():
        raise BridgeError('CANCELLED')
    if digest(request['source']) != info['source_sha256']:
        raise BridgeError('SOURCE_CHANGED')
    match = re.fullmatch(r'OK\|([1-9][0-9]{0,2})', response.strip())
    if not match:
        raise BridgeError(response.strip())
    expected = int(match[1])
    output = Path(request['output'])
    if output != job / 'compatible.pdf' or output.is_symlink() or not output.is_file() or not 0 < output.stat().st_size <= 200_000_000:
        raise BridgeError('INVALID_PDF')
    from PySide6.QtPdf import QPdfDocument
    from .source_compatibility import MAX_VISIBLE_CHARACTERS, placeholder_language
    document = QPdfDocument()
    try:
        if document.load(str(output)) != QPdfDocument.Error.None_ or not 1 <= expected <= 100 or document.pageCount() != expected:
            raise BridgeError('INVALID_PDF')
        for page in range(expected):
            size = document.pagePointSize(page)
            if size.width() <= 0 or size.height() <= 0:
                raise BridgeError('INVALID_PDF')
            if placeholder_language(document.getSelectionAtIndex(page, 0, MAX_VISIBLE_CHARACTERS).text()):
                raise BridgeError('PLACEHOLDER')
    finally:
        document.close()
    info.update(state='PDF_VALIDATED', output_sha256=digest(output), page_count=expected, original_unchanged=True)
    (job / 'provenance.local.json').write_text(json.dumps(info, ensure_ascii=True, indent=2), encoding='utf-8')
    return output


class IllustratorBridge(QObject):
    ready = Signal(str, dict)
    failure = Signal(str)
    finished = Signal()
    TIMEOUT_MS = 600_000

    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = Path(root)
        self.process = None
        self.job = self.info = None
        self._stdout = bytearray()
        self._stopping = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self.stop('TIMEOUT'))

    def is_running(self):
        return self.process is not None

    def start(self, source):
        if self.is_running():
            raise BridgeError('HOST_FAILED')
        if not available():
            raise BridgeError('NOT_INSTALLED')
        try:
            self.job, self.info = prepare(source, self.root)
        except BridgeError:
            raise
        except (OSError, ValueError):
            raise BridgeError('LOCAL_IO') from None
        self._stdout.clear()
        self._stopping = None
        process = QProcess(self)
        self.process = process
        process.readyReadStandardOutput.connect(self._read)
        process.readyReadStandardError.connect(lambda: process.readAllStandardError())
        process.errorOccurred.connect(self._error)
        process.finished.connect(self._done)
        # QProcess uses a hidden console by default on Windows. No interactive terminal.
        executable = Path(sys.executable)
        if executable.name.casefold() == 'pythonw.exe':
            executable = executable.with_name('python.exe')
        process.setProgram(str(executable))
        process.setArguments(['-I', str(Path(__file__).with_name('illustrator_host.py')), str(self.job / 'run.jsx')])
        self.timer.start(self.TIMEOUT_MS)
        process.start()

    def _read(self):
        if self.process is not None:
            self._stdout.extend(bytes(self.process.readAllStandardOutput()))
            if len(self._stdout) > 1024:
                self.stop('HOST_FAILED')

    def _error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self._stopping = 'HOST_FAILED'
            self._done(-1)

    def stop(self, code='CANCELLED'):
        if self.process is not None:
            self._stopping = code
            try:
                (self.job / 'cancel').touch(exist_ok=True)
            except OSError:
                pass
            # Kill this helper only. COM server may continue; its late result is never adopted.
            self.process.kill()

    def _done(self, exit_code=0, _status=None):
        if self.process is None:
            return
        self.timer.stop()
        self._read()
        process, self.process = self.process, None
        process.deleteLater()
        try:
            if self._stopping:
                raise BridgeError(self._stopping)
            if exit_code:
                code = self._stdout.decode('ascii', errors='replace').strip()
                raise BridgeError(code if code in MESSAGES else 'HOST_FAILED')
            output = validate_result(self.job, self.info, self._stdout.decode('ascii', errors='replace'))
            self.ready.emit(str(output), dict(self.info))
        except BridgeError as error:
            self.failure.emit(str(error))
        except (OSError, ValueError, RuntimeError):
            self.failure.emit(MESSAGES['LOCAL_IO'])
        finally:
            self.finished.emit()

"""Bounded, owned local analysis subprocesses for the review workspace.

The main Qt thread only consumes JSON-line progress.  A real stage transition
starts that stage's budget; repeated messages do not extend it.  A partial
result is recovered only from an authenticated checkpoint inside this cache.
"""
from __future__ import annotations

from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
import uuid

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal


class AnalysisJobs(QObject):
    progress = Signal(str, dict)
    result = Signal(str, dict)
    failure = Signal(str, str)
    finished = Signal()

    STARTUP_TIMEOUT_SECONDS = 180
    TOTAL_TIMEOUT_SECONDS = 900
    MAX_STAGE_TIMEOUT_SECONDS = 600
    MAX_LINE_BYTES = 32 * 1024 * 1024
    MAX_STDOUT_BYTES = 64 * 1024 * 1024
    MAX_STDERR_BYTES = 64 * 1024

    def __init__(self, cache_dir, parent=None):
        super().__init__(parent)
        from ..offline_runtime import assert_local_path
        assert_local_path(cache_dir)
        self.cache_dir = Path(cache_dir).resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._request_dir = self.cache_dir / 'jobs'
        if self._request_dir.is_symlink():
            raise ValueError('本機工作資料夾不能是符號連結')
        self._request_dir.mkdir(exist_ok=True)
        self._queue = deque()
        self._active = None
        self._process = None
        self._session_active = False
        self._paused = False
        self._pause_requested = False
        self._stop_requested = False
        self._last_source_id = ''
        self._generation = 0
        self._ocr = True
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._check_deadlines)

    @property
    def paused(self):
        return self._paused

    @property
    def busy(self):
        return self._process is not None

    @property
    def running(self):
        return self._session_active

    def is_running(self):
        """True for an active queue, including a safely paused queue."""
        return self._session_active

    def start(self, sources, ocr=True):
        if self._session_active:
            raise RuntimeError('已有判讀工作，請先接續或停止目前工作')
        from ..offline_runtime import assert_local_path
        rows = []
        seen = set()
        for source in sources:
            if not isinstance(source, dict) or not isinstance(source.get('id'), str) or not source['id']:
                raise ValueError('判讀來源需要穩定識別碼')
            if not isinstance(source.get('path'), (str, Path)):
                raise ValueError('判讀來源需要本機檔案')
            assert_local_path(source['path'])
            if source['id'] in seen:
                continue
            seen.add(source['id'])
            rows.append({'id': source['id'], 'path': str(Path(source['path']).resolve())})
        self._queue = deque(rows)
        self._ocr = bool(ocr)
        self._paused = self._pause_requested = self._stop_requested = False
        self._session_active = True
        QTimer.singleShot(0, self._next)

    def pause(self):
        if not self._session_active or self._paused or self._pause_requested:
            return
        self._pause_requested = True
        self._emit_state('pausing', '正在暫停；目前檔案到安全邊界並保存後就會停止。')
        if not self.busy:
            self._next()

    def resume(self):
        if not self._session_active or not (self._paused or self._pause_requested):
            return
        self._paused = self._pause_requested = False
        self._emit_state('resumed', '已接續判讀，已完成結果保持不變。')
        if not self.busy:
            QTimer.singleShot(0, self._next)

    def stop(self):
        if not self._session_active or self._stop_requested:
            return
        self._stop_requested = True
        self._pause_requested = self._paused = False
        for source in self._queue:
            self.progress.emit(source['id'], {
                'stage': 'stopped', 'message': '尚未處理；可稍後重新開始判讀。',
            })
        self._queue.clear()
        if self.busy:
            self._abort('STOPPED', '判讀已停止，已保存的結果保持不變。', report_failure=False)
        else:
            self._emit_state('stopped', '判讀已停止，已保存的結果保持不變。')
            self._finish_session()

    def _emit_state(self, stage, message):
        identity = self._active['id'] if self._active else self._last_source_id
        self.progress.emit(identity, {'stage': stage, 'message': message})

    def _command(self, request_path):
        """Separate method keeps source/frozen invocation identical to release."""
        if getattr(sys, 'frozen', False):
            return sys.executable, ['--analysis-worker', str(request_path)]
        entry = Path(__file__).resolve().parents[2] / 'review_app.py'
        return sys.executable, [str(entry), '--analysis-worker', str(request_path)]

    def _next(self):
        if not self._session_active or self.busy:
            return
        if self._stop_requested or not self._queue:
            self._finish_session()
            return
        if self._pause_requested:
            self._paused = True
            self._emit_state('paused', '已暫停；目前已完成結果已交回保存，可按繼續判讀。')
            return
        self._active = self._queue.popleft()
        self._last_source_id = self._active['id']
        self._generation += 1
        generation = self._generation
        self._started_at = self._phase_started_at = time.monotonic()
        self._phase_key = ('worker_startup', None)
        self._phase_timeout = float(self.STARTUP_TIMEOUT_SECONDS)
        self._stdout = bytearray()
        self._stdout_total = 0
        self._stderr_tail = bytearray()
        self._full_result_received = False
        self._partial_emitted = False
        self._failure_message = None
        self._abort_code = None
        self._partial_checkpoint = None
        self._owned_process_identity = None
        request_path = self._request_dir / (uuid.uuid4().hex + '.request.json')
        self._stderr_path = request_path.with_suffix('.stderr.local.log')
        payload = json.dumps({
            'path': self._active['path'], 'cache_dir': str(self.cache_dir), 'ocr': self._ocr,
        }, ensure_ascii=False).encode('utf-8')
        try:
            if self._request_dir.is_symlink() or self._request_dir.resolve() != self.cache_dir/'jobs':
                raise OSError('invalid local request directory')
            with os.fdopen(os.open(request_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
                stream.write(payload)
        except OSError:
            identity = self._active['id']
            self._active = None
            self.failure.emit(identity, '尚未建立本機判讀工作；請確認保存位置可寫入及剩餘空間，再重試。')
            QTimer.singleShot(0, self._next)
            return
        process = QProcess(self)
        self._process = process
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert('QT_QPA_PLATFORM', 'offscreen')
        environment.insert('PYTHONUNBUFFERED', '1')
        environment.insert('PYTHONIOENCODING', 'utf-8')
        process.setProcessEnvironment(environment)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        process.setWorkingDirectory(str(Path(sys.executable).parent if getattr(sys, 'frozen', False)
                                        else Path(__file__).resolve().parents[2]))
        process.started.connect(lambda: self._started(process, generation))
        process.readyReadStandardOutput.connect(lambda: self._read_stdout(process, generation))
        process.readyReadStandardError.connect(lambda: self._read_stderr(process, generation))
        process.errorOccurred.connect(lambda error: self._process_error(process, generation, error))
        process.finished.connect(lambda code, state: self._process_finished(process, generation, code, state))
        self.progress.emit(self._active['id'], {
            'stage': 'worker_startup', 'message': '正在開啟本機判讀程序，原稿保持不變。',
            'phase_timeout': self.STARTUP_TIMEOUT_SECONDS,
        })
        self._timer.start()
        try:
            command, arguments = self._command(request_path)
            process.start(command, arguments)
        except Exception:
            self._failure_message = '尚未成功啟動本機判讀程序；請重試或匯出問題報告。'
            self._process_finished(process, generation, -1, QProcess.ExitStatus.CrashExit)

    def _current(self, process, generation):
        return self._process is process and self._generation == generation

    def _started(self, process, generation):
        if not self._current(process, generation):
            return
        import psutil
        try:
            pid = int(process.processId())
            self._owned_process_identity = (pid, psutil.Process(pid).create_time())
        except (psutil.Error, OSError):
            self._owned_process_identity = None
        if self._abort_code:
            self._terminate_owned_tree()

    def _read_stdout(self, process, generation, final=False):
        if not self._current(process, generation):
            return
        data = bytes(process.readAllStandardOutput())
        self._stdout_total += len(data)
        self._stdout.extend(data)
        if self._stdout_total > self.MAX_STDOUT_BYTES:
            self._abort('OUTPUT_LIMIT', '判讀回傳資料超出本版安全範圍；已完成頁仍可保留。')
            return
        while b'\n' in self._stdout:
            end = self._stdout.index(b'\n')
            if end > self.MAX_LINE_BYTES:
                self._abort('OUTPUT_LIMIT', '單次判讀結果超出本版安全範圍；可縮小檔案範圍後重試。')
                return
            line = bytes(self._stdout[:end]).strip()
            del self._stdout[:end+1]
            if line:
                self._consume(line)
            if self._abort_code:
                return
        if len(self._stdout) > self.MAX_LINE_BYTES:
            self._abort('OUTPUT_LIMIT', '單次判讀結果超出本版安全範圍；可縮小檔案範圍後重試。')
        elif final and self._stdout.strip():
            line = bytes(self._stdout).strip()
            self._stdout.clear()
            self._consume(line)

    def _consume(self, line):
        try:
            event = json.loads(line.decode('utf-8'))
            if not isinstance(event, dict):
                raise ValueError('not an event')
            kind = event.get('type')
            if kind == 'progress':
                stage = event.get('stage')
                if not isinstance(stage, str) or not stage or len(stage) > 80:
                    raise ValueError('invalid stage')
                key = (stage, event.get('page'))
                if key != self._phase_key:
                    limit = event.get('phase_timeout', self.STARTUP_TIMEOUT_SECONDS)
                    if not isinstance(limit, (int, float)) or isinstance(limit, bool) or not math.isfinite(limit):
                        raise ValueError('invalid timeout')
                    self._phase_key = key
                    self._phase_started_at = time.monotonic()
                    self._phase_timeout = min(float(self.MAX_STAGE_TIMEOUT_SECONDS), max(1.0, float(limit)))
                path, sha = event.get('checkpoint_path'), event.get('checkpoint_sha256')
                if isinstance(path, str) and isinstance(sha, str) and len(sha) == 64:
                    self._partial_checkpoint = (path, sha)
                self.progress.emit(self._active['id'], event)
            elif kind == 'result':
                result = event.get('result')
                if not isinstance(result, dict) or self._full_result_received:
                    raise ValueError('invalid or repeated result')
                self._full_result_received = True
                self.result.emit(self._active['id'], result)
            elif kind == 'error':
                from .source_compatibility import ISSUE_CODE, SAFE_MESSAGE
                # Only a known code selects fixed product wording. Never relay
                # arbitrary child messages, which may contain private artwork.
                self._failure_message = (SAFE_MESSAGE if event.get('code') == ISSUE_CODE else
                    '這個檔案尚未完成判讀；原稿保持不變，可重試或匯出問題報告。')
            else:
                raise ValueError('unknown event')
        except (ValueError, TypeError, UnicodeError, OverflowError):
            self._abort('PROTOCOL_ERROR', '判讀程序回傳了無法讀取的結果；已保留原稿與已完成頁。')

    def _read_stderr(self, process, generation):
        if not self._current(process, generation):
            return
        self._stderr_tail.extend(bytes(process.readAllStandardError()))
        if len(self._stderr_tail) > self.MAX_STDERR_BYTES:
            del self._stderr_tail[:-self.MAX_STDERR_BYTES]

    def _process_error(self, process, generation, error):
        if not self._current(process, generation):
            return
        if error == QProcess.ProcessError.FailedToStart:
            self._failure_message = '尚未成功啟動本機判讀程序；請重試或匯出問題報告。'
            self._process_finished(process, generation, -1, QProcess.ExitStatus.CrashExit)

    def _recover_partial(self):
        if self._full_result_received or self._partial_emitted or not self._partial_checkpoint:
            return
        try:
            raw_path, expected = self._partial_checkpoint
            path = Path(raw_path)
            resolved = path.resolve(strict=True)
            if path.is_symlink() or not resolved.is_relative_to(self.cache_dir) or not resolved.is_file():
                return
            if resolved.stat().st_size > self.MAX_LINE_BYTES:
                return
            raw = resolved.read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                return
            value = json.loads(raw.decode('utf-8'))
            if not isinstance(value, dict) or not isinstance(value.get('pages'), list) or not value['pages']:
                return
            if not isinstance(value.get('works'), list):
                return
            value['status'] = 'PARTIAL'
            value['recovered_after_interruption'] = True
            self._partial_emitted = True
            self.result.emit(self._active['id'], value)
        except (OSError, ValueError, UnicodeError, TypeError):
            # An unverifiable checkpoint is missing evidence, not a full result.
            return

    def _check_deadlines(self):
        if not self.busy or self._abort_code:
            return
        now = time.monotonic()
        if now-self._started_at > self.TOTAL_TIMEOUT_SECONDS:
            self._abort('TOTAL_TIMEOUT', '這個檔案已超過整體判讀時間；已成功保存的進度保持不變，可重試或先核對其他作品。')
        elif now-self._phase_started_at > self._phase_timeout:
            self._abort('STAGE_TIMEOUT', '目前判讀階段已超過處理時間；已成功保存的進度保持不變，可重試或匯出問題報告。')

    def _abort(self, code, message, report_failure=True):
        if not self.busy or self._abort_code:
            return
        self._abort_code = code
        if report_failure:
            self._failure_message = message
        self._emit_state('stopping' if code == 'STOPPED' else 'timeout' if 'TIMEOUT' in code else 'error', message)
        self._terminate_owned_tree()

    def _terminate_owned_tree(self):
        """Terminate only descendants of this live, identity-checked worker."""
        process = self._process
        if process is None:
            return
        import psutil
        owned = []
        if self._owned_process_identity:
            pid, born = self._owned_process_identity
            try:
                worker = psutil.Process(pid)
                if worker.create_time() == born:
                    owned = list(reversed(worker.children(recursive=True))) + [worker]
            except (psutil.Error, OSError):
                pass
        identities = []
        for child in owned:
            try:
                identities.append((child.pid, child.create_time()))
                child.terminate()
            except (psutil.Error, OSError):
                pass
        process.kill()

        def kill_remaining():
            for pid, born in identities:
                try:
                    child = psutil.Process(pid)
                    if child.create_time() == born:
                        child.kill()
                except (psutil.Error, OSError):
                    pass
        QTimer.singleShot(500, kill_remaining)

    def _process_finished(self, process, generation, code, state):
        if not self._current(process, generation):
            return
        self._timer.stop()
        self._read_stdout(process, generation, final=True)
        self._read_stderr(process, generation)
        if self._stderr_tail:
            try:
                with os.fdopen(os.open(self._stderr_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
                    stream.write(self._stderr_tail)
            except OSError:
                pass
        identity = self._active['id']
        if self._stop_requested:
            self._recover_partial()
            self.progress.emit(identity, {'stage': 'stopped', 'message': '判讀已停止；已完成頁已保留，目前檔案仍可重試。'})
        elif self._failure_message or code != 0 or state != QProcess.ExitStatus.NormalExit or not self._full_result_received:
            self._recover_partial()
            message = self._failure_message or '這個檔案尚未完成判讀；已保存的結果保持不變，可重試。'
            self.failure.emit(identity, message)
        self._process = None
        self._active = None
        process.deleteLater()
        QTimer.singleShot(0, self._next)

    def _finish_session(self):
        if not self._session_active:
            return
        self._timer.stop()
        self._session_active = False
        self._paused = self._pause_requested = False
        self.finished.emit()

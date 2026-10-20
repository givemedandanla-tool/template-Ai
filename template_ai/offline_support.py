"""Bounded, content-free local support journal and manually shared reports.

This journal describes application operation, not design truth or production
qualification. Existing diagnostic snapshots remain the authority for layout
checks. Nothing in this module sends data or reads private source attachments.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import html
import importlib.metadata
import io
import math
import os
from pathlib import Path
import platform
import re
import stat
import tempfile
import threading
import time
import uuid
import zipfile

from . import __version__
from .diagnostic_bundle import encoded, exact, parse_json, sha
from .offline_runtime import assert_local_path, offline_guard_enabled


MAX_EVENTS = 320
MAX_BYTES = 1024 * 1024
STAGES = {'APPLICATION', 'IMPORT', 'LEARNING', 'TEMPLATES', 'INPUT', 'LAYOUT', 'OUTPUT', 'SUPPORT'}
CODES = {
    'APP_STARTED': '軟體已啟動', 'APP_CLOSED': '軟體已結束',
    'STAGE_OPENED': '已切換工作區', 'INPUT_CHANGED': '輸入資料已變更',
    'ACTION_STARTED': '已開始處理', 'ACTION_COMPLETED': '處理已結束',
    'ACTION_CANCELLED': '已停止這次處理', 'ACTION_FAILED': '處理未完成',
    'UNHANDLED_ERROR': '軟體遇到未預期問題', 'NETWORK_BLOCKED': '已阻止網路存取',
    'REPORT_OPENED': '已開啟問題回報', 'REPORT_EXPORTED': '已手動保存問題報告',
    'REPORT_SAVE_FAILED': '問題報告尚未保存', 'GUI_STATUS_CHANGED': '操作狀態已更新',
    'PREVIOUS_SESSION_FOUND': '已找到上次使用紀錄', 'LOG_READ_FAILED': '上次紀錄無法驗證',
    'PREVIOUS_SESSION_INTERRUPTED': '上次使用未記錄正常結束',
    'USER_REPORTED_PROBLEM': '使用者標記需要協助的問題',
    'NATIVE_WARNING': '介面執行環境提出提示', 'NATIVE_CRITICAL': '介面執行環境遇到問題',
    'NATIVE_FATAL': '介面執行環境無法繼續',
}
ERRORS = {'NONE', 'VALUE', 'TYPE', 'FILE_MISSING', 'PERMISSION', 'OS', 'RUNTIME', 'MEMORY', 'OTHER'}
MISSING = {
    'NONE': '未標記缺少資訊', 'SOURCE': '來源檔案或可信外觀參考',
    'FONT': '本機字型或完整字形', 'OCR': '本機 OCR 引擎或語言資料',
    'MODEL': '可用模型或規則版本', 'CAPACITY': '已驗證的容量資訊',
    'QUALIFICATION': '正式啟用所需驗證', 'CONVERTER': '本機格式轉換工具',
    'UNCLASSIFIED': '需專業人員依問題代碼判斷',
}
NAMES = {'support.json', 'support.html', 'manifest.json'}
PRIVACY = 'SAFE_ALLOWLIST_NO_CONTENT_NO_PATHS_NO_ATTACHMENTS'


def utc_now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def error_kind(error):
    for cls, key in ((FileNotFoundError, 'FILE_MISSING'), (PermissionError, 'PERMISSION'),
                     (MemoryError, 'MEMORY'), (ValueError, 'VALUE'), (TypeError, 'TYPE'),
                     (OSError, 'OS'), (RuntimeError, 'RUNTIME')):
        if isinstance(error, cls):
            return key
    return 'NONE' if error is None else 'OTHER'


def missing_from_hint(message):
    """Classify a visible hint; the original message is never stored or returned.

    A classification is a troubleshooting lead, not proof that a resource is
    absent. Detailed layout/recovery reports retain their original authority.
    """
    if not isinstance(message, str):
        return 'UNCLASSIFIED'
    value = message.casefold()
    for keywords, kind in ((('inkscape', '轉換器', '轉換工具'), 'CONVERTER'),
                           (('tesseract', 'ocr', '語言模型'), 'OCR'),
                           (('字型', '字體', 'glyph'), 'FONT'),
                           (('容量', 'capacity'), 'CAPACITY'),
                           (('資格', '正式啟用'), 'QUALIFICATION'),
                           (('模型', 'model'), 'MODEL'),
                           (('來源', '原稿', 'source'), 'SOURCE')):
        if any(keyword in value for keyword in keywords):
            return kind
    return 'UNCLASSIFIED'


def safe_location(tb):
    """Only trusted package filenames and static function names, never source lines."""
    location = None
    package = Path(__file__).parent
    while tb is not None:
        code = tb.tb_frame.f_code
        p = Path(code.co_filename)
        if p.parent == package and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}\.py', p.name):
            name = code.co_name
            if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', name):
                location = {'module': p.stem, 'function': name, 'line': tb.tb_lineno}
        tb = tb.tb_next
    return location


def _number(value, maximum=1e12):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= maximum:
        raise ValueError('問題報告含不合法數值')


def validate_event(event):
    exact(event, {'utc', 'session', 'stage', 'code', 'error', 'missing', 'elapsed_ms', 'duration_ms', 'rss_mib', 'location'})
    if not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', event['utc']):
        raise ValueError('紀錄時間不合法')
    if not re.fullmatch(r'[0-9a-f]{32}', event['session']):
        raise ValueError('紀錄識別不合法')
    if event['stage'] not in STAGES or event['code'] not in CODES or event['error'] not in ERRORS or event['missing'] not in MISSING:
        raise ValueError('紀錄類型不合法')
    for key in ('elapsed_ms', 'duration_ms', 'rss_mib'):
        if event[key] is not None:
            _number(event[key])
    if event['location'] is not None:
        loc = event['location']
        exact(loc, {'module', 'function', 'line'})
        for key in ('module', 'function'):
            if not isinstance(loc[key], str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', loc[key]):
                raise ValueError('問題位置不合法')
        if type(loc['line']) is not int or not 1 <= loc['line'] < 1_000_000:
            raise ValueError('問題行號不合法')


def _version(name):
    try:
        value = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return 'UNAVAILABLE'
    return value if re.fullmatch(r'[0-9A-Za-z.+_-]{1,48}', value) else 'UNKNOWN'


@lru_cache(maxsize=1)
def implementation_fingerprint():
    """Fingerprint only trusted software modules, never the user's library."""
    package = Path(__file__).parent
    files = sorted(package.glob('*.py'))
    if (package.parent / 'app.py').is_file():
        files.append(package.parent / 'app.py')
    digest = hashlib.sha256()
    try:
        for path in files:
            if path.is_symlink():
                return 'UNAVAILABLE'
            body = path.read_bytes()
            digest.update(path.name.encode() + b'\0' + len(body).to_bytes(8, 'big') + body)
    except OSError:
        return 'UNAVAILABLE'
    return digest.hexdigest() if files else 'UNAVAILABLE'


def environment_facts():
    """No hostname, username, serial number, font list, GPU identifier or paths."""
    os_name = platform.system()
    if os_name not in ('Windows', 'Linux', 'Darwin'):
        os_name = 'OTHER'
    try:
        import psutil
        memory_mib = round(psutil.virtual_memory().total / (1024 * 1024))
    except Exception:
        memory_mib = None
    release = platform.version()
    release = release if re.fullmatch(r'\d+(?:\.\d+){0,3}', release) else 'UNKNOWN'
    return {'os': os_name, 'os_version': release, 'python': platform.python_version(),
            'app': __version__, 'pyside6': _version('PySide6'), 'numpy': _version('numpy'),
            'scipy': _version('scipy'), 'scikit_learn': _version('scikit-learn'),
            'hdbscan': _version('hdbscan'), 'kiwisolver': _version('kiwisolver'),
            'cpu_count': os.cpu_count(), 'memory_mib': memory_mib,
            'implementation_sha256': implementation_fingerprint(),
            'implementation_scope': 'APP_AND_PACKAGE_PY',
            'python_network_guard': offline_guard_enabled(),
            'native_process_firewall': 'NOT_CLAIMED'}


def validate_report(data):
    exact(data, {'schema_version', 'report_id', 'created_utc', 'privacy', 'historical', 'nonformal',
                 'environment', 'events', 'omitted_events', 'journal_persisted', 'summary'})
    if type(data['schema_version']) is not int or data['schema_version'] != 1 or data['privacy'] != PRIVACY:
        raise ValueError('不支援此問題報告格式')
    if data['historical'] is not True or data['nonformal'] is not True or type(data['journal_persisted']) is not bool:
        raise ValueError('問題報告不能代替作品驗證')
    if not isinstance(data['report_id'], str) or not re.fullmatch('[0-9a-f]{32}', data['report_id']):
        raise ValueError('問題報告識別不合法')
    if not isinstance(data['created_utc'], str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', data['created_utc']):
        raise ValueError('問題報告時間不合法')
    env = data['environment']
    exact(env, {'os', 'os_version', 'python', 'app', 'pyside6', 'numpy', 'scipy', 'scikit_learn', 'hdbscan', 'kiwisolver',
                'cpu_count', 'memory_mib', 'implementation_sha256', 'implementation_scope',
                'python_network_guard', 'native_process_firewall'})
    if env['os'] not in ('Windows', 'Linux', 'Darwin', 'OTHER') or type(env['python_network_guard']) is not bool or env['native_process_firewall'] != 'NOT_CLAIMED':
        raise ValueError('環境資訊不合法')
    for key in ('os_version', 'python', 'app', 'pyside6', 'numpy', 'scipy', 'scikit_learn', 'hdbscan', 'kiwisolver'):
        if not isinstance(env[key], str) or not re.fullmatch(r'[0-9A-Za-z.+_-]{1,48}', env[key]):
            raise ValueError('版本資訊不合法')
    if env['cpu_count'] is not None and (type(env['cpu_count']) is not int or not 1 <= env['cpu_count'] <= 100000):
        raise ValueError('處理器數量不合法')
    if env['memory_mib'] is not None:
        _number(env['memory_mib'])
    if (env['implementation_sha256'] != 'UNAVAILABLE' and not re.fullmatch('[0-9a-f]{64}', env['implementation_sha256'])) or env['implementation_scope'] != 'APP_AND_PACKAGE_PY':
        raise ValueError('程式版本指紋不合法')
    if type(data['events']) is not list or len(data['events']) > MAX_EVENTS:
        raise ValueError('操作紀錄超出預算')
    for event in data['events']:
        validate_event(event)
    if type(data['omitted_events']) is not int or data['omitted_events'] < 0:
        raise ValueError('省略紀錄數量不合法')
    if data['summary'] != report_summary(data):
        raise ValueError('白話摘要與技術內容不一致')
    if len(encoded(data)) > MAX_BYTES:
        raise ValueError('問題報告超過大小預算')
    return data


def report_summary(data):
    errors = sum(e['code'] in ('ACTION_FAILED', 'UNHANDLED_ERROR', 'REPORT_SAVE_FAILED', 'LOG_READ_FAILED', 'USER_REPORTED_PROBLEM', 'NATIVE_CRITICAL', 'NATIVE_FATAL') for e in data['events'])
    missing = sorted({e['missing'] for e in data['events']} - {'NONE'})
    return {'發生什麼': f'這份本地紀錄包含 {len(data["events"])} 筆操作與 {errors} 筆問題。',
            '影響什麼': '報告只記錄使用情況；不修改原稿，也不代表模型、字型或印刷已驗證。',
            '接下來怎麼做': '把這個報告檔手動附到 Codex 對話，並說明當時想完成的工作。軟體不會自動傳送。',
            '缺少資訊': '、'.join(MISSING[m] for m in missing) if missing else '紀錄未標記缺少資訊；不代表所有條件已具備。'}


def report_html(data):
    validate_report(data)
    # Canonical ordering keeps the rendered content byte-identical after JSON
    # round trips (including summary and optional location dictionaries).
    data = parse_json(encoded(data))
    esc = lambda value: html.escape(str(value))
    overview = ''.join(f'<h2>{esc(k)}</h2><p>{esc(v)}</p>' for k, v in data['summary'].items())
    rows = ''.join('<tr>' + ''.join(f'<td>{esc(v)}</td>' for v in
        (e['utc'], e['stage'], CODES[e['code']], e['error'], MISSING[e['missing']],
         e['duration_ms'] if e['duration_ms'] is not None else '未量測',
         e['rss_mib'] if e['rss_mib'] is not None else '未量測', e['location'] or '未取得')) + '</tr>' for e in data['events'])
    body = '<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'"><title>Template AI 離線問題報告</title><style>body{font:16px sans-serif;max-width:1100px;margin:24px auto;color:#17243b}td,th{border:1px solid #d5dce5;padding:8px}table{border-collapse:collapse;width:100%}pre{white-space:pre-wrap}</style><h1>離線問題報告</h1>'
    body += overview + '<p>報告沒有私人原文、檔案路徑、原圖、字型檔或資料庫。僅保留最近的有界紀錄；不是完整操作錄影。</p>'
    body += '<h2>技術環境</h2><pre>' + esc(encoded(data['environment']).decode()) + '</pre>'
    body += '<h2>操作與問題</h2><table><tr><th>UTC</th><th>階段</th><th>狀況</th><th>錯誤類型</th><th>缺少資訊</th><th>耗時 ms</th><th>程序記憶體 MiB</th><th>程式位置</th></tr>' + rows + '</table>'
    body += '<p>環境中的 Python 網路防護不代表第三方原生程式或整個作業系統已設置防火牆。此報告不自行證明網路隔離或作品生產資格。</p></html>'
    return body.encode('utf-8')


def build_support_bundle(data):
    public = encoded(validate_report(data))
    page = report_html(data)
    manifest = encoded({'schema_version': 1, 'integrity': 'SHA256_NOT_SIGNATURE',
                        'files': {name: {'bytes': len(body), 'sha256': sha(body)}
                                  for name, body in [('support.json', public), ('support.html', page)]}})
    if sum(map(len, (public, page, manifest))) > MAX_BYTES:
        raise ValueError('問題報告超過 1 MiB，請減少紀錄範圍')
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_STORED) as archive:
        for name, body in [('support.json', public), ('support.html', page), ('manifest.json', manifest)]:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o600 << 16
            archive.writestr(info, body)
    return out.getvalue()


def read_support_bundle(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES + 65536:
        raise ValueError('問題報告超出預算')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if archive.comment or len(entries) != 3 or {e.filename for e in entries} != NAMES:
                raise ValueError('問題報告僅允許三個固定條目')
            if any(e.comment or e.extra or e.flag_bits & 1 or stat.S_ISLNK(e.external_attr >> 16)
                   or e.compress_type != zipfile.ZIP_STORED for e in entries):
                raise ValueError('問題報告封裝不合法')
            if sum(e.file_size for e in entries) > MAX_BYTES:
                raise ValueError('問題報告內容超出預算')
            bodies = {e.filename: archive.read(e) for e in entries}
        data = validate_report(parse_json(bodies['support.json']))
        if raw != build_support_bundle(data):
            raise ValueError('問題報告損壞或摘要不一致')
        return data
    except (zipfile.BadZipFile, UnicodeError, TypeError, KeyError, RuntimeError, RecursionError) as error:
        raise ValueError('問題報告無法驗證') from error


def save_support_bundle(target, raw):
    read_support_bundle(raw)
    assert_local_path(target)
    target = Path(target)
    if target.suffix.lower() != '.zip' or not target.parent.is_dir():
        raise ValueError('請選擇本機資料夾及 ZIP 檔名')
    if target.exists() or target.is_symlink():
        raise FileExistsError('不覆寫既有報告，請使用其他檔名')
    fd, temporary = tempfile.mkstemp(prefix='.support-', suffix='.zip', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        read_support_bundle(Path(temporary).read_bytes())
        from .safe_publish import publish_complete
        publish_complete(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return target


class OfflineJournal:
    def __init__(self, root):
        assert_local_path(root)
        self.path = Path(root) / 'local-support' / 'recent-operations.json'
        self.session = uuid.uuid4().hex
        self.started = time.monotonic()
        self.lock = threading.RLock()
        self.events = []
        self.omitted_events = 0
        self.persisted = False
        self.read_failed = False
        try:
            if self.path.is_file() and self.path.stat().st_size <= MAX_BYTES:
                saved = validate_report(parse_json(self.path.read_bytes()))
                self.events = saved['events']
                self.omitted_events = saved['omitted_events']
            elif self.path.exists():
                self.read_failed = True
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            self.read_failed = True
        previous = bool(self.events)
        unfinished = previous and self.events[-1]['code'] != 'APP_CLOSED'
        self.record('APPLICATION', 'APP_STARTED')
        if previous:
            self.record('APPLICATION', 'PREVIOUS_SESSION_FOUND')
        if unfinished:
            self.record('APPLICATION', 'PREVIOUS_SESSION_INTERRUPTED')
        if self.read_failed:
            self.record('SUPPORT', 'LOG_READ_FAILED')

    def record(self, stage, code, *, error=None, missing='NONE', duration_ms=None, location=None):
        try:
            import psutil
            rss = round(psutil.Process().memory_info().rss / (1024 * 1024), 2)
        except Exception:
            rss = None
        event = {'utc': utc_now(), 'session': self.session, 'stage': stage, 'code': code,
                 'error': error_kind(error), 'missing': missing,
                 'elapsed_ms': round((time.monotonic() - self.started) * 1000, 2),
                 'duration_ms': duration_ms, 'rss_mib': rss, 'location': location}
        validate_event(event)
        with self.lock:
            self.events.append(event)
            if len(self.events) > MAX_EVENTS:
                self.omitted_events += len(self.events) - MAX_EVENTS
                self.events = self.events[-MAX_EVENTS:]
            self._persist()
        return event

    def capture_exception(self, error, tb=None):
        return self.record('APPLICATION', 'UNHANDLED_ERROR', error=error, missing='UNCLASSIFIED', location=safe_location(tb))

    def report(self):
        with self.lock:
            data = {'schema_version': 1, 'report_id': uuid.uuid4().hex, 'created_utc': utc_now(),
                    'privacy': PRIVACY, 'historical': True, 'nonformal': True,
                    'environment': environment_facts(), 'events': [dict(e) for e in self.events],
                    'omitted_events': self.omitted_events, 'journal_persisted': self.persisted}
            data['summary'] = report_summary(data)
            return validate_report(data)

    def _persist(self):
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = self.report()
            data['journal_persisted'] = True
            body = encoded(data)
            fd, temporary = tempfile.mkstemp(prefix='.support-', suffix='.json', dir=self.path.parent)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            self.persisted = True
        except (OSError, ValueError):
            self.persisted = False
        finally:
            if temporary:
                try:
                    Path(temporary).unlink(missing_ok=True)
                except OSError:
                    pass

    def bundle(self):
        return build_support_bundle(self.report())


def install_exception_reporting(journal, notify=None):
    """Opt-in app entrypoint hooks. Never serializes exception text or locals.

    Returns an explicit restore callback, so in-process launch tests and orderly
    shutdown do not leave handlers attached to a destroyed application window.
    """
    import sys
    old_main, old_thread, old_unraisable = sys.excepthook, threading.excepthook, sys.unraisablehook

    def capture(error, tb):
        try:
            journal.capture_exception(error, tb)
        except Exception:
            pass
        if notify is not None:
            try:
                notify()
            except Exception:
                pass
        print('Template AI 遇到問題；請使用本機「問題回報」或 --support-report 匯出安全報告。', file=sys.stderr)

    def main_hook(kind, error, tb):
        if kind in (KeyboardInterrupt, SystemExit):
            return old_main(kind, error, tb)
        capture(error, tb)

    def thread_hook(args):
        if args.exc_type is SystemExit:
            return
        capture(args.exc_value, args.exc_traceback)

    def unraisable_hook(args):
        capture(args.exc_value, args.exc_traceback)

    sys.excepthook, threading.excepthook, sys.unraisablehook = main_hook, thread_hook, unraisable_hook

    def restore():
        if sys.excepthook is main_hook:
            sys.excepthook = old_main
        if threading.excepthook is thread_hook:
            threading.excepthook = old_thread
        if sys.unraisablehook is unraisable_hook:
            sys.unraisablehook = old_unraisable
    return restore


def install_qt_message_reporting(journal):
    """Record only Qt severity. Qt itself still terminates after qFatal.

    Message text, logging context, thread stack and native paths are never
    serialized. This opt-in hook belongs solely to the launched application.
    """
    import sys
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler
    codes = {QtMsgType.QtWarningMsg: 'NATIVE_WARNING', QtMsgType.QtCriticalMsg: 'NATIVE_CRITICAL',
             QtMsgType.QtFatalMsg: 'NATIVE_FATAL'}
    old = None

    def handler(kind, context, message):
        code = codes.get(kind)
        if code is not None:
            try:
                journal.record('APPLICATION', code, error=RuntimeError() if kind != QtMsgType.QtWarningMsg else None)
            except Exception:
                pass
        if old is not None:
            old(kind, context, message)
        elif code is not None:
            print('Template AI 介面執行環境：' + code + '；請使用本機問題回報。', file=sys.stderr)

    old = qInstallMessageHandler(handler)
    def restore():
        qInstallMessageHandler(old)
    return restore

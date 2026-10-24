"""Small STA COM host. Its only stdout is a fixed status, never Adobe error text."""
from pathlib import Path
import re
import sys

RESULT = re.compile(r'(OK\|[1-9][0-9]{0,2}|INVALID_SOURCE|OUTPUT_EXISTS|CANCELLED|ALERTS_DISABLED|SOURCE_OPEN|PAGE_LIMIT|EXPORT_FAILED|CLOSE_FAILED)')


def registered_clsid():
    """Read registration without starting Adobe or manufacturing an OLE1 ProgID."""
    try:
        import winreg
    except ImportError:
        return None
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r'Illustrator.Application\CLSID',
                                0, winreg.KEY_READ | view) as key:
                value = winreg.QueryValueEx(key, None)[0]
                if re.fullmatch(r'\{[0-9a-fA-F-]{36}\}', value):
                    return value
        except OSError:
            pass
    return None


def run(script_path):
    try:
        import pythoncom
        from win32com.client import dynamic
    except ImportError:
        return 'MISSING_BRIDGE'
    application = dispatch = None
    initialized = False
    try:
        path = Path(script_path)
        if not 0 < path.stat().st_size <= 128_000:
            return 'HOST_FAILED'
        script = path.read_text(encoding='utf-8')
        pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
        initialized = True
        clsid = registered_clsid()
        if clsid is None:
            return 'NOT_INSTALLED'
        # Local out-of-process Adobe server; no generated makepy cache or global registration.
        dispatch = pythoncom.CoCreateInstance(pythoncom.MakeIID(clsid), None, pythoncom.CLSCTX_LOCAL_SERVER, pythoncom.IID_IDispatch)
        application = dynamic.Dispatch(dispatch)
        result = str(application.DoJavaScript(script))
        return result if RESULT.fullmatch(result) else 'EXPORT_FAILED'
    except Exception:
        return 'HOST_FAILED'
    finally:
        # Releasing this client's references is not application.Quit().
        application = dispatch = None
        if initialized:
            pythoncom.CoUninitialize()


if __name__ == '__main__':
    result = run(sys.argv[1]) if len(sys.argv) == 2 else 'HOST_FAILED'
    sys.stdout.write(result)
    raise SystemExit(0 if result.startswith('OK|') else 2)

"""Separate Windows original font-viewer handoff; never a silent installer."""
import sys
from pathlib import Path
from .font_catalog import asset_health
from .font_evidence import inspect_font
from .background import file_digest

def _launch_viewer(source):
    import ctypes,subprocess
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);function=kernel.GetSystemDirectoryW;function.argtypes=[ctypes.c_wchar_p,ctypes.c_uint];function.restype=ctypes.c_uint
    buffer=ctypes.create_unicode_buffer(32768);length=function(buffer,len(buffer))
    if not length or length>=len(buffer):raise OSError('Windows系統目錄無法核對')
    viewer=Path(buffer.value)/'fontview.exe'
    if viewer.is_symlink() or not viewer.is_file():raise OSError('Windows原生字型檢視器不可用，未下載或改用其他安裝器')
    return subprocess.Popen([str(viewer),str(source)],shell=False,close_fds=True).pid

def open_windows_font_workflow(asset,actor,basis,consent=False):
    if consent is not True:raise ValueError('需獨立明確同意Windows原生字型流程；程式內匯入不代表系統安裝授權')
    if not all(isinstance(v,str) and v.strip() and len(v)<=2000 and not any(ord(c)<32 for c in v) for v in (actor,basis)):raise ValueError('需具名與有權提供／安裝的來源授權依據')
    if sys.platform!='win32':raise ValueError('目前不是Windows，無法啟動或驗證Windows字型安裝流程')
    status,issues=asset_health(asset)
    if status!='HEALTHY':raise ValueError('；'.join(issues))
    source=Path(asset['path'])
    if source.suffix.lower() not in ('.ttf','.otf'):raise ValueError('需已核對且獨立的TTF／OTF字面，不直接安裝整個集合')
    proof=inspect_font(source)
    if proof['hash']!=asset['hash'] or len(proof['faces'])!=1 or file_digest(source)!=asset['hash']:raise ValueError('核對期間字型來源已變更或字面不唯一')
    pid=_launch_viewer(source.resolve())
    return dict(state='VIEWER_OPENED_PENDING_OS_ACTION',viewer_pid=pid,asset_sha256=proof['hash'],family=proof['faces'][0]['family'],actor=actor.strip(),basis=basis.strip(),system_installed=None,scope='TO_BE_CHOSEN_AND_CONFIRMED_IN_WINDOWS',admin_required=None,source_changed=False,paid_services=False,
                reason='僅開啟Windows原生字型檢視器；未宣稱安裝完成。安裝範圍／管理員與最終授權須在Windows另行確認；回復須依Windows字型設定核對實際安裝項目。')

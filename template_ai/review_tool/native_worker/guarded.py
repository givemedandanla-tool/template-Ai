import ctypes as C,json,runpy,sys,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from ctypes import wintypes as W
a=C.WinDLL('advapi32');k=C.WinDLL('kernel32');k.GetCurrentProcess.restype=W.HANDLE;a.OpenProcessToken.argtypes=[W.HANDLE,W.DWORD,C.POINTER(W.HANDLE)];a.GetTokenInformation.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.POINTER(W.DWORD)];token=W.HANDLE();assert a.OpenProcessToken(k.GetCurrentProcess(),8,C.byref(token));v=W.DWORD();n=W.DWORD();assert a.GetTokenInformation(token,29,C.byref(v),4,C.byref(n));assert v.value==1;size=W.DWORD();a.GetTokenInformation(token,30,None,0,C.byref(size));buffer=C.create_string_buffer(size.value);assert a.GetTokenInformation(token,30,buffer,size,C.byref(size));assert W.DWORD.from_buffer(buffer).value==0;k.CloseHandle.argtypes=[W.HANDLE];k.CloseHandle(token);dest=Path(sys.argv[sys.argv.index('--output')+1]);(dest.parent/(dest.name+'-containment.json')).write_text(json.dumps({'is_appcontainer':True}),encoding='utf8')
try:
 sys.argv[0]=str(Path(__file__).with_name('engine_worker.py'));namespace=runpy.run_path(sys.argv[0],run_name='__main__')
 import os
 os._exit(0)
except BaseException:
 (dest.parent/(dest.name+'-error.local.txt')).write_text(traceback.format_exc(),encoding='utf8')
 import os
 os._exit(1)

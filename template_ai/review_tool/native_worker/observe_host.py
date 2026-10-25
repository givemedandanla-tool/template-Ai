"""Observe only this test process. No window titles or document text recorded."""
import ctypes as C,threading,time,os
from ctypes import wintypes as W
class Observer:
 def __init__(self):
  self.stop=threading.Event();self.samples=0;self.visible=set();self.peak_working_set=0;self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
 def run(self):
  U=C.WinDLL('user32');K=C.WinDLL('kernel32');PS=C.WinDLL('psapi')
  U.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)];U.IsWindowVisible.argtypes=[W.HWND];U.GetClassNameW.argtypes=[W.HWND,W.LPWSTR,C.c_int]
  CB=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
  @CB
  def visit(hwnd,param):
   pid=W.DWORD();U.GetWindowThreadProcessId(hwnd,C.byref(pid))
   if pid.value==os.getpid() and U.IsWindowVisible(hwnd):
    name=C.create_unicode_buffer(128);U.GetClassNameW(hwnd,name,128);self.visible.add(name.value)
   return True
  class PMC(C.Structure):_fields_=[('cb',W.DWORD),('faults',W.DWORD)]+[(name,C.c_size_t) for name in ['peak','working','pp','p','pnp','np','page','peakpage']]
  PS.GetProcessMemoryInfo.argtypes=[W.HANDLE,P:=C.POINTER(PMC),W.DWORD]
  while not self.stop.is_set():
   U.EnumWindows(visit,0);self.samples+=1;pmc=PMC();pmc.cb=C.sizeof(pmc)
   if PS.GetProcessMemoryInfo(W.HANDLE(-1),C.byref(pmc),pmc.cb):self.peak_working_set=max(self.peak_working_set,pmc.peak)
   self.stop.wait(.1)
 def finish(self):
  self.stop.set();self.thread.join(timeout=2)
  return {'samples':self.samples,'interval_seconds':.1,'visible_window_classes':sorted(self.visible),'peak_working_set_bytes':self.peak_working_set}

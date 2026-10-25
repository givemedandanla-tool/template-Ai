"""Fail-closed Windows containment for an owned, one-document native worker.

The parent never loads an Adobe DLL. Zero AppContainer capabilities, a verified
restricted child-process policy and a kill-on-close job are required before the
worker's first instruction. Only caller-created local staging paths get ACLs.
"""
from __future__ import annotations
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import os
import subprocess
import time
import uuid

P=C.c_void_p;D=W.DWORD;SIZE=C.c_size_t
class IsolationError(RuntimeError):
    code='NATIVE_ISOLATION_UNAVAILABLE'
    safe_message='無法建立安全的離線讀取程序，已停止；原稿保持不變。'

class _SI(C.Structure):
    _fields_=[('cb',D),('reserved',W.LPWSTR),('desktop',W.LPWSTR),('title',W.LPWSTR),('x',D),('y',D),('xs',D),('ys',D),('xc',D),('yc',D),('fill',D),('flags',D),('show',W.WORD),('reserved2n',W.WORD),('reserved2',P),('stdin',W.HANDLE),('stdout',W.HANDLE),('stderr',W.HANDLE)]
class _SIX(C.Structure):_fields_=[('si',_SI),('attributes',P)]
class _PI(C.Structure):_fields_=[('process',W.HANDLE),('thread',W.HANDLE),('pid',D),('tid',D)]
class _CAP(C.Structure):_fields_=[('sid',P),('caps',P),('count',D),('reserved',D)]
class _LIMIT(C.Structure):
    _fields_=[('process_time',C.c_int64),('job_time',C.c_int64),('flags',D),('min_working',SIZE),('max_working',SIZE),('active',D),('affinity',SIZE),('priority',D),('scheduling',D)]
class _EXTENDED(C.Structure):
    _fields_=[('basic',_LIMIT),('io',C.c_uint64*6),('process_memory',SIZE),('job_memory',SIZE),('peak_process',SIZE),('peak_job',SIZE)]

def local_staging_path(value):
    path=Path(value)
    if not path.is_absolute() or str(path).startswith(('\\\\','//')):
        raise IsolationError('Staging must be an absolute local path')
    for item in [path,*path.parents]:
        if item.is_symlink() or (hasattr(item,'is_junction') and item.is_junction()):
            raise IsolationError('Staging cannot contain a reparse link')
        if item.exists() and getattr(item.stat(),'st_file_attributes',0)&0x400:
            raise IsolationError('Staging cannot contain a reparse point')
    resolved=path.resolve(strict=True)
    if resolved==Path(resolved.anchor) or resolved==Path.home():
        raise IsolationError('Staging scope is too broad')
    k=C.WinDLL('kernel32',use_last_error=True);k.GetDriveTypeW.argtypes=[W.LPCWSTR]
    if k.GetDriveTypeW(resolved.anchor) not in (2,3):
        raise IsolationError('Staging must use a local disk')
    return resolved

class WindowsIsolation:
    def __init__(self, staging_root):
        if os.name!='nt':raise IsolationError('Windows containment is required')
        self.root=local_staging_path(staging_root)
        self.k=C.WinDLL('kernel32',use_last_error=True)
        self.a=C.WinDLL('advapi32',use_last_error=True)
        self.u=C.WinDLL('userenv',use_last_error=True)
        self.sid=P();self.name='TemplateAI.Review.Native.'+uuid.uuid4().hex
        self.granted=[];self.closed=False
        self.u.CreateAppContainerProfile.argtypes=[W.LPCWSTR,W.LPCWSTR,W.LPCWSTR,P,D,C.POINTER(P)]
        self.u.CreateAppContainerProfile.restype=C.c_long
        self.u.DeleteAppContainerProfile.argtypes=[W.LPCWSTR]
        self.a.ConvertSidToStringSidW.argtypes=[P,C.POINTER(W.LPWSTR)]
        self.a.FreeSid.argtypes=[P];self.k.LocalFree.argtypes=[P]
        status=self.u.CreateAppContainerProfile(self.name,self.name,'Offline document reader',None,0,C.byref(self.sid))
        if status:raise IsolationError('Profile creation failed: '+hex(status&0xffffffff))
        text=W.LPWSTR()
        if not self.a.ConvertSidToStringSidW(self.sid,C.byref(text)):
            self.close();raise IsolationError('Profile SID unavailable')
        self.sid_text=text.value;self.k.LocalFree(text)

    def grant(self,path,*,writable=False):
        path=local_staging_path(path)
        if path!=self.root and self.root not in path.parents:
            raise IsolationError('ACL target escaped staging')
        # Inherited ACEs propagate from the new staging directory; no broad
        # user, Everyone, system-folder or source-artwork permission changes.
        permission='M' if writable else 'RX'
        result=subprocess.run(['icacls.exe',str(path),'/grant','*'+self.sid_text+':(OI)(CI)'+permission],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=60)
        if result.returncode:raise IsolationError('Staging permission failed')
        self.granted.append(path)
        if writable:
            result=subprocess.run(['icacls.exe',str(path),'/setintegritylevel','(OI)(CI)L'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=60)
            if result.returncode:raise IsolationError('Writable staging integrity failed')

    def _verify(self,process):
        a=self.a;k=self.k
        a.OpenProcessToken.argtypes=[W.HANDLE,D,C.POINTER(W.HANDLE)]
        a.GetTokenInformation.argtypes=[W.HANDLE,C.c_int,P,D,C.POINTER(D)]
        a.EqualSid.argtypes=[P,P]
        token=W.HANDLE()
        if not a.OpenProcessToken(process,8,C.byref(token)):raise IsolationError('Cannot inspect worker token')
        def info(kind):
            size=D();a.GetTokenInformation(token,kind,None,0,C.byref(size))
            if not 4<=size.value<=65536:raise IsolationError('Invalid token information size')
            data=C.create_string_buffer(size.value)
            if not a.GetTokenInformation(token,kind,data,size,C.byref(size)):raise IsolationError('Token query failed')
            return data
        try:
            if D.from_buffer(info(29)).value!=1:raise IsolationError('Worker is not in an AppContainer')
            if D.from_buffer(info(30)).value!=0:raise IsolationError('Unexpected worker capabilities')
            data=info(31);actual=P.from_buffer(data).value
            if not actual or not a.EqualSid(actual,self.sid):raise IsolationError('Unexpected AppContainer identity')
            policy=D();k.GetProcessMitigationPolicy.argtypes=[W.HANDLE,C.c_int,P,SIZE]
            # PROCESS_MITIGATION_POLICY::ProcessChildProcessPolicy (Windows SDK).
            if not k.GetProcessMitigationPolicy(process,13,C.byref(policy),4) or not policy.value&1:
                raise IsolationError('Child process restriction was not applied')
            return {'is_appcontainer':True,'capability_count':0,'child_process_creation_blocked':True}
        finally:k.CloseHandle(token)

    def run(self,command,environment,*,cwd,timeout=180,cancelled=None):
        if self.closed:raise IsolationError('Container already closed')
        executable=local_staging_path(command[0]);cwd=local_staging_path(cwd)
        if self.root not in executable.parents or (cwd!=self.root and self.root not in cwd.parents):
            raise IsolationError('Worker path escaped staging')
        k=self.k;k.CloseHandle.argtypes=[W.HANDLE]
        k.InitializeProcThreadAttributeList.argtypes=[P,D,D,C.POINTER(SIZE)];k.UpdateProcThreadAttribute.argtypes=[P,D,SIZE,P,SIZE,P,P];k.DeleteProcThreadAttributeList.argtypes=[P]
        k.CreateJobObjectW.argtypes=[P,W.LPCWSTR];k.CreateJobObjectW.restype=W.HANDLE
        k.SetInformationJobObject.argtypes=[W.HANDLE,C.c_int,P,D]
        k.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE]
        k.TerminateJobObject.argtypes=[W.HANDLE,W.UINT]
        k.CreateProcessW.argtypes=[W.LPCWSTR,W.LPWSTR,P,P,W.BOOL,D,P,W.LPCWSTR,C.POINTER(_SIX),C.POINTER(_PI)]
        k.ResumeThread.argtypes=[W.HANDLE];k.ResumeThread.restype=D
        k.WaitForSingleObject.argtypes=[W.HANDLE,D];k.GetExitCodeProcess.argtypes=[W.HANDLE,C.POINTER(D)]
        k.TerminateProcess.argtypes=[W.HANDLE,W.UINT]
        pi=_PI();attrs=None;job=None;assigned=False
        try:
            job=k.CreateJobObjectW(None,None)
            if not job:raise IsolationError('Worker job creation failed')
            limits=_EXTENDED();limits.basic.flags=0x2000|0x8|0x100;limits.basic.active=1;limits.process_memory=2*1024**3
            if not k.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)):
                raise IsolationError('Worker job limits failed')
            size=SIZE();k.InitializeProcThreadAttributeList(None,2,0,C.byref(size))
            if not 0<size.value<65536:raise IsolationError('Invalid process attribute size')
            attrs=C.create_string_buffer(size.value)
            if not k.InitializeProcThreadAttributeList(attrs,2,0,C.byref(size)):raise IsolationError('Process attributes unavailable')
            caps=_CAP(self.sid,None,0,0);policy=D(1)
            for number,value in [(0x20009,caps),(0x2000e,policy)]:
                if not k.UpdateProcThreadAttribute(attrs,0,number,C.byref(value),C.sizeof(value),None,None):raise IsolationError('Containment attribute rejected')
            si=_SIX();si.si.cb=C.sizeof(si);si.si.desktop='winsta0\\default';si.attributes=C.cast(attrs,P)
            env=C.create_unicode_buffer('\0'.join(key+'='+value for key,value in sorted(environment.items()))+'\0\0')
            cmd=C.create_unicode_buffer(subprocess.list2cmdline([str(x) for x in command]))
            old_mode=k.SetErrorMode(0x8003)
            try:
                created=k.CreateProcessW(str(executable),cmd,None,None,False,0x80000|0x08000000|0x400|0x4,env,str(cwd),C.byref(si),C.byref(pi))
            finally:k.SetErrorMode(old_mode)
            if not created:raise IsolationError('Worker creation failed: '+str(C.get_last_error()))
            if not k.AssignProcessToJobObject(job,pi.process):raise IsolationError('Cannot bind worker lifetime')
            assigned=True;proof=self._verify(pi.process)
            if k.ResumeThread(pi.thread)==0xffffffff:raise IsolationError('Cannot resume contained worker')
            started=time.monotonic();reason=None
            while True:
                status=k.WaitForSingleObject(pi.process,100)
                if status==0:break
                if status!=258:raise IsolationError('Worker wait failed')
                if cancelled and cancelled():reason='cancelled'
                elif time.monotonic()-started>timeout:reason='timeout'
                if reason:
                    if not k.TerminateJobObject(job,1):raise IsolationError('Cannot stop owned worker job')
                    if k.WaitForSingleObject(pi.process,5000)!=0:raise IsolationError('Owned worker did not stop')
                    break
            code=D()
            if not k.GetExitCodeProcess(pi.process,C.byref(code)):raise IsolationError('Worker exit status unavailable')
            return {**proof,'pid':pi.pid,'exit_code':code.value,'stop_reason':reason,'seconds':round(time.monotonic()-started,3),'job_process_limit':1,'kill_on_job_close':True}
        finally:
            if pi.process and not assigned:
                k.TerminateProcess(pi.process,1);k.WaitForSingleObject(pi.process,5000)
            if job:k.CloseHandle(job)
            if pi.thread:k.CloseHandle(pi.thread)
            if pi.process:k.CloseHandle(pi.process)
            if attrs:k.DeleteProcThreadAttributeList(attrs)

    def close(self):
        if self.closed:return
        self.closed=True
        for path in reversed(self.granted):
            subprocess.run(['icacls.exe',str(path),'/remove:g','*'+self.sid_text],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW,timeout=60)
        self.u.DeleteAppContainerProfile(self.name)
        if self.sid:self.a.FreeSid(self.sid);self.sid=P()

def worker_environment(temp,python):
    allowed={'systemroot','windir','userprofile','localappdata','appdata','programdata','allusersprofile','public','comspec','homedrive','homepath','username','userdomain','programfiles','programfiles(x86)','programw6432','commonprogramfiles','commonprogramfiles(x86)','os','processor_architecture'}
    result={k:v for k,v in os.environ.items() if k.lower() in allowed}
    result.update(TEMP=str(temp),TMP=str(temp),PYTHONHOME=str(python),PYTHONDONTWRITEBYTECODE='1',PATH=str(python)+r';C:\Windows\System32')
    return result

"""Version-pinned, process-local idle mailbox for a read-only linguistic host.

No Adobe bytes are changed on disk. Only three imports of this exact loaded
module are redirected. Unrelated file operations retain the real OS APIs.
This prototype does not claim qualification until output regression succeeds.
"""
import ctypes as C,hashlib,threading
from ctypes import wintypes as W
from pathlib import Path
P=C.c_void_p;D=W.DWORD
class LocalMailboxes:
 def __init__(self,binary,emit):
  target=Path(binary)/'AdobeLinguistic.dll'
  if hashlib.sha256(target.read_bytes()).hexdigest()!='4d1ccfe62d3261bb61b10ec097a40e90702b67ba3ee2fc4e2a0a9678ff36e00e':raise RuntimeError('Unverified linguistic library')
  self.module=C.WinDLL(str(target));self.kernel=C.WinDLL('kernel32',use_last_error=True);k=self.kernel
  k.CreateEventW.argtypes=[P,W.BOOL,W.BOOL,W.LPCWSTR];k.CreateEventW.restype=W.HANDLE
  k.SetEvent.argtypes=[W.HANDLE];k.WaitForSingleObject.argtypes=[W.HANDLE,D];k.CloseHandle.argtypes=[W.HANDLE]
  k.ReadFile.argtypes=[W.HANDLE,P,D,C.POINTER(D),P];k.ReadFile.restype=W.BOOL
  k.VirtualProtect.argtypes=[P,C.c_size_t,D,C.POINTER(D)];k.SetLastError.argtypes=[D]
  self.emit=emit;self.boxes={};self.lock=threading.Lock();self.callbacks=[];self.counts={'created':0,'read_timeouts':0,'closed':0,'overlapped_rejected':0}
  def create(name,size,timeout,security):
   handle=k.CreateEventW(None,True,False,None)
   if not handle:return C.c_void_p(-1).value
   with self.lock:self.boxes[handle]={'timeout':timeout,'size':size};self.counts['created']+=1
   emit('local_mailbox_create',size=size,timeout=timeout)
   return handle
  def read(handle,buffer,count,read_count,overlapped):
   with self.lock:box=self.boxes.get(handle)
   if box is None:return k.ReadFile(handle,buffer,count,read_count,overlapped)
   if read_count:read_count[0]=0
   if overlapped:
    self.counts['overlapped_rejected']+=1;C.set_last_error(50);return False
   delay=box['timeout']
   # The reader has no mutable user dictionaries or other processes to notify.
   # Return the same empty-read timeout as an idle finite-timeout mailslot.
   if delay==0xffffffff:delay=1000
   signaled=k.WaitForSingleObject(handle,min(delay,1000))==0
   self.counts['read_timeouts']+=1
   C.set_last_error(995 if signaled else 121)
   return False
  def close(handle):
   with self.lock:box=self.boxes.pop(handle,None)
   if box is not None:self.counts['closed']+=1;k.SetEvent(handle)
   return k.CloseHandle(handle)
  prototypes=[(0x56120,C.WINFUNCTYPE(W.HANDLE,W.LPCWSTR,D,D,P,use_last_error=True),create),
              (0x560d0,C.WINFUNCTYPE(W.BOOL,W.HANDLE,P,D,C.POINTER(D),P,use_last_error=True),read),
              (0x56010,C.WINFUNCTYPE(W.BOOL,W.HANDLE,use_last_error=True),close)]
  self.originals=[]
  for offset,prototype,function in prototypes:
   address=self.module._handle+offset;old=D();callback=prototype(function);self.callbacks.append(callback)
   original=P.from_address(address).value;self.originals.append((address,original))
   if not k.VirtualProtect(address,C.sizeof(P),0x04,C.byref(old)):raise C.WinError(C.get_last_error())
   P.from_address(address).value=C.cast(callback,P).value
   restored=D()
   if not k.VirtualProtect(address,C.sizeof(P),old.value,C.byref(restored)):raise C.WinError(C.get_last_error())
  emit('linguistic_local_mailbox_installed',imports=3,network_capability_added=False)

"""Noninteractive PDF export for the exact verified AILib build; new targets only."""
import ctypes as C,hashlib
from pathlib import Path
P=C.c_void_p;I=C.c_int32;B=C.c_ubyte

def export_pdf(lib,ctx,target,emit,has_text=True):
    from font_probe import inspect_fonts
    inspect_fonts(lib,ctx,Path(target).parent,emit,has_text)
    target=Path(target)
    if target.exists():raise FileExistsError('Export target already exists')
    basic=(P*8).from_address(ctx)
    acquire=C.CFUNCTYPE(I,C.c_char_p,I,C.POINTER(P))(basic[0]);release=C.CFUNCTYPE(I,C.c_char_p,I)(basic[1])
    suite=P();err=acquire(b'AI Document Suite',17,C.byref(suite))
    if err:raise RuntimeError('Document suite 17 unavailable')
    path=P();string=P()
    string_new=C.CFUNCTYPE(P,P,C.c_wchar_p)(lib._handle+0x430590);string_delete=C.CFUNCTYPE(None,P)(lib._handle+0xb6f70)
    path_new=C.CFUNCTYPE(P,P,P,B)(lib._handle+0x46af20);path_delete=C.CFUNCTYPE(None,P)(lib._handle+0x46af40)
    try:
        address=(P*61).from_address(suite.value)[60]
        if address!=lib._handle+0x2e0440:raise RuntimeError('Unexpected WriteDocumentWithOptions pointer')
        string_new(C.byref(string),str(target));path_new(C.byref(path),C.byref(string),1)
        write=C.CFUNCTYPE(I,P,C.c_char_p,I,P,I)(address)
        flags=(1<<9)|(1<<14)|(1<<15)|(1<<21)|(1<<22)
        emit('pdf_write_begin',target_name=target.name,flags=hex(flags))
        error=write(C.byref(path),b'PDF File Format',flags,None,0)
        result={'format':'PDF File Format','error':error,'error_hex':hex(error&0xffffffff),'file_exists':target.is_file(),
                'bytes':target.stat().st_size if target.is_file() else 0,'full_fidelity_verified':False}
        if target.is_file():result['sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
        result['write_pass']=error==0 and result['bytes']>0
        emit('pdf_write_end',**result)
        from export_svg import export_svg
        result['svg']=export_svg(lib,ctx,target.with_suffix('.svg'),emit,has_text)
        return result
    finally:
        if path.value:path_delete(C.byref(path))
        if string.value:string_delete(C.byref(string))
        release(b'AI Document Suite',17)

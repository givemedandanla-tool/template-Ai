"""Version-pinned contained native reader. Inputs are never saved or overwritten."""
import argparse,ctypes as C,hashlib,json,os,time
from pathlib import Path
from ctypes import wintypes as W
from observe_host import Observer
P=C.c_void_p; I=C.c_int32; B=C.c_ubyte

def modules():
    k=C.WinDLL('kernel32');p=C.WinDLL('psapi');k.GetCurrentProcess.restype=W.HANDLE
    p.EnumProcessModules.argtypes=[W.HANDLE,C.POINTER(W.HMODULE),W.DWORD,C.POINTER(W.DWORD)]
    p.GetModuleFileNameExW.argtypes=[W.HANDLE,W.HMODULE,W.LPWSTR,W.DWORD]
    a=(W.HMODULE*4096)();n=W.DWORD();h=k.GetCurrentProcess()
    if not p.EnumProcessModules(h,a,C.sizeof(a),C.byref(n)):raise RuntimeError('MODULE_ENUM_FAILED')
    result=[]
    for v in a[:n.value//C.sizeof(W.HMODULE)]:
        s=C.create_unicode_buffer(32768);p.GetModuleFileNameExW(h,v,s,len(s));result.append(s.value)
    return sorted(result)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runtime',type=Path,required=True);ap.add_argument('--input-dir',type=Path,required=True);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.mode='pdf';a.load_local_fonts=True
    runtime=a.runtime;binary=runtime/'Support Files/Contents/Windows';out=a.output
    out.mkdir(exist_ok=False);start=time.monotonic();log=(out/'events.jsonl').open('x',encoding='utf8')
    def emit(stage,**data):log.write(json.dumps({'stage':stage,'elapsed':round(time.monotonic()-start,3),**data})+'\n');log.flush()
    observer=Observer();services=[];bib_context=None;ctx=None;lib=None
    for n in ['tmp','appdata','localappdata','scratch1','scratch2','prefs']:(out/n).mkdir()
    os.environ.update(TEMP=str(out/'tmp'),TMP=str(out/'tmp'),APPDATA=str(out/'appdata'),LOCALAPPDATA=str(out/'localappdata'),AIROBIN_DISABLE_CRASH_REPORTER='1')
    os.chdir(binary);cookie=os.add_dll_directory(str(binary));C.windll.kernel32.SetErrorMode(0x8003)
    crt=runtime.parent/'support/crt'
    crt_cookie=os.add_dll_directory(str(crt)) if crt.is_dir() else None
    class Host(C.Structure):
        _fields_=[('name',C.c_wchar_p),('major',C.c_uint64),('pref_name',C.c_wchar_p),('plugins',C.c_wchar_p),('required',C.c_wchar_p),('extra_plugins',C.c_wchar_p),('plugin_filter',C.c_wchar_p),('root',C.c_wchar_p),('perf_log',B),('general_log',B),('padding',B*6),('scratch1',C.c_wchar_p),('scratch2',C.c_wchar_p),('locale',C.c_wchar_p),('prefs',C.c_wchar_p),('cloud_prefs',C.c_wchar_p),('sofia',C.c_wchar_p)]
    assert C.sizeof(Host)==0x78
    host=Host();host.name='AIRobin';host.major=24;host.pref_name='ReviewToolOfflineReader';host.plugins=str(runtime/'Plug-ins');host.required=str(runtime/'Support Files/Required');host.extra_plugins=str(runtime/'Support Files/Required/AIRobin_Plug-ins');host.plugin_filter=str(binary/'AIRobinPluginFilter.cfg');host.root=str(binary/'Illustrator.exe');host.perf_log=3;host.general_log=3;host.scratch1=str(out/'scratch1');host.scratch2=str(out/'scratch2');host.locale='en_US';host.prefs=str(out/'prefs/IllustratorPrefs');host.cloud_prefs=str(out/'prefs/CloudPrefs');host.sofia=''
    summary={'mode':a.mode,'pid':os.getpid(),'cases':[],'qualified_full_fidelity':False}
    emit('start',pid=os.getpid(),mode=a.mode)
    registered_fonts=[]
    if a.load_local_fonts:
        gdi=C.WinDLL('gdi32');gdi.AddFontResourceExW.argtypes=[C.c_wchar_p,W.DWORD,P];gdi.AddFontResourceExW.restype=I
        font_directory=Path(os.environ.get('REVIEW_PROBE_FONT_DIR',str(a.input_dir.parent/'local-fonts')))
        for font in sorted(font_directory.rglob('*')):
            if font.suffix.lower() not in ('.ttf','.ttc','.otf'):continue
            count=gdi.AddFontResourceExW(str(font),0x10,None)
            if count:registered_fonts.append(str(font))
            emit('local_font_registered',file=font.name,faces=count)
    try:
        expected='fb1ded30ca8b3034f91a835ab09ca440d1ab545e193d27897629164d5970d2c2'
        if hashlib.sha256((binary/'AILib.dll').read_bytes()).hexdigest()!=expected:raise RuntimeError('UNVERIFIED_AILIB_BINARY')
        bib=C.WinDLL(str(binary/'BIB.dll'));f=bib.BIBInitialize3;f.argtypes=[P]*7+[I,P];f.restype=P;bib_context=f(None,None,None,None,None,None,None,1,None)
        if not bib_context:raise RuntimeError('BIB_INIT_NULL')
        for name,ordinal,extra in [('BIBUtils',3,[]),('ACE',3,[0]),('AGM',3,[0x41e57,0,0]),('ARE',3,[]),('MPS',1,[])]:
            dll=C.WinDLL(str(binary/(name+'.dll')));services.append((name,dll));f=dll[ordinal];f.argtypes=[P]+[C.c_uint64]*len(extra);f.restype=I
            ok=f(bib_context,*extra);emit('service',name=name,result=ok)
            if not ok:raise RuntimeError('SERVICE_INIT_FAILED:'+name)
        lib=C.WinDLL(str(binary/'AILib.dll'),winmode=0x100|0x1000);init=lib.AILInitializeWithHostApplicationData;init.argtypes=[C.POINTER(Host)];init.restype=P
        from local_mailbox import LocalMailboxes
        global _mailboxes_keepalive
        _mailboxes_keepalive=LocalMailboxes(binary,emit)
        emit('initialize_begin');ctx=init(C.byref(host));emit('initialize_end',context_nonnull=bool(ctx))
        if not ctx:raise RuntimeError('AIL_INIT_NULL')
        from read_artwork import read_artwork
        from export_document import export_pdf
        callback=lambda artwork:export_pdf(lib,ctx,out/'document.pdf',emit,has_text=any(row['type']==12 for row in artwork['art_items']))
        result=read_artwork(lib,ctx,a.source,out/'artwork.local.json',emit,callback)
        if not result['source_unchanged'] or not result['export']['write_pass'] or not result['export']['svg']['write_pass']:
            raise RuntimeError('NATIVE_OUTPUT_FAILED')
        summary.update(status='EXPORTED',source_sha256=result['sha256_before'],artboards=result['artboard_count'],export=result['export'])
    except BaseException as error:
        summary.update(status='FAILED',error_type=type(error).__name__,error=str(error));emit('error',type=type(error).__name__,message=str(error));raise
    finally:
        summary['loaded_modules']=modules()
        if ctx:
            emit('terminate_begin');term=lib.AILTerminate;term.argtypes=[];term.restype=None;term();emit('terminated')
        for name,dll in reversed(services):
            f=dll[2 if name=='MPS' else 4];f.argtypes=[];f.restype=I;f()
        if bib_context:
            f=bib.BIBTerminate;f.argtypes=[];f.restype=I;f()
        if registered_fonts:
            gdi.RemoveFontResourceExW.argtypes=[C.c_wchar_p,W.DWORD,P]
            for font in registered_fonts:gdi.RemoveFontResourceExW(font,0x10,None)
        summary['observation']=observer.finish();summary['seconds']=round(time.monotonic()-start,3)
        emit('observation',**summary['observation'])
        with (out/'summary.json').open('x',encoding='utf8') as f:json.dump(summary,f,indent=2)
        log.close()

if __name__=='__main__':main()

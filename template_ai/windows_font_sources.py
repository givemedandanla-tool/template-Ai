"""Bounded read-only registered font files, distinct from actual Qt face selection."""
import os,sys
from pathlib import Path
from .background import file_digest
from .font_evidence import inspect_font,MAX_FONT_BYTES

SCOPE='REGISTERED_FILES_NOT_ACTIVE_QT_FACE_OR_LICENCE'

def collect_registered_font_sources(records,roots,*,max_files=128,max_bytes=128*1024**2,max_faces=512,allow_registered_absolute_local=False):
    if type(max_files) is not int or not 1<=max_files<=256 or type(max_bytes) is not int or not 0<=max_bytes<=256*1024**2 or type(max_faces) is not int or not 1<=max_faces<=1024:raise ValueError('Windows字型來源盤點預算無效')
    report=dict(status='COMPLETE',scope=SCOPE,files=[],rejected=[],source_bytes_budgeted=0,notes=[]);seen={};faces_left=max_faces
    def reject(reason):report['status']='PARTIAL';report['rejected'].append(str(reason)[:500])
    for number,record in enumerate(records):
        if number>=1000:reject('字型登錄超過1000筆，本輪未完整盤點');break
        try:
            if not isinstance(record,dict):raise ValueError('字型登錄資料格式未知')
            scope=record.get('scope');value=record.get('file')
            if scope not in ('MACHINE','USER') or scope not in roots or roots[scope] is None:raise ValueError('未核對Windows來源目錄／範圍')
            if not isinstance(value,str) or not value or len(value)>4096 or '\x00' in value or value.startswith(('\\\\','//')) or '..' in value.replace('\\','/').split('/'):raise ValueError('字型來源不是可核對的本機路徑')
            value=os.path.expandvars(value);root=Path(roots[scope])
            if str(root).startswith(('\\\\','//')) or value.startswith(('\\\\','//')):raise ValueError('不讀取網路字型來源')
            source=Path(value);source=source if source.is_absolute() else root/source
            registered_absolute=Path(value).is_absolute() and allow_registered_absolute_local is True
            if source.is_symlink() or (not source.resolve().is_relative_to(root.resolve()) and not registered_absolute):raise ValueError('字型來源超出已核對字型目錄')
            if str(source.resolve()).startswith(('\\\\','//')):raise ValueError('不讀取網路字型來源')
            source=source.resolve()
            if source.suffix.lower() not in ('.ttf','.otf','.ttc'):raise ValueError('此來源格式未經目前字型解析器核對')
            if source in seen:
                if scope not in seen[source]['registry_scopes']:seen[source]['registry_scopes'].append(scope)
                continue
            length=source.stat().st_size
            if not 0<length<=MAX_FONT_BYTES:raise ValueError('單檔字型來源超過可核對範圍')
            if len(seen)>=max_files or report['source_bytes_budgeted']+length>max_bytes or faces_left<=0:reject('字型檔案／位元組／字面預算不足，未當成完整來源');continue
            report['source_bytes_budgeted']+=length;proof=inspect_font(source)
            if file_digest(source)!=proof['hash']:raise ValueError('字型來源在盤點期間變更')
            faces=[]
            for face in proof['faces'][:faces_left]:
                faces.append(dict(index=face['index'],family=str(face.get('family') or '')[:500],style=str(face.get('style') or '')[:200]))
            if len(faces)<len(proof['faces']):reject('集合字面未全部涵蓋')
            faces_left-=len(faces);entry=dict(path=str(source),hash=proof['hash'],faces=faces,registry_scopes=[scope],actual_qt_face_verified=False,source_rights_verified=False);seen[source]=entry;report['files'].append(entry)
        except (ValueError,OSError,KeyError,TypeError) as error:reject(error)
    # Registry entries can outlive a file; discard changed file snapshots as well.
    for entry in list(report['files']):
        try:unchanged=file_digest(entry['path'])==entry['hash']
        except OSError:unchanged=False
        if not unchanged:report['files'].remove(entry);reject('盤點結束前字型來源已變更，未保留新鮮來源宣告')
    return report

def _native_roots():
    import ctypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True);function=kernel.GetWindowsDirectoryW;function.argtypes=[ctypes.c_wchar_p,ctypes.c_uint];function.restype=ctypes.c_uint;buffer=ctypes.create_unicode_buffer(32768);length=function(buffer,len(buffer))
    if not length or length>=len(buffer):raise OSError('Windows字型目錄無法核對')
    local=os.environ.get('LOCALAPPDATA');return dict(MACHINE=Path(buffer.value)/'Fonts',USER=Path(local)/'Microsoft/Windows/Fonts' if local and Path(local).is_absolute() else None)

def _registry_snapshot():
    import winreg
    records=[];notes=[];partial=False;visited=0
    for scope,hive in (('MACHINE',winreg.HKEY_LOCAL_MACHINE),('USER',winreg.HKEY_CURRENT_USER)):
        try:
            with winreg.OpenKey(hive,r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts',0,winreg.KEY_READ|getattr(winreg,'KEY_WOW64_64KEY',0)) as key:
                count=winreg.QueryInfoKey(key)[1]
                take=min(count,20000-visited)
                for index in range(take):
                    visited+=1;name,value,kind=winreg.EnumValue(key,index)
                    if kind in (winreg.REG_SZ,winreg.REG_EXPAND_SZ):records.append(dict(scope=scope,file=value))
                    else:partial=True
                if take<count:partial=True
        except FileNotFoundError:continue
        except OSError:partial=True;notes.append(scope+'字型登錄無法完整讀取')
        if visited>=20000:partial=True;break
    return dict(records=records,partial=partial,notes=notes)

def windows_font_sources():
    if sys.platform!='win32':return dict(status='UNAVAILABLE',scope=SCOPE,files=[],rejected=[],source_bytes_budgeted=0,notes=['目前非Windows；Qt可用名單不代表Windows已安裝來源'])
    try:
        first=_registry_snapshot();report=collect_registered_font_sources(first['records'],_native_roots());last=_registry_snapshot()
        if first['records']!=last['records']:report.update(status='STALE',files=[]);report['notes'].append('盤點期間Windows登錄已改變，請重新盤點')
        elif first['partial'] or last['partial']:report['status']='PARTIAL'
        report['notes'].extend(first['notes']+last['notes']);return report
    except (OSError,ValueError,ImportError):return dict(status='UNAVAILABLE',scope=SCOPE,files=[],rejected=[],source_bytes_budgeted=0,notes=['Windows來源無法核對，未宣稱安裝或實際選字成功'])


def scan_registered_pages(records,roots,*,cancelled=lambda:False,progress=lambda value:None):
    """Bounded per-page I/O while permitting the complete installed catalogue."""
    if not isinstance(records,list) or len(records)>20000:raise ValueError('Registered font catalogue exceeds explicit 20000-record budget')
    combined=dict(status='COMPLETE',scope=SCOPE,files=[],rejected=[],notes=[],source_bytes_budgeted=0,
                  next_offset=0,total_records=len(records));seen={}
    for offset in range(0,len(records),4):
        if cancelled():combined['status']='PAUSED';break
        page=collect_registered_font_sources(records[offset:offset+4],roots,max_files=4,max_bytes=256*1024**2,max_faces=1024,allow_registered_absolute_local=True)
        if page['status']!='COMPLETE':combined['status']='PARTIAL'
        combined['source_bytes_budgeted']+=page['source_bytes_budgeted'];combined['rejected'].extend(page['rejected'])
        for row in page['files']:
            key=(row['path'],row['hash'])
            if key in seen:
                seen[key]['registry_scopes']=sorted(set(seen[key]['registry_scopes']+row['registry_scopes']))
            else:seen[key]=row;combined['files'].append(row)
        combined['next_offset']=min(offset+4,len(records));progress(combined['next_offset'])
    return combined


def windows_font_sources_all(*,cancelled=lambda:False):
    if sys.platform!='win32':return windows_font_sources()
    try:
        first=_registry_snapshot();report=scan_registered_pages(first['records'],_native_roots(),cancelled=cancelled)
        last=_registry_snapshot()
        if first['records']!=last['records']:report.update(status='STALE',files=[]);report['notes'].append('盤點期間字型登錄改變，請重新盤點')
        elif first['partial'] or last['partial']:report['status']='PARTIAL'
        report['notes'].extend(first['notes']+last['notes']);return report
    except (OSError,ValueError,ImportError):return dict(status='UNAVAILABLE',scope=SCOPE,files=[],rejected=[],source_bytes_budgeted=0,notes=['本機來源盤點未完成'])

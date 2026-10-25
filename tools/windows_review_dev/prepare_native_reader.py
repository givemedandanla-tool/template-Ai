"""Prepare a new local runtime from user-provided files. Never downloads Adobe."""
import argparse,hashlib,json,os,shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from template_ai.review_tool.native_reader import digest,AILIB_SHA256,LINGUISTIC_SHA256
from template_ai.review_tool.native_isolation import local_staging_path

def prepare(engine,python,fonts,crt,target,config):
    for p in (engine,python,fonts,crt):local_staging_path(p)
    target=Path(target);config=Path(config)
    local_staging_path(target.parent);local_staging_path(config.parent)
    if target.exists() or config.exists():raise FileExistsError('Choose new runtime and configuration paths; nothing overwritten')
    if target.resolve() in [p.resolve() for p in (engine,python,fonts,crt)]:raise ValueError('Target cannot be an input')
    binary=engine/'Support Files/Contents/Windows'
    if digest(binary/'AILib.dll')!=AILIB_SHA256 or digest(binary/'AdobeLinguistic.dll')!=LINGUISTIC_SHA256:raise ValueError('Unsupported engine build')
    target.mkdir();excluded=[]
    def ignore(folder,names):
        skipped=[]
        for name in names:
            p=Path(folder)/name
            if p.is_symlink() or (p.stat().st_file_attributes&0x400):raise ValueError('Input contains a reparse link')
            # Illustrator.exe is retained solely as signed resource metadata.
            if p.is_file() and (p.suffix.lower()=='.exe' and name.lower()!='illustrator.exe' or name.lower()=='libcef.dll'):
                skipped.append(name);excluded.append(p.relative_to(engine).as_posix())
        return skipped
    shutil.copytree(engine,target/'engine',ignore=ignore)
    shutil.copytree(python,target/'python',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(fonts,target/'support/fonts');shutil.copytree(crt,target/'support/crt')
    binary=target/'engine/Support Files/Contents/Windows';helper=binary/'ReviewToolNativeReader.exe'
    shutil.copyfile(target/'python/pythonw.exe',helper);shutil.copyfile(target/'python/python311.dll',binary/'python311.dll')
    helper.with_suffix('._pth').write_text(str(target/'python/Lib')+'\n'+str(target/'python/DLLs')+'\n',encoding='utf8')
    manifest=dict(version=1,excluded_executables_and_browser=excluded,files={p.relative_to(target).as_posix():digest(p) for p in target.rglob('*') if p.is_file()})
    path=target/'runtime-manifest.local.json';path.write_text(json.dumps(manifest,indent=2),encoding='utf8')
    config.write_text(json.dumps(dict(root=str(target.resolve()),manifest_sha256=digest(path)),indent=2),encoding='utf8')
    print(json.dumps(dict(prepared=True,files=len(manifest['files']),excluded=len(excluded),private_data_upload=False)))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('engine','python','fonts','crt','target','config'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();prepare(a.engine,a.python,a.fonts,a.crt,a.target,a.config)

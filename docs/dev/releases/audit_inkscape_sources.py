"""Read pinned upstream public build-package metadata and verify source access."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'artifacts/inkscape-distribution-audit'
ENV_URL='https://gitlab.com/api/v4/projects/46863172/packages/generic/windows/r88/ink88.7z'
ENV_SHA='fefbd2d14808424ecc942a78b4a2dced8175a01506161c1e85e1d333f09e5bac'
AUDIT_URL='https://raw.githubusercontent.com/givemedandanla-tool/template-Ai/945469e95e9f07ad78d973a904029710869becd5/eecb07e11c176b1e5a575b175cd5f6cfaa1a5fd6/inventory.json'


def download(url,path=None,maximum=700*1024*1024):
    h=hashlib.sha256();size=0
    dest=path.open('xb') if path else None
    try:
        with urllib.request.urlopen(url,timeout=45) as stream:
            while True:
                block=stream.read(1048576)
                if not block:break
                size+=len(block)
                if size>maximum:raise ValueError('Source size exceeds bound')
                h.update(block)
                if dest:dest.write(block)
        return dict(status='AVAILABLE',bytes=size,sha256=h.hexdigest(),url=url)
    finally:
        if dest:dest.close()


def fields(path):
    result={};key=None
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('%') and line.endswith('%'):key=line.strip('%');result[key]=[]
        elif line and key:result[key].append(line)
    return result


def main():
    if os.name!='nt' or os.environ.get('GITHUB_ACTIONS')!='true':raise RuntimeError('Fresh Windows runner only')
    OUT.mkdir(parents=True,exist_ok=True)
    archive=OUT/'ink88.7z';proof=download(ENV_URL,archive)
    if proof['sha256']!=ENV_SHA:raise RuntimeError('Upstream environment checksum mismatch')
    listing=subprocess.run(['7z','l','-slt',str(archive)],capture_output=True,text=True,encoding='utf-8',errors='replace',check=True).stdout
    selected=[]
    for line in listing.splitlines():
        if not line.startswith('Path = '):continue
        name=line[7:].replace('\\','/')
        if '/var/lib/pacman/local/' in '/'+name or '/share/licenses/' in '/'+name:selected.append(name)
    if not selected:raise RuntimeError('No package/source metadata found; not an empty pass')
    selection=OUT/'selected.txt';selection.write_text('\n'.join(selected),encoding='utf-8')
    target=OUT/'upstream-metadata'
    subprocess.run(['7z','x','-y','-scsUTF-8','-o'+str(target),'-i@'+str(selection),str(archive)],stdout=subprocess.DEVNULL,check=True)
    with urllib.request.urlopen(AUDIT_URL,timeout=30) as r:audited=json.load(r)
    wanted={r['path'].casefold() for r in audited['inventory']}
    owners=[];claimed=set()
    for desc in target.rglob('desc'):
        package=fields(desc)
        if 'NAME' not in package:continue
        file_path=desc.parent/'files'
        if not file_path.is_file():continue
        matches=[]
        for name in fields(file_path).get('FILES',[]):
            for prefix in ['ucrt64/','mingw64/']:
                if name.startswith(prefix) and name[len(prefix):].casefold() in wanted:
                    matches.append(name[len(prefix):]);claimed.add(name[len(prefix):].casefold())
        if matches:
            owners.append(dict(name=package['NAME'][0],base=package.get('BASE',package['NAME'])[0],
                version=package['VERSION'][0],licenses=package.get('LICENSE',[]),upstream=package.get('URL',[]),
                owned_runtime_files=matches,builddate=package.get('BUILDDATE',[])))
    if not owners:raise RuntimeError('Runtime package owner lookup found no matches')
    specs={(r['base'],r['version']) for r in owners}
    def source(spec):
        base,version=spec;url='https://repo.msys2.org/mingw/sources/'+base+'-'+version+'.src.tar.zst'
        try:return dict(base=base,version=version,**download(url,maximum=512*1024*1024))
        except Exception as error:return dict(base=base,version=version,status='ACCESS_UNRESOLVED',url=url,error=str(error)[:160])
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:sources=list(pool.map(source,sorted(specs)))
    licenses=[]
    for path in target.rglob('*'):
        if path.is_file() and '/share/licenses/' in path.as_posix() and path.stat().st_size<=200000:
            licenses.append(dict(path=path.relative_to(target).as_posix(),text=path.read_text(encoding='utf-8',errors='replace')))
    result=dict(kind='UPSTREAM_ENVIRONMENT_AND_SOURCE_ACCESS_AUDIT_NOT_RELEASE',environment=proof,
        metadata_selected=len(selected),runtime_owners=owners,corresponding_package_sources=sources,
        unclaimed_runtime_files=sorted(wanted-claimed),license_texts=licenses,
        source_access_counts={s:sum(r['status']==s for r in sources) for s in ['AVAILABLE','ACCESS_UNRESOLVED']})
    (OUT/'source-environment.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(runtime_packages=len(owners),source_access_counts=result['source_access_counts'],unclaimed=len(wanted-claimed))))


if __name__=='__main__':main()

"""Preserve original dependency-license bytes from the exact upstream IDW88.

This release-data step supplements the unmodified runtime before its final pin
is frozen. It does not add upstream build programs or run any downloaded code.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'tools'), str(Path(__file__).parent)]
from bundled_inkscape_build import STAGED, fetch, digest, write

ENVIRONMENT = dict(url='https://gitlab.com/api/v4/projects/46863172/packages/generic/windows/r88/ink88.7z',
                   bytes=524800330, sha256='fefbd2d14808424ecc942a78b4a2dced8175a01506161c1e85e1d333f09e5bac')


def fetch_license_archive():
    """Retry transport corruption without accepting different upstream bytes."""
    target = ROOT/'build/ink88-license-source.7z'
    attempts = []
    for attempt in range(1, 4):
        try:
            archive = fetch(ENVIRONMENT, target)
        except (OSError, RuntimeError) as error:
            partial = target.with_suffix(target.suffix+'.partial')
            attempts.append(dict(attempt=attempt, state='REJECTED',
                                 error_type=type(error).__name__,
                                 bytes=partial.stat().st_size if partial.is_file() else None,
                                 sha256=digest(partial) if partial.is_file() else None))
            write(ROOT/'artifacts/upstream-license-download.json',
                  dict(expected=ENVIRONMENT, attempts=attempts))
            if attempt == 3:
                raise
        else:
            attempts.append(dict(attempt=attempt, state='VERIFIED',
                                 bytes=archive.stat().st_size, sha256=digest(archive)))
            write(ROOT/'artifacts/upstream-license-download.json',
                  dict(expected=ENVIRONMENT, attempts=attempts))
            return archive


def main():
    if os.name != 'nt' or os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('Fresh authorized Windows runner only')
    archive = fetch_license_archive()
    listing = subprocess.run(['7z','l','-slt','-sccUTF-8',str(archive)],capture_output=True,text=True,encoding='utf-8',errors='strict',check=True).stdout
    selected = []
    for line in listing.splitlines():
        if line.startswith('Path = '):
            name = line[7:].replace('\\','/')
            if '/share/licenses/' in '/'+name:
                path = Path(name)
                if path.is_absolute() or '..' in path.parts or ':' in name:
                    raise RuntimeError('Unexpected upstream license path')
                selected.append(name)
    if not selected:
        raise RuntimeError('Empty upstream license selection')
    selection = ROOT/'build/license-selection.txt'
    selection.write_text('\n'.join(selected),encoding='utf-8')
    destination = STAGED/'TEMPLATE_AI_DEPENDENCY_LICENSES'
    if destination.exists():
        raise RuntimeError('Do not overwrite staged license notices')
    subprocess.run(['7z','x','-y','-scsUTF-8','-o'+str(destination),'-i@'+str(selection),str(archive)],stdout=subprocess.DEVNULL,check=True)
    files = [p for p in destination.rglob('*') if p.is_file()]
    if not 200 <= len(files) <= 2000 or sum(p.stat().st_size for p in files) > 16*1024*1024:
        raise RuntimeError('Unexpected upstream license inventory')
    write(destination/'SOURCE.json',dict(kind='ORIGINAL_LICENSE_BYTES_FROM_UPSTREAM_BUILD_ENVIRONMENT',
          environment=ENVIRONMENT,files=len(files),scope='Includes reference notices for build dependencies not necessarily present in the runtime'))
    manifest = STAGED/'manifest.json'
    value = json.loads(manifest.read_text(encoding='utf-8'))
    value['files'] = [dict(path=p.relative_to(STAGED).as_posix(),bytes=p.stat().st_size,sha256=digest(p))
                      for p in sorted(STAGED.rglob('*')) if p.is_file() and p != manifest]
    write(manifest,value)
    pin_path = ROOT/'build/release/inkscape-runtime-pin.json'
    pin = json.loads(pin_path.read_text())
    pin.update(manifest_sha256=digest(manifest),files=len(value['files']))
    write(pin_path,pin)
    write(ROOT/'artifacts/dependency-license-verification.json',dict(status='PASS',environment=ENVIRONMENT,
          original_license_files=len(files),runtime_files=len(value['files']),manifest_sha256=pin['manifest_sha256']))
    archive.unlink()
    print(json.dumps(dict(status='LICENSE_NOTICES_ADDED_BEFORE_FREEZING',license_files=len(files))))


if __name__ == '__main__':
    main()

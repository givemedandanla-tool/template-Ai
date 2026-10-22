"""Pinned, locally executed assembly of the unmodified official Windows engine.

Only the fresh authorized Windows release runner downloads public dependencies.
The shipped application never imports this module or downloads an engine.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT/'tools/inkscape_distribution_lock.json'
STAGED = ROOT/'build/inkscape-staged'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def fetch(row, path):
    if path.is_file() and digest(path) == row['sha256']:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.partial')
    count = 0
    with urllib.request.urlopen(row['url'], timeout=60) as source, temporary.open('wb') as dest:
        for block in iter(lambda: source.read(1048576), b''):
            count += len(block)
            if count > row['bytes']:
                raise RuntimeError('Upstream object exceeds its locked size')
            dest.write(block)
    if count != row['bytes'] or digest(temporary) != row['sha256']:
        raise RuntimeError('Upstream object fails its locked size/hash')
    temporary.replace(path)
    return path


def prepare(lock):
    installed = Path(r'C:\Program Files\Inkscape')
    proof = fetch(lock['inventory'], ROOT/'build/upstream-inventory.json')
    upstream = json.loads(proof.read_text(encoding='utf-8'))
    expected = {r['path']: r for r in upstream['inventory']}
    actual = {p.relative_to(installed).as_posix(): p for p in installed.rglob('*') if p.is_file()}
    if not expected or actual.keys() != expected.keys():
        raise RuntimeError('Installed official runtime differs from the audited file inventory')
    for name, path in actual.items():
        row = expected[name]
        if path.is_symlink() or path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise RuntimeError('Official runtime identity mismatch: '+name)
    if STAGED.exists():
        raise RuntimeError('Refuse to reuse an unqualified staged runtime')
    shutil.copytree(installed, STAGED)
    write(STAGED/'TEMPLATE_AI_SOURCE_MAP.json', lock)
    shutil.copy2(ROOT/'docs/dev/releases/INKSCAPE_REDISTRIBUTION.md', STAGED/'TEMPLATE_AI_REDISTRIBUTION.md')
    rows = [dict(path=p.relative_to(STAGED).as_posix(), bytes=p.stat().st_size, sha256=digest(p))
            for p in sorted(STAGED.rglob('*')) if p.is_file()]
    manifest = STAGED/'manifest.json'
    write(manifest, dict(schema_version=1, kind='BUNDLED_INKSCAPE_RUNTIME', version=lock['version'],
                         executable='bin/inkscape.exe', upstream_inventory_sha256=lock['inventory']['sha256'], files=rows))
    write(ROOT/'build/release/inkscape-runtime-pin.json', dict(version=lock['version'],
          manifest_sha256=digest(manifest), executable_sha256=lock['executable_sha256'], files=len(rows)))
    print(json.dumps(dict(status='PREPARED_VERIFIED_OFFICIAL_RUNTIME', files=len(rows))))


def install(lock):
    target = ROOT/'dist/TemplateAI/engines/inkscape'
    pin = json.loads((ROOT/'build/release/inkscape-runtime-pin.json').read_text())
    if digest(STAGED/'manifest.json') != pin['manifest_sha256'] or pin['version'] != lock['version']:
        raise RuntimeError('Staged engine identity changed before installation')
    if target.exists():
        raise RuntimeError('Refuse to overwrite an existing packaged engine')
    shutil.copytree(STAGED, target)


def sources(lock):
    cache = ROOT/'artifacts/corresponding-source-cache'
    def one(row):
        return fetch(row, cache/row['asset_name'])
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        files = list(pool.map(one, lock['corresponding_sources']))
    target = ROOT/'artifacts/inkscape-1.4.2-corresponding-sources.zip'
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        archive.write(LOCK, 'SOURCE_MAP.json')
        archive.write(ROOT/'docs/dev/releases/INKSCAPE_REDISTRIBUTION.md', 'README.md')
        archive.write(STAGED/'share/inkscape/doc/LICENSE', 'INKSCAPE-GPL-3.0.txt')
        for path in files:
            archive.write(path, 'sources/'+path.name)
    write(ROOT/'artifacts/corresponding-source-verification.json', dict(status='PASS',
          asset=target.name, bytes=target.stat().st_size, sha256=digest(target), archives_verified=len(files),
          source_map_sha256=digest(LOCK)))
    shutil.rmtree(cache)


def vendor_inventory(folder):
    """An exact allow-list for public upstream files, never a broad exemption."""
    manifest = folder/'engines/inkscape/manifest.json'
    pin = json.loads((folder/'_internal/release-info.json').read_text(encoding='utf-8'))['inkscape_runtime']
    if digest(manifest) != pin['manifest_sha256']:
        raise RuntimeError('Packaged vendor manifest differs from the frozen release pin')
    value = json.loads(manifest.read_text(encoding='utf-8'))
    expected = {'engines/inkscape/'+r['path']: r for r in value['files']}
    actual = {p.relative_to(folder).as_posix() for p in manifest.parent.rglob('*') if p.is_file()}
    if actual != expected.keys() | {'engines/inkscape/manifest.json'}:
        raise RuntimeError('Unlisted file in public vendor component')
    for name, row in expected.items():
        path = folder/name
        if path.is_symlink() or path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise RuntimeError('Vendor file changed after actual-EXE acceptance: '+name)
    return set(expected) | {'engines/inkscape/manifest.json'}


def verify_source_archive(path):
    lock = json.loads(LOCK.read_text(encoding='utf-8'))
    expected = {'sources/'+r['asset_name']: r for r in lock['corresponding_sources']}
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != expected.keys() | {'SOURCE_MAP.json','README.md','INKSCAPE-GPL-3.0.txt'}:
            raise RuntimeError('Corresponding-source archive inventory differs')
        if archive.read('SOURCE_MAP.json') != LOCK.read_bytes():
            raise RuntimeError('Corresponding-source lock differs')
        for name, row in expected.items():
            h = hashlib.sha256()
            with archive.open(name) as stream:
                for block in iter(lambda: stream.read(1048576), b''):
                    h.update(block)
            if archive.getinfo(name).file_size != row['bytes'] or h.hexdigest() != row['sha256']:
                raise RuntimeError('Corresponding source failed verification: '+name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'install', 'sources'])
    args = parser.parse_args()
    if os.name != 'nt' or os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('Only the authorized fresh native Windows runner assembles public dependencies')
    globals()[args.command](json.loads(LOCK.read_text(encoding='utf-8')))

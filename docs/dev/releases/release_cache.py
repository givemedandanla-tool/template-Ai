"""Content-verified Windows build inputs; never imported by the product."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def load_locks(root=ROOT):
    wheels = json.loads((root/'.github/windows-wheels-lock.json').read_text())
    assets = json.loads((root/'.github/release-assets-lock.json').read_text())
    if wheels['platform'] != 'windows-x64' or wheels['python_minor'] != '3.11':
        raise ValueError('Unsupported wheel target; regenerate the reviewed lock')
    for group in (wheels['inputs'], assets['engine']['inputs']):
        for name, expected in group.items():
            if sha(root/name) != expected:
                raise ValueError('Changed build input requires a new reviewed cache lock: '+name)
    return wheels, assets


def cache_key(root=ROOT):
    wheels, assets = load_locks(root)
    body = json.dumps([1, sys.version.split()[0], 'windows-x64', wheels, assets], sort_keys=True).encode()
    return 'template-ai-verified-inputs-v1-'+hashlib.sha256(body).hexdigest()


def member_name(name):
    p = PurePosixPath(name)
    if (not name or '\\' in name or ':' in name or p.is_absolute() or '..' in p.parts
            or p.as_posix() != name):
        raise ValueError('Unsafe archive member')
    return p


def verify_object(path, row):
    path = Path(path)
    return (path.is_file() and not path.is_symlink() and path.stat().st_size == row['bytes']
            and sha(path) == row['sha256'])


def fetch_verified(row, folder, *, opener=urllib.request.urlopen):
    name = member_name(row['filename'])
    if len(name.parts) != 1:
        raise ValueError('Cache filename must be a basename')
    folder = Path(folder)
    if folder.is_symlink():
        raise ValueError('Cache directory may not be a symlink')
    folder.mkdir(parents=True, exist_ok=True)
    target = folder/name.name
    start = time.perf_counter()
    if verify_object(target, row):
        return target, dict(file=name.name, state='HIT_VALIDATED', bytes=row['bytes'],
                            downloaded_bytes=0, seconds=time.perf_counter()-start)
    invalid = target.exists() or target.is_symlink()
    if invalid:
        if not target.is_file() or target.is_symlink():
            raise ValueError('Unexpected cache entry type')
        target.unlink()
    temporary = folder/(name.name+'.partial')
    if temporary.is_symlink():
        raise ValueError('Partial cache entry may not be a symlink')
    downloaded = 0
    for attempt in range(3):
        try:
            count = 0
            with opener(row['url'], timeout=60) as source, temporary.open('wb') as dest:
                for block in iter(lambda: source.read(1048576), b''):
                    count += len(block)
                    downloaded += len(block)
                    if count > row['bytes']:
                        raise ValueError('Download exceeds locked size')
                    dest.write(block)
            if not verify_object(temporary, row):
                raise ValueError('Downloaded object does not match locked size/hash')
            temporary.replace(target)
            return target, dict(file=name.name, state='INVALID_REPLACED' if invalid else 'MISS_FETCHED_VERIFIED',
                                bytes=row['bytes'], downloaded_bytes=downloaded,
                                attempts=attempt+1, seconds=time.perf_counter()-start)
        except (OSError, ValueError):
            temporary.unlink(missing_ok=True)
            if attempt == 2:
                raise


def validate_engine(folder, pin, *, root=ROOT):
    folder = Path(folder)
    manifest = folder/'manifest.json'
    if folder.is_symlink() or not manifest.is_file() or sha(manifest) != pin['manifest_sha256']:
        raise ValueError('Engine manifest differs from the reviewed release pin')
    value = json.loads(manifest.read_bytes())
    if value['version'] != pin['version'] or value['executable'] != 'bin/inkscape.exe':
        raise ValueError('Engine version/executable differs')
    rows = value['files']
    if len(rows) != pin['files']:
        raise ValueError('Incomplete engine inventory')
    actual = set()
    for path in folder.rglob('*'):
        if path.is_symlink():
            raise ValueError('Unexpected engine symlink')
        if path.is_file():
            name = path.relative_to(folder).as_posix().casefold()
            if name in actual:
                raise ValueError('Case-colliding engine file')
            actual.add(name)
    expected = {}
    for row in rows:
        name = member_name(row['path']).as_posix()
        if name.casefold() in expected or name == 'manifest.json':
            raise ValueError('Duplicate engine member')
        expected[name.casefold()] = name
        p = folder/name
        if not verify_object(p, row):
            raise ValueError('Engine content differs: '+name)
    if actual != set(expected) | {'manifest.json'}:
        raise ValueError('Unlisted engine payload')
    if (folder/'TEMPLATE_AI_SOURCE_MAP.json').read_bytes() != (root/'tools/inkscape_distribution_lock.json').read_bytes():
        raise ValueError('Engine source map changed')
    if (folder/'TEMPLATE_AI_REDISTRIBUTION.md').read_bytes() != (root/'docs/dev/releases/INKSCAPE_REDISTRIBUTION.md').read_bytes():
        raise ValueError('Engine licensing instructions changed')
    executable = next(row for row in rows if row['path'] == 'bin/inkscape.exe')
    return dict(version=pin['version'], manifest_sha256=pin['manifest_sha256'],
                executable_sha256=executable['sha256'], files=len(rows))


def extract_engine(archive, target, pin, *, root=ROOT):
    if target.exists():
        raise FileExistsError('Do not overwrite an assembled runtime')
    prefix = 'TemplateAI/engines/inkscape/'
    with zipfile.ZipFile(archive) as source:
        names = source.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP member')
        selected = [info for info in source.infolist() if info.filename.startswith(prefix)]
        if len(selected) != pin['files']+1:
            raise ValueError('Cached release has an unexpected engine member count')
        # Validate every selected name/type BEFORE writing any member.
        for info in selected:
            member_name(info.filename[len(prefix):])
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode) or info.is_dir():
                raise ValueError('Unexpected vendor member type')
        target.mkdir(parents=True)
        for info in selected:
            dest = target/info.filename[len(prefix):]
            dest.parent.mkdir(parents=True, exist_ok=True)
            with source.open(info) as src, dest.open('xb') as dst:
                shutil.copyfileobj(src, dst, 1048576)
    return validate_engine(target, pin, root=root)


def prepare(cache, output, *, root=ROOT):
    """Same content verification on cold, local-warm and Actions-restored input."""
    start = time.perf_counter()
    wheels, assets = load_locks(root)
    cache, output = Path(cache), Path(output)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        wheel_results = list(pool.map(lambda row: fetch_verified(row, cache/'wheels'), wheels['wheels']))
    engine_zip, engine_record = fetch_verified(assets['engine_archive'], cache/'assets')
    source_zip, source_record = fetch_verified(assets['sources'], cache/'assets')
    expected_cache = {'wheels/'+row['filename'] for row in wheels['wheels']}
    expected_cache |= {'assets/'+assets[key]['filename'] for key in ('engine_archive','sources')}
    actual_cache = set()
    for path in cache.rglob('*'):
        if path.is_symlink():
            raise ValueError('Cache contains a symlink')
        if path.is_file():
            actual_cache.add(path.relative_to(cache).as_posix())
    if actual_cache != expected_cache:
        raise ValueError('Cache contains unlisted files; never upload arbitrary workspace data')
    stage = root/'build/inkscape-staged'
    engine_start = time.perf_counter()
    if stage.exists():
        try:
            pin = validate_engine(stage, assets['engine'], root=root)
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            if stage.is_symlink():
                raise ValueError('Staged engine symlink')
            shutil.rmtree(stage)
            pin = extract_engine(engine_zip, stage, assets['engine'], root=root)
            engine_record['assembly'] = 'INVALID_STAGE_REBUILT'
        else:
            engine_record['assembly'] = 'EXISTING_STAGE_REVALIDATED'
    else:
        pin = extract_engine(engine_zip, stage, assets['engine'], root=root)
        engine_record['assembly'] = 'EXTRACTED_VERIFIED_RELEASE_ENGINE'
    engine_record['verification_seconds'] = time.perf_counter()-engine_start
    write(root/'build/release/inkscape-runtime-pin.json', pin)
    # Reuse the original 125-object verifier, not a weaker ZIP-only check.
    sys.path.insert(0, str(root/'tools'))
    from bundled_inkscape_build import verify_source_archive
    verify_source_archive(source_zip)
    target = root/'artifacts'/assets['sources']['filename']
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if not verify_object(target, assets['sources']):
            raise ValueError('Existing source asset changed')
    else:
        try:
            os.link(source_zip, target)
        except OSError:
            shutil.copy2(source_zip, target)
    proof = dict(status='PASS', asset=target.name, bytes=target.stat().st_size, sha256=sha(target),
                 archives_verified=125, source_map_sha256=sha(root/'tools/inkscape_distribution_lock.json'),
                 url=assets['sources']['url'], reuse_release=assets['source_release'])
    write(root/'artifacts/corresponding-source-verification.json', proof)
    records = [record for _, record in wheel_results]+[engine_record, source_record]
    report = dict(status='PASS', cache_key=cache_key(root), files=len(records), wheels=len(wheel_results),
                  engine_files=pin['files'], source_archives=125, records=records,
                  downloaded_bytes=sum(row['downloaded_bytes'] for row in records),
                  seconds=time.perf_counter()-start)
    write(output, report)
    return report


def install_dependencies(cache, *, root=ROOT):
    wheels, _ = load_locks(root)
    if sys.platform != 'win32' or sys.version_info[:2] != (3, 11):
        raise ValueError('Pinned wheels require Windows Python3.11 x64')
    rows = []
    for row in wheels['wheels']:
        if not verify_object(Path(cache)/'wheels'/row['filename'], row):
            raise ValueError('Wheel cache changed before installation')
        rows.append(row['name']+'=='+row['version']+' --hash=sha256:'+row['sha256'])
    requirements = root/'build/windows-wheels-hashed.txt'
    requirements.parent.mkdir(parents=True, exist_ok=True)
    requirements.write_text('\n'.join(rows)+'\n')
    subprocess.run([sys.executable, '-m', 'pip', '--disable-pip-version-check', 'install', '--no-input',
                    '--no-index', '--find-links', str(Path(cache)/'wheels'), '--only-binary=:all:',
                    '--require-hashes', '--no-deps', '-r', str(requirements)], check=True)
    subprocess.run([sys.executable, '-m', 'pip', 'check'], check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['key', 'prepare', 'install'])
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.command == 'key':
        print(cache_key())
    elif args.command == 'prepare':
        print(json.dumps(prepare(args.cache, args.output)))
    else:
        install_dependencies(args.cache)

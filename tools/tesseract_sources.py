"""Pinned corresponding source for the bundled OCR CLI; never uploads user data.

Input archives remain compressed inside a ZIP_STORED release attachment.  Every
cache hit and downloaded attachment is checked against the committed source lock.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'tools/tesseract_sources_lock.json'
NOTICES = ROOT / 'docs/third_party/tesseract'
RUNTIME_LOCK = ROOT / 'tools/tesseract_distribution_lock.json'


def _hash(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            result.update(block)
    return result.hexdigest()


def _json(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def _name(value):
    if (not isinstance(value, str) or not value or '\\' in value
            or PurePosixPath(value).name != value or value in ('.', '..')
            or any(ord(c) < 32 for c in value)):
        raise ValueError('Source archive name must be a single safe filename')
    return value


def load_lock():
    document = json.loads(LOCK.read_text(encoding='utf-8'))
    if document.get('schema_version') != 1 or document.get('legal_status') != 'REVIEWED':
        raise ValueError('OCR source and license review is incomplete')
    rows = document.get('archives')
    if not isinstance(rows, list) or not rows:
        raise ValueError('OCR corresponding-source inventory is empty')
    names = set()
    for row in rows:
        name = _name(row['asset_name'])
        if (name in names or type(row.get('bytes')) is not int or row['bytes'] <= 0
                or not re.fullmatch('[0-9a-f]{64}', row.get('sha256', ''))
                or not row.get('url', '').startswith('https://')):
            raise ValueError('Invalid or duplicate pinned OCR source')
        names.add(name)
    if document.get('archive_count') != len(rows):
        raise ValueError('OCR source count does not match the lock')
    runtime = json.loads(RUNTIME_LOCK.read_text(encoding='utf-8'))
    if runtime.get('installer', {}).get('sha256') != document.get('installer_sha256'):
        raise ValueError('OCR source review belongs to another runtime installer')
    runtime_files = {row['path'] for row in runtime['runtime_files']}
    covered = {name for row in rows for name in row.get('runtime_files', [])}
    if covered != runtime_files:
        raise ValueError('OCR source mapping does not cover the actual runtime closure')
    return document


def _version():
    tree = ast.parse((ROOT / 'template_ai/review_tool/__init__.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__version__' for t in node.targets):
            value = ast.literal_eval(node.value)
            if isinstance(value, str) and re.fullmatch(r'\d+\.\d+\.\d+-beta\.\d+', value):
                return value
    raise ValueError('Review component version is unavailable')


def _pinned(path, row):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('OCR source must be an ordinary file: ' + row['asset_name'])
    if path.stat().st_size != row['bytes'] or _hash(path) != row['sha256']:
        raise ValueError('OCR corresponding-source bytes differ: ' + row['asset_name'])


def _obtain(cache, row):
    target = cache / row['asset_name']
    if target.exists() or target.is_symlink():
        _pinned(target, row)
        return target, 'VERIFIED_CACHE_HIT'
    seed = ROOT / 'build/tesseract-research/sources' / row['asset_name']
    fd, temporary = tempfile.mkstemp(prefix='.ocr-source-', dir=cache)
    os.close(fd)
    temporary = Path(temporary)
    try:
        if seed.exists():
            _pinned(seed, row)
            shutil.copyfile(seed, temporary)
            origin = 'VERIFIED_LOCAL_SEED'
        else:
            request = urllib.request.Request(row['url'], headers={'User-Agent': 'TemplateAIReview-corresponding-source/1'})
            total = 0
            with urllib.request.urlopen(request, timeout=45) as response, temporary.open('wb') as out:
                for block in iter(lambda: response.read(1048576), b''):
                    total += len(block)
                    if total > row['bytes']:
                        raise ValueError('OCR source exceeded its pinned byte budget')
                    out.write(block)
            origin = 'DOWNLOADED_AND_VERIFIED'
        _pinned(temporary, row)
        os.replace(temporary, target)
        return target, origin
    finally:
        temporary.unlink(missing_ok=True)


def _documents(lock):
    result = {}
    files = lock.get('notice_files', [])
    if not files:
        raise ValueError('OCR source license notices are missing')
    for row in files:
        relative = PurePosixPath(row['path'])
        if relative.is_absolute() or '..' in relative.parts or '\\' in row['path']:
            raise ValueError('Invalid OCR notice path')
        path = NOTICES.joinpath(*relative.parts)
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(NOTICES.resolve()):
            raise ValueError('OCR notice is not a regular repository file')
        if path.stat().st_size != row['bytes'] or _hash(path) != row['sha256']:
            raise ValueError('OCR notice differs from reviewed bytes: ' + row['path'])
        result['notices/' + relative.as_posix()] = path.read_bytes()
    result['SOURCE_LOCK.json'] = LOCK.read_bytes()
    result['RUNTIME_DISTRIBUTION_LOCK.json'] = RUNTIME_LOCK.read_bytes()
    result['SOURCES_MANIFEST.json'] = _json(dict(schema_version=1,
        version=_version(), archive_count=len(lock['archives']),
        installer_sha256=lock['installer_sha256'], source_lock_sha256=_hash(LOCK),
        archives=lock['archives'], notice_files=lock['notice_files']))
    return result


def _write_member(archive, name, data):
    info = zipfile.ZipInfo(name, date_time=(2024, 6, 6, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data)


def verify(archive):
    """Check every inner source archive, notice and lock against current pins."""
    archive = Path(archive)
    lock = load_lock()
    documents = _documents(lock)
    expected = set(documents) | {'archives/' + row['asset_name'] for row in lock['archives']}
    with zipfile.ZipFile(archive) as stream:
        names = stream.namelist()
        if len(names) != len(set(names)) or set(names) != expected:
            raise ValueError('OCR source ZIP has duplicate, missing or unlisted members')
        for info in stream.infolist():
            kind = (info.external_attr >> 16) & 0o170000
            if info.is_dir() or kind not in (0, 0o100000) or info.compress_type != zipfile.ZIP_STORED:
                raise ValueError('OCR source ZIP contains a non-regular or recompressed member')
        for name, data in documents.items():
            info = stream.getinfo(name)
            if info.file_size != len(data) or stream.read(name) != data:
                raise ValueError('OCR source ZIP notice or lock differs: ' + name)
        for row in lock['archives']:
            name = 'archives/' + row['asset_name']
            info = stream.getinfo(name)
            if info.file_size != row['bytes'] or info.compress_type != zipfile.ZIP_STORED:
                raise ValueError('OCR source ZIP archive size or method differs: ' + name)
            result = hashlib.sha256()
            with stream.open(name) as source:
                for block in iter(lambda: source.read(1048576), b''):
                    result.update(block)
            if result.hexdigest() != row['sha256']:
                raise ValueError('OCR source ZIP contains changed source: ' + name)
    return dict(status='PASS', archive_count=len(lock['archives']),
        archives_verified=len(lock['archives']), notices_verified=len(lock['notice_files']),
        source_lock_sha256=_hash(LOCK),
        archive=dict(name=archive.name, path=str(archive), bytes=archive.stat().st_size, sha256=_hash(archive)))


def prepare(cache_dir, output_dir):
    """Reuse verified archives and assemble an immutable release source asset."""
    lock = load_lock()
    documents = _documents(lock)
    cache = Path(cache_dir) / 'sources'
    output = Path(output_dir)
    cache.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    inputs = []
    for row in lock['archives']:
        path, origin = _obtain(cache, row)
        inputs.append((row, path, origin))
    target = output / ('TemplateAIReview-' + _version() + '-ocr-corresponding-source.zip')
    temporary = target.with_suffix('.zip.partial')
    if temporary.exists() or temporary.is_symlink():
        raise ValueError('An incomplete OCR source assembly already exists')
    try:
        with zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for name, data in sorted(documents.items()):
                _write_member(archive, name, data)
            for row, path, _ in inputs:
                info = zipfile.ZipInfo('archives/' + row['asset_name'], date_time=(2024, 6, 6, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = 0o100644 << 16
                with archive.open(info, 'w', force_zip64=True) as out, path.open('rb') as source:
                    shutil.copyfileobj(source, out, length=1048576)
        report = verify(temporary)
        if target.exists():
            if _hash(target) != _hash(temporary):
                raise ValueError('Existing OCR source asset differs; it will not be overwritten')
            temporary.unlink()
        else:
            os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    report['archive']['name'] = target.name
    report['archive']['path'] = str(target)
    report['cache_inputs'] = [dict(asset_name=row['asset_name'], origin=origin) for row, _, origin in inputs]
    report['license_paths'] = [str(NOTICES / row['path']) for row in lock['notice_files']]
    report['legal_status'] = lock['legal_status']
    (output / 'ocr-source-verification.json').write_bytes(_json(report))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'verify'])
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--archive', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        if args.cache is None or args.output is None:
            parser.error('prepare requires --cache and --output')
        result = prepare(args.cache, args.output)
    else:
        if args.archive is None:
            parser.error('verify requires --archive')
        result = verify(args.archive)
    print(json.dumps(result, ensure_ascii=False))

"""Export committed review source and public dependencies to a NEW offline directory.

Developer utility, Windows x64. No network calls, no release, no private data discovery.
Supply a verified official Python NuGet archive, official Inkscape MSI and public wheels.
"""
from __future__ import annotations

import argparse
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

from offline_start import BRANCH, digest, safe_member, write_new

SOURCE_PATHS = ['template_ai', 'review_app.py', 'requirements-lock.txt', 'START_REVIEW_WINDOWS.bat',
                'tools/local_start.py', 'tools/windows_review_dev/illustrator_bridge',
                'tools/windows_review_dev/usb']
FORBIDDEN_SUFFIXES = {'.ai', '.pdf', '.ttf', '.otf', '.woff', '.woff2', '.db', '.sqlite', '.sqlite3', '.log', '.pyc', '.pdb'}
SOURCE_SUFFIXES = {'.py', '.jsx', '.cjs', '.json', '.md', '.txt', '.bat', '.cmd'}


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.PIPE, timeout=120,
                                   env=dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0'))


def export_source(repo, output, commit):
    # git archive can prefetch unrelated blobs in a partial clone. Read only local
    # allowlisted working files, checking every byte against the committed tree.
    raw = git(repo, 'ls-tree', '-rz', '--full-tree', commit, '--', *SOURCE_PATHS)
    if not raw:
        raise ValueError('No committed source files')
    for entry in raw.rstrip(b'\0').split(b'\0'):
        header, encoded_name = entry.split(b'\t', 1)
        mode, kind, expected = header.decode('ascii').split()
        name = encoded_name.decode('utf-8')
        if kind != 'blob' or mode != '100644' or Path(name).suffix.lower() not in SOURCE_SUFFIXES:
            raise ValueError('Unexpected source file in export: ' + name)
        data = safe_member(repo, name).read_bytes()
        def git_blob(value):
            return hashlib.sha1(b'blob ' + str(len(value)).encode() + b'\0' + value).hexdigest()
        if git_blob(data) != expected:
            data = data.replace(b'\r\n', b'\n')
            if git_blob(data) != expected:
                raise ValueError('Local source does not match commit: ' + name)
        target = safe_member(output, name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)


def python_runtime(archive, output, expected):
    if digest(archive) != expected:
        raise ValueError('Python archive hash mismatch')
    with zipfile.ZipFile(archive) as zipped:
        for item in zipped.infolist():
            if not item.filename.startswith('tools/') or item.is_dir():
                continue
            name = item.filename[len('tools/'):]
            target = safe_member(output, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(item) as source, target.open('xb') as dest:
                shutil.copyfileobj(source, dest)
    if not (output / 'python.exe').exists() or not (output / 'LICENSE.txt').exists():
        raise ValueError('Incomplete official Python runtime or license')


def install_wheels(wheels, output):
    lines = []
    names = set()
    for wheel in sorted(wheels.glob('*.whl')):
        with zipfile.ZipFile(wheel) as archive:
            candidates = [n for n in archive.namelist() if n.endswith('.dist-info/METADATA')]
            if len(candidates) != 1:
                raise ValueError('Invalid wheel metadata')
            meta = BytesParser().parsebytes(archive.read(candidates[0]))
        name, version = meta['Name'], meta['Version']
        normalized = re.sub(r'[-_.]+', '-', name).lower()
        if normalized in names or not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or not re.fullmatch(r'[A-Za-z0-9_.+!-]+', version):
            raise ValueError('Duplicate or invalid wheel')
        names.add(normalized)
        shutil.copyfile(wheel, output / wheel.name)
        lines.append(f'{name}=={version} --hash=sha256:{digest(wheel)}')
    if not {'pyside6', 'pywin32'} <= names:
        raise ValueError('Missing GUI or COM dependencies')
    return '\n'.join(lines) + '\n'


def copy_engine(extracted, output):
    candidates = list(extracted.rglob('bin/inkscape.exe'))
    if len(candidates) != 1:
        raise ValueError('Official Inkscape archive has an unexpected layout')
    engine = candidates[0].parent.parent
    for path in sorted(engine.rglob('*')):
        if path.is_symlink():
            raise ValueError('Unexpected vendor symbolic link')
        if not path.is_file():
            continue
        rel = path.relative_to(engine)
        # MSI administrative image includes its installer, which is not a runtime file.
        if path.suffix.lower() == '.msi':
            continue
        if path.suffix.lower() in {'.ttf', '.otf', '.woff', '.woff2', '.pfb', '.pfm'}:
            raise ValueError('Font file requires explicit review; not copied: ' + rel.as_posix())
        dest = output / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--python-archive', required=True, type=Path)
    parser.add_argument('--inkscape-msi', required=True, type=Path)
    parser.add_argument('--wheels', required=True, type=Path)
    args = parser.parse_args()
    if os.name != 'nt':
        raise RuntimeError('Run this source-transfer preparation on Windows')
    repo = args.repo.resolve()
    if git(repo, 'branch', '--show-current').decode().strip() != BRANCH:
        raise ValueError('Wrong development branch')
    if git(repo, 'status', '--porcelain', '--', *SOURCE_PATHS).strip():
        raise ValueError('Commit reviewed source changes first; no uncommitted or private files are exported')
    commit = git(repo, 'rev-parse', 'HEAD').decode().strip()
    lock = json.loads((Path(__file__).parent / 'dependency-sources.json').read_text(encoding='utf-8'))
    if digest(args.inkscape_msi) != lock['inkscape']['sha256']:
        raise ValueError('Inkscape official MSI hash mismatch')
    if digest(args.python_archive) != lock['python']['sha256']:
        raise ValueError('Python official archive hash mismatch')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    export_source(repo, output / 'source', commit)
    python_runtime(args.python_archive, output / 'python', lock['python']['sha256'])
    (output / 'wheels').mkdir()
    (output / 'offline-requirements.txt').write_text(install_wheels(args.wheels, output / 'wheels'), encoding='utf-8')
    # Preserve the fresh administrative extraction locally for diagnostics; never copy its log.
    scratch = Path(tempfile.mkdtemp(prefix='review-usb-vendor-'))
    command = ['msiexec.exe', '/a', str(args.inkscape_msi.resolve()), '/qn', 'TARGETDIR=' + str(scratch / 'image'),
               '/L*v', str(scratch / 'extract.local.log')]
    rc = subprocess.run(command, timeout=600, creationflags=0x08000000).returncode
    if rc != 0:
        raise RuntimeError('Vendor extraction failed; local scratch: ' + str(scratch))
    copy_engine(scratch / 'image', output / 'inkscape')
    for name in ('START_REVIEW.cmd', 'RETEST_ILLUSTRATOR.cmd', 'README.txt'):
        data = (output / 'source/tools/windows_review_dev/usb' / name).read_bytes()
        if name.endswith('.cmd'):
            data = data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
        (output / name).write_bytes(data)
    files = []
    for path in sorted(output.rglob('*')):
        if path.is_file():
            files.append({'path': path.relative_to(output).as_posix(), 'bytes': path.stat().st_size, 'sha256': digest(path)})
    write_new(output / 'transfer-manifest.json', {'schema_version': 1, 'component': 'review-tool', 'branch': BRANCH,
              'source_commit': commit, 'offline': True, 'source_transfer_not_exe_release': True,
              'private_data_included': False, 'dependencies': lock, 'files': files})
    print(json.dumps({'status': 'SOURCE_TRANSFER_PREPARED', 'files': len(files), 'bytes': sum(x['bytes'] for x in files),
                      'source_commit': commit, 'manifest_sha256': digest(output / 'transfer-manifest.json')}))


if __name__ == '__main__':
    main()

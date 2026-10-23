"""Rebuild the project-local GUI skill and optional isolated Debian X11 tools."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import urllib.request

from tooling_extensions import discover_skills, verify_extensions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--with-x11', action='store_true', help='Install hash-pinned headless editing tools locally')
    parser.add_argument('--tool-root', type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    repository = here.parents[2]
    assert (repository / 'AGENTS.md').is_file()
    upstream = json.loads((here / 'UPSTREAM.json').read_text())
    vendor = here / 'vendor/ui-ux-pro-max'
    for name, expected in upstream['files'].items():
        if hashlib.sha256((vendor / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Vendored skill changed: ' + name)
    extensions = verify_extensions(here)
    entries = discover_skills(repository, here, extensions)
    result = dict(skill='template-ai-gui', entry=entries[0], additional_entries=entries[1:],
                  upstream_files_verified=len(upstream['files']),
                  additional_upstream_files_verified=len(extensions['sources']),
                  agent_roles=list(extensions['agent_roles']), x11='NOT_REQUESTED')
    if args.with_x11:
        release = Path('/etc/os-release').read_text()
        if 'VERSION_ID="13"' not in release or platform.machine() != 'x86_64':
            raise RuntimeError('Pinned X11 helper packages target Debian 13 amd64 only; use native Qt Designer on other systems')
        base = (args.tool_root or repository.parent / 'template-ai-gui-tools').resolve()
        if not base.is_relative_to(repository.parent):
            raise RuntimeError('The tool root must stay within the workspace')
        archives, native = base / 'debs', base / 'root'
        archives.mkdir(parents=True, exist_ok=True)
        native.mkdir(parents=True, exist_ok=True)
        lock = json.loads((here / 'NATIVE_PACKAGES.json').read_text())
        for package in lock['packages']:
            archive = archives / package['archive']
            if not archive.is_file():
                temporary = archive.with_suffix('.download')
                try:
                    with urllib.request.urlopen(package['url'], timeout=45) as response, temporary.open('xb') as target:
                        remaining = 10 * 1024 * 1024
                        while chunk := response.read(min(65536, remaining + 1)):
                            remaining -= len(chunk)
                            if remaining < 0:
                                raise RuntimeError('Unexpectedly large tool package')
                            target.write(chunk)
                    if hashlib.sha256(temporary.read_bytes()).hexdigest() != package['sha256']:
                        raise RuntimeError('Downloaded package hash differs: ' + package['package'])
                    temporary.replace(archive)
                finally:
                    temporary.unlink(missing_ok=True)
            if hashlib.sha256(archive.read_bytes()).hexdigest() != package['sha256']:
                raise RuntimeError('Cached package hash differs: ' + package['package'])
            subprocess.run(['dpkg-deb', '-x', str(archive), str(native)], check=True)
        result.update(x11='HASH_VERIFIED_EXTRACTED_LOCALLY', native_root=str(native),
                      packages=[p['package'] for p in lock['packages']])
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

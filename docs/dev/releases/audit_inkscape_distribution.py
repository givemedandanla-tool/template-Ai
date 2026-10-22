"""Inspect public upstream installation only; no private/project data input."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'artifacts/inkscape-distribution-audit'
BRANCH = 'research-evidence/inkscape-1.4.2-beta2'
REMOTE = 'https://github.com/givemedandanla-tool/template-Ai.git'


def git(folder, *args):
    return subprocess.run(['git', '-C', str(folder), *args], check=True,
                          capture_output=True, text=True)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for b in iter(lambda: stream.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def audit():
    if os.name != 'nt' or os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('This audit only reads the authorized fresh Windows runner installation')
    root = Path(r'C:\Program Files\Inkscape').resolve(strict=True)
    executable = root / 'bin/inkscape.exe'
    version = subprocess.run([str(executable), '--version'], capture_output=True,
                             text=True, timeout=20, check=True).stdout.strip()
    if 'Inkscape 1.4.2 ' not in version:
        raise RuntimeError('Unexpected upstream version')
    rows, licenses = [], []
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        path.resolve(strict=True).relative_to(root)
        relative = path.relative_to(root).as_posix()
        rows.append(dict(path=relative, bytes=path.stat().st_size, sha256=sha(path)))
        if (path.name.lower().startswith(('copying', 'license', 'copyright', 'source', 'verification'))
                and path.stat().st_size <= 150000 and len(licenses) < 200):
            licenses.append(dict(path=relative, text=path.read_text(encoding='utf-8', errors='replace')))
    if not rows:
        raise RuntimeError('Empty upstream inventory')
    choco = Path(r'C:\ProgramData\chocolatey\lib\inkscape')
    recipe = []
    for path in sorted(choco.rglob('*')):
        if path.is_file() and path.name.lower() in {'chocolateyinstall.ps1', 'verification.txt', 'license.txt', 'inkscape.nuspec'}:
            if path.stat().st_size > 150000:
                raise RuntimeError('Unexpected package metadata size')
            recipe.append(dict(path=path.relative_to(choco).as_posix(), text=path.read_text(encoding='utf-8', errors='replace')))
    write(OUT/'inventory.json', dict(status='UPSTREAM_DISTRIBUTION_AUDITED_NOT_PRODUCT_RELEASED',
          version=version, executable_sha256=sha(executable), files=len(rows),
          total_bytes=sum(r['bytes'] for r in rows), inventory=rows,
          license_texts=licenses, pinned_package_recipe=recipe,
          largest=sorted(rows, key=lambda r:r['bytes'], reverse=True)[:12]))


def persist():
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('Only the authorized runner may publish this public-package audit')
    source = git(ROOT, 'rev-parse', 'HEAD').stdout.strip()
    record = dict(source_commit=source, status='AUDIT_COMPLETED_NOT_RELEASED' if (OUT/'inventory.json').is_file() else 'AUDIT_FAILED_NOT_RELEASED',
                  recorded_utc=datetime.now(timezone.utc).isoformat(),
                  run_url='https://github.com/givemedandanla-tool/template-Ai/actions/runs/'+os.environ['GITHUB_RUN_ID'])
    with tempfile.TemporaryDirectory(prefix='inkscape-distribution-proof-') as raw:
        folder = Path(raw)
        git(folder, 'init');git(folder, 'config', 'user.name', 'github-actions[bot]')
        git(folder, 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
        git(folder, 'remote', 'add', 'origin', REMOTE)
        if git(folder, 'ls-remote', '--heads', 'origin', BRANCH).stdout.strip():
            git(folder, 'fetch', '--depth=1', 'origin', BRANCH)
            git(folder, 'checkout', '-b', 'evidence', 'FETCH_HEAD')
        else:
            git(folder, 'checkout', '--orphan', 'evidence')
        target = folder/source;target.mkdir(exist_ok=True)
        if (OUT/'inventory.json').is_file():
            shutil.copy2(OUT/'inventory.json', target/'inventory.json')
        write(target/'status.json', record);write(folder/'latest.json', record)
        git(folder, 'add', '.');git(folder, 'commit', '-m', 'public Inkscape distribution audit '+source[:12])
        git(folder, 'push', 'origin', 'HEAD:refs/heads/'+BRANCH)
    print(json.dumps(record))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__);p.add_argument('--persist', action='store_true')
    persist() if p.parse_args().persist else audit()

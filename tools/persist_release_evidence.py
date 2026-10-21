"""Small explicit release evidence branch; excludes synthetic DBs and fonts."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BRANCH = 'release-evidence/v0.2.0-beta.1'
REMOTE = 'https://github.com/givemedandanla-tool/template-Ai.git'


def git(folder, *args):
    return subprocess.run(['git', '-C', str(folder), *args], check=True, capture_output=True, text=True)


def persist(status):
    if os.environ.get('GITHUB_ACTIONS') != 'true' or not os.environ.get('GITHUB_RUN_ID'):
        raise RuntimeError('Only the authorized GitHub runner publishes this evidence')
    source = git(ROOT, 'rev-parse', 'HEAD').stdout.strip()
    artifacts = ROOT / 'artifacts'
    evidence = dict(status=status, source_commit=source,
         run_url='https://github.com/givemedandanla-tool/template-Ai/actions/runs/' + os.environ['GITHUB_RUN_ID'],
         recorded_at=datetime.now(timezone.utc).isoformat(), release_tag='v0.2.0-beta.1',
         scope='NATIVE_WINDOWS_AUTOMATION_NOT_USER_HARDWARE_QUALIFICATION')
    with tempfile.TemporaryDirectory(prefix='release-evidence-') as temp:
        folder = Path(temp)
        git(folder, 'init')
        git(folder, 'config', 'user.name', 'github-actions[bot]')
        git(folder, 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
        git(folder, 'remote', 'add', 'origin', REMOTE)
        refs = git(folder, 'ls-remote', '--heads', 'origin', BRANCH).stdout
        if refs.strip():
            git(folder, 'fetch', '--depth=1', 'origin', BRANCH)
            git(folder, 'checkout', '-b', 'evidence', 'FETCH_HEAD')
        else:
            git(folder, 'checkout', '--orphan', 'evidence')
        target = folder / source
        target.mkdir(exist_ok=True)
        names = ['WINDOWS_RUNTIME.txt', 'installed-dependencies.txt', 'pyinstaller.log', 'release-manifest.json',
                 'SHA256SUMS.txt', 'download/download-verification.json', 'source-tests/summary.json',
                 'source-tests/tests.json', 'source-tests/catalog.json', 'source-tests/runtime-errors.json',
                 'source-tests/live/test-modules.json']
        for name in names:
            path = artifacts / name
            if path.is_file() and path.stat().st_size <= 12 * 1024 * 1024:
                dest = target / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
        package_check = artifacts / 'package-check'
        if package_check.exists():
            for path in package_check.iterdir():
                if path.is_file() and path.suffix in {'.json', '.png', '.log'} and path.stat().st_size <= 8 * 1024 * 1024:
                    dest = target / 'package-check' / path.name
                    dest.parent.mkdir(exist_ok=True)
                    shutil.copy2(path, dest)
        metadata = artifacts / 'source-tests/live/test-modules.json'
        if metadata.is_file():
            for module in json.loads(metadata.read_text(encoding='utf-8')).get('modules', []):
                if module['healthy']:
                    continue
                name = module['module'] + '-stdout.log'
                path = artifacts / 'source-tests/live/modules' / name
                if path.is_file():
                    dest = target / 'failed-modules' / name
                    dest.parent.mkdir(exist_ok=True)
                    dest.write_bytes(path.read_bytes()[-64000:])
        for path in [target / 'status.json', folder / 'latest.json']:
            path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        git(folder, 'add', '.')
        git(folder, 'commit', '-m', 'release evidence: ' + source[:12] + ' ' + status)
        git(folder, 'push', 'origin', 'HEAD:refs/heads/' + BRANCH)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status', required=True)
    persist(parser.parse_args().status)

"""Portable native Git checkpoint readback; no API token or REST projection fiction.

Reuses the existing checkpoint acknowledgement and independent Git-object method.
This administrative helper is outside the product and the distributed EXE.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from dev_common import valid_id


def git(*arguments, directory=ROOT):
    return subprocess.check_output(['git', '-C', str(directory), *arguments], stderr=subprocess.PIPE, timeout=180)


def verify(expected, checkpoint, branch, acknowledge=False):
    valid_id(checkpoint)
    expected = git('rev-parse', '--verify', expected + '^{commit}').decode().strip()
    destination = ROOT / '.checkpoints' / checkpoint / 'native-readback'
    if destination.exists():
        raise FileExistsError('Immutable proof destination already exists; choose a new ID')
    remote = 'https://github.com/givemedandanla-tool/template-Ai.git'
    # Reuse a previously independent repository when available; otherwise a
    # temporary blobless fetch only needs commit/tree objects for this proof.
    with tempfile.TemporaryDirectory(prefix='template-ai-readback-') as raw:
        location = Path('/tmp/template-ai-current-readback-location.json')
        bare = Path(json.loads(location.read_text())['git_dir']) if location.is_file() else Path(raw) / 'objects.git'
        if not bare.is_dir():
            bare = Path(raw) / 'objects.git'
            subprocess.run(['git', 'init', '--bare', str(bare)], check=True, capture_output=True, timeout=30)
        reference = 'refs/heads/readback-' + expected[:12] + '-' + uuid.uuid4().hex[:8]
        git('fetch', '--no-tags', '--depth=1', '--filter=blob:none', remote,
            'refs/heads/' + branch + ':' + reference, directory=bare)
        actual = git('rev-parse', reference, directory=bare).decode().strip()
        if actual != expected:
            raise ValueError('Remote branch moved; inspect the actual source before continuing')
        commit = git('cat-file', 'commit', actual, directory=bare)
        entries = git('ls-tree', '-r', '--full-tree', '-z', actual, directory=bare)
        if commit != git('cat-file', 'commit', expected) or entries != git('ls-tree', '-r', '--full-tree', '-z', expected):
            raise ValueError('Independent raw commit or recursive file list differs')
        tree_sha = git('rev-parse', actual + '^{tree}', directory=bare).decode().strip()
    items = []
    for entry in entries.split(b'\0')[:-1]:
        metadata, path = entry.split(b'\t', 1)
        mode, kind, identity = metadata.decode().split()
        items.append(dict(path=path.decode('utf-8'), mode=mode, type=kind, sha=identity))
    proof = dict(method='NATIVE_AUTHENTICATED_GIT_FETCH_INDEPENDENT_BARE_REPOSITORY', api_response=False,
                 raw_commit_sha256=hashlib.sha256(commit).hexdigest(),
                 recursive_file_list_sha256=hashlib.sha256(entries).hexdigest(), file_entries=len(items),
                 verified_utc=datetime.now(timezone.utc).isoformat(), snapshot_commit=actual, tree_sha=tree_sha,
                 content_verification='Exact raw commit/tree objects and every path/mode/blob ID; not a REST API response')
    destination.mkdir(parents=True, exist_ok=False)
    (destination / 'raw-commit.txt').write_bytes(commit)
    for name, data in [('proof.json', proof), ('commit.json', dict(sha=actual, tree=dict(sha=tree_sha), native_transport_provenance=proof)),
                       ('tree.json', dict(sha=tree_sha, truncated=False, tree=items, native_transport_provenance=proof))]:
        (destination / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if acknowledge:
        from dev_checkpoint import acknowledge as ack
        receipt = ack(ROOT, checkpoint, destination / 'commit.json', destination / 'tree.json',
            verification='Native authenticated Git: independent raw commit and complete path/mode/blob tree match; scoped checkpoint blobs and checkpoint record checked. No REST response claimed.')
        return {key: receipt[key] for key in ['phase', 'snapshot_commit', 'verified_files']}
    return {key: proof[key] for key in ['method', 'snapshot_commit', 'tree_sha', 'file_entries']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected', required=True)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--branch', default='dev/v0.1-first-version')
    parser.add_argument('--ack', action='store_true')
    arguments = parser.parse_args()
    print(json.dumps(verify(arguments.expected, arguments.checkpoint, arguments.branch, arguments.ack)))

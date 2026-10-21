"""Prepare a compact incremental checkpoint; restore requires the stated Git base."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from dev_common import digest, manifest_digest, read_json, write_json, valid_id, safe_path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--id', required=True)
p.add_argument('--base', required=True)
p.add_argument('--scope', choices=['formal', 'completion'], required=True)
p.add_argument('--run-path', default='docs/evidence/runs/RUN-NONCODE-ALL-001')
p.add_argument('--extra-root', action='append', default=[])
p.add_argument('--summary', default='Actual non-code audit evidence; original product/external qualification unchanged. Incremental restore requires stated base.')
a = p.parse_args(); valid_id(a.id)
a.base = subprocess.check_output(['git', 'rev-parse', '--verify', a.base + '^{commit}'], cwd=ROOT, text=True).strip()
subprocess.run(['git', 'merge-base', '--is-ancestor', a.base, 'HEAD'], cwd=ROOT, check=True)
record = ROOT / 'docs/checkpoints' / (a.id + '.json')
folder = ROOT / '.checkpoints' / a.id
if record.exists() or folder.exists():
    raise FileExistsError('Immutable checkpoint ID already exists')
roots = [safe_path(ROOT, a.run_path), *[safe_path(ROOT, path) for path in a.extra_root]]
if a.scope == 'completion':
    roots += [ROOT / 'docs/dev/non_code_audit']
if not all(root.exists() for root in roots):raise ValueError('Checkpoint scope root missing; not an empty scan')
state_path = ROOT / 'docs/dev/STATE.json'
state = read_json(state_path)
state['pending_remote'] = list(dict.fromkeys([*state.get('pending_remote', []), a.id]))
write_json(state_path, state)
paths = {path for root in roots for path in ([root] if root.is_file() else root.rglob('*'))
         if path.is_file() and not path.is_symlink() and '__pycache__' not in path.parts}
paths |= {ROOT / name for name in ['AGENTS.md', 'docs/dev/STATE.json', 'docs/dev/REQUIREMENTS.json', 'docs/dev/FEATURES.md',
    'docs/dev/CURRENT_PROGRESS.json', 'docs/dev/PROGRESS.md', 'docs/dev/PROJECT_ROADMAP.md', 'docs/dev/PROJECT_ROADMAP.json',
    'docs/dev/ACTIVE_DEVELOPMENT_HANDOFF.md', 'docs/dev/WORK_LOG.md', 'docs/dev/HANDOFF.md']}
files = {}
for path in sorted(paths):
    data = path.read_bytes()
    files[path.relative_to(ROOT).as_posix()] = dict(bytes=len(data), sha256=digest(data),
        git_blob_sha1=hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest())
folder.mkdir(parents=True)
archive = folder / 'source.zip'
with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
    for relative in files:
        bundle.write(ROOT / relative, relative)
    bundle.writestr('CHECKPOINT_MANIFEST.json', json.dumps(files, ensure_ascii=False, indent=2))
with zipfile.ZipFile(archive) as bundle, tempfile.TemporaryDirectory(prefix='noncode-restore-',dir=ROOT/'.checkpoints') as raw:
    assert bundle.testzip() is None
    target = Path(raw)
    for relative, info in files.items():
        dest = target / relative
        assert target.resolve() in dest.resolve().parents
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(bundle.read(relative))
        assert digest(dest.read_bytes()) == info['sha256']
restore = dict(status='PASS', kind='INCREMENTAL_CHANGED_PATH_RESTORE_NOT_STANDALONE_PRODUCT', files=len(files),
               base_commit_required=a.base, archive_sha256=digest(archive.read_bytes()),
               isolated_temporary_restore=True, all_hashes_match=True, user_data_included=False)
write_json(folder / 'restore-verification.json', restore)
write_json(record, dict(schema_version=1, id=a.id, kind='INCREMENTAL_' + a.scope.upper(), phase='PREPARED', base_commit=a.base,
    created_utc=datetime.now(timezone.utc).isoformat(), summary=a.summary,
    source_files=files, source_manifest_sha256=manifest_digest(files),
    local_snapshot=dict(path=archive.relative_to(ROOT).as_posix(), sha256=digest(archive.read_bytes())),
    requirement_ids=['GOV-001', 'GOV-002', 'GOV-004'],
    next_step='Use compact repository handoff; local feedback via manually exported safe support report.',
    remote_confirmation='PENDING_ACTUAL_REMOTE_READBACK', restore_verification=restore))
print(json.dumps(dict(id=a.id, phase='PREPARED', files=len(files), restore='PASS')))

"""Run the original isolated test executor with explicit LOCAL_ONLY provenance."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
from dev_common import manifest
from evidence_modules import run_modules


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def catalog(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from catalog(test)
        else:
            yield test.id()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--module', action='append', default=[])
    args = parser.parse_args()
    os.chdir(ROOT)
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    source = manifest(code_only=True)
    tree = subprocess.check_output(['git', 'ls-tree', '-r', '--full-tree', head], text=True)
    blobs = {line.split('\t', 1)[1]: line.split('\t', 1)[0].split()[2]
             for line in tree.splitlines()}
    dirty = [path for path, info in source.items()
             if blobs.get(path) != info['git_blob_sha1']]
    if dirty:
        raise SystemExit('Commit code/test changes before a source-bound run: ' + ', '.join(dirty[:10]))
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(ROOT / 'tests'))
    if args.module:
        suite = unittest.defaultTestLoader.loadTestsFromNames(args.module)
    else:
        suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    ids = list(catalog(suite))
    old = json.loads((ROOT / 'docs/evidence/runs/RUN-GUI-OFFLINE-ALL-006/test-catalog.json').read_text())
    if not args.module and set(old) - set(ids):
        raise SystemExit('Original test IDs missing from discovered catalog')
    write(args.output / 'source.json', {
        'qualification': 'LOCAL_ONLY_NOT_REMOTE_VERIFIED', 'commit': head,
        'python': sys.version, 'command': sys.argv, 'source_manifest': source,
        'original_catalog_size': len(old), 'expected': len(ids),
        'new_ids': sorted(set(ids) - set(old)),
        'manifest_sha256': hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest(),
    })
    write(args.output / 'catalog.json', ids)
    result, errors, log = run_modules(ids, args.output / 'live', module_timeout=180, workers=1)
    counts = Counter(record['status'] for record in result.records.values())
    unchanged = manifest(code_only=True) == source
    healthy = sum(module['healthy'] for module in result.modules)
    passed = (len(result.records) == len(ids) and counts == {'PASS': len(ids)}
              and not errors and healthy == len(result.modules) and unchanged)
    write(args.output / 'tests.json', list(result.records.values()))
    write(args.output / 'runtime-errors.json', errors)
    (args.output / 'unittest.log').write_text(log)
    summary = {
        'qualification': 'LOCAL_ONLY_NOT_REMOTE_VERIFIED', 'source_commit': head,
        'software_execution': 'PASS' if passed else 'FAIL', 'planned': len(ids),
        'completed': len(result.records), 'statuses': dict(counts),
        'modules': len(result.modules), 'healthy_modules': healthy,
        'runtime_errors': len(errors), 'source_unchanged_during_run': unchanged,
        'original_test_ids_preserved': not (set(old) - set(ids)) if not args.module else None,
        'remote_gate': 'NOT_EXECUTED_REMOTE_PROVENANCE_UNAVAILABLE',
        'windows_private_corpus_physical_print': 'NOT_QUALIFIED_BY_THIS_RUN',
    }
    write(args.output / 'summary.json', summary)
    print(json.dumps(summary))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())

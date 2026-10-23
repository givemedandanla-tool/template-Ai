"""Bounded regression for the import/analysis bug; not full source qualification."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests'), str(ROOT)]
from dev_common import manifest, manifest_digest, write_json
from evidence_modules import run_modules

MODULES = (
    'test_import_then_analysis', 'test_automatic_training', 'test_automatic_pages',
    'test_runtime_source_refresh', 'test_runtime_dispatch',
    'test_source_region_hypotheses', 'test_source_text_budget',
    'test_desktop_workspace', 'test_startup_catalog', 'test_design_observation',
    'test_semantic_learning', 'test_quality_provenance', 'test_quality_engine',
)


def identities(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from identities(item)
        else:
            yield item.id()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Immutable run output already exists')
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    before = manifest(ROOT, code_only=True)
    expected = list(identities(unittest.defaultTestLoader.loadTestsFromNames(MODULES)))
    if not expected or any(name.startswith('unittest.loader.') for name in expected):
        raise ValueError('Incomplete test catalog')
    started = time.perf_counter()
    result, errors, log = run_modules(expected, args.output, module_timeout=180, workers=1)
    unchanged = manifest_digest(before) == manifest_digest(manifest(ROOT, code_only=True))
    records = list(result.records.values())
    summary = dict(status='PASS' if result.wasSuccessful() and not errors and unchanged else 'FAIL',
                   kind='TARGETED_LINUX_SYNTHETIC_REAL_QT_NOT_FULL_SOURCE_OR_WINDOWS_EXE_QUALIFICATION',
                   source_commit=source, code_manifest_sha256=manifest_digest(before), source_unchanged=unchanged,
                   python=sys.version, command=[sys.executable, str(Path(__file__).relative_to(ROOT)), *sys.argv[1:]],
                   modules=MODULES, healthy_modules=sum(item['healthy'] for item in result.modules),
                   module_results=result.modules, planned=len(expected), completed=len(records),
                   counts={state: sum(row['status'] == state for row in records) for state in ('PASS', 'FAIL', 'ERROR', 'SKIP')},
                   runtime_errors=errors, seconds=time.perf_counter() - started,
                   full_source_qualification=False, windows_verified=False, exe_verified=False,
                   private_data_included=False)
    write_json(args.output / 'summary.json', summary)
    write_json(args.output / 'source-manifest.json', before)
    write_json(args.output / 'test-results.json', records)
    (args.output / 'modules.log').write_text(log, encoding='utf-8')
    print(json.dumps({key: summary[key] for key in ('status', 'source_commit', 'planned', 'completed', 'counts', 'healthy_modules', 'seconds')}))
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())

"""Explicit audit profiles; original quality configuration/baselines stay intact."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'docs/dev/debug_tooling'))
import quality


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scope', choices=['application', 'tools', 'tests'], required=True)
    parser.add_argument('--mode', choices=['runtime-pyright', 'clones'], required=True)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    quality.verify_sources()
    files = quality.inventory(ROOT, args.scope)
    before = quality.manifest(files, ROOT)
    node = shutil.which('node')
    if not node:
        raise SystemExit('Existing Node runtime unavailable')
    if args.mode == 'runtime-pyright':
        config = json.loads((quality.HERE / 'pyrightconfig.json').read_text())
        extra = [ROOT]
        # These are the actual explicit sys.path insertions proven per original
        # finding in runtime-import-path-proof.json. No diagnostic is disabled.
        if args.scope == 'tools':
            extra.append(ROOT / 'tests')
        if args.scope == 'tests':
            extra.append(ROOT / 'tools')
        config.update(pythonVersion=f'{sys.version_info.major}.{sys.version_info.minor}',
                      include=[os.path.relpath(p, args.output) for p in files],
                      executionEnvironments=[{'root': str(ROOT), 'extraPaths': list(map(str, extra))}])
        config_file = args.output / 'pyrightconfig.json'
        dump(config_file, config)
        command = [node, str(quality.home() / 'node/node_modules/pyright/index.js'),
                   '--project', str(config_file), '--pythonpath', str(ROOT / '.venv/bin/python'), '--outputjson']
    else:
        config = json.loads((quality.HERE / 'jscpd.json').read_text())
        config_file = args.output / 'jscpd-config.json'
        dump(config_file, config)
        command = [node, str(quality.home() / 'node/node_modules/jscpd/run-jscpd.js'),
                   '--config', str(config_file), '--no-gitignore', '--output', str(args.output / 'clones'),
                   '--silent', '--ignore-identifiers', '--max-gap-lines', '1', '--similarity=0.8',
                   *[str(p) for p in files]]
    started = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=240)
    (args.output / 'stdout.txt').write_text(result.stdout)
    (args.output / 'stderr.txt').write_text(result.stderr)
    if result.returncode not in (0, 1):
        raise SystemExit(f'Supplemental scan failed with exit {result.returncode}; retained logs')
    if args.mode == 'runtime-pyright':
        raw = json.loads(result.stdout)
        findings = [quality.diagnostic('pyright', row.get('rule', 'unknown'),
                    quality.locate(row['file'], files, ROOT),
                    row['range']['start']['line'] + 1, row['message'], ROOT)
                    for row in raw['generalDiagnostics']]
        coverage = raw['summary']
    else:
        raw = json.loads((args.output / 'clones/jscpd-report.json').read_text())
        findings = raw.get('duplicates', [])
        coverage = raw.get('statistics', {})
    unchanged = before == quality.manifest(files, ROOT)
    report = {'profile': f'AUDIT_{args.mode.upper()}_V1', 'scope': args.scope,
              'purpose': 'Supplemental evidence; not comparable with or a replacement for immutable original baseline',
              'source': before, 'input_files': len(files), 'coverage': coverage,
              'versions': quality.versions(quality.home()), 'command': command,
              'exit_code': result.returncode, 'seconds': time.monotonic() - started,
              'configuration_sha256': hashlib.sha256(config_file.read_bytes()).hexdigest(),
              'source_unchanged': unchanged, 'findings': findings,
              'structural_test_file_exclusion': 'jscpd similarity excludes test files by design; token-based renamed comparison still covers explicit inputs' if args.mode == 'clones' else None,
              'paid_or_remote_model': False}
    dump(args.output / 'report.json', report)
    print(json.dumps({'scope': args.scope, 'mode': args.mode, 'inputs': len(files), 'findings': len(findings), 'source_unchanged': unchanged}))
    return 0 if unchanged else 1


if __name__ == '__main__':
    raise SystemExit(main())

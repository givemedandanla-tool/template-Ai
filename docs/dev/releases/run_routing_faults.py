"""Bounded labelled fault injection against the real routing contract assertions."""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT/'tests')]


def main():
    import template_ai.inkscape_runtime as runtime
    import test_bundled_inkscape as tests
    import os
    original = runtime.inkscape_path
    # Derive original test IDs from their actual names; do not weaken assertions.
    names = ['test_frozen_prefers_bundle_even_when_external_setting_and_path_exist',
             'test_missing_bundle_does_not_fall_back_to_installed_engine']
    if not set(names) <= set(unittest.defaultTestLoader.getTestCaseNames(tests.BundledInkscapeTests)):
        raise RuntimeError('Original routing assertions changed; inspect before running faults')
    def legacy():
        return os.environ.get('TEMPLATE_AI_INKSCAPE') or original()
    def silent_fallback():
        try:
            return original()
        except ValueError:
            return os.environ.get('TEMPLATE_AI_INKSCAPE')
    output = ROOT/'docs/dev/releases/v0.2.0-beta.2/routing-fault-injection-002'
    output.mkdir(parents=True,exist_ok=False)
    rows = []
    for label, fn in [('correct',original),('env-first-fault',legacy),('missing-bundle-fallback-fault',silent_fallback)]:
        stream = io.StringIO()
        suite = unittest.TestSuite(tests.BundledInkscapeTests(name) for name in names)
        with patch.object(runtime,'inkscape_path',fn):
            result = unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        (output/(label+'.log')).write_text(stream.getvalue(),encoding='utf-8')
        rows.append(dict(variant=label,tests=result.testsRun,failures=len(result.failures),errors=len(result.errors)))
    if rows[0]['failures'] or rows[0]['errors'] or any(not (r['failures'] or r['errors']) for r in rows[1:]):
        raise RuntimeError('Fault injection failed to distinguish intended behavior')
    (output/'result.json').write_text(json.dumps(dict(kind='CONTROLLED_FAULT_INJECTION_NOT_NATIVE_ENGINE_PROOF',status='PASS',selected_tests=names,results=rows),indent=2)+'\n')
    print(json.dumps(rows))


if __name__ == '__main__':
    main()

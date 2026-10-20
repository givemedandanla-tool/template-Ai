"""Capture actual new desktop workflows using authored local fixtures only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tests'), str(ROOT)]
from dev_common import manifest, manifest_digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', type=Path, required=True)
    args = parser.parse_args()
    args.folder.mkdir(parents=True, exist_ok=True)
    os.environ['TEMPLATE_AI_DESKTOP_CAPTURE_DIR'] = str(args.folder)
    before = manifest_digest(manifest(ROOT, code_only=True))
    from test_desktop_workspace import DesktopNavigationTests, DesktopProductionTests
    suite = unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(DesktopNavigationTests))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(DesktopProductionTests))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    expected = [*(f'desktop-mode-{i}.png' for i in range(3)),
                'desktop-small-window.png', 'desktop-guidance.png', 'desktop-offline-support.png',
                'desktop-learned-preview.png', 'desktop-confirmed.png', 'desktop-stale-after-correction.png',
                'desktop-corrected-preview.png', 'desktop-after-drag.png']
    unchanged = before == manifest_digest(manifest(ROOT, code_only=True))
    missing = [name for name in expected if not (args.folder / name).is_file()]
    success = result.wasSuccessful() and result.testsRun > 0 and unchanged and not missing
    screens = {name: dict(sha256=hashlib.sha256((args.folder / name).read_bytes()).hexdigest(),
                         bytes=(args.folder / name).stat().st_size) for name in expected if (args.folder / name).is_file()}
    data = dict(status='PASS' if success else 'FAIL', tests_run=result.testsRun, screenshots=screens,
                missing=missing, source_unchanged=unchanged, source_manifest_sha256=before,
                qt_platform=os.environ.get('QT_QPA_PLATFORM', 'default'), actual_gui=True,
                scope='AUTHORED_LOCAL_DESKTOP_WORKFLOWS_NOT_WINDOWS_OR_HUMAN_USABILITY_QUALIFICATION')
    (args.folder / 'desktop-workspace-audit.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: data[k] for k in ('status', 'tests_run', 'source_unchanged', 'qt_platform')}, ensure_ascii=False))
    return 0 if success else 1


if __name__ == '__main__':
    raise SystemExit(main())

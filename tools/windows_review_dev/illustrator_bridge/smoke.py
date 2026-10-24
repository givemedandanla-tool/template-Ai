"""Opt-in real Illustrator qualification with generated data only; writes local evidence.

No input-work path. Requires a NEW short local --output directory. No screenshots,
documents, font files or raw diagnostics are uploaded by this tool.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    from template_ai.review_tool.illustrator_bridge import available, local_path, IllustratorBridge, digest
    if not available():
        print(json.dumps(dict(status='NOT_RUN', reason='ILLUSTRATOR_NOT_REGISTERED', real_illustrator_verified=False)))
        return 3
    root = local_path(args.output)
    root.mkdir(parents=True, exist_ok=False)
    fixture = root / 'synthetic-native.ai'
    create = root / 'create.jsx'
    create.write_text(Path(__file__).with_name('create_fixture.jsx').read_text(encoding='utf-8') +
                      '\ncreateReviewFixture(' + json.dumps(str(fixture), ensure_ascii=True) + ');\n', encoding='utf-8')
    host = ROOT / 'template_ai/review_tool/illustrator_host.py'
    report = dict(schema_version=1, status='FAILED', synthetic_only=True, real_illustrator_verified=False,
                  visual_fidelity='MANUAL_REVIEW_REQUIRED', uploaded=False)
    try:
        # Timeout ends only this helper, not Illustrator. Do not reuse a timed-out directory.
        result = subprocess.run([sys.executable, '-I', str(host), str(create)], capture_output=True, timeout=600,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode or result.stdout.strip() != b'OK|2':
            report['reason'] = 'SYNTHETIC_FIXTURE_CREATION_FAILED'
        else:
            from PySide6.QtCore import QEventLoop
            from PySide6.QtWidgets import QApplication
            from PySide6.QtPdf import QPdfDocument
            app = QApplication.instance() or QApplication([])
            loop = QEventLoop()
            adapter = IllustratorBridge(root / 'bridge')
            outputs, errors = [], []
            adapter.ready.connect(lambda path, info: outputs.append(path))
            adapter.failure.connect(lambda message: errors.append(True))
            adapter.finished.connect(loop.quit)
            original = digest(fixture)
            adapter.start(fixture)
            loop.exec()
            report['source_unchanged'] = digest(fixture) == original
            if outputs and not errors:
                document = QPdfDocument()
                try:
                    document.load(outputs[0])
                    text = [document.getSelectionAtIndex(i, 0, 4096).text() for i in range(document.pageCount())]
                    checks = [len(text) == 2, len(text) == 2 and 'SYNTHETIC_ALPHA' in text[0],
                              len(text) == 2 and 'SYNTHETIC_BETA' in text[1], report['source_unchanged']]
                    checks.append(all(abs(document.pagePointSize(i).width() - 300) < 1 and
                                      abs(document.pagePointSize(i).height() - 200) < 1 for i in range(document.pageCount())))
                finally:
                    document.close()
                # Use the actual existing review pipeline too; OCR deliberately disabled.
                from template_ai.review_tool.analysis import analyse_file
                packet = analyse_file(outputs[0], root / 'analysis', ocr=False)
                checks.append(len(packet['pages']) == 2)
                report.update(checks_passed=sum(checks), checks_total=len(checks),
                              status='AUTOMATED_PASS' if all(checks) else 'FAILED',
                              real_illustrator_verified=all(checks), private_fidelity_verified=False)
            else:
                report['reason'] = 'BRIDGE_FAILED'
    except subprocess.TimeoutExpired:
        report['reason'] = 'FIXTURE_TIMEOUT_CHECK_ILLUSTRATOR_MANUALLY'
    except Exception:
        # Keep public-safe receipt free of machine paths, Adobe messages and contents.
        report['reason'] = 'LOCAL_SMOKE_ERROR'
    (root / 'summary.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))
    return 0 if report['status'] == 'AUTOMATED_PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())

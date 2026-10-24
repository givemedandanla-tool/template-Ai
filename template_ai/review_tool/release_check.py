"""Bounded acceptance through the actual small-tool window and worker.

Only --release-check invokes this module. All sources below are authored,
synthetic fixtures. This is not private Illustrator/font/corpus qualification.
"""
from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


def _require(value, message):
    if not value:
        raise RuntimeError(message)


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# Authored outline artwork, not an installed/bundled font. Provenance and OFL
# attribution are recorded in tests/fixtures/review_ocr_outline_provenance.json.
_AUTHORED_CJK_SVG_PATH = 'M 50.07812 56.28125 L 56.46875 56.28125 L 56.46875 61.25000 L 50.07812 61.25000 L 50.07812 56.28125 M 50.07812 63.76562 L 56.46875 63.76562 L 56.46875 68.76562 L 50.07812 68.76562 L 50.07812 63.76562 M 50.07812 48.84375 L 56.46875 48.84375 L 56.46875 53.76562 L 50.07812 53.76562 L 50.07812 48.84375 M 47.51562 46.20312 L 47.51562 71.40625 L 59.15625 71.40625 L 59.15625 46.20312 L 47.51562 46.20312 M 54.59375 73.35938 C 56.20312 75.35938 58.20312 78.07812 59.03125 79.79688 L 61.43750 78.28125 C 60.51562 76.64062 58.51562 74.00000 56.84375 72.12500 L 54.59375 73.35938 M 49.15625 72.23438 C 47.95312 75.00000 45.87500 77.79688 43.79688 79.64062 C 44.43750 80.04688 45.64062 80.87500 46.15625 81.32812 C 48.31250 79.28125 50.56250 76.07812 51.95312 73.00000 L 49.15625 72.23438 M 69.15625 44.39062 L 69.15625 77.43750 C 69.15625 78.12500 68.87500 78.31250 68.23438 78.35938 C 67.59375 78.35938 65.46875 78.40625 63.07812 78.31250 C 63.46875 79.15625 63.87500 80.43750 64.00000 81.20312 C 67.28125 81.20312 69.18750 81.12500 70.31250 80.59375 C 71.43750 80.15625 71.90625 79.31250 71.90625 77.43750 L 71.90625 44.39062 L 69.15625 44.39062 M 62.20312 48.53125 L 62.20312 71.43750 L 64.82812 71.43750 L 64.82812 48.53125 L 62.20312 48.53125 M 38.23438 46.96875 C 40.51562 48.07812 43.23438 49.96875 44.56250 51.28125 L 46.35938 48.89062 C 44.95312 47.56250 42.23438 45.89062 39.95312 44.84375 L 38.23438 46.96875 M 36.51562 57.76562 C 38.87500 58.76562 41.67188 60.43750 43.07812 61.71875 L 44.79688 59.28125 C 43.40625 58.00000 40.56250 56.48438 38.15625 55.56250 L 36.51562 57.76562 M 37.31250 79.07812 L 40.04688 80.67188 C 41.76562 77.00000 43.79688 72.07812 45.28125 67.87500 L 42.87500 66.32812 C 41.23438 70.79688 38.95312 76.00000 37.31250 79.07812 M 78.54688 56.48438 L 78.54688 58.89062 L 89.29688 58.89062 L 89.29688 56.48438 L 78.54688 56.48438 M 78.54688 61.76562 L 78.54688 64.12500 L 89.29688 64.12500 L 89.29688 61.76562 L 78.54688 61.76562 M 76.85938 51.20312 L 76.85938 53.68750 L 90.01562 53.68750 L 90.01562 51.20312 L 76.85938 51.20312 M 80.62500 45.43750 C 81.70312 47.03125 83.01562 49.35938 83.57812 50.79688 L 86.01562 49.40625 C 85.42188 47.95312 84.10938 45.82812 82.93750 44.23438 L 80.62500 45.43750 M 106.62500 46.43750 C 107.93750 48.03125 109.45312 50.25000 110.09375 51.64062 L 112.29688 50.25000 C 111.62500 48.84375 110.09375 46.71875 108.70312 45.23438 L 106.62500 46.43750 M 78.54688 67.07812 L 78.54688 80.68750 L 81.14062 80.68750 L 81.14062 78.76562 L 89.34375 78.76562 L 89.34375 67.07812 L 78.54688 67.07812 M 81.14062 69.59375 L 86.70312 69.59375 L 86.70312 76.23438 L 81.14062 76.23438 L 81.14062 69.59375 M 102.65625 44.46875 C 102.70312 47.10938 102.73438 49.76562 102.81250 52.28125 L 91.06250 52.28125 L 91.06250 55.07812 L 102.90625 55.07812 C 103.54688 69.71875 105.37500 81.23438 109.93750 81.23438 C 112.37500 81.23438 113.26562 79.31250 113.70312 73.35938 C 112.98438 73.04688 112.01562 72.40625 111.37500 71.76562 C 111.29688 76.23438 110.93750 78.31250 110.29688 78.31250 C 108.17188 78.31250 106.29688 68.56250 105.73438 55.07812 L 113.50000 55.07812 L 113.50000 52.28125 L 105.65625 52.28125 C 105.57812 49.76562 105.54688 47.15625 105.57812 44.46875 L 102.65625 44.46875 M 90.01562 75.25000 L 90.90625 78.17188 C 94.46875 77.17188 99.14062 75.85938 103.54688 74.53125 L 103.26562 71.93750 L 97.65625 73.37500 L 97.65625 63.48438 L 101.98438 63.48438 L 101.98438 60.76562 L 90.65625 60.76562 L 90.65625 63.48438 L 94.90625 63.48438 L 94.90625 74.09375 L 90.01562 75.25000 M 130.60938 44.39062 C 130.12500 46.10938 129.53125 47.87500 128.84375 49.60938 L 117.48438 49.60938 L 117.48438 52.40625 L 127.56250 52.40625 C 125.04688 57.56250 121.37500 62.35938 116.68750 65.56250 C 117.28125 66.15625 118.20312 67.20312 118.64062 67.87500 C 121.09375 66.15625 123.25000 64.04688 125.12500 61.71875 L 125.12500 67.64062 C 125.12500 71.40625 124.76562 75.87500 121.45312 79.07812 C 122.00000 79.51562 123.17188 80.76562 123.53125 81.40625 C 125.92188 79.20312 127.09375 76.20312 127.64062 73.23438 L 144.89062 73.23438 L 144.89062 77.40625 C 144.89062 78.00000 144.68750 78.23438 144.00000 78.23438 C 143.25000 78.28125 140.79688 78.31250 138.17188 78.20312 C 138.56250 79.04688 139.00000 80.28125 139.17188 81.07812 C 142.60938 81.07812 144.79688 81.07812 146.12500 80.64062 C 147.43750 80.12500 147.84375 79.20312 147.84375 77.43750 L 147.84375 57.04688 L 128.35938 57.04688 C 129.28125 55.56250 130.09375 54.00000 130.84375 52.40625 L 152.51562 52.40625 L 152.51562 49.60938 L 132.04688 49.60938 C 132.64062 48.12500 133.17188 46.59375 133.64062 45.10938 L 130.60938 44.39062 M 144.89062 66.43750 L 144.89062 70.64062 L 128.00000 70.64062 C 128.09375 69.59375 128.12500 68.60938 128.12500 67.68750 L 128.12500 66.43750 L 144.89062 66.43750 M 144.89062 63.87500 L 128.12500 63.87500 L 128.12500 59.76562 L 144.89062 59.76562 L 144.89062 63.87500 M 158.62500 46.04688 L 158.62500 81.14062 L 161.31250 81.14062 L 161.31250 48.76562 L 167.10938 48.76562 C 166.26562 51.43750 165.10938 54.96875 163.95312 57.79688 C 166.82812 61.00000 167.54688 63.76562 167.54688 65.96875 C 167.54688 67.20312 167.31250 68.32812 166.71875 68.76562 C 166.34375 68.96875 165.90625 69.07812 165.46875 69.12500 C 164.82812 69.15625 164.03125 69.12500 163.10938 69.07812 C 163.59375 69.84375 163.87500 71.00000 163.87500 71.71875 C 164.75000 71.76562 165.79688 71.76562 166.54688 71.64062 C 167.39062 71.56250 168.10938 71.32812 168.62500 70.92188 C 169.79688 70.07812 170.23438 68.40625 170.23438 66.23438 C 170.23438 63.71875 169.54688 60.84375 166.67188 57.48438 C 167.98438 54.28125 169.46875 50.35938 170.62500 47.07812 L 168.67188 45.92188 L 168.23438 46.04688 L 158.62500 46.04688 M 187.39062 56.15625 L 187.39062 61.12500 L 175.59375 61.12500 L 175.59375 56.15625 L 187.39062 56.15625 M 187.39062 53.64062 L 175.59375 53.64062 L 175.59375 48.81250 L 187.39062 48.81250 L 187.39062 53.64062 M 172.51562 81.21875 C 173.26562 80.70312 174.54688 80.25000 182.78125 78.01562 C 182.70312 77.37500 182.62500 76.12500 182.67188 75.28125 L 175.59375 77.01562 L 175.59375 63.76562 L 179.42188 63.76562 C 181.42188 71.71875 185.23438 77.89062 191.50000 80.93750 C 191.95312 80.09375 192.85938 78.93750 193.54688 78.32812 C 190.34375 77.01562 187.75000 74.76562 185.78125 71.92188 C 187.98438 70.59375 190.62500 68.84375 192.67188 67.15625 L 190.70312 65.04688 C 189.10938 66.51562 186.59375 68.40625 184.46875 69.76562 C 183.46875 67.96875 182.67188 65.92188 182.06250 63.76562 L 190.26562 63.76562 L 190.26562 46.17188 L 172.62500 46.17188 L 172.62500 75.89062 C 172.62500 77.57812 171.79688 78.37500 171.18750 78.73438 C 171.62500 79.32812 172.26562 80.53125 172.51562 81.21875 M 207.60938 45.56250 C 205.09375 51.68750 200.89062 57.56250 196.42188 61.32812 C 197.17188 61.89062 198.50000 63.09375 199.06250 63.73438 C 203.53125 59.60938 207.96875 53.20312 210.85938 46.60938 L 207.60938 45.56250 M 201.45312 79.26562 C 202.93750 78.65625 205.17188 78.53125 226.09375 77.14062 C 226.93750 78.53125 227.65625 79.85938 228.21875 80.93750 L 231.25000 79.29688 C 229.32812 75.73438 225.45312 70.09375 222.21875 65.76562 L 219.32812 67.04688 C 220.93750 69.21875 222.68750 71.81250 224.32812 74.29688 L 205.78125 75.37500 C 209.93750 70.57812 214.04688 64.32812 217.53125 58.12500 L 214.17188 56.68750 C 210.81250 63.53125 205.65625 70.68750 203.96875 72.53125 C 202.45312 74.45312 201.34375 75.78125 200.21875 76.01562 C 200.70312 76.93750 201.25000 78.57812 201.45312 79.26562 M 213.29688 45.40625 L 213.29688 48.48438 L 220.76562 48.48438 C 223.01562 54.53125 226.89062 60.37500 231.40625 63.76562 C 231.93750 62.84375 233.04688 61.57812 233.76562 60.93750 C 229.01562 57.84375 224.96875 51.81250 223.04688 45.40625 L 213.29688 45.40625 M 238.71875 54.07812 L 238.71875 56.71875 L 262.84375 56.71875 L 262.84375 54.07812 L 238.71875 54.07812 M 238.43750 46.96875 L 238.43750 49.84375 L 267.39062 49.84375 L 267.39062 76.68750 C 267.39062 77.43750 267.15625 77.68750 266.43750 77.68750 C 265.59375 77.71875 262.84375 77.76562 260.07812 77.64062 C 260.51562 78.56250 261.00000 80.04688 261.12500 80.92188 C 264.71875 80.92188 267.20312 80.87500 268.59375 80.35938 C 270.03125 79.84375 270.43750 78.79688 270.43750 76.71875 L 270.43750 46.96875 L 238.43750 46.96875 M 244.20312 63.71875 L 257.12500 63.71875 L 257.12500 71.20312 L 244.20312 71.20312 L 244.20312 63.71875 M 241.28125 61.04688 L 241.28125 76.84375 L 244.20312 76.84375 L 244.20312 73.84375 L 260.03125 73.84375 L 260.03125 61.04688 L 241.28125 61.04688'
_OCR_EXPECTED_TEXT = ('測試有限公司', 'REVIEW DEMO', '0900-000-000', 'hello@example.com')


def _compact_text(value):
    return re.sub(r'\s+', '', str(value)).casefold()


def assert_positive_ocr(source):
    """Require actual expected words, line bounds, semantic and safe ownership.

    A successful process, nonempty output or whole-page manual fallback is not
    OCR acceptance. Chinese inter-word spaces are ignored only for comparison.
    """
    cap = source.get('analysis', {}).get('capabilities', {})
    _require(cap.get('ocr_available') and cap.get('ocr_executed'),
             'OCR did not actually execute on the authored bilingual fixture')
    _require(set(('eng', 'chi_tra')) <= set(cap.get('ocr_languages', [])),
             'Actual OCR is missing an English or Traditional Chinese model')
    fields = [(work, field) for work in source.get('works', [])
              for field in work.get('fields', [])]
    matches = {}
    for expected in _OCR_EXPECTED_TEXT:
        matching = [(work, field) for work, field in fields
                    if _compact_text(expected) in _compact_text(field.get('text', ''))]
        _require(matching, 'OCR failed to recognize authored text: ' + expected)
        for work, field in matching:
            rect = field.get('rect') or {}
            values = [rect.get(key) for key in ('x', 'y', 'w', 'h')]
            _require(all(type(value) in (int, float) and math.isfinite(value) for value in values),
                     'OCR candidate has missing or nonfinite geometry')
            x, y, width, height = values
            crop = work['crop']
            _require(x >= 0 and y >= 0 and width > 0 and height > 0
                     and x + width <= crop['w'] + .001 and y + height <= crop['h'] + .001,
                     'OCR candidate is outside the actual work bounds')
            _require(width * height < crop['w'] * crop['h'] * .8,
                     'Whole-page fallback was substituted for an actual OCR line')
            prediction = field.get('prediction') or {}
            _require(prediction.get('classification') == 'OCR_CANDIDATE',
                     'Expected OCR geometry was replaced by another observation channel')
            _require(field.get('owner') is None and prediction.get('owner') is None
                     and prediction.get('owner_status') == 'UNCONFIRMED_LEGACY_CANDIDATE',
                     'OCR fabricated an owner instead of retaining an unconfirmed candidate')
        matches[expected] = [field['id'] for _, field in matching]
    mobile = next(field for _, field in fields
                  if _compact_text('0900-000-000') in _compact_text(field.get('text', '')))
    email = next(field for _, field in fields
                 if _compact_text('hello@example.com') in _compact_text(field.get('text', '')))
    _require(mobile['prediction'].get('semantic', {}).get('semantic_type') == 'mobile'
             and email['prediction'].get('semantic', {}).get('semantic_type') == 'email',
             'Actual OCR text did not reach the existing semantic candidate recognizer')
    return dict(expected_text=list(_OCR_EXPECTED_TEXT), matches=matches,
                owner='UNKNOWN_UNTIL_HUMAN_ASSIGNMENT', geometry='ACTUAL_POSITIVE_LINE_BOUNDS',
                real_corpus_qualified=False)


def authored_ocr_failure_diagnostics(source, authored_root, capability):
    """Bounded diagnostics only for this module's positively authored fixtures.

    Logs persist even when a unittest later removes its TemporaryDirectory.
    Never call this for user artwork: the sentinel and source allowlist below
    are required before reading or printing any recognized text.
    """
    from PySide6.QtGui import QImageReader

    root = Path(authored_root).resolve()
    path = Path(source.get('path', '')).resolve()
    allowed = {'DEMO-bilingual-outline.svg', 'DEMO-bilingual-raster.pdf'}
    _require((root / 'SYNTHETIC_ONLY').read_text(encoding='ascii') == 'NO_PRIVATE_DATA'
             and path.parent == root and path.name in allowed,
             'OCR text diagnostics are restricted to the authored acceptance fixtures')
    fields = [field for work in source.get('works', []) for field in work.get('fields', [])]
    diagnostic = dict(schema_version=1, scope='AUTHORED_FIXTURE_ONLY_NOT_USER_DATA',
        fixture_name=path.name, source_sha256=_digest(path), expected_text=list(_OCR_EXPECTED_TEXT),
        capability=source.get('analysis', {}).get('capabilities', {}),
        actual_fields=[dict(text=str(field.get('text', ''))[:160], rect=field.get('rect'),
                            classification=field.get('prediction', {}).get('classification'),
                            kind=field.get('kind')) for field in fields[:30]],
        actual_fields_count=len(fields), fields_truncated=len(fields) > 30,
        issue_codes=[row.get('code') for row in source.get('issues', [])][:30], pages=[])
    try:
        version = subprocess.run([capability['executable'], '--version'], capture_output=True,
            text=True, encoding='utf-8', errors='replace', timeout=5,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        diagnostic['actual_runtime_version'] = version.stdout.splitlines()[:2]
        diagnostic['runtime_version_exit_code'] = version.returncode
    except (OSError, ValueError, subprocess.TimeoutExpired, KeyError) as error:
        diagnostic['runtime_version_error_type'] = type(error).__name__
    for page in source.get('analysis', {}).get('pages', [])[:2]:
        image = Path(page['image']).resolve()
        image.relative_to(root)
        reader = QImageReader(str(image));size = reader.size()
        proof = page.get('ocr_evidence') or {}
        row = dict(image_sha256=_digest(image), width_pixels=size.width(), height_pixels=size.height(),
                   width_mm=page.get('width_mm'), height_mm=page.get('height_mm'),
                   renderer_identity=page.get('renderer_identity'), ocr_evidence=proof)
        diagnostic['pages'].append(row)
        # Replay is explicitly identified: original raw TSV is not retained by
        # the product adapter. Keep word/block/line IDs to expose split lines.
        languages = proof.get('languages') or [language for language in ('chi_tra', 'eng')
                                               if language in capability.get('languages', [])]
        command = [capability.get('executable', ''), str(image), 'stdout']
        if capability.get('data_dir'):
            command += ['--tessdata-dir', capability['data_dir']]
        command += ['-l', '+'.join(languages), '--psm', '11',
                    '-c', 'tessedit_create_tsv=1', '-c', 'tessedit_create_txt=0']
        try:
            environment = os.environ.copy();environment['OMP_THREAD_LIMIT'] = '1'
            replay = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                errors='replace', timeout=15, env=environment,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            words = []
            for word in csv.DictReader(replay.stdout[:1_048_576].splitlines(), delimiter='\t'):
                if (word.get('text') or '').strip():
                    words.append({key: str(word.get(key, ''))[:80] for key in (
                        'text', 'level', 'page_num', 'block_num', 'par_num', 'line_num',
                        'word_num', 'left', 'top', 'width', 'height', 'conf')})
                    if len(words) >= 64:
                        break
            row['diagnostic_replay'] = dict(not_original_invocation=True, languages=languages,
                exit_code=replay.returncode, words=words, maximum_words=64,
                output_truncated=len(replay.stdout) > 1_048_576)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            row['diagnostic_replay'] = dict(not_original_invocation=True, languages=languages,
                                            error_type=type(error).__name__)
    # All text above comes only from this positively authored synthetic source.
    # Technical paths in renderer metadata are unnecessary; retain safe hashes.
    for row in diagnostic['pages']:
        renderer = row.get('renderer_identity') or {}
        row['renderer_identity'] = {key: renderer[key] for key in (
            'version', 'origin', 'policy', 'executable_sha256') if key in renderer}
    # ASCII JSON survives redirected Windows cp1252 consoles; its Unicode
    # escapes retain every actual Chinese character for later exact decoding.
    print('AUTHORED_OCR_FAILURE_DIAGNOSTICS:' + json.dumps(diagnostic, ensure_ascii=True), flush=True)
    return diagnostic


def assert_bundled_ocr(source, pin, model_manifest, version_line):
    """Bind actual worker inference to the release's exact binary and models."""
    from ..ocr_runtime import VERSION

    cap = source.get('analysis', {}).get('capabilities', {})
    identity = cap.get('ocr_runtime') or {}
    _require(cap.get('ocr_available') and cap.get('ocr_executed')
             and identity.get('origin') == 'BUNDLED' and identity.get('policy') == 'BUNDLED_ONLY',
             'Frozen OCR did not execute the bundled-only runtime')
    _require(pin.get('version') == VERSION and identity.get('version') == VERSION
             and version_line.strip() == 'tesseract v' + VERSION,
             'Actual OCR executable version differs from the fixed release pin')
    _require(all(isinstance(pin.get(key), str) and re.fullmatch(r'[0-9a-f]{64}', pin[key])
                 for key in ('executable_sha256', 'manifest_sha256')),
             'Release OCR binary and manifest hashes are missing')
    _require(identity.get('executable_sha256') == pin.get('executable_sha256')
             and identity.get('runtime_manifest_sha256') == pin.get('manifest_sha256')
             and identity.get('verified_files') == pin.get('files')
             and type(pin.get('files')) is int and pin['files'] > 0,
             'Actual OCR runtime inventory differs from the release pin')
    expected_models = {row['name'].removesuffix('.traineddata'): row['sha256']
                       for row in model_manifest.get('files', [])
                       if row.get('name') in ('eng.traineddata', 'chi_tra.traineddata')}
    _require(set(expected_models) == {'eng', 'chi_tra'}
             and all(re.fullmatch(r'[0-9a-f]{64}', value) for value in expected_models.values()),
             'Release does not identify both actual OCR models')
    proofs = [page.get('ocr_evidence') for page in source.get('analysis', {}).get('pages', [])
              if page.get('ocr_evidence')]
    _require(proofs, 'Actual worker did not preserve OCR invocation evidence')
    for proof in proofs:
        _require(proof.get('executable_sha256') == pin['executable_sha256']
                 and {row['language']: row['sha256'] for row in proof.get('models', [])}
                 == expected_models,
                 'Actual OCR inference did not use both pinned model files')
    return dict(version=VERSION, runtime_origin='BUNDLED', models=['eng', 'chi_tra'],
                executable_sha256=pin['executable_sha256'],
                runtime_manifest_sha256=pin['manifest_sha256'],
                model_sha256=expected_models, actual_version_output=version_line.strip())


def authored_ocr_sources(root):
    """Same authored bilingual artwork as vector outlines and raster pixels."""
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QMarginsF, QRectF, QSizeF
    from PySide6.QtGui import QFont, QImage, QPainter, QPainterPath, QPageSize, QPdfWriter
    from PySide6.QtSvg import QSvgRenderer

    _require(bool(_AUTHORED_CJK_SVG_PATH), 'Authored Chinese outline fixture is missing')
    root = Path(root)
    english = QPainterPath()
    font = QFont('Arial')
    font.setPixelSize(29)
    for y, text in ((136, 'REVIEW DEMO'), (198, '0900-000-000'), (260, 'hello@example.com')):
        english.addText(35, y, font, text)
    outline = root / 'DEMO-bilingual-outline.svg'
    outline.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="60mm" height="30mm" '
        'viewBox="0 0 600 300"><rect width="600" height="300" fill="white"/>'
        '<path fill="#000000" fill-rule="evenodd" d="' + _AUTHORED_CJK_SVG_PATH
        + '"/><path fill="#000000" fill-rule="evenodd" d="'
        + painter_path_svg(english) + '"/></svg>', encoding='utf-8')
    image = QImage(1600, 800, QImage.Format.Format_RGB32)
    image.fill('white')
    painter = QPainter(image)
    renderer = QSvgRenderer(str(outline))
    _require(renderer.isValid(), 'Authored outlined OCR fixture is not valid SVG')
    renderer.render(painter, QRectF(0, 0, 1600, 800))
    painter.end()
    raster = root / 'DEMO-bilingual-raster.png'
    _require(image.save(str(raster)), 'Authored raster OCR fixture could not be saved')
    # The actual tool accepts AI/SVG/PDF, not standalone image files. A PDF
    # containing only these raster pixels exercises that supported path without
    # broadening the product's import contract or hiding a text layer.
    raster_pdf = root / 'DEMO-bilingual-raster.pdf'
    pdf_bytes = QByteArray()
    device = QBuffer(pdf_bytes)
    _require(device.open(QIODevice.OpenModeFlag.WriteOnly), 'Authored PDF memory buffer could not be opened')
    writer = QPdfWriter(device)
    writer.setResolution(72)
    writer.setPageSize(QPageSize(QSizeF(60, 30), QPageSize.Unit.Millimeter))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    painter = QPainter(writer)
    _require(painter.isActive(), 'Authored raster-only PDF could not be created')
    painter.drawImage(QRectF(0, 0, writer.width(), writer.height()), image)
    painter.end()
    del painter
    del writer
    device.close()
    raster_pdf.write_bytes(bytes(pdf_bytes))
    return [outline, raster_pdf]


def painter_path_svg(path):
    commands, index = [], 0
    while index < path.elementCount():
        element = path.elementAt(index)
        if element.isMoveTo():
            commands.append(f'M {element.x:.5f} {element.y:.5f}')
        elif element.isLineTo():
            commands.append(f'L {element.x:.5f} {element.y:.5f}')
        elif element.isCurveTo():
            second, third = path.elementAt(index + 1), path.elementAt(index + 2)
            commands.append(f'C {element.x:.5f} {element.y:.5f} {second.x:.5f} '
                            f'{second.y:.5f} {third.x:.5f} {third.y:.5f}')
            index += 2
        index += 1
    return ' '.join(commands)


@contextmanager
def physical_ocr_fault(executable, scratch, mode):
    """Temporarily damage only the owned staged runtime, with exact restoration.

    No environment preference override and no installed system executable is
    permitted. Release packaging must verify all bytes again after this probe.
    """
    executable, scratch = Path(executable), Path(scratch)
    _require(executable.parent.name == 'tesseract' and executable.parent.parent.name == 'engines',
             'OCR fault probe may only touch the owned staged bundled runtime')
    manifest = executable.parent / 'BUNDLED_RUNTIME.json'
    _require(executable.is_file() and manifest.is_file(), 'Staged OCR runtime is not intact')
    scratch.mkdir(parents=True, exist_ok=True)
    if mode == 'MISSING_EXECUTABLE':
        relocated = scratch / 'quarantined-tesseract.exe'
        _require(not relocated.exists(), 'OCR quarantine already exists')
        original_hash = _digest(executable)
        executable.replace(relocated)
        try:
            yield
        finally:
            relocated.replace(executable)
            _require(_digest(executable) == original_hash, 'Quarantined OCR bytes were not restored')
    elif mode == 'CORRUPT_MANIFEST':
        original = manifest.read_bytes()
        try:
            manifest.write_bytes(b'{"AUTHORED_CORRUPT_OCR_MANIFEST":true}')
            yield
        finally:
            manifest.write_bytes(original)
            _require(manifest.read_bytes() == original, 'OCR manifest was not restored byte-for-byte')
    else:
        raise ValueError('Unsupported authored OCR fault mode')


@contextmanager
def missing_ocr_runtime(capability, scratch):
    if capability.get('runtime', {}).get('origin') == 'BUNDLED':
        with physical_ocr_fault(capability['executable'], scratch, 'MISSING_EXECUTABLE'):
            yield
    else:
        # Explicit local selection is a documented source-development feature.
        # A frozen acceptance run is never allowed to use this branch.
        _require(not getattr(sys, 'frozen', False), 'Frozen OCR must use a physical bundle fault')
        old = os.environ.get('TEMPLATE_AI_TESSERACT')
        os.environ['TEMPLATE_AI_TESSERACT'] = str(Path(scratch) / 'missing-tesseract.exe')
        try:
            yield
        finally:
            if old is None:
                os.environ.pop('TEMPLATE_AI_TESSERACT', None)
            else:
                os.environ['TEMPLATE_AI_TESSERACT'] = old


def authored_sources(root):
    """Calibrated text/outline SVG and a PDF-compatible AI, never native AI."""
    from PySide6.QtCore import QMarginsF, QSizeF
    from PySide6.QtGui import QFont, QPageSize, QPainter, QPainterPath, QPdfWriter, QPen, QColor

    root = Path(root)
    svg = root / 'DEMO-001.svg'
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="60mm" height="30mm" '
        'viewBox="0 0 600 300"><rect x="1" y="1" width="598" height="298" '
        'fill="white" stroke="#335577" stroke-width="1"/>'
        '<g font-family="sans-serif" font-size="25" fill="#17324d">'
        '<text x="35" y="52">Review Demo Company</text>'
        '<text x="35" y="105">Lin Example</text>'
        '<text x="35" y="160">0900-000-000</text>'
        '<text x="35" y="212">hello@example.com</text></g></svg>', encoding='utf-8')
    ai = root / '示例作品.ai'
    writer = QPdfWriter(str(ai))
    writer.setResolution(72)
    writer.setPageSize(QPageSize(QSizeF(60, 30), QPageSize.Unit.Millimeter))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))
    painter = QPainter(writer)
    _require(painter.isActive(), '無法建立明確合成 PDF-compatible AI 測試作品')
    painter.setPen(QPen(QColor('#335577'), .5))
    painter.drawRect(1, 1, 168, 83)
    painter.setFont(QFont('Arial', 7))
    for y, text in [(15, 'Review Demo Company'), (32, 'Lin Example'),
                    (49, '0900-000-000'), (66, 'hello@example.com')]:
        painter.drawText(9, y, text)
    painter.end()
    # Render font outlines into vector paths: the source deliberately has no
    # readable <text> node, just like a common outlined-text delivery.
    outlines = QPainterPath()
    font = QFont('Arial')
    font.setPixelSize(27)
    for y, text in [(65, 'HELLO REVIEW'), (125, '0900-000-000'), (190, 'hello@example.com')]:
        outlines.addText(35, y, font, text)
    commands = []
    index = 0
    while index < outlines.elementCount():
        element = outlines.elementAt(index)
        if element.isMoveTo():
            commands.append(f'M {element.x:.5f} {element.y:.5f}')
        elif element.isLineTo():
            commands.append(f'L {element.x:.5f} {element.y:.5f}')
        elif element.isCurveTo():
            second, third = outlines.elementAt(index + 1), outlines.elementAt(index + 2)
            commands.append(f'C {element.x:.5f} {element.y:.5f} {second.x:.5f} '
                            f'{second.y:.5f} {third.x:.5f} {third.y:.5f}')
            index += 2
        index += 1
    outline = root / 'DEMO-outline.svg'
    outline.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="60mm" height="30mm" '
                       'viewBox="0 0 600 300"><rect x="1" y="1" width="598" height="298" '
                       'fill="white" stroke="#335577" stroke-width="1"/>'
                       '<path fill="#111111" fill-rule="evenodd" d="' + ' '.join(commands)
                       + '"/></svg>', encoding='utf-8')
    return [svg, ai, outline]


def exercise_discard_close(window, source, wait):
    """Actual close dialog while a real owned worker is still running."""
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication.instance()
    window.show()
    app.processEvents()
    window.add_files([str(source)])
    QTest.mouseClick(window.save_button, Qt.MouseButton.LeftButton)
    _require(not window.store.dirty, 'Discard fixture baseline was not saved')
    baseline = window.store.path.read_bytes()
    QTest.mouseClick(window.start_button, Qt.MouseButton.LeftButton)
    wait(lambda: window.jobs.busy and window.jobs._process.processId() > 0, 5)
    window.store.add_owner('UNSAVED_DISCARD_SENTINEL', 'PERSON')
    window._update_save_state()
    handled, errors = [], []

    def choose_discard():
        dialog = app.activeModalWidget()
        try:
            _require(isinstance(dialog, QMessageBox), 'Expected actual close dialog')
            button = next(button for button in dialog.buttons()
                          if button.text() == '放棄未保存修改')
            handled.append(True)
            QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        except Exception as error:
            errors.append(str(error))
            if dialog is not None:
                dialog.reject()

    QTimer.singleShot(15, choose_discard)
    window.close()
    wait(lambda: not window.jobs.is_running(), 10)
    app.processEvents()
    _require(handled and not errors, 'Actual discard interaction failed: ' + '; '.join(errors))
    _require(not window.isVisible(), 'Discard action did not close the window')
    _require(window.store.path.read_bytes() == baseline,
             'Discarded changes were written by background worker stop/finished callbacks')
    return {'saved_snapshot_byte_identical': True, 'actual_owned_worker_stopped': True,
            'actual_close_dialog_used': True}


def run(output_path):
    """Write output JSON even on failure; return an executable exit status."""
    from PySide6.QtCore import QEventLoop, QTimer, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QScrollArea, QInputDialog
    from . import __version__

    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    root = output.parent / (output.stem + '-synthetic')
    # Never reuse an earlier run and turn stale screenshots into new evidence.
    root.mkdir(exist_ok=False)
    (root / 'SYNTHETIC_ONLY').write_text('NO_PRIVATE_DATA', encoding='ascii')
    app = QApplication.instance() or QApplication([])
    quit_on_last = app.quitOnLastWindowClosed()
    app.setQuitOnLastWindowClosed(False)
    checks = []
    details = {}
    dialogs = []
    windows = []
    result = {
        'schema_version': 1, 'status': 'FAIL', 'version': __version__,
        'actual_frozen_executable': bool(getattr(sys, 'frozen', False)),
        'fixture': 'AUTHORED_REVIEW_ACCEPTANCE_V1',
        'fixture_types': ['CALIBRATED_SVG', 'PDF_COMPATIBLE_AI_SIMULATION', 'OUTLINED_TEXT_SVG',
                          'BILINGUAL_OUTLINED_TEXT_SVG', 'RASTER_ONLY_PDF'],
        'worker_mode': 'ACTUAL_QPROCESS', 'checks': checks,
        'check_details': details, 'artifacts': [], 'source_unchanged': False,
        'private_data_included': False, 'real_corpus_qualified': False,
        'native_illustrator_private_format_qualified': False,
        'os_native_file_picker_automated': False,
        'bundled_ocr': {'status': 'NOT_VERIFIED', 'required': bool(getattr(sys, 'frozen', False)),
                        'english_positive': False, 'traditional_chinese_positive': False,
                        'missing_corrupt_fallback_verified': False},
    }
    started = time.monotonic()

    def checked(name, value=True, **evidence):
        _require(not dialogs, '操作出現非預期提示：' + '; '.join(dialogs))
        _require(value, name)
        checks.append(name)
        details[name] = evidence or {'status': 'PASS'}
        (root / 'progress.json').write_text(
            json.dumps({'checks': checks}, ensure_ascii=False, indent=2), encoding='utf-8')
        print('review-release-check:', name, flush=True)

    def wait(predicate, seconds=30):
        if predicate():
            return
        loop = QEventLoop()
        poll = QTimer()
        deadline = QTimer()
        deadline.setSingleShot(True)
        poll.timeout.connect(lambda: loop.quit() if predicate() or dialogs else None)
        deadline.timeout.connect(loop.quit)
        poll.start(20)
        deadline.start(round(seconds * 1000))
        try:
            loop.exec()
        finally:
            poll.stop()
            deadline.stop()
        _require(not dialogs, '操作出現非預期提示：' + '; '.join(dialogs))
        _require(predicate(), '背景操作未於限定時間完成')

    def capture(window, name):
        app.processEvents()
        path = root / (name + '.png')
        _require(window.grab().save(str(path)), '真實視窗截圖未保存')
        result['artifacts'].append({'path': str(path.relative_to(output.parent)),
                                    'sha256': _digest(path), 'kind': 'ACTUAL_QT_WINDOW'})

    def click(widget):
        # QTest can deliver events to a clipped child directly. Scroll it into
        # the actual viewport first so the probe does not hide a layout bug.
        for scroll in widget.window().findChildren(QScrollArea):
            if scroll.isAncestorOf(widget):
                scroll.ensureWidgetVisible(widget)
        app.processEvents()
        _require(widget.isVisible() and not widget.visibleRegion().isEmpty(),
                 '操作按鈕不在可見畫面中：' + widget.text())
        _require(widget.isEnabled(), '操作按鈕目前不可用：' + widget.text())
        QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
        app.processEvents()

    def drag(canvas, start_local, end_local):
        start = canvas.mapFromScene(canvas.local_to_scene(start_local))
        end = canvas.mapFromScene(canvas.local_to_scene(end_local))
        _require(canvas.viewport().rect().contains(start)
                 and canvas.viewport().rect().contains(end), '標記操作超出可見原稿範圍')
        QTest.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.NoModifier, start)
        QTest.mouseMove(canvas.viewport(), end, delay=10)
        QTest.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton,
                           Qt.KeyboardModifier.NoModifier, end)
        app.processEvents()

    def overview_item(tree, match):
        def walk(item):
            if match(item):
                return item
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found is not None:
                    return found
            return None
        for index in range(tree.topLevelItemCount()):
            found = walk(tree.topLevelItem(index))
            if found is not None:
                return found
        raise RuntimeError('總覽缺少可定位的資料列')

    def refuse_unexpected_modal():
        dialog = app.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            if dialog.windowTitle() == '離開前保存工作' and getattr(dialog.parent(), '_acceptance_discard', False):
                return
            dialogs.append(dialog.windowTitle() + ': ' + dialog.text())
            dialog.reject()

    watchdog = QTimer()
    watchdog.timeout.connect(refuse_unexpected_modal)
    watchdog.start(150)
    try:
        from .window import ReviewWindow

        window = ReviewWindow(root / 'data')
        windows.append(window)
        window.show()
        wait(window.isVisible, 10)
        checked('actual_review_window_opens', window.canvas.isVisible())
        checked('technical_overview_hidden_initially', not window.overview_tree.isVisible())
        capture(window, '01-empty-window')

        sources = authored_sources(root)
        source_hashes = {path.name: _digest(path) for path in sources}
        # The public add-files controller receives actual local paths. The OS
        # native picker is explicitly outside this automated smoke scope.
        window.add_files([str(path) for path in sources])
        checked('actual_add_files_entry_registers_three_sources', len(window.store.sources()) == 3)
        finished = []
        window.analysisFinished.connect(lambda: finished.append(True))
        heartbeats = []
        responsiveness = QTimer()
        responsiveness.timeout.connect(lambda: heartbeats.append(time.monotonic()))
        responsiveness.start(100)
        click(window.start_button)
        wait(lambda: bool(finished), 230)
        responsiveness.stop()
        checked('actual_qprocess_analysis_completes', len(window.store.works()) >= 3,
                gui_timer_events=len(heartbeats))
        checked('gui_event_loop_remains_responsive', len(heartbeats) >= 2)

        all_sources = window.store.sources()
        checked('svg_and_pdf_compatible_ai_have_real_previews', all(
            source.get('analysis', {}).get('pages') and all(
                Path(page['image']).is_file() for page in source['analysis']['pages'])
            for source in all_sources))
        capabilities = [source['analysis'].get('capabilities', {}) for source in all_sources]
        details['worker_capabilities'] = capabilities
        checked('actual_vector_analysis_executes', any(
            cap.get('vector_analysis_executed') for cap in capabilities))
        if result['actual_frozen_executable']:
            checked('actual_worker_uses_bundled_inkscape', all(
                cap.get('inkscape_runtime', {}).get('origin') == 'BUNDLED'
                for cap in capabilities))

        outline_source = next(source for source in all_sources if source['name'] == sources[2].name)
        outline_cap = outline_source['analysis']['capabilities']
        if result['actual_frozen_executable']:
            _require(outline_cap.get('ocr_available')
                     and {'eng', 'chi_tra'} <= set(outline_cap.get('ocr_languages', [])),
                     'A frozen release requires actual bundled English and Traditional Chinese OCR')
        if outline_cap.get('ocr_available'):
            checked('actual_ocr_reads_authored_outline_source',
                    outline_cap.get('ocr_executed') and any(work.get('fields')
                                                           for work in outline_source['works']))
            result['ocr_scope'] = 'ACTUAL_LOCAL_OCR_EXECUTED_ON_AUTHORED_OUTLINES'
        else:
            checked('missing_ocr_is_explicit_for_outline_source', any(
                issue.get('code') == 'OCR_UNAVAILABLE' for issue in outline_source.get('issues', [])))
            result['ocr_scope'] = 'OCR_UNAVAILABLE_EXPLICIT_MANUAL_FALLBACK_NOT_OCR_QUALIFICATION'

        from .analysis import _ocr_capability
        local_ocr = _ocr_capability()
        if result['actual_frozen_executable'] or (
                local_ocr.get('available') and {'eng', 'chi_tra'} <= set(local_ocr.get('languages', []))):
            bilingual = ReviewWindow(root / 'bilingual-data')
            windows.append(bilingual)
            bilingual.show()
            bilingual_sources = authored_ocr_sources(root)
            for path in bilingual_sources:
                source_hashes[path.name] = _digest(path)
            sources.extend(bilingual_sources)
            bilingual.add_files([str(path) for path in bilingual_sources])
            bilingual_finished = []
            bilingual.analysisFinished.connect(lambda: bilingual_finished.append(True))
            click(bilingual.start_button)
            wait(lambda: bool(bilingual_finished), 180)
            actual_bilingual = bilingual.store.sources()
            for expected_source in bilingual_sources:
                actual = next(row for row in actual_bilingual if row['name'] == expected_source.name)
                try:
                    proof = assert_positive_ocr(actual)
                except Exception:
                    diagnostic = {'scope': 'AUTHORED_FIXTURE_ONLY_NOT_USER_DATA', 'fixtures': []}
                    for diagnostic_source in actual_bilingual:
                        try:
                            diagnostic['fixtures'].append(authored_ocr_failure_diagnostics(
                                diagnostic_source, root, local_ocr))
                        except Exception as diagnostic_error:
                            diagnostic['fixtures'].append({'diagnostic_error_type': type(diagnostic_error).__name__})
                            print('AUTHORED_OCR_DIAGNOSTIC_ERROR:' + type(diagnostic_error).__name__, flush=True)
                    result['ocr_failure_diagnostics'] = diagnostic
                    (root / 'authored-ocr-failure.json').write_text(
                        json.dumps(diagnostic, ensure_ascii=False, indent=2), encoding='utf-8')
                    raise
                checked('actual_bilingual_ocr_reads_authored_' + (
                    'outlines' if expected_source.suffix == '.svg' else 'raster'), **proof)
            checked('actual_ocr_candidates_keep_ownership_unknown', all(
                field['owner'] is None for row in actual_bilingual
                for work in row['works'] for field in work['fields']))
            result['bundled_ocr'].update(english_positive=True, traditional_chinese_positive=True,
                                         models=['eng', 'chi_tra'])
            if result['actual_frozen_executable']:
                package = Path(sys.executable).resolve().parent
                metadata = Path(getattr(sys, '_MEIPASS', package)) / 'release-info.json'
                pin = json.loads(metadata.read_text(encoding='utf-8'))['tesseract_runtime']
                model_manifest = json.loads((package / 'engines/ocr-models/MODEL_MANIFEST.json').read_text(encoding='utf-8'))
                version_process = subprocess.run([local_ocr['executable'], '--version'],
                    capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=10,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                _require(version_process.returncode == 0, 'Bundled OCR version command failed')
                version_line = version_process.stdout.splitlines()[0]
                runtime_proof = assert_bundled_ocr(actual_bilingual[0], pin, model_manifest, version_line)
                for actual in actual_bilingual[1:]:
                    assert_bundled_ocr(actual, pin, model_manifest, version_line)
                checked('actual_bundled_ocr_binary_and_models_match_release', **runtime_proof)
                standard_installs = [Path(os.environ.get(key, '')) / 'Tesseract-OCR/tesseract.exe'
                                     for key in ('ProgramFiles', 'ProgramFiles(x86)') if os.environ.get(key)]
                checked('clean_host_has_no_ocr_on_path_or_standard_locations',
                        shutil.which('tesseract') is None and not any(path.exists() for path in standard_installs),
                        system_ocr_on_path=False, standard_ocr_installations=0)
                result['bundled_ocr'].update(runtime_proof, status='PASS')
                result['ocr_scope'] = 'BUNDLED_BILINGUAL_OCR_ACTUAL_OUTLINE_AND_RASTER_POSITIVE'
            else:
                result['bundled_ocr'].update(status='SOURCE_LOCAL_POSITIVE_NOT_BUNDLE_QUALIFICATION',
                                             runtime_origin=local_ocr.get('runtime', {}).get('origin'))
            ocr_work = bilingual.store.works()[0]
            ocr_field = next(field for field in ocr_work['fields'] if '0900' in field.get('text', ''))
            ocr_prediction = deepcopy(ocr_field['prediction'])
            human_owner = bilingual.store.add_owner('Authored OCR Person', 'PERSON')
            bilingual.select_work(ocr_work['id'])
            bilingual.select_field(ocr_field['id'])
            owner_index = bilingual.owner_combo.findData(human_owner['id'])
            _require(owner_index >= 0, 'OCR owner selector is not connected to the actual editor')
            bilingual.owner_combo.setCurrentIndex(owner_index)
            click(bilingual.apply_field_button)
            click(bilingual.save_button)
            capture(bilingual, '06-bilingual-ocr-positive')
            bilingual.close()
            ocr_reopened = ReviewWindow(root / 'bilingual-data')
            windows.append(ocr_reopened)
            ocr_reopened.show()
            assigned = ocr_reopened.store.get_field(ocr_work['id'], ocr_field['id'])
            checked('actual_ocr_owner_assignment_survives_save_and_reopen',
                    assigned['owner'] == human_owner['id'] and assigned['prediction'] == ocr_prediction,
                    original_owner='UNKNOWN', current_owner='EXPLICIT_HUMAN_ASSIGNMENT')
            click(ocr_reopened.save_button)
            ocr_reopened.close()

        # Exercise a genuinely missing executable in an owned local worker.
        # Packaged mode physically quarantines the staged bundled executable;
        # environment variables must never bypass its bundled-only policy.
        no_ocr = ReviewWindow(root / 'no-ocr-data')
        windows.append(no_ocr)
        no_ocr.show()
        no_ocr.add_files([str(sources[2])])
        missing_finished = []
        no_ocr.analysisFinished.connect(lambda: missing_finished.append(True))
        with missing_ocr_runtime(local_ocr, root / 'ocr-quarantine'):
            click(no_ocr.start_button)
            wait(lambda: bool(missing_finished), 90)
        missing_source = no_ocr.store.sources()[0]
        checked('real_missing_ocr_worker_preserves_explicit_fallback',
                missing_source['analysis']['capabilities'].get('ocr_available') is False
                and any(issue.get('code') == 'OCR_UNAVAILABLE'
                        for issue in missing_source.get('issues', []))
                and bool(missing_source.get('works')))
        if result['actual_frozen_executable']:
            _require(missing_source['analysis']['capabilities'].get('ocr_runtime', {}).get('error_code')
                     == 'BUNDLED_OCR_RUNTIME_INVALID', 'Missing bundled engine silently fell back to host OCR')
        missing_work = missing_source['works'][0]
        no_ocr.select_work(missing_work['id'])
        missing_count = len(missing_work['fields'])
        next(action for action in no_ocr.add_mark_button.menu().actions()
             if action.text() == '文字欄位').trigger()
        crop = missing_work['crop']
        drag(no_ocr.canvas, (crop['w'] * .1, crop['h'] * .1),
             (crop['w'] * .4, crop['h'] * .3))
        checked('manual_annotation_works_when_ocr_executable_is_missing',
                len(no_ocr.store.get_work(missing_work['id'])['fields']) == missing_count + 1)
        click(no_ocr.save_button)
        capture(no_ocr, '05-no-ocr-manual-fallback')
        no_ocr.close()

        if result['actual_frozen_executable']:
            corrupt = ReviewWindow(root / 'corrupt-ocr-data')
            windows.append(corrupt)
            corrupt.show()
            corrupt.add_files([str(sources[2])])
            corrupt_finished = []
            corrupt.analysisFinished.connect(lambda: corrupt_finished.append(True))
            with physical_ocr_fault(local_ocr['executable'], root / 'ocr-quarantine', 'CORRUPT_MANIFEST'):
                click(corrupt.start_button)
                wait(lambda: bool(corrupt_finished), 90)
            corrupt_source = corrupt.store.sources()[0]
            corrupt_cap = corrupt_source['analysis']['capabilities']
            checked('real_corrupt_bundled_ocr_preserves_explicit_fallback',
                    corrupt_cap.get('ocr_available') is False
                    and corrupt_cap.get('ocr_runtime', {}).get('error_code') == 'BUNDLED_OCR_RUNTIME_INVALID'
                    and any(issue.get('code') == 'OCR_UNAVAILABLE' for issue in corrupt_source.get('issues', []))
                    and bool(corrupt_source.get('works')))
            corrupt_work = corrupt_source['works'][0]
            corrupt.select_work(corrupt_work['id'])
            corrupt_count = len(corrupt_work['fields'])
            next(action for action in corrupt.add_mark_button.menu().actions()
                 if action.text() == '文字欄位').trigger()
            corrupt_crop = corrupt_work['crop']
            drag(corrupt.canvas, (corrupt_crop['w'] * .1, corrupt_crop['h'] * .1),
                 (corrupt_crop['w'] * .4, corrupt_crop['h'] * .3))
            checked('manual_annotation_works_when_bundled_ocr_manifest_is_corrupt',
                    len(corrupt.store.get_work(corrupt_work['id'])['fields']) == corrupt_count + 1)
            click(corrupt.save_button)
            capture(corrupt, '07-corrupt-ocr-manual-fallback')
            corrupt.close()
            result['bundled_ocr']['missing_corrupt_fallback_verified'] = True
        app.processEvents()
        window.raise_()
        window.activateWindow()

        work = next(work for work in window.store.works() if work.get('fields'))
        work_id = work['id']
        field = next((item for item in work['fields'] if '0900' in item.get('text', '')),
                     work['fields'][0])
        field_id = field['id']
        original_prediction = deepcopy(field['prediction'])
        window.select_work(work_id)
        app.processEvents()
        QTest.mouseClick(window.canvas.viewport(), Qt.MouseButton.LeftButton,
                         pos=window.canvas.field_center(field_id))
        app.processEvents()
        checked('canvas_click_updates_actual_editor',
                window.text_edit.toPlainText() == field['text'])

        owner = window.store.add_owner('Synthetic Person', 'PERSON')
        shared = window.store.add_owner('Synthetic Shared Person', 'PERSON')
        window.select_field(field_id)
        app.processEvents()
        owner_index = window.owner_combo.findData(owner['id'])
        _require(owner_index >= 0, '人物資料未接入實際歸屬選單')
        window.owner_combo.setCurrentIndex(owner_index)
        desired_kind = 'mobile'
        kind_index = window.kind_combo.findData(desired_kind)
        _require(kind_index >= 0, '欄位種類選單缺少手機')
        window.kind_combo.setCurrentIndex(kind_index)
        private_marker = 'PRIVATE_REVIEW_SENTINEL_91'
        window.text_edit.setPlainText('0900-000-000 ' + private_marker)
        review_index = window.review_combo.findData('REVIEWED')
        _require(review_index >= 0, '缺少明確人工核對狀態')
        window.review_combo.setCurrentIndex(review_index)
        matched_shared = False
        for index in range(window.shared_list.count()):
            item = window.shared_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == shared['id']:
                item.setCheckState(Qt.CheckState.Checked)
                matched_shared = True
        _require(matched_shared, '共享人物未接入實際核對面板')
        click(window.apply_field_button)
        changed = window.store.get_field(work_id, field_id)
        checked('actual_editor_applies_content_kind_owner_and_sharing',
                changed['kind'] == desired_kind and changed['owner'] == owner['id']
                and shared['id'] in changed['shared_with'] and private_marker in changed['text'])
        checked('original_prediction_remains_separate', changed['prediction'] == original_prediction)

        # Exercise the real menu action, drawing gesture and controller; no
        # substituted annotation handler or preconstructed fake window.
        before_ids = {part['id'] for part in window.store.get_work(work_id)['fields']}
        action = next(action for action in window.add_mark_button.menu().actions()
                      if action.text() == '文字欄位')
        action.trigger()
        work = window.store.get_work(work_id)
        width, height = work['crop']['w'], work['crop']['h']
        drag(window.canvas, (width * .70, height * .70), (width * .88, height * .82))
        after = window.store.get_work(work_id)['fields']
        new_fields = [part for part in after if part['id'] not in before_ids]
        checked('actual_canvas_draw_creates_manual_annotation', len(new_fields) == 1)
        added_id = new_fields[0]['id']
        before_rect = deepcopy(new_fields[0]['rect'])
        window.select_field(added_id)
        click(window.resize_button)
        drag(window.canvas,
             (before_rect['x'] + before_rect['w'], before_rect['y'] + before_rect['h']),
             (before_rect['x'] + before_rect['w'] + width * .025,
              before_rect['y'] + before_rect['h'] + height * .03))
        resized = window.store.get_field(work_id, added_id)['rect']
        checked('actual_canvas_resize_updates_annotation_only',
                resized['w'] > before_rect['w'] and resized['h'] > before_rect['h'])
        remove = next(button for button in window.findChildren(QPushButton)
                      if button.text() == '移除這個標記')
        click(remove)
        checked('actual_remove_button_removes_only_annotation',
                added_id not in {part['id'] for part in window.store.get_work(work_id)['fields']})
        click(window.undo_button)
        checked('actual_undo_button_restores_removed_annotation',
                window.store.get_field(work_id, added_id)['rect'] == resized)
        window.select_field(field_id)

        other_id = next(part['id'] for part in window.store.get_work(work_id)['fields']
                        if part['id'] not in (field_id, added_id))
        QTest.mouseClick(window.canvas.viewport(), Qt.MouseButton.LeftButton,
                         pos=window.canvas.field_center(field_id))
        QTest.mouseClick(window.canvas.viewport(), Qt.MouseButton.LeftButton,
                         Qt.KeyboardModifier.ControlModifier,
                         window.canvas.field_center(other_id))
        checked('actual_multiselection_retains_both_relation_endpoints',
                set(window.canvas.selected_fields()) == {field_id, other_id})
        modal_seen = []
        modal_errors = []

        def select_group_relation():
            dialog = app.activeModalWidget()
            try:
                _require(isinstance(dialog, QInputDialog), '未開啟真正的關係選擇視窗')
                dialog.setTextValue('同一組')
                modal_seen.append(True)
                dialog.accept()
            except Exception as error:
                modal_errors.append(str(error))
                if dialog is not None:
                    dialog.reject()

        QTimer.singleShot(60, select_group_relation)
        click(window.relation_button)
        _require(not modal_errors and modal_seen, '關係視窗未完成真實操作')
        checked('actual_relation_dialog_creates_group', any(
            relation.get('kind') == 'group' and set(relation.get('field_ids', [])) == {field_id, other_id}
            for relation in window.store.get_work(work_id)['relations']))
        window.select_field(field_id)

        click(window.overview_button)
        app.processEvents()
        checked('overview_preserves_visible_original',
                window.overview_tree.isVisible() and window.canvas.isVisible())
        # Click the actual overview data row so controller wiring is covered.
        size_row = overview_item(window.overview_tree, lambda item:
            item.data(0, Qt.ItemDataRole.UserRole) in [('metric', 'width'), ['metric', 'width']])
        window.overview_tree.scrollToItem(size_row)
        QTest.mouseClick(window.overview_tree.viewport(), Qt.MouseButton.LeftButton,
                         pos=window.overview_tree.visualItemRect(size_row).center())
        app.processEvents()
        checked('actual_overview_row_draws_linked_dimensions', bool(window.canvas.measurement_items))
        capture(window, '02-overview-dimensions')
        QTest.mouseClick(window.canvas.viewport(), Qt.MouseButton.LeftButton,
                         pos=window.canvas.field_center(other_id))
        app.processEvents()
        checked('canvas_selection_updates_overview_without_leaving_mode',
                window.overview_tree.isVisible() and window.current_field_id == other_id)
        window.show_review()

        unchecked_before = sum(item['review_state'] == 'UNCHECKED'
                               for item in window.store.get_work(work_id)['fields'])
        if unchecked_before:
            click(window.complete_button)
            checked('completion_does_not_silently_review_unchecked',
                    sum(item['review_state'] == 'UNCHECKED'
                        for item in window.store.get_work(work_id)['fields']) == unchecked_before
                    and window.store.get_work(work_id)['review_state'] == 'UNCHECKED')
        remaining = [item for item in window.store.get_work(work_id)['fields'] if item['id'] != field_id]
        for item in remaining:
            window.store.update_field(work_id, item['id'], {'review_state': 'REVIEWED'})
        unknown_id = added_id
        window.select_field(unknown_id)
        window.review_combo.setCurrentIndex(window.review_combo.findData('UNKNOWN'))
        click(window.apply_field_button)
        click(window.complete_button)
        checked('explicit_unknown_survives_human_completion',
                window.store.get_field(work_id, unknown_id)['review_state'] == 'UNKNOWN'
                and window.store.get_work(work_id)['review_state'] == 'REVIEWED_WITH_UNKNOWNS')

        window.select_field(field_id)
        click(window.save_button)
        checked('actual_save_button_persists_session', not window.store.dirty)
        capture(window, '03-saved-review')
        saved = deepcopy(window.store.data)
        window.close()
        app.processEvents()
        reopened = ReviewWindow(root / 'data')
        windows.append(reopened)
        reopened.show()
        app.processEvents()
        restored = reopened.store.get_field(work_id, field_id)
        checked('actual_window_reopens_saved_corrections', restored == changed or (
            restored['text'] == changed['text'] and restored['owner'] == changed['owner']
            and restored['shared_with'] == changed['shared_with']
            and restored['prediction'] == original_prediction))
        checked('unknown_is_not_replaced_by_defaults_after_reopen',
                reopened.store.get_field(work_id, unknown_id)['review_state'] == 'UNKNOWN')
        checked('source_ids_and_work_ids_survive_reopen',
                [s['id'] for s in reopened.store.sources()] == [s['id'] for s in saved['sources']])

        discarded = ReviewWindow(root / 'discard-data')
        discarded._acceptance_discard = True
        discard_evidence = exercise_discard_close(discarded, sources[0], wait)
        checked('actual_discard_does_not_save_draft_on_worker_stop', **discard_evidence)
        # The discarded window is deliberately not passed to finally's save
        # cleanup, which would undo the very behavior being verified.
        discarded.deleteLater()
        app.processEvents()

        report = root / 'safe-report.json'
        reopened.export_report(str(report))
        raw_report = report.read_bytes()
        report_data = json.loads(raw_report.decode('utf-8'))

        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, dict):
                for key, part in value.items():
                    yield str(key)
                    yield from strings(part)
            elif isinstance(value, list):
                for part in value:
                    yield from strings(part)

        decoded_report = '\n'.join(strings(report_data))
        normalized_report = decoded_report.replace('\\', '/').casefold()
        checked('safe_diagnostic_excludes_private_content_and_paths',
                private_marker not in decoded_report
                and str(root).replace('\\', '/').casefold() not in normalized_report
                and all(path.name not in decoded_report for path in sources))
        for path in sources:
            _require(_digest(path) == source_hashes[path.name], '原稿內容遭到修改')
        result['source_unchanged'] = True
        checked('all_authored_sources_remain_byte_identical')
        capture(reopened, '04-reopened-window')
        result['status'] = 'PASS'
    except Exception as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error)[:1200]}
    finally:
        result['elapsed_seconds'] = round(time.monotonic() - started, 3)
        for window in windows:
            try:
                if window.jobs.is_running():
                    window.jobs.stop()
                    deadline = time.monotonic() + 10
                    while window.jobs.is_running() and time.monotonic() < deadline:
                        QTest.qWait(20)
                # Close through the real handler after an explicit save so a
                # failed probe does not strand a hidden modal dialog.
                window.save_progress()
                window.close()
            except Exception:
                pass
        app.processEvents()
        watchdog.stop()
        app.setQuitOnLastWindowClosed(quit_on_last)
        if dialogs:
            result['status'] = 'FAIL'
            result['unexpected_dialogs'] = dialogs
        temp = output.with_suffix(output.suffix + '.tmp')
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temp, output)
    return 0 if result['status'] == 'PASS' else 1

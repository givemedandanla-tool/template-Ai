"""Inkscape semantic recovery alongside an independent appearance reference.

Derived SVG declarations never become original font identity evidence. All
artifacts stay local; diagnostics use the fixed vocabulary shared by the UI.
"""
from pathlib import Path
import shutil
import subprocess
import os
import re
import tempfile
import xml.etree.ElementTree as ET

import numpy as np
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtPdf import QPdfDocument

from .background import file_digest
from .recovery_diagnostics import VERSION, issue

_CONVERTER_VERSIONS={}


def converter_version(executable):
    if not executable:return None
    try:
        stat=Path(executable).stat();key=(str(executable),stat.st_mtime_ns,stat.st_size)
        if key not in _CONVERTER_VERSIONS:
            with tempfile.TemporaryDirectory(prefix='template-ai-version-') as folder:
                env=os.environ.copy();env['INKSCAPE_PROFILE_DIR']=folder
                result=subprocess.run([executable,'--version'],capture_output=True,text=True,timeout=10,env=env,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            match=re.search(r'Inkscape ([0-9]+(?:\.[0-9]+){1,3})',result.stdout)
            _CONVERTER_VERSIONS[key]=match[1] if result.returncode==0 and match else None
        return _CONVERTER_VERSIONS[key]
    except (OSError,subprocess.TimeoutExpired):return None


def image_gray(image):
    if image.isNull() or image.width()*image.height() > 12_000_000:
        raise ValueError('Invalid or oversized comparison image')
    converted = image.convertToFormat(QImage.Format_Grayscale8)
    return np.frombuffer(converted.constBits(), dtype=np.uint8).reshape(
        converted.height(), converted.bytesPerLine())[:, :converted.width()].copy()


def compare_images(reference, candidate, *, max_mean_error=.03, min_ink_iou=.80):
    if not 0 <= max_mean_error <= 1 or not 0 <= min_ink_iou <= 1:
        raise ValueError('Invalid visual comparison policy')
    a, b = image_gray(reference), image_gray(candidate)
    if a.shape != b.shape:
        return dict(status='REVIEW_REQUIRED', reason='DIMENSION_MISMATCH', policy=dict(
            max_mean_error=max_mean_error, min_ink_iou=min_ink_iou))
    mae = float(np.mean(np.abs(a.astype(float)-b.astype(float)))/255)
    ink_a, ink_b = a < 200, b < 200
    union = int(np.count_nonzero(ink_a | ink_b))
    iou = float(np.count_nonzero(ink_a & ink_b)/union) if union else 1.
    return dict(status='WITHIN_POLICY' if mae <= max_mean_error and iou >= min_ink_iou else 'REVIEW_REQUIRED',
                mean_absolute_error=mae, ink_iou=iou, ink_pixels=union,
                policy=dict(max_mean_error=max_mean_error, min_ink_iou=min_ink_iou),
                qualification='DIGITAL_COMPARISON_ONLY_NOT_PRINT_OR_FONT_IDENTITY')


def recover_semantics(path, directory, page, is_pdf, converter, *, run):
    path, directory = Path(path), Path(directory)
    target = directory/'semantic.svg'
    report = dict(schema=VERSION, source_kind='PDF' if is_pdf else 'SVG' if path.suffix.lower()=='.svg' else 'OTHER',
                  semantic_status='UNKNOWN', fidelity_status='UNKNOWN', issues=[], counts={})
    report['software_versions']=dict(inkscape=converter_version(converter))
    try:
        if path.suffix.lower()=='.svg':
            shutil.copyfile(path, target)
            report['semantic_status'] = 'ORIGINAL_TEXT'
        elif converter:
            arguments = [str(path), '--export-plain-svg', '--export-type=svg', '--export-filename='+str(target)]
            if is_pdf:
                # Internal importer preserves text; Poppler route serves appearance.
                arguments += [f'--pages={page}', '--pdf-font-strategy=keep']
            try:run(converter, arguments, directory)
            except ValueError as error:
                if not is_pdf or '--pdf-font-strategy' not in str(error):raise
                target.unlink(missing_ok=True)
                run(converter,[arg for arg in arguments if not arg.startswith('--pdf-font-strategy')],directory)
                report['issues'].append(issue('CONVERTER_VARIANT_UNAVAILABLE'))
            report['semantic_status'] = 'DERIVATIVE_TEXT'
            report['issues'].append(issue('DERIVATIVE_TEXT_ONLY'))
        else:
            report['issues'].append(issue('CONVERTER_UNAVAILABLE'))
            return '', report
        if target.stat().st_size > 32_000_000:
            raise ValueError('Semantic SVG exceeds bounded parser budget')
        raw = target.read_bytes()
        if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
            raise ValueError('External XML declarations are not semantic evidence')
        root = ET.fromstring(raw)
        nodes = list(root.iter())
        if len(nodes) > 100000:
            raise ValueError('Semantic SVG node budget exceeded')
        texts = [node for node in nodes if node.tag.rsplit('}',1)[-1]=='text' and ''.join(node.itertext()).strip()]
        report['counts'] = dict(text_nodes=len(texts), path_nodes=sum(node.tag.rsplit('}',1)[-1]=='path' for node in nodes))
        if not texts:
            report['semantic_status'] = 'NO_TEXT'
            report['issues'].append(issue('NO_EDITABLE_TEXT'))
        report['semantic_sha256'] = file_digest(target)
        return str(target), report
    except (ValueError, OSError, ET.ParseError, subprocess.TimeoutExpired):
        target.unlink(missing_ok=True)
        report['semantic_status'] = 'FAILED'
        report['issues'].append(issue('SEMANTIC_CONVERSION_FAILED'))
        return '', report


def original_pdf_reference(path, page, size):
    document = QPdfDocument()
    try:
        if document.load(str(path)) != QPdfDocument.Error.None_:
            raise ValueError('Original PDF reference unavailable')
        result = document.render(page-1, QSize(*size))
        if result.isNull():
            raise ValueError('Original PDF reference rendering failed')
        return result
    finally:
        document.close()

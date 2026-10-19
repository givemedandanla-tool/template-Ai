"""Read original-source declarations without promoting derivative/default fonts.

Records are page-scoped, not automatic work/person/field assignments. PDF visitor
matrices are extraction context, never claimed as exact glyph coordinates.
"""
from __future__ import annotations

from io import BytesIO
import hashlib
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .design_observation import ObservedScalar, canonical_digest, effective_point_size, unknown
from .source_links import verify_source

VERSION = 'original-text-observation-1'
MAX_BYTES = 32_000_000
MAX_NODES = 4000
MAX_RUNS = 512
MAX_TEXT = 100_000
IDENTITY = (1., 0., 0., 1., 0., 0.)
NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'


class EvidenceBudget(ValueError):
    pass


def _finite(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('Nonfinite source text metric')
    return result


def _multiply(a, b):
    return (a[0]*b[0]+a[2]*b[1], a[1]*b[0]+a[3]*b[1],
            a[0]*b[2]+a[2]*b[3], a[1]*b[2]+a[3]*b[3],
            a[0]*b[4]+a[2]*b[5]+a[4], a[1]*b[4]+a[3]*b[5]+a[5])


def _transform(value):
    result, end = IDENTITY, 0
    for match in re.finditer(r'([A-Za-z]+)\s*\(([^()]*)\)', value):
        if value[end:match.start()].strip(' ,\t\r\n'):
            raise ValueError('Unsupported source transform')
        name = match[1]
        items = match[2].replace(',', ' ').split()
        if not all(re.fullmatch(NUMBER, item) for item in items):
            raise ValueError('Unsupported source transform operands')
        v = [_finite(item) for item in items]
        if name == 'matrix' and len(v) == 6:
            current = tuple(v)
        elif name == 'translate' and len(v) in (1, 2):
            current = (1, 0, 0, 1, v[0], v[1] if len(v) == 2 else 0)
        elif name == 'scale' and len(v) in (1, 2):
            current = (v[0], 0, 0, v[1] if len(v) == 2 else v[0], 0, 0)
        elif name == 'rotate' and len(v) in (1, 3):
            angle = math.radians(v[0]); c, s = math.cos(angle), math.sin(angle)
            current = (c, s, -s, c, 0, 0)
            if len(v) == 3:
                current = _multiply(_multiply((1, 0, 0, 1, v[1], v[2]), current),
                                    (1, 0, 0, 1, -v[1], -v[2]))
        else:
            raise ValueError('Unsupported source transform')
        result = _multiply(result, current); end = match.end()
    if value[end:].strip(' ,\t\r\n'):
        raise ValueError('Unsupported source transform')
    if not all(math.isfinite(x) for x in result):
        raise ValueError('Nonfinite source transform')
    return result


def _length(value):
    match = re.fullmatch(r'\s*(' + NUMBER + r')\s*(px|pt|mm|cm|in)?\s*', value)
    if not match:
        raise ValueError('Relative or unsupported font length')
    return _finite(match[1])*{'': 1, 'px': 1, 'pt': 96/72, 'mm': 96/25.4,
                              'cm': 960/25.4, 'in': 96}[match[2] or '']


def _run(source, locator, value):
    ref = 'SOURCE_TEXT:'+canonical_digest([source['hash'], source.get('page', 1), locator])
    return dict(id=ref, source_locator=locator, text_sha256=hashlib.sha256(value.encode()).hexdigest(),
                decoded_character_count=len(value), font_declaration=None, font_program_sha256=None,
                font_asset_identity='UNKNOWN', source_pt=unknown('pt'), declared_pt=unknown('pt'),
                baseline_anchor_mm=None, baseline_status='UNKNOWN', glyph_runs='UNKNOWN',
                shaped_advance=unknown('mm'), tracking=unknown('mm'), horizontal_scale=unknown('ratio'),
                role_mapping='UNKNOWN', evidence_refs=[ref])


def _svg(source, data):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('SVG entity declarations unsupported')
    root = ET.fromstring(data)
    if root.tag.rsplit('}', 1)[-1] != 'svg':
        raise ValueError('Not an original SVG document')
    nodes = list(root.iter())
    if len(nodes) > MAX_NODES:
        raise EvidenceBudget('SVG node processing budget exceeded')
    css = any(n.tag.rsplit('}', 1)[-1] == 'style' for n in nodes)
    try:
        viewport_width = _length(root.attrib['width'])*25.4/96
        viewport_height = _length(root.attrib['height'])*25.4/96
        physical_known = (viewport_width > 0 and viewport_height > 0
                          and math.isclose(viewport_width, source['width_mm'], rel_tol=1e-7)
                          and math.isclose(viewport_height, source['height_mm'], rel_tol=1e-7))
    except (KeyError, ValueError, OverflowError):
        physical_known = False
    raw_box = root.get('viewBox')
    if raw_box:
        box = [_finite(v) for v in raw_box.replace(',', ' ').split()]
        if len(box) != 4 or box[2] <= 0 or box[3] <= 0:
            raise ValueError('Invalid SVG viewBox')
        sx, sy = source['width_mm']/box[2], source['height_mm']/box[3]
        aspect = root.get('preserveAspectRatio', 'xMidYMid meet').strip()
        if aspect == 'none':
            viewport = (sx, 0, 0, sy, -box[0]*sx, -box[1]*sy)
        elif aspect in ('xMidYMid', 'xMidYMid meet'):
            scale = min(sx, sy)
            viewport = (scale, 0, 0, scale,
                        -box[0]*scale+(source['width_mm']-box[2]*scale)/2,
                        -box[1]*scale+(source['height_mm']-box[3]*scale)/2)
        else:
            viewport = None
    else:
        viewport = (25.4/96, 0, 0, 25.4/96, 0, 0)
    if not physical_known:
        viewport = None
    result, characters = [], 0

    def walk(node, path, inherited, matrix, in_text=False):
        nonlocal characters
        kind = node.tag.rsplit('}', 1)[-1]
        style = dict(inherited)
        style.update({k: v for k, v in node.attrib.items() if k in (
            'font-size', 'font-family', 'font-style', 'font-weight', 'writing-mode',
            'baseline-shift', 'dominant-baseline', 'display', 'visibility')})
        for declaration in node.get('style', '').split(';'):
            key, separator, value = declaration.partition(':')
            if separator:
                style[key.strip()] = value.strip()
        try:
            matrix = _multiply(matrix, _transform(node.get('transform', ''))) if matrix else None
        except ValueError:
            matrix = None
        if kind == 'svg' and path:
            matrix = None  # Nested viewport semantics are not guessed.
        if kind in ('text', 'tspan') and node.text and node.text.strip():
            characters += len(node.text)
            if len(result) >= MAX_RUNS or characters > MAX_TEXT:
                raise EvidenceBudget('SVG text processing budget exceeded')
            row = _run(source, dict(kind='SVG_TEXT', tree_path=path, object_id=node.get('id')), node.text)
            row['font_declaration'] = {k: style[k][:500] for k in
                ('font-family', 'font-size', 'font-style', 'font-weight') if k in style}
            safe = (not css and not any(k in style for k in ('font', 'font-size-adjust'))
                    and not any('!' in v or 'var(' in v for v in style.values()))
            if any(k in style for k in ('transform', 'transform-origin', 'transform-box', 'zoom')):
                matrix = None
            try:
                size = _length(style['font-size'])
                if size <= 0:
                    raise ValueError('Font size must be positive')
                if safe:
                    declared = ObservedScalar(size*72/96, 'pt', 'OBSERVED',
                                              'ORIGINAL_SVG_FONT_DECLARATION_CSS_UNITS', (row['id'],))
                    row['declared_pt'] = declared.to_dict()
                    if matrix:
                        physical = tuple(v*96/25.4 if i < 4 else v for i, v in enumerate(matrix))
                        row['source_pt'] = effective_point_size(declared, physical).to_dict()
            except (ValueError, KeyError, OverflowError):
                pass
            # This is a declared text anchor, not recovered glyph ink bounds.
            if (safe and matrix and node.get('x') is not None and node.get('y') is not None
                    and not any(k in style for k in ('baseline-shift', 'dominant-baseline', 'writing-mode'))
                    and not any(node.get(k) for k in ('dx', 'dy', 'rotate', 'textLength'))):
                try:
                    x, y = _length(node.get('x')), _length(node.get('y'))
                    row['baseline_anchor_mm'] = dict(x=matrix[0]*x+matrix[2]*y+matrix[4],
                                                    y=matrix[1]*x+matrix[3]*y+matrix[5])
                    row['baseline_status'] = 'DECLARED_ANCHOR_NOT_GLYPH_ORIGIN'
                except ValueError:
                    pass
            row['stylesheet_unresolved'] = css
            row['visibility'] = ('UNKNOWN' if css else 'HIDDEN' if style.get('display') == 'none'
                                 or style.get('visibility') in ('hidden', 'collapse') else 'DECLARED_VISIBLE')
            result.append(row)
        for index, child in enumerate(node):
            walk(child, path+[index], style, matrix, in_text or kind in ('text', 'tspan'))
            if child.tail and child.tail.strip() and (in_text or kind in ('text', 'tspan')):
                characters += len(child.tail)
                if len(result) >= MAX_RUNS or characters > MAX_TEXT:
                    raise EvidenceBudget('SVG text processing budget exceeded')
                result.append(_run(source, dict(kind='SVG_TEXT_TAIL', tree_path=path+[index]), child.tail))

    walk(root, [], {}, viewport)
    return 'ORIGINAL_SVG', result


def _pdf(source, data):
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(data), strict=True)
    if reader.is_encrypted:
        raise ValueError('Encrypted source is not training evidence')
    page_number = source.get('page', 1)
    if type(page_number) is not int or not 1 <= page_number <= len(reader.pages):
        raise ValueError('Original PDF page is unavailable')
    page = reader.pages[page_number-1]
    contents = page.get_contents()
    if contents and len(contents.get_data()) > 8_000_000:
        raise EvidenceBudget('PDF content processing budget exceeded')
    result, characters = [], 0

    def visit(value, cm, tm, font, size):
        nonlocal characters
        if not value.strip():
            return
        characters += len(value)
        if len(result) >= MAX_RUNS or characters > MAX_TEXT:
            raise EvidenceBudget('PDF text processing budget exceeded')
        row = _run(source, dict(kind='PDF_TEXT_VISITOR', index=len(result)), value)
        row['extraction_context'] = dict(cm=[_finite(v) for v in cm], tm=[_finite(v) for v in tm],
                                        basis='PYPDF_VISITOR_CONTEXT_NOT_EXACT_GLYPH_ORIGIN')
        if font:
            row['font_declaration'] = dict(base_font=str(font.get('/BaseFont', ''))[:500],
                                          subtype=str(font.get('/Subtype', ''))[:100])
            try:
                scalar = _finite(size)
                if scalar > 0:
                    row['declared_pt'] = ObservedScalar(scalar, 'pt', 'OBSERVED',
                        'ORIGINAL_PDF_TEXT_STATE_FONT_SIZE_NOT_PHYSICAL_SCALE', (row['id'],)).to_dict()
            except (ValueError, OverflowError):
                pass
            descendants = font.get('/DescendantFonts')
            descriptor = (descendants[0].get_object() if descendants else font).get('/FontDescriptor')
            descriptor = descriptor.get_object() if descriptor else {}
            for key in ('/FontFile', '/FontFile2', '/FontFile3'):
                stream = descriptor.get(key)
                if stream:
                    program = stream.get_object().get_data()
                    if len(program) > 8_000_000:
                        raise EvidenceBudget('Embedded font processing budget exceeded')
                    row['font_program_sha256'] = hashlib.sha256(program).hexdigest()
                    row['embedded_program_kind'] = key
                    break
        result.append(row)

    page.extract_text(visitor_text=visit)
    return 'ORIGINAL_PDF_COMPATIBILITY_LAYER_NOT_ILLUSTRATOR_PRIVATE', result


def original_text_observation(source):
    """Hash-verified, bounded observation; never substitutes a converted cache.

    Unsupported/budget-limited inputs produce no partial pretend-complete runs.
    A changed source raises instead of returning a usable observation.
    """
    before = verify_source(source['current_path'], source['hash'])
    path = Path(source['current_path'])
    document = dict(version=VERSION, source_hash=source['hash'], page=source.get('page', 1),
                    scope='SOURCE_PAGE_NOT_WORK_OR_FIELD', state='UNSUPPORTED', channel='UNKNOWN',
                    native_illustrator_editability='UNKNOWN', qualification='NOT_EVALUATED', runs=[])
    try:
        if path.stat().st_size > MAX_BYTES:
            raise EvidenceBudget('Original text processing budget exceeded')
        data = path.read_bytes()
        if data.startswith(b'%PDF-'):
            channel, rows = _pdf(source, data)
        elif path.suffix.lower() == '.svg':
            if source.get('page', 1) != 1:
                raise ValueError('SVG source has no requested page')
            channel, rows = _svg(source, data)
        else:
            channel, rows = 'UNSUPPORTED_ORIGINAL_FORMAT', []
        document.update(channel=channel, runs=rows,
                        state='OBSERVED' if rows else 'NO_READABLE_TEXT' if channel != 'UNSUPPORTED_ORIGINAL_FORMAT' else 'UNSUPPORTED')
    except EvidenceBudget:
        document.update(state='BUDGET_EXCEEDED', reason='BOUNDED_EXTRACTION_NO_PARTIAL_RESULT')
    except Exception as error:
        # Parser errors cannot manufacture source truth or leak customer text.
        document.update(state='UNAVAILABLE', reason=type(error).__name__)
    after = verify_source(source['current_path'], source['hash'])
    if before.stat != after.stat:
        raise ValueError('Original source changed during text observation')
    document['document_digest'] = canonical_digest(document)
    return document

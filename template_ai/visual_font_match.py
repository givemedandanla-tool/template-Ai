"""Local, bounded font outline matching; OCR is text evidence, not font proof.

Qt performs shaping with an exact raw-face check. Symmetric distance transforms
and foreground overlap compare glyph shapes after fitting physical scale. No
model, crop or font is sent to a service and no font substitution is permitted.
"""
from contextlib import contextmanager
import hashlib
import math
from pathlib import Path
import tempfile

import numpy as np
from scipy.ndimage import distance_transform_edt
from PySide6.QtCore import QByteArray, QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter, QPainterPath, QRawFont, QTextLayout, QTransform

from .background import file_digest
from .font_catalog import face_fingerprint
from .font_evidence import face_bytes
from .recovery_diagnostics import issue
from .source_recovery import image_gray

VERSION = 'local-outline-font-match-1'


def registered_faces(report):
    """Use the existing Windows registry/file inventory; no second catalogue."""
    return [dict(path=row['path'], sha256=row['hash'], face_index=face['index'])
            for row in report.get('files', []) for face in row.get('faces', [])]


@contextmanager
def exact_face(face):
    path = Path(face['path'])
    expected = face['sha256']
    if path.is_symlink() or file_digest(path) != expected:
        raise ValueError('Font source changed or is not a normal local file')
    data = face_bytes(path, face.get('face_index', 0))
    raw = QRawFont(QByteArray(data), 96., QFont.PreferNoHinting)
    if not raw.isValid():
        raise ValueError('Cannot parse selected font face')
    handle = QFontDatabase.addApplicationFontFromData(QByteArray(data))
    if handle < 0:
        raise ValueError('Cannot register selected local font face')
    try:
        yield raw
        if file_digest(path) != expected:
            raise ValueError('Font source changed during comparison')
    finally:
        QFontDatabase.removeApplicationFont(handle)


def shaped_outline(text, raw, tracking_em=0.):
    if (not isinstance(text, str) or not text.strip() or len(text)>512
            or any(ord(c)<32 or 0xD800<=ord(c)<=0xDFFF for c in text)):
        raise ValueError('Font matching needs bounded, nonempty single-line text')
    if any(not raw.supportsCharacter(ord(c)) for c in text if not c.isspace()):
        raise ValueError('FONT_MISSING_GLYPHS')
    font = QFontDatabase.font(raw.familyName(), raw.styleName(), 96)
    font.setPixelSize(96)
    font.setHintingPreference(QFont.PreferNoHinting)
    font.setStyleStrategy(QFont.NoFontMerging)
    font.setLetterSpacing(QFont.AbsoluteSpacing, tracking_em*96)
    layout = QTextLayout(text, font)
    layout.beginLayout()
    line = layout.createLine()
    if line.isValid():
        line.setLineWidth(1000000)
    layout.endLayout()
    if not line.isValid() or line.textLength()!=len(text.encode('utf-16-le'))//2:
        raise ValueError('Incomplete shaped text')
    path = QPainterPath()
    expected = face_fingerprint(raw)
    runs = layout.glyphRuns()
    if not runs:
        raise ValueError('No visible shaped glyphs')
    for run in runs:
        actual = run.rawFont()
        if face_fingerprint(actual) != expected:
            raise ValueError('Silent fallback or wrong font face rejected')
        for glyph, point in zip(run.glyphIndexes(), run.positions()):
            if not glyph:
                raise ValueError('FONT_MISSING_GLYPHS')
            path.addPath(actual.pathForGlyph(glyph).translated(point))
    if path.isEmpty() or path.boundingRect().height()<=0:
        raise ValueError('No visible outlines')
    return path


def render_outline(path, width, height):
    if type(width) is not int or type(height) is not int or min(width,height)<1 or width*height>2_000_000:
        raise ValueError('Font crop pixel budget exceeded')
    bounds = path.boundingRect()
    transform = QTransform()
    transform.scale(width/bounds.width(), height/bounds.height())
    transform.translate(-bounds.x(), -bounds.y())
    image = QImage(width+4, height+4, QImage.Format_RGB32)
    image.fill(0xFFFFFFFF)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(2,2)
        painter.fillPath(transform.map(path), QColor('black'))
    finally:
        painter.end()
    return image


def _ink(gray):
    mask = gray < 180
    ys, xs = np.where(mask)
    if len(xs)<8:
        raise ValueError('Crop has insufficient visible ink')
    return gray[ys.min():ys.max()+1, xs.min():xs.max()+1], dict(
        left=int(xs.min()), top=int(ys.min()), width=int(xs.max()-xs.min()+1), height=int(ys.max()-ys.min()+1))


def shape_error(reference, candidate):
    a, b = reference < 180, candidate < 180
    if a.shape != b.shape or not a.any() or not b.any():
        raise ValueError('Invalid outline comparison')
    chamfer = float((distance_transform_edt(~a)[b].mean()+distance_transform_edt(~b)[a].mean())/(2*max(1,a.shape[0])))
    union = np.count_nonzero(a|b)
    overlap = float(np.count_nonzero(a&b)/union)
    return dict(score=chamfer+.25*(1-overlap), symmetric_chamfer=chamfer, ink_iou=overlap)


def match_fonts(crop, text_candidates, faces, *, pixels_per_mm=None, max_faces=64, offset=0,
                tracking_options=(-.02, 0., .02, .04), scale_bounds=(.5,1.5),
                maximum_error=.18, minimum_margin=.015, cancelled=lambda:False):
    if type(max_faces) is not int or not 1<=max_faces<=256 or type(offset) is not int or offset<0:
        raise ValueError('Invalid font search page')
    if (not isinstance(text_candidates,list) or not 1<=len(text_candidates)<=4
            or not isinstance(faces,list) or len(faces)>10000):
        raise ValueError('Font/text candidate budget exceeded')
    if (not tracking_options or len(tracking_options)>16 or any(type(v) not in (int,float) or not math.isfinite(v) or not -.1<=v<=.2 for v in tracking_options)
            or len(scale_bounds)!=2 or not 0<scale_bounds[0]<=scale_bounds[1]<=4
            or not 0<=maximum_error<=1 or not 0<=minimum_margin<=1):
        raise ValueError('Invalid font match geometry/policy')
    if pixels_per_mm is not None and (type(pixels_per_mm) not in (int,float) or not math.isfinite(pixels_per_mm) or pixels_per_mm<=0):
        raise ValueError('Invalid source physical calibration')
    # Validate all text before attempting any face; never truncate OCR silently.
    for candidate in text_candidates:
        value=candidate.get('text')
        if not isinstance(value,str) or not value.strip() or len(value)>512 or any(ord(c)<32 for c in value):
            raise ValueError('Invalid text candidate')
        if candidate.get('origin') not in ('ORIGINAL_TEXT','OCR','REVIEWED_TEXT'):
            raise ValueError('Unknown text evidence origin')
    target, bounds = _ink(image_gray(crop))
    if target.size>2_000_000:
        raise ValueError('Font crop exceeds analysis pixel budget')
    report=dict(schema=VERSION, status='NO_MATCH', font_match_status='NO_MATCH', candidates=[], exclusions=[],
                checked_faces=0, omitted_faces=max(0,len(faces)-offset-max_faces), next_offset=offset,
                issues=[], physical_calibration='KNOWN' if pixels_per_mm else 'UNKNOWN',
                policy=dict(maximum_error=maximum_error,minimum_margin=minimum_margin,scale_bounds=list(scale_bounds)),
                identity='VISUAL_CANDIDATES_NOT_BINARY_SOURCE_IDENTITY_OR_LICENCE',
                crop_digest=hashlib.sha256(image_gray(crop).tobytes()).hexdigest())
    for index,face in enumerate(faces[offset:offset+max_faces],offset):
        if cancelled():
            report['omitted_faces']=len(faces)-index
            break
        report['checked_faces']+=1;report['next_offset']=index+1
        best=None
        try:
            with exact_face(face) as raw:
                for evidence in text_candidates:
                    for tracking in tracking_options:
                        path=shaped_outline(evidence['text'],raw,tracking)
                        rect=path.boundingRect();vertical=bounds['height']/rect.height()
                        horizontal=bounds['width']/(rect.width()*vertical)
                        if not scale_bounds[0]<=horizontal<=scale_bounds[1]:
                            continue
                        image=render_outline(path,bounds['width'],bounds['height'])
                        gray,_=_ink(image_gray(image));gray=np.ascontiguousarray(gray)
                        # Pixel quantization may alter the clipped edge by one pixel.
                        normalized=QImage(gray.data,gray.shape[1],gray.shape[0],gray.strides[0],QImage.Format_Grayscale8).copy()
                        fitted=image_gray(normalized.scaled(bounds['width'],bounds['height']))
                        error=shape_error(target,fitted)
                        value=dict(error,face=dict(face),family=raw.familyName(),style=raw.styleName(),
                            text=evidence['text'],text_origin=evidence['origin'],tracking_em=tracking,
                            horizontal_scale=horizontal,
                            size_pt=96*vertical/pixels_per_mm*72/25.4 if pixels_per_mm else None,
                            face_fingerprint=face_fingerprint(raw),
                            text_verified=evidence['origin'] in ('ORIGINAL_TEXT','REVIEWED_TEXT'))
                        if best is None or (value['score'],abs(tracking))<(best['score'],abs(best['tracking_em'])):
                            best=value
            if best is not None:
                report['candidates'].append(best)
        except (ValueError, OSError, KeyError, TypeError):
            report['exclusions'].append(dict(index=index,code='FONT_UNREADABLE_OR_UNSUPPORTED'))
    report['candidates'].sort(key=lambda row:(row['score'],row['face']['sha256'],row['face'].get('face_index',0),row['text']))
    choices=report['candidates']
    if choices and choices[0]['score']<=maximum_error:
        ambiguous=len(choices)>1 and choices[1]['score']-choices[0]['score']<minimum_margin
        report['status']='AMBIGUOUS' if ambiguous else 'CANDIDATE'
        if ambiguous:report['issues'].append(issue('FONT_AMBIGUOUS'))
        if not choices[0]['text_verified']:report['issues'].append(issue('OCR_REVIEW_REQUIRED'))
    else:
        report['issues'].append(issue('FONT_NO_MATCH'))
    if report['omitted_faces'] or report['exclusions']:
        report['issues'].append(issue('SEARCH_INCOMPLETE'))
        report['search_complete']=False
    else:
        report['search_complete']=True
    report['font_match_status']=report['status'] if report['search_complete'] else 'INCOMPLETE'
    report['candidates']=choices[:10]
    return report


def ocr_text_candidates(crop, record):
    """Reuse actual frozen local Tesseract; caller must review any OCR text."""
    from .quality_ocr import lines
    with tempfile.TemporaryDirectory(prefix='template-ai-local-ocr-') as directory:
        path=Path(directory)/'crop.png'
        if crop.isNull() or crop.width()*crop.height()>2_000_000 or not crop.save(str(path),'PNG'):
            raise ValueError('Invalid bounded OCR crop')
        rows=lines(dict(image=str(path),width_mm=float(crop.width()),height_mm=float(crop.height())),record)
        return [dict(text=row['text'],origin='OCR',word_confidences=row['word_confidences']) for row in rows]

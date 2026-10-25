"""Explicitly derived evidence from a hash-verified native export."""
from pathlib import Path
import xml.etree.ElementTree as ET
from .native_reader import digest,IsolationError

def pdf_source(source):
    from ..source_links import verify_source
    verify_source(source['current_path'],source['hash'])
    derivative=source['native_derivative'];path=Path(derivative['pdf'])
    if derivative['source_sha256']!=source['hash'] or digest(path)!=derivative['sha256']:
        raise IsolationError('Native derivative lineage changed')
    return dict(source,current_path=str(path),hash=derivative['sha256'],semantic_svg='',svg='')

def original_observation(source):
    from ..original_text_observation import original_text_observation
    from ..design_observation import canonical_digest
    result=original_text_observation(pdf_source(source))
    result.update(channel='ADOBE_DERIVED_PDF_NOT_ORIGINAL_AI_DECLARATIONS',
                  original_source_sha256=source['hash'],derivative_sha256=source['native_derivative']['sha256'],
                  native_illustrator_editability='UNKNOWN')
    for row in result['runs']:
        row['native_derivative']=dict(source_sha256=source['hash'],pdf_sha256=source['native_derivative']['sha256'])
        row['qualification']='DERIVED_EXPORT_REQUIRES_VISUAL_REVIEW'
        for key in ('source_pt','declared_pt'):
            if isinstance(row.get(key),dict):row[key]['basis']='ADOBE_EXPORTED_PDF_DECLARATION_NOT_ORIGINAL_AI'
    result['document_digest']=canonical_digest(result)
    return result

def pdf_texts(source):
    from ..source_region_hypotheses import original_pdf_texts
    rows,evidence=original_pdf_texts(pdf_source(source))
    evidence.update(state='ADOBE_DERIVED_PDF_GLYPH_CANDIDATES',original_source_sha256=source['hash'],
                    derivative_sha256=source['native_derivative']['sha256'])
    return rows,evidence

def vector_objects(source,assets):
    """Qt measures Adobe SVG shapes; text uses the PDF's embedded-font metrics."""
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtCore import QByteArray
    from ..model import Rect
    from ..source_links import verify_source
    from ..source_derivative import assign_query_ids
    from ..offline_runtime import assert_local_document
    verify_source(source['current_path'],source['hash'])
    path=Path(source['semantic_svg'])
    if path.stat().st_size>32_000_000 or digest(path)!=source['file_hashes']['semantic_svg']:
        raise IsolationError('SVG derivative changed or exceeds budget')
    assert_local_document(path,require_svg=True)
    root=ET.parse(path).getroot();elements=list(root.iter())
    if len(elements)>4000:raise ValueError('向量物件超過本次判讀預算')
    assign_query_ids(root)
    query=ET.fromstring(ET.tostring(root))
    # Avoid host font substitution and duplicate text: the PDF has embedded
    # font metrics. This does not remove text from the displayed PDF artwork.
    for parent in query.iter():
        for child in list(parent):
            if child.tag.rsplit('}',1)[-1]=='text':parent.remove(child)
    renderer=QSvgRenderer(QByteArray(ET.tostring(query)))
    if not renderer.isValid():raise ValueError('Adobe 向量輸出無法核對')
    view=renderer.viewBoxF()
    if view.width()<=0 or view.height()<=0:raise ValueError('Invalid native viewport')
    sx=source['width_mm']/view.width();sy=source['height_mm']/view.height();bounds={}
    for n in elements:
        key=n.get('id');tag=n.tag.rsplit('}',1)[-1]
        if not key or tag not in ('rect','path','g','image','polygon','polyline','ellipse','circle','line','use'):continue
        if renderer.elementExists(key):
            r=renderer.transformForElement(key).mapRect(renderer.boundsOnElement(key))
            if r.width()>0 and r.height()>0:
                bounds[key]=Rect((r.x()-view.x())*sx,(r.y()-view.y())*sy,r.width()*sx,r.height()*sy)
    verify_source(source['current_path'],source['hash'])
    if digest(path)!=source['file_hashes']['semantic_svg']:raise IsolationError('SVG changed during observation')
    return root,elements,bounds

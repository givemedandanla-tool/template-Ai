"""Owned PDF-compatible .ai import/glyph/font/fit workload, never user data."""
from pathlib import Path
import hashlib
from copy import deepcopy

from PySide6.QtCore import QMarginsF,QSizeF
from PySide6.QtGui import QFont,QFontDatabase,QPainter,QPageLayout,QPageSize,QPdfWriter

from .background import file_digest
from .importer import import_file
from .original_text_observation import original_text_observation
from .font_catalog import analyze_font
from .training_store import digest


def source_benchmark_item(library,plan,index):
    asset=plan['font_asset'];number=plan['items'][index]
    folder=library.root/'authored-ai-sources';folder.mkdir(exist_ok=True)
    path=folder/('owned-'+str(number)+'.ai')
    values=[('name','Synthetic '+format(number,'04d'),18.,8.,14.,70.,11.),
            ('email','case'+format(number,'04d')+'@example.test',10.,8.,40.,70.,7.)]
    if not path.exists():
        writer=QPdfWriter(str(path));writer.setResolution(72)
        writer.setPageSize(QPageSize(QSizeF(90,54),QPageSize.Millimeter));writer.setPageMargins(QMarginsF(0,0,0,0),QPageLayout.Millimeter)
        painter=QPainter(writer)
        try:
            for kind,value,pt,x,y,w,h in values:
                font=QFontDatabase.font(asset['families'][0],(asset.get('styles') or [''])[0],round(pt))
                font.setPointSizeF(pt);font.setStyleStrategy(QFont.NoFontMerging);painter.setFont(font)
                painter.drawText(round(x*72/25.4),round(y*72/25.4),value)
        finally:painter.end();del writer
    before=file_digest(path);source=import_file(path,library.assets);source.update(current_path=str(path),id='owned-'+str(number))
    observed=original_text_observation(source)
    runs=[row for row in observed['runs'] if row['source_locator']['kind']=='PDF_ORIGINAL_GLYPH_RUN']
    # Qt may write one text-show operator per glyph, without explicit spaces.
    # Validate the known authored fields against interpreted glyph sequences;
    # whitespace remains author-labelled data, not invented original text.
    from .original_pdf_glyphs import extract_pdf_glyphs
    private=extract_pdf_glyphs(source,path.read_bytes(),include_private_text=True)
    fields=[]
    for ordinal,(kind,value,pt,x,y,w,h) in enumerate(values):
        group=[r for r in private['runs'] if r['source_pt']['value'] is not None and abs(r['source_pt']['value']-pt)<.01]
        recovered=''.join(r['_private_text'] for r in group)
        if not group or ''.join(recovered.split())!=''.join(value.split()):
            raise ValueError('Actual original PDF glyphs/physical point size were not recovered')
        run=group[0]
        measured=analyze_font(dict(kind='ASSET',asset=asset),value,pt,100.,.05)
        if not measured.get('measurement_verified'):raise ValueError('Actual local font/glyph measurement failed')
        fields.append(dict(id=kind,kind=kind,owner='p1',index=0,rect=dict(x=x,y=y-h,w=w,h=h),
            measured_grapheme_count=len(value),source_typography=dict(font_asset_ref=deepcopy(asset),source_pt=run['source_pt'],
                horizontal_scale=run['horizontal_scale'],tracking=run['tracking'],word_spacing=run['word_spacing'],
                shaped_advance=dict(value=measured['advance_width_mm'],unit='mm',status='DERIVED',evidence_refs=[run['id']])),
            source_alignment='left',label_binding=dict(status='CONFIRMED',kind='NO_FIXED_LABEL',evidence_refs=['known authored source'])))
    if before!=file_digest(path):raise ValueError('Original synthetic AI changed')
    return dict(source_hash=before,source_name=path.name,original_glyph_runs=len(runs),
        example=dict(id='owned-'+str(number),role='TRAIN',lineage_group='controlled-unit-'+str(number),
            width_mm=source['width_mm'],height_mm=source['height_mm'],fields=fields),
        scope='ACTUAL_SMALL_OWNED_PDF_COMPATIBLE_AI_NOT_PRIVATE_ILLUSTRATOR_FORMAT_OR_FULL_FONT_SEARCH')


def summarize_source_benchmark(library,job,results):
    import time
    from .design_family import train_families
    from .design_profiles import learn_profiles
    examples=[row['example'] for row in results];started=time.perf_counter()
    families=train_families(examples);profiles=learn_profiles(families,examples)
    if not families['families']:raise ValueError('Actual parsed source workload did not fit a shared family')
    for row in results:
        path=library.root/'authored-ai-sources'/row['source_name']
        if file_digest(path)!=row['source_hash']:raise ValueError('Source prefix changed during benchmark')
    return dict(items=len(results),shared_families=len(families['families']),profiles=len(profiles['families']),
        shared_fit_seconds=time.perf_counter()-started,elapsed_item_seconds=job['elapsed_seconds'],
        actual_glyph_runs=sum(row['original_glyph_runs'] for row in results),source_bytes_unchanged=True,
        scope='ACTUAL_OWNED_PDF_COMPATIBLE_AI_GENERATION_IMPORT_ORIGINAL_GLYPHS_LOCAL_FONT_MEASUREMENT_AND_SHARED_FIT',
        excluded='Private Illustrator structure,full installed-font image search,real aesthetics,Windows and physical prepress',
        model_digest=digest([families,profiles]),production_qualification='NOT_GRANTED_SYNTHETIC_BENCHMARK')

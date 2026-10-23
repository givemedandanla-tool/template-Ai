"""Local observation adapter for the small review application.

Reuses the existing immutable importer, source-region hypotheses, semantic
recognition and original-text evidence.  This module produces observations,
never inferred template permissions or fabricated typography.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from typing import Callable

VERSION = 'review-observations-1'
MAX_PAGES = 100
MAX_FIELDS = 4000
# These are bounds for actual phases, not fake heartbeats.  Conversion can make
# several separately bounded Inkscape calls, so a blanket 120s parent timeout
# must not be reused by the new launcher.
STAGE_TIMEOUTS = {
    'validate': 90, 'import': 480, 'original_text': 120,
    'geometry': 120, 'ocr': 90, 'assemble': 60,
}


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def _issue(code: str, summary: str, *, page=None, detail=None) -> dict:
    row = dict(code=code, summary=summary, scope='LOCAL_SOURCE_REVIEW')
    if page is not None:
        row['page'] = page
    if detail:
        row['detail'] = detail
    return row


def _unknown(unit: str, reason='NO_SOURCE_EVIDENCE') -> dict:
    return dict(value=None, unit=unit, status='UNKNOWN', basis=reason,
                evidence_refs=[])


def _measured(value, ref, *, basis='SOURCE_GEOMETRY_NOT_CONTAINER'):
    return dict(value=value, unit='mm', status='DERIVED', basis=basis,
                evidence_refs=[ref])


def _valid_rect(value) -> bool:
    return (isinstance(value, dict) and all(
        isinstance(value.get(k), (int, float)) and not isinstance(value.get(k), bool)
        and math.isfinite(value[k]) for k in ('x', 'y', 'w', 'h'))
        and value['w'] > 0 and value['h'] > 0)


def _atomic_json(path: Path, value) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('本機觀察資料位置不能是符號連結')
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    handle, temporary = tempfile.mkstemp(prefix='.review-', suffix='.json', dir=path.parent)
    try:
        with os.fdopen(handle, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if Path(temporary).exists():
            Path(temporary).unlink()
    return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def _original_runs(document):
    """Index original node IDs as well as addressed PDF glyph runs."""
    result = {}
    for row in document.get('runs', []):
        result[row['id']] = row
        locator = row.get('source_locator') or {}
        if locator.get('kind') == 'INKSCAPE_DERIVED_TEXT':
            locator = locator.get('derivative_locator') or {}
        native = locator.get('object_id')
        if native:
            result.setdefault(native, row)
    return result


def _field_from_observation(observation, candidate, source, runs) -> dict | None:
    absolute = observation.get('region')
    if not _valid_rect(absolute):
        return None
    crop = candidate['crop']
    rect = dict(x=absolute['x']-crop['x'], y=absolute['y']-crop['y'],
                w=absolute['w'], h=absolute['h'])
    native_mapping = candidate.get('evidence', {}).get('slot_source_map', {}).get(
        observation.get('slot_id'), {})
    native = native_mapping.get('original_run_ref') or native_mapping.get('svg_object_id')
    original = runs.get(native)
    semantic = deepcopy(observation.get('semantic') or {})
    slot = next((s for s in candidate.get('slots', [])
                 if s.get('id') == observation.get('slot_id')), {})
    kind = str(semantic.get('semantic_type') or slot.get('kind') or semantic.get('slot_kind') or 'unknown').casefold()
    if observation.get('object_type') == 'LOGO_PART':
        kind = 'logo'
    fid = observation.get('slot_id') or observation.get('id') or ('field-'+_digest(
        [source['hash'], source['page'], absolute, observation.get('text')])[:24])
    ref = 'SOURCE_FIELD:'+_digest([source['hash'], source['page'], fid])
    measures = {f'{k}_mm': _measured(rect[k], ref) for k in ('x', 'y', 'w', 'h')}
    # Friendly aliases do not change the measurement coordinate system.
    measures['width_mm'] = deepcopy(measures['w_mm'])
    measures['height_mm'] = deepcopy(measures['h_mm'])
    measures.update(
        frame=dict(rect=deepcopy(rect), coordinate='WORK_LOCAL_MM', status='DERIVED',
                   basis='SOURCE_GEOMETRY_NOT_CONTAINER', evidence_refs=[ref]),
        ink_bounds=_unknown('mm', 'QUERY_BOUNDS_NOT_VERIFIED_GLYPH_INK'),
        container_bounds=_unknown('mm', 'SOURCE_CONTAINER_NOT_IDENTIFIED'),
        font_size_pt=deepcopy(original.get('source_pt') or _unknown('pt')) if original else _unknown('pt'),
        declared_font_size_pt=deepcopy(original.get('declared_pt') or _unknown('pt')) if original else _unknown('pt'),
        horizontal_scale=deepcopy(original.get('horizontal_scale') or _unknown('ratio')) if original else _unknown('ratio'),
        tracking=deepcopy(original.get('tracking') or _unknown('mm')) if original else _unknown('mm'),
        word_spacing=_unknown('mm'),
        baseline=_unknown('mm', 'DECLARED_ANCHOR_IS_NOT_VERIFIED_GLYPH_BASELINE'),
        distribution=dict(status='UNKNOWN', basis='NO_IDENTIFIABLE_DISTRIBUTION_STRATEGY',
                          units=[], extra_gaps=[]),
        alignment=dict(status='UNKNOWN', basis='RELATION_REQUIRES_REVIEW'))
    if original and original.get('baseline_anchor_mm'):
        measures['declared_anchor_mm'] = dict(
            value=deepcopy(original['baseline_anchor_mm']), unit='mm', status='DERIVED',
            basis=original.get('baseline_status'), evidence_refs=[original['id']])
    text = observation.get('text', '')
    prediction = dict(text=text, kind=kind, owner=slot.get('owner'), rect=deepcopy(rect),
                      source_rect=deepcopy(absolute), measurements=deepcopy(measures),
                      owner_status='UNCONFIRMED_LEGACY_CANDIDATE',
                      semantic=semantic, classification=observation.get('classification'))
    evidence = dict(ref=ref, source_hash=source['hash'], source_page=source['page'],
                    source_object=native_mapping, original_text=deepcopy(original),
                    source_scope='DERIVED_GEOMETRY_REQUIRES_VISUAL_REVIEW',
                    source_mapping=observation.get('prior_prediction', 'UNKNOWN'),
                    native_illustrator_mapping='UNKNOWN', measurement_coordinate='WORK_LOCAL_MM')
    return dict(id=fid, rect=rect, source_rect=deepcopy(absolute), text=text,
                kind=kind, owner=None, reviewed=False, review_state='UNCHECKED',
                prediction=prediction, evidence=evidence, measurements=measures)


def _ocr_capability() -> dict:
    from ..logo_ocr import capability
    try:
        cap = capability()
        # Installed executables usually know a system data directory.  Read its
        # reported location rather than copying models or downloading anything.
        if cap.get('available') and not cap.get('data_dir'):
            result = subprocess.run([cap['executable'], '--list-langs'], capture_output=True,
                                    text=True, timeout=10,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            match = re.search(r'"([^"]+)"', result.stdout.splitlines()[0] if result.stdout else '')
            if match and Path(match[1]).is_dir():
                cap['data_dir'] = match[1]
        return cap
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return dict(available=False, languages=[], reason='本機文字辨識工具尚未準備完成')


def _ocr_observations(source, cap) -> tuple[list, dict]:
    """Run actual local OCR, reusing the existing bounded TSV parser."""
    from ..quality_ocr import parse_tsv
    from ..background import file_digest
    from PySide6.QtGui import QImageReader
    languages = [x for x in ('chi_tra', 'eng') if x in cap.get('languages', [])]
    if not cap.get('available') or not languages:
        return [], dict(status='UNAVAILABLE', reason=cap.get('reason'))
    reader = QImageReader(source['image']);size = reader.size()
    if not size.isValid() or size.width()*size.height() > 12_000_000:
        raise ValueError('文字辨識預覽無效或超過像素預算')
    command = [cap['executable'], source['image'], 'stdout']
    if cap.get('data_dir'):
        command += ['--tessdata-dir', cap['data_dir']]
    # Bundled language-only directories do not contain Tesseract config files.
    # Explicit variables work offline with just the pinned language models.
    command += ['-l', '+'.join(languages), '--psm', '11',
                '-c', 'tessedit_create_tsv=1', '-c', 'tessedit_create_txt=0']
    env = os.environ.copy();env['OMP_THREAD_LIMIT'] = '1'
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=output, stderr=errors, env=env,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        start=time.monotonic()
        try:
            while process.poll() is None:
                if (time.monotonic()-start>35 or os.fstat(output.fileno()).st_size>1_048_576
                        or os.fstat(errors.fileno()).st_size>65_536):
                    raise ValueError('文字辨識超過本階段時間或輸出預算，已停止並保留原稿')
                try:process.wait(timeout=.1)
                except subprocess.TimeoutExpired:pass
        finally:
            if process.poll() is None:
                from ..runtime_worker import stop_tree
                stop_tree(process)
            process.wait()
        if process.returncode or os.fstat(output.fileno()).st_size > 1_048_576:
            raise ValueError('本機文字辨識失敗或超出輸出預算')
        output.seek(0);raw = output.read(1_048_577).decode('utf-8', 'strict')
    lines = parse_tsv(raw, size.width(), size.height(), source['width_mm'], source['height_mm'])
    models = []
    for lang in languages:
        file = Path(cap['data_dir'])/(lang+'.traineddata') if cap.get('data_dir') else None
        models.append(dict(language=lang, sha256=file_digest(file) if file and file.is_file() else None))
    proof = dict(status='OCR_CANDIDATE_NOT_SOURCE_TEXT', languages=languages, models=models,
                 executable_sha256=file_digest(cap['executable']), psm=11,
                 calibration='OCR_SCORES_ARE_NOT_PROBABILITY_OF_CORRECT_IDENTITY')
    return lines, proof


def _ocr_fallback(source, cap) -> tuple[list, dict]:
    from ..semantic_fields import recognize
    lines, proof = _ocr_observations(source, cap)
    observations = []
    for row in lines:
        semantic = recognize(row['text'])
        key = 'ocr-'+_digest([source['hash'], source['page'], row['key'], row['rect']])[:24]
        observations.append(dict(id=key, slot_id=key, text=row['text'], region=row['rect'],
                                 object_type='TEXT', classification='OCR_CANDIDATE',
                                 prior_prediction='LOCAL_OCR_NOT_ORIGINAL_TEXT', semantic=semantic))
    candidate = dict(key='ocr-page', crop=dict(x=0., y=0., w=source['width_mm'], h=source['height_mm']),
                     observations=observations, slots=[], evidence={'ocr': proof})
    return ([candidate] if observations else []), proof


def _geometry_relations(fields, *, calibrated):
    """Measured neighbour relationships, not learned alignment permissions."""
    lookup={field['id']:field for field in fields};pairs=set()
    def center(field):
        r=field['rect'];return r['x']+r['w']/2,r['y']+r['h']/2
    for field in fields:
        x,y=center(field)
        near=sorted((math.hypot(center(other)[0]-x,center(other)[1]-y),other['id'])
                    for other in fields if other['id']!=field['id'])[:3]
        for _,other in near:pairs.add(tuple(sorted((field['id'],other))))
    result=[]
    for first,second in sorted(pairs):
        a=lookup[first]['rect'];b=lookup[second]['rect']
        rid='geometry-'+_digest([first,second])[:24]
        values=dict(dx_mm=(b['x']+b['w']/2)-(a['x']+a['w']/2),
                    dy_mm=(b['y']+b['h']/2)-(a['y']+a['h']/2),
                    left_residual_mm=b['x']-a['x'],
                    right_residual_mm=b['x']+b['w']-a['x']-a['w'],
                    center_residual_mm=(b['x']+b['w']/2)-(a['x']+a['w']/2),
                    horizontal_gap_mm=b['x']-(a['x']+a['w']),
                    vertical_gap_mm=b['y']-(a['y']+a['h']))
        result.append(dict(id=rid,kind='relative_position',status='DERIVED',
            field_ids=[first,second],source=first,target=second,
            measurements={key:(_measured(value,rid,basis='SIGNED_TARGET_MINUS_SOURCE_WORK_LOCAL_GEOMETRY')
                               if calibrated else _unknown('mm','PHYSICAL_SCALE_NOT_VERIFIED'))
                          for key,value in values.items()},
            evidence=dict(basis='THREE_NEAREST_FIELDS_MEASURED_NOT_ALIGNMENT_PERMISSION',
                          coordinate='WORK_LOCAL_MM',source_refs=[lookup[first]['evidence']['ref'],lookup[second]['evidence']['ref']]),
            policy_status='NOT_EVALUATED',alignment_status='UNKNOWN'))
    return result


def analyse_file(path, cache_dir, progress_callback: Callable | None = None, ocr=True) -> dict:
    """Return a JSON-compatible, local-only review observation packet.

    Requires a QApplication (the worker creates one). Progress callback receives
    only real phase transitions, with explicit phase budgets. Source text and
    font evidence are local private data, never a safe support-report payload.
    """
    from ..offline_runtime import assert_local_document, assert_local_path
    from ..background import file_digest
    from ..importer import import_file
    from ..source_analysis import analyse_source
    from ..original_text_observation import original_text_observation
    path = Path(path).resolve();cache_dir = Path(cache_dir).resolve()
    assert_local_document(path);assert_local_path(cache_dir)
    if not path.is_file() or path.stat().st_size > 200_000_000:
        raise ValueError('檔案不存在或超過本版單檔200MB支援範圍')
    cache_dir.mkdir(parents=True, exist_ok=True)
    def progress(stage, message, page=1, total_pages=None, **metadata):
        if progress_callback:
            progress_callback(dict(stage=stage, message=message, page=page,
                                   total_pages=total_pages, phase_timeout=STAGE_TIMEOUTS[stage], **metadata))
    progress('validate', '正在檢查原稿與本機資料位置')
    sha = file_digest(path);sid='source-'+_digest([str(path), sha])[:24]
    packet = dict(schema_version=1, analysis_version=VERSION,
                  source=dict(id=sid, path=str(path), hash=sha, page_count=None, lineage=sha),
                  pages=[], works=[], issues=[], status='ANALYSED', relations=[],
                  capabilities=dict(local_only=True, native_illustrator_mapping='UNKNOWN',
                                    ocr_requested=bool(ocr), ocr_executed=False,
                                    inkscape_conversion_executed=False, vector_analysis_executed=False))
    cap = None
    page_count = 1
    page_number = 1
    fields_count = 0
    while page_number <= min(page_count, MAX_PAGES):
        progress('import', f'正在準備第 {page_number} 頁原稿預覽', page_number, page_count)
        try:
            imported = import_file(path, cache_dir/'assets', page=page_number)
        except Exception as error:
            if not packet['pages']:
                raise
            packet['issues'].append(_issue('PAGE_IMPORT_FAILED', '這一頁未能讀取；已完成頁面仍保留',
                                                  page=page_number, detail=type(error).__name__))
            packet['status']='PARTIAL';page_number+=1;continue
        page_count = imported['page_count'];packet['source']['page_count'] = page_count
        source = dict(imported, id=sid, current_path=str(path))
        page_id=f'{sid}-p{page_number}'
        page = dict(id=page_id, page=page_number, image=source['image'],
                    width_mm=source['width_mm'], height_mm=source['height_mm'],
                    calibrated=source.get('calibrated', False),
                    source_hash=sha, image_hash=source['file_hashes']['image'],
                    engine=source['engine'], recovery=deepcopy(source.get('recovery', {})),
                    renderer_identity=deepcopy(source.get('renderer_identity')),
                    renderer_execution=source.get('renderer_execution', 'NOT_USED'))
        packet['pages'].append(page)
        identity=source.get('renderer_identity') or {}
        safe_identity={k:identity[k] for k in (
            'state','origin','policy','version','executable_sha256','verified_files') if k in identity}
        safe_identity['origin']='BUNDLED' if identity.get('policy')=='BUNDLED_ONLY' else 'EXTERNAL' if identity.get('policy')=='SOURCE_EXTERNAL' else 'NONE'
        if identity.get('runtime_manifest_sha256'):
            safe_identity['manifest_sha256']=identity['runtime_manifest_sha256']
        packet['capabilities']['inkscape_runtime']=safe_identity
        if source.get('renderer_execution')=='SELECTED_INKSCAPE_CONVERSION_SUCCEEDED':
            packet['capabilities']['inkscape_conversion_executed']=True
        if not source.get('calibrated',False):
            packet['issues'].append(_issue('PHYSICAL_SIZE_UNCALIBRATED',
                '這一頁只有預覽比例，實體尺寸尚未確認；請勿將畫面大小當成印刷尺寸',page=page_number))
        progress('original_text', '正在保存來源文字與字型依據', page_number, page_count)
        document = original_text_observation(source)
        folder=cache_dir/'observations'/sha/f'page-{page_number}'
        page['original_evidence'] = _atomic_json(folder/'original-text.json', document)
        page['original_evidence']['state']=document.get('state')
        runs = _original_runs(document)
        progress('geometry', '正在尋找作品範圍、文字及圖形', page_number, page_count)
        candidates=[]
        try:
            candidates=analyse_source(source, cache_dir/'analysis')
            packet['capabilities']['vector_analysis_executed']=True
        except Exception as error:
            packet['issues'].append(_issue('VECTOR_ANALYSIS_UNAVAILABLE',
                '這一頁的物件結構尚未完整讀取，可核對原稿並補上標記',
                page=page_number, detail=type(error).__name__))
        vector_text = any(o.get('object_type')=='TEXT' for c in candidates for o in c.get('observations', []))
        if ocr and not vector_text:
            progress('ocr', '正在檢查本機文字辨識配套', page_number, page_count)
            if cap is None:
                cap=_ocr_capability()
                packet['capabilities']['ocr_available']=cap.get('available', False)
                packet['capabilities']['ocr_languages']=cap.get('languages', [])
            if cap.get('available'):
                progress('ocr', '正在以本機文字辨識補充候選', page_number, page_count)
                try:
                    packet['capabilities']['ocr_executed']=True
                    ocr_candidates, ocr_proof = _ocr_fallback(source, cap)
                    page['ocr_evidence']=ocr_proof
                    if ocr_candidates:
                        # OCR lines are currently page-scoped. Preserve the
                        # vector segmentation as source evidence rather than
                        # silently reassigning lines to potentially wrong cards.
                        page['vector_region_candidates_before_ocr']=_atomic_json(folder/'vector-before-ocr.json', candidates)
                        candidates=ocr_candidates
                except Exception as error:
                    packet['issues'].append(_issue('OCR_FAILED', '文字辨識未完成，可直接在原稿補上文字標記',
                                                          page=page_number, detail=type(error).__name__))
            else:
                packet['issues'].append(_issue('OCR_UNAVAILABLE',
                    '尚無可用的本機文字辨識配套；仍可查看原稿並人工補上文字標記', page=page_number))
        if not candidates:
            candidates=[dict(key='manual-page', crop=dict(x=0., y=0., w=source['width_mm'], h=source['height_mm']),
                             observations=[], slots=[], evidence=dict(state='MANUAL_RANGE_REVIEW_REQUIRED'))]
        page['analysis_evidence'] = _atomic_json(folder/'source-candidates.json', candidates)
        progress('assemble', '正在整理並保存可核對的結果', page_number, page_count)
        for index,candidate in enumerate(candidates):
            crop=candidate['crop']
            if not _valid_rect(crop):
                packet['issues'].append(_issue('INVALID_WORK_RANGE', '作品範圍需人工重新框選',page=page_number));continue
            fields=[]
            for obs in candidate.get('observations', []):
                field=_field_from_observation(obs, candidate, source, runs)
                if field:
                    if fields_count>=MAX_FIELDS:
                        packet['issues'].append(_issue('FIELD_BUDGET_REACHED',
                            '本次欄位數已達處理預算，未處理內容需分批核對', page=page_number));break
                    fields.append(field);fields_count+=1
            wid='work-'+_digest([sid, page_number, candidate['key']])[:24]
            issues = []
            if not fields:
                issues.append(_issue('NO_FIELD_OBSERVATIONS', '尚未取得欄位標記，請查看原稿並補上漏判內容',page=page_number))
            issues.append(_issue('WORK_RANGE_UNCONFIRMED', '作品範圍與歸屬仍需人工核對',page=page_number))
            work= dict(id=wid, name=f'作品 {index+1}', page_id=page_id,
                page=page_number, crop=deepcopy(crop), rect=deepcopy(crop), image=source['image'],
                width_mm=source['width_mm'], height_mm=source['height_mm'],
                fields=fields, relations=[], issues=issues, reviewed=False,
                source_hash=sha, evidence=dict(source_observation=deepcopy(page['analysis_evidence']),
                original_text_observation=deepcopy(page['original_evidence']),
                region=candidate.get('evidence', {}), native_illustrator_mapping='UNKNOWN'),
                measurements=dict(width_mm=_measured(crop['w'],wid),height_mm=_measured(crop['h'],wid)))
            if not source.get('calibrated',False):
                work['measurements']={k:_unknown('mm','PHYSICAL_SCALE_NOT_VERIFIED') for k in ('width_mm','height_mm')}
                for field in fields:
                    for key in ('x_mm','y_mm','w_mm','h_mm','width_mm','height_mm'):
                        field['measurements'][key]=_unknown('mm','PHYSICAL_SCALE_NOT_VERIFIED')
                    field['measurements']['frame']['coordinate']='UNVERIFIED_PREVIEW_MM'
                    field['evidence']['physical_scale']='UNKNOWN'
            work['geometry_relations']=_geometry_relations(fields,calibrated=source.get('calibrated',False))
            work['geometry_relation_coverage']=dict(mode='THREE_NEAREST_PER_FIELD',
                all_pairs=False,version=1,does_not_grant_alignment_or_swap_permission=True)
            packet['works'].append(work)
        packet['source']['analysis_complete_pages']=len(packet['pages'])
        packet['source']['analysis_complete_fields']=fields_count
        checkpoint=_atomic_json(cache_dir/'observations'/sha/'review-packet.partial.json',
                                dict(packet,status='PARTIAL',analysis_in_progress=True))
        progress('assemble','這一頁的判讀結果已保存',page_number,page_count,
                 checkpoint_path=checkpoint['path'],checkpoint_sha256=checkpoint['sha256'])
        page_number+=1
    if page_count>MAX_PAGES:
        packet['issues'].append(_issue('PAGE_BUDGET_REACHED',
            f'來源共有 {page_count} 頁，本輪只處理前 {MAX_PAGES} 頁，其餘尚未判讀'))
    if file_digest(path)!=sha:
        raise ValueError('分析期間原稿內容已改變，請重新加入並保留先前人工記錄')
    if packet['issues']:
        packet['status']='PARTIAL'
    packet['capabilities'].setdefault('ocr_available', None)
    packet['capabilities']['unknowns_are_not_zero']=True
    packet['private_data']=True
    packet['source']['analysis_complete_pages']=len(packet['pages'])
    packet['source']['analysis_complete_fields']=fields_count
    _atomic_json(cache_dir/'observations'/sha/'review-packet.json',packet)
    return packet

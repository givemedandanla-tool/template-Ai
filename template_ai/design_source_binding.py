"""Explicit expert source/field/font correspondence, never customer fine tuning.

Complete original runs can be explicitly bound as a reviewed composite field.
Every character and source run must have unambiguous ownership and coverage.
"""
from copy import deepcopy
import hashlib
import math

from .training_store import TrainingStore, digest, text
from .design_observation import ObservedScalar, unknown, canonical_digest, effective_point_size
from .fonts import font_errors


class SourceTypographyReview:
    def __init__(self,library):
        self.library=library
        self.store=TrainingStore.bind(library) if library.db.in_transaction else TrainingStore(library)

    def plan(self,work_id,slot_id,source_run_id,font_asset,review):
        return self._plan_run(work_id,slot_id,source_run_id,font_asset,review)

    def _plan_run(self,work_id,slot_id,source_run_id,font_asset,review,span=None):
        if not isinstance(review,dict) or review.get('source_identity_confirmed') is not True:
            raise ValueError('Explicit expert source/font identity review is required;names do not prove identity')
        text(review.get('basis'),'Source correspondence evidence',2048)
        if not isinstance(font_asset,dict) or not font_asset.get('families'):
            raise ValueError('A real verified local font asset is required')
        errors=font_errors(font_asset,font_asset['families'][0])
        if errors:raise ValueError('；'.join(errors))
        work=self.library.artwork(work_id);pins=self.store.pins(work_id)
        source=self.library.source(work['source_id'])
        if self.store.facts_state(work_id)!='CONFIRMED':raise ValueError('Field/source facts need confirmation first')
        slot=next((slot for slot in work['payload']['slots'] if slot['id']==slot_id),None)
        facts=self.store.facts(work_id);selected=set(facts['confirmation']['observation_ids'])
        matches=[row for row in facts['observations'] if row['id'] in selected and row.get('slot_id')==slot_id
                 and row['classification']=='FIELD' and row['object_type']=='TEXT']
        if not slot or len(matches)!=1:raise ValueError('Need an unambiguous confirmed field')
        observation=self.store._design_observation_document(work_id);original=observation['original_text_evidence']
        run=next((row for row in original['runs'] if row['id']==source_run_id),None)
        field_text=matches[0]['text']
        if span is not None:
            start,end=span
            if type(start) is not int or type(end) is not int or not 0<=start<end<=len(field_text):
                raise ValueError('Composite span range is invalid')
            field_text=field_text[start:end]
        if not run or run['text_sha256']!=hashlib.sha256(field_text.encode()).hexdigest():
            raise ValueError('Complete original text run does not match this reviewed field;composite spans remain unknown')
        if run.get('source_locator',{}).get('kind')=='PDF_TEXT_VISITOR':
            raise ValueError('Visitor context is not a visible glyph correspondence;select interpreted original glyph evidence')
        if run.get('baseline_orientation','HORIZONTAL_FORWARD')!='HORIZONTAL_FORWARD':
            raise ValueError('Rotated or unknown source text orientation needs supported output shaping')
        if run.get('visibility') in ('NONPAINTING_TEXT','HIDDEN','UNKNOWN') or run.get('unicode_status','MAPPED')!='MAPPED':
            raise ValueError('Hidden or unmapped source glyphs cannot establish a visible field')
        if run.get('writing_mode','HORIZONTAL')!='HORIZONTAL':
            raise ValueError('Vertical source text needs a supported shaping path')
        if run.get('source_locator',{}).get('kind')=='PDF_ORIGINAL_GLYPH_RUN':
            page=original.get('pdf_glyph_evidence',{})
            if page.get('source_canvas_mapping')!='VERIFIED_PHYSICAL_VIEWPORT':
                raise ValueError('Original PDF glyph viewport does not match the confirmed source')
        alignment=review.get('source_alignment','UNKNOWN')
        if alignment not in ('UNKNOWN','left','center','right','distributed'):
            raise ValueError('Unsupported reviewed source alignment')
        if alignment=='distributed':
            permission=review.get('source_distribution',{})
            if (slot['kind'] not in ('title','address') or permission.get('approved') is not True
                    or not permission.get('actor') or not permission.get('reason')):
                raise ValueError('Distributed source style needs explicit semantic permission and source evidence')
        label=review.get('label_binding')
        if label is not None:
            if not isinstance(label,dict) or label.get('status')!='CONFIRMED' or not label.get('evidence_refs'):
                raise ValueError('Source label mapping needs reviewed evidence')
            if label.get('kind') not in ('NO_FIXED_LABEL','DYNAMIC_PREFIX','SEPARATE_STATIC_LABEL'):
                raise ValueError('Unsupported source label mapping')
            if label['kind']=='DYNAMIC_PREFIX' and (not isinstance(label.get('prefix'),str)
                    or not label['prefix'] or not matches[0]['text'].startswith(label['prefix'])):
                raise ValueError('Fixed source prefix must actually occur in the reviewed original field')
        point=run['source_pt']['value']
        if point is None:
            point=review.get('physical_source_pt')
            if point is not None and not review.get('physical_measurement_refs'):
                raise ValueError('Unknown physical source pt needs external measured-source evidence')
        elif review.get('physical_source_pt') is not None and not math.isclose(point,review['physical_source_pt'],rel_tol=1e-7):
            raise ValueError('Review contradicts known original physical source pt')
        if point is not None and (type(point) not in (int,float) or not math.isfinite(point) or not 0<point<10000):
            raise ValueError('Source pt must be a finite measured positive value')
        crop=work['payload']['crop']
        sx=work['payload']['work_width']/crop['w'];sy=work['payload']['work_height']/crop['h']
        refs=(source_run_id,'EXPERT_SOURCE_REVIEW:'+digest(review))
        source_point=(ObservedScalar(point,'pt','OBSERVED','ORIGINAL_RUN_OR_MEASURED_SOURCE_PAGE_PT',refs)
            if point is not None else ObservedScalar(None,'pt','UNKNOWN','ORIGINAL_SOURCE_PAGE_PT_UNKNOWN',refs))
        work_point=effective_point_size(source_point,[sx,0,0,sy,-crop['x']*sx,-crop['y']*sy])
        uniform=math.isclose(sx,sy,rel_tol=1e-9)
        measured_work=review.get('physical_work_pt')
        if measured_work is not None:
            if (type(measured_work) not in (int,float) or not math.isfinite(measured_work)
                    or not 0<measured_work<10000 or not review.get('physical_work_measurement_refs')):
                raise ValueError('Measured work pt requires finite value and work-space measurement evidence')
            if work_point.value is not None and not math.isclose(work_point.value,measured_work,rel_tol=1e-7):
                raise ValueError('Measured work pt contradicts the uniform source transform')
            work_point=ObservedScalar(measured_work,'pt','OBSERVED','EXPERT_MEASURED_WORK_PT',
                tuple(review['physical_work_measurement_refs'])+refs)
        if work_point.value is None:
            reason='Anisotropic work transform' if not uniform else 'Unknown source physical pt'
            raise ValueError(reason+' has unknown scalar pt;explicit measured work pt is required')
        point=work_point.value
        key=digest([work_id,slot_id]);before=self.store.get('DESIGN_SOURCE_BINDING',key)
        typography=dict(font_asset_ref=deepcopy(font_asset),source_font_status='HUMAN_CONFIRMED_SOURCE_ASSOCIATION',
            source_pt=work_point.to_dict(),source_page_pt=source_point.to_dict(),
            source_to_work=dict(scale_x=sx,scale_y=sy,crop=deepcopy(crop),unit='mm'),
            horizontal_scale=unknown('ratio'),tracking=unknown('mm'),word_spacing=unknown('mm'),shaped_advance=unknown('mm'),
            glyph_runs=dict(status='UNKNOWN',basis='ORIGINAL_GLYPH_POSITIONS_NOT_RECOVERED'))
        if run.get('glyphs') or run.get('glyph_evidence'):
            typography['glyph_runs']=dict(status='OBSERVED_SOURCE_GLYPH_PLACEMENT',source_run_ref=source_run_id,
                glyph_digest=run['glyph_evidence']['digest'] if run.get('glyph_evidence') else canonical_digest(run['glyphs']),
                bounds_basis=run.get('bounds_basis'),font_correspondence='HUMAN_CONFIRMED_NOT_BINARY_IDENTITY_PROOF')
        for name,unit in [('horizontal_scale','ratio'),('tracking','mm'),('word_spacing','mm')]:
            original_parameter=run.get(name,{})
            if (uniform and original_parameter.get('status') in ('OBSERVED','DERIVED')
                    and original_parameter.get('value') is not None):
                value=original_parameter['value']*(sx if name!='horizontal_scale' else 1.)
                typography[name]=ObservedScalar(value,unit,'DERIVED','SOURCE_PARAMETER_IN_WORK_PHYSICAL_SPACE',refs).to_dict()
            work_measurement='work_'+name in review
            measured=review.get('work_'+name) if work_measurement else review.get(name) if uniform else None
            if measured is not None:
                if not review.get('parameter_measurement_refs'):
                    raise ValueError('Extra source parameters need explicit measured evidence')
                if type(measured) not in (int,float) or not math.isfinite(measured):
                    raise ValueError('Invalid measured source parameter')
                if (name=='horizontal_scale' and not 0<measured<=10) or (name!='horizontal_scale' and not -100<measured<100):
                    raise ValueError('Source parameter processing range exceeded')
                if uniform and not work_measurement and name!='horizontal_scale':measured*=sx
                known=typography[name].get('value')
                if known is not None and not math.isclose(known,measured,rel_tol=1e-7,abs_tol=1e-9):
                    raise ValueError('Review contradicts known original source parameter')
                typography[name]=ObservedScalar(measured,unit,'OBSERVED','EXPERT_MEASURED_SOURCE_PARAMETER',refs).to_dict()
        spacing=(review.get('source_text_flow') or {}).get('spacing_rule',{})
        name={'WORDS':'word_spacing','CHARACTERS':'tracking'}.get(spacing.get('mode'))
        if name and typography[name].get('value') is not None:
            supplied=spacing.get('value_mm')
            if (type(supplied) not in (int,float) or not math.isfinite(supplied) or not math.isclose(
                    typography[name]['value'],supplied,rel_tol=1e-7,abs_tol=1e-9)):
                raise ValueError('Reviewed flow spacing contradicts measured original parameter in work coordinates')
        anchor=run.get('baseline_anchor_mm')
        if isinstance(anchor,dict) and all(type(anchor.get(k)) in (int,float) for k in ('x','y')):
            typography['source_anchor_work_mm']=dict(x=(anchor['x']-crop['x'])*sx,
                y=(anchor['y']-crop['y'])*sy,status=run.get('baseline_status','UNKNOWN'),evidence_refs=list(refs))
            if run.get('baseline_status')=='ORIGINAL_PDF_TEXT_ORIGIN_PLUS_RISE':
                typography['baseline']=ObservedScalar((anchor['y']-crop['y'])*sy,'mm','DERIVED',
                    'ORIGINAL_PDF_BASELINE_IN_WORK_PHYSICAL_SPACE',refs).to_dict()
        # Natural demand at the reviewed source font/pt is derived from Qt;
        # it is not claimed to recover original source kerning/glyph positions.
        if 1<=point<=200:
            from .font_catalog import analyze_font
            measurement=analyze_font(dict(kind='ASSET',asset=font_asset),field_text,point,2000,.05,
                                     (font_asset.get('styles') or [None])[0])
            if measurement.get('measurement_verified'):
                typography['shaped_advance']=ObservedScalar(measurement['advance_width_mm'],'mm','DERIVED',
                    'QT_NATURAL_ADVANCE_AT_REVIEWED_SOURCE_FONT_NOT_ORIGINAL_GLYPH_SPACING',refs).to_dict()
        presentation=(review.get('source_text_flow') or {}).get('presentation')
        if presentation:
            from .design_components import validate_presentation
            validate_presentation(presentation)
            for part in presentation['components']:
                if part['kind']=='STATIC_TEXT':
                    reference=next((row for row in original['runs'] if row['id']==part.get('source_run_id')),None)
                    if (not reference or reference['text_sha256']!=hashlib.sha256(part['text'].encode()).hexdigest()
                            or reference.get('visibility') in ('HIDDEN','NONPAINTING_TEXT','UNKNOWN')):
                        raise ValueError('Static label needs an exact visible original source run')
                    asset=part['font_asset'];errors=font_errors(asset,(asset.get('families') or [''])[0])
                    if errors:raise ValueError('Static label font is unavailable or changed')
                    source_pt=reference['source_pt'].get('value')
                    measured=part.get('physical_work_pt')
                    expected_pt=source_pt*sx if source_pt is not None and uniform else None
                    if expected_pt is None:
                        if not part.get('physical_pt_measurement_refs'):raise ValueError('Static label point size needs independent measurement')
                        expected_pt=measured
                    if type(expected_pt) not in (int,float) or not math.isclose(expected_pt,point*part['pt_ratio'],rel_tol=1e-6):
                        raise ValueError('Static label point ratio contradicts source/work evidence')
                elif part['asset'].get('source_hash')!=source['hash'] or part['asset'].get('reviewed_source_association') is not True:
                    raise ValueError('Static icon needs explicitly reviewed association with this source')
        if label and label.get('kind')=='SEPARATE_STATIC_LABEL' and not presentation:
            raise ValueError('Separate labels need source-reviewed component geometry')
        plan=dict(id=key,work_id=work_id,slot_id=slot_id,pins=pins,facts_revision=facts['revision'],
            original_evidence_digest=original['document_digest'],source_run_id=source_run_id,
            expected_revision=before['revision'] if before else 0,font_asset=deepcopy(font_asset),
            review=deepcopy(review),typography=typography)
        plan['digest']=digest(plan);return plan

    def plan_composite(self,work_id,slot_id,spans,review):
        from .design_rich_text import resolve_segments
        if not isinstance(spans,list) or not 2<=len(spans)<=32:
            raise ValueError('Composite fields need two to thirty-two explicit source runs')
        if self.store.facts_state(work_id)!='CONFIRMED':raise ValueError('Composite field facts need confirmation first')
        facts=self.store.facts(work_id)
        selected=set(facts['confirmation']['observation_ids'])
        fields=[row for row in facts['observations'] if row['id'] in selected and row.get('slot_id')==slot_id
                and row['classification']=='FIELD' and row['object_type']=='TEXT']
        if len(fields)!=1:raise ValueError('Composite field correspondence is ambiguous')
        value=fields[0]['text'];cursor=0;parts=[];segments=[];seen=set()
        for span in spans:
            start,end=span.get('start'),span.get('end');run_id=span.get('source_run_id')
            if start!=cursor or type(end) is not int or end<=start or end>len(value) or run_id in seen:
                raise ValueError('Composite source ranges must be unique and cover every character in order')
            seen.add(run_id);cursor=end
            child_review={k:deepcopy(v) for k,v in review.items() if k!='source_text_flow'}
            child_review.update(span.get('review',{}))
            part=self._plan_run(work_id,slot_id,run_id,span['font_asset'],child_review,(start,end))
            parts.append(part)
            point=part['typography']['source_pt']['value'];base=parts[0]['typography']['source_pt']['value']
            tracking=part['typography']['tracking'].get('value')
            horizontal=part['typography']['horizontal_scale'].get('value')
            base_horizontal=parts[0]['typography']['horizontal_scale'].get('value')
            if tracking is None or horizontal is None or base_horizontal is None:
                raise ValueError('Composite source run needs evidenced tracking and horizontal scale')
            segments.append(dict(selector=deepcopy(span.get('selector',dict(kind='EXACT_SOURCE_RANGE',start=start,end=end))),
                font_asset=deepcopy(span['font_asset']),pt_ratio=point/base,tracking_mm=tracking,
                horizontal_scale_ratio=horizontal/base_horizontal,source_run_ref=run_id,
                evidence_refs=[run_id,'EXPERT_COMPOSITE_REVIEW:'+digest(review)]))
        if cursor!=len(value):raise ValueError('Composite source does not cover the full field text')
        rich=dict(status='HUMAN_CONFIRMED_SOURCE_RULE',evidence_refs=[p['source_run_id'] for p in parts],
            source_text_sha256=hashlib.sha256(value.encode()).hexdigest(),segments=segments)
        resolved=resolve_segments(value,rich)
        if [(p['start'],p['end']) for p in resolved]!=[(s['start'],s['end']) for s in spans]:
            raise ValueError('Reviewed selectors do not match original source spans')
        plan=deepcopy(parts[0]);plan.pop('digest',None);plan['source_run_id']=None
        plan.update(source_run_ids=[p['source_run_id'] for p in parts],spans=deepcopy(spans),review=deepcopy(review),composite_review=deepcopy(review))
        flow=deepcopy(review.get('source_text_flow') or dict(status='HUMAN_CONFIRMED_SOURCE_RULE',
            break_rule='NO_WRAP',max_lines_observed=1,line_height_factor=1.,alignment='left',evidence_refs=rich['evidence_refs']))
        flow['rich_text']=rich;plan['review']['source_text_flow']=flow
        plan['typography']['rich_text']=rich
        plan['typography']['source_components']=[dict(source_run_ref=p['source_run_id'],typography=deepcopy(p['typography'])) for p in parts]
        # Measure the complete, mixed-face text through the same output path.
        from .design_text_flow import shape_flow
        work=self.library.artwork(work_id);slot=next(s for s in work['payload']['slots'] if s['id']==slot_id)
        primary=plan['typography'];asset=plan['font_asset']
        measured=shape_flow(value,asset['families'][0],primary['source_pt']['value'],
            primary['horizontal_scale']['value'],2000,asset,(asset.get('styles') or [''])[0],
            primary['tracking']['value'],flow,slot['kind'])
        primary['shaped_advance']=ObservedScalar(measured['natural_advance_mm'],'mm','DERIVED',
            'QT_COMPLETE_REVIEWED_COMPOSITE_NATURAL_ADVANCE',tuple(rich['evidence_refs'])).to_dict()
        plan['digest']=digest(plan);return plan

    def confirm(self,plan,actor,approved=False):
        if approved is not True:raise ValueError('Explicit expert correspondence confirmation is required')
        text(actor,'Source reviewer',120)
        with self.store.transaction():
            if plan.get('spans'):
                fresh=self.plan_composite(plan['work_id'],plan['slot_id'],plan['spans'],plan['composite_review'])
            else:fresh=self.plan(plan['work_id'],plan['slot_id'],plan['source_run_id'],plan['font_asset'],plan['review'])
            if fresh!=plan:raise ValueError('Source/font/facts/binding version changed during review')
            value={k:deepcopy(v) for k,v in plan.items() if k not in ('id','expected_revision','digest','font_asset')}
            value.update(state='APPROVED',actor=actor)
            for key in ('container_binding','label_binding','icon_binding','source_alignment','source_distribution','source_text_flow'):
                if key in plan['review']:value[key]=deepcopy(plan['review'][key])
            return self.store._write('DESIGN_SOURCE_BINDING',plan['id'],value,plan['expected_revision'],
                                     'source_field_typography_explicitly_bound_by_expert')

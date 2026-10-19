"""Explicit expert source/field/font correspondence, never customer fine tuning.

Only a complete single original text run is supported here. Ambiguous composite
runs remain unbound; equal strings alone never create a binding automatically.
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
        if not isinstance(review,dict) or review.get('source_identity_confirmed') is not True:
            raise ValueError('Explicit expert source/font identity review is required;names do not prove identity')
        text(review.get('basis'),'Source correspondence evidence',2048)
        if not isinstance(font_asset,dict) or not font_asset.get('families'):
            raise ValueError('A real verified local font asset is required')
        errors=font_errors(font_asset,font_asset['families'][0])
        if errors:raise ValueError('；'.join(errors))
        work=self.library.artwork(work_id);pins=self.store.pins(work_id)
        if self.store.facts_state(work_id)!='CONFIRMED':raise ValueError('Field/source facts need confirmation first')
        slot=next((slot for slot in work['payload']['slots'] if slot['id']==slot_id),None)
        facts=self.store.facts(work_id);selected=set(facts['confirmation']['observation_ids'])
        matches=[row for row in facts['observations'] if row['id'] in selected and row.get('slot_id')==slot_id
                 and row['classification']=='FIELD' and row['object_type']=='TEXT']
        if not slot or len(matches)!=1:raise ValueError('Need an unambiguous confirmed field')
        observation=self.store._design_observation_document(work_id);original=observation['original_text_evidence']
        run=next((row for row in original['runs'] if row['id']==source_run_id),None)
        if not run or run['text_sha256']!=hashlib.sha256(matches[0]['text'].encode()).hexdigest():
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
            if label.get('kind') not in ('NO_FIXED_LABEL','DYNAMIC_PREFIX'):
                raise ValueError('Unsupported source label mapping')
            if label['kind']=='DYNAMIC_PREFIX' and (not isinstance(label.get('prefix'),str)
                    or not label['prefix'] or not matches[0]['text'].startswith(label['prefix'])):
                raise ValueError('Fixed source prefix must actually occur in the reviewed original field')
        point=run['source_pt']['value']
        if point is None:
            point=review.get('physical_source_pt')
            if not review.get('physical_measurement_refs'):
                raise ValueError('Unknown physical source pt needs external measured-source evidence')
        elif review.get('physical_source_pt') is not None and not math.isclose(point,review['physical_source_pt'],rel_tol=1e-7):
            raise ValueError('Review contradicts known original physical source pt')
        if type(point) not in (int,float) or not math.isfinite(point) or not 0<point<10000:
            raise ValueError('Source pt must be a finite measured positive value')
        crop=work['payload']['crop']
        sx=work['payload']['work_width']/crop['w'];sy=work['payload']['work_height']/crop['h']
        refs=(source_run_id,'EXPERT_SOURCE_REVIEW:'+digest(review))
        source_point=ObservedScalar(point,'pt','OBSERVED','ORIGINAL_RUN_OR_MEASURED_SOURCE_PAGE_PT',refs)
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
            raise ValueError('Anisotropic work transform has unknown scalar pt;explicit measured work pt is required')
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
            measured=review.get(name if uniform else 'work_'+name)
            if measured is not None:
                if not review.get('parameter_measurement_refs'):
                    raise ValueError('Extra source parameters need explicit measured evidence')
                if type(measured) not in (int,float) or not math.isfinite(measured):
                    raise ValueError('Invalid measured source parameter')
                if (name=='horizontal_scale' and not 0<measured<=10) or (name!='horizontal_scale' and not -100<measured<100):
                    raise ValueError('Source parameter processing range exceeded')
                if uniform and name!='horizontal_scale':measured*=sx
                known=typography[name].get('value')
                if known is not None and not math.isclose(known,measured,rel_tol=1e-7,abs_tol=1e-9):
                    raise ValueError('Review contradicts known original source parameter')
                typography[name]=ObservedScalar(measured,unit,'OBSERVED','EXPERT_MEASURED_SOURCE_PARAMETER',refs).to_dict()
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
            measurement=analyze_font(dict(kind='ASSET',asset=font_asset),matches[0]['text'],point,2000,.05,
                                     (font_asset.get('styles') or [None])[0])
            if measurement.get('measurement_verified'):
                typography['shaped_advance']=ObservedScalar(measurement['advance_width_mm'],'mm','DERIVED',
                    'QT_NATURAL_ADVANCE_AT_REVIEWED_SOURCE_FONT_NOT_ORIGINAL_GLYPH_SPACING',refs).to_dict()
        plan=dict(id=key,work_id=work_id,slot_id=slot_id,pins=pins,facts_revision=facts['revision'],
            original_evidence_digest=original['document_digest'],source_run_id=source_run_id,
            expected_revision=before['revision'] if before else 0,font_asset=deepcopy(font_asset),
            review=deepcopy(review),typography=typography)
        plan['digest']=digest(plan);return plan

    def confirm(self,plan,actor,approved=False):
        if approved is not True:raise ValueError('Explicit expert correspondence confirmation is required')
        text(actor,'Source reviewer',120)
        with self.store.transaction():
            fresh=self.plan(plan['work_id'],plan['slot_id'],plan['source_run_id'],plan['font_asset'],plan['review'])
            if fresh!=plan:raise ValueError('Source/font/facts/binding version changed during review')
            value={k:deepcopy(v) for k,v in plan.items() if k not in ('id','expected_revision','digest','font_asset')}
            value.update(state='APPROVED',actor=actor)
            for key in ('container_binding','label_binding','icon_binding','source_alignment','source_distribution','source_text_flow'):
                if key in plan['review']:value[key]=deepcopy(plan['review'][key])
            return self.store._write('DESIGN_SOURCE_BINDING',plan['id'],value,plan['expected_revision'],
                                     'source_field_typography_explicitly_bound_by_expert')

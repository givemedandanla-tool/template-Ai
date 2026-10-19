"""Explicit expert source/field/font correspondence, never customer fine tuning.

Only a complete single original text run is supported here. Ambiguous composite
runs remain unbound; equal strings alone never create a binding automatically.
"""
from copy import deepcopy
import hashlib
import math

from .training_store import TrainingStore, digest, text
from .design_observation import ObservedScalar, unknown, canonical_digest
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
        if run.get('visibility')=='NONPAINTING_TEXT' or run.get('unicode_status','MAPPED')!='MAPPED':
            raise ValueError('Hidden or unmapped source glyphs cannot establish a visible field')
        if run.get('writing_mode','HORIZONTAL')!='HORIZONTAL':
            raise ValueError('Vertical source text needs a supported shaping path')
        if run.get('source_locator',{}).get('kind')=='PDF_ORIGINAL_GLYPH_RUN':
            page=original.get('pdf_glyph_evidence',{})
            if page.get('source_canvas_mapping')!='VERIFIED_PHYSICAL_VIEWPORT':
                raise ValueError('Original PDF glyph viewport does not match the confirmed source')
        point=run['source_pt']['value']
        if point is None:
            point=review.get('physical_source_pt')
            if not review.get('physical_measurement_refs'):
                raise ValueError('Unknown physical source pt needs external measured-source evidence')
        elif review.get('physical_source_pt') is not None and not math.isclose(point,review['physical_source_pt'],rel_tol=1e-7):
            raise ValueError('Review contradicts known original physical source pt')
        if type(point) not in (int,float) or not math.isfinite(point) or not 0<point<10000:
            raise ValueError('Source pt must be a finite measured positive value')
        key=digest([work_id,slot_id]);before=self.store.get('DESIGN_SOURCE_BINDING',key)
        refs=(source_run_id,'EXPERT_SOURCE_REVIEW:'+digest(review))
        typography=dict(font_asset_ref=deepcopy(font_asset),source_font_status='HUMAN_CONFIRMED_SOURCE_ASSOCIATION',
            source_pt=ObservedScalar(point,'pt','OBSERVED','ORIGINAL_RUN_AND_EXPERT_SOURCE_FONT_REVIEW',refs).to_dict(),
            horizontal_scale=unknown('ratio'),tracking=unknown('mm'),shaped_advance=unknown('mm'),
            glyph_runs=dict(status='UNKNOWN',basis='ORIGINAL_GLYPH_POSITIONS_NOT_RECOVERED'))
        if run.get('glyphs'):
            typography['glyph_runs']=dict(status='OBSERVED_SOURCE_GLYPH_PLACEMENT',source_run_ref=source_run_id,
                glyph_digest=canonical_digest(run['glyphs']),
                bounds_basis=run.get('bounds_basis'),font_correspondence='HUMAN_CONFIRMED_NOT_BINARY_IDENTITY_PROOF')
        for name,unit in [('horizontal_scale','ratio'),('tracking','mm')]:
            original_parameter=run.get(name,{})
            if original_parameter.get('status') in ('OBSERVED','DERIVED') and original_parameter.get('value') is not None:
                typography[name]=deepcopy(original_parameter)
            measured=review.get(name)
            if measured is not None:
                if not review.get('parameter_measurement_refs'):
                    raise ValueError('Extra source parameters need explicit measured evidence')
                if type(measured) not in (int,float) or not math.isfinite(measured):
                    raise ValueError('Invalid measured source parameter')
                if (name=='horizontal_scale' and not 0<measured<=10) or (name=='tracking' and not -100<measured<100):
                    raise ValueError('Source parameter processing range exceeded')
                known=typography[name].get('value')
                if known is not None and not math.isclose(known,measured,rel_tol=1e-7,abs_tol=1e-9):
                    raise ValueError('Review contradicts known original source parameter')
                typography[name]=ObservedScalar(measured,unit,'OBSERVED','EXPERT_MEASURED_SOURCE_PARAMETER',refs).to_dict()
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
            for key in ('container_binding','label_binding','icon_binding','source_alignment','source_distribution'):
                if key in plan['review']:value[key]=deepcopy(plan['review'][key])
            return self.store._write('DESIGN_SOURCE_BINDING',plan['id'],value,plan['expected_revision'],
                                     'source_field_typography_explicitly_bound_by_expert')

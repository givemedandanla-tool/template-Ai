"""Persist actual local visual matching as reviewed, explicitly inferred evidence.

This path works when native text/font declarations are absent. It does not
forge an original text run, original point size or original font binary proof.
"""
from copy import deepcopy
import hashlib
import math

from PySide6.QtGui import QImage

from .background import file_digest
from .font_catalog import analyze_font,face_fingerprint,raw_asset
from .fonts import font_errors
from .model import new_id
from .training_store import TrainingStore,digest,text
from .design_observation import ObservedScalar,unknown
from .source_recovery import image_gray
from .visual_font_match import match_fonts


class LocalFontRecovery:
    def __init__(self,library):
        self.library=library
        self.store=TrainingStore.bind(library) if library.db.in_transaction else TrainingStore(library)

    def _field(self,work_id,slot_id):
        if self.store.facts_state(work_id)!='CONFIRMED':raise ValueError('Visual typography needs confirmed field/source facts')
        work=self.library.artwork(work_id);source=self.library.source(work['source_id']);facts=self.store.facts(work_id)
        chosen=set(facts['confirmation']['observation_ids'])
        rows=[r for r in facts['observations'] if r['id'] in chosen and r.get('slot_id')==slot_id and r['classification']=='FIELD' and r['object_type']=='TEXT']
        if len(rows)!=1:raise ValueError('Visual field correspondence is ambiguous')
        self.store.checked(work_id,self.store.source_proof(work_id))
        if file_digest(source['image'])!=source['file_hashes']['image']:raise ValueError('Source image changed;visual evidence is stale')
        return work,source,facts,rows[0]

    def record(self,work_id,slot_id,crop_rect,report,candidate_index,actor,approved=False):
        if not approved:raise ValueError('Explicit local visual evidence recording required')
        text(actor,'Local visual reviewer',120)
        work,source,facts,field=self._field(work_id,slot_id)
        if (not isinstance(crop_rect,list) or len(crop_rect)!=4 or any(type(v) is not int or v<0 for v in crop_rect)
                or min(crop_rect[2:])<=0 or type(candidate_index) is not int or candidate_index<0):
            raise ValueError('Invalid source crop/candidate')
        if candidate_index>=len(report.get('candidates',[])):raise ValueError('Visual candidate does not exist')
        candidate=report['candidates'][candidate_index]
        if candidate['text']!=field['text']:raise ValueError('Visual text does not match the complete confirmed field')
        image=QImage(source['image']);x,y,w,h=crop_rect
        if x+w>image.width() or y+h>image.height():raise ValueError('Visual crop exceeds original image')
        crop=work['payload']['crop'];sx=image.width()/source['width_mm'];sy=image.height()/source['height_mm']
        slot=next(s for s in work['payload']['slots'] if s['id']==slot_id);r=slot['rect']
        field_x=(crop['x']+r['x']*crop['w']/work['payload']['work_width'])*sx
        field_y=(crop['y']+r['y']*crop['h']/work['payload']['work_height'])*sy
        field_w=r['w']*crop['w']/work['payload']['work_width']*sx;field_h=r['h']*crop['h']/work['payload']['work_height']*sy
        if not (x<field_x+field_w and x+w>field_x and y<field_y+field_h and y+h>field_y):
            raise ValueError('Visual crop does not intersect the selected source field')
        actual=image.copy(x,y,w,h)
        if hashlib.sha256(image_gray(actual).tobytes()).hexdigest()!=report['crop_digest']:
            raise ValueError('Visual report does not match this exact source crop')
        if not source.get('calibrated') or candidate['size_pt'] is None:raise ValueError('Physical source size must be calibrated before typography learning')
        ppm=image.width()/source['width_mm']
        repeated=match_fonts(actual,[dict(text=field['text'],origin='REVIEWED_TEXT')],[candidate['face']],
            pixels_per_mm=ppm,tracking_options=(candidate['tracking_em'],),scale_bounds=report['policy']['scale_bounds'],
            maximum_error=report['policy']['maximum_error'],minimum_margin=report['policy']['minimum_margin'])
        if not repeated['candidates'] or repeated['status']=='NO_MATCH':raise ValueError('Actual visual font match cannot be reproduced')
        verified=repeated['candidates'][0]
        if any(not math.isclose(verified[key],candidate[key],rel_tol=1e-6,abs_tol=1e-6) for key in ('score','size_pt','horizontal_scale')):
            raise ValueError('Visual match geometry or source physical scale changed')
        if file_digest(source['image'])!=source['file_hashes']['image']:raise ValueError('Source image changed during matching')
        with self.store.transaction():
            return self.store._write('DESIGN_FONT_MATCH',new_id(),dict(work_id=work_id,slot_id=slot_id,pins=self.store.pins(work_id),
                facts_revision=facts['revision'],source_image_hash=source['file_hashes']['image'],crop_rect=crop_rect,
                crop_digest=report['crop_digest'],candidate=deepcopy(verified),search_complete=report.get('search_complete') is True,
                original_search_status=report['status'],actor=actor,scope='REPRODUCED_VISUAL_HYPOTHESIS_NOT_NATIVE_FONT_IDENTITY'),0,
                'actual_local_visual_font_evidence_saved')

    def checked(self,identity):
        record=self.store.get('DESIGN_FONT_MATCH',identity)
        if not record:raise ValueError('Local visual source evidence missing')
        work,source,facts,field=self._field(record['work_id'],record['slot_id'])
        if self.store.pins(record['work_id'])!=record['pins'] or facts['revision']!=record['facts_revision'] or source['file_hashes']['image']!=record['source_image_hash']:
            raise ValueError('Local visual source evidence is stale')
        return record

    def plan_binding(self,work_id,slot_id,match_id,font_asset,review):
        if review.get('source_identity_confirmed') is not True or review.get('visual_geometry_confirmed') is not True:
            raise ValueError('Explicit field/font/visual geometry review required')
        text(review.get('basis'),'Visual source review basis',2048)
        record=self.checked(match_id)
        if record['work_id']!=work_id or record['slot_id']!=slot_id:raise ValueError('Visual match belongs to another field')
        if font_errors(font_asset,(font_asset.get('families') or [''])[0]):raise ValueError('Visual font asset is unavailable')
        if face_fingerprint(raw_asset(font_asset))!=record['candidate']['face_fingerprint']:
            raise ValueError('Imported face differs from actual visual source candidate')
        work,source,facts,field=self._field(work_id,slot_id);crop=work['payload']['crop']
        sx=work['payload']['work_width']/crop['w'];sy=work['payload']['work_height']/crop['h'];candidate=record['candidate']
        point=candidate['size_pt']*sy;horizontal=candidate['horizontal_scale']*sx/sy
        tracking=candidate['tracking_em']*candidate['size_pt']*25.4/72*sx
        if not 1<=point<=200 or not .05<=horizontal<=10 or not 0<=tracking<=2:
            raise ValueError('Visual source typography is outside currently supported output policy')
        refs=(match_id,'EXPERT_VISUAL_REVIEW:'+digest(review))
        def observed(value,unit,basis):return ObservedScalar(value,unit,'DERIVED',basis,refs).to_dict()
        typography=dict(font_asset_ref=deepcopy(font_asset),source_font_status='REVIEWED_LOCAL_VISUAL_HYPOTHESIS_NOT_NATIVE_BINARY_IDENTITY',
            source_pt=observed(point,'pt','REVIEWED_LOCAL_OUTLINE_FIT_IN_WORK_COORDINATES'),
            source_page_pt=unknown('pt','ORIGINAL_NATIVE_POINT_SIZE_UNAVAILABLE',refs),
            reconstructed_source_pt=observed(candidate['size_pt'],'pt','REVIEWED_LOCAL_OUTLINE_FIT_SOURCE_COORDINATES'),
            horizontal_scale=observed(horizontal,'ratio','REVIEWED_LOCAL_OUTLINE_HORIZONTAL_FIT'),
            tracking=observed(tracking,'mm','REVIEWED_LOCAL_OUTLINE_TRACKING_FIT'),
            word_spacing=unknown('mm','WORD_SPACING_NOT_IDENTIFIED_FROM_THIS_FIT',refs),
            glyph_runs=dict(status='UNKNOWN',basis='NATIVE_GLYPH_PLACEMENT_UNAVAILABLE'))
        spacing=review.get('work_word_spacing')
        if spacing is None and review.get('word_spacing') is not None:spacing=review['word_spacing']*sx
        if spacing is not None:
            if type(spacing) not in (int,float) or not math.isfinite(spacing) or not 0<=spacing<=2 or not review.get('parameter_measurement_refs'):
                raise ValueError('Visual-source word spacing needs explicit bounded independent measurement')
            typography['word_spacing']=ObservedScalar(spacing,'mm','OBSERVED','EXPERT_MEASURED_VISUAL_SOURCE_WORD_SPACING',refs).to_dict()
        measurement=analyze_font(dict(kind='ASSET',asset=font_asset),field['text'],point,2000,.05,tracking_mm=tracking)
        if not measurement.get('measurement_verified'):raise ValueError('Reviewed visual source cannot shape complete text')
        typography['shaped_advance']=observed(measurement['advance_width_mm'],'mm','QT_MEASURED_REVIEWED_VISUAL_SOURCE_FACE')
        original=self.store._design_observation_document(work_id)['original_text_evidence']
        identity=digest([work_id,slot_id]);before=self.store.get('DESIGN_SOURCE_BINDING',identity)
        result=dict(id=identity,work_id=work_id,slot_id=slot_id,source_run_id=None,visual_match_id=match_id,
            visual_match_digest=digest(record),pins=self.store.pins(work_id),facts_revision=facts['revision'],
            original_evidence_digest=original['document_digest'],font_asset=deepcopy(font_asset),review=deepcopy(review),
            expected_revision=before['revision'] if before else 0,typography=typography)
        result['digest']=digest(result);return result

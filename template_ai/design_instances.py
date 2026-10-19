"""Qualified input-specific instances; never one new global template per work."""
from copy import deepcopy
from pathlib import Path
import sqlite3

from .training_store import TrainingStore,digest
from .design_learning import CrossWorkLearning
from .design_qualification import validate_certificate
from .candidate_risk import placement_digest,pin_inputs,engine_digest
from .layout import layout_dependency


def _readonly(root):
    from .storage import Library
    library=object.__new__(Library);library.root=Path(root).resolve();library.assets=library.root/'assets'
    library.db=sqlite3.connect((library.root/'library.sqlite3').as_uri()+'?mode=ro',uri=True,timeout=.1)
    library.db.create_function('training_casefold',1,lambda value:str(value).casefold(),deterministic=True)
    library.db.execute('BEGIN')
    return library


def register_instance(library,session,result,candidate,actor):
    from .input_graph import InputGraph
    from .design_evaluation import check_layout
    store=TrainingStore.bind(library);model,_=CrossWorkLearning(library).checked_model(session['model_id'])
    certificate=validate_certificate(library,model)
    if model['formal_qualification']!='PASS':raise ValueError('Production model qualification is incomplete')
    integrity=check_layout(candidate,InputGraph(session['input_graph']),session['intents'])
    if integrity['status']!='PASS':raise ValueError('Current whole layout failed independent checks')
    reference=dict(model_id=model['id'],weights_digest=model['weights_digest'],manifest_digest=model['manifest_digest'],
        qualification_id=certificate['id'],input_digest=result['input_digest'],result_digest=result['content_digest'],
        input_graph=deepcopy(session['input_graph']),intents=deepcopy(session['intents']),engine_digest=engine_digest())
    identity='generated-'+digest([reference,candidate.template.to_dict(),placement_digest(candidate)])
    reference['instance_id']=identity;candidate.template.generation_reference=reference;candidate.template.state='learned_instance'
    candidate.issues=[issue for issue in candidate.issues if issue!='新學習實例尚待正式來源／模型資格核實']
    candidate.diagnostics=[row for row in candidate.diagnostics if row.get('code')!='UNPUBLISHED']
    snapshot=deepcopy(candidate.risk_context['input_snapshot']);candidate.dependency_stamp=layout_dependency(candidate.template,snapshot['logos'])
    pin_inputs(candidate,**snapshot);candidate.risk_context['source_trust_root']=str(library.root)
    value=dict(state='APPROVED_CURRENT_INPUT_ONLY',actor=actor,reference=reference,template=candidate.template.to_dict(),
        placement_digest=placement_digest(candidate),input_snapshot_digest=digest(snapshot),integrity=integrity)
    prior=store.get('DESIGN_INSTANCE',identity)
    if prior:
        if any(prior[key]!=value[key] for key in value if key!='actor'):raise ValueError('Instance identity already has different content')
    else:store._write('DESIGN_INSTANCE',identity,value,0,'qualified_current_input_instance_saved_not_global_template')
    return candidate


def verify_instance(candidate,library=None):
    own=library is None
    if own:
        root=candidate.risk_context.get('source_trust_root')
        if not root:raise ValueError('Generated instance trust root missing')
        library=_readonly(root)
    try:
        reference=candidate.template.generation_reference
        if candidate.template.state!='learned_instance' or not isinstance(reference,dict):raise ValueError('Unqualified generated state')
        store=TrainingStore.bind(library);record=store.get('DESIGN_INSTANCE',reference.get('instance_id','missing'))
        if not record or record['state']!='APPROVED_CURRENT_INPUT_ONLY':raise ValueError('Generated instance missing or withdrawn')
        if (record['template']!=candidate.template.to_dict() or record['placement_digest']!=placement_digest(candidate)
                or record['reference']!=reference or record['input_snapshot_digest']!=digest(candidate.risk_context['input_snapshot'])):
            raise ValueError('Generated geometry/data/provenance differs from exact approved instance')
        model,dataset=CrossWorkLearning(library).checked_model(reference['model_id'])
        certificate=validate_certificate(library,model)
        if (model['weights_digest']!=reference['weights_digest'] or model['manifest_digest']!=reference['manifest_digest']
                or certificate['id']!=reference['qualification_id']):raise ValueError('Generated instance model qualification differs')
        from .quality_source_rechecks import source_or_template_blocked
        from .model import Template
        for entry in dataset['entries']:
            probe=Template('Source trust probe',1,1,[],id='',family_id='',source_work_id=entry['work_id'],source_work_revision=entry['pins']['work_revision'])
            if source_or_template_blocked(library,probe):raise ValueError('Supporting source is under major quality review')
        from .design_evaluation import check_layout
        from .input_graph import InputGraph
        integrity=check_layout(candidate,InputGraph(reference['input_graph']),reference['intents'])
        if integrity['status']!='PASS':raise ValueError('Fresh generated-instance data/geometry checks failed')
        return record
    finally:
        if own:library.db.close()


def condition(candidate):
    try:verify_instance(candidate)
    except (ValueError,OSError,KeyError,sqlite3.Error) as error:
        return dict(id='CURRENT_GENERATED_INSTANCE',status='UNKNOWN',reason=str(error))
    return dict(id='CURRENT_GENERATED_INSTANCE',status='PASS',reason='已核對多來源模型資格、當次完整資料、實際字形與確切實例；仍須格式與資產輸出核驗')

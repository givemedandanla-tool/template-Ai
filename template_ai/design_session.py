"""Persistent input/layout separation for the desktop shared-learning workflow.

Semantic requests are idempotent; late results cannot overwrite a newer draft.
Preview acceptance never publishes a model or bypasses formal export checks.
"""
from copy import deepcopy
from pathlib import Path
import hashlib

from .training_store import TrainingStore,digest,text
from .model import Template,new_id
from .input_graph import InputGraph
from .layout import Candidate,Placed,layout_dependency
from .design_learning import CrossWorkLearning
from .design_synthesis import synthesize,input_facts,_relation_graph
from .design_ranking import rank


def _body(record):return {k:v for k,v in record.items() if k not in ('id','revision')}


def _serialize(candidate):
    return dict(template=candidate.template.to_dict(),items=[dict(slot_id=item.slot.id,text=item.text,
        scale=item.scale,tracking_mm=item.tracking_mm,logo=item.logo) for item in candidate.items],
        issues=candidate.issues,score=candidate.score,generation=candidate.generation,reasons=candidate.reasons,
        diagnostics=candidate.diagnostics,measurements=candidate.measurements,
        dependency_stamp=candidate.dependency_stamp,risk_context=deepcopy(candidate.risk_context))


def _candidate(value):
    template=Template.from_dict(value['template']);slots={slot.id:slot for slot in template.slots}
    return Candidate(template,[Placed(slots[item['slot_id']],item['text'],item['scale'],item['tracking_mm'],item['logo'])
        for item in value['items']],deepcopy(value['issues']),value['score'],value['generation'],
        deepcopy(value['reasons']),deepcopy(value['diagnostics']),deepcopy(value['measurements']),
        value['dependency_stamp'],deepcopy(value['risk_context']))


class DesignSessions:
    def __init__(self,library):
        self.library=library
        self.store=TrainingStore.bind(library) if library.db.in_transaction else TrainingStore(library)
        self.learning=CrossWorkLearning(library)

    def current(self,session_id,expected_revision=None):
        row=self.store.get('DESIGN_SESSION',session_id)
        if not row or expected_revision is not None and row['revision']!=expected_revision:
            raise ValueError('Session is missing or its expected revision is stale')
        return row

    def create(self,graph,width,height,actor,model_id=None,policy=None):
        text(actor,'Session actor',120);graph.validate(graph.data)
        if model_id is None:
            model,active=self.learning.active()
            if model is None:raise ValueError('No current approved preview/production learning model')
            model_id=model['id'];policy=active['policy']
        model,_=self.learning.checked_model(model_id)
        policy=deepcopy(policy or {})
        if policy.get('approved') is not True or not policy.get('version'):
            raise ValueError('Session requires a versioned core policy')
        if any(type(v) not in (int,float) or not 0<v<=2000 for v in (width,height)):
            raise ValueError('Invalid physical dimensions')
        with self.store.transaction():
            return self.store._write('DESIGN_SESSION',new_id(),dict(schema=1,input_graph=deepcopy(graph.data),
                width_mm=width,height_mm=height,actor=actor,model_id=model_id,model_revision=model['revision'],
                weights_digest=model['weights_digest'],policy=policy,data_revision=1,layout_revision=0,
                intents=[],layout_undo=[],result_id=None,result_state='NEEDS_SOLVE',confirmation=None),
                0,'design_session_created')

    def _edit(self,session_id,expected_revision,request_id,command,change):
        text(request_id,'Request ID',128)
        key=digest([session_id,request_id]);payload_digest=digest(command)
        with self.store.transaction():
            prior=self.store.get('DESIGN_COMMAND',key)
            if prior:
                if prior['payload_digest']!=payload_digest:raise ValueError('Idempotency key reused for a different command')
                return dict(prior,replayed=True,current_session_revision=self.current(session_id)['revision'])
            session=self.current(session_id,expected_revision);value=deepcopy(_body(session))
            change(value);value['result_state']='STALE';value['confirmation']=None
            saved=self.store._write('DESIGN_SESSION',session_id,value,session['revision'],'design_semantic_intent_or_data_changed')
            return self.store._write('DESIGN_COMMAND',key,dict(session_id=session_id,request_id=request_id,
                payload_digest=payload_digest,command=deepcopy(command),applied_revision=saved['revision']),
                0,'design_command_idempotently_applied')

    def replace_input(self,session_id,expected_revision,request_id,graph):
        graph.validate(graph.data)
        def change(value):
            value['input_graph']=deepcopy(graph.data);value['data_revision']+=1
        return self._edit(session_id,expected_revision,request_id,dict(action='REPLACE_INPUT',graph=graph.data),change)

    def set_relation(self,session_id,expected_revision,request_id,subject,relation,object_id):
        intent=dict(subject=subject,relation=relation,object=object_id)
        def change(value):
            graph=InputGraph(value['input_graph']);facts=input_facts(graph)
            ids={row['render_id'] for row in facts}
            _relation_graph([intent],ids)
            movable=set(value['policy'].get('movable_kinds',('phone','email','line','ig','address')))
            subject_fact=next(row for row in facts if row['render_id']==subject)
            if subject_fact['kind'] not in movable:raise ValueError('Protected role cannot be moved by this policy')
            target_fact=next(row for row in facts if row['render_id']==object_id)
            if subject_fact['owner_port']!=target_fact['owner_port']:
                raise ValueError('Cross-owner relative editing lacks supported group correspondence')
            old=deepcopy(value['intents']);axis='V' if relation in ('ABOVE','BELOW') else 'H'
            kept=[row for row in old if not ({row['subject'],row['object']}=={subject,object_id}
                and ('V' if row['relation'] in ('ABOVE','BELOW') else 'H')==axis)]
            updated=kept+[intent];_relation_graph(updated,ids)
            value['layout_undo'].append(old);value['intents']=updated;value['layout_revision']+=1
        return self._edit(session_id,expected_revision,request_id,dict(action='SET_RELATION',intent=intent),change)

    def undo_layout(self,session_id,expected_revision,request_id):
        def change(value):
            if not value['layout_undo']:raise ValueError('No layout intention to undo')
            value['intents']=value['layout_undo'].pop();value['layout_revision']+=1
        return self._edit(session_id,expected_revision,request_id,dict(action='UNDO_LAYOUT'),change)

    def resolve_logos(self,graph,width,height):
        from .logo_store import LogoStore
        logo_store=LogoStore(self.library);resolved_logos={}
        for i,entity in enumerate(graph.data['companies']):
            if not entity['logo_id']:continue
            label=next((field['value'] for field in graph.data['fields']
                if field['kind']=='name' and entity['id'] in field['users']),'')
            match=logo_store.match(entity['id'],label,width,height,selected_id=entity['logo_id'])
            if match['selected']:resolved_logos['c'+str(i+1)]=dict(match['selected'],design_entity_ref=entity['id'])
        return resolved_logos

    def solve(self,session_id,expected_revision):
        snapshot=self.current(session_id,expected_revision)
        model,_=self.learning.checked_model(snapshot['model_id'])
        if model['revision']!=snapshot['model_revision'] or model['weights_digest']!=snapshot['weights_digest']:
            raise ValueError('Pinned session model differs;do not silently replace it')
        graph=InputGraph(snapshot['input_graph']);cache=self.store.get('DESIGN_RESULT',snapshot.get('result_id') or 'missing')
        resolved_logos=self.resolve_logos(graph,snapshot['width_mm'],snapshot['height_mm'])
        if (cache and snapshot['result_state']=='CURRENT' and cache['data_revision']==snapshot['data_revision']
                and cache['layout_revision']==snapshot['layout_revision']):
            if cache.get('selected'):
                old=_candidate(cache['selected']['serialized'])
                if old.dependency_stamp==layout_dependency(old.template,resolved_logos):return cache
        choices=[];attempts=[]
        previous_family=cache['selected']['family_id'] if cache and cache.get('selected') else None
        families=sorted(model['artifact']['profile_model']['families'],
                        key=lambda row:(row['family_id']!=previous_family,row['family_id']))
        for family in families:
            result=synthesize(family,graph,snapshot['width_mm'],snapshot['height_mm'],snapshot['policy'],snapshot['intents'],resolved_logos)
            attempts.append(dict(family_id=family['family_id'],status=result['status'],issues=result['issues'],
                                 searched=result['searched'],complete_search=result['complete_search']))
            for index,row in enumerate(result['candidates']):
                candidate=row['candidate'];area=sum(item.slot.rect.w*item.slot.rect.h for item in candidate.items)
                choices.append(dict(id=family['family_id']+':'+str(index),family_id=family['family_id'],
                    configuration_ids=row['configuration_ids'],geometry_digest=row['geometry_digest'],
                    legal_preview_geometry=True,formal_eligible=candidate.formal_eligible,
                    features=dict(deviation=-candidate.score,scale_loss=sum(1-item.scale for item in candidate.items),
                        density=area/(snapshot['width_mm']*snapshot['height_mm']),
                        relation_changes=len(snapshot['intents']),joint_style_residual=0.),serialized=_serialize(candidate)))
            if previous_family==family['family_id'] and choices:
                break  # A legal current-family variant precedes cross-family fallback.
        ranking=rank(choices,dict(version=snapshot['policy']['version'],family_order=snapshot['policy'].get('family_order',[])))
        selected=ranking['ranked'][0]['candidate'] if ranking['ranked'] else None
        body=dict(session_id=session_id,data_revision=snapshot['data_revision'],layout_revision=snapshot['layout_revision'],
            input_digest=digest(graph.data),model_id=model['id'],model_revision=model['revision'],weights_digest=model['weights_digest'],
            policy_version=snapshot['policy']['version'],status='FEASIBLE_PREVIEW' if selected else 'NO_SUPPORTED_CANDIDATE',
            selected=deepcopy(selected),attempts=attempts,ranking_scope=ranking['scope'],
            previous_family=previous_family,
            family_switch_requires_review=bool(selected and previous_family and selected['family_id']!=previous_family),
            production_qualification='NOT_EVALUATED',customer_confirmation_is_not_publication=True)
        body['content_digest']=digest(body)
        with self.store.transaction():
            current=self.current(session_id,snapshot['revision'])
            if self.learning.checked_model(model['id'])[0]!=model:raise ValueError('Model/source changed while solving')
            saved=self.store._write('DESIGN_RESULT',new_id(),body,0,'shared_model_layout_result_saved')
            value=deepcopy(_body(current));value.update(result_id=saved['id'],result_state='CURRENT',confirmation=None)
            self.store._write('DESIGN_SESSION',session_id,value,current['revision'],'exact_layout_result_installed')
            return saved

    def checked_result(self,session_id):
        session=self.current(session_id);result=self.store.get('DESIGN_RESULT',session.get('result_id') or 'missing')
        if (session['result_state']!='CURRENT' or not result or result['status']!='FEASIBLE_PREVIEW'
                or result['data_revision']!=session['data_revision'] or result['layout_revision']!=session['layout_revision']
                or result['input_digest']!=digest(session['input_graph'])):
            raise ValueError('Current input/layout has no current verified preview;new data is retained')
        body={k:v for k,v in result.items() if k not in ('id','revision','content_digest')}
        if digest(body)!=result['content_digest']:raise ValueError('Saved result content differs')
        model,_=self.learning.checked_model(session['model_id'])
        if model['weights_digest']!=result['weights_digest']:raise ValueError('Model/source proof is stale')
        candidate=_candidate(result['selected']['serialized'])
        logos=self.resolve_logos(InputGraph(session['input_graph']),session['width_mm'],session['height_mm'])
        if candidate.dependency_stamp!=layout_dependency(candidate.template,logos):raise ValueError('Font/asset/engine dependencies changed')
        return session,result,candidate

    def confirm(self,session_id,expected_revision,actor,*,for_production=False):
        text(actor,'Confirmation actor',120)
        with self.store.transaction():
            session,result,candidate=self.checked_result(session_id)
            if session['revision']!=expected_revision:raise ValueError('Confirmation revision is stale')
            if for_production and not candidate.formal_eligible:raise ValueError('Production qualification is incomplete')
            confirmation=dict(result_id=result['id'],content_digest=result['content_digest'],
                data_revision=session['data_revision'],layout_revision=session['layout_revision'],
                actor=actor,for_production=for_production,scope='PRINT_RESULT' if for_production else 'PREVIEW_ONLY')
            value=deepcopy(_body(session));value['confirmation']=confirmation
            return self.store._write('DESIGN_SESSION',session_id,value,session['revision'],'exact_result_confirmed_without_rule_publication')

    def export(self,session_id,target,*,preview=True,dpi=150):
        with self.store.transaction():
            session,result,candidate=self.checked_result(session_id);confirmation=session.get('confirmation')
            if (not confirmation or confirmation['result_id']!=result['id']
                    or confirmation['content_digest']!=result['content_digest']):raise ValueError('Confirm exact current result before output')
            if not preview and not confirmation['for_production']:raise ValueError('Preview confirmation is not production approval')
            from .render import export
            path=export(candidate,target,dpi=dpi,preview=preview)
            data=Path(path).read_bytes();artifact=dict(session_id=session_id,result_id=result['id'],
                input_digest=result['input_digest'],content_digest=result['content_digest'],
                path=str(Path(path).resolve()),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),
                production=not preview,model_id=result['model_id'],weights_digest=result['weights_digest'])
            try:
                return self.store._write('DESIGN_ACCEPTED_ARTIFACT',new_id(),artifact,0,'exact_output_artifact_retained')
            except BaseException:
                # Remove only our exact newly created file if recording fails.
                output=Path(path)
                if output.is_file() and not output.is_symlink() and hashlib.sha256(output.read_bytes()).hexdigest()==artifact['sha256']:
                    output.unlink()
                raise

    def replay_artifact(self,artifact_id):
        artifact=self.store.get('DESIGN_ACCEPTED_ARTIFACT',artifact_id)
        if not artifact:raise ValueError('Accepted output artifact does not exist')
        path=Path(artifact['path'])
        if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=artifact['sha256']:
            raise ValueError('Exact accepted artifact is unavailable;JSON recomputation is not replay')
        return artifact

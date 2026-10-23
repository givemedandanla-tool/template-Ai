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
from .design_ranking import rank,candidate_features


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

    def _choice_summaries(self,choices):
        """Keep bounded result metadata; immutable candidate payloads live separately."""
        summaries=[]
        for choice in choices:
            value=deepcopy(choice);serialized=value.pop('serialized')
            key=digest(serialized);record=self.store.get('DESIGN_CHOICE',key)
            if record:
                if digest(record['serialized'])!=key:raise ValueError('Saved candidate content differs')
            else:
                self.store._write('DESIGN_CHOICE',key,dict(serialized=serialized),0,'exact_candidate_payload_saved')
            value.update(serialized_ref=key,item_count=len(serialized['items']))
            summaries.append(value)
        return summaries

    def _expand_choice(self,choice):
        value=deepcopy(choice)
        if 'serialized' not in value:
            key=value.get('serialized_ref');record=self.store.get('DESIGN_CHOICE',key or 'missing')
            if not record or digest(record['serialized'])!=key:raise ValueError('Saved candidate is missing or changed;regenerate before selection')
            value['serialized']=deepcopy(record['serialized'])
        return value

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
        ranker_ref=None
        if policy.get('use_preference_ranker') is True:
            from .design_feedback import DesignFeedback
            active=self.store.get('DESIGN_RANKER_ACTIVE','local-preference')
            if active:
                ranker=DesignFeedback(self.library).checked_ranker(active['model_id'])
                ranker_ref=dict(id=ranker['id'],weights_digest=ranker['weights_digest'])
                if policy.get('production') is True:
                    from .design_rank_qualification import RankerQualification
                    if active['policy'].get('production') is not True:raise ValueError('Preview ranker cannot be used for a production session')
                    qualification_id=active['policy'].get('qualification_id','missing')
                    RankerQualification(self.library).checked(qualification_id,ranker['id'])
                    ranker_ref['qualification_id']=qualification_id
            elif policy.get('production') is True:raise ValueError('Requested production ranker is not active')
        with self.store.transaction():
            return self.store._write('DESIGN_SESSION',new_id(),dict(schema=1,input_graph=deepcopy(graph.data),
                width_mm=width,height_mm=height,actor=actor,model_id=model_id,model_revision=model['revision'],
                weights_digest=model['weights_digest'],policy=policy,data_revision=1,layout_revision=0,
                ranker_ref=ranker_ref,intents=[],layout_undo=[],layout_redo=[],result_id=None,result_state='NEEDS_SOLVE',confirmation=None),
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

    def resize(self,session_id,expected_revision,request_id,width,height):
        if any(type(v) not in (int,float) or not 0<v<=2000 for v in (width,height)):raise ValueError('Invalid physical dimensions')
        def change(value):
            value.update(width_mm=width,height_mm=height,data_revision=value['data_revision']+1)
        return self._edit(session_id,expected_revision,request_id,dict(action='RESIZE',width=width,height=height),change)

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
            value['layout_undo'].append(old);value['layout_redo']=[];value['intents']=updated;value['layout_revision']+=1
        return self._edit(session_id,expected_revision,request_id,dict(action='SET_RELATION',intent=intent),change)

    def undo_layout(self,session_id,expected_revision,request_id):
        def change(value):
            if not value['layout_undo']:raise ValueError('No layout intention to undo')
            value.setdefault('layout_redo',[]).append(deepcopy(value['intents']))
            value['intents']=value['layout_undo'].pop();value['layout_revision']+=1
        return self._edit(session_id,expected_revision,request_id,dict(action='UNDO_LAYOUT'),change)

    def redo_layout(self,session_id,expected_revision,request_id):
        def change(value):
            if not value.get('layout_redo'):raise ValueError('No layout intention to redo')
            value['layout_undo'].append(deepcopy(value['intents']))
            value['intents']=value['layout_redo'].pop();value['layout_revision']+=1
        return self._edit(session_id,expected_revision,request_id,dict(action='REDO_LAYOUT'),change)

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

    def solve(self,session_id,expected_revision,*,cancel=None,progress=None):
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
        for family_index,family in enumerate(families):
            if cancel and cancel():raise ValueError('LAYOUT_CANCELLED: 已停止排版；輸入資料與先前稿件仍保留。')
            if progress:progress(dict(done=family_index,total=len(families),phase='FAMILY'))
            kwargs=dict(cancel=cancel) if cancel else {}
            result=synthesize(family,graph,snapshot['width_mm'],snapshot['height_mm'],snapshot['policy'],snapshot['intents'],resolved_logos,**kwargs)
            attempts.append(dict(family_id=family['family_id'],status=result['status'],issues=result['issues'],
                                 searched=result['searched'],complete_search=result['complete_search']))
            for index,row in enumerate(result['candidates']):
                candidate=row['candidate']
                choices.append(dict(id=family['family_id']+':'+str(index),family_id=family['family_id'],
                    default_preference_cost=row.get('default_preference_cost',0),
                    configuration_ids=row['configuration_ids'],geometry_digest=row['geometry_digest'],
                    legal_preview_geometry=True,formal_eligible=candidate.formal_eligible,
                    features=candidate_features(
                        candidate,snapshot['width_mm'],snapshot['height_mm'],snapshot['intents']),serialized=_serialize(candidate)))
            if previous_family==family['family_id'] and choices:
                break  # A legal current-family variant precedes cross-family fallback.
        preference=None
        if snapshot.get('ranker_ref'):
            from .design_feedback import DesignFeedback
            ranker=DesignFeedback(self.library).checked_ranker(snapshot['ranker_ref']['id'])
            if ranker['weights_digest']!=snapshot['ranker_ref']['weights_digest']:raise ValueError('Pinned preference weights differ')
            preference=ranker['artifact']
        ranking=rank(choices,dict(version=snapshot['policy']['version'],family_order=snapshot['policy'].get('family_order',[])),preference)
        minima={}
        for row in ranking['ranked']:
            choice=row['candidate'];family=choice['family_id'];cost=choice.get('default_preference_cost',0)
            minima[family]=min(minima.get(family,cost),cost)
        # Stable sort preserves cross-family ranking among preferred legal results.
        ranking['ranked'].sort(key=lambda row:row['candidate'].get('default_preference_cost',0)>minima[row['candidate']['family_id']])
        selected=ranking['ranked'][0]['candidate'] if ranking['ranked'] else None
        body=dict(session_id=session_id,data_revision=snapshot['data_revision'],layout_revision=snapshot['layout_revision'],
            input_digest=digest(graph.data),input_graph=deepcopy(graph.data),ranker_ref=deepcopy(snapshot.get('ranker_ref')),model_id=model['id'],model_revision=model['revision'],weights_digest=model['weights_digest'],
            policy_version=snapshot['policy']['version'],status='FEASIBLE_PREVIEW' if selected else 'NO_SUPPORTED_CANDIDATE',
            selected=deepcopy(selected),choices=deepcopy([row['candidate'] for row in ranking['ranked']]),attempts=attempts,ranking_scope=ranking['scope'],
            previous_family=previous_family,
            family_switch_requires_review=bool(selected and previous_family and selected['family_id']!=previous_family),
            production_qualification='NOT_EVALUATED',customer_confirmation_is_not_publication=True)
        body['content_digest']=digest(body)
        if cancel and cancel():raise ValueError('LAYOUT_CANCELLED: 已停止排版；未採用這次結果。')
        with self.store.transaction():
            current=self.current(session_id,snapshot['revision'])
            if self.learning.checked_model(model['id'])[0]!=model:raise ValueError('Model/source changed while solving')
            body['choices']=self._choice_summaries(body['choices'])
            body.pop('content_digest',None);body['content_digest']=digest(body)
            saved=self.store._write('DESIGN_RESULT',new_id(),body,0,'shared_model_layout_result_saved')
            value=deepcopy(_body(current));value.update(result_id=saved['id'],result_state='CURRENT',confirmation=None)
            self.store._write('DESIGN_SESSION',session_id,value,current['revision'],'exact_layout_result_installed')
            return saved

    def select_candidate(self,session_id,expected_revision,index):
        with self.store.transaction():
            session,result,_=self.checked_result(session_id)
            if session['revision']!=expected_revision:raise ValueError('Candidate selection is stale')
            choices=result.get('choices',[])
            if type(index) is not int or not 0<=index<len(choices):raise ValueError('Candidate choice is unavailable')
            body=deepcopy(_body(result));body.pop('content_digest',None)
            body['selected']=self._expand_choice(choices[index])
            body['family_switch_requires_review']=bool(result.get('previous_family') and body['selected']['family_id']!=result['previous_family'])
            body['production_qualification']='NOT_EVALUATED';body['content_digest']=digest(body)
            saved=self.store._write('DESIGN_RESULT',new_id(),body,0,'explicit_candidate_selection')
            value=deepcopy(_body(session));value.update(result_id=saved['id'],confirmation=None)
            self.store._write('DESIGN_SESSION',session_id,value,session['revision'],'selected_exact_layout_candidate')
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
        if session.get('ranker_ref'):
            from .design_feedback import DesignFeedback
            ranker=DesignFeedback(self.library).checked_ranker(session['ranker_ref']['id'])
            if ranker['weights_digest']!=session['ranker_ref']['weights_digest']:raise ValueError('Preference support changed')
        candidate=_candidate(result['selected']['serialized'])
        logos=self.resolve_logos(InputGraph(session['input_graph']),session['width_mm'],session['height_mm'])
        if candidate.dependency_stamp!=layout_dependency(candidate.template,logos):raise ValueError('Font/asset/engine dependencies changed')
        return session,result,candidate

    def review_family_switch(self,session_id,expected_revision,actor):
        text(actor,'Layout change reviewer',120)
        with self.store.transaction():
            session,result,_=self.checked_result(session_id)
            if session['revision']!=expected_revision:raise ValueError('Layout review revision is stale')
            body=deepcopy(_body(session));body['family_switch_review']=dict(result_id=result['id'],
                content_digest=result['content_digest'],actor=actor)
            return self.store._write('DESIGN_SESSION',session_id,body,session['revision'],'changed_family_explicitly_reviewed')

    def qualify_result(self,session_id,expected_revision,actor):
        text(actor,'Current instance reviewer',120)
        with self.store.transaction():
            session,result,candidate=self.checked_result(session_id)
            if session['revision']!=expected_revision:raise ValueError('Instance review revision is stale')
            from .design_instances import register_instance
            candidate=register_instance(self.library,session,result,candidate,actor)
            body=deepcopy(_body(result));body.pop('content_digest',None)
            body['selected']['serialized']=_serialize(candidate);body['selected']['geometry_digest']=digest(candidate.template.to_dict())
            body.update(production_qualification='CORE_DIGITAL_INSTANCE_QUALIFIED',parent_result_id=result['id'])
            body['content_digest']=digest(body)
            saved=self.store._write('DESIGN_RESULT',new_id(),body,0,'qualified_instance_result_preserved')
            value=deepcopy(_body(session));value.update(result_id=saved['id'],confirmation=None)
            review=session.get('family_switch_review',{})
            if review.get('result_id')==result['id'] and review.get('content_digest')==result['content_digest']:
                value['family_switch_review']=dict(review,result_id=saved['id'],content_digest=saved['content_digest'],parent_review_result=result['id'])
            self.store._write('DESIGN_SESSION',session_id,value,session['revision'],'qualified_instance_installed_for_explicit_confirmation')
            return saved

    def confirm(self,session_id,expected_revision,actor,*,for_production=False):
        text(actor,'Confirmation actor',120)
        with self.store.transaction():
            session,result,candidate=self.checked_result(session_id)
            if session['revision']!=expected_revision:raise ValueError('Confirmation revision is stale')
            review=session.get('family_switch_review',{})
            if result.get('family_switch_requires_review') and (review.get('result_id')!=result['id'] or review.get('content_digest')!=result['content_digest']):
                raise ValueError('Changed template family needs explicit review of this exact result')
            if for_production and not candidate.formal_eligible:raise ValueError('Production qualification is incomplete')
            confirmation=dict(result_id=result['id'],content_digest=result['content_digest'],
                data_revision=session['data_revision'],layout_revision=session['layout_revision'],
                actor=actor,for_production=for_production,scope='PRINT_RESULT' if for_production else 'PREVIEW_ONLY')
            value=deepcopy(_body(session));value['confirmation']=confirmation
            return self.store._write('DESIGN_SESSION',session_id,value,session['revision'],'exact_result_confirmed_without_rule_publication')

    def accepted_key(self,graph,width,height,intents=None):
        graph.validate(graph.data);data=deepcopy(graph.data);data.pop('revision',None)
        ordered=sorted(deepcopy(intents or []),key=digest)
        return digest(dict(input=data,width_mm=float(width),height_mm=float(height),intents=ordered))

    def find_accepted(self,graph,width,height,intents=None,*,production=True):
        key=self.accepted_key(graph,width,height,intents)
        reference=self.store.get('DESIGN_OUTPUT_DEFAULT',digest([key,production]))
        if not reference:return None
        artifact=self.replay_artifact(reference['artifact_id'])
        if artifact.get('accepted_input_key')!=key or artifact['production']!=production:
            raise ValueError('Accepted output default reference differs')
        return artifact

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
                production=not preview,model_id=result['model_id'],weights_digest=result['weights_digest'],
                accepted_input_key=self.accepted_key(InputGraph(session['input_graph']),session['width_mm'],session['height_mm'],session['intents']),
                accepted_candidate=_serialize(candidate),accepted_candidate_digest=digest(_serialize(candidate)),
                supporting_source_hashes=[entry['source_hash'] for entry in self.learning.checked_model(result['model_id'])[1]['entries']])
            try:
                saved=self.store._write('DESIGN_ACCEPTED_ARTIFACT',new_id(),artifact,0,'exact_output_artifact_retained')
                key=digest([artifact['accepted_input_key'],artifact['production']])
                prior=self.store.get('DESIGN_OUTPUT_DEFAULT',key)
                if prior is None:self.store._write('DESIGN_OUTPUT_DEFAULT',key,dict(artifact_id=saved['id'],basis='FIRST_EXPLICITLY_CONFIRMED_OUTPUT_STABLE_UNTIL_EXPLICIT_REVIEW'),0,'accepted_output_default_fixed')
                return saved
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
        if artifact.get('production'):
            saved=artifact.get('accepted_candidate')
            if not saved or digest(saved)!=artifact.get('accepted_candidate_digest'):
                raise ValueError('Exact accepted output provenance is unavailable;do not regenerate')
            from .trusted_sample_pool import source_restriction
            for source_hash in artifact.get('supporting_source_hashes',[]):
                if source_restriction(self.store,source_hash,'CROSS_WORK_RULE_LEARNING_LOCAL'):
                    raise ValueError('Accepted artifact source rights are stopped;do not replace its layout')
            candidate=_candidate(saved)
            current_fonts={asset['hash']:asset for asset in self.library.fonts()}
            for item in candidate.items:
                if item.slot.kind!='logo':
                    asset=item.slot.font_asset
                    if not asset or asset['hash'] not in current_fonts:raise ValueError('Current output font-rights record missing')
                    item.slot.font_asset=current_fonts[asset['hash']]
            from .font_evidence import font_rights_diagnostics
            problems=[reason for row in font_rights_diagnostics(candidate,path.suffix.lstrip('.')) for reason in row['reasons']]
            if problems:raise ValueError('Current artifact reuse rights unavailable: '+'；'.join(problems))
            reference=candidate.template.generation_reference or {}
            graph=reference.get('input_graph')
            if graph:
                logos=self.resolve_logos(InputGraph(graph),candidate.template.width_mm,candidate.template.height_mm)
                for item in candidate.items:
                    if item.slot.kind=='logo' and (not item.logo or logos.get(item.slot.owner,{}).get('id')!=item.logo.get('id')):
                        raise ValueError('Exact accepted Logo identity/version is no longer authorized')
        return artifact

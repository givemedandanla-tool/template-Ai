"""Evidence-based three-valued candidate gates, never confidence/sample-count permission."""
import copy
from functools import lru_cache
from pathlib import Path
from dataclasses import asdict
from .training_store import digest

HARD_CODES=frozenset(('CAPACITY','NO_SLOT','WIDTH','HEIGHT','TEMPLATE_CHECK','BOUNDS','DIMENSIONS','FIELD_PROPERTIES','DUPLICATE_MAPPING'))
UNKNOWN_CODES=frozenset(('FONT_UNVERIFIED','LOGO_MISSING','LOGO_MISMATCH','BACKGROUND_CHECK','DEPENDENCY_CHANGED','REQUIRED','UNKNOWN_COMPANY','COMPANY_BINDING','UNBOUND_COMPANY','SOURCE_MISSING','VISUAL_PENDING','SOURCE_IDENTITY_UNKNOWN','LOGO_CONTENT_UNKNOWN'))
LABELS=dict(SAFE_RECOMMENDATION='安全候選／仍需輸出前重核',REVIEW_DRAFT='待確認草稿／禁止正式輸出',EVIDENCE_REQUIRED='資料或來源待核實／禁止正式輸出',HARD_BLOCKED='當前候選硬性阻擋／禁止正式輸出')


def conjunction(statuses):
    if 'FAIL' in statuses:return 'FAIL'
    if 'UNKNOWN' in statuses:return 'UNKNOWN'
    return 'PASS'


def assess(candidate):
    context=getattr(candidate,'risk_context',{}) or {};diagnostics=candidate.diagnostics;codes={row.get('code') for row in diagnostics};hard=sorted(codes&HARD_CODES);unknown=sorted(codes&UNKNOWN_CODES);approval='PASS' if candidate.template.state=='published' else 'UNKNOWN'
    # Unclassified old-engine issues never become an unsatisfiability certificate.
    unexplained=bool(candidate.issues) and not hard and not unknown and codes!={'UNPUBLISHED'}
    physical='FAIL' if hard else 'UNKNOWN' if unknown or unexplained else 'PASS'
    evidence=copy.deepcopy(context.get('conditions',[]))
    if context.get('comparison_only'):evidence.append(dict(id='COMPARISON_ONLY',status='UNKNOWN',reason='非正式比較副本；尚未明確採用，不得正式輸出'))
    if any(not isinstance(c,dict) or c.get('status') not in ('PASS','FAIL','UNKNOWN') or not c.get('reason') for c in evidence):raise ValueError('風險條件需明確PASS／FAIL／UNKNOWN與具體原因')
    conditions=[dict(id='ENGINE_REQUIRED_CONDITIONS',status=physical,reason='實際既有語意／固定字級／框位／Logo檢查',hard_failures=hard,unknown_conditions=unknown),dict(id='PUBLISHED_BASE_APPROVAL',status=approval,reason='目前模板已發布' if approval=='PASS' else '尚未完成模板發布核准')]+evidence
    conditions.extend(freshness_conditions(candidate))
    evidence += [c for c in conditions if c.get('id')=='SNAPSHOT_FRESHNESS']
    trust=conjunction([c['status'] for c in evidence if c.get('required',True)]);review=any(c['status']!='PASS' for c in evidence if not c.get('required',True));basis_approved=approval=='PASS' or valid_approved_base(context.get('approved_base'))
    if not basis_approved:conditions.append(dict(id='APPROVED_OR_REVIEWED_BASE',status='UNKNOWN',reason='尚無已核准基準的可核對憑證'))
    state='HARD_BLOCKED' if hard else 'EVIDENCE_REQUIRED' if physical=='UNKNOWN' or trust!='PASS' or not basis_approved else 'REVIEW_DRAFT' if approval!='PASS' or review else 'SAFE_RECOMMENDATION'
    result=dict(state=state,label=LABELS[state],conditions=conditions,known_hard_conditions_passed=physical=='PASS' and trust=='PASS' and basis_approved,formal_allowed=state=='SAFE_RECOMMENDATION' and candidate.valid,score_kind='RULE_FITNESS_NOT_CALIBRATED_CONFIDENCE',generation=candidate.generation,template_id=candidate.template.id,template_version=candidate.template.version,dimensions=[candidate.template.width_mm,candidate.template.height_mm],template_digest=digest(candidate.template.to_dict()),input_digest=context.get('input_digest'),engine_digest=context.get('engine_digest'),models_used=['EXPLICIT_RULE_TEMPLATE_NO_INFERENCE_MODEL'],dependency_stamp=candidate.dependency_stamp,basis=context.get('basis',['EXPLICIT_PUBLISHED_RULE_TEMPLATE'] if approval=='PASS' else ['UNAPPROVED_CANDIDATE_ONLY']),supplementation=False,automatic_learning=False,accept_risk_is_not_a_gate=True)
    result['digest']=digest(result);return result


def bind_source(candidate,library,conditions=None,require_registered=False):
    context=copy.deepcopy(candidate.risk_context);context['conditions']=copy.deepcopy(conditions if conditions is not None else [x for x in context.get('conditions',[]) if x['id'] not in ('SOURCE_AND_QUALITY_TRUST','EXACT_PUBLISHED_SOURCE_VERSION','ORIGINAL_SOURCE_BYTES')]);context['basis']=['EXACT_PUBLISHED_TEMPLATE','CURRENT_EXPLICIT_SOURCE_AND_GEOMETRY_PROVENANCE']
    try:library._template_provenance(candidate.template)
    except (ValueError,OSError) as error:context['conditions'].append(dict(id='SOURCE_AND_QUALITY_TRUST',status='UNKNOWN',reason=str(error)))
    else:context['conditions'].append(dict(id='SOURCE_AND_QUALITY_TRUST',status='PASS',reason='現行模板與來源／標記／必要用途已核對'))
    pinned=context.get('source_template_pin')
    if require_registered or pinned:
        try:
            source=library.object_snapshot('TEMPLATE',candidate.template.id)['payload']
            if source.get('state')!='published':raise ValueError('來源模板已不再發布')
            expected=dict(id=source['id'],version=source['version'],digest=digest(source))
            if pinned is not None and pinned!=expected:raise ValueError('已核准來源模板exact版本已變更，需重新選擇／核對')
            if pinned is None:
                if digest(candidate.template.to_dict())!=expected['digest']:raise ValueError('局部版面缺已核對來源版本與人工更動憑證')
                context['source_template_pin']=expected
        except (ValueError,OSError,KeyError) as error:context['conditions'].append(dict(id='EXACT_PUBLISHED_SOURCE_VERSION',status='UNKNOWN',reason=str(error)))
        else:context['conditions'].append(dict(id='EXACT_PUBLISHED_SOURCE_VERSION',status='PASS',reason='來源已發布模板exact版次仍一致；本次幾何另受整張Gate核對'))
    if candidate.template.source_id:
        try:
            source=library.source(candidate.template.source_id);proof=context.get('original_source_proof')
            from .source_links import fingerprint
            from pathlib import Path
            if not proof or proof['hash']!=source['hash'] or proof['path']!=str(Path(source['current_path']).resolve()) or proof['link_revision']!=source['link_revision'] or tuple(proof['stat'])!=fingerprint(Path(proof['path']).stat()):raise ValueError('原稿內容／路徑／連結版次缺當次背景核實憑證或已變更，需重新排版')
        except (ValueError,OSError,KeyError) as error:context['conditions'].append(dict(id='ORIGINAL_SOURCE_BYTES',status='UNKNOWN',reason=str(error)))
        else:context['conditions'].append(dict(id='ORIGINAL_SOURCE_BYTES',status='PASS',reason='原稿SHA-256／byte長度／檔案指紋與當次背景核實一致'))
    candidate.risk_context=context;return assess(candidate)


def search_result(candidates,*,scope_complete=False,unstarted=0,excluded=None):
    excluded=excluded or [];assessments=[assess(c) for c in candidates];safe=[r for r in assessments if r['formal_allowed']];drafts=[r for r in assessments if r['state'] in ('REVIEW_DRAFT','EVIDENCE_REQUIRED')]
    proven=bool(assessments) and scope_complete and not unstarted and not excluded and all(r['state']=='HARD_BLOCKED' and all(c['status']!='UNKNOWN' for c in r['conditions'] if c.get('required',True)) for r in assessments)
    state='SAFE_OPTIONS' if safe else 'REVIEW_OPTIONS' if drafts else 'PROVEN_BLOCKED_IN_DECLARED_SCOPE' if proven else 'INSUFFICIENT_OR_PARTIAL_SCOPE'
    return dict(state=state,safe=len(safe),drafts=len(drafts),checked=len(assessments),unstarted=unstarted,scope_complete=scope_complete,excluded=copy.deepcopy(excluded),proven_unsatisfiable_in_declared_scope=proven,global_unsolvable=False,all_possible_designs_checked=False,assessments=assessments,supplementation=False)


def transient_draft(candidate,reason):
    if not isinstance(reason,str) or not reason.strip() or len(reason)>2000:raise ValueError('需明列此次臨時草稿的核對理由')
    result=copy.deepcopy(candidate);result.risk_context=copy.deepcopy(candidate.risk_context)
    result.risk_context.setdefault('conditions',[]).append(dict(id='TRANSIENT_HUMAN_REVIEW',status='UNKNOWN',required=False,reason=reason))
    result.risk_context['transient_only']=True;return result


def assert_formal(candidate):
    result=assess(candidate)
    if not result['formal_allowed']:raise ValueError('正式輸出被分級風險Gate阻擋：'+result['label']+'；'+'；'.join(c['reason'] for c in result['conditions'] if c['status']!='PASS'))
    from .layout import generate
    snapshot=candidate.risk_context['input_snapshot']
    fresh=generate(candidate.template,**snapshot,generation=candidate.generation)
    if not fresh.valid or placement_digest(fresh)!=placement_digest(candidate):raise ValueError('正式輸出重核不通過，請重新排版：'+'；'.join(fresh.issues))
    return result


def placement_digest(candidate):
    return digest([asdict(item) for item in candidate.items])

def pin_inputs(candidate,people,companies,logos):
    snapshot=copy.deepcopy(dict(people=people,companies=companies,logos=logos))
    candidate.risk_context.update(engine_digest=engine_digest(),input_snapshot=snapshot,input_digest=digest(snapshot),template_snapshot_digest=digest(candidate.template.to_dict()),placement_snapshot_digest=placement_digest(candidate))

def freshness_conditions(candidate):
    context=candidate.risk_context;reasons=[]
    if context.get('engine_digest')!=engine_digest():reasons.append('排版引擎／語意與安全規則版本已變更')
    if 'input_snapshot' not in context:return [dict(id='SNAPSHOT_FRESHNESS',status='UNKNOWN',reason='缺當次輸入快照，需重新排版')]
    if digest(context['input_snapshot'])!=context.get('input_digest'):reasons.append('輸入快照已變更')
    if digest(candidate.template.to_dict())!=context.get('template_snapshot_digest'):reasons.append('模板內容已變更')
    if placement_digest(candidate)!=context.get('placement_snapshot_digest'):reasons.append('已量測的文字／框位／Logo已變更')
    if candidate.template.source_id and not context.get('original_source_proof'):reasons.append('來源模板缺原稿內容核實憑證，需先背景核對')
    if context.get('original_source_proof'):
        from .source_links import fingerprint
        from pathlib import Path
        proof=context['original_source_proof']
        try:unchanged=tuple(proof['stat'])==fingerprint(Path(proof['path']).stat())
        except (OSError,ValueError,KeyError):unchanged=False
        if not unchanged:reasons.append('已核實原稿指紋已變更／失聯')
    from .layout import layout_dependency
    if layout_dependency(candidate.template,context['input_snapshot']['logos'])!=candidate.dependency_stamp:reasons.append('字型／Logo／來源檔依賴已變更')
    return [dict(id='SNAPSHOT_FRESHNESS',status='UNKNOWN' if reasons else 'PASS',reason='；'.join(reasons) if reasons else '輸入／模板／實際框位／資產依賴仍符合本次快照')]

def valid_approved_base(base):
    # A bare flag, score, or user acceptance is never an approval receipt.
    return isinstance(base,dict) and base.get('state')=='published' and bool(base.get('id')) and isinstance(base.get('version'),int) and base.get('digest')==digest(base.get('payload')) and isinstance(base.get('payload'),dict) and base['payload'].get('state')=='published'


def verify_original_source(candidate,library,cache=None):
    if not candidate.template.source_id:return
    from .source_links import verify_source,fingerprint
    from pathlib import Path
    source=library.source(candidate.template.source_id);path=Path(source['current_path']).resolve();stamp=fingerprint(path.stat());identity=(str(path),source['hash'],stamp)
    proof=(cache or {}).get(identity)
    if proof is None:
        proof=verify_source(path,source['hash'])
        if proof.stat[2]!=source['byte_size']:raise ValueError('原稿byte長度與內容目錄不符')
        if cache is not None:cache[identity]=proof
    candidate.risk_context['original_source_proof']=dict(path=proof.path,hash=proof.hash,stat=list(proof.stat),link_revision=source['link_revision'])


@lru_cache(maxsize=128)
def _code_digest(name,mtime_ns,size):
    from .background import file_digest
    return file_digest(Path(__file__).parent/name)

def engine_digest():
    from PySide6.QtCore import qVersion
    names=('candidate_edit_dispatch.py','candidate_changes.py','candidate_edit.py','layout.py','render.py','candidate_risk.py','model.py','text_policy.py','text_metrics.py','font_catalog.py','font_evidence.py','fonts.py','logo_assets.py','background.py')
    versions={}
    for name in names:
        stamp=(Path(__file__).parent/name).stat();versions[name]=_code_digest(name,stamp.st_mtime_ns,stamp.st_size)
    return digest(dict(qt=qVersion(),code=versions,algorithm='EXPLICIT_FIXED_FONT_LOSSLESS_RULE_TEMPLATE'))

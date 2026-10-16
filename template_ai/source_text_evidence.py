"""Report observed derivative attributes without claiming private AI semantics."""
from __future__ import annotations


def text_evidence(source, elements, bounds, logo_members=()):
    parents={child:parent for parent in elements for child in parent}
    rows={}
    for node in elements:
        identity=node.get('id')
        if not identity or node.tag.rsplit('}',1)[-1] not in ('text','path','g'):continue
        chain=[];current=node
        while current is not None:
            chain.append(current);current=parents.get(current)
        observed={};effects=[]
        for ancestor in reversed(chain):
            attributes={k:ancestor.get(k) for k in ('font-family','font-size','font-style','font-weight','textLength','lengthAdjust','transform','filter','stroke') if ancestor.get(k) is not None}
            for declaration in ancestor.get('style','').split(';'):
                key,sep,value=declaration.partition(':')
                if sep and key.strip() in ('font-family','font-size','font-style','font-weight','filter','stroke'):
                    attributes[key.strip()]=value.strip()
            observed.update({k:v[:500] for k,v in attributes.items() if k not in ('transform','filter','stroke')})
            effects.extend(dict(object_id=ancestor.get('id'),attribute=k,value=v[:500]) for k,v in attributes.items() if k in ('transform','filter','stroke'))
        kind=node.tag.rsplit('}',1)[-1]
        rect=bounds.get(identity)
        rows[identity]=dict(svg_object_id=identity,
            classification='DERIVATIVE_TEXT' if kind=='text' else 'VECTOR_PATH_TEXT_ORIGIN_UNKNOWN' if kind=='path' else 'DERIVATIVE_GROUP',
            native_editability='UNKNOWN',true_outline='UNKNOWN',native_effect_type='UNKNOWN',
            original_font_identity='UNIDENTIFIED',font_declarations=observed,observed_effect_attributes=effects,
            source_font_size_pt=None,source_font_width_mm=None,
            derivative_bounds_mm=vars(rect) if rect else None,
            logo_protected=id(node) in logo_members,
            evidence_channel='INKSCAPE_SVG_DERIVATIVE',confidence='DIRECT_ATTRIBUTE_ONLY_NOT_NATIVE_AI',
            source_hash=source['hash'],derivative_hash=source.get('file_hashes',{}).get('svg'),
            stylesheet_unresolved=any(e.tag.rsplit('}',1)[-1]=='style' for e in elements))
    return rows


def identity_match(reference, candidate):
    """A name or shape never establishes the source face's binary identity."""
    common=dict(editable_source='UNKNOWN',original_ai_font_relation='UNVERIFIED')
    if reference.get('font_sha256') and reference['font_sha256']==candidate.get('hash'):
        from .font_evidence import inspect_font
        from .background import file_digest
        try:
            if not reference.get('font_path') or not candidate.get('path'):raise ValueError('只有宣告雜湊，缺少實際字型檔案')
            source=inspect_font(reference['font_path']);selected=inspect_font(candidate['path'])
            if source['hash']!=reference['font_sha256'] or selected['hash']!=candidate['hash']:raise ValueError('實際字型檔已變更，不能沿用宣告雜湊')
            left=reference.get('face_index',0 if len(source['faces'])==1 else None)
            right=candidate.get('font_evidence',{}).get('index',0 if len(selected['faces'])==1 else None)
            if type(left) is not int or type(right) is not int or not 0<=left<len(source['faces']) or not 0<=right<len(selected['faces']) or left!=right:raise ValueError('同一集合檔不代表相同字面，需核對確切字面索引')
            if file_digest(reference['font_path'])!=source['hash'] or file_digest(candidate['path'])!=selected['hash']:raise ValueError('字型在核對期間變更')
            return dict(state='PROVEN_SAME_BYTES',basis='ACTUAL_CURRENT_FILE_SHA256_AND_FACE',face_index=left,font_sha256=source['hash'],**common)
        except (ValueError,OSError,TypeError,KeyError) as error:
            return dict(state='UNIDENTIFIED',basis='ACTUAL_FILE_PROOF_FAILED',reason=str(error),**common)
    names={str(candidate.get(k) or '').casefold() for k in ('family','postscript_name','unique_name')}-{''}
    refs={str(reference.get(k) or '').casefold() for k in ('family','postscript_name','unique_name')}-{''}
    return dict(state='POSSIBLE_ALIAS' if names & refs else 'UNIDENTIFIED',
                basis='NAME_ONLY_REQUIRES_REVIEW' if names & refs else 'NO_IDENTITY_EVIDENCE',**common)

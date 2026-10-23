"""Report observed derivative attributes without claiming private AI semantics."""
from __future__ import annotations


FONT_ATTRIBUTES=('font-family','font-size','font-style','font-weight','font-stretch',
                 'letter-spacing','word-spacing','textLength','lengthAdjust')
EFFECT_ATTRIBUTES=('transform','filter','stroke','stroke-width','paint-order','mask','clip-path','opacity')


def text_evidence(source, elements, bounds, logo_members=(), *, svg_channel='svg'):
    """Bound literal observations; never resolve CSS or native Illustrator semantics."""
    if svg_channel not in ('svg','semantic_svg'):
        raise ValueError('文字觀察缺少明確衍生管道')
    elements=list(elements)
    parents={child:parent for parent in elements[:4000] for child in parent}
    stylesheet=any(e.tag.rsplit('}',1)[-1]=='style' for e in elements[:4000])
    rows={};remaining=250_000;work_remaining=50_000
    for node in elements[:4000]:
        identity=node.get('id');kind=node.tag.rsplit('}',1)[-1]
        if not identity or kind not in ('text','path','g'):continue
        reasons=[];chain=[];current=node;seen=set()
        while current is not None and len(chain)<64 and id(current) not in seen:
            seen.add(id(current));chain.append(current);current=parents.get(current)
        if current is not None:reasons.append('ANCESTRY_BUDGET_OR_CYCLE')
        if len(elements)>4000:reasons.append('NODE_BUDGET')
        observed={};effects=[]
        for ancestor in reversed(chain):
            if work_remaining<=0:reasons.append('ATTRIBUTE_WORK_BUDGET');break
            work_remaining-=1
            attributes={k:ancestor.get(k) for k in FONT_ATTRIBUTES+EFFECT_ATTRIBUTES if ancestor.get(k) is not None}
            style=ancestor.get('style','')
            if len(style)>8192:reasons.append('STYLE_BUDGET')
            for declaration in style[:8192].split(';'):
                key,sep,value=declaration.partition(':');key=key.strip()
                if sep and key in FONT_ATTRIBUTES+EFFECT_ATTRIBUTES:attributes[key]=value.strip()
            for key,value in attributes.items():
                if len(value)>500:reasons.append('VALUE_BUDGET')
                value=value[:500]
                if remaining<len(value):reasons.append('TOTAL_CHARACTER_BUDGET');continue
                remaining-=len(value)
                if key in FONT_ATTRIBUTES:observed[key]=value
                elif len(effects)<32:effects.append(dict(object_id=ancestor.get('id'),attribute=key,value=value))
                else:reasons.append('EFFECT_BUDGET')
        rect=bounds.get(identity)
        if identity in rows:reasons.append('DUPLICATE_OBJECT_ID')
        rows[identity]=dict(svg_object_id=identity,
            classification='DERIVATIVE_TEXT' if kind=='text' else 'VECTOR_PATH_TEXT_ORIGIN_UNKNOWN' if kind=='path' else 'DERIVATIVE_GROUP',
            native_editability='UNKNOWN',true_outline='UNKNOWN',native_effect_type='UNKNOWN',
            original_font_identity='UNIDENTIFIED',font_declarations=observed,observed_effect_attributes=effects,
            source_font_size_pt=None,source_font_width_mm=None,
            derivative_bounds_mm=vars(rect) if rect else None,
            logo_protected=id(node) in logo_members,
            evidence_channel='INKSCAPE_SVG_DERIVATIVE',confidence='DIRECT_ATTRIBUTE_ONLY_NOT_NATIVE_AI',
            source_hash=source['hash'],derivative_channel=svg_channel,derivative_hash=source.get('file_hashes',{}).get(svg_channel),
            stylesheet_unresolved=stylesheet,literal_evidence_complete=not reasons,
            evidence_limits=sorted(set(reasons)),native_provider='UNAVAILABLE_NOT_PARSED')
    return rows


def evidence_summary(proof):
    """Plain text for the original diagnostic pane; no invented measurements."""
    if not proof:return '目前無來源物件證據；原生可編輯性、字型、轉曲及字級均未知。'
    labels={'DERIVATIVE_TEXT':'衍生向量文字','VECTOR_PATH_TEXT_ORIGIN_UNKNOWN':'向量路徑；文字來源未知','DERIVATIVE_GROUP':'衍生物件群組'}
    declarations=proof.get('font_declarations',{})
    lines=['來源物件：'+str(proof.get('svg_object_id') or '未知'),
        '可取得管道：Inkscape 衍生 SVG；Illustrator 原生私有資料尚未解析。',
        '觀察類型：'+labels.get(proof.get('classification'),'來源不足，類型未知'),
        '原生可編輯性／真正轉曲／原生效果：未知；外觀效果不證明轉曲或可編輯。',
        '原稿實體字級／字寬：未知；下列文字屬性為衍生宣告值，不作原稿量測。']
    lines.extend(key+'：'+str(value) for key,value in declarations.items())
    effects=proof.get('observed_effect_attributes',[])
    if effects:lines.append('觀察到的外觀／變形：'+ '; '.join(str(e.get('object_id') or '匿名')+'／'+str(e.get('attribute'))+'='+str(e.get('value')) for e in effects))
    rect=proof.get('derivative_bounds_mm')
    if rect:lines.append('衍生幾何包圍框（mm）：'+str(rect))
    if proof.get('stylesheet_unresolved'):lines.append('含未解析樣式表；不能保證宣告值等於最終外觀。')
    if not proof.get('literal_evidence_complete',False):lines.append('證據不完整／超出資源預算；需人工核對，不能當作完整來源證明。')
    if proof.get('logo_protected'):lines.append('複合 Logo 受保護，不能當一般文字框替換字型。')
    return '\n'.join(lines)


def identity_match(reference, candidate):
    """A name or shape never establishes the source face's binary identity."""
    common=dict(editable_source='UNKNOWN',original_ai_font_relation='UNVERIFIED')
    if reference.get('font_sha256') and candidate.get('hash'):
        from .font_evidence import inspect_font,face_bytes
        from .background import file_digest
        import hashlib
        try:
            if not reference.get('font_path') or not candidate.get('path'):raise ValueError('只有宣告雜湊，缺少實際字型檔案')
            source=inspect_font(reference['font_path']);selected=inspect_font(candidate['path'])
            if source['hash']!=reference['font_sha256'] or selected['hash']!=candidate['hash']:raise ValueError('實際字型檔已變更，不能沿用宣告雜湊')
            left=reference.get('face_index',0 if len(source['faces'])==1 else None)
            right=0 if len(selected['faces'])==1 else candidate.get('font_evidence',{}).get('index')
            if type(left) is not int or type(right) is not int or not 0<=left<len(source['faces']) or not 0<=right<len(selected['faces']):raise ValueError('需核對存在的來源及目前實體字面索引')
            same_file=source['hash']==selected['hash']
            same_extracted=not same_file and len(selected['faces'])==1 and hashlib.sha256(face_bytes(reference['font_path'],left)).hexdigest()==selected['hash']
            if file_digest(reference['font_path'])!=source['hash'] or file_digest(candidate['path'])!=selected['hash']:raise ValueError('字型在核對期間變更')
            if same_file and left!=right:raise ValueError('同一集合檔不代表相同字面')
            if same_file or same_extracted:return dict(state='PROVEN_SAME_BYTES' if same_file else 'PROVEN_SAME_EXTRACTED_FACE',basis='ACTUAL_CURRENT_FILE_SHA256_AND_FACE' if same_file else 'ACTUAL_SOURCE_FACE_BYTES_SHA256',source_face_index=left,physical_face_index=right,font_sha256=source['hash'],**common)
        except (ValueError,OSError,TypeError,KeyError) as error:
            return dict(state='UNIDENTIFIED',basis='ACTUAL_FILE_PROOF_FAILED',reason=str(error),**common)
    names={str(candidate.get(k) or '').casefold() for k in ('family','postscript_name','unique_name')}-{''}
    refs={str(reference.get(k) or '').casefold() for k in ('family','postscript_name','unique_name')}-{''}
    return dict(state='POSSIBLE_ALIAS' if names & refs else 'UNIDENTIFIED',
                basis='NAME_ONLY_REQUIRES_REVIEW' if names & refs else 'NO_IDENTITY_EVIDENCE',**common)

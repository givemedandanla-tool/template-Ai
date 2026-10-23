"""Derived indexes over existing IDs; never infer a native Illustrator mapping."""
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET
from .model import KINDS, company_ports
from .object_tools import slots_of

MAX_XML_BYTES = 2 * 1024 * 1024
MAX_NODES = 2000
MAX_DEPTH = 40


def semantic_index(payload):
    slots = sorted(slots_of(payload), key=lambda s: (s.owner, s.kind, s.index, s.id))
    by_owner = {}
    for s in slots:
        by_owner.setdefault(s.owner, []).append(s)
    links = payload.get('company_bindings', {})
    if not isinstance(links, dict):
        links = {}
    people = sorted(set(o for o in by_owner if o.startswith('p')) | set(p for p in links if p.startswith('p')))
    def leaf(s):
        return {'label': f'{KINDS.get(s.kind,s.kind)} {s.index+1} · {s.id}', 'ids': [s.id], 'children': []}
    roots = []
    for p in people:
        children = [leaf(s) for s in by_owner.get(p, [])]
        bound=company_ports(links.get(p))
        for c in bound:
            if c in by_owner and c.startswith('c'):
                children.append({'label': f'引用公司 {c}（同一資產／共享）', 'ids': [s.id for s in by_owner[c]], 'children': [leaf(s) for s in by_owner[c]]})
        if not bound:
            children.append({'label': '無公司（明確確認）' if p in links and isinstance(links[p],list) and not links[p] else '公司關聯 UNKNOWN／未確認', 'ids': [], 'children': []})
        roots.append({'label': f'人物 ROOT {p}', 'ids': sorted({i for n in children for i in n['ids']}), 'children': children})
    for owner in sorted(o for o in by_owner if not o.startswith('p')):
        refs = sorted(p for p, c in links.items() if owner in company_ports(c))
        roots.append({'label': f'公司實體 {owner} · 共享引用 '+(', '.join(refs) or 'UNKNOWN'), 'ids': [s.id for s in by_owner[owner]], 'children': [leaf(s) for s in by_owner[owner]]})
    return roots


def matching_ids(payload, query='', state='ALL', structure=None):
    slots = slots_of(payload)
    links = payload.get('company_bindings', {})
    tokens = query.casefold().split()
    result = [];source_words={}
    def index(node):
        for identity in node.get('ids',[]):source_words[identity]=source_words.get(identity,'')+' '+node.get('label','')
        for child in node.get('children',[]):index(child)
    for node in (structure or {}).get('nodes',[]):index(node)
    for s in sorted(slots, key=lambda s: (s.owner, s.kind, s.index, s.id)):
        shared = s.owner.startswith('c') and sum(s.owner in company_ports(c) for c in links.values()) > 1
        problem = not s.rect.inside(payload.get('width_mm',payload.get('work_width',0)),payload.get('height_mm',payload.get('work_height',0)))
        words = ' '.join([s.id,s.owner,s.kind,KINDS.get(s.kind,s.kind),s.font,s.font_style, 'locked 鎖定' if s.locked else 'unlocked 未鎖定', 'shared 共享' if shared else '', 'problem 問題' if problem else '', source_words.get(s.id,'來源對應 UNKNOWN')]).casefold()
        if state == 'LOCKED' and not s.locked or state == 'SHARED' and not shared or state == 'PROBLEM' and not problem:
            continue
        if all(t in words for t in tokens):
            result.append(s.id)
    return result


def source_structure(source,payload=None):
    """Read the verified derivative only. No native/layer or slot association is invented."""
    unknown = {'status':'UNKNOWN','provenance':'衍生 SVG／非 Illustrator 原生圖層','mapping':'UNKNOWN','nodes':[]}
    if not source or not source.get('svg'):
        return {**unknown,'reason':'沒有可驗證 SVG 結構；既有語意物件仍可搜尋'}
    try:
        channel=(payload or {}).get('analysis_evidence',{}).get('vector_channel','svg')
        if channel not in ('svg','semantic_svg') or not source.get(channel):
            raise ValueError('缺少明確且可讀的衍生SVG管道')
        expected=source.get('file_hashes',{}).get(channel)
        original=Path(source.get('current_path',source['original_path']))
        if not original.is_file() or original.is_symlink() or original.stat().st_size > 50*1024*1024:
            raise ValueError('來源失聯／超出預算')
        from .source_links import verify_source,check_verified
        proof=verify_source(original,source['hash'])
        path=Path(source[channel])
        if path.is_symlink() or path.stat().st_size>MAX_XML_BYTES:
            raise ValueError('SVG 超出結構預算／符號連結')
        with path.open('rb') as stream:data=stream.read(MAX_XML_BYTES+1)
        if len(data)>MAX_XML_BYTES:raise ValueError('SVG 超出結構預算')
        if hashlib.sha256(data).hexdigest()!=expected:
            raise ValueError('SVG 快取內容已異動或沒有 hash 證據')
        if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
            raise ValueError('不接受 DTD／entity 的結構')
        root=ET.fromstring(data); count=0; seen=set()
        if (payload or {}).get('analysis_evidence',{}).get('query_ids_version'):
            from .source_derivative import assign_query_ids,QUERY_IDS_VERSION
            if payload['analysis_evidence']['query_ids_version']!=QUERY_IDS_VERSION:
                raise ValueError('不支援的衍生SVG查詢ID版本')
            assign_query_ids(root)
        def visit(e,depth,address):
            nonlocal count
            count+=1
            if count>MAX_NODES or depth>MAX_DEPTH:
                raise ValueError('SVG 節點／深度超出結構預算')
            identity=e.get('id','')
            if identity and identity in seen:raise ValueError('SVG ID 不唯一，不能唯一映射')
            if identity:seen.add(identity)
            label=e.get('{http://www.inkscape.org/namespaces/inkscape}label','')
            return {'label':f'{e.tag.rsplit("}",1)[-1]} · {label or identity or address} · 對應 UNKNOWN','address':address,'source_id':identity,'ids':[],'children':[visit(c,depth+1,address+'/'+str(i)) for i,c in enumerate(e)]}
        nodes=[visit(root,0,'0')]
        mapping=(payload or {}).get('analysis_evidence',{}).get('slot_source_map',{});slot_ids={s['id'] for s in (payload or {}).get('slots',[])};linked=[]
        if isinstance(mapping,dict) and len(mapping)<=200:
            def link(node):
                node['ids']=sorted(sid for sid,reference in mapping.items() if sid in slot_ids and isinstance(reference,dict) and reference.get('source_hash')==source['hash'] and reference.get('svg_channel','svg')==channel and reference.get('svg_hash')==expected and reference.get('svg_object_id') and reference['svg_object_id']==node['source_id'])
                if node['ids']:node['label']=node['label'].replace('對應 UNKNOWN','衍生SVG對應；原生Illustrator UNKNOWN');linked.extend(node['ids'])
                for child in node['children']:link(child)
            for node in nodes:link(node)
        with path.open('rb') as stream:after_data=stream.read(MAX_XML_BYTES+1)
        if len(after_data)>MAX_XML_BYTES or hashlib.sha256(after_data).hexdigest()!=expected:
            raise ValueError('結構讀取期間檔案異動')
        check_verified(proof,source['hash'])
        return {**unknown,'status':'VERIFIED_DERIVATIVE','mapping':'VERIFIED_SVG_LINKS' if linked else 'UNKNOWN','reason':'只對已保存且來源／快取hash一致的衍生SVG連結；其餘slot及原生Illustrator對應UNKNOWN','nodes':nodes,'count':count,'linked_slot_ids':sorted(set(linked))}
    except (OSError,ValueError,ET.ParseError,KeyError,TypeError) as error:
        return {**unknown,'status':'BLOCKED','reason':str(error)}

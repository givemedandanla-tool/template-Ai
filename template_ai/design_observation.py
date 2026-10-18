"""Bounded, source-scoped observations. An annotation is never a font measurement.

This layer records evidence; it neither admits training samples nor makes templates.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import re

SCHEMA_VERSION = 1
EXTRACTOR_VERSION = 'design-observation-1'
MAX_SLOTS = 512  # Processing budget, not learned card/person capacity.
MAX_NODES = 2000
MAX_EDGES = 4000
UNITS = {'mm', 'pt', 'ratio', 'count'}
STATUSES = {'UNKNOWN', 'ANNOTATED', 'OBSERVED', 'DERIVED'}
NODE_KINDS = {'WORK_CONTAINER', 'PERSON_GROUP', 'COMPANY_GROUP', 'UNKNOWN_OWNER',
              'FIELD_ROLE', 'TEXT', 'ANNOTATION', 'LOGO', 'UNKNOWN'}
EDGE_KINDS = {'contains', 'owned_by', 'observes_role', 'person_company',
              'derived_relative_geometry'}


def canonical_digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


@dataclass(frozen=True)
class ObservedScalar:
    value: float | None
    unit: str
    status: str
    basis: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self):
        if (not isinstance(self.unit, str) or self.unit not in UNITS
                or not isinstance(self.status, str) or self.status not in STATUSES
                or not isinstance(self.basis, str) or not self.basis
                or not isinstance(self.evidence_refs, tuple)):
            raise ValueError('觀察量需明確單位、狀態與依據')
        if self.status == 'UNKNOWN':
            if self.value is not None:
                raise ValueError('UNKNOWN不能帶入預設數值')
        elif not _number(self.value) or not self.evidence_refs:
            raise ValueError('已知觀察量需有限數值與來源引用')
        if any(not isinstance(ref, str) or not ref for ref in self.evidence_refs):
            raise ValueError('觀察引用不合法')

    def to_dict(self):
        return dict(value=self.value, unit=self.unit, status=self.status,
                    basis=self.basis, evidence_refs=list(self.evidence_refs))


def unknown(unit, reason='NO_SOURCE_EVIDENCE', refs=()):
    return ObservedScalar(None, unit, 'UNKNOWN', reason, tuple(refs)).to_dict()


def effective_point_size(source_pt: ObservedScalar, physical_transform):
    """Similarity transforms preserve a scalar point size; anisotropy does not.

    Matrix is (a,b,c,d,tx,ty), already expressed in physical source coordinates.
    Declared template pt is ANNOTATED and cannot become an observed source pt.
    """
    if source_pt.unit != 'pt':
        raise ValueError('來源字級需pt單位')
    if (not isinstance(physical_transform, (tuple, list)) or len(physical_transform) != 6
            or not all(_number(x) for x in physical_transform)):
        raise ValueError('物理仿射矩陣需六個有限實數')
    if source_pt.status != 'OBSERVED' or source_pt.value <= 0:
        return ObservedScalar(None, 'pt', 'UNKNOWN', 'SOURCE_PT_NOT_OBSERVED')
    a, b, c, d, _, _ = physical_transform
    sx, sy = math.hypot(a, b), math.hypot(c, d)
    if (sx == 0 or sy == 0 or not math.isclose(sx, sy, rel_tol=1e-9)
            or abs(a*c+b*d) > 1e-9*sx*sy):
        return ObservedScalar(None, 'pt', 'UNKNOWN', 'NON_SIMILARITY_TRANSFORM')
    return ObservedScalar(source_pt.value*sx, 'pt', 'DERIVED',
                          'OBSERVED_PT_TIMES_UNIFORM_PHYSICAL_SCALE', source_pt.evidence_refs)


@dataclass(frozen=True)
class ObservationNode:
    id: str
    kind: str
    properties: dict

    def __post_init__(self):
        if (not isinstance(self.id, str) or not self.id or not isinstance(self.kind, str)
                or self.kind not in NODE_KINDS or not isinstance(self.properties, dict)):
            raise ValueError('觀察節點型別不合法')

    def to_dict(self):
        return dict(id=self.id, kind=self.kind, properties=deepcopy(self.properties))


@dataclass(frozen=True)
class ObservationEdge:
    source: str
    target: str
    kind: str
    properties: dict

    def __post_init__(self):
        if (not isinstance(self.source, str) or not self.source
                or not isinstance(self.target, str) or not self.target
                or not isinstance(self.kind, str) or self.kind not in EDGE_KINDS
                or not isinstance(self.properties, dict)):
            raise ValueError('觀察關係型別不合法')

    def to_dict(self):
        return dict(source=self.source, target=self.target, kind=self.kind,
                    properties=deepcopy(self.properties))


@dataclass(frozen=True)
class DesignObservation:
    context: dict
    nodes: tuple[ObservationNode, ...]
    edges: tuple[ObservationEdge, ...]

    def to_dict(self):
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)) or len(ids) > MAX_NODES or len(self.edges) > MAX_EDGES:
            raise ValueError('觀察圖ID重複或超過處理預算，未截斷')
        known = set(ids)
        if any(e.source not in known or e.target not in known for e in self.edges):
            raise ValueError('觀察關係引用不存在的節點')
        result = deepcopy(self.context)
        result.update(nodes=[n.to_dict() for n in sorted(self.nodes, key=lambda n: n.id)],
                      edges=[e.to_dict() for e in sorted(self.edges,
                            key=lambda e: (e.source, e.kind, e.target))])
        json.dumps(result, allow_nan=False)  # Reject non-finite/nonscalar payloads before storage.
        return result


def _rect(value):
    if (not isinstance(value, dict) or set(value) != {'x', 'y', 'w', 'h'}
            or not all(_number(v) for v in value.values()) or value['w'] <= 0 or value['h'] <= 0):
        raise ValueError('觀察範圍需有限座標及正寬高')
    return dict(value)


def _node_id(work_id, kind, local_id):
    return 'do-'+canonical_digest([work_id, kind, local_id])[:40]


def _typography(ref):
    fields = {'source_pt': 'pt', 'baseline': 'mm', 'shaped_advance': 'mm',
              'horizontal_scale': 'ratio', 'tracking': 'mm', 'grapheme_count': 'count'}
    result = {k: unknown(unit, refs=(ref,)) for k, unit in fields.items()}
    result.update(font_asset_ref=None, source_font_status='UNKNOWN',
                  glyph_runs=dict(status='UNKNOWN', value=None, basis='NOT_EXTRACTED'),
                  text_run_segmentation='UNKNOWN', distribution_mode='UNKNOWN', alignment='UNKNOWN')
    return result


def build_observation(work, source, facts, pins, facts_state, noise_signature, noise_rows):
    """Project current annotations into a graph without copying source text/defaults.

    Old facts remain in history; facts pinned to another work revision are not
    relinked to current fields. Group edges are semantic, not collision obstacles.
    """
    from .model import Rect, company_ports

    payload = work['payload']
    crop = _rect(payload['crop'])
    if not Rect(**crop).inside(source['width_mm'], source['height_mm']):
        raise ValueError('作品範圍超出來源頁')
    width, height = payload['work_width'], payload['work_height']
    if not all(_number(v) and v > 0 for v in (width, height)):
        raise ValueError('作品觀察需有限的毫米尺寸')
    slots = payload['slots']
    if not isinstance(slots, list) or len(slots) > MAX_SLOTS:
        raise ValueError('單作品觀察超過512標記框處理預算，未截斷')
    slot_ids = [s.get('id') for s in slots]
    if (any(not isinstance(s, str) or not s or len(s) > 128 for s in slot_ids)
            or len(slot_ids) != len(set(slot_ids))):
        raise ValueError('觀察需要唯一且非空的stable slot IDs')
    if len(facts['observations']) > 200:
        raise ValueError('來源觀察超過200項預算，未截斷')

    work_id = work['id']
    root = _node_id(work_id, 'work', work_id)
    ref = 'WORK:'+work_id+':'+str(work['revision'])
    nodes = [ObservationNode(root, 'WORK_CONTAINER', dict(
        frame_mm=dict(x=0, y=0, w=width, h=height), frame_basis='WORK_DIMENSION_ANNOTATION',
        available_space='UNKNOWN', baseline=unknown('mm', refs=(ref,))))]
    edges = []
    owners, role_ids, by_owner = {}, {}, {}

    def owner_node(owner):
        if not isinstance(owner, str) or not owner or len(owner) > 128:
            raise ValueError('人物／公司標記需有界穩定ID')
        if owner not in owners:
            if len(nodes) >= MAX_NODES:
                raise ValueError('觀察節點超過預算，未截斷')
            kind = ('PERSON_GROUP' if re.fullmatch(r'p[1-9][0-9]*', owner) else
                    'COMPANY_GROUP' if re.fullmatch(r'c[1-9][0-9]*', owner) else 'UNKNOWN_OWNER')
            nid = _node_id(work_id, 'owner', owner)
            owners[owner] = (nid, kind)
            nodes.append(ObservationNode(nid, kind, dict(local_owner_ref=owner,
                evidence_status='ANNOTATED', cross_work_person_identity='UNKNOWN',
                container_bounds='UNKNOWN', collision_obstacle=False)))
            edges.append(ObservationEdge(root, nid, 'contains', dict(scope='SEMANTIC_ANNOTATION')))
        return owners[owner][0]

    for slot in slots:
        sid = slot['id']; nid = _node_id(work_id, 'slot', sid)
        role_ids[sid] = nid
        owner = slot.get('owner') or 'UNASSIGNED'
        owner_id = owner_node(owner)
        try:
            frame = _rect(slot.get('rect'))
            anchors = dict(left=frame['x']/width, top=frame['y']/height,
                           right=(frame['x']+frame['w'])/width,
                           bottom=(frame['y']+frame['h'])/height)
        except ValueError:
            frame, anchors = None, None  # Preserve a repairable bad annotation, not fake geometry.
        nodes.append(ObservationNode(nid, 'FIELD_ROLE', dict(
            slot_ref=sid, role=slot.get('kind'), owner_ref=owner, frame_mm=frame,
            frame_status='ANNOTATED' if frame else 'UNKNOWN', normalized_anchors=anchors,
            anchors_unit='ratio', anchors_basis='DERIVED_FROM_ANNOTATED_FRAME',
            typography=_typography(ref), source_container='UNKNOWN',
            design_parameters_ref=dict(work_id=work_id, slot_id=sid),
            label_binding='UNKNOWN', icon_binding='UNKNOWN')))
        edges.extend([ObservationEdge(owner_id, nid, 'contains', dict(scope='SEMANTIC_ANNOTATION')),
                      ObservationEdge(nid, owner_id, 'owned_by', dict(status='ANNOTATED'))])
        if frame:
            by_owner.setdefault(owner, []).append((nid, frame))

    bindings = payload.get('company_bindings', {})
    if not isinstance(bindings, dict) or len(bindings) > MAX_SLOTS:
        raise ValueError('公司關聯不合法或超過處理預算')
    for person, companies in sorted(bindings.items()):
        ports = company_ports(companies)
        if len(ports) > MAX_SLOTS or len(edges)+len(ports) > MAX_EDGES:
            raise ValueError('公司關聯超過觀察處理預算，未截斷')
        for company in ports:
            edges.append(ObservationEdge(owner_node(person), owner_node(company),
                         'person_company', dict(status='ANNOTATED', source_ref=ref)))

    for group in by_owner.values():
        ordered = sorted(group, key=lambda item: (item[1]['y'], item[1]['x'], item[0]))
        for (left_id, left), (right_id, right) in zip(ordered, ordered[1:]):
            edges.append(ObservationEdge(left_id, right_id, 'derived_relative_geometry', dict(
                delta_x=ObservedScalar(right['x']-left['x'], 'mm', 'DERIVED',
                                      'ANNOTATED_FRAME_DELTA', (ref,)).to_dict(),
                delta_y=ObservedScalar(right['y']-left['y'], 'mm', 'DERIVED',
                                      'ANNOTATED_FRAME_DELTA', (ref,)).to_dict(),
                reading_order='UNKNOWN', baseline_alignment='UNKNOWN')))

    applicable = facts['pins'] == pins
    observations = facts['observations'] if applicable else []
    confirmed = set((facts.get('confirmation') or {}).get('observation_ids', [])) if facts_state == 'CONFIRMED' else set()
    noise = {r['observation_id']: r for r in noise_rows}
    seen = set()
    for observation in observations:
        oid = observation['id']
        if oid in seen:
            raise ValueError('來源觀察ID重複')
        seen.add(oid)
        nid = _node_id(work_id, 'fact', oid)
        kind = {'TEXT': 'TEXT', 'ANNOTATION': 'ANNOTATION', 'LOGO_PART': 'LOGO'}.get(observation['object_type'], 'UNKNOWN')
        sid = observation.get('slot_id')
        if sid is not None and sid not in role_ids:
            raise ValueError('當前觀察連結的標記框不存在')
        region = _rect(observation['region'])
        if sid is not None and not Rect(region['x']-crop['x'], region['y']-crop['y'],
                                       region['w'], region['h']).inside(crop['w'], crop['h']):
            raise ValueError('欄位來源觀察跨出本作品範圍，不能連結到其他作品')
        item_ref = 'FACTS:'+work_id+':'+str(facts['revision'])+':'+oid
        decision = noise.get(oid, {})
        nodes.append(ObservationNode(nid, kind, dict(
            observation_ref=oid, facts_revision=facts['revision'],
            text_ref=dict(kind='FACTS', id=work_id, revision=facts['revision'], observation_id=oid),
            classification=observation['classification'], source_region_mm=region,
            geometry_status='ANNOTATED', native_mapping='UNKNOWN',
            evidence_status='USER_CONFIRMED' if oid in confirmed else 'PENDING',
            noise_state=decision.get('state', 'UNKNOWN'),
            noise_rule_refs=[dict(id=r['id'], revision=r['revision']) for r in decision.get('rule_matches', [])],
            typography=_typography(item_ref) if kind == 'TEXT' else None)))
        edges.append(ObservationEdge(root, nid, 'contains', dict(scope='ANNOTATED_SOURCE_REGION')))
        if sid is not None:
            edges.append(ObservationEdge(nid, role_ids[sid], 'observes_role', dict(
                status='USER_CONFIRMED' if oid in confirmed else 'PENDING')))

    signature = canonical_digest(dict(extractor=EXTRACTOR_VERSION, pins=pins,
        facts_revision=facts['revision'], facts_digest=canonical_digest(facts),
        noise_signature=noise_signature, source_cache=source['file_hashes']))
    context = dict(schema_version=SCHEMA_VERSION, extractor_version=EXTRACTOR_VERSION,
        input_signature=signature, pins=deepcopy(pins),
        source_cache=deepcopy(source['file_hashes']), noise_signature=noise_signature,
        facts_ref=dict(id=work_id, revision=facts['revision'], digest=canonical_digest(facts),
                       applicability='CURRENT' if applicable else 'STALE'),
        coordinate_systems=dict(source_unit='mm', work_unit='mm', source_crop=deepcopy(crop),
            work_size=dict(width_mm=width, height_mm=height),
            source_to_work=[width/crop['w'], 0, 0, height/crop['h'],
                            -crop['x']*width/crop['w'], -crop['y']*height/crop['h']],
            basis='ANNOTATED_CROP_TO_NOMINAL_WORK_SIZE_NOT_FONT_TRANSFORM'),
        qualification=dict(facts_state=facts_state, visual_confirmed=payload.get('visual_confirmed') is True,
                           training_admission='NOT_EVALUATED', purpose='OBSERVATION_ONLY'),
        lineage=dict(source_content_group=source['hash'], source_id=source['id'],
                     work_id=work_id, page=source.get('page', 1),
                     cross_work_person_and_family_correspondence='UNKNOWN'),
        counts=dict(annotated_person_groups=sum(k == 'PERSON_GROUP' for _, k in owners.values()),
                    field_roles=len(slots), source_regions=len(observations),
                    confirmed_source_regions=len(confirmed & seen),
                    stale_regions_not_relinked=0 if applicable else len(facts['observations']),
                    logical_data_count=unknown('count'), rendered_instance_count=unknown('count')))
    return DesignObservation(context, tuple(nodes), tuple(edges)).to_dict()

"""Functional style keys exclude review provenance, which remains on observations.

Only identity comparisons use these keys. Execution still receives the complete
source asset and permission records and must pass their current validity checks.
"""
from copy import deepcopy

_PROVENANCE = frozenset({
    'evidence_refs', 'actor', 'reason', 'basis', 'reviewer', 'reviewed_at',
    'created_at', 'updated_at', 'source_ref', 'source_refs', 'example_id',
    'path', 'original_name', 'usage_rights', 'font_evidence',
})


def functional(value):
    if isinstance(value, dict):
        return {key: functional(item) for key, item in sorted(value.items())
                if key not in _PROVENANCE}
    if isinstance(value, (list, tuple)):
        return [functional(item) for item in value]
    return deepcopy(value)


def font_identity(asset):
    if not isinstance(asset, dict):
        return asset
    # Imported face bytes already have their own hash. Names alone never prove
    # source font identity; the explicit source binding remains mandatory.
    return {key: functional(asset[key]) for key in
            ('hash', 'sha256', 'face_index', 'families', 'styles', 'axes', 'selected_axes')
            if key in asset}


def style_identity(condition):
    value = functional(condition)
    if isinstance(condition, dict) and 'font_asset' in condition:
        value['font_asset'] = font_identity(condition['font_asset'])
    return value

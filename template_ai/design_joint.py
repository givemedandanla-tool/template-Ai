"""TRAIN-only, source-conditioned joint typography/container regression.

Ridge predicts whole vectors inside observed input support. Font/alignment/label
modes stay separate; rare and missing styles remain source configurations. Fit
residuals are diagnostics, never heldout quality or production qualification.
"""
from collections import defaultdict
from copy import deepcopy
import math

from .training_store import digest
from .design_style import style_identity

VERSION = 'joint-ridge-2-functional-lineage-balanced'
INPUTS = ('width_mm', 'height_mm', 'natural_advance_per_pt_mm')
OUTPUTS = ('source_pt', 'horizontal_scale', 'tracking_mm', 'frame_width_mm', 'frame_height_mm')


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def fit_joint(samples):
    import numpy as np
    from sklearn.linear_model import Ridge
    from sklearn.mixture import GaussianMixture
    groups = defaultdict(list)
    for row in sorted(samples, key=lambda item: (item['lineage_group'], item['example_id'])):
        vector = row['joint']; font = row.get('source_font_ref')
        values = [vector.get(key) for key in OUTPUTS]
        advance = vector.get('shaped_advance_mm')
        if not font or not all(_finite(value) for value in values) or not _finite(advance):
            continue
        if values[0] <= 0 or advance <= 0:
            continue
        x = list(row['dimensions_mm']) + [advance / values[0]]
        if not all(_finite(value) and value > 0 for value in x):
            continue
        condition = dict(font_asset=font, align=row['align'], distribution=row['distribution'],
                         label_binding=row['label_binding'], text_flow=row.get('source_text_flow'),
                         word_spacing_mm=vector.get('word_spacing_mm'))
        groups[digest(style_identity(condition))].append((row, x, values, condition))
    modes = []
    for condition_id, rows in sorted(groups.items()):
        all_rows = rows
        # Exact aliases carry provenance but cannot multiply a lineage's density.
        unique = {}
        for row in rows:
            unique.setdefault(digest([row[0]['lineage_group'], row[1], row[2]]), row)
        rows = list(unique.values())
        # Correlated aliases do not multiply statistical weight.
        weights = defaultdict(int)
        for row, *_ in rows:
            weights[row['lineage_group']] += 1
        if len(weights) < 5:
            continue
        x = np.asarray([row[1] for row in rows]); y = np.asarray([row[2] for row in rows])
        fit_weights = np.asarray([1 / weights[row[0]['lineage_group']] for row in rows])
        y_mean = np.average(y, axis=0, weights=fit_weights)
        y_scale = np.maximum(np.sqrt(np.average((y-y_mean)**2, axis=0, weights=fit_weights)), 1e-6)
        normalized = (y - y_mean) / y_scale
        # BIC only proposes modes; each fitted mode still needs independent support.
        assignments = np.zeros(len(rows), dtype=int)
        if len(weights) >= 10 and len(rows) >= 10 and np.unique(normalized, axis=0).shape[0] >= 2:
            # BIC proposals see one representative per independent lineage.
            # Every observed configuration remains available outside regression.
            proposal=np.asarray([np.mean([normalized[i] for i,row in enumerate(rows)
                if row[0]['lineage_group']==group],axis=0) for group in sorted(weights)])
            choices = []
            for count in range(1, min(3, len(weights) // 5) + 1):
                model = GaussianMixture(count, random_state=0, n_init=3, reg_covar=1e-4).fit(proposal)
                labels = model.predict(normalized)
                if all(len({rows[i][0]['lineage_group'] for i in range(len(rows)) if labels[i] == k}) >= 5
                       for k in range(count)):
                    choices.append((float(model.bic(proposal)), count, labels))
            if choices:
                assignments = min(choices, key=lambda item: (item[0], item[1]))[2]
        for label in sorted(set(assignments)):
            selected = [row for i, row in enumerate(rows) if assignments[i] == label]
            mx = np.asarray([row[1] for row in selected]); my = np.asarray([row[2] for row in selected])
            mode_groups = defaultdict(int)
            for item in selected: mode_groups[item[0]['lineage_group']] += 1
            sample_weight = np.asarray([1 / mode_groups[row[0]['lineage_group']] for row in selected])
            centre = np.average(mx, axis=0, weights=sample_weight)
            scale = np.maximum(np.sqrt(np.average((mx-centre)**2, axis=0, weights=sample_weight)), 1e-6)
            response_centre = np.average(my, axis=0, weights=sample_weight)
            response_scale = np.maximum(np.sqrt(np.average((my-response_centre)**2, axis=0, weights=sample_weight)), 1e-6)
            regressor = Ridge(alpha=1., fit_intercept=True)
            regressor.fit((mx-centre)/scale, (my-response_centre)/response_scale, sample_weight=sample_weight)
            residuals = (my-response_centre)/response_scale - regressor.predict((mx-centre)/scale)
            selected_keys={digest([v[0]['lineage_group'],v[1],v[2]]) for v in selected}
            row = dict(condition_id=condition_id, condition=deepcopy(selected[0][3]),
                independent_support=len({item[0]['lineage_group'] for item in selected}),
                members=sorted(item[0]['example_id'] for item in selected),
                source_refs=sorted(item[0]['example_id'] for item in all_rows
                    if digest([item[0]['lineage_group'], item[1], item[2]]) in
                    selected_keys),
                x_centre=centre.tolist(), x_scale=scale.tolist(), x_min=mx.min(axis=0).tolist(),
                x_max=mx.max(axis=0).tolist(), x_support=((mx-centre)/scale).tolist(),
                y_centre=response_centre.tolist(), y_scale=response_scale.tolist(),
                coefficients=regressor.coef_.tolist(), intercept=regressor.intercept_.tolist(),
                fit_residual_rms=np.sqrt((residuals**2).mean(axis=0)).tolist(),
                quality_scope='TRAIN_FIT_DIAGNOSTIC_ONLY_NOT_CALIBRATED', alpha=1.)
            row['id'] = digest(row); modes.append(row)
    return dict(version=VERSION, inputs=list(INPUTS), outputs=list(OUTPUTS), modes=modes,
                absent_or_rare='RETAIN_OBSERVED_CONFIGURATIONS_NO_INVENTED_PARAMETERS')


def predict_joint(artifact, width, height, natural_advance_per_pt):
    import numpy as np
    if artifact.get('version') != VERSION:
        raise ValueError('Unknown joint model version')
    values = [width, height, natural_advance_per_pt]
    if not all(_finite(value) and value > 0 for value in values):
        raise ValueError('Joint demand requires positive finite physical measurements')
    x = np.asarray(values); predictions = []
    for mode in artifact['modes']:
        if digest({k:v for k,v in mode.items() if k != 'id'}) != mode['id']:
            raise ValueError('Joint weights digest differs')
        lower = np.asarray(mode['x_min']); upper = np.asarray(mode['x_max'])
        if np.any(x < lower-1e-7) or np.any(x > upper+1e-7):
            continue
        normalized = (x-np.asarray(mode['x_centre'])) / np.asarray(mode['x_scale'])
        # Do not bridge holes merely because independent ranges overlap.
        distance = min(float(np.linalg.norm(normalized-np.asarray(row))) for row in mode['x_support'])
        if distance > 1.5:
            continue
        y = (np.asarray(mode['coefficients']) @ normalized + np.asarray(mode['intercept']))
        y = y*np.asarray(mode['y_scale']) + np.asarray(mode['y_centre'])
        if not np.isfinite(y).all():
            continue
        predictions.append(dict(mode_id=mode['id'], joint=dict(zip(OUTPUTS, y.tolist())),
            condition=deepcopy(mode['condition']), support=mode['independent_support'],
            support_distance=distance, scope='MODEL_PROPOSAL_REQUIRES_WHOLE_LAYOUT_VERIFICATION'))
    return sorted(predictions, key=lambda row:(row['support_distance'], -row['support'], row['mode_id']))

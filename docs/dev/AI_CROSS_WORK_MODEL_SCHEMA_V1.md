# Cross-work model schema v1: implementation contract

2026-10-19. Formalizes the pending three profile designs and the shared AI02–06
pipeline. This is an implementation contract, not trained-model evidence or
completion of the three design TODOs. Source code staged during a frozen formal
run is explicitly UNAPPLIED until installed and tested in template_ai/tests.

## Reuse and migration

Keep the existing Library SQLite, TrainingStore transactions/history, SAMPLE,
DATASET, QualityGroups, InputGraph, Qt shaping, Kiwi and font/Logo/output checks.
New typed records in training_records are not a parallel database. Legacy
geometry-only learning remains labeled and cannot satisfy the cross-work goal.
New cross-work DATASET manifests declare their purpose and admission permission;
geometry-only permission never silently grants semantic-text training rights.
Schema versions, optional fields and purpose dispatch preserve legacy behavior.

## Admission and frozen manifest

Each entry pins sample/work/facts/observation/source revision and content digest,
source page, work dimensions/crop, known correlation projection and use rights.
An entry has one explicit TRAIN, VALIDATION or HOLDOUT role. A known correlated
component cannot span roles; historical exposure and later discovered links stay
conservative. Missing near-duplicate review is UNKNOWN, never independence proof.
Raw customer/name strings are not family identity features. No filename-based
customer inference is introduced; existing verified customer associations remain.

Model fitting/normalization use TRAIN only. VALIDATION selects hyperparameters and
calibrates applicability. HOLDOUT is sealed and exposure is persisted. Independent
lineage support counts replace raw import counts. Exact repeat observations do
not increase support; unclassified/rare qualified styles remain retrievable.

## Shared observations and profiles

- Field identity: stable field/data/render-instance references, semantic role,
  person/company ownership and label/icon bindings with independent evidence.
- Geometry: physical mm plus normalized container coordinates, ink/frame/available
  space distinction, baseline/anchor, relation edges and containment hierarchy.
- Typography: source-backed font/pt, shaped width/height, horizontal scale,
  tracking/distribution units and legal boundaries. Missing values carry masks;
  default Slot values and PDF visitor context are not original glyph truth.
- DataRequirementProfile conditions on semantic role, family, size, script,
  source-backed typography and policy. It stores measured occupation, legal
  breaks/presentation modes, observed/recommended/validated regions and support.
- FieldCapabilityProfile conditions on container, family, size, assets, owners,
  label/icon binding, optional/repeat structure and joint parameter region.
- ConditionalMatch keeps evidence_status, policy_status and feasibility_status
  separate, plus applicable conditions, reasons and dependency versions. Strict
  equivalence differs from directed substitution; a swap checks both destinations
  and surrounding relations with actual input measurements.

Unknown labels are masked, not negative. One fact printed twice retains one
logical identity and two rendered occupations. Observed configurations, proposed
transformations and permitted runtime transformations are distinct records.

## Family/rule artifact

TRAIN structural features encode role/container organization, normalized frame
statistics, observed typography masks and four style families. They exclude raw
strings, customer/source IDs and filenames. Robust scaling and HDBSCAN provide
family candidates, requiring the retained minimum5 independent lineages for a
supported family. Clustering/noise thresholds are versioned hyperparameters, not
learned product capacity. Re-estimation stores membership correspondence; no fake
partial_fit claim.

Each family stores independent support and counterexamples, role/owner patterns,
optional/repeated structures, relative relation support, conditional joint style
configurations and applicability/unknowns. Per-parameter min/max is not a joint
region. Distinct style modes and low-frequency qualified observations survive.
One family/rule artifact produces multiple input instances, not one template per
work or permutation. Removing supporting observations invalidates dependent rules.

## Generation and stable decisions

Compile bounded legal structural branches, instantiate all facts without loss,
shape actual text with the same Qt/font assets used for rendering, solve geometry
with Kiwi and recheck whole-layout hard constraints. Search states distinguish
verified feasible, verified infeasible, unknown and exhausted budget. Nonconvex
structure choices are not delegated to a linear solver as if it handled them all.

Use core-controlled joint field/pt/width/alignment/distribution choices; clients
express necessary relative intent only. Preserve protected/unaffected relative
relations without freezing every absolute coordinate. Same-template legal swaps
precede compatible-family fallback, with ownership and label/icon checks.

Every legal multi-choice decision has a versioned default and stable tie-break:
family, role assignment/order, structure, joint parameters and equal scores.
Explicit customer relations override applicable defaults. Default frequency is
not aesthetic truth; independent pair comparisons are needed for preference
training. Ranking never overrides hard checks or claims global optimum.

## Lifecycle, interaction and validation

Immutable model artifacts pin data/observations/schema/features/parameters/
policy/fonts/assets/solver. PENDING evaluation, policy-governed activation,
rollback, withdrawal and dependency invalidation do not rewrite historical output.
Feedback stores before/intent/after/reason/acceptance/scope. One local edit does
not become global policy. New features may be proposed, not silently authorized.

Desktop input/draft/relative edit/local correction/undo/preview/confirmation/
validated output uses the same core. Data/layout revisions remain separate;
requests carry expected revision and idempotency key, late results are rejected.
Accepted repeat orders reuse the actual retained output and dependencies; a JSON
recompute is not exact replay. Archive retention and cross-device services remain
OPEN; standalone web/mobile implementations remain deferred.

Evaluate role/relation correctness, family support/coverage, lawful swaps,
same-family adaptation, joint-style preservation, complete-data rate, defaults,
reprint reuse, uncertainty/error denominators and measured resource behavior.
Compare per-work-template, semantic-only, geometry-only and full baselines.
Actual authorized lineage-heldout, Windows/reference hardware, physical phone and
prepress evidence remain separate from authored synthetic mechanism checks.

---
name: template-ai-dry-refactoring
description: Triage local Template AI clone reports against callers and product rules, distinguishing useful reuse from intentional duplication without automatic bulk refactoring.
---

Read AGENTS.md and the current task. Read the pinned upstream at
docs/dev/debug_tooling/vendor/dry-refactoring/SKILL.md and its jscpd reference at
docs/dev/debug_tooling/vendor/jscpd/SKILL.md. TOOLCHAIN.json records provenance.

Use only the installed pinned local entrypoint:
`python docs/dev/debug_tooling/quality.py scan --scope application`.
Do not run the upstream's unpinned npx installation examples. No agents, external
model/API, hosted scan, new CI runner or paid resource is authorized.

Reports are leads. Inspect both fragments, callers, contracts, state and failure
behavior before calling them redundant. Preserve different identity/ownership,
old-template/confirmed-version behavior, font/ScaleX, relative positioning,
determinism and no-solution gates. Test fixtures and independent algorithms may
deliberately look alike. Record reasons for retained copies.

This environment task authorizes baseline and backlog construction, not the
upstream's repeat-until-eliminated loop. Only a subsequent task or necessary small
tool integration authorizes refactoring. If authorized, update every relevant call
site and rerun the same detection flags and meaningful behavioral tests. A lower
duplicate percentage alone is not acceptance. Keep exact and renamed/structural
results separate; only reviewed exact findings may gate new changes.

---
name: template-ai-diagnosing-bugs
description: Diagnose Template AI defects using bounded local reproduction, root-cause evidence and existing isolated tests, without private uploads, paid services or agents.
---

Read AGENTS.md, docs/dev/STATE.json and the relevant handoff first. Read the pinned
upstream at docs/dev/debug_tooling/vendor/diagnosing-bugs/SKILL.md; source, license
and hashes are in docs/dev/debug_tooling/TOOLCHAIN.json.

The user task, privacy and product contracts take precedence. Use one Codex, no
agents, remote models or paid service. First reproduce the exact symptom through
the real call path, then test falsifiable hypotheses, fix the root cause and run
the original repro plus relevant regression tests. Keep Qt's existing fresh
process isolation. Never relax a source/font/output gate to obtain a pass.

Default to at most 3 reproduction attempts or 120 seconds per hypothesis; extend
only to investigate an identified remaining risk. Do not mechanically run the
upstream's 100/1000-iteration suggestions. Do not request private works, raw
payloads, font files, whole databases or full logs. Use existing safe local report
exports. No HITL script or web/browser dependency is required for this desktop
project. Missing Windows/private-data reproduction is a documented limitation.

For tool installation verification, use the labelled isolated demo from
`python docs/dev/debug_tooling/quality.py selftest`; it does not prove real product
quality. Save the symptom, repro command/status, competing explanations, confirmed
cause, fix and regression outcome. Environment construction alone does not
authorize product fixes or a whole-repository cleanup.

---
name: promotion-scanner
description: Use when repeated manual, agent, subagent, trace, monitor, shell, or run-log work should be evaluated for promotion into repo code, tests, docs, coverage gaps, or Gauntlet workflow guidance.
---

# Promotion Scanner

Find repeated manual or agent loops that deserve durable engineering. This is a promotion brief, not an action recommender. No live operational actions.

Use on explicit request, Release or live-ops wrap-up, repeated manual verification, repeated `Cannot verify`, or repeated run-log evidence. Do not run for ordinary Patch.

If evidence is missing or stale, write `Cannot verify`. If the scan is outside scope, write `Not relevant because...`. Optional example: read `examples/promotion-brief.md` only when output shape is ambiguous.

## Output Contract

- Title: `Promotion Brief`
- Verdict: `Candidates found`, `No action`, `Needs proof`, or `Cannot verify`
- Evidence reviewed: traces, shell outputs, subagent reports, monitor logs, run logs, code paths, tests, repo guidance, and prior decisions
- Current evidence table by entity or surface, with source, timestamp or freshness, and confidence
- Timeline highlights with stale vs latest evidence separated
- Repeated manual loops observed
- Promotion candidates with confidence and proof needed
- Recommended destination: `repo code`, `repo test`, `repo docs/run log`, `Gauntlet skill/tool`, `coverage gap`, or `Reject`
- Edge cases and tests
- secrets/redaction notes
- Do not infer warnings
- Agent next: one bounded follow-up

## Rules

- No live operational actions: do not say to terminate, delete, bill, deploy, revoke, migrate, or mutate production state now.
- Use explicit artifacts over vague memory. Separate observed facts from inference.
- Separate stale scary lines from latest evidence; call out contradictory evidence.
- Repo-specific vocabulary, commands, dashboards, and business rules stay repo-local.
- Add or update a `GAP-###` only for Gauntlet-general missing guidance. Repo-specific candidates go to repo code, repo test, repo docs/run log, or issue follow-up.
- Redact secrets from packets, examples, and quoted logs.
- Reject one-off incidents, low-confidence patterns, stale mappings, or loops already covered by existing code/tests.
- In monorepos or giant files, split by concrete surface only when evidence supports it.

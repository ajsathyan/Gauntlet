---
name: issue-triager
description: Use when planned work, review findings, test failures, bugs, or open questions need classification, reproduction, prioritization, deduplication, or routing into ready items.
---

# Issue Triager

Triage is flow control. Convert messy inputs into ready work, deferred notes, duplicates, rejected items, or blocked questions.

## Ready Item

For each issue, output:

If a field is outside accepted scope, write `Not relevant because...` instead of creating speculative work. Optional example: read `examples/ready-item.md` only when output shape is ambiguous.

- Classification: bug, test failure, review finding, release concern, cleanup, open question, duplicate, or no-action
- Decision: `Ship blocker`, `Conditional blocker`, `Manual fallback`, `Private beta gate`, `Defer`, `Reject`, or `Ready`
- Priority: P0/P1/P2/P3
- Status: `Ready`, `Blocked`, `Deferred`, `Duplicate`, `Rejected`, or `No action`
- Source handle or source text
- Observed vs expected
- Evidence
- Repro state: exact repro, partial repro, missing repro, or not reproducible
- Cannot verify: missing data and next proof
- Done when
- Next action
- Owner/role
- WIP guidance

Independent findings may be triaged by parallel subagents when sources do not overlap. Merge only when cause or resolution is shared.

## Rules

- Mark work Ready only when the next action and Done when are clear.
- Do not assign root cause without evidence.
- Split broad findings into implementable tasks.
- For Production Quality Bar findings, keep automatable proof separate from Human judgment and downgrade speculative launch concerns with `Not relevant because...`, `Defer`, or `Reject`.
- Preserve the Release launch cut line, panel delta, decisions, and `| Concern | Decision | Why Not Defer | Proof | Plan Delta |`.
- A `Ship blocker` must name concrete harm, why fallback/deferral/recovery is not acceptable, executable proof, and plan delta.
- Cleanup becomes Ready only with evidence, scope, done criteria, and verification; otherwise Defer, Reject, or No action.

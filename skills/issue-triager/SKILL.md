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
- Decision: `Block`, `Ready`, `Defer`, `Reject`, `Duplicate`, or `No action`
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
- Use `Block` only for concrete harm or missing authority/proof that prevents the accepted next action. Name the decision, recommended resolution, impact, and unaffected work that may continue.
- Cleanup becomes Ready only with evidence, scope, done criteria, and verification; otherwise Defer, Reject, or No action.
- Make `Done when` an observable outcome or invariant with meaningful limits. For consequential behavior, include a plausible wrong case and required non-effects; a phrase, populated field, self-report, or green command alone is insufficient.

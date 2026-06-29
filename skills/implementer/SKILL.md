---
name: implementer
description: Use when executing ready task packets against an accepted spec while preserving repo patterns, limiting scope, and returning proof.
---

# Implementer

Turn one ready task packet into working, maintainable code.

## Implementation Packet

Read the task packet, then return:

If a field is outside accepted scope, write `Not relevant because...` instead of expanding the task. Optional example: read `examples/implementation-report.md` only when output shape is ambiguous.

- Status: `Done`, `Done with concerns`, `Blocked`, or `Needs context`
- Changed files
- Behavior changed
- Proof: commands, screenshots, benchmarks, logs, manual checks, what they prove, and what they do not prove
- Cannot verify: missing proof, why it matters, and who can check it
- Review concerns: human judgment, missing proof, or reopened attention
- User-work note: unrelated dirty files noticed and preserved
- Next action

For Feature or Release work, also report run-log-friendly exceptions:

- Material assumptions, decisions, deviations, and tradeoffs
- Failed, skipped, partial, or unavailable proof
- Things that went wrong and follow-ups
- Coverage gap candidate when reusable guidance is missing

## Rules

- Read before editing.
- Match local patterns.
- Implement the smallest correct step.
- Keep interfaces narrow and behavior explicit.
- Add or update tests when behavior changes.
- For independent task packets with disjoint files, state, and proof, use only subagent lanes accepted by `scripts/check-subagent-plan.py`; otherwise implement sequentially. Do not repeat large shared context into subagents unless speed gains justify the tokens.
- Avoid broad rewrites, speculative abstractions, unrelated cleanup, and silent behavior changes.
- After substantial or generated-code-heavy changes, remove dead code and unnecessary abstractions you introduced before final verification.
- Do not damage unrelated user work in a dirty workspace.
- Done requires required proof to pass or be explicitly Not Applicable with rationale; code alone is not done.

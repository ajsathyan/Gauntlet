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
- For practical behavior changes, use RED-GREEN-REFACTOR: make the relevant test fail for the intended reason, implement the smallest source fix, then refactor while green. For docs, generated output, or legacy surfaces without a credible harness, record why and run the closest regression proof.
- Verify review feedback against the accepted spec, code, and tests before applying it. Return `Needs context` when feedback would silently change behavior.
- Refuse parallel delegated implementation when the accepted current-run manifest is missing or rejected. The manifest is the packet; do not require a second Markdown copy.
- Before implementing added scope, require its scope-addition delta to be resolved; a clean check may be represented by `Scope delta checked: no material change.` in the plan or task packet.
- For independent task packets with disjoint files, state, and proof, use only subagent lanes accepted by `scripts/check-subagent-plan.py`; otherwise implement sequentially. Do not repeat large shared context into subagents unless speed gains justify the tokens.
- Avoid broad rewrites, speculative abstractions, unrelated cleanup, and silent behavior changes.
- After substantial or generated-code-heavy changes, remove dead code and unnecessary abstractions you introduced before final verification.
- Do not damage unrelated user work in a dirty workspace.
- Done requires required proof to pass or be explicitly Not Applicable with rationale; code alone is not done.

## Attribution

RED-GREEN-REFACTOR, evidence-before-completion, and verify-before-applying-review guidance are adapted from Jesse Vincent's Superpowers `test-driven-development`, `verification-before-completion`, and `receiving-code-review` skills, version 5.1.3 (MIT). Gauntlet keeps bounded exceptions for work without a credible test harness. See `docs/upstream-superpowers.md`.

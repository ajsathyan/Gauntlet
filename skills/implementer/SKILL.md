---
name: implementer
description: Use when executing ready task packets against an accepted spec while preserving repo patterns, limiting scope, and returning proof.
---

# Implementer

Execute one accepted packet. Preserve unrelated work and prove behavior.

## Delegated Lane Receipt

When dispatched as a child lane, do not narrate routine work. Return exactly one compact receipt and no surrounding prose:

```json
{"status":"Done","changedFiles":["path"],"proof":["command: result"],"blocker":null}
```

Use `Done`, `Done with concerns`, `Blocked`, or `Needs decision` for `status`. Keep `changedFiles` and `proof` as short arrays. Use `null` for `blocker` unless integration cannot continue.

## Implementation Packet

Non-delegated reports contain changed behavior, proof, real concerns, and the next action:

Optional example: read `examples/implementation-report.md` only when the output shape is ambiguous.

- Status: `Done`, `Done with concerns`, `Blocked`, or `Needs context`
- Changed files and behavior
- Proof: evidence, what it proves, and its limits
- `Cannot verify`: material missing proof, why, and who can check it
- Review concerns: remaining human judgment or missing proof
- User-work note: unrelated dirty files preserved
- Next action

For Feature or Release work, add only exceptions that occurred: material decisions, deviations, proof gaps, failures, follow-ups, or a reusable coverage gap.

## Rules

- Read first, match local patterns, implement the smallest correct step, and test behavior changes.
- For practical behavior changes, use RED-GREEN-REFACTOR: observe the relevant test fail for the intended reason, implement the smallest source fix, then refactor while green. When no credible harness exists, record why and run the closest regression proof.
- Verify review feedback against the accepted spec, code, and tests before applying it; return `Needs decision` when it would silently change behavior.
- Every delegated lane requires one bounded task packet naming objective, ownership, dependencies, constraints, proof, return contract, and ask-user policy.
- Native Codex state and main-task messages own live coordination.
- Shared accepted context lives in the canonical plan; child prompts contain only the context needed for their lane.
- For child lanes selected by the standing router authorization, preserve disjoint ownership, state, and proof. Otherwise work sequentially. Repeat shared context only when speed or independent evidence justifies it.
- Keep delegation, child progress, and compact receipts out of user-facing messages unless the host requires disclosure; all other applicable workflow etiquette still runs internally.
- Keep clean validation, mode/gate selection, scope-delta checks, review transitions, and hygiene transitions out of the report.
- Resolve added-scope deltas first. A clean plan/task may retain `Scope delta checked: no material change.`
- Retry a delegated-lane failure silently only when the next attempt is safe, materially different, and inside accepted authority and appetite. Stop and return the compact receipt when the failure fingerprint would repeat, new authority is required, destructive external state is at risk, or the appetite would be exceeded.
- Avoid broad rewrites, speculative abstractions, unrelated cleanup, and silent behavior changes.
- Remove current-change dead code and unnecessary abstractions before final verification.
- Done requires required proof to pass or be explicitly unavailable with its consequence stated; code alone is not done.

## Attribution

RED-GREEN-REFACTOR, evidence-before-completion, and verify-before-applying-review guidance are adapted from Jesse Vincent's Superpowers `test-driven-development`, `verification-before-completion`, and `receiving-code-review` skills, version 5.1.3 (MIT). See `docs/upstream-superpowers.md`.

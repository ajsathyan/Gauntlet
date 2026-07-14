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

Optional example: `examples/implementation-report.md`.

- Status: `Done`, `Done with concerns`, `Blocked`, or `Needs context`
- Changed files and behavior
- Proof: evidence, what it proves, and its limits
- `Cannot verify`: material missing proof, why, and who can check it
- Review concerns: remaining human judgment or missing proof
- User-work note: unrelated dirty files preserved
- Next action

## Rules

- Read first, match local patterns, implement the smallest correct step, and test behavior changes.
- For practical behavior changes, use RED-GREEN-REFACTOR: observe the relevant test fail for the intended reason, implement the smallest source fix, then refactor while green. When no credible harness exists, record why and run the closest regression proof.
- Verify review feedback against the accepted spec, code, and tests before applying it; return `Needs decision` when it would silently change behavior.
- Every delegated lane requires one bounded task packet naming objective, ownership, dependencies, constraints, proof, return contract, and ask-user policy.
- Native Codex state owns coordination. Keep shared context in the canonical plan and child ownership, state, proof, and prompts bounded; otherwise work sequentially.
- Keep delegation, child progress, and compact receipts out of user-facing messages unless the host requires disclosure; all other applicable workflow etiquette still runs internally.
- Keep clean validation, mode/gate selection, scope-delta checks, review transitions, and hygiene transitions out of the report.
- Resolve added-scope deltas first. A clean plan/task may retain `Scope delta checked: no material change.`
- Retry a delegated-lane failure silently only when the next attempt is safe, materially different, and inside accepted authority and appetite. Stop and return the compact receipt when the failure fingerprint would repeat, new authority is required, destructive external state is at risk, or the appetite would be exceeded.
- Avoid broad rewrites, speculative abstractions, unrelated cleanup, and silent behavior changes.
- Keep secrets and environment-specific values in the project's approved secret or configuration mechanism. Keep stable product constants in typed, reviewed, tested code instead of turning every value into mutable configuration.
- Remove current-change dead code and unnecessary abstractions before final verification.
- Under an active `doc_org.md`, child worktrees do not create alternate canonical documents. Return material decisions, exceptions, unresolved gaps, and proof so the main task can update the primary-worktree copies before cleanup.
- Done requires required proof to pass or be explicitly unavailable with its consequence stated; code alone is not done.

## Attribution

RED-GREEN-REFACTOR, evidence-before-completion, and verify-before-applying-review guidance are adapted from Jesse Vincent's Superpowers `test-driven-development`, `verification-before-completion`, and `receiving-code-review` skills, version 5.1.3 (MIT). See `docs/upstream-superpowers.md`.

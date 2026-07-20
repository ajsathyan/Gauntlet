---
name: implementer
description: Use when executing a bounded Build workstream against requested outcomes while preserving repo patterns, unrelated work, and meaningful proof.
---

# Implementer

Execute one bounded workstream from the user request and any accepted design. A
child assignment cannot narrow requested outcomes or an applicable canonical
Build Contract.

## Delegated Workstream Receipt

Do not narrate routine work, tool choice, recoverable issues, or retries. Return only status, changed files or artifact, proof and its limit, and a blocker or risk. Use JSON only when parsed. Contact the parent early only for new authority, an unrecoverable blocker, a safety stop, or a required heartbeat.

## Implementation Report

Non-delegated reports contain:

Optional example: read `examples/implementation-report.md` only when the output shape is ambiguous.

- Status: `Done`, `Done with concerns`, `Blocked`, or `Needs context`
- Changed files and behavior
- Proof: evidence, what it proves, and its limits
- `Cannot verify`: material missing proof, why, and who can check it
- User-work note: unrelated dirty files preserved
- Next action

## Rules

- Read first, match local patterns, implement the smallest correct step, and test behavior changes.
- For practical behavior changes, use RED-GREEN-REFACTOR: observe the relevant test fail for the intended reason, implement the smallest source fix, then refactor while green. When no credible harness exists, record why and run the closest regression proof.
- Verify review feedback before applying it. Resolve routine behavior choices
  inside the assigned scope and record material decisions; return `Needs
  decision` only for scope, safety, authority, or external-effect changes.
- Every delegated lane gets one bounded workstream assignment containing only applicable fields. Proof expectations are proportional to risk; the return contract and ask-parent policy are explicit.
- Native Codex state owns coordination. Child prompts contain only their outcome slice and assignment, with disjoint ownership, state, and proof; otherwise work sequentially.
- Keep delegation, child progress, clean checks, and receipts out of user-facing messages unless required.
- Resolve material added-scope deltas by updating affected ownership, dependencies, and proof. Keep no-op checks silent.
- Child tests are evidence, not sole acceptance. A ticket may authorize edits to assertions, graders, fixtures, or oracles, but an edited oracle cannot establish acceptance until the parent independently reviews or redefines it.
- Make tests behavior-sensitive: establish the intended failure when practical, include a plausible wrong case or required non-effect, and state what the result proves. Phrases, fields, and green commands alone do not prove semantics.
- When `gauntlet-sensors.json` exists, run `gauntlet sensors run` before handoff. A nonzero verdict blocks the workstream; use its compact attention items, open referenced raw logs only as needed, repair the code, and rerun. Planning or normalization alone is not sensor proof.
- The parent reruns or inspects proof; consequential work may need independent black-box or hidden checks.
- The parent hands the exact integrated revision to Verify. A child receipt,
  green sensors, or this report cannot establish the requested Build outcome.
- Retry silently only when safe, materially different, and authorized. Stop before repeating a failure fingerprint or risking destructive state.
- Avoid broad rewrites, speculative abstractions, unrelated cleanup, and silent behavior changes.
- Done requires required proof to pass or be explicitly unavailable with its consequence stated; code alone is not done.

## Attribution

RED-GREEN-REFACTOR, evidence-before-completion, and verify-before-applying-review guidance are adapted from Jesse Vincent's Superpowers `test-driven-development`, `verification-before-completion`, and `receiving-code-review` skills, version 5.1.3 (MIT). See `docs/upstream-superpowers.md`.

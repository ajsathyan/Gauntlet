---
name: planner
description: Use when Build needs an ephemeral implementation sequence, bounded workstream assignments, dependencies, and proof for an accepted design.
---

# Planner

Shape an internal disposable Build plan. Split only independent ownership and proof.

Plan only from the exact accepted design. Its `Acceptance` section remains the canonical Build Contract. If observable done behavior or another material product decision is absent, return to Design; do not fill the gap with a plausible requirement, non-goal, safety boundary, gate, or worker checklist.

## Output Contract

Optional example: `examples/workstream-assignment.md`.

- First coherent Build step
- Dependencies, shared boundaries, and integration order
- Deferrals, risks, verification, and ordered implementation steps
- Independent workstreams and compact child assignments, only when work will be dispatched
- Material scope additions and their effect on ownership, dependencies, and proof

Include an optional profile only when it materially improves the lane; omit no-op fields.

The plan exists only in current task state and is discarded after Build. The accepted Design remains the durable source of product truth.

## Workstream Assignment

Each dispatched child gets one concise prose ticket with only applicable fields:

- Objective
- Ownership: files, state, contracts, or evidence the child owns and must avoid
- Material dependencies and inputs/outputs
- Constraints and authority
- Proof contract, proportional to risk:
  - Claim or invariant
  - Observable oracle
  - Required checks
  - Negative control or plausible wrong case
  - Required non-effects
  - Oracle/fixture ownership and anti-tamper boundary
  - Parent independent verification
  - `Cannot verify` limits
- Return contract and ask-parent policy

This compact child assignment is temporary implementation context. The child works autonomously without routine narration and returns only the artifact or findings, compact proof, and risk.

## Rules

- Use end-to-end steps unless files, state, and proof are independent enough to split.
- Convert uncertainty into probes, assumptions, or `Cannot verify` items. Name one first-ready lane.
- Dispatch through native Codex state. Send each child only its outcome slice and bounded assignment.
- When scope changes materially, update affected ownership, dependencies, and proof. Keep no-op checks silent.
- Keep proposed discussion and unaccepted agent suggestions out of the plan. Preserve existing behavior unless the accepted artifact explicitly changes it.
- Define proof around observable behavior or invariants, not self-reports or a green command alone.
- Child tests are evidence, not sole acceptance. A ticket may authorize oracle or fixture edits, but an edited oracle cannot establish acceptance until the parent independently reviews or redefines it.
- Plan focused workstream checks and one independent final Verify pass against the accepted design on the exact integrated revision. Reuse evidence only when revision/tree, command, toolchain, fixtures or oracle, and relevant environment all match.
- Use direct parent verification for ordinary work. Add independent review only for a concrete consequential boundary.
- Do not split tightly coupled state or one decision tree across child lanes.
- Carry the accepted design's concrete consequence triggers into Build and Verify; omission never means `none`. Triggered security, recovery, black-box, dry-run, bounded-canary, or rollback proof remains separate.
- Include TypeScript durability only when its classifier requires it or the user asks.
- Use the Production Quality Bar only for near-launch, private-beta, production-bound, hardened, or audited work; otherwise omit it. When active, include explicit deferrals and repository-owned release proof such as dry-run/no-mutation behavior and automated GitHub release tags.
- Stop planning once the first build step and first meaningful proof path are obvious.

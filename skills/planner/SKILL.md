---
name: planner
description: Use when a spec needs bounded steps, delegation tickets, dependencies, proof, risks, deferrals, and a first ready task.
---

# Planner

Shape canonical plan steps. Define appetite before scope; split only independent ownership and proof.

## Output Contract

Optional example: `examples/ticket.md`.

- Problem, target outcome, and appetite
- Must-haves and non-goals
- Deferrals, risks, verification, and ordered implementation steps
- Independent child lanes and **Gauntlet Tickets**, only when work will be dispatched
- Material scope additions and their effect on ownership, dependencies, and proof
- First ready task

Include routing only when material; omit no-op fields.

## Gauntlet Ticket

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

The child works autonomously without routine narration. It returns only the artifact or findings, compact proof, and risk. It contacts the parent only for new authority, an unrecoverable blocker, a safety stop, or a required heartbeat.

## Rules

- Use end-to-end steps unless files, state, and proof are independent enough to split.
- Convert uncertainty into probes, assumptions, or `Cannot verify` items. Name one first-ready lane.
- Dispatch through native Codex state. Send each child only its bounded ticket.
- When scope changes materially, update affected ownership, dependencies, and proof. Keep no-op checks silent.
- Define proof around observable behavior or invariants, not self-reports or a green command alone.
- Child tests are evidence, not sole acceptance. A ticket may authorize oracle or fixture edits, but an edited oracle cannot establish acceptance until the parent independently reviews or redefines it.
- Plan targeted Ticket checks, optional Cohort checks for a named shared invariant, and one final Epic verification on the exact integrated revision. Reuse a receipt only when commit/tree, command, toolchain, fixtures or oracle, and relevant environment all match.
- Use direct parent verification for ordinary work. Add independent review only for a concrete consequential boundary.
- Do not split tightly coupled state or one decision tree across child lanes.
- Copy the locked Epic's consequence triggers exactly into its Ticket Graph; omission never means `none`. A non-empty set requires three exact-revision lenses: security/authority, failure/recovery, and black-box non-effects. Run deterministic checks first, fix findings, rerun affected proof, then require repository-owned dry-run, bounded-canary, and rollback evidence.
- For TypeScript work, include the TS Durability gate only when the classifier says `durabilityRequired: true` or the user explicitly asks.
- Trigger the Production Quality Bar only for near-launch, private-beta, production-bound, hardened, or audited work; otherwise omit it. When triggered, attach release proof such as dry-run/no-mutation evidence, automated GitHub release tags, and explicit deferrals.
- Stop planning once the first build step and first meaningful proof path are obvious.

## Attribution

End-to-end task sizing, explicit interfaces, and execution checkpoints are adapted from Jesse Vincent's Superpowers `writing-plans` and `executing-plans` skills, version 5.1.3 (MIT). See `docs/upstream-superpowers.md`.

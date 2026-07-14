---
name: planner
description: Use when an accepted spec needs bounded implementation steps, delegation tickets, dependencies, interfaces, proof, risks, deferrals, and a first ready task.
---

# Planner

Turn accepted work into steps. Define appetite before scope; split only independent ownership and proof.

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

Each dispatched child gets one concise prose ticket. Include only fields that apply:

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

Unless specified otherwise, the child works autonomously without narrating routine progress, tool choice, recoverable issues, or retries. It returns only the requested artifact or findings, compact proof, and risk. It contacts the parent early only for new authority, an unrecoverable blocker, a safety stop, or a required heartbeat.

## Rules

- Use end-to-end steps unless files, state, and proof are independent enough to split.
- Convert uncertainty into probes, assumptions, or `Cannot verify` items. Name one first-ready lane.
- Dispatch through native Codex state. Keep shared context in the canonical plan and send each child only its bounded ticket.
- When scope changes materially, update affected ownership, dependencies, and proof. Keep no-op checks silent.
- Define proof around observable behavior or invariants, not phrases, fields, self-reports, or a green command alone.
- Child tests are evidence, not sole acceptance. Protect oracles, shared fixtures, hidden checks, and graders unless explicitly owned; require parent rerun or inspection.
- Compare or adversarially check consequential performance, security, reliability, and hot-path work.
- Do not split tightly coupled state or one decision tree across child lanes.
- Preserve guarded Release decisions and the `| Concern | Decision | Why Not Defer | Proof | Plan Delta |` table. A `Ship blocker` needs concrete harm, no acceptable fallback, executable proof, and plan delta.
- For TypeScript work, include the TS Durability gate only when the classifier says `durabilityRequired: true` or the user explicitly asks.
- Trigger the Production Quality Bar only for near-launch, private-beta, production-bound, hardened, or audited work; otherwise omit it.
- Stop planning once the first build step and first meaningful proof path are obvious.

## Attribution

End-to-end task sizing, explicit interfaces, and execution checkpoints are adapted from Jesse Vincent's Superpowers `writing-plans` and `executing-plans` skills, version 5.1.3 (MIT). Gauntlet omits prewritten production code, micro-step ceremony, and duplicate plan documents. See `docs/upstream-superpowers.md`.

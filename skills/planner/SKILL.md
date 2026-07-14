---
name: planner
description: Use when an accepted spec needs bounded task packets with dependencies, interfaces, proof, risks, deferrals, and a first ready task.
---

# Planner

Turn accepted work into bounded steps.

## Output

Optional example: `examples/task-packet.md`.

- Problem, outcome, appetite
- Must-haves and non-goals
- Scope pressure, deferrals, and risks/unknowns
- Configuration, secrets, and constants: external values, destination, defaults, validation, redaction, or `None identified`
- Verification plan
- Parallelizable lanes: independent tasks that can go to subagents, or omit when none
- Scope-addition delta: material change or `Scope delta checked: no material change.`
- Ordered **Gauntlet Task Packet** list
- First ready task

Include routing only when material; omit no-op fields.

## Gauntlet Task Packet

Each main-plan task gets an end-to-end packet:

- Task and goal
- Files/areas to inspect and avoid
- Consumes: named dependencies and state
- Produces: named outputs and state
- Steps
- Proof and `Cannot verify` limits
- Configuration and secret handling required by this task
- Done when

## Child Implementation Lanes

- Give each child one bounded task packet with objective, ownership, dependencies, contracts, constraints, proof, return contract, and ask-user policy.
- Coordinate through native state and preserve bounded ownership and proof.
- Keep the plan end-to-end when lanes are coupled or the gain does not beat context and coordination cost.

## Rules

- Use end-to-end steps unless files, state, and proof are independent enough to split.
- Convert uncertainty into probes, assumptions, or `Cannot verify` items.
- Keep shared context in the canonical plan and send each child only what it needs. Name dependencies and one first-ready lane.
- Before added scope, run delta foresight. Keep `Scope delta checked: no material change.` inside the affected plan/task; material findings update scope and proof.
- Do not split tightly coupled state or one decision tree across child lanes.
- For Release panels, preserve launch cut line, panel delta, and `| Concern | Decision | Why Not Defer | Proof | Plan Delta |`. A `Ship blocker` requires concrete harm, no acceptable fallback, executable proof, and a plan delta; otherwise downgrade it.
- Decisions: `Ship blocker`, `Conditional blocker`, `Manual fallback`, `Private beta gate`, `Defer`, or `Reject`.
- Do not union every idea from duplicate Release plans.
- For TypeScript work, include the TS Durability gate only when the classifier says `durabilityRequired: true` or the user explicitly asks.
- Trigger the Production Quality Bar only for near-launch, private-beta, production-bound, hardened, or audited work. Include release proof such as dry-run/no-mutation evidence, automated GitHub release tags, and explicit deferrals; omit the field when the trigger is absent.
- Under an active `doc_org.md`, write build-ready plans in the canonical primary-worktree location, inventory configuration/secrets/constants, and resolve the plan's authority, rollout, rollback, proof, and release-source fields without copying the reusable release contract.
- Never hardcode secrets, credentials, private resource identifiers, environment-specific endpoints, deployment identifiers, or values that legitimately vary by environment or operator. Stable typed and tested product or protocol constants may remain in code.
- Stop planning once the first build step and first meaningful proof path are obvious.

## Attribution

End-to-end task sizing, explicit interfaces, and execution checkpoints are adapted from Jesse Vincent's Superpowers `writing-plans` and `executing-plans` skills, version 5.1.3 (MIT). Gauntlet omits prewritten production code, micro-step ceremony, and duplicate plan documents. See `docs/upstream-superpowers.md`.

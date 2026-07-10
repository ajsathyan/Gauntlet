---
name: planner
description: Use when an accepted spec needs bounded task packets with dependencies, interfaces, proof, risks, deferrals, and a first ready task.
---

# Planner

Turn accepted work into steps. Define appetite before scope; split only independent ownership and proof.

## Output

Optional example: `examples/task-packet.md`.

- Problem, target outcome, and appetite
- Must-haves and non-goals
- Scope pressure, deferrals, and risks/unknowns
- Verification plan
- Parallelizable lanes: independent tasks that can go to subagents, or omit when none
- Scope-addition delta: material change or `Scope delta checked: no material change.`
- Ordered **Gauntlet Task Packet** list
- First ready task

Include routing only when material; omit no-op fields.

## Gauntlet Task Packet

Each main-plan task gets an end-to-end packet:

- Task and goal
- Files/areas to inspect and avoid; Global Constraints copied verbatim
- Consumes: prior outputs, exact names, contracts, state, or handles
- Produces: outputs, exact names, contracts, state, or handles
- Steps
- Proof and `Cannot verify` limits
- Done when

## Child Implementation Lanes

- Give each child one bounded task packet from the canonical plan. Include objective, skill, ownership, dependencies, consumes/produces contracts, constraints, proof, return contract, and ask-user policy.
- Dispatch and coordinate through native Codex state and main-task messages.
- For child lanes selected by the standing router authorization, preserve their bounded ownership and proof contracts.
- Keep the plan end-to-end when lanes are coupled or the gain does not beat context and coordination cost.

## Rules

- Use end-to-end steps unless files, state, and proof are independent enough to split.
- Convert uncertainty into probes, assumptions, or `Cannot verify` items.
- Keep shared context in the canonical plan and send each child only what it needs. Name dependencies and one first-ready lane.
- Before added scope, run delta foresight. Keep `Scope delta checked: no material change.` inside the affected plan/task; material findings update scope and proof.
- Compare or adversarially check consequential performance, security, reliability, and hot-path work.
- Do not split tightly coupled state or one decision tree across child lanes.
- For Release panels, preserve the launch cut line, panel delta, `| Concern | Decision | Why Not Defer | Proof | Plan Delta |`, and allowed decisions: `Ship blocker`, `Conditional blocker`, `Manual fallback`, `Private beta gate`, `Defer`, `Reject`.
- A `Ship blocker` needs concrete harm, no acceptable fallback/deferral, executable proof, and a real plan delta; otherwise downgrade it.
- When running duplicate Release planning prompts, compare missing blockers, dependency order, proof requirements, first task, deferrals, and rejections. Do not union every idea.
- For TypeScript work, include the TS Durability gate only when the classifier says `durabilityRequired: true` or the user explicitly asks.
- Trigger the Production Quality Bar only for near-launch, private-beta, production-bound, hardened, or audited work. When triggered, include release proof such as dry-run/no-mutation evidence, automated GitHub release tags, and explicit deferrals; omit the field when the trigger is absent.
- Stop planning once the first build step and first meaningful proof path are obvious.

## Attribution

End-to-end task sizing, explicit interfaces, and execution checkpoints are adapted from Jesse Vincent's Superpowers `writing-plans` and `executing-plans` skills, version 5.1.3 (MIT). Gauntlet omits prewritten production code, micro-step ceremony, and duplicate plan documents. See `docs/upstream-superpowers.md`.

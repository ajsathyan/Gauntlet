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
- Subagent manifest and dispatch source: `.gauntlet/subagent-plan.json`, or omit when no gated child lane exists
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

- The validated manifest lane is the bounded child contract. Do not write a second Markdown packet.
- For two or more parallel lanes or any write-heavy child implementation lane, write schema `1.2` in `.gauntlet/subagent-plan.json` with shared accepted context and lane-specific deltas. Validate it before implementation, not merely before dispatch.
- Render the child prompt with `scripts/check-subagent-plan.py "$PROJECT_ROOT" .gauntlet/subagent-plan.json --render-lane "$LANE_ID"`; rendered text is a view, not another source of truth.
- A single small read-only child gets a bounded prompt without the manifest gate.
- Successful validation stays silent. Surface only a material finding or blocker.
- Use subagents only for independent lanes.

## Rules

- Use end-to-end steps unless files, state, and proof are independent enough to split.
- Convert uncertainty into probes, assumptions, or `Cannot verify` items.
- Share inherited `acceptedSource` and `constraints` at plan level. `dependencies` remains descriptive; it provides no DAG, readiness, review, or completion state.
- Before added scope, run delta foresight. Keep `Scope delta checked: no material change.` inside the affected plan/task; material findings update scope and proof.
- Compare or adversarially check consequential performance, security, reliability, and hot-path work.
- Do not split tightly coupled state or one decision tree across child lanes.
- For Release panels, preserve the launch cut line, panel delta, `| Concern | Decision | Why Not Defer | Proof | Plan Delta |`, and allowed decisions: `Ship blocker`, `Conditional blocker`, `Manual fallback`, `Private beta gate`, `Defer`, `Reject`.
- A `Ship blocker` needs concrete harm, no acceptable fallback/deferral, executable proof, and a real plan delta; otherwise downgrade it.
- When running duplicate Release planning prompts, compare missing blockers, dependency order, proof requirements, first task, deferrals, and rejections. Do not union every idea.
- For TypeScript work, include the TS Durability gate only when the classifier says `durabilityRequired: true` or the user explicitly asks.
- Trigger the Production Quality Bar only for near-launch, private-beta, production-bound, hardened, or audited work. When triggered, include release proof such as dry-run/no-mutation evidence, automated GitHub release tags, and explicit deferrals; omit the field when the trigger is absent.
- Stop planning once the first build step and first meaningful proof path are obvious.

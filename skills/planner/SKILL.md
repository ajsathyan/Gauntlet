---
name: planner
description: Use when an accepted spec needs bounded task packets with dependencies, interfaces, proof, risks, deferrals, and a first ready task.
---

# Planner

Turn accepted work into implementation steps. Define appetite before scope and split only independent ownership and proof.

## Output

Optional example: read `examples/task-packet.md` only when the packet shape is ambiguous.

- Problem, target outcome, and appetite
- Must-haves and non-goals
- Scope pressure, deferrals, and risks/unknowns
- Verification plan
- Ordered **Gauntlet Task Packet** list
- First ready task

Include internal routing only when it changes scope, order, proof, cost, or a user decision. Omit no-op and `Not relevant because...` fields.

## Gauntlet Task Packet

Each task gets an end-to-end packet:

- Task and goal
- Files/areas to inspect and avoid; Global Constraints copied verbatim
- Consumes: prior outputs, exact names, contracts, state, or handles
- Produces: outputs, exact names, contracts, state, or handles
- Steps
- Proof and `Cannot verify` limits
- Done when

## Child Implementation Lanes

- Every child implementation lane gets a bounded task packet before implementation.
- For two or more parallel lanes or any write-heavy child implementation lane, write schema `1.2` in `.gauntlet/subagent-plan.json` with shared context and lane deltas. Validate it with `scripts/check-subagent-plan.py` before implementation, not merely before dispatch.
- Omit the subagent manifest field when no child implementation lanes are proposed. Do not record packetization when no child implementation lanes exist.
- A small read-only child gets a bounded prompt without the manifest gate.
- Successful packet validation stays silent. Surface only material findings.
- Use subagents only for independent packets.

## Rules

- Use end-to-end steps unless files, state, and proof are independent enough to split.
- Convert uncertainty into probes, assumptions, or `Cannot verify` items.
- Before added scope, run delta foresight. Keep `Scope delta checked: no material change.` inside the affected packet; material findings update scope and proof.
- Compare or adversarially check consequential performance, security, reliability, and hot-path work.
- For Release panels, preserve the launch cut line, panel delta, `| Concern | Decision | Why Not Defer | Proof | Plan Delta |`, and allowed decisions: `Ship blocker`, `Conditional blocker`, `Manual fallback`, `Private beta gate`, `Defer`, `Reject`.
- A `Ship blocker` needs concrete harm, no acceptable fallback/deferral, executable proof, and a real plan delta; otherwise downgrade it.
- When running duplicate Release planning prompts, compare missing blockers, dependency order, proof requirements, first task, deferrals, and rejections. Do not union every idea.
- For TypeScript work, include the TS Durability gate only when the classifier says `durabilityRequired: true` or the user explicitly asks.
- Trigger the Production Quality Bar only for near-launch, private-beta, production-bound, hardened, or audited work. When triggered, include release proof such as dry-run/no-mutation evidence, automated GitHub release tags, and explicit deferrals; omit the field when the trigger is absent.
- Stop planning once the first build step and first meaningful proof path are obvious.

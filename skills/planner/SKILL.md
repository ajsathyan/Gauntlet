---
name: planner
description: Use when an accepted spec needs bounded task packets with dependencies, interfaces, proof, risks, deferrals, and a first ready task.
---

# Planner

Shape work into user-valuable implementation steps. Define appetite before scope. Separate mode (`Patch`, `Feature`, `Release`) from depth (`Standard`, `Deep`).

## Output

If a field is outside accepted scope, write `Not relevant because...` instead of stretching the plan. Optional example: read `examples/task-packet.md` only when output shape is ambiguous.

- Problem
- Target outcome
- Appetite
- Mode and depth
- Triggered gates
- Production Quality Bar: triggered near-launch guardrails, release proof, and deferrals, or `Not relevant because...`
- Must-haves
- Non-goals
- Scope pressure and deferrals
- Risks/unknowns
- Verification plan
- Parallelizable lanes: independent tasks that can go to subagents, or `None`
- Subagent manifest: `.gauntlet/subagent-plan.json` or `Not relevant because...`
- Subagent dispatch source: canonical manifest or `Not relevant because...`
- Scope-addition delta: material change or `Scope delta checked: no material change.`
- Ordered **Gauntlet Task Packet** list
- First ready task

## Gauntlet Task Packet

Each task gets a packet. Keep tasks end-to-end unless files, state, and proof are independent enough for parallel subagents.

- Task
- Goal
- Files/areas to inspect
- Files/areas to avoid
- Global Constraints copied verbatim from the spec
- Consumes: prior outputs, exact names, contracts, state, or handles
- Produces: outputs, exact names, contracts, state, or handles
- Steps
- Proof: command, screenshot, benchmark, manual check, or static scan
- Cannot verify: cross-task or external proof the implementer cannot check
- Done when
- Review target: reviewer skill, run log, or coverage gap expected

## Rules

- Use end-to-end steps unless files, state, and proof are independent enough to split.
- Convert uncertainty into probes, checks, explicit assumptions, or Cannot verify items.
- For performance, security, reliability, and hot-path work, include a comparison or adversarial check when appetite allows.
- For parallel lanes, write and validate `.gauntlet/subagent-plan.json` as the sole lane contract before dispatch.
- Do not write Markdown lane handoffs; render with `scripts/check-subagent-plan.py "$PROJECT_ROOT" .gauntlet/subagent-plan.json --render-lane "$LANE_ID"`.
- Share inherited `acceptedSource` and `constraints` at plan level. `dependencies` remains descriptive; it provides no DAG, readiness, or completion state.
- Run scope-addition delta foresight before added scope; use the one-line marker for clean checks.
- Use subagents only for accepted independent manifest lanes; do not split tightly coupled state or one decision tree across workers.
- For Release panels, preserve the launch cut line, panel delta, `| Concern | Decision | Why Not Defer | Proof | Plan Delta |`, and the allowed decisions: `Ship blocker`, `Conditional blocker`, `Manual fallback`, `Private beta gate`, `Defer`, `Reject`.
- A `Ship blocker` needs concrete harm, no acceptable fallback/deferral, executable proof, and a real plan delta; otherwise downgrade it.
- When running duplicate planning prompts for Release risk, compare missing blockers, dependency order, proof requirements, first task, deferrals, and rejections. Do not union every idea.
- For TypeScript work, include the TS Durability gate only when the classifier says `durabilityRequired: true` or the user explicitly asks.
- Trigger the Production Quality Bar only for near-launch, private-beta, production-bound, hardened, or audited work; plan release proof such as CI/local checks, no-mutation or dry-run, automated GitHub release tags/artifacts, and rollback/support evidence.
- Stop planning once the first build step and first meaningful proof path are obvious.

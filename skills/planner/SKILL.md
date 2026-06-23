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
- Must-haves
- Non-goals
- Scope pressure and deferrals
- Risks/unknowns
- Verification plan
- Parallelizable lanes: independent tasks that can go to subagents, or `None`
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
- Review target: reviewer skill or review brief handle expected

## Rules

- Prefer end-to-end steps over component piles.
- Convert uncertainty into probes, checks, explicit assumptions, or Cannot verify items.
- For performance, security, reliability, and hot-path work, include a comparison or adversarial check when appetite allows.
- Use subagents only for independent task packets; do not split tightly coupled state or one decision tree across workers.
- For Release panels, preserve the launch cut line, panel delta, `| Concern | Decision | Why Not Defer | Proof | Plan Delta |`, and the allowed decisions: `Ship blocker`, `Conditional blocker`, `Manual fallback`, `Private beta gate`, `Defer`, `Reject`.
- A `Ship blocker` needs concrete harm, no acceptable fallback/deferral, executable proof, and a real plan delta; otherwise downgrade it.
- When running duplicate planning prompts for Release risk, compare missing blockers, dependency order, proof requirements, first task, deferrals, and rejections. Do not union every idea.
- For TypeScript work, include the TS Durability gate only when the classifier says `durabilityRequired: true` or the user explicitly asks.
- Stop planning once the first build step and first meaningful proof path are obvious.

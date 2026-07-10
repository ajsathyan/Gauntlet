---
name: planner
description: Use when an accepted spec needs one canonical implementation plan with bounded tasks, dependencies, interfaces, proof, risks, deferrals, and a first ready task.
---

# Planner

Turn an accepted direction into one canonical plan. Define appetite before scope. Optional example: `examples/task-packet.md`.

## Output

If a field is outside scope, write `Not relevant because...` instead of padding the plan. Read the optional example only when output shape is ambiguous.

- Problem and target outcome
- Appetite
- Change mode and depth
- Accepted spec/source
- Must-haves and non-goals
- Material assumptions, decisions, and deferrals
- Risks/unknowns and invalidation triggers
- Verification plan
- Parallel lanes with separate files/state/proof, or `None`
- Subagent manifest: `.gauntlet/subagent-plan.json` or `Not relevant because...`
- Scope-addition delta: material change or `Scope delta checked: no material change.`
- Ordered **Gauntlet Task Packet** list
- First ready task

## Gauntlet Task Packet

- Task and goal
- Files/areas to inspect and avoid
- Inherited constraints
- Consumes and produces: exact contracts, state, or handles
- Implementation outline
- Proof: command, screenshot, benchmark, manual check, or static scan
- Cannot verify: external or cross-task proof unavailable to the implementer
- Done when
- Review target

## Rules

- Use one accepted spec and one canonical plan. Intake notes, exploration, and Implementation Memory are not parallel sources of truth.
- Stop planning once the first build step and first meaningful proof path are obvious.
- Use end-to-end steps unless files, state, and proof are independent enough to split.
- Do not use 2-5 minute micro-steps or commits after every mechanical action.
- Do not pre-write production code in the plan. Include code only for a small interface, migration shape, or probe that resolves real ambiguity.
- Compare alternatives in one bounded Deep pass. Use a second plan only for concrete Release-class harm or explicit request.
- Convert uncertainty into probes, explicit assumptions, invalidation triggers, or Cannot verify items.
- When parallelism is earned, `.gauntlet/subagent-plan.json` is the canonical lane contract. Do not write a second Markdown packet; generate prompts from lane entries.
- Validate the manifest before parallel dispatch. Revalidate only when material scope changes reshape lanes.
- Use typed `dependsOn` lane IDs. The first ready lane has no unresolved dependency.
- Do not use subagents for tightly coupled state, overlapping writes, or a single decision tree.
- For guarded Release work, preserve the launch cut line, panel delta, and `| Concern | Decision | Why Not Defer | Proof | Plan Delta |`. Decisions: `Ship blocker`, `Conditional blocker`, `Manual fallback`, `Private beta gate`, `Defer`, or `Reject`. A blocker needs concrete harm, no acceptable fallback, executable proof, and a real delta. Do not union every idea from reviews.
- Trigger the Production Quality Bar only for near-launch, private-beta, production-bound, hardened, or audited work; otherwise mark `Not relevant because...`. When active, make release proof concrete: dry-run or no-mutation evidence, automated GitHub release tags or artifacts when relevant, rollback/support proof, and explicit deferrals.

## Attribution

End-to-end task sizing, explicit interfaces, and execution checkpoints are adapted from Jesse Vincent's Superpowers `writing-plans` and `executing-plans` skills, version 5.1.3 (MIT). Gauntlet intentionally omits prewritten implementation code, mandatory micro-steps, duplicate plan documents, and universal human checkpoints. See `docs/upstream-superpowers.md`.

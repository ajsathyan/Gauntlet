---
name: planner
description: Use when an accepted spec needs one canonical implementation plan with bounded tasks, dependencies, interfaces, proof, risks, deferrals, and a first ready task.
---

# Planner

Create one canonical plan. Optional example: `examples/task-packet.md`.

## Output

Use `Not relevant because...` only for a required field that truly does not apply.

- Problem, target outcome, appetite, mode, and depth
- Accepted spec/source
- Must-haves and non-goals
- Material assumptions, decisions, deferrals, risks, and invalidation triggers
- Verification plan
- Independent parallel lanes, if any
- Subagent manifest: `.gauntlet/subagent-plan.json` only when a child implementation lane requires it
- Scope-addition delta: material change or `Scope delta checked: no material change.`
- Ordered **Gauntlet Task Packet** list
- First ready task

## Gauntlet Task Packet

- Task and goal
- Files/areas to inspect and avoid
- Inherited constraints
- Consumes/produces contracts, state, or handles
- Implementation outline
- Proof and Cannot verify
- Done when
- Review target

## Rules

- Use one accepted spec and one canonical plan; other notes are not parallel sources of truth.
- Stop planning once the first build step and first meaningful proof path are obvious.
- Use end-to-end steps unless files, state, and proof are independent enough to split.
- Avoid 2-5 minute micro-steps and mechanical commits.
- Do not pre-write production code in the plan. Include code only for a small interface, migration shape, or probe that resolves real ambiguity.
- Compare alternatives in one Deep pass; use a second plan only for concrete Release harm or explicit request.
- Convert uncertainty into probes, explicit assumptions, invalidation triggers, or Cannot verify items.
- For two or more parallel lanes or any write-heavy child implementation lane, `.gauntlet/subagent-plan.json` is the canonical lane contract. Generate prompts from it; do not write a Markdown duplicate. A single small read-only child needs no gate.
- Omit the subagent manifest field when no child implementation lane requires it. Successful packet validation stays silent.
- Validate before implementation; revalidate only when material scope changes reshape lanes.
- Store common context once in `shared`. Use typed `dependsOn` IDs and native Codex progress state.
- Do not use subagents for tightly coupled state, overlapping writes, or a single decision tree.
- For guarded Release work, preserve the launch cut line, panel delta, and `| Concern | Decision | Why Not Defer | Proof | Plan Delta |`. Decisions: `Ship blocker`, `Conditional blocker`, `Manual fallback`, `Private beta gate`, `Defer`, or `Reject`. A blocker needs concrete harm, no acceptable fallback, executable proof, and a real delta. Do not union every idea from reviews.
- Trigger the Production Quality Bar only for near-launch, private-beta, production-bound, hardened, or audited work; omit the field when the trigger is absent. When active, make release proof concrete: dry-run or no-mutation evidence, automated GitHub release tags or artifacts when relevant, rollback/support proof, and explicit deferrals.

## Attribution

End-to-end task sizing, explicit interfaces, and execution checkpoints are adapted from Jesse Vincent's Superpowers `writing-plans` and `executing-plans` skills, version 5.1.3 (MIT). Gauntlet intentionally omits prewritten implementation code, mandatory micro-steps, duplicate plan documents, and universal human checkpoints. See `docs/upstream-superpowers.md`.

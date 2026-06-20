---
name: planner
description: Use after intake to shape an accepted spec into bounded, ordered implementation steps with risks, non-goals, proof requirements, and a first ready task.
---

# Planner

Shape work into user-valuable implementation steps. Define appetite before scope. Keep the whole workflow visible: user/system goal, affected interfaces, acceptance criteria, risks, and verification.

Separate mode from depth. Mode is `Patch`, `Feature`, or `Release`; depth is `Standard` or `Deep`. For Patch with Deep depth, keep the patch narrow while planning alternative probes, benchmark/security proof, and the stopping rule for "best enough."

Output:

- Problem
- Target outcome
- Appetite
- Mode and depth
- Ordered implementation steps
- Triggered gates
- Must-haves
- Non-goals
- Scope pressure and deferrals
- Risks/unknowns
- Verification plan
- First ready task

Rules:

- Start from the user or system workflow.
- Prefer end-to-end steps over component piles.
- Convert uncertainty into probes, checks, or explicit assumptions.
- For performance, security, reliability, and hot-path work, plan at least one comparison or adversarial check when appetite allows.
- For Release role panels, produce one launch cut line and one decision table: `| Concern | Decision | Why Not Defer | Proof | Plan Delta |`.
- Use only these panel decisions: `Ship blocker`, `Conditional blocker`, `Manual fallback`, `Private beta gate`, `Defer`, and `Reject`.
- Treat `Ship blocker` as a high bar: concrete user/data/money/security/legal/release harm, no acceptable fallback or deferral, executable proof, and a real panel delta. Downgrade concerns that fail any part of this bar.
- Run an anti-theater check for panels: keep the panel only if the panel delta changes scope, ordering, proof, risk priority, the first ready task, deferral, fallback, launch cut line, or rejects a plausible alternative. Otherwise collapse to a normal plan and say the panel added no unique value.
- For Release, auth, billing, migrations, permissions, privacy, concurrency, data integrity, or ambiguous broad work, run the same planning prompt twice when cost is reasonable. Compare missing blockers, dependency order, proof requirements, first ready task, deferrals, and rejections. Merge only items that pass the decision table. Do not union every idea.
- For Feature, Release, or broad changes, include a scope-discipline note: required new abstractions, likely-obsolete paths, explicit non-goals, and the architecture hygiene proof path. Do not plan speculative generalization.
- For TypeScript work, include the TS Durability gate decision when relevant. Apply heavyweight TypeScript durability standards only when `.gauntlet-ts-durability.json` has `durabilityRequired: true` or the user explicitly asks for them.
- Do not over-specify internals before code discovery.
- Stop planning once the next build step and the first meaningful proof path are obvious.
- Preserve implementer autonomy while making proof requirements clear.

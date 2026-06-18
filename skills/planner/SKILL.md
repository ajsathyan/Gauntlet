---
name: planner
description: Use after intake to shape an accepted spec into bounded, ordered implementation slices with risks, non-goals, proof requirements, and a first ready task.
---

# Planner

Shape work into user-valuable vertical slices. Define appetite before scope. Keep the whole workflow visible: user/system goal, affected interfaces, acceptance criteria, risks, and verification.

Separate mode from depth. Mode is the change shape and risk surface; depth is how hard to search. For Deep Patch, keep the patch narrow while planning alternative probes, benchmark/security proof, and the stopping rule for "best enough."

Output:

- Problem
- Target outcome
- Appetite
- Mode and depth
- Ordered slices
- Must-haves
- Non-goals
- Scope pressure and deferrals
- Risks/unknowns
- Verification plan
- First ready task

Rules:

- Start from the user or system workflow.
- Prefer end-to-end slices over component piles.
- Convert uncertainty into probes, checks, or explicit assumptions.
- For performance, security, reliability, and hot-path work, plan at least one comparison or adversarial check when appetite allows.
- For Release role panels, keep panelists constrained: up to 3 candidate ship blockers, up to 3 deferrals or manual fallbacks, 1 rejected alternative or tradeoff, 1 `do not ship if` condition, and 1 proof requirement each. The engineering lead must classify every panel concern as ship blocker, defer, or reject, then produce one ordered plan with a launch cut line.
- Treat `ship blocker` as a high bar: likely user harm, data/money/security/legal risk, or release regression with no acceptable manual, support, private-beta, or post-launch fallback. Proof must be executable or a concrete manual script.
- Run an anti-theater check for panels: keep the panel only if it changes scope, ordering, proof, risk priority, the first ready task, or rejects a plausible alternative. Include `Panel Changed The Plan: concern -> decision -> plan change -> executable proof or concrete manual proof script`; otherwise collapse to a normal plan and say the panel added no unique value.
- For Slice, Release, or broad changes, include a scope-discipline note: required new abstractions, likely-obsolete paths, explicit non-goals, and the architecture hygiene proof path. Do not plan speculative generalization.
- Do not over-specify internals before code discovery.
- Stop planning once the next build step and the first meaningful proof path are obvious.
- Preserve implementer autonomy while making proof requirements clear.

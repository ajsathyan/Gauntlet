# Run Log: Product Thinking And Proof Scope

Scope: Reposition Gauntlet as a product-thinking harness for AI coding agents and codify seven checks that should scale by smoke, delta, or full proof scope.

## Assumptions

- The strongest user-visible value is thought-through feature shaping and consistency checking, not risk-first positioning.
- The gap model stays as pending backlog-style guidance; no promotion behavior changed in this run.

## Decisions

- Updated README language from prototyping/risk-first framing to product-thinking, coherent-feature framing.
- Added proof scopes: `smoke`, `delta`, `full`, and `not relevant`.
- Made Feature and Release loops explicit about delta/full routing.
- Made the second Release triage pass conditional on findings, deferrals, or follow-ups.
- Made black-box and experience passes scope-aware and combinable for small UI changes.
- Added targeted skill-eval filtering for changed-skill checks while keeping full-suite evals for releases or calibration.
- Documented global install verification as a triggered check, not a default for local-only edits.
- Added implementer guidance for parallel subagents only when task packets have disjoint files, state, and proof.
- Replaced soft planner and product-architect verbs with conditional operating rules.
- Added a subagent context-efficiency guard: do not parallelize when repeated heavy context costs more than the likely speedup.

## Exceptions

- Coverage gaps added: none.
- Things that went wrong: not applicable.
- Cannot verify: no live product feature was changed; proof is limited to workflow checks, skill-change checks, targeted evals, and installed-copy verification.

## Not Relevant Because

- Release proof is not relevant because this is workflow and documentation infrastructure, not a production launch.

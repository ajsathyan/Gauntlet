# Run Log: Workflow Speedup Helpers

Scope: Add advisory changed-surface, test-planning, review-packet, and subagent packet safety helpers for Gauntlet-general workflow speedups.

Proof scope: delta

## Assumptions

- The repeated pain is generic diff/review/test setup, not repo-specific product-surface naming.
- Helper output should reduce shell exploration while preserving agent judgment through confidence and `Cannot verify` fields.

## Decisions

- Implemented `diff-intel.py`, `test-plan.py`, and `review-pack.py` as advisory helpers instead of a `quality-check --surface` gate.
- Kept `quality-check --surface ...` deferred because named surfaces are usually repo-specific and can make Patch work feel heavy.
- Kept child packets bounded to concrete ownership, context, and proof.
- Filtered `.gauntlet/` run artifacts from changed-file discovery so helper-generated files do not pollute follow-up helper runs.

## Exceptions

- Cannot verify: heuristics were validated against synthetic fixture repos and this Gauntlet repo smoke path, not a broad monorepo corpus.
- Cannot verify: no reviewer subagent was spawned because the available subagent tool allows spawning only when the user explicitly asks for delegation.
- Coverage gaps added: none.

## Production Quality Bar

Not relevant because this is workflow tooling, not near-launch app behavior or deploy-sensitive production work.

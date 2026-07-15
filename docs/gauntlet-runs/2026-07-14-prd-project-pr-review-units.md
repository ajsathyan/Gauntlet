# PRD Project PR And Review Units

> Superseded runtime evidence. The active contract now creates one visible task, one Execution Run, and one Project PR per independently shippable Epic. See `docs/prd-execution.md`.

Date: 2026-07-14
Status: Implemented and verified

## Material Decisions

- Small reviewable multi-Epic targets use `single-final-pr`: child checkpoints integrate on the parent branch and one complete Project PR targets `main`.
- Large, tightly coupled targets may use `review-prs-plus-final`: frozen parent-owned Review Unit PRs target the integration branch, followed by the same complete Project PR to `main`.
- Independently shippable outcomes use separate Execution Runs. Review Units are review boundaries, not release boundaries.
- The PR strategy freezes at run initialization. Review Unit Ticket membership and dependencies freeze when the Ticket Graph compiles. Integration and PR topology remain parent-owned and absent from child bundles.
- A run-backed Project PR comes from `prd-run.py project-pr --run <run>` and flows through `gauntlet.py merge prepare|plan|execute --run <run>` as schema v2. Caller-authored schema v1 `--handoff` remains available only for non-run patches.
- Full-PRD proof binds the repository and exact integration head. The installed controller, distinct final-merge authority, GitHub expected-head guard, remote integration reachability checks, and leased cleanup keep the candidate branch and concurrent ref changes from redefining acceptance.

## Exceptions And Limits

- The intermediate surface is `gauntlet.py review-unit prepare|plan|execute --run <run> --unit <id>`.
- The earlier `2026-07-14-parent-integration-branch.md` run log remains historical and now carries a superseded note instead of being rewritten.

## Proof

- Documentation assertions cover frozen strategy selection, Review Unit scope, complete Project PR coverage, parent-only topology, run-backed schema v2 merge, and non-run schema v1 compatibility.
- `python3 scripts/test-prd-run.py` covers controller state, negative controls, repository/head bindings, stale evidence, exact Review Unit dependencies, and legacy tree-SHA compatibility.
- `python3 scripts/check-gauntlet-workflow.py` covers schema v2 rendering, downgrade rejection including custom run roots, installed-controller isolation, authority denial, Project PR head drift, Review Unit head drift, interrupted integration recovery, remote reachability, and leased cleanup.

## Remaining Limits

- Live GitHub behavior is exercised through a local bare remote and deterministic `gh` substitute; the final repository PR sequence provides the live-host proof.
- In-flight runs initialized before PR strategy metadata existed remain on their legacy schema v1 closeout path. New repository/head bindings apply only to newly initialized runs, avoiding an unsafe retroactive proof claim.

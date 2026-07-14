# Parent Integration Branch Workflow

> Superseded on 2026-07-14 by `2026-07-14-prd-project-pr-review-units.md`. The parent integration branch remains authoritative, but the one-final-PR-only policy below has been replaced by a frozen choice between `single-final-pr` and `review-prs-plus-final`, both ending in one complete Project PR to `main`.

## Decision

Multi-Ticket Execution Runs use one parent-owned integration branch and one final PR per run. `main` remains the clean product line. Independent release boundaries should become separate runs rather than task-level PRs merged into local `main`.

The run manifest records the integration branch, parent merge executor after user authority, and PR strategy. Child bundles remain bounded and do not receive run-level Git metadata unless a Ticket needs a named worktree. Run metadata does not grant merge authority.

## Proof and limits

- `scripts/prd-run.py` records and resumes the integration metadata and rejects the default branches as integration targets.
- The source guidance and installer tests cover the parent integration boundary and bounded-context rule.
- This change does not automate creation of Git worktrees or PRs; the parent task and existing merge helper retain those responsibilities.

## Redundancy flags

- The parent-integration/one-final-PR invariant is summarized in the global router and detailed in `docs/prd-execution.md` and `docs/github-discipline.md`. Existing mentions in `docs/workflow-etiquette.md`, `docs/workflow-speedups.md`, and `docs/meaningful-proof.md` are retained as audience-specific references; do not add another full procedure there.
- Merge authority is intentionally repeated in the router, GitHub discipline, workflow etiquette, and the local-document contract because those are separate authority surfaces. The detailed procedure remains in `docs/github-discipline.md`.
- Cache guidance is canonical in `docs/prd-execution.md`; the router and speedup reference should stay short and should not copy the full prefix/token section.

## Follow-up

If future runs show that the default one-PR boundary creates oversized PRs, split the accepted target into separate Execution Runs with explicit release boundaries. Do not add universal agent-count, token, or polling thresholds.

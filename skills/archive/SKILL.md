---
name: archive
description: Use when the user invokes /Archive, asks to archive completed work, or explicitly asks to merge or land completed work on the default branch with full safe closeout. Covers push, PR, required CI, merge, landed-revision verification, configured post-merge monitoring, default-branch sync, and safe branch/worktree cleanup; task archival remains exclusive to /Archive or an explicit archive request.
---

# Archive

Complete one authorized closeout without widening scope. `/Archive` authorizes the scoped commit, push, PR, required checks, merge, landed-revision verification, applicable post-merge monitoring, cleanup, requested local Gauntlet install, and task archival. “Merge this” or “land this” authorizes the same Git closeout, but not local installation or task archival.

## Prepare

1. Confirm completion and current proportional proof.
2. Inspect status and diff. Build an explicit list of intended repository paths; never stage the whole worktree by default.
3. Detect whether the branch belongs to an Execution Run. Run-backed work uses its path and controller-owned schema 3.0 Project PR projection. Non-run work uses a schema v1 handoff outside the repository. Record the exact test result.
4. Create an external Markdown file headed `## Archive Summary`.
5. Supply a conforming `--suggested-title` only when the current title is invalid.

## Execute

Use the repository CLI for Gauntlet changes and the installed CLI otherwise.

For a non-run `/Archive`, invoke `closeout execute` with the schema v1 `--handoff`, every intended `--stage`, title, Archive Summary, and install target when no separate post-merge monitor is configured. When post-merge monitoring applies, use the merge helper first, run that monitor against the landed revision, then run the archive planner.

For an Execution Run, complete required frozen Review Unit PRs first, then use `merge prepare|plan|execute --run <run>` for the Project PR. Never substitute schema v1 `--handoff`. Finish with `archive plan` and `archive execute`. Perform and verify any requested local install separately.

Closeout preflights local installation. Resolve reported conflicts, then rerun with `--instructions-reviewed`, `--response-style gauntlet|existing`, and `--codex-preferences gauntlet|existing|skip`; never bypass preflight.

## Land And Clean Up

Treat explicit merge or land authority as one ordered closeout:

1. Push the scoped branch, open or update a ready PR, and wait for required CI and blocking review state.
2. Merge through the PR, fetch the remote default branch, and verify it contains the accepted head or its tree-equivalent merge.
3. Run established post-merge CI, deployment health, or production monitoring when the repository provides it and the result can be tied to the landed revision. Never invent a monitor or equate PR CI with production health.
4. Only after landed verification and applicable monitoring pass, fast-forward the local default branch, delete the remote task branch, remove a clean isolated worktree, and delete the local task branch.
5. Stop cleanup when unique commits, dirty or untracked work, another worktree, branch drift, or failed monitoring would make deletion unsafe. Preserve the task branch/worktree and report the exact blocker.

Do not archive the Codex task until every required closeout step passes. Generic merge or land requests stop after Git closeout and do not archive the task.

## Finish In Codex

Continue only when JSON status is `pass` or `warn` and `remainingAppActions` exists. Execute actions in order:

1. Rename the current task when `set_thread_title` is returned.
2. Present the returned Archive Summary.
3. Archive the current task with the Codex task-archive tool when `archive_thread` is returned.

Do not emit raw directives or claim archival before the app tool succeeds.

## Output Contract

Return only the PR and merge state, install and proof results, and unresolved risk. `Cannot verify` names missing proof and the next check.

Optional example: read `examples/standard-closeout.md` when the handoff files or returned app-action sequence are unclear.

## Stop Conditions

- Stop before committing when archive inputs are invalid or dirty work falls outside the explicit paths.
- Stop if a run-backed branch is offered a schema v1 handoff, the Project PR projection does not cover the locked target, or required Review Units remain unintegrated.
- Stop without archiving when checks, merge, cleanup, local installation, or archive planning fails.
- Preserve the task branch/worktree when failure occurs before cleanup.
- Do not ask for another confirmation after `/Archive` unless a new material scope, data-loss, permission, or preservation risk appears.

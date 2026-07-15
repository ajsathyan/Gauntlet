---
name: archive
description: Use when the user invokes /Archive or explicitly asks to apply completed work locally, merge it to the default branch through a new pull request, and then archive the current Codex task.
---

# Archive

Complete one authorized closeout without widening scope. An explicit `/Archive` invocation authorizes the task’s scoped commit, push, PR, required checks, merge, cleanup, requested local Gauntlet install, and archival.

## Prepare

1. Confirm completion and current proportional proof.
2. Inspect status and diff. Build an explicit list of intended repository paths; never stage the whole worktree by default.
3. Detect whether the branch belongs to an Execution Run. Run-backed work uses its path and controller-owned schema 3.0 Project PR projection. Non-run work uses a schema v1 handoff outside the repository. Record the exact test result.
4. Create an external Markdown file headed `## Archive Summary`.
5. Supply a conforming `--suggested-title` only when the current title is invalid.

## Execute

Use the repository CLI for Gauntlet changes and the installed CLI otherwise.

For a non-run patch, invoke one `closeout execute` with the schema v1 `--handoff`, every intended `--stage`, title, Archive Summary, and install target.

For an Execution Run, complete required frozen Review Unit PRs first, then use `merge prepare|plan|execute --run <run>` for the Project PR. Never substitute schema v1 `--handoff`. Finish with `archive plan` and `archive execute`. Perform and verify any requested local install separately.

Closeout preflights local installation. Resolve reported conflicts, then rerun with `--instructions-reviewed`, `--response-style gauntlet|existing`, and `--codex-preferences gauntlet|existing|skip`; never bypass preflight.

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
- Preserve the task branch when failure occurs before merge.
- Do not ask for another confirmation after `/Archive` unless a new material scope, data-loss, permission, or preservation risk appears.

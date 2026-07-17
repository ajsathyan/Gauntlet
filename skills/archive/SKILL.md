---
name: archive
description: Use when the user invokes /Archive or explicitly asks to archive completed work. Composes the Gauntlet land flow, any explicitly requested local Codex installation, an Archive Summary, and task archival. Do not trigger for generic merge, land, push-to-main, branch-push, or PR-only requests.
---

# Archive

Complete one authorized archive without widening scope. Read `../land/SKILL.md` completely and use it for the Git closeout. `/Archive` additionally authorizes any explicitly requested local Gauntlet install, the archive plan, and task archival.

## Prepare

1. Confirm completion and current proportional proof.
2. Create an external Markdown file headed `## Archive Summary`.
3. Supply a conforming `--suggested-title` only when the current title is invalid.

## Execute

1. Complete the `land` skill. Stop without archival if it does not pass.
2. Perform and verify any explicitly requested local install. Resolve instruction or preference conflicts through the installer’s normal review flags; never bypass preflight.
3. Run `archive plan` and `archive execute` with the Archive Summary.

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

- Stop without archiving when land, cleanup, local installation, or archive planning fails.
- Preserve the task branch/worktree when failure occurs before cleanup.
- Do not ask for another confirmation after `/Archive` unless a new material scope, data-loss, permission, or preservation risk appears.

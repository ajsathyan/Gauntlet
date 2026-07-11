---
name: archive
description: Use when the user invokes /Archive or explicitly asks to apply completed work locally, merge it to the default branch through a new pull request, and then archive the current Codex task.
---

# Archive

Complete one authorized closeout without widening the accepted scope. An explicit `/Archive` invocation authorizes the current task’s scoped commit, push, PR creation or update, required checks, merge, safe branch cleanup, requested local Gauntlet install, and task archival.

## Prepare

1. Confirm the requested work is complete and proportionally proved. Run the relevant check if its result is not current.
2. Inspect `git status` and the diff. Build an explicit list of intended repository paths; never stage the whole worktree by default.
3. Create a merge-handoff JSON file outside the repository using Gauntlet’s required handoff schema. State the exact test command and result.
4. Create an archive-summary Markdown file outside the repository with an `## Archive Summary` heading and concise outcome bullets.
5. Read the current task title. If it is not in `p#: four word goal` or `p#-auto: four word goal` form, supply a valid four-word `--suggested-title`.

## Execute

Use the repository’s `scripts/gauntlet.py` when changing Gauntlet itself. Otherwise use the installed CLI at `$CODEX_HOME/gauntlet/scripts/gauntlet.py`, falling back to `$HOME/.codex/gauntlet/scripts/gauntlet.py` when `CODEX_HOME` is unset.

Run exactly one shell-side closeout command:

```sh
python3 "$GAUNTLET_CLI" closeout execute \
  --git-root "$PROJECT_ROOT" \
  --handoff "$HANDOFF_PATH" \
  --stage path/to/changed-file \
  --install-target codex \
  --title "$THREAD_TITLE" \
  --suggested-title "p3-auto: complete guarded release closeout" \
  --content "$ARCHIVE_SUMMARY_PATH" \
  --json
```

Repeat `--stage` once for every intended path. Use `--install-target codex` for Gauntlet changes that should become active locally; use `none` for ordinary downstream repositories.

## Finish In Codex

Read the JSON result. Continue only when its status is `pass` or `warn` and `remainingAppActions` is present.

Execute every returned app action in order:

1. Rename the current task when `set_thread_title` is returned.
2. Present the returned Archive Summary.
3. Archive the current task with the Codex task-archive tool when `archive_thread` is returned.

Do not emit raw archive directives or claim the task is archived before the app tool succeeds.

## Output Contract

Return only material closeout facts before the task disappears: PR URL and merged state, local install result, proof result, and any unresolved risk. `Cannot verify` must name any missing app action, merge proof, or install proof and the exact next check. Do not claim completion when `remainingAppActions` is empty because of a failure.

Optional example: read `examples/standard-closeout.md` when the handoff files or returned app-action sequence are unclear.

## Stop Conditions

- Stop before committing when archive inputs are invalid or dirty work falls outside the explicit paths.
- Stop without archiving when checks, merge, cleanup, local installation, or archive planning fails.
- Preserve the committed task branch for recovery when failure occurs before merge.
- Do not ask for another confirmation after an explicit `/Archive` invocation unless a new material scope, data-loss, permission, or preservation risk appears.

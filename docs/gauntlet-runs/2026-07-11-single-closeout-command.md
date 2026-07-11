# Single Closeout Command

## Decision

- Add `gauntlet.py closeout execute` for the explicit instruction to apply Gauntlet locally, merge it through a PR, and archive the task.
- Require repeated `--stage` arguments so the command never infers commit scope from a mixed worktree.
- Validate the handoff, archive summary, and current or suggested task title before creating a commit.
- Reuse the existing PR checks and merge policy instead of adding a second merge implementation.
- Install from the fast-forwarded default branch only after the merge is verified.
- Return Codex app actions rather than pretending a local process can rename or archive a Codex task.
- Expose the flow through the installed `/Archive` skill so the invocation itself carries the accepted closeout authority and procedure.

## Recovery

- Before the commit, validation failures leave source files untouched except for work the user already had.
- After a closeout commit, a safe retry is allowed only when the tip commit title and the complete default-branch diff match the declared handoff and `--stage` scope.
- Merge, cleanup, install, or archive-planning failures stop later actions and return no archive action.

## Proof

- A temporary-repository integration test covers archive preflight, explicit staging, commit creation, PR creation, check waiting, merge, remote and local branch cleanup, default-branch sync, and ordered app-action output.

## Things That Went Wrong

- The first implementation validated archive inputs after merge. Review moved that validation before the commit so malformed task metadata cannot fail only after an irreversible merge.
- Default Git status output collapsed new skill directories into one path. Closeout now requests every untracked file so repeated `--stage` paths can match and protect nested new files precisely.

## Limitation

- `remainingAppActions` still require the calling Codex agent to invoke the app tools. This preserves the app trust boundary while keeping all shell-side closeout work in one CLI execution.
- Cannot verify slash-menu discovery until the merged skill is installed and Codex reloads; file installation and skill validation are automated proof, while UI discovery remains a reload-time check.

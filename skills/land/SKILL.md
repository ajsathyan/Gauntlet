---
name: land
description: Publish one exact verified candidate through the established pull-request format, direct merge, landed proof, and safe cleanup.
---

# Land

The accepted Design or Normal Request authorizes the scoped Git lifecycle. No
second routine acceptance is required.

## Prepare

1. Require passing Build and applicable Architecture verdicts for the exact local candidate commit and tree.
2. Require the Verify binding to include the checked remote/default-branch base.
3. Inspect status, diff, branch, worktrees, automation, and release documentation.
4. Resolve the writable head remote separately from the PR base repository and
   default branch. Fail on zero or multiple valid identities; do not create an `origin` alias.
5. Fetch immediately before merge. Refuse a changed candidate or known base drift
   until the candidate is updated and affected Verify passes again.

## Pull request and merge

Use the established title and body format: Problem, Solution, Changelog, Testing,
and Security / Risk only when material. Testing text is an evidence pointer.

```sh
python3 scripts/gauntlet.py land execute \
  --git-root "$PROJECT_ROOT" --handoff "$HANDOFF" --body "$PR_BODY" --json
```

Land pushes, creates or updates the ready PR, waits for required checks and
blocking reviews, and directly merges with the expected head. Gauntlet has no
queue or auto-merge requirement. Direct unprotected merge retains a narrow race
after the last base comparison; verify the landed revision and recover ad hoc if
integration changed behavior.

Clean up only state proven represented by the landed revision. Preserve modified
files, unique commits, drift, other worktrees, or failed monitoring.

Return PR and merge state, exact landed proof, monitoring state, cleanup state,
and unresolved risk.

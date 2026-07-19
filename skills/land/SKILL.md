---
name: land
description: Use when the user explicitly asks to merge or land completed work on the repository’s default branch. Completes the verified generic GitHub closeout without granting installation, deployment, production, or archival authority.
---

# Land

Land one verified branch through its pull request and clean up only safe Git
state.

## Authority

- A branch push or pull-request request stops before merge.
- “Merge,” “land,” “ship to main,” or “push to main” authorizes this flow.
- Installation, deployment, production changes, migration, destructive or paid
  actions, credential use, rollback, and task archival retain separate authority.

Proceed without another confirmation unless scope, preservation, credentials, or
another material choice becomes unresolved.

## Prepare

1. Confirm the exact candidate has passing Build, Architecture, and Sensor
   verdicts where applicable.
2. Inspect status, diff, branch, worktrees, remote default branch, and the
   source-bound merge handoff. Name every intended path and preserve unrelated
   work.
3. Use local `git` and authenticated `gh` by default. Use a GitHub connector only
   when the user requests it or `gh` cannot perform the required operation.
4. Commit only intended paths. Keep coherent atomic commits and never stage the
   whole worktree by default.
5. Run the read-only merge preflight against the current branch, handoff, PR
   body, default head, and required checks.

## Land

Use the repository's generic closeout:

```sh
python3 scripts/gauntlet.py land execute \
  --git-root "$PROJECT_ROOT" \
  --handoff "$HANDOFF" \
  --body "$PR_BODY" \
  --json
```

The flow pushes the scoped branch, creates or updates the ready pull request,
waits for required CI and blocking review state, merges through the pull request,
and verifies that the remote default branch contains the accepted head or a
tree-equivalent merge.

Run established post-merge CI or health monitoring only when the repository
provides it and the result is attributable to the landed revision. Pull-request
CI does not prove production health.

## Clean up

After landed verification and applicable monitoring pass:

1. fast-forward the checkout that owns the local default branch without
   disturbing user files;
2. confirm remote branch deletion;
3. remove a clean isolated worktree;
4. delete the local task branch.

Preserve the branch or worktree when unique commits, modified files, branch
drift, another worktree, or failed monitoring makes cleanup unsafe.

## Output

Return the pull-request and merge state, landed-revision proof, cleanup state,
and unresolved risk. Use `Cannot verify` for missing proof and name the next
check.

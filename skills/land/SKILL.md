---
name: land
description: Use when a verified implementation is ready to push, open or update its pull request, merge to the default branch, and monitor the landed revision.
---

# Land

Land one verified branch through its pull request and clean up only safe Git
state.

## Authority

- For a Normal Request, the implementation request authorizes the scoped Git lifecycle. For non-trivial work, the accepted Design/PRD authorizes it.
- No second acceptance is required between commit, branch push, pull-request creation, merge, and ordinary merge-triggered deployment.
- Inspect repository automation and release documentation before merge. Stop only when the merge would cause an unexpected destructive, paid, credential, migration, privacy, security, or production effect outside the accepted scope.
- Installation and rollback retain separately scoped authority.

## Prepare

1. Confirm the exact candidate has passing Build and applicable Architecture verdicts.
2. Inspect status, diff, branch, worktrees, remote default branch, and source-bound merge handoff. Preserve unrelated work.
3. Inspect default-branch automation and release documentation so ordinary deployment effects are understood.
4. Use local `git` and authenticated `gh` by default. Use a GitHub connector only when requested or when `gh` cannot perform the operation.
5. Commit only intended paths and run the read-only merge preflight against the current branch, handoff, PR body, default head, and required checks.

## Land

```sh
python3 scripts/gauntlet.py land execute \
  --git-root "$PROJECT_ROOT" \
  --handoff "$HANDOFF" \
  --body "$PR_BODY" \
  --json
```

The flow pushes the scoped branch, creates or updates the ready pull request,
waits for required CI and blocking review state, merges through the pull
request, verifies the remote default branch contains the accepted head or a
tree-equivalent merge, and monitors attributable exact-revision push workflows.
Pull-request CI does not prove production health.

## Clean up

After landed verification and applicable monitoring pass, fast-forward the
checkout that owns the local default branch, confirm remote branch deletion,
remove a clean isolated worktree, and delete the local task branch. Preserve
anything with unique commits, modified files, drift, another worktree, or failed
monitoring.

## Output

Return pull-request and merge state, landed-revision proof, deployment-monitor
state, cleanup state, and unresolved risk. Use `Cannot verify` for missing proof.

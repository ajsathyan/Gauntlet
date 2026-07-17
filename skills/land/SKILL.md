---
name: land
description: Use when the user explicitly asks to merge, land, ship, or push completed work to GitHub’s default branch, including “merge this,” “land this,” “push this to main,” or “open a PR and merge it.” Completes ready PR creation, required CI, merge, landed-revision checks, configured post-merge monitoring, default-branch sync, and safe branch/worktree cleanup. Do not use for a branch-only push, draft PR, or PR creation without merge authority.
---

# Land

Land one accepted scope through GitHub and clean up its Git state. Do not install locally, deploy, or archive the Codex task unless the user separately authorizes that action.

## Authority

- “Push this branch” authorizes only the current branch push.
- “Open a PR” authorizes a PR but not merge.
- “Merge,” “land,” “ship to main,” or “push to main” authorizes the complete flow below.
- Do not ask for another confirmation unless scope, preservation, credentials, or another material choice becomes unresolved.

## Prepare

1. Confirm accepted behavior and proportional proof.
2. Inspect status, diff, branch, remote default branch, and worktrees. List intended paths explicitly; preserve unrelated work.
3. Use local `git` and `gh` by default. Run `gh auth status`; use a GitHub connector only when the user explicitly requests it or `gh` cannot perform a required operation.
4. Detect an Execution Run. Run-backed work uses its controller-owned schema 3.0 Project PR projection. A non-run patch uses an external schema v1 handoff.
5. Commit only intended dirty paths. Never stage the whole worktree by default.

## Land

Use the repository Gauntlet CLI for Gauntlet changes and the installed CLI otherwise. After `merge prepare` has produced the exact PR body, run the complete flow with:

- `python3 scripts/gauntlet.py land execute --handoff <handoff.json> --body <pr.md> --json` for a non-run patch.
- `python3 scripts/gauntlet.py land execute --run <run> --body <pr.md> --json` for an Execution Run after its frozen Review Unit PRs complete. Never substitute a caller-authored handoff.
- Push the scoped branch, create or update a ready PR, and wait for required CI and blocking review state.
- Merge through the PR. Fetch the remote default branch and verify it contains the accepted head or a tree-equivalent merge.
- Run established push-to-default CI, deployment health, or production monitoring only when the repository provides it and the result is attributable to the landed revision. PR CI is not production proof.

## Clean Up

After landed verification and applicable monitoring pass:

1. Fast-forward the checkout that owns the local default branch without disturbing dirty or untracked user files.
2. Confirm the remote task branch is deleted.
3. Remove a clean isolated worktree.
4. Delete the local task branch.

Stop cleanup and preserve the branch/worktree when unique commits, dirty work, branch drift, another worktree, or failed monitoring makes deletion unsafe.

## Output

Return only the PR and merge state, landed-revision proof, cleanup state, and unresolved risk. Use `Cannot verify` for missing proof and name the next check.

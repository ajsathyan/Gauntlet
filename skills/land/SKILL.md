---
name: land
description: Publish one exact verified candidate through the established pull-request format, direct merge, landed proof, and safe cleanup.
---

# Land

The accepted Design or Normal Request authorizes the scoped Git lifecycle. Do not
ask for a second routine acceptance.

## Bind and inspect

1. Require an independent Verify report with Build `Passed`, Architecture
   `Passed` or `Not applicable`, and the exact repository, candidate commit, tree,
   and checked base. Treat it as an omission and drift guard, not authenticated
   proof or approval.
2. Use native Git to confirm the candidate exists and resolves to the reported
   tree. Inspect status, staged/unstaged/untracked paths, branch, worktrees,
   candidate diff, release conventions, and repository automation. Preserve dirty
   or unrelated work.
3. Resolve the writable head remote separately from the PR base repository and
   default branch. Use remote URLs, existing PR metadata, and `gh repo view` as
   evidence. Handle forks explicitly; fail on zero or multiple valid identities
   and never invent an `origin` alias.
4. Fetch the base repository directly or through its configured remote. Refuse a
   changed candidate, tree mismatch, or checked-base drift until affected Verify
   passes again.

## Pull request and merge

Push the exact candidate to the chosen head branch with a native non-force push.
If an existing branch is not a fast-forward, stop, fetch it, inspect its unique
commits, and preserve them. Ordinary lifecycle acceptance does not authorize
rewriting published history. Rewrite only with existing explicit authority for
that rewrite, proof that unrelated commits are preserved, and an exact observed
lease; otherwise publish a new branch. Create or update a ready pull request with
these sections: Problem, Solution, Changelog, Testing, and Security / Risk only
when material. Testing points to evidence. The PR Changelog section is required,
but a repository changelog file is changed only when that repository's own
conventions require it.

Use `gh pr checks --required --watch` or equivalent repository-policy evidence to
wait only for required checks. If none are required, generic CI is not required.
Inspect the review decision and stop for blocking reviews. Gauntlet has no merge
queue or auto-merge requirement.

Immediately before merging:

- re-fetch the PR base and compare it with the checked base;
- confirm the PR head object is the verified candidate; and
- confirm the remote head branch has not changed.

Directly merge with the repository's permitted method and native expected-head
matching, such as `gh pr merge --match-head-commit <candidate>`. If expected-head
matching is unavailable, stop rather than approximate it with a custom wrapper.
An unprotected base can still move in the narrow comparison-to-merge interval;
check the landed result and recover ad hoc if that race changes behavior.

Fetch the landed revision, record its object ID and tree, and confirm the pull
request reports merged. When the verified base did not drift, the landed tree
must equal the candidate tree; otherwise do not claim the candidate landed.

## Cleanup

Remove a remote branch only with an expected-object-ID lease, for example
`git push --force-with-lease=refs/heads/<branch>:<candidate> <head-remote> :refs/heads/<branch>`.
A moved ref must make deletion fail. Immediately before local cleanup, recheck
the worktree status and branch tip. Remove a local branch or worktree only when
its tip is still the exact verified candidate, the landed revision represents it,
and no dirty or unique work can be lost. Never remove another worktree just
because it shares the branch name. Synchronize a local default branch only when
it can fast-forward without overwriting changes.

Return PR and merge state, writable-head and PR-base identities, exact landed
proof, required-check/review evidence, cleanup state, and unresolved risk.
Deployment and monitoring belong to Ship.

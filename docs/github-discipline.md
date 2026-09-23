# GitHub Discipline

The default path is:

```text
accepted scope -> coherent candidate commit -> independent exact Verify
-> ready PR -> direct merge -> landed proof -> declared deployment observation
```

Verify reports the repository, candidate commit, tree, and checked base in plain
language or a Markdown table. Land checks those objects again with native Git.
The report is an explicit coordination boundary, not authenticated enforcement.

Land resolves two identities when needed: the writable remote for the head branch
and the base repository/default branch for the pull request. Existing PR metadata,
remote URLs, and `gh repo view` distinguish them in fork workflows. Ambiguity is a
failure; creating an `origin` alias is not a fix.

Fetch before push and immediately before merge. Refuse candidate, head, or known
base drift until affected outcomes are verified again. Use non-force,
fast-forward pushes by default. A divergent published branch is preserved unless
an already-explicit rewrite authority covers it, unrelated commits are retained,
and an exact observed lease guards the rewrite; otherwise use a new branch. Use
GitHub's expected-head match when merging. Gauntlet has no durable queue or
auto-merge requirement. Direct merge on an unprotected base retains a narrow
comparison-to-merge race, so fetch and prove the landed revision afterward.

Pull requests use the established Problem, Solution, Changelog, and Testing
sections, plus Security / Risk when material. Testing prose points to evidence;
it is not proof. The PR Changelog section never forces a `CHANGELOG.md` edit.

Only repository-required checks and blocking reviews stop Land. No required
checks means CI is not required. Delete a remote branch only with an
expected-object-ID lease so an intervening update makes deletion fail. Recheck
local status and the local ref immediately before cleanup. Remove only refs and
worktrees whose exact tip is represented by the landed revision, and preserve
dirty paths, unique commits, branch drift, and unrelated worktrees.

Ship begins after Land confirms the merge. It observes configured deployments
already triggered by that merge; it does not dispatch CI or deployment workflows.
No declared deployment is `Not configured`. Missing attributable deployment or
production evidence is `Cannot verify`, never inferred health.

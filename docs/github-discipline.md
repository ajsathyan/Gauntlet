# GitHub Discipline

The default path is:

```text
accepted scope -> coherent candidate commit -> exact Verify -> PR -> direct merge
-> landed proof -> declared deployment -> attributable monitoring
```

Land resolves two identities when needed: the writable head remote for push and
the base repository/default branch for comparison and merge. It fails on
ambiguity and never creates an `origin` alias merely to satisfy tooling.

Verify binds candidate commit, tree, and checked base. Land fetches before merge
and refuses changed candidate or known base drift until affected Verify passes
again. Gauntlet has no durable queue, GitHub merge-queue requirement, or auto-merge
requirement. Direct unprotected merge retains a small comparison-to-merge race;
verify the landed revision and recover ad hoc if it matters.

Pull requests use one established format: Problem, Solution, Changelog, Testing,
and Security / Risk only when material. Testing prose points to evidence; it is
not proof.

Clean up only state represented by the landed revision. Preserve modified files,
unique commits, branch drift, other worktrees, and failed-monitoring evidence.

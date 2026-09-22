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

The merge handoff declares verification separately from its general source
binding:

```json
{
  "verification": {
    "build": "Passed",
    "architecture": "Passed",
    "sourceBinding": {
      "repository": "/absolute/path/to/repository",
      "commit": "<exact-git-object-id>",
      "tree": "<exact-git-object-id>",
      "base": "<exact-git-object-id>"
    }
  }
}
```

Architecture may be `Not applicable`. Plan, execute, and Land reject missing,
non-passing, or stale declarations before push or pull-request mutation. This is
a declarative omission and drift check, not authentication of proof or approval.
`merge prepare` may render local PR material before Verify without this block;
handoff and body files can remain outside the candidate tree.

Pull requests use one established format: Problem, Solution, Changelog, Testing,
and Security / Risk only when material. Testing prose points to evidence; it is
not proof. The Changelog section does not require a `CHANGELOG.md` file or mutate
one automatically; follow the target repository's own release-note conventions.

Clean up only state represented by the landed revision. Preserve modified files,
unique commits, branch drift, and other worktrees. Deployment and monitoring begin
in Ship, after Land has confirmed the merge and synchronized local state. Only
repository-required checks block Land; absent required checks, CI is not required,
and Gauntlet does not recommend adding it solely for its own workflow. Ship
observes intentionally configured deployments already triggered by the merge; it
does not dispatch or rerun them or generic CI, require generic CI, or invent
or require synthetic monitoring. With no declared deployment, report `Not
configured`; with missing attributable proof, report `Cannot verify`.

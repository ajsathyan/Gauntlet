# GitHub Discipline

Gauntlet Lite keeps the Git path simple enough for a solo builder and strict enough to preserve exact-revision evidence.

## Default path

```text
accepted Design / PRD
  -> branch from the current default head
  -> coherent atomic commits
  -> independent exact-revision verification
  -> one coherent pull request
  -> merge to the default branch
  -> ordinary declared deployment
  -> attributable post-merge monitoring
```

`main` is the product line. A branch is a bounded side lane. A worktree is an isolated folder for broad, dirty, or parallel writes. A commit is one reviewable behavior or invariant. A pull request preserves the problem, resulting behavior, proof, and landing boundary.

## Parent and delegated lanes

The parent owns the integration branch, product meaning, shared contracts, publication, merge, release, and rollback. Implementation children own disjoint files or state and return changed artifacts, compact proof, and risk. Read-only children return findings. Children do not publish or merge independently.

Integrate one coherent current-base candidate at a time. A changed base invalidates stale candidate proof; re-integrate and rerun affected checks against the new exact revision. Native Codex state is sufficient for coordination. Gauntlet Lite does not maintain a durable integration queue.

## Commits and pull requests

Prefer one pull request for one coherent requested scope. Use additional pull requests only for independently shippable outcomes. Keep commits coherent rather than artificially tiny. Default to the repository's established merge policy.

Use `<area>: <imperative behavioral outcome>` for commit subjects and pull-request titles.

A useful pull-request body contains:

1. **Problem:** who is affected and what was insufficient.
2. **Solution:** resulting behavior, important boundaries, and preserved behavior.
3. **Changelog:** the exact `Unreleased` entry when the repository uses one.
4. **Testing:** commands, the claim each supports, and any limitation.
5. **Security / Risk:** only for a concrete material risk.

The diff fact-checks this story; it does not define product intent.

## Authority and production

Explicit acceptance of a non-trivial Design/PRD authorizes scoped local commits, implementation branch push, pull-request creation, default-branch merge, and the repository's ordinary declared production deployment. A request limited to commit, push, or PR creation still stops at that stated boundary.

Before landing, inspect repository automation and release documentation. If the expected merge-triggered or standard deployment is inside the accepted Design/PRD, proceed without a second production acceptance. After merge, run repository-owned post-merge monitoring when it exists and can be attributed to the landed revision. Pull-request CI does not prove production health.

Stop when the discovered effect is outside the accepted scope or introduces unresolved destructive, paid, credential, migration, privacy, security, or preservation risk. Installation and rollback remain separately scoped.

The generic merge path consumes a source-bound handoff:

```sh
python3 scripts/gauntlet.py merge prepare \
  --git-root "$PROJECT_ROOT" --handoff "$HANDOFF" --json

python3 scripts/gauntlet.py merge plan \
  --git-root "$PROJECT_ROOT" --handoff "$HANDOFF" --body "$PR_BODY" --json
```

The `land` skill may then use `land execute` with the same handoff and body. It waits for required checks and blocking review state, merges through the PR, verifies default-branch reachability, and performs only safe cleanup. The `ship` skill owns post-merge deployment follow-through and monitoring.

## Preservation

Never stage the entire worktree by default. Name intended paths and preserve unrelated dirty or untracked work. Stop cleanup when unique commits, modified files, branch drift, another worktree, or failed monitoring makes deletion unsafe.

When cutting a version, move only shipped entries beneath the version heading and keep `Unreleased` for future work.

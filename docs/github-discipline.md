# GitHub Discipline

Gauntlet keeps the Git path simple enough for a solo builder and strict enough
to preserve evidence.

## Default path

```text
branch from the current default head
  -> coherent atomic commits
  -> one current-base integration candidate
  -> independent exact-revision verification
  -> one coherent pull request
  -> non-production merge under implementation authority
  -> explicit acceptance before any production consequence
```

`main` is the product line. A branch is a bounded side lane. A worktree is an
isolated folder for a branch and is useful when the current checkout is dirty or
parallel work needs separate files. A commit is one reviewable behavior or
invariant. A pull request preserves the problem, resulting behavior, proof, and
landing boundary.

## Parent and workstreams

The parent owns the integration branch, shared contracts, publication, merge,
release, and rollback.

Implementation children own disjoint files or state and return changed artifacts,
compact proof, and risk. Read-only children return findings. Children do not push
to the default branch or decide to merge.

Integrate coherent atomic candidates as they arrive. When candidates share a
base, serialize them through the generic workstream queue:

1. enqueue against the source commit;
2. claim the oldest ready candidate against the current default head;
3. bind the exact candidate commit and tree;
4. release only after integration or a terminal failure;
5. reconcile interrupted attempts from observable Git state.

A changed base invalidates stale candidate proof. Rebase or re-integrate, then
rerun the affected checks against the new exact revision.

## Commits and pull requests

Prefer one pull request for one coherent requested scope. Use additional pull
requests only for independently shippable outcomes, not as a substitute for
clear workstream ownership.

Keep commits coherent rather than artificially tiny. Preserve useful checkpoints
when each can be understood and verified on its own. Default to a merge commit
unless repository policy or the user requires squash or rebase.

Use `<area>: <imperative behavioral outcome>` for commit subjects and pull-request
titles.

A useful pull-request body contains:

1. **Problem:** who is affected and what was insufficient.
2. **Solution:** resulting behavior, important boundaries, and preserved behavior.
3. **Changelog:** the exact `Unreleased` entry when the repository uses one.
4. **Testing:** commands, the claim each supports, and any limitation.
5. **Security / Risk:** only for a concrete material risk.

The diff fact-checks this story; it does not define product intent.

## Authority

- An implementation request authorizes scoped local commits, the implementation
  branch push, pull-request creation, and non-production merge.
- A standalone request limited to commit, branch push, or pull-request creation
  stops at its stated boundary.
- “Merge,” “land,” or “ship to main” authorizes the verified merge flow for
  existing work that did not originate from an implementation request.
- Every deployment or production change requires separate explicit acceptance.
- Installation, destructive or paid actions, credential use, rollback, and task
  archival remain separately scoped.

Use local `git` and authenticated `gh` by default. Use a GitHub connector only
when the user requests it or the CLI cannot perform the required operation.

The generic merge path consumes a source-bound handoff:

```sh
python3 scripts/gauntlet.py merge prepare \
  --git-root "$PROJECT_ROOT" --handoff "$HANDOFF" --json

python3 scripts/gauntlet.py merge plan \
  --git-root "$PROJECT_ROOT" --handoff "$HANDOFF" --body "$PR_BODY" --json
```

Before landing, inspect repository automation and release documentation. If
merge deploys, publishes, migrates, or otherwise changes production, stop and
present the production acceptance request described by `ship`.

For a non-production merge, the `land` skill may use `land execute` with the same
handoff and body without another acceptance pause. It waits for required checks
and blocking review state, merges through the PR, verifies default-branch
reachability, and performs only safe cleanup. Repository-owned post-merge
monitoring runs only when it exists and can be attributed to the landed
revision.

## Preservation

Never stage the entire worktree by default. Name intended paths and preserve
unrelated dirty or untracked work. Stop cleanup when unique commits, modified
files, branch drift, another worktree, or failed monitoring makes deletion
unsafe.

When cutting a version, move only shipped entries beneath the version heading
and keep `Unreleased` for future work. Released history is immutable.

---
name: land
description: Publish one exact verified candidate through the established pull-request format, direct merge, landed proof, and safe cleanup.
---

# Land

The accepted Design or Normal Request authorizes the scoped Git lifecycle. No
second routine acceptance is required.

## Prepare

1. Require the merge handoff to declare Build `Passed` and Architecture
   `Passed` or `Not applicable` under `verification`.
2. Require `verification.sourceBinding` to independently bind those verdicts to
   the exact repository, candidate commit, tree, and checked
   remote/default-branch base. This is an omission and drift check, not
   authentication of evidence or user approval.
3. Inspect status, diff, branch, worktrees, automation, and release documentation.
4. Resolve the writable head remote separately from the PR base repository and
   default branch. Fail on zero or multiple valid identities; do not create an `origin` alias.
5. Fetch immediately before merge. Refuse a changed candidate or known base drift
   until the candidate is updated and affected Verify passes again.

## Pull request and merge

Use the established title and body format: Problem, Solution, Changelog, Testing,
and Security / Risk only when material. Testing text is an evidence pointer.
The PR Changelog section is always required; update a repository changelog only
when that repository's own conventions require it.

The exact verification shape is:

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

Architecture may instead be `Not applicable`. `merge prepare` may render local
PR material before Verify without this block; plan, execute, and Land require it.
Keep handoff and generated PR-body files outside the candidate tree when needed
to avoid self-binding artifacts.

```sh
python3 scripts/gauntlet.py land execute \
  --git-root "$PROJECT_ROOT" --handoff "$HANDOFF" --body "$PR_BODY" --json
```

Land pushes, creates or updates the ready PR, waits only for checks required by
the repository's branch policy and for blocking reviews, and directly merges with
the expected head. When no checks are required, Land does not require CI and
proceeds without it. Never recommend adding CI solely to satisfy Gauntlet.
Gauntlet has no queue or auto-merge requirement. Direct unprotected merge retains
a narrow race after the last base comparison; verify the landed revision and
recover ad hoc if integration changed behavior.

Clean up only state proven represented by the landed revision. Preserve modified
files, unique commits, drift, or other worktrees.

Return PR and merge state, exact landed proof, cleanup state, and unresolved risk.
Deployment and monitoring belong to Ship.

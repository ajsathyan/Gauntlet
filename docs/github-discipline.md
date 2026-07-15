# GitHub Discipline

Gauntlet's default Git strategy is for builders who are new to Git, working quickly, and relying on agents to do the disciplined parts that people often skip. Advanced users can override it, but the default should be boring, professional, and easy to adopt.

## Default Opinion

Use the startup-safe path for real repository changes:

```text
branch from main -> commit coherent checkpoints -> open a PR -> verify -> merge with a merge commit -> delete the branch
```

For one Epic Run, the parent branch is the integration boundary. The run freezes one of two review topologies at initialization:

```text
small target:
main <- complete Project PR <- parent integration branch <- child checkpoints

large, tightly coupled target:
main <- complete Project PR <- parent integration branch <- parent-owned Review Unit PRs <- child checkpoints
```

Independently shippable outcomes belong in separate Execution Runs. Review Unit PRs target only the integration branch and never replace the complete Project PR to `main`.

This gives solo builders and AI-assisted teams a durable trail: what changed, who or which agent did it, what proof ran, what review happened, and why the work landed.

## Beginner Mental Model

- `main` is the clean product line. Do not do real work directly there unless the user has chosen that shortcut.
- A branch is a safe side lane for one task.
- A worktree is a separate folder for a branch. Use it when the current folder has unrelated dirty files or parallel child work needs isolation.
- A commit is a checkpoint with a meaningful reason to exist.
- A PR is the memory and proof bundle for landing the work.
- A merge commit keeps the branch's checkpoint commits visible after the PR lands.

## Defaults By Work Type

| Work | Branch/worktree default | Commit default | PR default | Merge default |
| --- | --- | --- | --- | --- |
| `p4` brainstorm, research, admin | No branch unless creating a repo artifact | No commit unless preserving an artifact | No PR unless files should land in the repo | Not relevant |
| `p3` Patch | Branch from `main`; use a worktree if the workspace is dirty | One small, coherent commit with proof | Yes for any persisted code, docs, or policy change | Merge commit |
| `p2` Deep or high-consequence Patch | Branch or worktree | Atomic commits by fix, invariant, or test boundary | Required | Merge commit after checks |
| `p1` Feature | Worktree or branch | Checkpoint commits per coherent slice | Required, with proof and run-log context when relevant | Merge commit |
| `p0` Release or risky work | Isolated worktree or branch | Checkpointed, reviewable commits | Required, with an explicit decision gate | Merge commit only after gate and checks |

## Main Chats And Child Chats

The main chat owns the final Git story:

- Selects or creates the task branch.
- For one Epic Run, selects or creates its parent integration branch and freezes `single-final-pr` or `review-prs-plus-final`; child branches do not target `main`.
- Tracks child-lane decisions and integration state without printing a routine lane ledger.
- Integrates child implementation work.
- Opens or updates parent-owned Review Unit PRs when the compiled graph requires them, then opens the complete Project PR.
- Decides whether checks and review are enough to merge.

Child chats should stay bounded:

- Read-only review, research, summarization, and log-analysis lanes return reports, not commits.
- Implementation child chats use separate branches or worktrees when they write code, touch multiple files, or have uncertain ownership.
- Child chats do not direct-push to `main`.
- Implementation children return compact machine receipts with status, changed files, evidence pointers, and any blocker. Research and review children return their requested result compactly.

## Solo Builder Rules

Gauntlet should make the disciplined path cheap enough that solo builders use it by default:

- Prefer a PR even when nobody else will review it. The PR still records proof, context, and the merge boundary.
- Preserve useful agent checkpoint commits instead of squashing them away.
- Keep commits coherent rather than perfectly tiny. A good commit should explain one useful step in the work.
- Direct push to `main` is an explicit shortcut for tiny, low-risk solo changes, not the default taught path.
- If the workspace is dirty, first decide whether the dirty files belong to this task. If not, isolate new work in a worktree or ask before touching them.

## Merge Method

Gauntlet's automation default is merge commit.

Use merge commits because they preserve the branch's checkpoint commits and keep the PR as a visible boundary in history. This is especially useful for AI-assisted work, where the intermediate commits can show which agent or lane made a change and which proof happened before merge.

Use squash only when the user or repository explicitly prefers a linear history. Use rebase only when the repository's contribution rules require it or a maintainer asks.

## What Belongs In Automation

CLI helpers should own objective Git and GitHub facts:

- Dirty files and whether they are allowlisted.
- Current branch and upstream ahead/behind state.
- Whether the branch is the default branch.
- Whether a PR exists, is open, is mergeable, has passing checks, and has no blocking review state.
- The exact safe merge command for accepted automation.

Human or agent judgment should remain conversational:

- Whether a solo repo wants to opt out of branch protection.
- Whether a specific dirty file belongs to the task.
- Whether to abandon, park, or preserve uncommitted work.
- Whether a repo's history preference should override Gauntlet's merge-commit default.
- Whether a task is too risky to merge without human review.

## Changelog And Closeout

"Merge this," "land this," or "merge this to main" authorizes the complete safe closeout for the current scoped work: prepare the non-run handoff or run-backed Project PR projection, update `CHANGELOG.md`, commit coherent local changes, push the task branch, create or update the applicable PR, wait for required checks and blocking review state, merge, delete the remote branch, verify the default branch, and remove local branch/worktree state only when no unique work remains.

"push to git" means push the current branch. It does not imply direct-push to `main` or merge.

Use `scripts/gauntlet.py merge prepare` before committing the changelog, `scripts/gauntlet.py merge plan` for a read-only preflight, and `scripts/gauntlet.py merge execute` after the worktree is clean. For an Epic Run, pass `--run <run>` so the helper consumes schema 3.0 facts and verifies the locked Epic, graph, repository, branch, exact head, and final Epic verification binding. For a non-run Patch, pass schema v1 `--handoff <handoff.json>`. Never downgrade a run-bound branch to `--handoff`.

With `review-prs-plus-final`, the parent uses `scripts/gauntlet.py review-unit prepare|plan|execute --run <run> --unit <id>` to bind each frozen unit PR to the current integration base and exact GitHub head, wait for checks, merge serially, and verify the tested tree before preparing the Epic's Project PR. In both strategies, `merge ... --run` creates or updates that Project PR, requires distinct `merge-to-default` authority, binds the merge to the verified head, verifies default-branch reachability, records the merge in the run, and cleans with leases. Run-backed commands use the installed controller; candidate repositories cannot substitute their own verifier.

For explicit standalone drafts, use `scripts/gauntlet.py changelog pr --accepted-spec "$SPEC_PATH" --plan "$PLAN_PATH" --git-root "$PROJECT_ROOT"`. The hidden `--implementation-memory` alias remains migration-only.

For the combined instruction “apply it locally, merge it to main with a new PR, then archive this task,” use one guarded closeout execution:

```sh
python3 scripts/gauntlet.py closeout execute \
  --git-root "$PROJECT_ROOT" \
  --handoff "$HANDOFF_PATH" \
  --stage path/to/changed-file \
  --install-target codex \
  --title "$THREAD_TITLE" \
  --suggested-title "p3-auto: complete guarded release closeout" \
  --content "$ARCHIVE_SUMMARY_PATH" \
  --json
```

Repeat `--stage` for every intended source path. The command rejects unlisted dirty work and invalid archive inputs before committing. It prepares the PR body and changelog, commits the named scope, pushes, creates or updates one PR, waits for checks, merges, cleans the local and remote task branches, fast-forwards the default branch, installs the merged Gauntlet version when requested, and returns `remainingAppActions`. The agent must execute those Codex app actions in order; a local process cannot rename or archive a Codex task directly.

## Commit And PR Framing

Use `<area>: <imperative behavioral outcome>` for commit subjects and PR titles, such as `workflow: generate contextual merge handoffs`. A quick task normally has one behavioral commit with its tests and changelog; preserve multiple commits only when each is independently reviewable.

The contextual PR body is reviewer memory, not a file tour:

1. `## Problem`: who is affected, what was insufficient, and why it matters.
2. `## Solution`: resulting behavior, important invariants/design choices, preserved behavior, and meaningful non-goals.
3. `## Changelog`: one release-note bullet copied exactly into `CHANGELOG.md` under `Unreleased`.
4. `## Testing`: reported commands/results, the behavioral claim each check is intended to support, and any limitation or `Cannot verify` item. These records are evidence pointers, not independent proof; required merge checks or the integrating parent must rerun or resolve them before treating the claim as verified.
5. `## Security / Risk`: include only for a concrete material risk; omit empty boilerplate.

Build this framing from the user goal and accepted decisions. Use the diff only to fact-check completeness.

## Version Changelog

When cutting a version, move the shipped entries from `Unreleased` under a heading for that version and release date. Keep the `Unreleased` heading at the top for future work. Leave behind any entries that are not part of the release, and never delete released changelog history.

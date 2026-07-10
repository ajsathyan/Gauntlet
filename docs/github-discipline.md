# GitHub Discipline

Gauntlet's default Git strategy is for builders who are new to Git, working quickly, and relying on agents to do the disciplined parts that people often skip. Advanced users can override it, but the default should be boring, professional, and easy to adopt.

## Default Opinion

Use the startup-safe path for real repository changes:

```text
branch from main -> commit coherent checkpoints -> open a PR -> verify -> merge with a merge commit -> delete the branch
```

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
- Tracks the child-lane ledger and user-facing decisions.
- Integrates child implementation work.
- Opens or updates the final PR.
- Decides whether checks and review are enough to merge.

Child chats should stay bounded:

- Read-only review, research, summarization, and log-analysis lanes return reports, not commits.
- Implementation child chats use separate branches or worktrees when they write code, touch multiple files, or have uncertain ownership.
- Child chats do not direct-push to `main`.
- Child chats should return compact reports with changed files, proof, risks, and any unresolved decision for the main chat.

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

"Merge this," "land this," or "merge this to main" authorizes the complete safe closeout for the current scoped work: prepare the contextual handoff, update `CHANGELOG.md`, commit coherent local changes, push the task branch, create or update one pull request, wait for required checks and blocking review state, merge, delete the remote branch, verify the default branch, and remove local branch/worktree state only when no unique work remains.

"push to git" means push the current branch. It does not imply direct-push to `main` or merge.

Use `scripts/gauntlet.py merge prepare` before committing the changelog, `scripts/gauntlet.py merge plan` for a read-only preflight, and `scripts/gauntlet.py merge execute` after the worktree is clean. The helper creates or updates one PR, waits for checks, refreshes PR state, merges through repository policy, deletes the remote branch, and verifies the landed commit on the default branch. It does not create commits; the main task owns coherent commit boundaries.

The older `scripts/gauntlet.py changelog pr --implementation-memory "$MEMORY_PATH" --git-root "$PROJECT_ROOT"` remains available for explicit legacy drafts and archive summaries.

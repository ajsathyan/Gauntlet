# GitHub Discipline Defaults

Date: 2026-07-08
Scope: Turn the accepted GitHub discipline strategy into active Gauntlet guidance and a beginner-friendly reference.
Proof scope: delta.

## Assumptions

- The target user may be new to Git; advanced users can override repo history and merge preferences.
- The first implementation should be docs and active guidance only, not a new general Git automation helper.
- Existing archive automation remains allowed to merge green PRs with merge commits when deterministic checks pass.

## Decisions

- Make the taught default branch, coherent commits, PR, merge commit, and branch deletion.
- Treat PRs as memory and proof bundles for solo builders and AI-assisted work, not only as team review artifacts.
- Preserve useful checkpoint commits by default; squash and rebase are explicit repo/user preferences.
- Main chats own final PR and merge decisions. Child implementation chats may use isolated branches or worktrees, but return reports and do not direct-push to `main`.
- Keep changelog generation explicit. Default closeout facts do not commit, push, merge, generate changelogs, publish release notes, or archive threads.

## Exceptions

- No CLI behavior changed in this pass. A future `git plan` helper can generalize archive-time Git checks if repeated runs prove the loop.
- Used a sibling worktree for implementation because the source checkout had unrelated untracked `house-voice-plans.md`.
- Manual changelog-helper inspection after PR creation confirmed the helper is not default closeout behavior. Running `scripts/gauntlet.py changelog pr` against this run log failed because the helper expects an Implementation Memory file with required sections; it wrote no changelog file.

## Production Quality Bar

Not relevant because this is workflow guidance, not near-launch runtime behavior or deploy-sensitive code.

## Coverage Gap Candidates

None.

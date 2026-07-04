# Workflow Etiquette Checker

## Scope

Feature / Standard / delta: add deterministic checks and executable action planning for the Workflow Etiquette archive flow.

## Assumptions

- Archive automation is the accepted requirement. Decision Gates should pause only for major unresolved decisions, safety failures, or new material assumptions, not merely because the automation will perform durable actions.

## Decisions

- Added `scripts/check-workflow-etiquette.py` as a standalone stdlib helper with JSON output and exit codes: `0` pass/warn, `1` fail, `2` needs review.
- Added `effectiveExecutionMode` and `decisionGate` so autonomous work with a stop point is machine-readable.
- Renamed the default non-auto posture from `reviewed` to `review`; `review` means human clarification is needed before autonomous execution, not agent self-review.
- Added `Decision Gate` for autonomous work that must stop on a major unresolved decision, safety failure, or new material assumption.
- Kept missing kickoff fields warning-only and migration-friendly for now.
- Split autonomous assumptions into a closeout/adoption/archive gate rather than requiring `Assumptions Made` during kickoff.
- Added archive action planning for `set_thread_title`, `git_push`, and `archive_thread`.
- Made unresolved strong follow-ups, dirty worktrees, and branches behind upstream require review rather than fail.
- Made clean branches that are only ahead of upstream emit `git_push` before `archive_thread`.
- Dirty worktree messages show a short sample plus an omitted-file count when abbreviated.

## Exceptions

- The local helper emits thread actions; the agent executes them with Codex app tools such as `set_thread_title` and `set_thread_archived`.
- Git classifier is local-only in this slice: dirty worktree, ahead/behind upstream, clean repo state, and clean ahead-branch push planning.
- GitHub PR merge-state checks, CI checks, direct-push policy, and multi-repo attribution remain outside the local helper.
- Follow-up thread creation remains documented behavior, not code.

## Coverage Gap Candidates

- Not relevant because this run implemented an accepted local helper and did not expose missing reusable guidance beyond the current draft reference.

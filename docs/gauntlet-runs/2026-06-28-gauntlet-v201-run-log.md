# Run Log: Gauntlet v2.0.1 Run Log Shift

Mode: Feature / Standard
Scope: Replace the default review artifact workflow with exceptions-first Markdown run logs, pending coverage gaps, and Vercel-inspired design lint candidates.

## Assumptions

- `v2.0.1` means updating repository docs, skills, checks, install behavior, commit metadata, and a git tag.
- Historical planning docs that route agents through the old artifact should be removed rather than preserved as current guidance.

## Decisions

- Removed the old default data model instead of keeping it optional in active workflow docs.
- Kept routine successful proof out of run logs; final chat remains the place for normal passing checks.
- Preserved compact Release proof and panel tables because launch-risk decisions need durable evidence.
- Added autonomous `GAP-###` capture, but kept promotion to rules/lints/evals human-owned.

## Exceptions

- Checks skipped: none for install coverage.
- Things that went wrong: red workflow check initially failed because `run-log-builder` did not exist; the first linter pass also caught missing proof-bounded subagent guidance in `experience-reviewer`.
- Cannot verify: whether other machines or agent homes outside `/Users/ajsathyan/.codex` still have stale files.
- Follow-ups: none for the local/global Codex install.

## Coverage Gap Candidates

- GAP-001: covered. The local repo hook and `/Users/ajsathyan/.codex` global install now use v2.0.1 and no longer include the removed review artifact files.

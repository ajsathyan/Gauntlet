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

- Checks skipped: no global install was run against the user's live agent home.
- Things that went wrong: red workflow check initially failed because `run-log-builder` did not exist; the first linter pass also caught missing proof-bounded subagent guidance in `experience-reviewer`.
- Cannot verify: whether downstream installed agents still have stale local files until `scripts/install.sh` is run in that environment.
- Follow-ups: consider a stronger migration notice if stale installed agents keep following old workflow files.

## Coverage Gap Candidates

- GAP-001: pending. Existing global installs can keep stale files until the installer runs.

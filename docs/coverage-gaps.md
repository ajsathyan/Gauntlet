# Coverage Gaps

Coverage gaps are pending candidates for missing reusable guidance. Agents may add or update candidates autonomously, but humans decide whether a candidate becomes a rule, reference, exemplar, lint, eval, coverage gap, or no change.

Do not treat this file as standards. A gap means "we noticed missing guidance," not "this is now policy."

## Candidate Template

```md
## GAP-###: Short Name

Status: pending
Surface:
Seen in:
- docs/gauntlet-runs/YYYY-MM-DD-slug.md

Gap:

Why it matters:

Suggested destination:

Needs human:
```

## Autonomous Capture Signals

- A material assumption was needed because no rule/reference existed.
- A reviewer says the same issue keeps coming up.
- A finding is `Cannot verify` because the expected standard is missing.
- The same class of issue appears across multiple run logs.
- A lint/check cannot decide safely without product context.
- The agent asks a human question that repo guidance should eventually answer.
- A rule has too many exceptions and should move back to guidance.

## GAP-001: Stale Installed Workflow Copies

Status: covered
Surface: Gauntlet install migration
Seen in:
- docs/gauntlet-runs/2026-06-28-gauntlet-v201-run-log.md

Gap:
Gauntlet v2.0.1 removes the old default artifact from the repo, but existing global installs can keep stale files until `scripts/install.sh` runs.

Why it matters:
Future agents running from an old install could follow stale workflow instructions even after the repository has moved on.

Covered by:
- `./scripts/install.sh` installed v2.0.1 to `/Users/ajsathyan/.codex`.
- `/Users/ajsathyan/.codex/gauntlet/scripts/check-gauntlet-workflow.py` passed from the installed copy.
- Installed shape check confirmed `run-log-builder`, coverage gaps, and design lint docs exist, while the old review artifact skill, templates, root files, and startup scripts are absent.
- Local repo pre-commit hook still points at `scripts/run-skill-change-checks.sh`.

Needs human:
Not relevant because the user explicitly approved running the local/global install.

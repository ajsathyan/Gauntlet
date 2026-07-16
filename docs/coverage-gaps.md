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

## Promotion Rule

Use this decision path before adding process:

```text
Reliable failure signal?
No -> keep as experience guidance or human judgment.
Yes -> concrete fix?
No -> record guidance or an eval idea.
Yes -> add or update a pending GAP-### candidate with suggested destination.
```

Suggested destinations are `rule`, `reference`, `exemplar`, `lint`, `eval`, `coverage gap`, or `no change`.

At the end of a run, mention only new or updated gap IDs and why they matter. Put them at the end of the final response using this shape:

```text
Added GAP-###: Short name - why it matters
```

For multiple gaps, use one comma-separated sentence or one short bullet per gap. Do not report routine successful checks as gaps.

## Resolved Gap Cleanup

Remove a `GAP-###` entry from this file when the accepted destination exists and is covered by proof. Do not keep resolved gaps here as historical archive; the run log and git history are the archive.

Before removing a gap, confirm:

- The destination named by the gap exists, such as a rule, reference, exemplar, lint, eval, or explicit no-change decision.
- The destination is discoverable from the relevant workflow, role skill, doc, or checker.
- A local check, targeted search, review, or run log proves the destination was added.
- The run log records that the gap was resolved or removed.

If a gap is only partially addressed, keep it pending and narrow its wording to the remaining missing guidance.

## Promotion Scanner Routing

When `promotion-scanner` finds high-value repeated work, add or update a `GAP-###` only for Gauntlet-general missing guidance. Repo-specific promotion candidates should become repo code, repo test, repo docs/run log, or issue follow-up.

Do not use this file as a backlog for local automation candidates. If the repeated loop has a concrete repo fix, route it to the repo; if it exposes missing reusable agent guidance, record the narrowest coverage gap.

<!-- GAP CANDIDATES -->

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

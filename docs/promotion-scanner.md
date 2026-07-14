# Promotion Scanner

`promotion-scanner` turns repeated manual, agent, subagent, trace, monitor, shell, and run-log work into a bounded promotion decision. The goal is to decide whether a repeated loop should graduate into repo code, repo test, repo docs/run log, a Gauntlet skill/tool, a coverage gap, or Reject.

This is not an action recommender. No live operational actions: do not recommend terminating pods, deleting data, revoking access, deploying, billing, migrating, or mutating production state now.

## When To Run

Run on explicit user request or when repeated manual verification, repeated `Cannot verify`, or repeated evidence across run logs supports an actual durable destination. Do not run automatically for ordinary Patch or Release wrap-up.

Dynamic triggers beat calendar triggers. A useful threshold is two similar loops in one Release/live-ops run, or the same loop across two run logs, with enough explicit artifacts to distinguish stale vs latest evidence.

## Output

Integrate a compact candidate table into the current report by default. Produce a standalone Promotion Brief only when the user explicitly requests one or a durable cross-run artifact is the task.

- current evidence table by entity or surface
- timeline highlights with stale vs latest evidence separated
- repeated manual loops observed
- promotion candidates with confidence
- recommended destination: repo code, repo test, repo docs/run log, Gauntlet skill/tool, coverage gap, or Reject
- edge cases and proof needed
- secrets/redaction notes
- Do not infer warnings

## Gap Routing

Add or update a `GAP-###` only when the scanner finds Gauntlet-general missing guidance. Repo-specific candidates should become repo code, repo test, repo docs/run log, or issue follow-up. Do not use `docs/coverage-gaps.md` as a backlog for local automation ideas.

## Non-Goals

- No live operational actions.
- No automatic promotion to a rule, lint, or gate without human approval.
- No stale-test or stale-run-log confidence without current evidence.
- No broad subagent tickets that leak secrets or expand beyond the observed loop.

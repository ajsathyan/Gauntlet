# Gauntlet Lite Contributor Guide

Gauntlet Lite is a compact product, proof, and release workflow for Codex. The
installed router is `router/AGENTS.md`; procedures live in the nine retained
`skills/` packages.

## Workflow

- Use a Normal Request for bounded, reversible work and Research for read-only work.
- Before non-trivial implementation, use `design` and the main-agent six-lens
  review: Product, Engineering, Design, Analytics, QA, and Performance.
- Require acceptance of the exact final `Acceptance` section.
- Plan and implement natively in the main task. Use subagents only when AJS asks.
- Commit a coherent candidate, then use `verify` on that exact commit/tree/base.
- After passing proof, use `land` and `ship` without another routine prompt.

A complete user task may serve as Design. A lens may be `Not applicable` with a
reason. Review recommendations are advisory until the user accepts them.

## Proof and authority

Verify reports behavior and proof availability for every accepted outcome. Known
failure is `Failed`; no failure with missing required proof is `Blocked`; only
complete applicable proof is `Passed`. Architecture remains a separate verdict.
Manifests, documents, self-reports, and green commands do not prove behavior.

Acceptance authorizes the scoped implementation, checks, commit, push, pull
request, direct merge, ordinary deployment, and monitoring. Stop for effects
outside that scope or unexpected destructive, credential, migration,
privacy, security, data-loss, or production effects.

Preserve unrelated work. Gauntlet has no merge queue. Land fails on ambiguous
remotes or known stale proof, verifies the landed revision, and handles rare
direct-merge races ad hoc.

## Repository checks

For skill or workflow changes run:

```sh
scripts/run-skill-change-checks.sh
python3 scripts/check-gauntlet-workflow.py
```

Use temporary agent homes for install proof. Keep the router below Codex's 32 KiB
instruction limit and preserve bytes outside its managed block. Installer changes
must prove clean install, safe upgrade, ownership transfer, idempotency, malformed
state rejection, and uninstall preservation.

Do not retain aliases, fixtures, examples, documentation, or compatibility code
for retired behavior. Git history is the archive.

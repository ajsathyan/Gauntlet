# Workflow Speedup Helpers

These helpers reduce repeated shell setup for review and verification. They are advisory, not proof. Every output includes confidence or `Cannot verify` language so agents do not mistake stale heuristics for a complete quality gate.

## Tools

```sh
scripts/diff-intel.py "$PROJECT_ROOT"
scripts/test-plan.py "$PROJECT_ROOT"
scripts/review-pack.py "$PROJECT_ROOT"
```

`diff-intel.py` writes `.gauntlet/diff-intel.json` with changed files, package roots, risk triggers, generated/docs/UI flags, dirty worktree state, confidence, and `Cannot verify` notes.

`test-plan.py` writes `.gauntlet/test-plan.json` with focused and broader commands. It recommends broad suites only when risk triggers such as auth, security/privacy, persistence, public API, billing, or data integrity warrant them.

`review-pack.py` writes `.gauntlet/review-pack.md`, a bounded packet for reviewers or subagents. It includes changed files, risk triggers, invariants, redacted diff excerpts, proof gaps, and the shared role report contract.

## Boundaries

- Dirty worktree: helpers classify the current diff, but agents must preserve unrelated user changes.
- Local run artifacts: helper discovery ignores `.gauntlet/`, review-brief, and implementation-note artifacts so generated workflow files do not pollute follow-up runs.
- Monorepos: package-root detection is heuristic; low or medium confidence requires local confirmation.
- Projects without standard test naming: `test-plan.py` reports `Cannot verify` instead of inventing a mapping. Common sibling tests and Python `tests/test_*.py` patterns are mapped when present.
- Generated code: generated diffs require source-generator proof before confidence should rise.
- Docs-only changes: runtime tests are not recommended unless docs generation or executable examples are in scope.
- Security/privacy-sensitive diffs: review packets redact secret-like values, and broader tests/reviews are recommended.
- UI-only diffs: UI triggers stay separate from durable backend workflow triggers.
- Giant files: large changed files lower confidence because one file can hide many surfaces.
- Subagent packets: `scripts/check-subagent-plan.py` rejects secret-like inline context and overbroad scopes.
- Stale mappings: test recommendations are a starting point; missing tests are `Cannot verify`.

## Deferred

`quality-check --surface ...` is deferred. Named surfaces such as `dashboard/fleet/ops` are usually repo-specific, and a one-command quality runner can make every Patch feel heavy while giving false confidence. Build that later only if repeated run logs show the lower-level helpers still leave a real gap.

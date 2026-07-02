---
name: black-box-tester
description: Use when behavior must be validated externally through UI, CLI, API, docs, logs, persisted data, screenshots, browser checks, or user-visible outcomes.
---

# Black-Box Tester

Treat the implementation as opaque. Test observable behavior against the spec, user expectations, platform conventions, and outcomes.

## Input Packet

- Spec or task packet
- Oracle: expected behavior and acceptance criteria
- Surfaces: UI, CLI, API, docs, logs, persistence, screenshots, or browser checks
- Environment, accounts, data, and limits
- Non-goals
- Existing run log or coverage gap candidates, if any

Independent UI/API/CLI/persistence charters may run as parallel subagents when they do not mutate shared state.

## Output Contract

If a field is outside accepted scope, write `Not relevant because...` instead of stretching the charter. Optional example: read `examples/black-box-report.md` only when output shape is ambiguous.

- Verdict: `Pass`, `Fail`, `Needs proof`, or `Cannot verify`
- Confidence
- Proof scope: `smoke`, `delta`, `full`, or `not relevant`
- Charter
- Oracle
- Evidence
- Findings with reproduction path
- Cannot verify: missing access, data, environment, or proof
- Coverage notes: what was checked and what was intentionally not checked
- Residual risk
- Agent next: one concrete follow-up
- Coverage gap candidate: only when reusable guidance is missing

## Rules

- Report facts separately from guesses.
- Do not infer root cause from external evidence alone.
- Passing checks are evidence, not proof of internal quality.
- Stop when the charter answers the oracle or a missing proof item blocks further external validation.
- For Production Quality Bar charters, prove observable release proof such as dry-run or no-mutation behavior, persisted state, logs, automated GitHub release tags/artifacts, and recovery paths, or mark `Not relevant because...`.
- For substantial frontend UI, use `docs/ui-constitution.md` for relevant browser checks: form submit, duplicate-submit prevention, feedback placement, state reachability, and responsive/touch behavior.
- Use a combined black-box and experience pass for small UI changes when the same evidence answers both behavior and UX questions.
- Skip frontend constitution checks for non-frontend or narrow Patch charters with `Not relevant because...`.

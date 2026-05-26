# Global Codex Coding Workflow

For non-trivial coding work, use this loop:

1. intake
2. planner
3. issue-triager
4. implementer
5. adversarial-reviewer
6. black-box-tester
7. issue-triager
8. deep-code-reviewer

Scale by task tier:

- Tier 0 trivial: edit, verify, summarize.
- Tier 1 small: quick intake check, implement, verify, self-review.
- Tier 2 medium: intake, plan, implement with notes, targeted review/test.
- Tier 3 large or risky: full loop with role subagents.

## Intake Gate

Before substantial implementation, ensure the task has: goal, scope, non-goals, affected interfaces, acceptance criteria, verification/proof, constraints, and assumptions/open questions.

Ask only questions that materially affect implementation, product behavior, risk, UX, data, API behavior, verification, or scope. Otherwise make a reasonable assumption, record it, and proceed.

Treat `/intake` or "use intake" as an explicit request to run the intake skill before planning or implementation. For follow-ups, run delta intake: identify what changed, which assumptions are invalid, which acceptance criteria are new, and what new proof is required.

## Role Skills

Use these skills on demand:

- intake: turns rough intent into an implementable spec.
- planner: turns accepted specs into ordered implementation slices.
- issue-triager: converts plans/findings into prioritized ready tasks.
- implementer: executes scoped code changes.
- adversarial-reviewer: stress-tests assumptions, edge cases, trust boundaries, and regressions.
- black-box-tester: validates behavior externally.
- deep-code-reviewer: reviews correctness, maintainability, tests, and regression risk.

When spawning subagents, explicitly point each subagent at the relevant skill.

## Implementation Notes

For Tier 2/3 implementation, maintain `implementation-notes.html` in the project root unless the user specifies another location.

Before implementation continues, create the notes file if missing, start a local notes server, and give the user the URL. Prefer `scripts/serve-notes.sh` from Gauntlet when available; otherwise use `python3 -m http.server` from the project root on an available localhost port. The notes page should auto-refresh so the user can watch progress live.

The orchestrator owns the notes file. Subagents report findings; the orchestrator normalizes them.

Record only meaningful entries:

- Design decisions where the spec was ambiguous
- Intentional deviations from the spec and why
- Tradeoffs and alternatives considered
- Open questions for the user
- Proof of completion
- Quantitative impact

Do not turn notes into a changelog or a diary of trivial choices. Do not include secrets or sensitive data.

When notes include quantitative impact, present it with Tufte-style minimal visualization: compact tables, sparklines, small multiples, or simple charts with direct labels, high data-ink ratio, accessible contrast, and concise annotations. Use the `tufte-data-viz` skill when available.

## Stop Conditions

Stop and ask before proceeding when:

- A decision materially changes product behavior
- Data loss, migration, billing, security, or privacy risk is ambiguous
- The requested behavior conflicts with existing architecture or policy
- The likely cost exceeds the stated appetite
- Required credentials, permissions, or external state are unavailable

## Completion Rule

A coding task is complete only when acceptance criteria are met, relevant checks ran or limitations are stated, implementation notes are updated when required, no blocking review/test/triage findings remain, and the final response includes what changed, what was verified, and remaining risks.

For Tier 2/3 work, add one short workflow lesson when useful: whether a recurring failure should update a skill, test, checklist, or this file.

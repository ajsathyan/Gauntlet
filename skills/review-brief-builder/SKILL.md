---
name: review-brief-builder
description: Use for Slice and Release work to create a human review brief that prioritizes what engineers, PMs, and designers need to inspect and why.
---

# Review Brief Builder

Create the canonical human review surface for the current change. The goal is not to summarize everything; it is to help people put scarce attention in the right places.

Use `templates/review-brief.html` from Gauntlet when available.

## Inputs

Use available evidence:

- Accepted spec or intake output.
- Product-architect output.
- Implementation notes.
- Git diff summary, name-status, and changed files.
- Verification commands and results.
- Screenshots, benchmarks, visual diffs, logs, or black-box evidence.
- Reviewer findings and triage status.

Do not include secrets, raw private logs, or large pasted diffs.

## Output Sections

- Overview: one-paragraph summary, current status, and required reviewers.
- PM brief: product assumptions, behavior changes, acceptance criteria, launch/support risk, open decisions.
- Design brief: screens, states, interaction changes, responsive behavior, accessibility, visual diffs, design-system drift.
- Developer brief: risk-ranked review map, files to inspect, trust boundaries, tests, performance/security concerns.
- Proof: checks run, what they prove, what they do not prove, screenshots or benchmarks when available.
- Decisions: meaningful decisions, deviations, tradeoffs, and open questions.
- Handoff: how to run, how to review, what remains.

## Priority Rules

Mark review areas:

- P0: must inspect before merge.
- P1: should inspect.
- P2: skim.
- P3: low-risk or mechanical.

P0 triggers include auth, permissions, billing, migrations, destructive writes, private data, uploads, concurrency, public API contracts, and production deploy behavior.

P1 triggers include core business logic, persistence, cache behavior, state coordination, performance-sensitive paths, and error handling.

P2/P3 areas include docs, simple UI polish, build tooling, tests, formatting, mechanical extraction, and low-risk generated artifacts.

## Rules

- Show one current version of the change, not a chronological diary.
- Prioritize what needs review and why.
- Keep raw code exposure minimal in PM and design sections.
- Use compact tables or direct-labeled simple charts for quantitative metrics.
- State missing proof explicitly.

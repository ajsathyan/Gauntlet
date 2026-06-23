---
name: experience-reviewer
description: Use when an implemented user-facing Feature needs review for workflow clarity, states, accessibility, trust, product cohesion, or next action.
---

# Experience Reviewer

Review the implemented feature as a user experience. Separate PM/design judgment from engineering defects.

## Input Packet

- Product Packet or accepted feature spec
- Primary user, first-value moment, and workflow
- Surfaces and states to inspect
- Screenshots, URL, build, or reproduction path
- PM/design acceptance criteria
- Existing handles, if any

Independent screen, responsive, accessibility, and copy passes may run as parallel subagents for broad features. Do not expand into activation, retention, growth, or sharing unless accepted scope makes them relevant.

## Output Contract

If a field is outside accepted scope, write `Not relevant because...` instead of stretching into wishlist review. Optional example: read `examples/experience-report.md` only when output shape is ambiguous.

- Verdict: `Approved`, `Needs fixes`, `Needs decision`, or `Cannot verify`
- Findings first, grouped by P0/P1/P2/P3
- For each finding: Role, Surface or flow, User impact, Evidence, Recommended change, Acceptance or test idea
- Human decision needed
- Agent can fix next
- Cannot verify: missing screen, state, data, device, or product decision
- Residual risk
- Agent next: one concrete follow-up
- Suggested review brief links: `RB` concern and `P` proof handles when useful

## Check

- Entry point and user job clarity
- First-value path, progress, completion, and next best action
- Empty, loading, error, success, disabled, and partial-data states
- Accessibility basics, responsive behavior, trust, permission, and copy clarity
- Visual hierarchy and design-system consistency

Do not create metrics or UI requirements just to have findings.

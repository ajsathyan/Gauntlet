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
- Existing run log or coverage gap candidates, if any

Independent screen, responsive, accessibility, and copy passes may run as parallel subagents for broad features when each lane has separate proof. Do not expand into activation, retention, growth, or sharing unless accepted scope makes them relevant.

## Output Contract

If a field is outside accepted scope, write `Not relevant because...` instead of stretching into wishlist review. Optional example: read `examples/experience-report.md` only when output shape is ambiguous.

- Verdict: `Approved`, `Needs fixes`, `Needs decision`, or `Cannot verify`
- Proof scope: `smoke`, `delta`, `full`, or `not relevant`
- Findings first, grouped by P0/P1/P2/P3
- For each finding: Role, Surface or flow, User impact, Evidence, Recommended change, Acceptance or test idea
- Human decision needed
- Agent can fix next
- Cannot verify: missing screen, state, data, device, or product decision
- Residual risk
- Agent next: one concrete follow-up
- Coverage gap candidate: only when reusable guidance is missing

## Check

- Entry point and user job clarity
- First-value path, progress, completion, and next best action
- Empty, loading, error, success, disabled, and partial-data states
- Accessibility basics, responsive behavior, trust, permission, and copy clarity
- Production Quality Bar: decision-oriented UI with confidence, freshness, sample size, blockers, evidence, and next action, or `Not relevant because...`
- Visual hierarchy and design-system consistency
- For substantial frontend UI, use the Gauntlet reference document `docs/ui-constitution.md` in the Gauntlet source repo, or `$AGENT_HOME/gauntlet/docs/ui-constitution.md` in a global install, to check semantics, labels, states, feedback, disabled explanations, icon-only actions, and agent/process copy.
- Use delta review for accepted small changes and full review for new or ambiguous workflows.
- Test whether visible actions and states work, not merely whether a screenshot contains expected copy or controls. Pair semantic or functional claims with interaction evidence, negative states, and required non-effects where practical.

Do not create metrics or UI requirements just to have findings.

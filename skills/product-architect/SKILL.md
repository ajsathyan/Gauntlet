---
name: product-architect
description: Use when Feature mode or user-facing work needs workflow, IA, first value, meaningful metrics, trust, and PM/design acceptance before implementation.
---

# Product Architect

Turn user-facing intent into a **Product Packet**. The feature should feel like the real product, not a disposable draft or explanatory mock.

## Product Packet

If a field is outside accepted scope, write `Not relevant because...` instead of inventing product work. Optional example: read `examples/product-packet.md` only when output shape is ambiguous.

- Mode recommendation: Feature or escalation to Release
- Primary user and situation
- User job
- First-value moment
- Workflow
- Information architecture
- Key screens or states
- Key states not in scope
- Meaningful metrics, if any, and why they matter
- Production Quality Bar: launch trust, feedback loop, or decision-oriented UI needs, or `Not relevant because...`
- Not relevant because: activation, retention, growth, sharing, or handoff items that would stretch scope
- Trust, privacy, permission, and hesitation points
- Configuration requirements: behavior that must vary, who controls it, secret/private-data classes, and stable product constants
- PM acceptance criteria
- Design acceptance criteria
- Engineering handoff: affected flows, interfaces, and proof expectations
- Assumptions: mark as `user-stated`, `repo-inferred`, or `agent-assumed`
- Open questions
- Cannot verify: product facts that need human or data proof

## Rules

- Compare 2-3 approaches only when the choice materially changes workflow, architecture, trust, cost, or acceptance. Lead with a recommendation. Ask for approval only when the decision is genuinely the user's; do not impose a universal brainstorming gate.
- When the default local-document profile applies, update the canonical PRD from the primary worktree. Keep repository-required contracts and maintainer documentation tracked. Opted-out projects use the repository's established tracked documentation location.
- Never place secret values in the packet. Distinguish behavior that truly varies by environment or operator from stable product rules that belong in reviewed, tested code.
- Metrics belong in the product only when they help the user understand real progress, quality, confidence, speed, completion, improvement, or next action.
- Do not put draft explanations, agent/process notes, or absence-of-metric rationale in product UI; put non-obvious rationale in the run log.
- Include onboarding, activation, retention, or growth only when accepted scope or a real next action makes them relevant.
- For near-launch Production Quality Bar work, define confidence, freshness, blockers, evidence, user/operator feedback, and next action only where they help decisions.
- If screens or flows can be explored independently, name subagent-ready lanes for product review, visual review, and implementation handoff, each with separate proof expectations.

## Attribution

The material-alternatives technique is adapted from Jesse Vincent's Superpowers `brainstorming` skill, version 5.1.3 (MIT). Gauntlet removes the universal approval gate and permanent design-doc requirement. See `docs/upstream-superpowers.md`.

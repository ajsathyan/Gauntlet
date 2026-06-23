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
- Not relevant because: activation, retention, growth, sharing, or handoff items that would stretch scope
- Trust, privacy, permission, and hesitation points
- PM acceptance criteria
- Design acceptance criteria
- Engineering handoff: affected flows, interfaces, and proof expectations
- Assumptions: mark as `user-stated`, `repo-inferred`, or `agent-assumed`
- Open questions
- Cannot verify: product facts that need human or data proof

## Rules

- Ask only questions that materially affect the feature; otherwise make a marked assumption.
- Metrics belong in the product only when they help the user understand real progress, quality, confidence, speed, completion, improvement, or next action.
- Do not put draft explanations, agent/process notes, or absence-of-metric rationale in product UI; put rationale in the review brief.
- Consider onboarding, activation, retention, and growth only when tied to accepted scope or a real next action.
- If screens or flows can be explored independently, name subagent-ready lanes for product review, visual review, and implementation handoff, each with separate proof expectations.

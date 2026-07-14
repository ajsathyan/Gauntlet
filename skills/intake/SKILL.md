---
name: intake
description: Use when non-trivial coding work needs bounded scope, acceptance criteria, proof, assumptions, and material questions.
---

# Intake

Turn rough intent into an **Intake Packet** another agent can execute with minimal follow-up. Classify first, then ask only questions that materially change implementation, product behavior, risk, UX, data, API behavior, verification, or scope.

## Tier

- Tier 0 trivial: typo, label, tiny mechanical fix.
- Tier 1 small: localized change with obvious verification.
- Tier 1 high-upside: localized change where performance, security, reliability, or data integrity rewards deeper search.
- Tier 2 medium: multi-file or user-visible behavior change.
- Tier 3 large/risky: cross-system, migration, security/privacy, ambiguous product behavior, or weak test coverage.

## Intake Packet

Return fields in this order. Use `None` only when the field truly does not apply.

If a field is outside accepted scope, write `Not relevant because...` instead of expanding intake. Optional example: read `examples/intake-packet.md` only when output shape is ambiguous.

- Tier and reason
- Recommended path and depth: Research, Patch, Feature, or Release
- Goal
- In scope
- Out of scope
- Affected interfaces
- User/system flows
- Acceptance criteria
- Verification/proof
- Constraints
- Assumptions
- Open questions
- Cannot verify: unknowns, why they matter, and the next proof needed
- First implementation step

## Rules

- Ask up to three questions; for minor gaps, make an assumption and record it.
- Frame verification as a behavioral claim, observable outcome, and meaningful limits. For consequential behavior, name a plausible wrong case and required non-effects instead of relying on phrases, populated fields, or a green command.
- Keep intake in the conversation or canonical plan. Do not create a second permanent intake artifact unless the user explicitly asks for a spec document.
- When the default local-document profile applies, use its canonical location for a local artifact without creating a second intake or plan.
- Research intake bounds the question, evidence, freshness, and consequence; it does not force a Patch, Feature, or Release mode before implementation exists.
- For optimization, security, reliability, or audit work, separate scope from depth and clarify whether the user wants an acceptable improvement or the best improvement worth searching for when cost changes.
- For follow-ups, run delta intake: changed assumptions, new acceptance criteria, and new proof.
- Stop and ask when a missing answer could cause data loss, security/privacy exposure, billing impact, incompatible product behavior, or work beyond the stated appetite.

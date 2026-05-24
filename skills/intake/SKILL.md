---
name: intake
description: Use before non-trivial coding work, or when the user invokes /intake or asks for intake, to turn rough intent into a self-contained implementation spec with scope, boundaries, acceptance criteria, proof, assumptions, and open questions.
---

# Intake

Turn rough intent into a spec another agent can execute with minimal follow-up.

Classify the task first:

- Tier 0 trivial: typo, label, tiny mechanical fix.
- Tier 1 small: localized change with obvious verification.
- Tier 2 medium: multi-file or user-visible behavior change.
- Tier 3 large/risky: cross-system, migration, security/privacy, ambiguous product behavior, or weak test coverage.

Ask up to five questions only when answers materially affect implementation, product behavior, risk, UX, data model, API behavior, verification, or scope. For minor gaps, make a reasonable assumption and record it.

For follow-ups, run delta intake: what changed, which prior assumptions are invalid, which acceptance criteria are new, and what new proof is required.

Output this compact spec:

- Tier and reason
- Goal
- Background
- In scope
- Out of scope
- Affected interfaces
- User/system flows
- Acceptance criteria
- Constraints
- Verification/proof
- Default assumptions
- Open questions
- First implementation slice

Stop and ask when a missing answer could cause data loss, security/privacy exposure, billing impact, incompatible product behavior, or work beyond the stated appetite.

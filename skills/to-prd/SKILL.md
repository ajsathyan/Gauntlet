---
name: to-prd
description: Use when the user explicitly asks to create a product document from the current discussion without starting implementation.
---

# To PRD

Create the user-owned document through `maintain-prd`; do not publish it to an issue tracker or start implementation.

## Procedure

1. Read `doc_org.md`, `local-docs/INDEX.md`, and any existing product document.
2. Select the guided Founding Hypothesis for a new product or the guided Peter Yang PRD without Meeting Notes for a follow-up feature.
3. Fill only decisions the user explicitly stated or acknowledged. Preserve unanswered guidance, arbitrary sections, and existing behavior. Do not infer non-goals, security boundaries, rollout, metrics, acceptance, or implementation decisions.
4. Put helpful additions in at most three proposed edits with their practical effects. Apply them only after acknowledgment.
5. Return the path, what user-authorized content was added, and the one material unanswered question. Use `Cannot verify` when the discussion does not establish an answer.

## Completion

Complete when the requested draft exists and contains no unapproved product statement. Do not mark it accepted unless the user explicitly accepts it.

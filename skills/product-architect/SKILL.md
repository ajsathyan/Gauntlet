---
name: product-architect
description: Use when implementation needs a material product workflow, information-architecture, first-value, trust, alternative, or acceptance decision.
---

# Product Architect

Help resolve the product decision the user is actually making. Explicitly compare materially different approaches when the choice changes the experience or implementation boundary. Do not silently update the durable design.

## Output Contract

Optional example: read `examples/product-packet.md` only when the output shape is ambiguous.

Return at most three practical-effect bullets:

- the recommended decision and what changes for the user;
- a materially different alternative only when it is genuinely plausible;
- the one unresolved question or `Cannot verify` limit that could change the decision.

When the user explicitly requests a document edit, provide a targeted proposed edit for the named section and return it to the `design` skill for the user-authorized update.

## Rules

- Start from the current product document and repository behavior. Preserve existing behavior unless the user explicitly changes it.
- Return the decision to the `design` skill for the user-authorized Design/PRD
  update. Its accepted `Acceptance` section is the canonical Build Contract.
- Resolve routine choices independently inside the requested scope. Ask only
  when the answer changes scope, safety, authority, cost, or an external effect
  and cannot responsibly be decided within the request.
- Never invent non-goals, security boundaries, maturity gates, metrics, rollout, or supporting features. Suggest one only when tied to a concrete product effect, and keep it proposed until accepted.
- Compare approaches only when the choice materially changes the experience or implementation boundary.
- Do not turn ordinary internal tools into enterprise or state-of-the-art products by default.
- Keep secret values out of the document. Return `Cannot verify` when a decision needs evidence that is unavailable.

## Completion

Complete when the material product choice is clear enough for a targeted document edit or the blocking decision is plainly stated.

---
name: intake
description: Use when non-trivial coding work needs bounded scope, observable acceptance, proof, assumptions, and a material question before implementation.
---

# Intake

Bound the requested implementation without turning rough discussion into requirements.

## Intake Packet

Include only what applies:

- goal and requested scope;
- affected behavior or interfaces;
- observable done behavior and proportionate proof;
- constraints and user-stated assumptions;
- one material open question or `Cannot verify` limit;
- first coherent implementation step.

Optional example: read `examples/intake-packet.md` only when the output shape is ambiguous.

## Rules

- Use existing context first. Resolve routine choices independently inside the
  requested scope. Ask at most three short questions only when an answer changes
  scope, safety, authority, risk, cost, or an external effect and cannot
  responsibly be decided within the request.
- Do not create or expand a PRD unless the user explicitly requests that document action.
- Never infer non-goals, security boundaries, rollout, maturity gates, or
  supporting features from an empty packet field. Keep unrelated suggestions
  outside requested scope.
- Preserve existing behavior unless explicitly changed.
- Prove behavior with an observable outcome. Add a wrong case or required non-effect only when it materially distinguishes the result.
- Keep intake in the conversation or owning artifact; do not create a second permanent packet.

## Completion

Complete when the first build step and its proof are clear. If missing evidence prevents that, return `Cannot verify`, why it matters, and the next useful check.

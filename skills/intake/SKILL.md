---
name: intake
description: Use when non-trivial coding work needs bounded scope, observable acceptance, proof, assumptions, and a material question before implementation.
---

# Intake

Bound the requested implementation without turning rough discussion into requirements.

## Intake Packet

Include only what applies:

- goal and accepted scope;
- affected behavior or interfaces;
- observable done behavior and proportionate proof;
- constraints and user-stated assumptions;
- one material open question or `Cannot verify` limit;
- first coherent implementation step.

Optional example: read `examples/intake-packet.md` only when the output shape is ambiguous.

## Rules

- Use existing context first. Ask at most three short questions, and only when an answer changes behavior, scope, acceptance, authority, risk, cost, or external effect.
- Do not create or expand a PRD unless the user explicitly requests that document action.
- Never infer non-goals, security boundaries, rollout, maturity gates, or supporting features from an empty packet field. Keep suggestions outside accepted scope until acknowledged.
- Preserve existing behavior unless explicitly changed.
- Prove behavior with an observable outcome. Add a wrong case or required non-effect only when it materially distinguishes the result.
- Keep intake in the conversation or owning artifact; do not create a second permanent packet.

## Completion

Complete when the first build step and its proof are clear. If missing evidence prevents that, return `Cannot verify`, why it matters, and the next useful check.

---
name: design
description: Resolve material product decisions, run the six-lens review, and obtain acceptance before non-trivial implementation.
---

# Design

Turn material work into one accepted outcome contract. A bounded Normal Request
and research-only work do not use this gate.

## Shape the contract

1. Read the request, repository evidence, current behavior, and prior decisions.
2. Compare only materially different approaches and record the selected tradeoff.
3. Resolve observable outcomes, user-visible states, edge cases, authority, and
   behavior that must remain unchanged.
4. Use a complete user task as Design when it already resolves those points.
   Otherwise create one concise durable Design with an `Acceptance` section.
5. Run the `adversarial-reviewer` six-lens pass against the exact final contract.
6. Show every material recommendation before implementation. Record `accepted`,
   `rejected`, `deferred`, or `omitted` with a reason.
7. Require the user to accept the exact `Acceptance` section. A semantic edit
   reruns affected lenses and requires acceptance of the revised section.

Ask only when an answer changes scope, behavior, authority, risk, cost, or an
external effect and cannot be resolved from evidence. Review advice is not
implementation authority.

## Authority

Acceptance authorizes the scoped implementation, verification, commit, push,
pull request, merge, ordinary declared deployment, and monitoring. Explicit
narrower limits win. Stop for an unexpected destructive, credential,
migration, privacy, security, data-loss, or production effect.

## Output

Return the selected tradeoff, exact Acceptance, review recommendations and
dispositions, durable Design path when one is needed, and unresolved limits.

Complete when the exact final Acceptance has received all six lenses and the user
has accepted it.

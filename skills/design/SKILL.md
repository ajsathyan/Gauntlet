---
name: design
description: Use before non-trivial implementation to resolve product decisions and edge cases, run adversarial review, and obtain acceptance of the exact Design or PRD.
---

# Design

Turn a non-trivial implementation request into an accepted Design/PRD before
code changes begin. A bounded, low-consequence Normal Request bypasses this
skill and goes directly to the requested artifact and smoke check.

## Design Work

1. Read existing product documents, repository behavior, research, and user decisions before asking questions.
2. Explicitly brainstorm materially different approaches. Record the options considered, the recommended approach, and the practical tradeoff. Do not manufacture alternatives that would not change the product or implementation boundary.
3. Resolve assumptions, feature-completeness questions, user-visible states, edge cases, observable acceptance, and required non-effects. Make routine product and engineering decisions independently inside the requested scope and record material decisions. Ask at most three short questions per user round only when an answer changes scope, safety, authority, cost, risk, or an external effect and cannot responsibly be decided inside the request.
4. Create or update one permanent Design/PRD with explicit user authority. Preserve direct user edits and keep unaccepted suggestions outside it.
5. Run independent product-completeness, engineering-shape, and proof/consequence reviews. For stateful work, examine state transitions, retries, idempotency, recovery after partial failure, concurrency, and required non-effects.
6. Present the document and stop before implementation until the user accepts its exact `Acceptance` section. That section is the canonical Build Contract; do not narrow it into a second checklist.
7. Treat acceptance as authority for the scoped implementation, verification, branch publication, pull-request merge, and ordinary declared production deployment. Later semantic edits require re-acceptance.

Legacy accepted PRDs remain valid designs. They do not need rewriting merely to adopt new terminology.

## Advisory Review

Run three independent lenses against the same request or proposed design before
asking for acceptance:

- **Product completeness:** missing user outcomes, feature states, assumptions, and feature-level edge cases.
- **Engineering shape:** boundaries, dependencies, migrations, compatibility, and parallel ownership conflicts.
- **Proof and consequence:** observable oracles, false-green paths, required non-effects, and concrete security, privacy, billing, destructive, production, or specialist triggers.

Each lens returns only material findings. Deduplicate without losing provenance.
Show the user at most three recommendations per round, but retain and resolve
every material finding. Record `accepted`, `rejected`, `deferred`, or `omitted`
with a reason as the implementation disposition. Ask the user only when the
  finding exposes an unresolved material scope, safety, authority, or external
  effect.

When an accepted design exists and exact-design proof is useful, keep complete
review results in a task-temporary JSON file and invoke `workflow build-entry`
through the installed Gauntlet CLI path named by the router. Its returned
contract is temporary proof input, not implementation authority, a durable
design, implementation plan, or controller artifact. A failed command blocks
only that optional proof path.

## Output

- Material alternatives and chosen tradeoff
- Observable outcomes and required non-effects
- Material decisions made independently
- Durable design path and exact accepted digest when one exists
- Review findings and terminal dispositions
- Unresolved scope, safety, authority, external effect, or `Cannot verify` limit

## Completion

Design work is ready for implementation when the exact `Acceptance` section is
accepted, observable outcomes are clear enough to build, routine decisions are
resolved or recorded, and any unresolved scope, safety, authority, or external
effect is surfaced.

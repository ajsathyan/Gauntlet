---
name: design
description: Use around non-trivial implementation to brainstorm material alternatives, resolve product decisions and edge cases, and optionally create or update a durable design without blocking implementation.
---

# Design

Clarify a non-trivial implementation request without turning design acceptance
into permission to write or land code. A bounded, low-consequence Normal Request
bypasses this skill and goes directly to the requested artifact and smoke check.

## Design Work

1. Read existing product documents, repository behavior, research, and user decisions before asking questions.
2. Explicitly brainstorm materially different approaches. Record the options considered, the recommended approach, and the practical tradeoff. Do not manufacture alternatives that would not change the product or implementation boundary.
3. Resolve assumptions, feature-completeness questions, user-visible states, edge cases, observable acceptance, and required non-effects. Make routine product and engineering decisions independently inside the requested scope and record material decisions. Ask at most three short questions per user round only when an answer changes scope, safety, authority, cost, risk, or an external effect and cannot responsibly be decided inside the request.
4. Create or update one permanent design document only with explicit user authority. Preserve direct user edits and keep unaccepted suggestions outside it.
5. When the user accepts a durable design, its exact Acceptance section is the canonical Build Contract for the optional exact-design proof path. Do not copy, compile, summarize, or narrow it into a second requirements checklist.
6. Do not delay code edits, commits, publication, or a non-production merge for design creation or acceptance. Later semantic edits invalidate only the accepted-design proof binding until re-accepted.

Legacy accepted PRDs remain valid designs. They do not need rewriting merely to adopt new terminology.

## Advisory Review

When consequence or complexity justifies it, run three independent lenses against
the same request or accepted design before or during Build:

- **Product completeness:** missing user outcomes, feature states, assumptions, and feature-level edge cases.
- **Engineering shape:** boundaries, dependencies, migrations, compatibility, and parallel ownership conflicts.
- **Proof and consequence:** observable oracles, false-green paths, required non-effects, and concrete security, privacy, billing, destructive, production, or specialist triggers.

Each lens returns only material findings. Deduplicate without losing provenance.
Show the user at most three recommendations per round, but retain and resolve
every material finding. Record `accepted`, `rejected`, `deferred`, or `omitted`
with a reason as the implementation disposition. Ask the user only when the
finding exposes an unresolved material scope, safety, authority, or external
effect. Advisory disposition alone does not block implementation or landing.

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

Design work is ready for implementation when observable outcomes are clear
enough to build, routine decisions have been resolved or recorded, and any
unresolved scope, safety, authority, or external effect is surfaced. Durable
design acceptance is optional unless the user explicitly requests that artifact
or the exact-design proof path.

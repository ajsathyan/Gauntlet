---
name: design
description: Use before non-trivial implementation to brainstorm material alternatives, resolve product decisions and edge cases, and create or update one accepted durable design with its canonical Build Contract.
---

# Design

Turn a non-trivial implementation request into one durable, user-owned design. A bounded, low-consequence Normal Request bypasses this skill and goes directly to the requested artifact and smoke check.

## Design Gate

1. Read existing product documents, repository behavior, research, and user decisions before asking questions.
2. Explicitly brainstorm materially different approaches. Record the options considered, the recommended approach, and the practical tradeoff. Do not manufacture alternatives that would not change the product or implementation boundary.
3. Resolve material assumptions, feature-completeness questions, user-visible states, edge cases, observable acceptance, and required non-effects. Ask at most three short questions per user round and only when the answer changes behavior, scope, acceptance, authority, cost, risk, or an external effect.
4. Create or update one permanent design document only with explicit user authority. Preserve direct user edits and keep unaccepted suggestions outside it.
5. The exact Acceptance section is the canonical Build Contract. Do not copy, compile, summarize, or narrow it into a second requirements checklist. Build and Verify read the accepted design directly.
6. Obtain explicit acceptance of the exact document before Build. Later semantic edits require re-acceptance.

Legacy accepted PRDs remain valid designs. They do not need rewriting merely to adopt new terminology.

## Pre-Build Review

After acceptance and before Build, run three independent lenses against the same compact accepted design:

- **Product completeness:** missing user outcomes, feature states, assumptions, and feature-level edge cases.
- **Engineering shape:** boundaries, dependencies, migrations, compatibility, and parallel ownership conflicts.
- **Proof and consequence:** observable oracles, false-green paths, required non-effects, and concrete security, privacy, billing, destructive, production, or specialist triggers.

Each lens returns only material findings. Deduplicate without losing provenance. Show the user at most three recommendations per round, but retain and resolve every material finding. Each finding ends as `accepted`, `rejected`, `deferred`, or `omitted` with a reason. An unresolved material finding blocks only the affected Build work; it may not disappear because of the display cap.

Keep the complete review results in a task-temporary JSON file. Before Build
edits, invoke `workflow build-entry` through the installed Gauntlet CLI path
named by the router. Pass the accepted design and all three review results. A
failed command blocks Build. Its returned contract is temporary execution input,
not a durable design, implementation plan, or controller artifact.

## Output

- Durable design path and exact accepted revision or digest
- Material alternatives and decisions recorded
- Canonical Build Contract location
- Review findings and terminal dispositions
- Unresolved decision or `Cannot verify` limit

## Completion

Design completes when the user has accepted one exact durable design, its `Acceptance` section contains observable outcomes and required non-effects, and every material pre-build finding has a terminal disposition.

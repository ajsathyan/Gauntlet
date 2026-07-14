# Incremental Replacement Strategy

## Inputs

- Proved target architecture and stable seams
- Capabilities that can migrate independently
- Route, consumer, and rollback map

## Actions

1. Order capabilities by dependency and risk. Start with a representative vertical slice, then migrate bounded units behind stable contracts.
2. Keep old and new implementations comparable at each seam. Route one bounded capability at a time and retain a fast rollback until its ledger rows pass.
3. Prevent new dependencies on legacy internals. Move shared invariants to their authoritative layer before deleting family-local copies.
4. Keep intermediate states coherent, owned, testable, and safe to maintain longer than expected.
5. Separate read and write cutovers when state or persistence makes them independently risky.

## Gate

Pass strategy selection when seams isolate side effects and state, representative capabilities can cut over independently, rollback is concrete, and the intermediate architecture does not require duplicating unsettled shared contracts.

## Receipt

Add `incremental` to `migration-strategy.md` with ordering, seams, routing, rollback, ownership, and intermediate-state constraints. Update the selected strategy in `refactor-state.json`.

## Invalidation

Re-select strategy when capabilities cannot migrate independently, stable seams disappear, shared-state cutover becomes atomic, or the intermediate system violates compatibility or ownership boundaries.

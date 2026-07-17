# Dual-Run Strategy

## Inputs

- Proved target architecture
- State or output requiring controlled coexistence
- Safe comparison, reconciliation, rollback, and cutover mechanisms

## Actions

1. Define control and candidate paths, authority for returned results, comparison keys, mismatch policy, and observability before enabling coexistence.
2. Use shadow reads or duplicated pure computation when both paths can run safely. Do not duplicate non-idempotent shared-state side effects.
3. For state migration, define dual-write order, backfill, reconciliation/checksums, read cutover, write cutover, reverse-shadow or rollback, and final legacy deletion.
4. Bound mismatch storage and privacy exposure. Separate expected nondeterminism from semantic divergence.
5. Promote through explicit lifecycle criteria; keep the control authoritative until candidate evidence passes unless the migration contract says otherwise.

## Definition of Done

Strategy selection is done when dual execution is safe, comparisons are semantically meaningful, reconciliation and rollback are tested, side-effect authority is singular, and cutover criteria are observable.

## Receipt

Add `dual-run` to `migration-strategy.md` with control authority, comparison/reconciliation design, lifecycle criteria, rollback, privacy bounds, and deletion conditions. Update the selected strategy in `refactor-state.json`.

## Invalidation

Re-select strategy when both paths cannot run safely, side effects duplicate, comparison loses semantic meaning, reconciliation cannot bound data loss, or rollback becomes unavailable.

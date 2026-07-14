# Mechanical Replacement Strategy

## Inputs

- Proved target architecture and frozen contracts
- Strong implementation-independent oracle
- Evidence that old-to-new transformation is systematic and side effects are controlled

## Actions

1. Write explicit translation rules for syntax, types, errors, concurrency, platform behavior, and external contracts.
2. Partition work into non-overlapping translation units with frozen interfaces and one integrator.
3. Compare each unit against the original using implementation-independent tests and identical fixtures. Keep the original available as an oracle.
4. Preserve tests and supported platforms during translation. Defer unrelated architectural cleanup until translation parity unless the proved target architecture requires the change.
5. Record translation exceptions and prove them explicitly; do not infer parity from mechanical similarity.

## Gate

Pass strategy selection when translation rules cover representative common, complex, and outlier units; the oracle detects intentional mismatches; and the transformation does not require uncontrolled shared-state coexistence.

## Receipt

Add `mechanical` to `migration-strategy.md` with precondition evidence, translation guide path, partitions, oracle, rollback, and known exceptions. Update the selected strategy in `refactor-state.json`.

## Invalidation

Re-select strategy when mappings become semantic rather than mechanical, the oracle depends on the old implementation, unsupported platforms emerge, or partition ownership overlaps.

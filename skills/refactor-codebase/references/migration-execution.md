# Migration Execution

## Inputs

- Proved architecture, frozen contracts, selected strategy, and migration order
- Parity ledger, compatibility matrix, and baseline protocols

## Actions

1. Create `migration-register.tsv` with capability, owner, dependencies, contract version, current state, parity evidence, rollback, and retirement status.
2. Create `temporary-scaffolding.tsv`. For every adapter, bridge, compatibility layer, dual implementation, or migration tool, record owner, purpose, comparison method, deletion condition, and review point.
3. Migrate bounded capabilities in dependency order. Prove their relevant ledger and compatibility rows before routing more traffic or deleting old code.
4. Add or update behavior tests at shared-contract boundaries. Keep family-local code only for irreducible variation; remove local copies after the shared invariant owner passes all consumers.
5. Preserve public terminology and contracts unless explicitly in scope. Record repairs separately from preserved parity.
6. Re-run representative slices after shared-contract changes. Reconcile routes, exports, public exports, presets/fixtures, pipelines, and saved workflows continuously.
7. Count production, test, configuration, generated logic, dependencies, and temporary scaffolding without hiding displaced complexity.

## Gate

Pass each capability when every owned parity and compatibility row passes, rollback or recovery is proved, no supported consumer uses the superseded path, and removal deletes artifacts rather than features. Pass the phase when no capability remains unmigrated or ambiguously retired.

## Receipt

Maintain `migration-register.tsv`, `temporary-scaffolding.tsv`, and row-level evidence links. Update `refactor-state.json` after every bounded cutover with artifact hashes, contract version, open mismatches, and remaining scaffolding.

## Invalidation

Pause or reopen earlier phases when a contract changes, new capability evidence appears, a mismatch invalidates architecture assumptions, rollback fails, or migrated behavior depends on a retired path.

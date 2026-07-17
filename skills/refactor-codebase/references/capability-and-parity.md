# Capability And Parity

## Inputs

- Approved source snapshot and baseline
- UI/routes, tests, docs, examples, presets, fixtures, schemas, APIs, CLI, and integration surfaces

## Actions

1. Infer one sentence describing what users accomplish. If README, UI, tests, and workflows do not support one consistent product job, ask only: “In one sentence, what should this product help its users accomplish?”
2. Invoke `$craft-product-terminology` in `capability-map` mode. Preserve existing public terms. Map cohesive responsibilities, non-responsibilities, owners, dependencies, and reasons to change.
3. Reconcile independent discovery across routes/deep links/history; mouse/keyboard/focus/accessibility/responsive behavior; presets/examples/tests; imports/exports/APIs/CLI/plugins; schemas/saved data/versioning; loading/cancellation/validation/empty/error states; and security, privacy, telemetry, or operational behavior where evidenced.
4. Treat any reachable UI, documented workflow, fixture, test, saved format, external contract, accessibility interaction, or recoverable intent as capability evidence. Broken behavior becomes `repair`, not deletion.
5. Record each row as `preserve`, `repair`, `consolidate`, `remove-artifact`, or `needs-user-decision`. Use `remove-artifact` only when no distinct user-observable contract or supported consumer exists. Never classify a feature for removal.
6. Build a compatibility matrix for every saved or external format: old-to-new load; semantic load/save and unknown-field preservation; new-to-old requirement; versions and unsupported versions; identifiers, ordering, defaults, precision, errors; interrupted recovery and idempotence; export content equivalence.
7. Store inventory areas and capability rows in `parity-ledger.json`. Record unresolved discovery areas explicitly and validate the draft with [validate_parity_ledger.py](../scripts/validate_parity_ledger.py) using `--allow-incomplete`. Freeze the inventory version before architecture work.

## Definition of Done

Capability mapping is done when the product job and capability boundaries are coherent, every discovery area is resolved or explicitly blocked, every evidenced capability has a row and source citation, and every external or saved format has compatibility cases.

## Receipt

Write `capability-map.md`, `parity-ledger.json`, and `compatibility-matrix.tsv`. Update `refactor-state.json` with their hashes, inventory version, Definition of Done result, and unresolved areas.

## Invalidation

Reopen this phase when the product job, source snapshot, public terminology, capability evidence, supported integration, or compatibility requirement changes. Any material ledger change invalidates downstream architecture selection until reassessed.

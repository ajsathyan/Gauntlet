# Verification And Completion

## Inputs

- Current state index and every phase artifact
- Completed destination implementation and immutable-source snapshot
- User-supplied completion targets

## Actions

1. Run [source_integrity.py](../scripts/source_integrity.py) in `compare` mode against `source-snapshot.json`, then verify any supplementary remotes, ignored-file, or LFS interpretation recorded at baseline.
2. Reconcile every discovery area, route, preset/fixture, control/state, pipeline, editor, import/export, saved workflow, error/empty/loading path, accessibility interaction, and external contract. Require a final result and evidence link for every retained row.
3. Run all compatibility cases, including content semantics and interrupted recovery where relevant. A created file or successful load alone is insufficient.
4. Invoke `$refactor-performance` for optimization and comparable final measurements. Report test feedback separately from startup, interaction latency, throughput, memory, export duration, bundle/artifact size, and other relevant product measures.
5. Recompute LOC with [measure_loc.py](../scripts/measure_loc.py) and compare the emitted measurement to baseline. Audit excluded files, generated/configuration logic, dependencies, coverage, and displaced complexity when gains are unusually large.
6. Honor an explicitly requested verification surface. Otherwise, use the built-in Browser first for local or hosted web applications so verification can run without taking over the user's active desktop. Fix the route, fixture, viewport, browser state, and action order; check DOM and accessibility state, visual alignment, mouse and keyboard interactions, focus, editing, save/reload, validation/error behavior, screenshots, and export download/content. Return compact structured row results and evidence paths instead of interaction narration. Use Chrome only when the workflow requires the user's real browser profile, signed-in session, or extensions. Use Computer Use for native applications, OS-level dialogs, cross-application workflows, or browser-inaccessible behavior. If the user explicitly requested Computer Use, preserve it as the verification surface. When the selected surface cannot exercise the declared contract, record `Cannot verify`; do not silently substitute weaker evidence.
7. Run independent black-box, compatibility, and architecture/metric reviews. Use `fork_turns: "none"` and the stable observable-review packet only when the assigned observable contract is frozen and every input is available through its artifact paths. Resolve or explicitly defer findings within root-task authority.
8. Run [validate_parity_ledger.py](../scripts/validate_parity_ledger.py) without `--allow-incomplete`. Prove no dead routes, unused public exports, broken controls, unreachable retained presets, orphan pipelines, family-local shared-invariant copies, or unowned scaffolding remain.
9. Demonstrate adding one representative standard capability primarily through manifest/configuration, narrow renderer/adapter setup, and parity fixture without a family-sized subsystem.

## Gate

Pass only when source integrity is exact; all inventory and compatibility rows resolve; deterministic tests and external checks pass; measurements satisfy explicit targets; shared invariants have one owner; temporary scaffolding is deleted or explicitly accepted; and no material `Cannot verify` item remains. If a binding target conflicts with a higher priority, do not claim completion—report the measured gap and evidence.

## Receipt

Write `performance-results.json` and `final-verification.md`. Link source integrity, parity, compatibility, Browser, Chrome, or Computer Use evidence as applicable, test commands/results, LOC/runtime comparisons, extension demonstration, review disposition, residual risks, and `Cannot verify` items. Mark `refactor-state.json` complete only after all links and hashes verify.

## Invalidation

Reopen the earliest affected phase when source or destination changes, any row regresses, a comparison protocol changes, a completion target changes, a reviewer finds missing capability evidence, or final evidence cannot be reproduced.

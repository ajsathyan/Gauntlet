# Architecture Proof

## Inputs

- Selected breakthrough hypotheses and falsification criteria
- Frozen capability and compatibility artifacts
- Baseline measurements

## Actions

1. Select three representative slices before implementation: a common simple case, the most behaviorally complex case, and a structural outlier with materially different data, interaction, persistence, export, or runtime demands.
2. Prototype the strongest hypothesis end to end on all three. Prototype the second only when the first is falsified or evidence cannot distinguish them cheaply.
3. Define narrow contracts for capability identity, normalized data, rendering, controls/validation, editor state, persistence, imports/exports, and parity fixtures only where evidenced.
4. Give each shared invariant—one rule or guarantee that must remain true across contexts—one authoritative owner at the narrowest common layer. Do not merge similar behavior with different semantics, ownership, lifecycle, or reason to change.
5. Exercise every relevant ledger and compatibility row for each slice. Compare LOC, concepts, dependencies, extension steps, tests, and runtime against the baseline.
6. Track escape hatches. Reject or revise a declarative model when configuration contains control flow, lifecycle policy, scattered family rules, or growing exceptional syntax.
7. Have independent reviewers attack parity, false abstractions, displaced/generated/dependency complexity, metric validity, and extension cost.

## Gate

Pass when all three slices meet parity and compatibility, the architecture survives reviewer findings, shared invariants have clear owners, extension is primarily manifest/configuration for a standard case, and claimed step-change mechanisms are measured rather than inferred.

## Receipt

Write `architecture-decision.md` and `prototype-results.json` with contract boundaries, slice selection, measurements, exceptions, review findings, rejected hypotheses, and the chosen target architecture. Update `refactor-state.json` with hashes and contract version.

## Invalidation

Reopen this phase when a shared contract changes, a new structural outlier appears, a prototype parity row regresses, an escape hatch becomes a policy language, or a performance comparison becomes invalid.

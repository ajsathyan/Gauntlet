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
8. Apply the shared-architecture rules from `SKILL.md` to each prototype and record dependency, contract, ownership, test, repository-check, and extension evidence.

## Definition of Done

Architecture proof is done when all three slices meet parity and compatibility, satisfy the shared-architecture rules, survive reviewer findings, and measure rather than infer their extension-cost and step-change claims.

## Receipt

Write `architecture-decision.md` and `prototype-results.json` with contract boundaries, slice selection, measurements, exceptions, review findings, rejected hypotheses, and the chosen target architecture. Update `refactor-state.json` with hashes and contract version.

## Invalidation

Reopen this phase when a shared contract changes, a new structural outlier appears, a prototype parity row regresses, an escape hatch becomes a policy language, or a performance comparison becomes invalid.

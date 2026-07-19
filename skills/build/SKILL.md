---
name: build
description: Use when implementing an accepted durable design autonomously from its canonical Build Contract with an ephemeral plan and bounded workstreams.
---

# Build

Implement the accepted design without translating its product meaning into another durable requirements artifact.

## Inputs

- Exact accepted durable design
- Its `Acceptance` section, read in place as the canonical Build Contract
- Terminal pre-build review dispositions
- Repository instructions and current working state

If the accepted design is unavailable, semantically stale, lacks observable acceptance, or has an unresolved material finding that affects the work, stop. Do not infer or narrow the missing product decision.

## Procedure

1. Read the accepted design directly, inspect the repository, and trace relevant contracts and failure paths.
2. Create an internal, ephemeral implementation plan. It may change as evidence changes and disappears with the task; the accepted Design remains the only durable requirements source.
3. Keep work in the parent when one coherent lane is fastest. Delegate only independent ownership, state, or proof. Each child gets a compact workstream assignment containing its outcome slice, owned files or state, dependencies, constraints, proof, return contract, and ask-parent policy. The child reads the accepted outcome slice without receiving a rewritten requirements contract.
4. The parent keeps product meaning, shared contracts, integration, user decisions, GitHub effects, and final verification.
5. Read before editing, preserve unrelated user work, use practical RED-GREEN-REFACTOR for behavior changes, and integrate coherent atomic changes.
6. Run focused edit-loop proof as work lands. Execute configured required sensors with `sensors run`; a plan, normalized result, or stale pass does not prove completion.
7. Hand the exact integrated revision and accepted design to Verify. Build does not self-certify completion.

## Workstream Receipt

Return only changed paths or state, evidence and its limits, risks, and a blocker or required parent decision. Child-authored tests are evidence; they cannot replace or weaken the canonical Build Contract.

## Completion

Build completes when the exact integrated candidate is ready for independent Verify, every claimed outcome maps back to the accepted design, unrelated work is preserved, and missing proof is stated without a completion claim.

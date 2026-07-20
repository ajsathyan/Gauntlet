---
name: build
description: Use when implementing a requested outcome autonomously with an ephemeral plan, bounded workstreams, recorded decisions, and proportional proof.
---

# Build

Implement the requested outcome without waiting for a separate design or merge
acceptance and without translating product meaning into another durable
requirements artifact.

## Inputs

- User request and conversation decisions
- Existing product and repository context
- Any accepted durable design and its exact `Acceptance` section
- Advisory review findings and implementation dispositions when available
- Repository instructions and current working state

Resolve routine product and engineering decisions independently inside the
requested scope and record material decisions for the production acceptance
request. Stop only when an unresolved choice changes scope, safety, authority, or
an external effect, or when objective evidence makes the affected action unsafe.

Design acceptance and `workflow build-entry` do not authorize or block Build.
When an accepted design exists and exact-design proof is useful,
`workflow build-entry` may create a task-temporary proof contract. A failure
blocks only that optional contract path.

## Procedure

1. Read the request, any accepted design, and repository context directly; trace relevant contracts and failure paths.
2. Create an internal, ephemeral implementation plan. It may change as evidence
   changes and disappears with the task; the request and any accepted Design
   remain the requirements sources.
3. Keep work in the parent when one coherent lane is fastest. Delegate only independent ownership, state, or proof. Each child gets a compact workstream assignment containing its outcome slice, owned files or state, dependencies, constraints, proof, return contract, and ask-parent policy.
4. The parent keeps requested product meaning, shared contracts, integration,
   GitHub effects, and final verification.
5. Read before editing, preserve unrelated user work, use practical RED-GREEN-REFACTOR for behavior changes, and integrate coherent atomic changes.
6. Run focused edit-loop proof as work lands. Execute configured required sensors with `sensors run`; a plan, normalized result, or stale pass does not prove completion.
7. Hand the exact integrated candidate, requested outcomes, material decision
   record, and evidence to Verify. When using the optional exact-design proof
   path, run `workflow bind-candidate` with the temporary contract, complete
   review results, and exact integrated commit and tree. Build does not
   self-certify completion.

## Workstream Receipt

Return only changed paths or state, material decisions, evidence and its limits,
risks, and an objective blocker or required parent decision. Child-authored tests
are evidence; they cannot replace or weaken requested outcomes or an applicable
canonical Build Contract.

## Completion

Build completes when the exact integrated candidate is ready for independent
Verify, every claimed outcome maps back to the request and any applicable
accepted design, material implementation decisions are recorded, unrelated work
is preserved, and missing proof is stated without a completion claim.

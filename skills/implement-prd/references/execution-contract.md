# PRD Execution Contract

## Compiled Ticket Graph

Use stable, searchable Markdown:

```text
# <run title>
## Epic <EPIC-ID>: <title>
### Ticket <EPIC-ID>-T01: <title>
#### Objective
#### Scope Areas
#### Ownership
#### Dependencies
#### Inputs
#### Outputs
#### Constraints And Authority
#### Proof Contract
#### Verification Layer
#### Return Contract
#### Ask Parent Policy
```

Tickets are current execution units; Scope Areas are stable product units. A Ticket may reference several related Scope Areas, and a Scope Area may require sequential Tickets. One implementation Ticket has one active child owner. A separate verifier Ticket may evaluate the same output independently.

## Durable Run

Store the run under the canonical local-document root declared by `doc_org.md`:

```text
executions/<run-id>/
  source-lock.json
  manifest.json
  shared-context.md
  resume.md
  events.jsonl
  tickets/*.md
  receipts/*.json
  evidence/*.md
  cohorts/*.md
  release/integration.md
  release/deployment.md
  release/production-verification.md
```

The parent alone changes the manifest, resume state, cohorts, and release evidence. Children own their isolated code worktree plus the assigned receipt and evidence paths. Write state atomically. Claims contain the agent ID and attempt. Dispatched Ticket revisions are immutable. Append events; never reconstruct current state by replaying chat.

Validate transitions:

```text
discussing -> accepted -> compiled -> executing -> integrating
-> cohort_verified -> prd_verified -> merged -> deployed
-> production_verified -> complete
```

Do not skip a required state because a receipt says `done`. Invalidate and recompile only Tickets affected by changed Scope Area hashes; do not discard unaffected verified work.

## Resume And Materialization

After compaction or restart, read `resume.md`, `manifest.json`, and `source-lock.json`, then validate them against the canonical PRD before dispatching more work. Use the deterministic controller for validate/freeze, compile, materialize, claim, receipt, integrate, cohort/full/release transitions, and resume operations. Do not hand-edit machine-owned state when the controller is available.

Materialize one bounded child bundle from a stable prefix, applicable instruction version, relevant cohort context version, named dependency contracts, and required source slices. Keep run IDs, timestamps, absolute paths, live status, hashes, and agent nicknames out of the stable prefix and place unavoidable volatile values last.

## Meaningful Verification

- Ticket: verify the changed behavior immediately after parent integration.
- Cohort: verify the shared interface or invariant across related Tickets.
- Full PRD: verify every accepted outcome and required non-effect for the Implementation Target.
- Release: verify the pull request, merged exact revision, deployment, production behavior, and rollback path required by the PRD.

A child receipt points to evidence. It is not acceptance. Tests written by a child are evidence, but an edited assertion, fixture, grader, or oracle cannot establish the behavior until the parent independently reviews or redefines it. Keep raw logs in evidence files and receipts compact.

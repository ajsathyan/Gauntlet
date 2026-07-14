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

The controller accepts a compact machine graph with `version`, `scope_areas`, `shared_context`, `cohorts`, and `tickets`. `scope_areas` is only the sorted list of locked PRD Scope Area IDs; do not duplicate or rewrite their product descriptions in the graph. Each Ticket supplies `id`, `epic_id`, `title`, `objective`, `scope_area_ids`, `cohort_id`, `dependencies`, `ownership`, `constraints`, `acceptance`, `proof`, `return_contract`, `ask_parent_policy`, and relevant `source_files`. Scheduling fields are `kind` (`implementation` or `verification`), numeric `priority`, `interface_first`, and `affinity`. `proof` contains a behavioral `claim`, observable `oracle`, plausible `wrong_case`, and `non_effects`. This normalized JSON is local controller input, not a child packet or a second product specification; the controller validates it against locked target Epic/Scope sections, renders a searchable Markdown graph and immutable prose Tickets, and sends only one bounded bundle to each child.

## Durable Run

Store the run under the canonical local-document root declared by `doc_org.md`:

```text
executions/<run-id>/
  source-lock.json
  manifest.json
  ticket-graph.json
  ticket-graph.md
  shared-context/global-v1.md
  shared-context/<cohort>-v<N>.md
  resume.md
  events.jsonl
  tickets/*.md
  receipts/*.json
  handoffs/*.bundle.md
  handoffs/*.receipt.json
  evidence/*.md
  cohorts/*.md
  release/prd-verification.md
  release/merge.md
  release/deployment.md
  release/production-verification.md
  release/rollback.md
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

Use the installed controller at `$GAUNTLET_ROOT/scripts/prd-run.py` (or the repository copy while changing Gauntlet):

```text
init --executions <canonical-root>/executions --run-id <ID> --source <prd.md> --target <EPIC-ID> [--target <EPIC-ID>] --release-contract <version-or-hash> --release-stages merge[,deployment,production-verification] [--integration-branch <branch>]
transition --run <run> --to <next-state>
compile --run <run> --graph <ticket-graph.json>
ready --run <run> [--affinity <context-key>]
resume --run <run>
claim --run <run> --ticket <ID> --agent <agent-id> --attempt <N>
materialize-ticket --run <run> --ticket <ID> [--output <path>]
record-receipt --run <run> --ticket <ID> --receipt <receipt.json>
integrate --run <run> --ticket <ID> --evidence <parent-proof> --summary <claim>
verify-cohort --run <run> --cohort <ID> --result pass|fail --evidence <run-file>
verify-prd --run <run> --result pass|fail --summary <claim> --evidence <run-file>
record-merge --run <run> --pr <reference> --merged-sha <sha> --main-sha <sha> --evidence <reference>
record-release --run <run> --stage deployment|production-verification --result pass|fail|skipped --summary <claim> --evidence <reference> [--revision <merged-main-sha>]
record-rollback --run <run> --trigger <condition> --action <action> --result pass|fail --evidence <reference>
reconcile --run <run> --source <prd.md> --graph <ticket-graph.json>
```

`init` rejects target Epics that differ from `Implementation target`, are not `Accepted`, or lack searchable Scope Area sections. Move `discussing` to `accepted` with `transition` before compilation; `compile` performs the `accepted` to `compiled` transition and rejects graph Epic/Scope coverage that differs from the source lock. Claim before materializing so the bundle contains exact evidence and receipt handoff paths. The parent must supply verification evidence with distinct content from the child's evidence before `integrate` accepts a Ticket.

Materialize one bounded child bundle from a stable prefix, applicable instruction version, relevant cohort context version, named dependency contracts, and relevant source paths. The canonical handoff names the exact receipt schema and writable evidence/receipt destinations. Keep run IDs, timestamps, absolute paths, live status, hashes, agent nicknames, and parent PR strategy out of the stable prefix and place unavoidable volatile values last. The run manifest, not the child bundle, records the parent integration branch and one-final-PR strategy; it records the parent as the merge executor only after user authority, not as a grant of authority.

## Meaningful Verification

- Ticket: verify the changed behavior immediately after parent integration.
- Cohort: verify the shared interface or invariant across related Tickets.
- Full PRD: verify every accepted outcome and required non-effect for the Implementation Target.
- Release: verify the pull request, merged exact revision, deployment, production behavior, and rollback path required by the PRD.

A child receipt points to evidence. It is not acceptance. Tests written by a child are evidence, but an edited assertion, fixture, grader, or oracle cannot establish the behavior until the parent independently reviews or redefines it. Keep raw logs in evidence files and receipts compact.

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

The controller accepts a compact machine graph with `version`, `scope_areas`, `shared_context`, `cohorts`, `tickets`, and, for `review-prs-plus-final`, `review_units`. `scope_areas` is only the sorted list of locked PRD Scope Area IDs; do not duplicate or rewrite their product descriptions in the graph. Each Ticket supplies `id`, `epic_id`, `title`, `objective`, `scope_area_ids`, `cohort_id`, `dependencies`, `ownership`, `constraints`, `acceptance`, `proof`, `return_contract`, `ask_parent_policy`, and relevant `source_files`. Scheduling fields are `kind` (`implementation` or `verification`), numeric `priority`, `interface_first`, and `affinity`. `proof` contains a behavioral `claim`, observable `oracle`, plausible `wrong_case`, and `non_effects`. Each Review Unit supplies exact `ticket_ids` and unit `dependencies`; all Tickets belong to exactly one unit, and membership freezes at compile. This normalized JSON is local controller input, not a child packet or a second product specification; the controller validates it against locked target Epic/Scope sections, renders a searchable Markdown graph and immutable prose Tickets, and sends only one bounded bundle to each child.

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
  outcomes/
```

The parent alone changes the manifest, resume state, lanes, cohorts, and release evidence. Children own their isolated code worktree plus the assigned receipt and evidence paths. Write state atomically. Claims contain the agent ID and attempt. Dispatched Ticket revisions are immutable. Append events; never reconstruct current state by replaying chat. On restart, reconcile `events.jsonl` to the manifest's committed sequence: remove an uncommitted or partial tail, reject a missing committed event, and never replay a committed event. Repeating reconciliation with identical source and graph bytes is a no-op.

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
init --executions <canonical-root>/executions --run-id <ID> --source <prd.md> --target <EPIC-ID> [--target <EPIC-ID>] --release-contract <version-or-hash> --release-stages merge[,deployment,production-verification] --pr-strategy single-final-pr|review-prs-plus-final [--integration-branch <branch>]
transition --run <run> --to <next-state>
compile --run <run> --graph <ticket-graph.json>
ready --run <run> [--affinity <context-key>]
resume --run <run>
claim --run <run> --ticket <ID> --agent <agent-id> --attempt <N>
claim-lane --run <run> --lane <lane-id> --agent <agent-id> --attempt <N> --affinity <context-key> --ticket <ID> [--ticket <ID> ...]
materialize-ticket --run <run> --ticket <ID> [--output <path>]
materialize-lane --run <run> --lane <lane-id>
record-receipt --run <run> --ticket <ID> --receipt <receipt.json>
integrate --run <run> --ticket <ID> --evidence <parent-proof> --summary <claim>
verify-cohort --run <run> --cohort <ID> --result pass|fail --evidence <run-file>
verify-prd --run <run> --result pass|fail --summary <claim> --evidence <run-file>
record-merge --run <run> --pr <reference> --merged-sha <sha> --main-sha <sha> --evidence <reference>
record-release --run <run> --stage deployment|production-verification --result pass|fail|skipped --summary <claim> --evidence <reference> [--revision <merged-main-sha>]
record-rollback --run <run> --trigger <condition> --action <action> --result pass|fail --evidence <reference>
reconcile --run <run> --source <prd.md> --graph <ticket-graph.json>
record-authority --run <run> --capability <capability> --source <user-authority>
authority-status --run <run> --capability <capability>
review-unit-status --run <run> --unit <ID>
project-pr --run <run>
```

`init` rejects target Epics that differ from `Implementation target`, are not `Accepted`, or lack searchable Scope Area sections. It also freezes the PR strategy. Move `discussing` to `accepted` with `transition` before compilation; `compile` performs the `accepted` to `compiled` transition, rejects graph Epic/Scope coverage that differs from the source lock, and freezes Review Unit membership for `review-prs-plus-final`. Claim before materializing so the bundle contains exact evidence and receipt handoff paths. The parent must supply verification evidence with distinct content from the child's evidence before `integrate` accepts a Ticket.

`claim` preserves the single-Ticket path. `claim-lane` atomically leases any number of ready Tickets to one agent only when every Ticket declares the requested affinity and all share one cohort and an identical dependency contract. `materialize-lane` writes one generated-context bundle and privacy-safe metadata record per dispatched Ticket and returns their common stable-prefix digest. Lane membership is scheduling metadata; Ticket state remains authoritative. Record and integrate a completed Ticket immediately even while a sibling is blocked, then release only the completed Ticket's dependents.

The persisted child protocol remains `prd-run/v1`; this is separate from the schema v2 Project PR projection. Existing immutable bundles remain readable through the single-Ticket command. Runs initialized before PR strategy metadata existed keep their legacy schema v1 closeout path; the controller does not retroactively claim repository/head proof for them. Newly initialized runs freeze their PR strategy, repository binding, and, when selected, Review Unit membership at compile.

Materialize each bounded child bundle through `scripts/generated_context.py::render_manifest` from a stable prefix, applicable instruction version, relevant cohort context version, named dependency contracts, and relevant source paths. The canonical handoff names the exact receipt schema and writable evidence/receipt destinations. Keep run IDs, timestamps, absolute paths, live status, hashes, agent nicknames, integration branch, PR strategy, Review Unit topology, and merge authority out of the child context. The run manifest and compiled graph own that parent-only state.

After full-PRD verification, `project-pr --run <run>` emits the controller-owned schema v2 projection for the complete Project PR with deterministic locked Epic/Scope coverage. Verification freezes the repository identity and exact integration head; projection fails after any clean post-verification commit. Pass the run to `gauntlet.py merge prepare|plan|execute --run <run>`. Never replace this projection with a schema v1 `--handoff`; schema v1 remains only for non-run patches. Initialization registers the integration branch in the repository's Git common directory so this downgrade protection also covers custom execution roots. `merge execute` requires distinct `merge-to-default` authority and binds GitHub's merge to the projected head. For `review-prs-plus-final`, run `gauntlet.py review-unit prepare|plan|execute --run <run> --unit <id>` for every dependency-ready unit before generating the Project PR. Review checks bind the open PR's exact GitHub head, remote branch, integration base, and synthetic tree; integration and branch cleanup use explicit ref leases.

## Meaningful Verification

- Ticket: verify the changed behavior immediately after parent integration.
- Cohort: verify the shared interface or invariant across related Tickets.
- Full PRD: verify every accepted outcome and required non-effect for the Implementation Target.
- Release: verify the pull request, merged exact revision, deployment, production behavior, and rollback path required by the PRD.

A child receipt points to evidence. It is not acceptance. Tests written by a child are evidence, but an edited assertion, fixture, grader, or oracle cannot establish the behavior until the parent independently reviews or redefines it. Keep raw logs in evidence files and receipts compact.

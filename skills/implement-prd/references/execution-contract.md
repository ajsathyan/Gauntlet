# Epic Execution Contract

## Product Task And Launch Set

One product task may shape many Epics in one canonical PRD. `Implementation target` lists the complete accepted launch membership. `gauntlet.py epic-tasks init` freezes that membership, the source snapshot, each Epic's title, release stages, dependency boundaries, and closed high-consequence trigger IDs (or `none`). The product task executes only the controller's missing `create_thread` actions and records each proven native task ID.

Each target Epic gets one visible implementation task and one Execution Run. An Epic task reads `source.snapshotPath` from the launch set and passes that immutable file to `prd-run.py init --source`; it never passes the mutable canonical PRD path and never creates another Epic task. A dependency blocks only the downstream Epic whose declared `merged`, `deployed`, or `productionProved` boundary is unsatisfied; unrelated Epics continue.

## Compiled Ticket Graph

Each run locks exactly one accepted Epic. Tickets remain current execution units and Scope Areas remain stable product responsibilities. A Ticket has one implementation owner. The parent verifies ordinary evidence directly; independent verification Tickets are reserved for a named consequential boundary.

The normalized graph contains `version`, `scope_areas`, `shared_context`, `cohorts`, `tickets`, `checks`, `review`, and optional `review_units`. `cohorts` may be empty. A Ticket's `cohort_id` may be absent; assign one only when multiple Tickets share a material invariant. `checks` defines targeted Ticket checks, optional Cohort checks, and exactly one `final-epic` check. `review.triggers` must exactly equal the canonical Epic's locked declaration. A non-empty trigger set requires exactly the authority/security, failure/recovery, and black-box lenses; `none` requires zero review lenses.

## Durable Run

The run stores `source-lock.json`, `manifest.json`, `ticket-graph.json`, immutable Ticket bundles, compact receipts, evidence, optional Cohort reports, and release records. The parent alone writes controller state. Resume from `resume.md`, `manifest.json`, and `source-lock.json`; conversation history is advisory.

The lifecycle is:

```text
discussing -> accepted -> compiled -> executing -> integrating
-> cohort_verified -> epic_verified -> merged -> deployed
-> production_verified -> complete
```

`cohort_verified` is valid with zero declared Cohorts. A skipped inapplicable release stage is not production proof.

## Controller Commands

Use the installed controller:

```text
init --executions <root> --run-id <ID> --source <snapshot.md> --target <EPIC-ID> --launch-set <launch.json> --release-contract <version-or-hash> --release-stages merge[,deployment,production-verification] --pr-strategy single-final-pr|review-prs-plus-final
transition --run <run> --to <next-state>
compile --run <run> --graph <ticket-graph.json>
ready|resume|completion|run-facts --run <run>
claim|claim-lane|materialize-ticket|materialize-lane ...
record-receipt --run <run> --ticket <ID> --receipt <receipt.json>
integrate --run <run> --ticket <ID> --evidence <parent-proof> --summary <claim>
verify-cohort --run <run> --cohort <ID> --result pass|fail --evidence <receipt.json>
verify-epic --run <run> --verification-receipt <receipt.json>
record-merge|record-release|record-rollback ...
record-authority|authority-status ...
review-unit|review-unit-status ...
project-pr --run <run>
```

`init` rejects more than one target, launch/source mismatch, incomplete launch membership, and an Epic without its own task. `verify-epic` binds the canonical Epic section digest, exact commit and tree, command, toolchain, fixtures or oracle, relevant environment, result, and evidence. `completion` projects `implemented`, `merged`, `deployed`, `productionProved`, `complete`, exact revision, and pending gates without model prose. `run-facts` supplies the compact proof/review contract to helpers. `project-pr` emits schema 3.0 facts from the locked Epic, changed paths, accepted criteria, verification receipts, deferrals, completion state, and release gates. There are no `record-project-summary` or `record-epic-outcome` commands.

## Verification

- Ticket: targeted check after integration.
- Cohort: once, only for a declared shared interface or invariant.
- Final Epic: fresh verification of canonical acceptance on the exact integrated revision.
- Release: exact merge, deployment, production behavior, and rollback required by the Epic.

Reuse a verification receipt only when commit and tree, command, toolchain, fixtures or oracle, and relevant environment identity match exactly. A child receipt is an evidence pointer, not acceptance. The parent owns the oracle and final Epic judgment.

For a consequential trigger, run deterministic checks before three parallel review lenses: trust/security/authority; failure/concurrency/recovery; and black-box behavior/non-effects. Fix findings once, rerun affected proof, then execute the repository-owned dry run and any meaningful bounded canary and rollback. Gauntlet coordinates and records these gates; provider-specific actions remain repository-owned.

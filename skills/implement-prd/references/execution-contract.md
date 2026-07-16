# Epic Execution Contract

## Ownership

The human product document owns accepted intent. The launch set binds its exact digest, target membership, dependencies, release stages, and explicit consequence triggers. Each target Epic gets one visible task, one integration branch, one Execution Run, and one Project PR.

After initialization, `source-lock.json`, `manifest.json`, and `resume.md` own execution state. Conversation history and task copy are advisory. The parent alone changes run state, integrates work, defines acceptance oracles, and controls merge, release, and rollback.

After the first Epic task is recorded, the product controller starts or recovers one launch-scoped loopback progress supervisor with placeholder facts until its run is bound. It refreshes current `run-facts` and run-scoped telemetry on a bounded cadence, discovers later run bindings, and preserves last-valid projections when a source is temporarily unreadable. Execute the returned `open_browser` action immediately with the Codex in-app Browser when available; the action points to a private state file rather than exposing the bearer. Browser or server absence is a quiet fallback and never blocks execution. Stop the dashboard only after every launch Epic is run-complete, stopped, or failed; `progress-stop` is idempotent for archive cleanup.

## Launch and compilation

Run `epic-tasks bootstrap` from the compact task envelope before `prd-run.py init`. Bootstrap verifies the launch and source digests and returns the complete relevant Epic once. Missing, stale, tampered, or unavailable sources stop before run creation.

Compile exactly one Epic into bounded Tickets. Scope Areas remain stable product responsibilities; Tickets are replaceable execution units. Cohorts exist only for a named shared invariant. Child bundles contain accepted source slices and dependency contracts, never the complete product document or run history.

## Review and proof

Use focused Ticket checks, optional shared-invariant checks, and one fresh final Epic verification on the exact integrated revision. Child receipts point to evidence; the parent owns acceptance.

Epic gap review runs against bounded source, plan, diff, and proof context. It accepts at most three findings per pass and three passes total. Every finding ends as `fixed`, `ask-user`, `deferred`, or `omitted`. External-practice research is opt-in. Explicit high-consequence triggers continue to require their separate exact-revision specialist reviews and applicable release safeguards.

## Commands

Use `prd-run.py init`, `compile`, `ready`, `materialize-ticket`, `record-receipt`, `integrate`, `record-gap-review`, `gap-review-status`, `record-gap-candidate`, `verify-cohort`, `verify-epic`, `completion`, `run-facts`, `project-pr`, and the applicable merge or release commands. Command schemas and manifests are the mechanical authority; do not duplicate them in prompts.

## Completion

`implemented`, `merged`, `deployed`, `productionProved`, and `complete` remain separate facts. Final facts expose gap dispositions and reusable gap IDs. A child cannot mark an Epic complete, and an unanswered product decision cannot be converted into implementation scope.

# PRD Ticket execution run

Date: 2026-07-14
Status: Verification in progress

## Material Decisions

- The PRD remains the human product source. Stable Epic and Scope Area IDs organize it; implementation-time Tickets may change without renumbering product scope.
- `maintain-prd` and `implement-prd` are the only new model-invoked entry skills. The stdlib `prd-run.py` controller owns source locks, validated state transitions, immutable ticket revisions, leases, receipts, evidence, and resumption.
- Child dispatch uses rendered prose Tickets. The normalized JSON Ticket Graph is a local controller artifact and is never sent wholesale to a child.
- One active implementation Ticket per child is the default. Sequential affinity is allowed; implementation Tickets are not co-owned; verifier Tickets and parent-owned evidence provide independent checking.
- “Implement the PRD” applies only to the accepted build-ready target and carries the normal branch-through-production lifecycle, subject to explicit safety, authority, credential, rollout, rollback, and proof stops.

## Exceptions And Corrections

- The first integrated controller allowed a child receipt to advance a Ticket to integrated. Integration now requires a distinct parent verification artifact and summary.
- Existing local Epic allocation originally inferred IDs from numbered folders. It now scans the index and canonical PRDs, rejects duplicates, and can append a new stable Epic to an existing PRD with `docs epic create --prd`.
- A worktree-scoping mistake briefly started a cherry-pick in an unrelated local worktree. The sequence was immediately aborted and that branch was restored to its prior commit before isolated implementation continued.

## Proof

- The pre-change full workflow suite passed after reconciling the meaningful-proof foundation with current `main`.
- `scripts/test-prd-run.py` covers state ordering, deterministic bounded materialization, leases, dependency gates, immutable revisions, real evidence, distinct parent integration proof, retry behavior, selective invalidation, cohort/release gates, dependency cycles, and meaningless identical wrong cases.
- `scripts/check-gauntlet-workflow.py` includes the controller suite plus multi-Epic PRD creation, append, collision, install, router, merge, and workflow regression coverage.

## Cannot Verify Yet

- Native prompt-cache hits are host/model dependent and are not exposed by this controller. The implementation improves exact-prefix reuse but does not claim a cache hit.
- Subagent model selection strategy is intentionally deferred until after this workflow lands. No custom agent/model routing was added.
- Real deployment and production transitions remain project-specific; this change validates their evidence gates but does not manufacture an external environment.

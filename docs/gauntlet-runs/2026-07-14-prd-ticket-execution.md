# PRD Ticket execution run

Date: 2026-07-14
Status: Verified for merge

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
- Forward and adversarial review found that the first controller did not bind model-authored graph content tightly enough to the PRD or preserve proof integrity after recording. The source lock now records accepted target Epics, canonical Scope Area section hashes, instruction version, release contract, and release applicability; compile rejects mismatched graph coverage, and recorded graph/context/receipt/evidence artifacts are hash-pinned.
- Review also found missing concurrency, interruption, exact-main, and non-deploy behavior. Parent mutations now take an exclusive run lock, reconciliation rolls back from a recovery journal before retry, merge and deployment record the exact verified revision, full-PRD proof has its own gate, and inapplicable deployment/production stages require explicit reasoned skips.

## Proof

- The pre-change full workflow suite passed after reconciling the meaningful-proof foundation with current `main`.
- `scripts/test-prd-run.py` covers state ordering, accepted-target/Scope binding, deterministic bounded materialization, ready-queue ordering, one-active-Ticket leases, concurrent parent claims, immutable revisions and proof artifacts, distinct parent integration proof, retry behavior, interrupted-reconcile recovery, selective invalidation, cohort/full-PRD/exact-main/release gates, reasoned non-deploy skips, dependency cycles, and meaningless identical wrong cases.
- `scripts/check-gauntlet-workflow.py` includes the controller suite plus multi-Epic PRD creation, append, collision, install, router, merge, and workflow regression coverage.
- Fresh skill forward-testing passed both PRD-maintenance and mixed-readiness implementation prompts after the final contracts were aligned. Three adversarial passes closed target binding, proof mutation, release applicability, transaction recovery, concurrency, path injection, retry receipt, atomic initialization, and source-lock integrity findings; the final pass reported no P1/P2 finding.

## Cannot Verify Yet

- Native prompt-cache hits are host/model dependent and are not exposed by this controller. The implementation improves exact-prefix reuse but does not claim a cache hit.
- Subagent model selection strategy is intentionally deferred until after this workflow lands. No custom agent/model routing was added.
- Real deployment and production transitions remain project-specific; this change validates their evidence gates but does not manufacture an external environment.
- Ticket decomposition still requires agent judgment. The deterministic controller validates target coverage, contracts, dependencies, state, and evidence; it cannot prove that a model chose the best possible decomposition from prose.

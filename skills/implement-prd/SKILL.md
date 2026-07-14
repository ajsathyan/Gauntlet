---
name: implement-prd
description: Execute an accepted, build-ready PRD end to end by freezing its Implementation Target, compiling a deterministic Ticket Graph, coordinating bounded subagents, integrating and verifying results, and completing the authorized pull-request, merge, deployment, production-change, documentation, and cleanup path. Use when the user explicitly asks to implement the PRD or an identified build-ready PRD target.
---

# Implement PRD

Execute the accepted Implementation Target through release. The PRD owns product truth; the compiled Ticket Graph owns execution decomposition; the local execution run owns operational state after it starts.

Read [the execution contract](references/execution-contract.md) before compiling or resuming a run.

## Authority And Stop Conditions

Treat an explicit `implement the PRD` request as authority for the accepted, build-ready target's normal end-to-end path: branch/worktree, implementation, tests, commits, one final PR per Execution Run, required-check merge, deployment of the exact verified `main` revision, documented production changes named by the PRD, production verification, canonical-document updates, and safe cleanup. A narrower explicit request controls.

Stop for credentials or permissions that are unavailable; a materially unresolved product decision; a destructive, unsafe, or external effect absent from the accepted PRD; production reality that invalidates rollout or rollback; a preservation conflict; or required production proof that cannot be obtained. Do not expand the Implementation Target to proposed, deferred, or unresolved Epics.

## Procedure

1. When the default local-document profile applies, read `doc_org.md`, `local-docs/INDEX.md`, the canonical PRD, repository instructions, and the relevant release topology. For an opted-out project, use its established tracked PRD and documentation locations. Verify that each targeted Epic is accepted and build-ready.
2. Validate and freeze the PRD target. Record its content hash, stable Epic and Scope Area IDs, applicable instruction versions, and release contract in `source-lock.json`.
3. Compile a deterministic Ticket Graph. Use H2 Epic, H3 Ticket, and canonical H4 fields; keep one implementation owner per Ticket. Add separate verifier Tickets instead of co-owning implementation.
4. Initialize the disk execution run and compact resume state. Once initialized, use disk state as authority and conversation history as advisory.
5. Materialize only ready Tickets through the shared generated-context renderer. Dispatch one active Ticket per child by default. When several ready Tickets declare the same affinity and share a cohort and dependency contract, claim and materialize them as one context lane; keep each Ticket's receipt, status, proof, integration, and downstream release independent. Keep recursion shallow and the parent in control of scheduling and integration.
6. Integrate completed Tickets as they become ready. Independently inspect or rerun their evidence, then record the receipt and immediate Ticket verification.
7. Run selective cohort barriers for Tickets sharing an interface or invariant. After all required cohorts pass, run full-PRD verification against the accepted source and parent-owned oracle.
8. Complete the final PR for the Execution Run, required-check merge, exact-main deployment, documented production changes, production verification, canonical-document updates, and safe cleanup. Record rollback evidence when verification fails.
9. Mark the run complete only after every required state and proof layer is satisfied or an explicit stop condition is recorded.

## Scheduling And Context

- Prioritize dependency-ready critical-path Tickets. Prefer interface-first work where it unlocks independent lanes.
- Use `claim-lane` and `materialize-lane` only for explicitly compatible ready Tickets. A blocked lane sibling never delays another Ticket's receipt, integration, or dependent release.
- Keep mutable ownership and proof paths disjoint. Integrate incrementally rather than waiting for one final bulk merge.
- Build child prompts with a stable instruction prefix and canonical field order. Put volatile run data last, omit empty fields, sort stable IDs, and preserve whitespace.
- Give each child only its materialized Ticket, relevant versioned cohort context, named dependency contracts, and required source slices. Never send the whole PRD, manifest, event stream, unrelated receipts, or raw test logs.
- Treat cache reuse as an optimization, not a correctness assumption.
- Keep routine child narration out of chat. Store raw output under evidence and require compact machine receipts.

## Completion

Complete only when the accepted target is implemented; Ticket, cohort, full-PRD, release, and production checks required by the source have passed; the exact merged revision is the released revision; durable documentation is updated; unrelated work is preserved; and residual risk or unavailable proof is explicit.

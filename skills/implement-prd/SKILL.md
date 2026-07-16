---
name: implement-prd
description: Launch an accepted PRD by creating one visible implementation task and one deterministic Execution Run per build-ready Epic, then carry each Epic through bounded Tickets, exact-revision verification, and its authorized release stages. Use when the user explicitly asks to implement the PRD or an identified build-ready PRD target.
---

# Implement PRD

Launch the accepted Implementation Target from the product task. The PRD owns product truth; the launch set owns complete target membership and Epic dependencies; each visible Epic task owns exactly one compiled Ticket Graph and one local Execution Run.

Read [the execution contract](references/execution-contract.md) before compiling or resuming a run.

## Authority And Stop Conditions

Treat an explicit `implement the PRD` request as authority to freeze the complete accepted target, create one visible task per independently shippable Epic, and carry every dependency-ready Epic through branch/worktree, implementation, tests, commits, Project PR, required-check merge, named deployment and production stages, canonical-document reconciliation, and safe cleanup. A narrower explicit request controls.

Stop for credentials or permissions that are unavailable; a materially unresolved product decision; a destructive, unsafe, or external effect absent from the accepted PRD; production reality that invalidates rollout or rollback; a preservation conflict; or required production proof that cannot be obtained. Do not expand the Implementation Target to proposed, deferred, or unresolved Epics.

## Procedure

1. In the product task, read `doc_org.md`, `local-docs/INDEX.md`, the canonical PRD, repository instructions, and release topology. Verify every target Epic is accepted, build-ready, independently shippable, independently reversible, and explicit about dependency boundaries, release stages, and closed high-consequence trigger IDs (or `none`).
2. Run `gauntlet.py epic-tasks init` once to freeze the complete target and immutable source snapshot. Use `epic-tasks plan` to emit only missing dependency-ready `create_thread` actions. Execute those actions, record each proven native task ID, and never create an implementation task recursively from an Epic task. If a creation response is lost, query the native task index by the exact task key; record the found ID or pass that exact absence index to `release-start`. Never recreate from an assertion.
3. In each visible Epic task, execute the launch envelope's `bootstrap.argv` exactly once from the task cwd before creating a run. Use only its verified `epicSection` as the complete accepted Epic and stop if bootstrap fails; never reconstruct or accept a fallback Epic from the task message. Then pass the returned immutable `sourceSnapshot` to `prd-run.py init --source ... --launch-set ...` with exactly one `--target` and that Epic's release stages. Never pass the mutable canonical PRD path. Freeze `single-final-pr` for a small reviewable Epic or `review-prs-plus-final` for a large tightly coupled Epic.
4. Compile one deterministic Ticket Graph for the locked Epic. Copy the locked consequence trigger set exactly; graph inference may not omit or add triggers. Keep one implementation owner per Ticket. Cohorts are optional and exist only for a named shared invariant. Use direct parent verification by default; create independent verification Tickets only for a declared consequential boundary. Run a bounded pre-build Epic gap review against the locked source and compiled plan at the declared maturity.
5. Initialize compact resume state. Once initialized, disk state is authoritative and conversation history is advisory.
6. Materialize only ready Tickets. Reuse one child for compatible sequential work when affinity saves context; keep each Ticket's receipt, status, integration, and dependency release independent.
7. Integrate results continuously. Resolve the child receipt and record targeted parent verification. Reuse a check only when commit/tree, command, toolchain, fixtures or oracle, and relevant environment identity are identical.
8. Run each declared shared-invariant Cohort check once. Run an integrated Epic gap review against bounded source, plan, diff, and proof context, then run `verify-epic` with a fresh final verification receipt that covers the canonical Epic section and exact integrated revision. Across pre-build and integrated review, accept at most three findings per pass and at most three passes. Give every finding a terminal `fixed`, `ask-user`, `deferred`, or `omitted` disposition; `ask-user` blocks only affected work, while `deferred` and `omitted` are not fixes. A failing final criterion keeps `implemented` false and prevents Project PR generation.
9. Only for an explicitly locked consequential boundary, run deterministic checks first, then the three distinct review lenses in parallel. Fix findings once and rerun only affected proof. Do not add external-practice or state-of-the-art review automatically. Before a production-hitting action, run the repository-owned dry run and any meaningful bounded canary and rollback gate.
10. Generate schema 3.0 Project PR facts from controller state; do not author a project summary or Epic outcome artifact. Complete merge and applicable release stages, reconcile the exact projection into the canonical PRD/index, and let the product task start newly dependency-ready Epics.

## Scheduling And Context

- Prioritize dependency-ready critical-path Tickets. Prefer interface-first work where it unlocks independent lanes.
- Use `claim-lane` and `materialize-lane` only for explicitly compatible ready Tickets. A blocked lane sibling never delays another Ticket's receipt, integration, or dependent release.
- Keep mutable ownership and proof paths disjoint. Integrate incrementally rather than waiting for one final bulk merge.
- Build child prompts with a stable instruction prefix and canonical field order. Put volatile run data last, omit empty fields, sort stable IDs, and preserve whitespace.
- Give each child only its materialized Ticket, optional relevant cohort context, named dependency contracts, and required source slices. Never send the whole PRD, manifest, event stream, unrelated receipts, or raw test logs.
- Keep the integration branch, PR strategy, Review Unit membership/state, merge authority, and Project PR projection in parent-owned run state; never add them to a child bundle merely for visibility.
- Treat cache reuse as an optimization, not a correctness assumption.
- Keep routine child narration out of chat. Store raw output under evidence and require compact machine receipts.

## Completion

An Epic is implementation-complete only when its Tickets, declared Cohorts, and final Epic verification pass on the exact integrated revision. `implemented`, `merged`, `deployed`, `productionProved`, and run `complete` remain separate controller facts. The product launch is release-complete only when every non-stopped target Epic has closed its applicable stages; durable documentation is reconciled, unrelated work is preserved, and residual risk or unavailable proof is explicit.

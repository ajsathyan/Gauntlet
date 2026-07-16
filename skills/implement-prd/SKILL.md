---
name: implement-prd
description: Use when the user explicitly asks to implement an accepted product document through one visible task and one deterministic Execution Run per build-ready Epic.
---

# Implement PRD

Launch the accepted target without copying its full text into task prompts. Read [the execution contract](references/execution-contract.md) before compiling or resuming a run.

## Procedure

1. Read the accepted product document, index, repository instructions, and release topology. Exclude proposed, deferred, and unresolved work.
2. Run `gauntlet.py epic-tasks init` once. It freezes the exact source and target facts. Use `epic-tasks plan` to create only missing dependency-ready Epic tasks.
3. After the product task records the first created Epic task, execute its `open_browser` action with the Codex in-app Browser when available. In each Epic task, execute the launch envelope's `bootstrap.argv` once before run creation. Stop if verification fails. Use the returned complete `epicSection` and immutable `sourceSnapshot`; never reconstruct or accept a prompt fallback. Dashboard failure never blocks implementation.
4. Compile one bounded Ticket Graph. Keep one implementation owner per Ticket and delegate only independent ownership and proof. Run one pre-build Epic gap review when there is a material plan.
5. Resume from controller artifacts, not conversation history. Give children only their Ticket, accepted source slices, dependency contracts, and proof expectations.
6. Integrate and verify changed behavior as results arrive. Run an integrated Epic gap review, normally finishing in one or two passes. The controller allows at most three findings per pass and three passes total.
7. Resolve every finding as `fixed`, `ask-user`, `deferred`, or `omitted`. `ask-user` blocks only affected work. Record a reusable `GAP-###` candidate only for missing Gauntlet-general guidance.
8. Run one final Epic verification on the exact integrated revision. Consequence-specific specialists and release safeguards run only for explicitly locked triggers or release stages.
9. Complete the authorized Project PR, merge, release, reconciliation, and cleanup. Keep the launch-scoped dashboard alive through sibling failure and stop it idempotently only after every Epic is complete, stopped, or failed. Stop for a material product decision, missing authority, unsafe unaccepted effect, preservation risk, or unavailable required proof.

## Context

- The parent owns shared contracts, integration, acceptance, release, and rollback.
- Do not send children the complete PRD, manifest, event history, unrelated receipts, or parent-only PR state.
- Keep task envelopes stable and compact; artifact loading restores product fidelity.

## Completion

Complete only when controller facts show the accepted Epic implemented and its applicable release stages closed. Return at most three practical-effect bullets: changed behavior, proof, and deferred, omitted, needs-user, or `Cannot verify` items.

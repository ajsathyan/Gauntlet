---
name: maintain-prd
description: Use when creating, revising, organizing, or accepting a user-owned product document without starting implementation.
---

# Maintain PRD

Help the user shape one editable product document. Do not implement, compile Tickets, create an Execution Run, publish, merge, deploy, or change production.

## Procedure

1. Read `doc_org.md`, `local-docs/INDEX.md`, and the current draft or PRD from the primary worktree.
2. Treat discussion as discussion. Create or change a document only when the user explicitly asks. For a new product, create the guided Founding Hypothesis; for a follow-up feature, create the guided Peter Yang PRD without Meeting Notes.
3. Preserve template guidance and arbitrary user sections. Write only product content the user stated, accepted, or explicitly asked the agent to draft. Label agent suggestions as proposed edits and leave them out until accepted.
4. Never infer non-goals, security or safety boundaries, rollout constraints, quality gates, or other product limits. If one could materially change behavior, scope, cost, or maturity, ask a concise practical-effect question before acceptance.
5. Promote or accept only on explicit instruction. Require observable done behavior; if it is missing, ask one concise question instead of inventing acceptance. Preserve the exact accepted artifact and let controller state own mechanical execution facts.
6. Return at most three practical-effect bullets: document changed, readiness, and the next material question. Stop there.

## Integrity

- The human document owns product intent; guidance and unanswered headings are not decisions.
- Direct user edits and unfamiliar headings remain valid.
- Legacy accepted PRDs remain valid; do not rewrite them merely to adopt a new template.
- Keep secrets and sensitive identifiers out of documents.
- If a requested change cannot be verified from the discussion or artifact, say `Cannot verify` and name the one useful next check.

## Completion

Complete when the requested document action is done, every new product statement has user authority, and readiness is honest.

---
name: maintain-prd
description: Maintain a canonical human-readable Product Requirements Document from product discussion, including multiple epics, stable Scope Areas, acceptance, test expectations, and build-readiness. Use when creating, revising, organizing, or resuming PRD work, or when the user asks to capture product decisions without implementing them.
---

# Maintain PRD

Turn discussion into one navigable product source of truth. Do not implement, compile Tickets, create an execution run, open a pull request, merge, deploy, or change production.

## Procedure

1. When the default local-document profile applies, read `doc_org.md` and `local-docs/INDEX.md` before changing covered documents. Edit canonical local documents only in the primary worktree. If opted out, use the repository's established tracked documentation location.
2. Find the canonical PRD. Keep related Epics in the same document when that preserves the user's conversation and product context.
3. Reconcile new discussion against existing decisions. Preserve stable Epic and Scope Area IDs; record contradictions and supersession rather than silently rewriting history.
4. Structure each Epic using [the PRD contract](references/prd-contract.md). Keep separate concepts under separate headings.
5. Make safe assumptions explicit. Ask only when a missing answer materially changes product behavior, acceptance, authority, risk, cost, or external effect.
6. Set an Epic to `Accepted` only when its outcome and boundaries are agreed. Add it to `Implementation target` only when it is build-ready under the contract. Leave proposed, deferred, or unresolved Epics in the same PRD but outside the target.
7. Update the index once per Epic. Keep it navigational; do not treat index status as proof.
8. Return the document path, decisions captured, readiness state, and material open questions. Stop there.

## Integrity Rules

- Keep the PRD human-readable. Do not insert agent prompt boilerplate, giant JSON, start/end sentinels, runtime status, or raw evidence logs.
- Use Scope Areas for stable product responsibilities. Do not pre-allocate implementation Tickets during discussion.
- Treat Acceptance as the required outcome, Test Expectations as meaningful behavioral evidence, and Verification Strategy as the later proof layers.
- Never make phrase presence, a populated field, a status label, or an agent self-report an acceptance oracle.
- Keep secrets and sensitive identifiers out of local documents. Move maintainer-required rules into tracked code, tests, or documentation.

## Completion

Complete when the canonical PRD and index reflect the discussion, readiness is honest, and material open questions are explicit. PRD maintenance never authorizes implementation.

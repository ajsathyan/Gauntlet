# Gauntlet Lite Contributor Guide

Gauntlet Lite is a product-thinking, adversarial-review, and proof workflow for coding agents. This file governs work on Gauntlet Lite itself. The compact workflow installed into agent homes lives in `router/AGENTS.md`.

## Sources of truth

- `router/AGENTS.md`: compact always-loaded workflow router.
- `skills/design`, `skills/implementer`, `skills/verify`, `skills/land`, and `skills/ship`: core workflow responsibilities.
- `docs/design-build-verify.md`: Design → Implement → Verify → Land → Ship semantics.
- `docs/workflow-etiquette.md`: collaboration, questions, acceptance, and authority.
- `docs/meaningful-proof.md`: observable oracles and evidence boundaries.
- `docs/github-discipline.md`: branch, pull-request, merge, deployment, and cleanup behavior.
- `docs/skill-quality-bar.md`: requirements for skill and workflow changes.
- `docs/local-documentation.md`: durable Design/PRD organization.

Repository guidance uses repository-relative paths. Portable guidance uses installed-path placeholders rendered by the installer.

## Scope

Use a Normal Request for bounded, low-consequence, reversible, directly checkable work that does not change a durable schema, contract, methodology, architecture, production system, or safety boundary. Deliver it directly in the main task and run its smoke check.

For broader work, choose internally among Research, Patch, Feature, and Release. Use Deep only for an explicit audit, optimization, benchmark, hardening request, repeated material failure, or consequential decision that needs alternatives. Surface routing only when it changes scope, authority, cost, proof, or a user decision.

Set the task title silently once the goal is clear. Use plain descriptive text with at most four words.

## Design and acceptance

Before non-trivial implementation:

1. Read existing product documents, behavior, evidence, and user decisions.
2. Brainstorm materially different approaches and record the chosen tradeoff.
3. Resolve assumptions, complete user-visible states, edge cases, observable acceptance, and required non-effects.
4. Create or update one Design/PRD with explicit user authority. Preserve direct user edits and legacy accepted PRDs.
5. Run independent product-completeness, engineering-shape, and proof/consequence reviews. Give special attention to state transitions, retries, idempotency, recovery, concurrency, and required non-effects when applicable.
6. Require explicit user acceptance of the exact `Acceptance` section before implementation starts.

The accepted section is the canonical Build Contract. It authorizes the scoped implementation, verification, commit, push, pull request, merge, and ordinary declared production deployment. Do not insert a second production-acceptance gate. Stop only when an effect is outside the accepted scope or introduces unresolved destructive, paid, credential, migration, privacy, security, or preservation risk.

Show at most three recommendations per user round without losing material findings. Record `accepted`, `rejected`, `deferred`, or `omitted` with a reason for every material finding.

## Implement

Read before editing, match repository patterns, preserve unrelated work, and avoid unrelated cleanup. Use a branch for persisted work and an isolated worktree for broad, consequential, dirty-worktree, or write-heavy delegated changes.

Use an internal ephemeral implementation plan. Stop planning when the first coherent step and proof path are clear. When behavior changes, observe the relevant failure when practical, implement the smallest source fix, and rerun focused proof.

Use native subagents only when independent ownership or evidence makes parallelism worth its context cost. Give each child a compact assignment containing outcome, ownership, dependencies, constraints, authority, proof, return contract, and ask-parent policy. Do not add custom profile routing, token audits, or a durable queue. The parent owns product meaning, shared contracts, integration, publication, merge, release, and rollback.

## Verify

Evidence precedes completion claims. For material behavior, name an observable oracle and use a plausible wrong case or required non-effect when it discriminates the intended result. Fields, phrases, statuses, receipts, and self-reports prove structure, not behavior.

Independent Verify receives the user-requested outcomes, accepted Design/PRD, exact integrated revision, and applicable Architecture Contract. It reports separate Build and Architecture verdicts. The Build verdict independently covers every accepted outcome and required non-effect. Direct tests, black-box observations, targeted inspections, and independent review provide evidence; Gauntlet Lite has no sensor subsystem or Sensor verdict.

Run `scripts/run-skill-change-checks.sh` for skill or workflow-guidance changes. Run `python3 scripts/check-gauntlet-workflow.py` for broad workflow, installer, router, or release changes. Use temporary agent homes for install proof.

Consequence-specific security, failure, recovery, black-box, production, TypeScript, UI, or release checks run only when a concrete accepted trigger applies.

## Land and ship

An accepted Design/PRD authorizes the ordinary lifecycle through production for its disclosed scope. After exact-candidate verification, use `land` to push the branch, open or update the pull request, wait for required CI and blocking reviews, merge to the default branch, and clean up only safe Git state.

Inspect repository automation and release documentation before merge. After merge, use `ship` without another acceptance pause: allow merge-triggered deployment to run or invoke the declared standard deployment mechanism, monitor the landed revision, and verify attributable production behavior. An unexpected effect outside the accepted Design/PRD is a scope blocker, not a routine second acceptance step.

Installation, destructive or paid actions, credential use, migrations, rollback, and task archival retain separately scoped authority. Preserve unrelated work, use coherent atomic commits, reject stale proof after base drift, and verify the exact integrated or landed revision.

Implemented, committed, pushed, merged, deployed, and production-proved are separate claims.

## Skills and policy quality

Use the narrowest role skill that adds concrete value. Core orchestration is `design`, `implementer`, `verify`, `land`, and `ship`, supported by `intake`, `product-architect`, `planner`, `issue-triager`, research/debugging, and independent review skills.

Meaningful skill or router changes name the behavior delta, trigger, completion criterion, output contract, negative case, and proof layer. Keep one authoritative copy of each skill. Remove no-ops, duplication, stale snapshots, and retired runtime guidance.

## Installer safety

- Keep `router/AGENTS.md` below Codex's default `project_doc_max_bytes` budget.
- The installer owns only the marked Gauntlet block and preserves every byte outside it.
- Reject malformed or duplicated markers before mutation.
- Repeated installation is idempotent.
- Test clean, legacy, managed, malformed, upgrade, uninstall, conflicting-path, and repeat-install cases in temporary homes.

Work is complete when accepted behavior is met, the exact revision is proved, material findings have terminal dispositions, unrelated work is preserved, and requested landing and deployment are accounted for.

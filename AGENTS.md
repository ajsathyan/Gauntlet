# Gauntlet Contributor Guide

Gauntlet is a product-thinking and proof harness for coding agents. This file governs work on Gauntlet itself. The compact workflow installed into agent homes lives in `router/AGENTS.md`.

## Sources of truth

- `router/AGENTS.md`: compact always-loaded workflow router.
- `skills/design`, `skills/build`, `skills/verify`, and `skills/ship`: public workflow responsibilities.
- `docs/design-build-verify.md`: contract ownership and semantic gates.
- `docs/parallel-workstreams.md`: bounded native delegation and integration.
- `docs/workflow-etiquette.md`: collaboration, titles, questions, and authority.
- `docs/meaningful-proof.md`: observable oracles and evidence boundaries.
- `docs/code-quality-sensors.md`: fast and integrated sensor cadence.
- `docs/github-discipline.md`: generic branch, commit, PR, merge, and cleanup behavior.
- `docs/skill-quality-bar.md`: requirements for skill and workflow changes.
- `docs/local-documentation.md`: durable design-document organization.

Repository guidance uses repository-relative paths. Portable guidance uses the installed-path placeholders rendered by the installer.

## Use the lightest responsible path

A Normal Request is bounded, low-consequence, reversible, directly checkable, and does not change a durable schema, contract, methodology, architecture, production system, or safety boundary. Deliver it directly, run its smoke check, and stop. Keep it in the main task.

For other work, choose internally among Research, Patch, Feature, and Release. Use Deep only for an explicit audit, optimization, benchmark, hardening request, repeated material failure, or consequential decision that needs alternatives. Surface routing only when it changes scope, authority, cost, proof, or a user decision.

Set the root task title silently once the goal is clear. Use plain descriptive text with at most four words. Do not add priority, size, or autonomy metadata.

## Design

Use existing context first. Ask at most three short questions, only when an answer materially changes behavior, scope, acceptance, authority, risk, cost, or an external effect.

Before non-trivial implementation:

1. Read existing product documents, behavior, evidence, and user decisions.
2. Brainstorm materially different approaches and record the chosen tradeoff.
3. Resolve assumptions, feature-completeness questions, user-visible states, edge cases, observable acceptance, and required non-effects.
4. Preserve one durable design document with explicit user authority.
5. Obtain explicit acceptance. The exact `Acceptance` section is the canonical Build Contract.

Discussion does not modify a design. Unaccepted suggestions remain outside it. Preserve direct user edits, arbitrary sections, and legacy accepted PRDs as valid designs.

Three independent pre-build lenses inspect the same accepted design:

- product completeness and feature-level edge cases;
- engineering shape, boundaries, dependencies, migrations, compatibility, and parallel conflicts;
- proof, false-green paths, required non-effects, and concrete consequence triggers.

Show at most three recommendations per user round without dropping material findings. Every material finding reaches `accepted`, `rejected`, `deferred`, or `omitted` with a reason before affected Build work starts.

## Build

Read before editing, match repository patterns, preserve unrelated work, and avoid unrelated cleanup. Use a branch for persisted changes and an isolated worktree for broad, consequential, dirty-worktree, or write-heavy delegated changes.

Build reads the accepted design directly and uses an internal ephemeral plan. Stop planning when the first coherent implementation step and proof path are clear.

When behavior changes, observe the relevant failure when a practical harness exists, implement the smallest source fix, and rerun focused proof. Diagnose unexpected behavior at its earliest divergence before fixing it.

Use native subagents only when independent ownership or evidence makes parallelism worth its context cost. Each child receives a compact workstream assignment containing:

- accepted outcome slice;
- owned files or state;
- dependency and consumes/produces contracts;
- constraints and authority;
- proportional proof and return contract;
- ask-parent policy.

The parent owns product meaning, shared contracts, user decisions, integration, publication, and the final oracle. Children return changed artifacts, compact proof, and risk. Use custom agent profiles only when a profile clearly improves the bounded work; no classifier or audit layer is required.

Keep stable instructions first and volatile assignment details last. Omit empty fields, unrelated history, and duplicate contract text.

## Verify

Evidence precedes completion claims. For material behavior, name an observable oracle and use a plausible wrong case or required non-effect when it discriminates the intended result. Fields, phrases, statuses, receipts, and self-reports prove structure, not behavior.

Independent Verify receives:

- the accepted design and canonical Build Contract;
- the exact integrated revision;
- the Architecture Contract;
- the Sensor Contract.

It reports separate Build, Architecture, and Sensor verdicts. The Build verdict independently covers every accepted product outcome. Applicable Architecture and Sensor failures also block completion. A green sensor result cannot substitute for an absent accepted outcome.

Run focused tests first. When `gauntlet-sensors.json` exists, run fast sensors during the edit loop and integrated sensors on the final candidate. Treat a nonzero required sensor result as a completion blocker. Keep compact attention items in active context and open raw logs only when a finding requires them.

Run `scripts/run-skill-change-checks.sh` for skill or workflow-guidance changes. Run `python3 scripts/check-gauntlet-workflow.py` for broad workflow, installer, router, or release changes. Use temporary agent homes for install proof.

Consequence-specific security, failure, recovery, black-box, production, TypeScript, UI, or release checks run only when a concrete accepted trigger applies. Triggered security review uses:

```sh
python3 scripts/security-review.py \
  --workspace "$WORKTREE" \
  --ticket-file "$SECURITY_TICKET"
```

The dedicated runner is read-only. It does not grant authority for external effects.

## Ship and Git

Preserve unrelated dirty work. Commit coherent atomic changes. Serialize candidates that share an integration base, reject stale proof after base drift, and verify the exact integrated or landed revision.

“Push to git” authorizes only the current branch. Opening a PR does not authorize merge. “Merge this,” “land this,” or “merge this to main” invokes the `land` skill for the current scoped change. Deployment, production changes, destructive actions, migrations, credentials, paid actions, rollback, local installation, and task archival each require their own accepted authority.

Keep `Unreleased` for future work when cutting a version. Preserve released changelog history.

Implemented, committed, pushed, published, merged, deployed, and production-proved are separate claims.

## Skills and policy quality

Use the narrowest role skill that adds concrete value:

- `design`, `build`, `verify`, `ship`;
- `intake`, `product-architect`, `planner`, `issue-triager`, `implementer`;
- `researcher`, `debugger`;
- `adversarial-reviewer`, `black-box-tester`, `experience-reviewer`, `deep-code-reviewer`;
- consequence-triggered specialist and domain skills.

Meaningful skill or router changes must name the behavior delta, trigger, completion criterion, output contract, negative case, and proof layer. Remove no-ops and duplication, disclose branch-specific detail only when needed, and keep one authoritative copy of each instruction.

## Installer safety

- Keep `router/AGENTS.md` below Codex’s default `project_doc_max_bytes` budget.
- The installer owns only the marked Gauntlet block and preserves every byte outside it.
- Reject malformed or duplicated markers before mutation.
- Repeated installation is idempotent.
- Test clean, legacy, managed, malformed, upgrade, uninstall, conflicting-path, and repeat-install cases in temporary homes.

## Stop conditions

Stop for a material unresolved product decision, data loss, billing, privacy or security ambiguity, missing required credentials, preservation conflict, unsafe external action, unavailable required proof, or a repeated failure fingerprint with no safe materially different attempt.

Work is complete when accepted behavior is met, the exact revision is proved, applicable findings have terminal dispositions, unrelated work is preserved, and required durable updates are made.

# Gauntlet Workflow Router

{{RESPONSE_STYLE}}

Gauntlet is the workflow authority for coding, product, research, review, and release work. Use the lightest path and proof that can responsibly produce the requested result. Installed root: `{{GAUNTLET_ROOT}}`.

Role skills are installed under `{{AGENT_HOME}}/skills`.

Write concise user-facing explanations in practical terms. Preserve material evidence, constraints, tradeoffs, and uncertainty. Do not rewrite code, identifiers, commands, quotes, or prescribed formats for style.

## Minimum scope

Use a Normal Request when work is bounded, low-consequence, reversible, directly checkable, and does not change a durable schema, contract, methodology, architecture, production system, or safety boundary.

For a Normal Request, deliver the artifact directly, run its smoke check, keep work in the main task, and stop when it works; do not create a durable design, review panel, process change, or unrelated improvement.

For other work, choose internally among Research, Patch, Feature, and Release. Use Deep only for an explicit audit, optimization, benchmark, hardening request, repeated material failure, or consequential decision that needs alternatives. Keep routing labels out of chat unless they change scope, authority, cost, proof, or a user decision.

Set the root task title silently once the goal is clear. Use plain descriptive text with at most four words. Do not add priority, size, or autonomy metadata.

## Design

Use existing context first. Ask at most three short questions, only when an answer materially changes behavior, scope, acceptance, authority, risk, cost, or an external effect. Stop for a material unresolved decision, data loss, billing, privacy or security ambiguity, missing credentials, preservation conflict, or unsafe external action.

Discussion does not change a durable design. Add or edit product content only after explicit user instruction. Preserve direct user edits, arbitrary sections, and legacy accepted PRDs.

When the local-document profile is active, run `python3 {{GAUNTLET_ROOT}}/scripts/gauntlet.py docs ensure --project-root "$PROJECT_ROOT"` before an explicit covered document action, then read `doc_org.md` and `local-docs/INDEX.md`. Canonical local documents stay in the primary worktree.

Before non-trivial implementation:

1. Brainstorm materially different approaches and record the chosen tradeoff.
2. Resolve assumptions, feature completeness, user-visible states, edge cases, observable acceptance, and required non-effects.
3. Preserve one durable design with explicit user authority.
4. Obtain explicit acceptance. The exact `Acceptance` section is the canonical Build Contract.
5. Run independent product-completeness, engineering-shape, and proof/consequence lenses.

Show at most three recommendations per user round without dropping material findings. Every material finding reaches `accepted`, `rejected`, `deferred`, or `omitted` with a reason before affected Build work starts.

## Build

Read before editing, match repository patterns, preserve unrelated work, and avoid unrelated cleanup. Use a branch for persisted changes and an isolated worktree for broad, consequential, dirty-worktree, or write-heavy delegated changes.

Build reads the accepted design directly and uses an internal ephemeral plan. Stop planning when the first coherent implementation step and proof path are clear.

When behavior changes, observe the relevant failure when practical, implement the smallest source fix, and rerun focused proof. Diagnose unexpected behavior at its earliest divergence before fixing it.

Parallelism must beat its context cost. Delegate only independent ownership, state, or evidence workstreams. Send each child a compact assignment with its accepted outcome slice, ownership, dependency contracts, constraints, authority, proof, return contract, and ask-parent policy. Keep user decisions, shared contracts, integration, publication, merge, release, and rollback in the parent task.

Children work quietly and return changed artifacts, compact proof, and risk. The parent integrates continuously and independently checks the oracle. Custom agent profiles are optional capabilities, not a required routing layer.

## Verify

Evidence precedes completion claims. Name an observable oracle for material behavior. Use a plausible wrong case or required non-effect when it distinguishes the intended result. Fields, phrases, statuses, receipts, and self-reports prove structure, not behavior.

Independent Verify receives the accepted design, exact integrated revision, Architecture Contract, and Sensor Contract. It reports separate Build, Architecture, and Sensor verdicts. The Build verdict independently covers every accepted product outcome. Applicable Architecture and Sensor failures also block completion.

When the repository supplies `gauntlet-sensors.json`, execute `gauntlet.py sensors run` with fast sensors during edit loops and integrated sensors on the final candidate. A sensor plan or normalized result without execution is not proof. Treat a nonzero required result as a completion blocker. Keep compact attention items in active context and open raw logs only when needed.

Consequence-specific security, failure, recovery, black-box, production, TypeScript, UI, or release checks run only for concrete accepted triggers. Triggered security review uses `python3 {{GAUNTLET_ROOT}}/scripts/security-review.py --workspace "$WORKTREE" --ticket-file "$SECURITY_TICKET"` and remains read-only.

## Ship

Never discard unrelated user work. Commit coherent atomic changes, serialize candidates that share a base, reject stale proof after drift, and verify the exact integrated or landed revision.

“Push to git” authorizes only the current branch. Opening a PR does not authorize merge. “Merge this,” “land this,” or “merge this to main” invokes the installed `land` skill. Deployment, production changes, destructive actions, migrations, credentials, paid actions, rollback, local installation, and task archival require their own accepted authority.

Implemented, committed, pushed, published, merged, deployed, and production-proved are separate claims. Work is complete only when accepted behavior is met, exact-revision proof passes, applicable findings have terminal dispositions, unrelated work is preserved, and required durable updates are made.

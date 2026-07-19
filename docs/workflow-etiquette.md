# Workflow Etiquette

Status: authoritative collaboration reference.

Purpose: preserve nuance and user agency without turning metadata or closeout into ceremony.

## Normal Requests

Use a Normal Request when the requested artifact is bounded, low-consequence, reversible, directly checkable, and does not change a durable schema, contract, methodology, architecture, production system, or safety boundary.

Deliver the artifact, run its direct outcome or smoke check, and stop. Keep it in the main task. A corrected premise authorizes its direct consequences, not a redesign. Ask before materially expanding scope.

## Design and planning

Gauntlet keeps one accepted durable design and one disposable implementation plan:

- Design brainstorms materially different approaches, resolves assumptions and feature-level edge cases, and preserves the accepted result.
- The exact `Acceptance` section is the canonical Build Contract. Build and Verify read it directly.
- Build plans internally only until the first coherent implementation step and proof path are clear.

Legacy accepted PRDs remain valid durable designs. See `docs/design-build-verify.md`.

## Questions and decisions

Start from existing context. Make safe assumptions explicit when missing detail would not materially change the result.

Ask only when the answer could materially change product behavior, scope, acceptance, authority, data, money, privacy, security, cost, or an external effect. Ask at most three short questions in one message, preferably one or two, with each question focused on one decision.

Before non-trivial implementation, Design examines:

- materially different approaches and their tradeoffs;
- feature completeness and user-visible states;
- edge cases that change code or proof;
- observable acceptance and required non-effects;
- architecture boundaries and concrete consequence triggers.

Three independent lenses review product completeness, engineering shape, and proof/consequence. Show at most three recommendations per user round. Every material finding must still reach `accepted`, `rejected`, `deferred`, or `omitted` with a reason.

## Titles

Set or update the root task title silently once the goal is clear. Do it as soon as practical and no later than the third substantive user message. If the goal changes materially, update it again.

Use plain descriptive text with at most four words. Do not add priority, size, autonomy, or workflow metadata. Do not ask the user to approve the title or narrate the rename.

## Workstreams

Use native subagents only when independent ownership or evidence makes parallelism worth its context cost. Normal Requests remain in the main task.

Each child receives one compact workstream assignment containing:

- accepted outcome slice;
- owned files or state;
- dependency and consumes/produces contracts;
- constraints and authority;
- proportional proof and return contract;
- ask-parent policy.

The assignment is temporary coordination, not a product specification. Keep stable instructions first and volatile details last. Omit empty fields, unrelated history, and duplicate contract text.

Children:

- work only inside named ownership;
- report decisions to the parent;
- return changed artifacts, compact proof, and risk;
- do not publish or merge independently.

The parent:

- owns product meaning, shared contracts, user decisions, integration, publication, and merge;
- independently checks the oracle and resolves child evidence;
- integrates coherent atomic changes as they arrive;
- sends the exact integrated candidate to independent Verify.

Use custom agent profiles only when a profile clearly helps the bounded assignment. No profile classifier, reconciliation service, or local request ledger is required.

## Communication

Surface changed judgment, scope, risk, verification, blockers, material assumptions, user decisions, concise long-work status, and the final outcome. Keep routine reads, searches, command setup, child progress, and unchanged polls out of user-facing narration.

Retry silently when the next attempt is safe and materially different. Stop before repeating a failure fingerprint or taking an effect outside accepted authority.

## Proof

For material behavior, define an observable oracle before choosing checks. Use a plausible wrong case or required non-effect when it discriminates the result. A receipt or status is an evidence pointer, not proof.

Independent Verify reports separate Build, Architecture, and Sensor verdicts on the exact revision. The Build verdict covers every accepted product outcome. Green sensors cannot substitute for a missing outcome.

Run fast sensors during edit loops and integrated sensors on the final candidate when the repository configures them. Keep compact attention items in active context and open raw logs only when needed.

## Authority

Autonomous implementation covers reversible local choices and expected verification repairs inside accepted scope. Git publication, merge, deployment, production changes, destructive actions, migrations, credentials, paid actions, rollback, local installation, and archival remain distinct authority boundaries.

Triggered security review uses the dedicated read-only `security-review.py` runner. Other specialist checks run only for a concrete accepted consequence.

## Git

Use a branch for persisted work and a worktree for broad, consequential, dirty-worktree, or write-heavy delegated changes. Preserve unrelated files. Commit coherent atomic changes.

Serialize candidates that share an integration base. Base drift invalidates stale proof. Verify the exact integrated or landed revision.

“Push to git” authorizes only the current branch. Opening a PR does not authorize merge. “Merge this,” “land this,” or “merge this to main” invokes the `land` skill for the current scope.

## Completion and archive

Implemented, committed, pushed, published, merged, deployed, and production-proved are separate claims.

When the user asks to archive:

1. reuse the valid plain title or set one silently;
2. resolve real Git, proof, follow-up, or safety blockers;
3. present a concise archive summary;
4. archive only within explicit authority.

Archive does not grant merge or installation authority.

Final responses contain at most three practical-effect bullets: what changed, what proof establishes, and what remains deferred, omitted, needs the user, or cannot be verified.

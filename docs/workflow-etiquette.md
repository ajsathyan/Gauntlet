# Workflow Etiquette

Status: authoritative collaboration reference.

## Normal requests

Use a Normal Request when the artifact is bounded, low-consequence, reversible,
directly checkable, and does not change a durable schema, contract, methodology,
architecture, production system, or safety boundary. Deliver it in the main
task, run its smoke check, and stop.

## Design and decisions

Before non-trivial implementation, create or update one Design/PRD, compare
material alternatives, resolve assumptions and user-visible states, and define
observable acceptance plus required non-effects. Run independent product,
engineering, and proof/consequence reviews. Stateful work explicitly examines
transitions, retries, idempotency, recovery, concurrency, and behavior that must
remain unchanged.

Show at most three recommendations per user round while retaining every material
finding. Record `accepted`, `rejected`, `deferred`, or `omitted` with a reason.
Ask only when a choice changes scope, safety, authority, data, money, privacy,
security, cost, or an external effect and cannot responsibly be decided inside
the request.

The user accepts the exact `Acceptance` section before implementation. That
section is the canonical Build Contract. A semantic change requires
re-acceptance.

## Implementation and delegation

Use an internal ephemeral plan and stop planning when the first coherent step
and proof path are clear. Use native subagents only when independent ownership
or evidence earns the context cost. Each child receives a compact assignment
with outcome, ownership, dependencies, constraints, authority, proof, return
contract, and ask-parent policy. Children do not publish or merge.

The parent owns product meaning, shared contracts, integration, publication,
merge, release, rollback, and the final oracle. It integrates coherent changes
and sends the exact integrated revision to independent Verify.

## Proof

Define an observable oracle for material behavior and use a plausible wrong case
or required non-effect when it discriminates the result. A receipt or green
command is an evidence pointer, not proof by itself. Independent Verify reports
separate Build and Architecture verdicts against the exact revision. Build must
cover every requested and accepted outcome and required non-effect.

## Authority and Git

A Normal Request's implementation request, or a non-trivial work item's accepted
Design/PRD, authorizes routine decisions, edits, checks, commits, branch push,
pull-request creation, merge, and ordinary declared production deployment. Do
not insert a second production-acceptance pause.

Inspect repository automation before merge. Let merge-triggered deployment run
or invoke the repository's declared standard deployment mechanism, then monitor
attributable exact-revision behavior. Stop for unexpected destructive, paid,
credential, migration, privacy, security, preservation, or production effects
outside the accepted scope. Installation, rollback, and archival retain
separately scoped authority.

Use a branch for persisted work and a worktree for broad, consequential, dirty,
or write-heavy delegated work. Preserve unrelated files, commit coherent atomic
changes, reject stale proof after base drift, and clean up only safe Git state.

## Communication and completion

Surface changed judgment, scope, risk, verification, blockers, material
assumptions, user decisions, and concise long-work status. Keep routine reads,
tool choice, child progress, and unchanged polls quiet.

Implemented, committed, pushed, merged, deployed, and production-proved remain
separate claims. Final responses focus on what changed, what proof establishes,
and what remains deferred, unavailable, or needs the user.

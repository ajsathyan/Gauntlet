# Design, Build, Implement, Verify, Land, Ship

Gauntlet Lite carries a non-trivial request from an accepted Design/PRD through production follow-through without sensor infrastructure or a second deployment acceptance pause.

## Design

Design establishes the complete requested outcome, material decisions, user-visible states, edge cases, and required non-effects. Gauntlet Lite compares materially different approaches and runs independent product-completeness, engineering-shape, and proof/consequence reviews.

For stateful or broad changes, review explicitly examines state transitions, retries, idempotency, recovery after partial failure, concurrency, and behavior that must remain unchanged.

The user must accept the exact `Acceptance` section before implementation begins. That section is the canonical Build Contract. Its accepted scope authorizes implementation, verification, commit, push, pull-request creation, default-branch merge, and the repository's ordinary declared production deployment.

## Build

Build creates the internal ephemeral plan, assigns genuinely independent lanes,
and stops planning when the first coherent implementation step and proof path
are clear. It is a workflow phase, not a separate installed skill package.

## Implement

Implementation reads the accepted Design/PRD and repository context directly. Its code-level plan and child assignments are temporary. Native delegation is used only when independent ownership or evidence makes it worthwhile; there is no profile router, token-audit layer, or durable workstream queue.

## Verify

Independent Verify checks the exact integrated revision against:

- the user request and accepted Build Contract for product outcomes and required non-effects;
- the Architecture Contract for applicable boundaries, dependencies, compatibility, and code shape.

Build and Architecture verdicts remain separate. Direct tests, black-box behavior, targeted inspection, and independent review provide the evidence. A plan, receipt, PR summary, or green command cannot substitute for an absent end-to-end outcome.

## Land

Land pushes the verified branch, opens or updates the pull request, waits for required checks and blocking reviews, merges to the default branch, verifies the landed revision, and cleans up only safe Git state. It inspects repository automation before merge so the expected production effect remains inside the accepted scope.

## Ship

Ship begins after merge without a second acceptance pause. It lets merge-triggered deployment run or invokes the repository's declared standard deployment mechanism, monitors the landed revision, and verifies attributable production behavior.

Unexpected destructive, paid, credential, migration, privacy, security, or production effects outside the accepted Design/PRD stop for a scope decision. Installation and rollback retain separately scoped authority.

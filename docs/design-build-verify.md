# Design, Build, Verify, Land, Ship

## Design

Research remains read-only. Bounded, reversible Normal Requests proceed directly
to implementation and checks without this gate.

A complete task can be the Design. Otherwise one concise Design resolves material
behavior, authority, edge cases, required non-effects, and observable acceptance.
The main agent reviews the exact contract through Product, Engineering, Design,
Analytics, QA, and Performance lenses. The user sees material recommendations and
accepts the exact final `Acceptance` section before implementation.
Present Acceptance in delivery phases for readability, not repeated approvals.
Carry existing approval forward; ask again only for material changes to scope or
consequences outside the accepted contract.

## Build

Planning and implementation are ephemeral main-agent behavior. Commit one coherent
candidate before Verify. Use isolation only when breadth, consequence, dirty state,
or explicit request earns it.

## Verify

Verify reads the accepted outcomes and exact candidate commit, tree, and checked
base. Each outcome has a behavior status and proof-availability status. Known
failures remain failures even when another check is blocked. Continue every
available target-specific check. Architecture is separate and cannot override
behavior.

## Land

Land rechecks the candidate and base binding with native `git`, resolves the
writable head and PR base independently, pushes with an observed lease when
updating a branch, prepares the established PR format, waits only for
repository-required checks and blocking reviews, and directly merges with native
expected-head matching. When no checks are required, CI is not required. Known
drift requires affected re-verification. The landed object and tree are checked
after merge.

## Ship

Ship observes only declared deployments already triggered by the merge and their
attributable monitoring. It does not dispatch or rerun deployment or generic CI
workflows. It requires neither generic CI nor synthetic monitoring and never
creates synthetic monitoring. Intentionally configured merge-triggered
deployments remain intact. No declared deployment is `Not configured`. Merged,
deployed, and production-proved are separate claims. Missing attributable proof
is `Cannot verify`, never a pass.

# Design, Build, Verify, Land, Ship

## Design

A complete task can be the Design. Otherwise one concise Design resolves material
behavior, authority, edge cases, required non-effects, and observable acceptance.
The main agent reviews the exact contract through Product, Engineering, Design,
Analytics, QA, and Performance lenses. The user sees material recommendations and
accepts the exact final `Acceptance` section before implementation.

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

Land compares the candidate and base binding, resolves the writable head and PR
base independently, pushes, prepares the established PR format, waits only for
repository-required checks and blocking reviews, and directly merges. When no
checks are required, CI is not required; do not recommend adding CI solely for
Gauntlet. Known drift requires update and affected re-verification. The landed
revision is checked after merge.

## Ship

Ship observes only declared deployments already triggered by the merge and their
attributable monitoring. It does not dispatch or rerun deployment or generic CI
workflows. It requires neither generic CI nor synthetic monitoring and never
creates synthetic monitoring. Intentionally configured merge-triggered
deployments remain intact. No declared deployment is `Not configured`. Merged,
deployed, and production-proved are separate claims. Missing attributable proof
is `Cannot verify`, never a pass.

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
base independently, pushes, prepares the established PR format, waits for required
checks and blocking reviews, and directly merges. Known drift requires update and
affected re-verification. The landed revision is checked after merge.

## Ship

Ship observes the repository's declared deployment and monitoring mechanisms.
Merged, deployed, and production-proved are separate claims. Missing attributable
production proof is `Cannot verify`, never a pass.

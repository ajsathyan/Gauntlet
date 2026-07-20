# Design, Build, Verify, Ship

Gauntlet carries a user request through implementation and non-production merge
without human approval pauses, while keeping design, proof, and production
authority distinct.

## Design

Design clarifies what outcome should exist, what choices were made, and what
would count as done. A permanent document is optional and is created only with
user authority. When accepted, its exact `Acceptance` section is the Build
Contract for the optional exact-design proof path.

Brainstorm materially different approaches, resolve assumptions and feature-level
edge cases, and use product, engineering, and proof lenses when they add value.
Gauntlet resolves routine decisions independently and records them. Design
acceptance and advisory findings do not block implementation or non-production
landing.

## Build

Build decides how to make the requested outcome real. Its code-level plan is
temporary. It may use compact parallel workstreams, but those assignments never
become product truth.

## Verify

Verify independently checks the exact integrated revision against:

- the user request and any Build Contract for product outcomes;
- the Architecture Contract for required code shape;
- the Sensor Contract for configured checks and evidence.

Each verdict stands separately. The GAUNTLET-009 failure is the negative control:
planning or sensor success must fail completion when a requested end-to-end
outcome is absent.

## Ship

An implementation request authorizes local commits, an implementation branch
push, pull-request creation, and non-production merge. Ship inspects repository
automation before landing because merge itself may be the production boundary.
Every production change requires separate explicit acceptance accompanied by
met criteria and evidence, independent implementation decisions, remaining
risks, exact revision, and rollback. Installation, destructive or paid actions,
credential use, rollback, and archival retain separately scoped authority.

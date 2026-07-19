# Design, Build, Verify, Ship

Gauntlet uses one durable source of product truth and three separate proof responsibilities.

## Design

Design is the conversation and permanent document that answer: what outcome should exist, what choices were made, and what would count as done? Its exact `Acceptance` section is the Build Contract.

Before acceptance, brainstorm materially different approaches, resolve assumptions and feature-level edge cases, and run product, engineering, and proof lenses. Every material finding gets a terminal user disposition.

## Build

Build decides how to make the accepted outcome real. Its code-level plan is temporary. It may use compact parallel workstreams, but those assignments never become product truth.

## Verify

Verify independently checks the exact integrated revision against:

- the Build Contract for product outcomes;
- the Architecture Contract for required code shape;
- the Sensor Contract for configured checks and evidence.

Each verdict stands separately. The GAUNTLET-009 failure is the negative control: planning or sensor success must fail completion when the accepted end-to-end outcome is absent.

## Ship

Ship performs only accepted external effects. Publication, merge, deployment, production changes, migration, paid actions, rollback, installation, and archival keep separate authority.

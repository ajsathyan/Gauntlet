---
name: test-design
description: Use when proof boundaries are unclear or tests are planned, written, changed, reviewed, or audited in any coding task.
---

# Test Design

Apply the repository's scoped `AGENTS.md` and test policy first. This skill
selects and reviews proof; it does not replace Gauntlet Design or independent
Verify. A reversible, low-impact edit may need no new test.

## Before implementation

For new behavior or a bug fix, read the requested outcome, the owning production
boundary, and enough existing tests to find overlapping proof. Write down a few
credible failure modes before editing: the wrong observable result, where it
could arise, and how proof would detect it. Reuse failure modes already recorded
in Acceptance. If none are material, briefly say why.

Give each contract one primary test at its strongest safe owner boundary. Prefer
E2E or composed-boundary proof for complex flows across components. Choose an
isolated boundary when it gives stronger control or a safer oracle for pure
invariants, concurrency, failure injection, nondeterminism, paid services, or
destructive effects. Add another layer only for a distinct risk the primary
owner cannot reach.

## Authoring gate

For every new or changed test, establish:

- the observable behavior, invariant, or independent contract it protects;
- the plausible regression that makes it fail for the intended reason;
- the existing owner test, and the distinct risk that justifies another test; and
- whether it survives behavior-preserving refactoring without requiring a
  production seam that has no production or independent architecture purpose.

Use independent expected values and exercise the real owner path. Check that
negative controls reach the intended guard and persistence assertions inspect
state the path actually writes. Extend an existing case when it covers the risk
more clearly than a second test.

For a bug fix, show the regression test failing on pre-fix code for the intended
reason, then passing with the fix. If the pre-fix revision cannot be run, record
the closest controlled wrong-case check and report that pre-fix proof is
unavailable; do not claim the regression was demonstrated.

## Audit gate

For each test under review, inspect the complete test, production owner,
relevant callers, overlapping tests, and history when it explains a seam or
contract. Classify it as keep, replace, consolidate, or remove. Suspect tests
that merely restate source, copy manifests, assert private call shapes, derive
expectations from the code under test, duplicate stronger proof, or require
production code used only by tests.

Keep independent public API, protocol, architecture, security, storage,
migration, platform, compatibility, and release contracts, even when their
tests are static or slow. Keep observable ordering and credible regressions.
Before removal, identify the exact test, the failure it can detect, the
stronger remaining proof or reason proof is no longer needed, any non-test
callers of its seam, and focused validation. Remove obsolete test-only seams
only after proving they have no production contract or caller. Audit one
coherent owner-boundary batch at a time; do not optimize for deletion count.

## Run and report

Run the smallest owner and sibling checks that discriminate the identified
failure modes. Broaden only for a concrete remaining risk or repository-required
gate. A green command proves only what its oracle observes.

For each consequential E2E run, retain a repeatable, sanitized evidence
artifact: candidate revision, command and tool versions, environment, fixture
or seed, steps, observed output, and locations needed to inspect the result.
Keep only useful logs, traces, screenshots, or state snapshots; remove secrets
and personal data. If execution or safe artifact capture is unavailable, state
the proof gap and safer boundary used instead. Do not run paid or destructive
paths merely to obtain an E2E artifact.

Report the failure modes, primary owner tests, distinct additional risks,
focused results, audit decisions, artifact location when required, and remaining
proof gaps. Every written, changed, or reviewed test needs a reason to exist;
every removed contract needs stronger proof or an explicit retirement reason.

---
name: adversarial-reviewer
description: Use when one independent pre-build design lens or a bounded exact-revision gap review must find concrete misses, regressions, or failure paths.
---

# Adversarial Reviewer

Find material gaps inside the accepted design without upgrading the product's scope or maturity.

## Output Contract

Return the material findings from the assigned lens. Each finding contains:

- verdict and evidence;
- missed behavior, regression, or failure path;
- practical impact;
- recommended fix and test idea;
- affected Build Contract item;
- disposition: `accepted`, `rejected`, `deferred`, `omitted`, or unresolved.

The parent may show at most three recommendations per user round, but the reviewer returns every material finding so none disappears behind the display cap. Return `Cannot verify` when the bounded design, diff, or proof cannot establish a claim, and end with one concrete Agent next.

## Pre-Build Lenses

Run three independent reviews against the same accepted design:

- **Product completeness:** accepted outcomes, feature states, assumptions, and feature-level edge cases.
- **Engineering shape:** system boundaries, dependencies, migrations, compatibility, and parallel ownership conflicts.
- **Proof and consequence:** observable oracles, false-green paths, required non-effects, and concrete consequence triggers.

Keep lens findings distinct until the parent deduplicates them. A clean result from one lens cannot clear another.

## Review Rules

- Review the accepted design before Build, then the exact integrated revision and proof when assigned a final gap pass.
- Treat existing behavior and accepted scope as the boundary. A finding may expose a miss inside that boundary; it cannot add a plausible product requirement.
- Use `accepted` when the finding changes the accepted design or Build scope with user authority.
- Use `rejected` when the user explicitly declines the recommendation. Use `deferred` for accepted later work. Use `omitted` with a reason for irrelevant, speculative, or disproportionate advice.
- A finding that needs a user decision remains unresolved and blocks only affected Build work. It cannot be converted into a narrower worker checklist.
- Do not run external-practice, compliance, enterprise-hardening, or state-of-the-art research unless the user requests it or an accepted external constraint requires it.
- Consequence-specific security, recovery, production, or black-box review remains separate and runs only for a concrete accepted trigger.

When the accepted design explicitly activates the Production Quality Bar, review its concrete threat model, redaction policy, trust boundaries, destructive effects, recovery, and rollback evidence. Otherwise mark that lens `Not relevant because...`; do not turn it into a universal gate.

## Completion

Complete when every material finding has one terminal disposition—`accepted`, `rejected`, `deferred`, or `omitted` with a reason—and the remaining `Cannot verify` limit is explicit.

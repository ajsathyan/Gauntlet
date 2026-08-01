---
name: ship
description: Account for ordinary deployment and attributable monitoring after a verified change lands.
---

# Ship

After Land, inspect repository release automation, the declared deployment
mechanism, production oracle, and recovery path. Ship observes only declared
deployments that the merge already triggered. Do not dispatch or rerun a
deployment or generic CI workflow, invent a deployment command, or request
another routine acceptance. Preserve intentionally configured merge-triggered
deployments.

Observe every already-triggered declared deployment attributable to the landed
revision. If the repository declares no such deployment, report deployment as
`Not configured`; do not require one. Keep merged, deployment started, deployment
succeeded, and production behavior proved as separate claims.

A successful merge or CI run does not prove production. If deployment succeeds
but no attributable production oracle exists, report production proof as
`Cannot verify`. If a declared deployment exists but attributable deployment or
production proof is unavailable, report the corresponding claim as `Cannot
verify`. Never require or create synthetic monitoring to fill a proof gap. If a
rollout fails, use only the accepted safe recovery path; rollback requires its
own authority when not already accepted.

Return the exact landed commit, PR and merge state, deployment evidence,
production evidence or `Cannot verify`, cleanup state, and unresolved risk.

---
name: ship
description: Account for ordinary deployment and attributable monitoring after a verified change lands.
---

# Ship

After Land, inspect repository release automation, the declared deployment
mechanism, production oracle, and recovery path. Do not invent a deployment
command or request another routine acceptance.

Let merge-triggered deployment run or invoke the repository's declared standard
mechanism. Observe every declared workflow attributable to the landed revision.
Keep merged, deployment started, deployment succeeded, and production behavior
proved as separate claims.

A successful merge or CI run does not prove production. If deployment succeeds
but no attributable production oracle exists, report production proof as
`Cannot verify`. If rollout fails, use only the accepted safe recovery path;
rollback requires its own authority when not already accepted.

Return the exact landed commit, PR and merge state, deployment evidence,
production evidence or `Cannot verify`, cleanup state, and unresolved risk.

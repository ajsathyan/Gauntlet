---
name: ship
description: Use after independent verification to create coherent Git changes and perform only explicitly authorized push, pull-request, merge, deployment, or production effects.
---

# Ship

Move one exact verified revision through authorized Git and external effects. Shipping authority does not repair a failed Build, Architecture, or Sensor verdict.

## Authority

- “Commit” authorizes only the scoped local commit.
- “Push this branch” authorizes only the current branch push.
- “Open a PR” authorizes publication but not merge.
- “Merge” or “land” authorizes the repository's verified merge flow.
- Deployment, production changes, migrations, destructive actions, credentials, paid actions, rollback, installation, and task archival require their own accepted scope and authority.

## Procedure

1. Confirm the exact revision has passing Build, Architecture, and Sensor verdicts where applicable.
2. Inspect Git state and explicitly name intended paths. Preserve unrelated, untracked, or user-modified work.
3. Create coherent atomic commits. When parallel candidates exist, integrate only one current-base candidate at a time; base drift invalidates its proof and requires fresh integration and exact-candidate verification.
4. Use the existing generic Git, pull-request, merge, deployment, or production mechanism. Stop at the boundary of granted authority.
5. Verify the landed or externally changed revision with repository-owned evidence. Do not infer production health from pull-request checks.

## Output

Return scoped commit or pull-request state, exact-revision evidence, authorized external effects completed, cleanup state, and unresolved risk.

## Completion

Ship completes only through the last authorized stage. State explicitly when work is verified but not pushed, published but not merged, merged but not deployed, or deployed without production proof.

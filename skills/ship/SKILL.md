---
name: ship
description: Use after independent verification to carry an implementation through commit, pull request, and non-production merge, then request separate acceptance for production effects.
---

# Ship

Move one exact verified revision through authorized Git and external effects. Shipping authority does not repair a failed Build, Architecture, or Sensor verdict.

## Authority

- An implementation request authorizes scoped local commits, an implementation
  branch push, pull-request creation, and merge to the default branch.
- Do not ask for another acceptance between those ordinary implementation stages.
- If merge deploys, publishes, migrates, or otherwise changes production, merge
  is the production boundary and requires explicit acceptance first.
- Deployment and every other production change require separate explicit
  acceptance for the disclosed revision and effect.
- Installation, destructive or paid actions, credential use, rollback, and task
  archival retain separately scoped authority.

## Procedure

1. Confirm the exact revision has passing Build, Architecture, and Sensor verdicts where applicable.
2. Inspect Git state and explicitly name intended paths. Preserve unrelated, untracked, or user-modified work.
3. Create coherent atomic commits. When parallel candidates exist, integrate only one current-base candidate at a time; base drift invalidates its proof and requires fresh integration and exact-candidate verification.
4. Before merge, inspect repository automation and release documentation for a production consequence. Use the `land` skill immediately when merge is non-production.
5. At a production boundary, stop and present the acceptance request below. A concise user response accepts the listed production action; do not require the user to repeat the bullets. Revision or effect drift invalidates that acceptance.
6. After acceptance, use the existing deployment or production mechanism within the disclosed scope.
7. Verify the landed or externally changed revision with repository-owned evidence. Do not infer production health from pull-request checks.

## Production Acceptance Request

Name the production action, then provide bullets for:

- acceptance criteria met, with evidence;
- material product or engineering decisions made independently during implementation and their tradeoffs;
- unmet criteria, verification limits, and remaining risk;
- exact candidate revision and the production effect it will cause;
- rollback path and any limit on recoverability.

Never request acceptance with only a generic confirmation or a success-only
summary. Never perform the production action from implementation authority alone.

## Output

Return scoped commit, pull-request, and merge state; exact-revision evidence;
material decisions; authorized external effects completed; cleanup state; and
unresolved risk.

## Completion

Ship completes through non-production merge by default. At a production boundary,
it completes only through the last explicitly accepted effect. State explicitly
when work is merged but not deployed or deployed without production proof.

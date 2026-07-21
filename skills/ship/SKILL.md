---
name: ship
description: Use after independent verification to carry accepted work through merge, ordinary production deployment, monitoring, and attributable production proof.
---

# Ship

Carry one exact verified revision through the accepted Git and production
lifecycle. Shipping authority does not repair a failed Build or Architecture
verdict.

## Authority

- For a Normal Request, the implementation request authorizes the scoped ordinary lifecycle. For non-trivial work, the accepted Design/PRD authorizes it.
- Do not request another acceptance between commit, pull request, merge, and the repository's ordinary declared production deployment.
- Merge-triggered deployment proceeds automatically. If the repository declares a separate standard deployment command or API for accepted work, invoke it after merge.
- Stop for effects outside the accepted scope and for unexpected destructive, paid, credential, migration, privacy, security, or preservation risk.
- Installation and rollback retain separately scoped authority.

## Procedure

1. Confirm the exact revision has passing Build and applicable Architecture verdicts.
2. Inspect Git state, repository automation, deployment documentation, production oracle, and rollback path. Preserve unrelated work.
3. Use `land` to commit, push, open or update the pull request, wait for required CI and review, merge to the default branch, and verify the landed revision.
4. Let merge-triggered deployment run or invoke the declared standard deployment mechanism. Do not invent a generic deploy command.
5. Monitor exact-revision deployment evidence and exercise the repository's attributable production oracle. Do not infer production health from pull-request checks or a successful merge alone.
6. If rollout fails, follow the repository's safe recovery path inside accepted authority. Stop before rollback when it requires separate authority.

## Output

Return exact commit, pull-request and merge state, deployment state, production
evidence and its limits, cleanup state, material decisions, and unresolved risk.
Keep implemented, committed, pushed, merged, deployed, and production-proved as
separate claims.

## Completion

Ship completes when the accepted revision is merged, its ordinary deployment is
accounted for, attributable production proof passes or is explicitly unavailable,
and safe cleanup is complete.

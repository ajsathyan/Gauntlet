---
name: refactor-codebase
description: Simplify or rebuild a broad existing codebase while preserving evidenced behavior and proving replacement before retirement.
---

# Refactor Codebase

Use for broad or destructive simplification. Work in the current branch or a
worktree by default; use an independent destination only when source immutability,
experimentation, or explicit authority requires it.

## Safety core

1. Bind the source revision and preserve unrelated work.
2. Inventory observable capabilities, callers, public imports, state readers,
   operator paths, side effects, and recovery paths.
3. Record only material parity and compatibility rows: behavior, current owner,
   intended owner, callers, proof, and retirement condition.
4. Give policy, state, and side effects one authoritative owner. Prove ownership
   through real imports and calls, not a manifest.
5. Migrate one vertical slice: introduce the owner, route a real caller, prove
   behavior/state/compatibility, then retire its old path.
6. Delete only after every live caller, state reader, operator flow, and recovery
   path has passing replacement proof or is proved unreachable.
7. Preserve an incomplete isolated candidate by returning its exact repository or
   worktree path, revision, tree, diff identity, verdicts, and remaining checks.
   Never auto-promote failed work.

Exercise compatibility where mature systems break: import orders, fresh processes,
supported direct calls, injection or monkeypatch seams, exact CLI defaults/output,
saved-state readers, and accepted legacy routes. For stateful paths target retries,
duplicates, idempotency, crash/restart, concurrency, stale generations, rollback,
retention, and boundary limits. When architecture quality matters, make one
representative extension and check that it touches one owner without unrelated
adapter changes.

## Conditional machinery

Use an independent destination, durable ledgers, multiple architecture proposals,
specialist review, dual-run, or extensive phase artifacts only when consequence,
scale, repeated failure, or explicit request earns their cost. Stop creating
artifacts once they stop changing decisions or finding defects.

Complete only when capability and compatibility obligations pass, replacement
owners serve real callers, deletion conditions pass, temporary scaffolding is
removed or accepted, and exact before/after evidence is reported.

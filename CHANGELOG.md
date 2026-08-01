# Changelog

## Unreleased

- Make Gauntlet the single canonical workflow source and remove the final retired local-document reference.
- Reduce CI consumption by running Gauntlet's complete pull-request verification in one job without a duplicate main-branch run, enforcing only repository-required checks during Land, and limiting Ship to observation of already-triggered deployments.

## 3.0.0 - 2026-07-27

- Reset Gauntlet around a compact, proportional workflow and removed controllers, queues, context machinery, specialist handoffs, release simulations, unsupported compatibility paths, and obsolete infrastructure.
- Renamed the current product to Gauntlet and rewrote the README around Gauntlet 3, GPT-5.6 Sol in Codex, the Research/Normal/Material request paths, and the owner-controlled repository lifecycle.
- Added `orchestrate` as the required implementation procedure while keeping requirements, approvals, and integration in the main Codex task.
- Kept exact-candidate verification, consistent pull-request landing, declared deployment follow-through, the six-lens Design review for material work, and the refactor safety core.

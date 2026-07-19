# Workflow Helpers

Use a helper only when its mechanical loop saves more attention than it costs.
Helper output is an evidence pointer, never product truth or proof by itself.

| Need | Helper |
| --- | --- |
| Changed-surface discovery | `scripts/diff-intel.py "$PROJECT_ROOT"` |
| Proportional test selection | `scripts/test-plan.py "$PROJECT_ROOT"` |
| Bounded reviewer context | `scripts/review-pack.py "$PROJECT_ROOT"` |
| Durable Design profile | `scripts/gauntlet.py docs ensure --project-root "$PROJECT_ROOT"` |
| Create a Design | `scripts/gauntlet.py docs design create --project-root "$PROJECT_ROOT" --title "$TITLE"` |
| Accept a Design | `scripts/gauntlet.py docs design accept --project-root "$PROJECT_ROOT" --design "$DESIGN_ID"` |
| Fast sensor pass | `scripts/gauntlet.py sensors run --project-root "$PROJECT_ROOT" --workflow-mode feature --phase fast --json` |
| Integrated sensor pass | `scripts/gauntlet.py sensors run --project-root "$PROJECT_ROOT" --workflow-mode feature --phase integrated --json` |
| Current-base integration queue | `scripts/gauntlet.py workstreams snapshot --repo "$PROJECT_ROOT" --state "$QUEUE_FILE"` |
| Pull-request preparation | `scripts/gauntlet.py merge prepare --git-root "$PROJECT_ROOT" --handoff "$HANDOFF" --json` |
| Read-only merge preflight | `scripts/gauntlet.py merge plan --git-root "$PROJECT_ROOT" --handoff "$HANDOFF" --body "$PR_BODY" --json` |
| Explicitly authorized landing | `scripts/gauntlet.py land execute --git-root "$PROJECT_ROOT" --handoff "$HANDOFF" --body "$PR_BODY" --json` |

## Boundaries

- The accepted Design and its exact `Acceptance` section own product intent.
- Build planning and workstream assignments stay ephemeral.
- Native Codex task state owns live coordination. Use a worktree for disjoint
  write-heavy lanes when isolation earns its cost.
- The parent keeps user decisions, shared contracts, integration, publication,
  merge, release, and rollback.
- Integrate one current-base candidate at a time. Base drift invalidates stale
  proof.
- Keep stable instructions first and volatile workstream values last. Omit
  unrelated history, empty fields, and repeated contract text.
- Sensor handoffs contain only compact attention items. Open referenced raw logs
  only when a finding requires them.
- Preserve unrelated dirty work.
- Confidence labels, receipts, green commands, and pull-request checks do not
  replace an observable oracle.
- Deferred helper ideas stay deferred until repeated evidence shows a low-risk
  mechanical loop.

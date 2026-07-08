# Workflow Speedup Helpers

Use these helpers when the matching manual loop appears. They are advisory unless a command explicitly performs an accepted action.

## Commands

| Manual loop | Command |
| --- | --- |
| Changed-surface discovery | `scripts/diff-intel.py "$PROJECT_ROOT"` |
| Test selection | `scripts/test-plan.py "$PROJECT_ROOT"` |
| Reviewer/subagent packet | `scripts/review-pack.py "$PROJECT_ROOT"` |
| Review packet with Implementation Memory | `scripts/review-pack.py "$PROJECT_ROOT" --implementation-memory "$MEMORY_PATH"` |
| Implementation Memory structure check | `scripts/gauntlet.py memory lint --path "$MEMORY_PATH"` |
| PR/changelog draft | `scripts/gauntlet.py changelog pr --implementation-memory "$MEMORY_PATH" --git-root "$PROJECT_ROOT"` |
| Follow-up note | `scripts/gauntlet.py followup note ...` |
| Follow-up thread packet | `scripts/gauntlet.py followup thread --content "$FOLLOWUP_FILE" --title "$THREAD_TITLE" --json` |

## Boundaries

- Honor confidence and `Cannot verify`; helper output is not proof.
- Preserve unrelated dirty worktree changes.
- Implementation Memory remains the source for intent, scope, edge cases, verification expectations, and follow-ups.
- GitHub metadata verifies objective PR facts only.
- Follow-up thread helpers emit `create_thread` app-action packets; create the actual Codex thread with app tools after checking the packet.
- Child implementation lanes should use separate git worktrees by default when they write code, edit multiple files, or have uncertain ownership. Read-only review, exploration, summarization, and log-analysis lanes do not need worktrees by default.
- Child thread titles should preserve the Gauntlet priority prefix and add lane/status tags, such as `p1-auto: [C1][In Progress] Backend policy layer`.
- The main chat owns the child-lane ledger, user questions, merge decisions, and final synthesis. Child chats return compact reports and archive after their reports are integrated.
- Keep `quality-check --surface ...`, `.gitignore` suggestions, broad worktree dependency classification, Mermaid rendering, and multi-repo attribution deferred until repeated runs prove a low-risk mechanical loop.

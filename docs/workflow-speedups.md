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
| Local analytics event | `scripts/gauntlet.py analytics emit --project-root "$PROJECT_ROOT" --run-id "$RUN_ID" --event-type "$EVENT_TYPE"` |
| Local closeout facts | `scripts/gauntlet.py analytics closeout --project-root "$PROJECT_ROOT" --run-id "$RUN_ID" --file-changed "$PATH" --proof "$COMMAND" --risk "$RISK"` |
| Release-candidate impact summary | `scripts/gauntlet.py analytics summarize --project-root "$PROJECT_ROOT" --baseline "$BASELINE" --candidate "$CANDIDATE"` |
| Bounded attempt memory | `scripts/gauntlet.py attempt-memory add --project-root "$PROJECT_ROOT" --run-id "$RUN_ID" --kind proof_failure --fingerprint "$FINGERPRINT" --summary "$SUMMARY"` |
| PR/changelog draft | `scripts/gauntlet.py changelog pr --implementation-memory "$MEMORY_PATH" --git-root "$PROJECT_ROOT"` |
| Contextual merge handoff | `scripts/gauntlet.py merge prepare --git-root "$PROJECT_ROOT" --handoff .gauntlet/merge-handoff.json --body-output .gauntlet/pr-body.md --json` |
| Merge preflight | `scripts/gauntlet.py merge plan --git-root "$PROJECT_ROOT" --handoff .gauntlet/merge-handoff.json --body .gauntlet/pr-body.md --json` |
| Authorized merge execution | `scripts/gauntlet.py merge execute --git-root "$PROJECT_ROOT" --handoff .gauntlet/merge-handoff.json --body .gauntlet/pr-body.md --json` |
| Archive Summary display | `scripts/gauntlet.py archive plan --content "$CHANGELOG_OR_CLOSEOUT" --title "$THREAD_TITLE" --git-root "$PROJECT_ROOT"` |
| Follow-up note | `scripts/gauntlet.py followup note ...` |
| Follow-up thread packet | `scripts/gauntlet.py followup thread --content "$FOLLOWUP_FILE" --title "$THREAD_TITLE" --json` |

## Boundaries

- Honor confidence and `Cannot verify`; helper output is not proof.
- Preserve unrelated dirty worktree changes.
- Implementation Memory remains the source for intent, scope, edge cases, verification expectations, and follow-ups.
- Local analytics writes only under `.gauntlet/analytics/` by default, using local salted hashes for repo, branch, file, command, and fingerprint details.
- Release-candidate summaries require explicit `--baseline` and `--candidate` labels; if either is missing, the helper asks for them instead of guessing.
- Closeout facts are deliberately small: files changed, proof/tests completed, unresolved risks, and optional attempt-memory expiry. They do not commit, push, merge, generate changelogs, publish release notes, or archive threads.
- Attempt memory is a local bounded scratchpad. Repeated fingerprints are summarized, old entries can be pruned with `--max-age-days`, and run-scoped entries can be expired with `analytics closeout --expire-attempt-memory`.
- PR/changelog output should carry the agent-authored Archive Summary; archive planning reuses that short block instead of replaying the transcript.
- GitHub metadata verifies objective PR facts only.
- Follow-up thread helpers emit `create_thread` app-action packets; create the actual Codex thread with app tools after checking the packet.
- Child implementation lanes should use separate git worktrees by default when they write code, edit multiple files, or have uncertain ownership. Read-only review, exploration, summarization, and log-analysis lanes do not need worktrees by default.
- Native Codex state owns child progress; use stable lane ids only in bounded packets and returned reports when the main task needs a coordination handle.
- The main chat owns the child-lane ledger, user questions, merge decisions, and final synthesis. Child chats return compact reports and do not direct-push to `main`.
- Keep `quality-check --surface ...`, `.gitignore` suggestions, broad worktree dependency classification, Mermaid rendering, and multi-repo attribution deferred until repeated runs prove a low-risk mechanical loop.

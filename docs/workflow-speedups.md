# Workflow Speedup Helpers

Use these helpers when the matching manual loop appears. They are advisory unless a command explicitly performs an accepted action.

## Commands

| Manual loop | Command |
| --- | --- |
| Changed-surface discovery | `scripts/diff-intel.py "$PROJECT_ROOT"` |
| Test selection | `scripts/test-plan.py "$PROJECT_ROOT"` |
| Reviewer/child context pack | `scripts/review-pack.py "$PROJECT_ROOT"` |
| Review packet with accepted context | `scripts/review-pack.py "$PROJECT_ROOT" --accepted-spec "$SPEC_PATH" --plan "$PLAN_PATH"` |
| Local analytics event | `scripts/gauntlet.py analytics emit --project-root "$PROJECT_ROOT" --run-id "$RUN_ID" --event-type "$EVENT_TYPE"` |
| Local closeout facts | `scripts/gauntlet.py analytics closeout --project-root "$PROJECT_ROOT" --run-id "$RUN_ID" --file-changed "$PATH" --proof "$COMMAND" --risk "$RISK"` |
| Release-candidate impact summary | `scripts/gauntlet.py analytics summarize --project-root "$PROJECT_ROOT" --baseline "$BASELINE" --candidate "$CANDIDATE"` |
| Bounded attempt memory | `scripts/gauntlet.py attempt-memory add --project-root "$PROJECT_ROOT" --run-id "$RUN_ID" --kind proof_failure --fingerprint "$FINGERPRINT" --summary "$SUMMARY"` |
| PR/changelog draft | `scripts/gauntlet.py changelog pr --accepted-spec "$SPEC_PATH" --plan "$PLAN_PATH" --git-root "$PROJECT_ROOT"` |
| Local document profile | `scripts/gauntlet.py docs init --project-root "$PROJECT_ROOT" --epic-prefix "$PREFIX"` |
| Local document check | `scripts/gauntlet.py docs check --project-root "$PROJECT_ROOT"` |
| Stable local epic | `scripts/gauntlet.py docs epic create --project-root "$PROJECT_ROOT" --title "$TITLE"` |
| PRD execution contract | `docs/prd-execution.md` |
| Contextual merge handoff | `scripts/gauntlet.py merge prepare --git-root "$PROJECT_ROOT" --title "$PR_TITLE" --changelog "$CHANGELOG_BULLET" --problem "$PROBLEM" --solution "$SOLUTION" --testing "$TESTING" --pr-note "$PR_NOTE"` |
| Merge preflight | `scripts/gauntlet.py merge plan --git-root "$PROJECT_ROOT" --json` |
| Authorized merge | `scripts/gauntlet.py merge execute --git-root "$PROJECT_ROOT" --json` |
| Archive Summary display | `scripts/gauntlet.py archive plan --content "$CHANGELOG_OR_CLOSEOUT" --title "$THREAD_TITLE" --git-root "$PROJECT_ROOT"` |
| Follow-up note | `scripts/gauntlet.py followup note ...` |
| Follow-up thread packet | `scripts/gauntlet.py followup thread --content "$FOLLOWUP_FILE" --title "$THREAD_TITLE" --json` |

## Boundaries

- Honor confidence and `Cannot verify`; helper output and child receipts are evidence pointers, not proof. Resolve commands or artifacts against the relevant oracle.
- Preserve unrelated dirty worktree changes.
- The accepted spec and canonical plan remain the sources for intent, scope, edge cases, verification expectations, and follow-ups.
- For PRD-backed work, the PRD is the human source and the generated Ticket Graph is the run plan. Compile only the explicit build-ready target.
- When `doc_org.md` is active, local canonical documents live in the primary worktree; linked worktrees must not create alternate copies.
- `memory lint` and `--implementation-memory` remain deprecated compatibility inputs for one migration window; new work must not create a third intent artifact.
- Local analytics writes only under `.gauntlet/analytics/` by default, using local salted hashes for repo, branch, file, command, and fingerprint details.
- Release-candidate summaries require explicit `--baseline` and `--candidate` labels; if either is missing, the helper asks for them instead of guessing.
- Closeout facts are deliberately small: files changed, proof/tests completed, unresolved risks, and optional attempt-memory expiry. They do not commit, push, merge, generate changelogs, publish release notes, or archive threads.
- Attempt memory is a local bounded scratchpad. Repeated fingerprints are summarized, old entries can be pruned with `--max-age-days`, and run-scoped entries can be expired with `analytics closeout --expire-attempt-memory`.
- PR/changelog output should carry the agent-authored Archive Summary; archive planning reuses that short block instead of replaying the transcript.
- Archive planning fails closed when that content or section is missing and emits `present_archive_summary` immediately before `archive_thread`.
- GitHub metadata verifies objective PR facts only.
- Follow-up thread helpers emit `create_thread` app-action packets; create the actual Codex thread with app tools after checking the packet.
- Child implementation lanes should use separate git worktrees by default when they write code, edit multiple files, or have uncertain ownership. Read-only review, exploration, summarization, and log-analysis lanes do not need worktrees by default.
- Native Codex state owns child progress; use stable lane ids rather than title/status churn.
- The main chat owns user questions, the oracle, independent evidence verification, merge decisions, and final synthesis. It integrates child commits into one branch with targeted checks as they arrive, runs combined proof after all required tickets finish, and opens one final PR. Child chats return compact reports and archive after integration.
- Schedule ready tickets by critical path and unlock value, preserve useful agent affinity, land interfaces first, and integrate continuously. Use selective cohort barriers for shared invariants instead of a global wait after every child.
- Materialize bounded child context from stable instructions, one ticket, relevant versioned shared context, named dependencies, and owned source. Stable prefixes can improve cache reuse, but no helper may claim a guaranteed cache hit.
- After an Execution Run starts, recover from its source lock, manifest, and resume file; use the append-only event stream only for debugging.
- Keep `quality-check --surface ...`, `.gitignore` suggestions, broad worktree dependency classification, Mermaid rendering, and multi-repo attribution deferred until repeated runs prove a low-risk mechanical loop.

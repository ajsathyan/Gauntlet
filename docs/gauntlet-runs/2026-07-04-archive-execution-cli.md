# Archive Execution CLI

Date: 2026-07-04
Scope: Add a small deterministic CLI for archive planning/execution, install verification, follow-up note formatting, saved diagram lookup, and thread-level change retrieval.
Proof scope: delta.

## Assumptions

- Codex app actions such as thread rename, archive, and new-thread creation remain agent/app-owned, not shell-owned.
- Git and GitHub facts should be code-owned when they are objective: dirty state, upstream divergence, PR checks, mergeability, and merge command shape.
- `archive anyway` should bypass unresolved strong follow-ups, but should not bypass dirty, unpushed, or unmerged code without an explicit git-risk confirmation.

## Decisions

- Keep `scripts/check-workflow-etiquette.py` as the etiquette classifier and add `scripts/gauntlet.py` as the higher-level CLI executor.
- Use merge commits for automatic PR merges: `gh pr merge <number> --merge --delete-branch`.
- Leave `archive_thread` and `set_thread_title` as returned app actions so the Codex app tools execute them.
- Support `--allow-dirty` for intentionally parked local files and `--confirm-git-risk` for explicit user-confirmed abandonment.
- Add thread changelog documentation so future chats can retrieve the PR history and follow-up lanes without reading the whole trace.

## Exceptions

- Follow-up thread creation is still not automated because creating a user-owned Codex thread needs app-tool execution and a product decision on when to fork versus continue.
- Multi-repo attribution is still not automated.
- The CLI does not poll GitHub checks; it plans/executes from the current PR state. The agent or a future workflow runner can wait and rerun.

## Proof

- `python3 scripts/check-gauntlet-workflow.py`

## Production Quality Bar

Not relevant because this is workflow/tooling automation, not an application launch surface.

## Coverage Gap Candidates

None.

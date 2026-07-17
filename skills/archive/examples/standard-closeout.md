# Standard Closeout

User request: `/Archive`

Expected behavior:

1. Verify the accepted work and list only its changed paths.
2. Determine whether the branch belongs to an Execution Run and create the Archive Summary.
3. For a non-run patch, create a temporary schema v1 handoff and run one `gauntlet.py closeout execute` command. For a run-backed branch, use `merge prepare|plan|execute --run <run>`, then the archive planner; never substitute the v1 handoff.
4. Verify the landed revision, run any established revision-attributable post-merge monitor, then sync the local default branch and safely remove the remote branch, isolated worktree, and local branch.
5. Stop and preserve cleanup state if checks, monitoring, merge verification, or deletion safety fails.
6. Execute `set_thread_title`, `present_archive_summary`, and `archive_thread` in the returned order only after Git closeout passes.

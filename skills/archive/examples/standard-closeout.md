# Standard Closeout

User request: `/Archive`

Expected behavior:

1. Verify the accepted work and list only its changed paths.
2. Determine whether the branch belongs to an Execution Run and create the Archive Summary.
3. For a non-run patch, create a temporary schema v1 handoff and run one `gauntlet.py closeout execute` command. For a run-backed branch, use `merge prepare|plan|execute --run <run>`, then the archive planner; never substitute the v1 handoff.
4. Stop if the command does not return `pass` or `warn`.
5. Execute `set_thread_title`, `present_archive_summary`, and `archive_thread` in the returned order.

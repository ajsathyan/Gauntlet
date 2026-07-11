# Standard Closeout

User request: `/Archive`

Expected behavior:

1. Verify the accepted work and list only its changed paths.
2. Create temporary handoff and Archive Summary files.
3. Run one `gauntlet.py closeout execute` command with those paths and the local install target.
4. Stop if the command does not return `pass` or `warn`.
5. Execute `set_thread_title`, `present_archive_summary`, and `archive_thread` in the returned order.

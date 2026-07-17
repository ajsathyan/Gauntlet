# Standard Closeout

User request: `/Archive`

Expected behavior:

1. Verify the accepted work and create the Archive Summary.
2. Load and complete the `land` skill, including landed-revision monitoring and safe cleanup.
3. Stop and preserve cleanup state if checks, monitoring, merge verification, or deletion safety fails.
4. Install and verify the landed revision only when the user explicitly requests it.
5. Run the archive planner with the Archive Summary.
6. Execute `set_thread_title`, `present_archive_summary`, and `archive_thread` in the returned order.

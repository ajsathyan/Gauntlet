# Optional Agent Profiles

Custom Codex profiles are optional capabilities. They are useful when a bounded workstream clearly benefits from a specialized read-only, implementation, verification, research, security, or release posture. They are not a required scheduling layer.

## Choose directly

Use the parent task when the work is tightly coupled, small, or context-heavy. Use a native child when ownership or independent evidence makes delegation worthwhile.

Available profiles may include:

- a fast reader for bounded source discovery;
- a standard worker for clear implementation;
- a deep worker for cross-cutting implementation;
- an independent verifier for behavioral proof;
- a deep researcher for consequential research;
- a release integrator for bounded release preparation.

The child’s prompt supplies authority and ownership. A profile never grants additional permission. If no profile clearly improves the work, use the native default or keep the work in the parent.

## Compact assignment

Send only:

- the requested outcome slice;
- owned files or state;
- dependency contracts;
- constraints and authority;
- proportional proof;
- return contract and ask-parent policy.

Keep stable instructions first, volatile details last, and omit unrelated
history. The parent retains requested product meaning, shared contracts,
integration, publication, merge, release, and rollback.

## Security boundary

When a concrete credential, permission, paid/destructive authority, migration, or production consequence triggers security review, use the dedicated runner:

```sh
python3 "$GAUNTLET_ROOT/scripts/security-review.py" \
  --workspace "$WORKTREE" \
  --ticket-file "$SECURITY_TICKET" \
  --output "$SECURITY_REVIEW_OUTPUT"
```

The runner is non-interactive and read-only. Keep its optional output outside the reviewed workspace. Ordinary work does not pay for this review.

## Completion

Children return changed artifacts, compact proof, and unresolved risk. The parent independently resolves evidence and sends the exact integrated candidate to Verify. Native task state is sufficient for live coordination.
